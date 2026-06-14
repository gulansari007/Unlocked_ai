import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from config.settings import settings
from providers.base import BaseLLMClient, ChatMessage, LLMResponse, LLMStreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)

class OllamaClient(BaseLLMClient):
    """
    Client adapter for local Ollama server.
    Interacts with Ollama's /api/chat endpoint.
    """
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip('/')
        self.endpoint = f"{self.base_url}/api/chat"

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            item = {"role": msg.role}
            if msg.content is not None:
                item["content"] = msg.content
            
            if msg.role == "assistant" and msg.tool_calls:
                # Ollama function tool format
                item["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
            formatted.append(item)
        return formatted

    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
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
        model_name = model or settings.default_ollama_model
        payload = {
            "model": model_name,
            "messages": self._format_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature,
                **kwargs
            }
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(self.endpoint, json=payload)
            response.raise_for_status()
            data = response.json()

            message = data.get("message", {})
            content = message.get("content")
            
            tool_calls = None
            if "tool_calls" in message and message["tool_calls"]:
                tool_calls = []
                for idx, tc in enumerate(message["tool_calls"]):
                    func = tc.get("function", {})
                    args_val = func.get("arguments", {})
                    # Standardize arguments as a JSON string
                    args_str = json.dumps(args_val) if not isinstance(args_val, str) else args_val
                    tool_calls.append(
                        ToolCall(
                            id=f"ollama_{idx}", # Ollama doesn't always return unique call IDs
                            name=func.get("name", ""),
                            arguments=args_str
                        )
                    )

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
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
        model_name = model or settings.default_ollama_model
        payload = {
            "model": model_name,
            "messages": self._format_messages(messages),
            "stream": True,
            "options": {
                "temperature": temperature,
                **kwargs
            }
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", self.endpoint, json=payload) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        chunk_data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse Ollama stream line: {line}")
                        continue
                        
                    message = chunk_data.get("message", {})
                    content_delta = message.get("content")
                    
                    tool_calls_delta = None
                    if "tool_calls" in message and message["tool_calls"]:
                        tool_calls_delta = []
                        for idx, tc in enumerate(message["tool_calls"]):
                            func = tc.get("function", {})
                            args_val = func.get("arguments", {})
                            args_str = json.dumps(args_val) if not isinstance(args_val, str) else args_val
                            tool_calls_delta.append(
                                ToolCall(
                                    id=f"ollama_{idx}",
                                    name=func.get("name", ""),
                                    arguments=args_str
                                )
                            )

                    yield LLMStreamChunk(
                        content_delta=content_delta,
                        tool_calls_delta=tool_calls_delta,
                        raw_chunk=chunk_data
                    )
