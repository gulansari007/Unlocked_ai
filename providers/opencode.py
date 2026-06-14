import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import httpx

from config.settings import settings
from providers.base import BaseLLMClient, ChatMessage, LLMResponse, LLMStreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)

class OpenCodeClient(BaseLLMClient):
    """
    Client adapter for OpenCode developer API and proxies.
    Utilizes standard OpenAI-compatible endpoints with custom Base URLs.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.opencode_api_key
        raw_base = base_url or settings.opencode_base_url
        
        # Ensure base_url ends correctly
        base = raw_base.rstrip('/')
        if not base.endswith('/chat/completions') and not base.endswith('/chat'):
            self.endpoint = f"{base}/chat/completions"
        else:
            self.endpoint = base

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _format_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            item = {"role": msg.role}
            if msg.content is not None:
                item["content"] = msg.content
            
            if msg.role == "assistant" and msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments
                        }
                    }
                    for tc in msg.tool_calls
                ]
                
            if msg.role == "tool":
                item["tool_call_id"] = msg.tool_call_id
                item["name"] = msg.name
                
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
        model_name = model or settings.default_opencode_model
        payload = {
            "model": model_name,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            **kwargs
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.endpoint,
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            choice = data["choices"][0]
            message = choice["message"]
            
            tool_calls = None
            if "tool_calls" in message and message["tool_calls"]:
                tool_calls = [
                    ToolCall(
                        id=tc["id"],
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"]
                    )
                    for tc in message["tool_calls"]
                ]

            return LLMResponse(
                content=message.get("content"),
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
        model_name = model or settings.default_opencode_model
        payload = {
            "model": model_name,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if tools:
            payload["tools"] = self._format_tools(tools)

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                self.endpoint,
                headers=self._get_headers(),
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            chunk_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse OpenCode stream chunk: {line}")
                            continue

                        choice = chunk_data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        
                        content_delta = delta.get("content")
                        
                        tool_calls_delta = None
                        if "tool_calls" in delta and delta["tool_calls"]:
                            tool_calls_delta = []
                            for tc in delta["tool_calls"]:
                                name = tc.get("function", {}).get("name")
                                args = tc.get("function", {}).get("arguments")
                                tool_calls_delta.append(
                                    ToolCall(
                                        id=tc.get("id", ""),
                                        name=name if name else "",
                                        arguments=args if args else ""
                                    )
                                )

                        yield LLMStreamChunk(
                            content_delta=content_delta,
                            tool_calls_delta=tool_calls_delta,
                            raw_chunk=chunk_data
                        )
