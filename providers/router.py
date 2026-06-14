import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from config.settings import settings
from config.providers import parse_model_string, PROVIDERS
from providers.base import BaseLLMClient, ChatMessage, LLMResponse, LLMStreamChunk, ToolDefinition
from providers.openrouter import OpenRouterClient
from providers.opencode import OpenCodeClient
from providers.ollama import OllamaClient
from providers.gemini import GeminiClient
from providers.groq import GroqClient
from providers.openai import OpenAIClient
from providers.anthropic import AnthropicClient

logger = logging.getLogger(__name__)

class MultiProviderRouter(BaseLLMClient):
    """
    Unified LLM client router for Unlocked AI.
    Inspects model identifiers and transparently routes calls to:
    - OpenRouterClient
    - OpenCodeClient
    - OllamaClient
    - GeminiClient
    - GroqClient
    - OpenAIClient
    - AnthropicClient
    """
    def __init__(self):
        self._clients: Dict[str, BaseLLMClient] = {}
        self.override_model: Optional[str] = None

    def _get_client(self, provider: str) -> BaseLLMClient:
        provider = provider.lower()
        if provider not in PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")

        # Return cached instance if available
        if provider in self._clients:
            return self._clients[provider]

        # Check configuration safety first
        if provider == "openrouter":
            if not settings.is_provider_configured("openrouter"):
                raise ValueError("OpenRouter API key (OPENROUTER_API_KEY) is not configured.")
            client = OpenRouterClient()
        elif provider == "opencode":
            if not settings.is_provider_configured("opencode"):
                raise ValueError("OpenCode API key (OPENCODE_API_KEY) is not configured.")
            client = OpenCodeClient()
        elif provider == "ollama":
            # Ollama is local; we assume it is accessible if requested
            client = OllamaClient()
        elif provider == "gemini":
            if not settings.is_provider_configured("gemini"):
                raise ValueError("Google Gemini API key (GEMINI_API_KEY) is not configured.")
            client = GeminiClient()
        elif provider == "groq":
            if not settings.is_provider_configured("groq"):
                raise ValueError("Groq API key (GROQ_API_KEY) is not configured.")
            client = GroqClient()
        elif provider == "openai":
            if not settings.is_provider_configured("openai"):
                raise ValueError("OpenAI API key (OPENAI_API_KEY) is not configured.")
            client = OpenAIClient()
        elif provider == "anthropic":
            if not settings.is_provider_configured("anthropic"):
                raise ValueError("Anthropic API key (ANTHROPIC_API_KEY) is not configured.")
            client = AnthropicClient()
        else:
            raise ValueError(f"No adapter registered for provider: {provider}")

        self._clients[provider] = client
        return client


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
        Dynamically route a non-streaming generation request to the proper client.
        """
        if self.override_model:
            model = self.override_model

        if not model:
            # Fallback to Gemini or OpenRouter as default
            provider = "gemini" if settings.is_provider_configured("gemini") else "openrouter"
            target_model = settings.default_gemini_model if provider == "gemini" else settings.default_openrouter_model
        else:
            provider, target_model = parse_model_string(model)

        client = self._get_client(provider)
        logger.debug(f"Routing non-stream generate to provider '{provider}', model '{target_model}'")
        return await client.generate(
            messages=messages,
            model=target_model,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
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
        """
        Dynamically route a streaming generation request to the proper client.
        """
        if self.override_model:
            model = self.override_model

        if not model:
            provider = "gemini" if settings.is_provider_configured("gemini") else "openrouter"
            target_model = settings.default_gemini_model if provider == "gemini" else settings.default_openrouter_model
        else:
            provider, target_model = parse_model_string(model)

        client = self._get_client(provider)
        logger.debug(f"Routing stream generate to provider '{provider}', model '{target_model}'")
        
        async for chunk in client.generate_stream(
            messages=messages,
            model=target_model,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        ):
            yield chunk
