import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from config.settings import settings
from providers.base import BaseLLMClient, ChatMessage, LLMResponse, LLMStreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)

class AnthropicClient(BaseLLMClient):
    """
    Client adapter for Anthropic Claude API.
    Translates OpenAI/GenAI unified schemas to Anthropic messages/tools format.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key
        self.base_url = base_url or settings.anthropic_base_url
        if not self.base_url.endswith("/messages"):
            self.base_url = self.base_url.rstrip("/") + "/messages"

    def _get_headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

    def _format_messages_and_system(self, messages: List[ChatMessage]) -> tuple[List[Dict[str, Any]], Optional[str]]:
        system_instructions = []
        formatted = []

        for msg in messages:
            if msg.role == "system":
                if msg.content:
                    system_instructions.append(msg.content)
                continue

            content_blocks = []
            if msg.content:
                content_blocks.append({"type": "text", "text": msg.content})

            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    # Translate tool call args to dict
                    args = tc.arguments
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            pass
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": args
                    })

            if msg.role == "tool":
                content_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content or ""
                })
                # Anthropic tool results are submitted with role "user"
                role = "user"
            else:
                role = msg.role

            # Merge consecutive messages of same role (Anthropic requires strict alternating roles)
            if formatted and formatted[-1]["role"] == role:
                formatted[-1]["content"].extend(content_blocks)
            else:
                formatted.append({
                    "role": role,
                    "content": content_blocks
                })

        system = "\n\n".join(system_instructions) if system_instructions else None
        return formatted, system

    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters
            }
            for t in tools
        ]

    async def generate(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        model_name = model or settings.default_anthropic_model
        formatted_msgs, system = self._format_messages_and_system(messages)
        
        payload = {
            "model": model_name,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            **kwargs
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.base_url,
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            # Parse contents
            text_content = ""
            tool_calls = []

            for content_block in data.get("content", []):
                if content_block.get("type") == "text":
                    text_content += content_block.get("text", "")
                elif content_block.get("type") == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            id=content_block.get("id"),
                            name=content_block.get("name"),
                            arguments=json.dumps(content_block.get("input", {}))
                        )
                    )

            return LLMResponse(
                content=text_content if text_content else None,
                tool_calls=tool_calls if tool_calls else None,
                model_name=model_name,
                raw_response=data
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
        model_name = model or settings.default_anthropic_model
        formatted_msgs, system = self._format_messages_and_system(messages)
        
        payload = {
            "model": model_name,
            "messages": formatted_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            "stream": True,
            **kwargs
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = self._format_tools(tools)

        # We need to assemble tool use chunks manually, as they stream in parts
        current_tool_id = ""
        current_tool_name = ""
        current_tool_input = ""

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                self.base_url,
                headers=self._get_headers(),
                json=payload
            ) as response:
                response.raise_for_status()
                
                # Anthropic sends event-stream
                # Lines are like:
                # event: content_block_delta
                # data: {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hello"}}
                
                current_event = None
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        try:
                            event_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        content_delta = None
                        tool_calls_delta = None

                        if current_event == "content_block_start":
                            block = event_data.get("content_block", {})
                            if block.get("type") == "tool_use":
                                current_tool_id = block.get("id", "")
                                current_tool_name = block.get("name", "")
                                current_tool_input = ""

                        elif current_event == "content_block_delta":
                            delta = event_data.get("delta", {})
                            if delta.get("type") == "text_delta":
                                content_delta = delta.get("text")
                            elif delta.get("type") == "input_json_delta":
                                # Accumulate JSON arguments
                                json_part = delta.get("partial_json", "")
                                current_tool_input += json_part
                                # Return incremental delta to router
                                tool_calls_delta = [
                                    ToolCall(
                                        id=current_tool_id,
                                        name=current_tool_name,
                                        arguments=json_part
                                    )
                                ]

                        yield LLMStreamChunk(
                            content_delta=content_delta,
                            tool_calls_delta=tool_calls_delta,
                            raw_chunk=event_data
                        )
