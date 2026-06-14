import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from config.settings import settings
from providers.base import BaseLLMClient, ChatMessage, LLMResponse, LLMStreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)

class GeminiClient(BaseLLMClient):
    """
    Client adapter for Google Gemini API using the official google-genai SDK.
    Supports Gemini 1.5 and 2.0 specs.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.gemini_api_key
        # We import genai inside to avoid loading overhead or errors if not installed
        from google import genai
        self.client = genai.Client(api_key=self.api_key)

    def _dict_to_gemini_schema(self, d: Dict[str, Any]) -> Any:
        from google.genai import types
        if not isinstance(d, dict):
            return None
            
        s_type = d.get("type", "string").upper()
        properties = {}
        if "properties" in d:
            for k, v in d["properties"].items():
                prop_schema = self._dict_to_gemini_schema(v)
                if prop_schema:
                    properties[k] = prop_schema
                    
        required = d.get("required")
        items = None
        if "items" in d:
            items = self._dict_to_gemini_schema(d["items"])
            
        return types.Schema(
            type=s_type,
            properties=properties if properties else None,
            required=required if required else None,
            items=items if items else None,
            description=d.get("description")
        )

    def _build_config_and_contents(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> tuple:
        from google.genai import types

        # Extract system instructions
        system_msgs = [m.content for m in messages if m.role == "system" and m.content]
        system_instruction = "\n".join(system_msgs) if system_msgs else None

        # Build tools list
        gemini_tools = None
        if tools:
            function_declarations = []
            for t in tools:
                schema = self._dict_to_gemini_schema(t.parameters)
                func_decl = types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters=schema
                )
                function_declarations.append(func_decl)
            
            gemini_tools = [types.Tool(function_declarations=function_declarations)]

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            tools=gemini_tools
        )

        # Build contents
        contents = []
        for msg in messages:
            if msg.role == "system":
                continue
            
            # Gemini roles: 'user' or 'model'
            gemini_role = "user" if msg.role in ("user", "tool") else "model"
            parts = []

            if msg.role == "tool":
                # A tool response part in Gemini SDK
                # Response is expected to be a dictionary structure representing the output
                try:
                    resp_val = json.loads(msg.content) if msg.content else {}
                except json.JSONDecodeError:
                    resp_val = {"output": msg.content}
                    
                parts.append(
                    types.Part.from_function_response(
                        name=msg.name or "",
                        response={"result": resp_val}
                    )
                )
            else:
                if msg.content:
                    parts.append(types.Part.from_text(text=msg.content))
                
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        try:
                            args_dict = json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                        except json.JSONDecodeError:
                            args_dict = {"arguments": tc.arguments}
                        parts.append(
                            types.Part.from_function_call(
                                name=tc.name,
                                args=args_dict
                            )
                        )

            if parts:
                contents.append(types.Content(role=gemini_role, parts=parts))

        return config, contents

    async def generate(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        model_name = model or settings.default_gemini_model
        config, contents = self._build_config_and_contents(messages, tools, temperature, max_tokens)

        # Execute async call
        response = await self.client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
            **kwargs
        )

        tool_calls = None
        if response.function_calls:
            tool_calls = []
            for fc in response.function_calls:
                # Format args as a JSON string
                args_str = json.dumps(fc.args) if fc.args else "{}"
                # Generate unique ID since Gemini SDK function call ID might be empty
                fc_id = getattr(fc, "id", None) or f"gemini_{fc.name}"
                tool_calls.append(
                    ToolCall(
                        id=fc_id,
                        name=fc.name,
                        arguments=args_str
                    )
                )

        return LLMResponse(
            content=response.text,
            tool_calls=tool_calls,
            model_name=model_name,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else {}
        )

    async def generate_stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        model_name = model or settings.default_gemini_model
        config, contents = self._build_config_and_contents(messages, tools, temperature, max_tokens)

        response_stream = await self.client.aio.models.generate_content_stream(
            model=model_name,
            contents=contents,
            config=config,
            **kwargs
        )

        async for chunk in response_stream:
            content_delta = chunk.text
            
            tool_calls_delta = None
            if chunk.function_calls:
                tool_calls_delta = []
                for fc in chunk.function_calls:
                    args_str = json.dumps(fc.args) if fc.args else "{}"
                    fc_id = getattr(fc, "id", None) or f"gemini_{fc.name}"
                    tool_calls_delta.append(
                        ToolCall(
                            id=fc_id,
                            name=fc.name,
                            arguments=args_str
                        )
                    )

            yield LLMStreamChunk(
                content_delta=content_delta,
                tool_calls_delta=tool_calls_delta,
                raw_chunk=chunk.model_dump() if hasattr(chunk, "model_dump") else {}
            )
