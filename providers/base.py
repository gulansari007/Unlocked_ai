from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field

class ToolDefinition(BaseModel):
    """
    Schema representing a tool that can be called by the model.
    Based on JSON Schema format.
    """
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema description of parameters

class ToolCall(BaseModel):
    """
    Schema representing a tool call request from the model.
    """
    id: str
    name: str
    arguments: str  # JSON-serialized string of arguments

class ChatMessage(BaseModel):
    """
    Schema representing a chat message.
    """
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: Optional[str] = None
    name: Optional[str] = None  # Needed for 'tool' role (holds the function name)
    tool_call_id: Optional[str] = None  # Needed for 'tool' role (links to the request ToolCall ID)
    tool_calls: Optional[List[ToolCall]] = None  # Present in assistant messages if they invoke tools

class LLMResponse(BaseModel):
    """
    Schema representing a completed response from the LLM.
    """
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    model_name: str
    raw_response: Dict[str, Any] = Field(default_factory=dict)

class LLMStreamChunk(BaseModel):
    """
    Schema representing a single chunk returned from a streaming LLM request.
    """
    content_delta: Optional[str] = None
    tool_calls_delta: Optional[List[ToolCall]] = None
    raw_chunk: Dict[str, Any] = Field(default_factory=dict)

class BaseLLMClient(ABC):
    """
    Interface definition for all LLM providers in Unlocked AI.
    """
    @abstractmethod
    async def generate(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Generate a non-streaming response for a given list of chat messages.
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs: Any
    ) -> AsyncGenerator[LLMStreamChunk, None]:
        """
        Generate a streaming response for a given list of chat messages.
        """
        pass
