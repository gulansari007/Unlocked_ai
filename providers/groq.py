import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from groq import AsyncGroq

from config.settings import settings
from providers.base import BaseLLMClient, ChatMessage, LLMResponse, LLMStreamChunk, ToolCall, ToolDefinition

logger = logging.getLogger(__name__)

class GroqClient(BaseLLMClient):
    """
    Client adapter for Groq API using the official groq SDK.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.groq_api_key
        self.client = AsyncGroq(api_key=self.api_key)

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
        model_name = model or settings.default_groq_model
        params = {
            "model": model_name,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            **kwargs
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = self._format_tools(tools)

        response = await self.client.chat.completions.create(**params)
        
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments
                )
                for tc in message.tool_calls
            ]

        return LLMResponse(
            content=message.content,
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
        model_name = model or settings.default_groq_model
        params = {
            "model": model_name,
            "messages": self._format_messages(messages),
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if tools:
            params["tools"] = self._format_tools(tools)

        stream = await self.client.chat.completions.create(**params)
        
        async for chunk in stream:
            choice = chunk.choices[0]
            delta = choice.delta
            
            content_delta = delta.content
            
            tool_calls_delta = None
            if delta.tool_calls:
                tool_calls_delta = [
                    ToolCall(
                        id=tc.id or "",
                        name=tc.function.name or "",
                        arguments=tc.function.arguments or ""
                    )
                    for tc in delta.tool_calls
                ]

            yield LLMStreamChunk(
                content_delta=content_delta,
                tool_calls_delta=tool_calls_delta,
                raw_chunk=chunk.model_dump() if hasattr(chunk, "model_dump") else {}
            )
