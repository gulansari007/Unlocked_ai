import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from providers.router import MultiProviderRouter
from providers.base import ChatMessage, LLMResponse

class TestRouterRouting(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.router = MultiProviderRouter()

    @patch("providers.router.settings")
    @patch("providers.router.OpenRouterClient")
    async def test_route_openrouter(self, mock_client_class, mock_settings):
        # Setup settings mocks
        mock_settings.is_provider_configured.return_value = True
        mock_settings.default_openrouter_model = "meta-llama/llama-3-8b-instruct:free"

        # Setup client instance mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        # AsyncMock for generate
        mock_client_instance.generate = AsyncMock()
        mock_client_instance.generate.return_value = LLMResponse(
            content="Hello from OpenRouter!",
            model_name="meta-llama/llama-3-8b-instruct:free"
        )

        messages = [ChatMessage(role="user", content="Hello")]
        response = await self.router.generate(
            messages=messages,
            model="openrouter/meta-llama/llama-3-8b-instruct:free"
        )

        # Assert correct routing and client call
        self.assertEqual(response.content, "Hello from OpenRouter!")
        mock_client_class.assert_called_once()
        mock_client_instance.generate.assert_called_once_with(
            messages=messages,
            model="meta-llama/llama-3-8b-instruct:free",
            tools=None,
            temperature=0.7,
            max_tokens=None
        )

    @patch("providers.router.settings")
    @patch("providers.router.GeminiClient")
    async def test_route_gemini(self, mock_client_class, mock_settings):
        mock_settings.is_provider_configured.return_value = True
        mock_settings.default_gemini_model = "gemini-2.5-flash"

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        mock_client_instance.generate = AsyncMock()
        mock_client_instance.generate.return_value = LLMResponse(
            content="Hello from Gemini!",
            model_name="gemini-2.5-flash"
        )

        messages = [ChatMessage(role="user", content="Hello")]
        response = await self.router.generate(
            messages=messages,
            model="gemini/gemini-2.5-flash"
        )

        self.assertEqual(response.content, "Hello from Gemini!")
        mock_client_class.assert_called_once()

    @patch("providers.router.settings")
    @patch("providers.router.OllamaClient")
    async def test_route_ollama(self, mock_client_class, mock_settings):
        mock_settings.is_provider_configured.return_value = True
        mock_settings.default_ollama_model = "qwen2.5-coder:7b"

        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance
        
        mock_client_instance.generate = AsyncMock()
        mock_client_instance.generate.return_value = LLMResponse(
            content="Hello from Ollama!",
            model_name="qwen2.5-coder:7b"
        )

        messages = [ChatMessage(role="user", content="Hello")]
        response = await self.router.generate(
            messages=messages,
            model="ollama/qwen2.5-coder:7b"
        )

        self.assertEqual(response.content, "Hello from Ollama!")
        mock_client_class.assert_called_once()

    @patch("providers.router.settings")
    async def test_route_unconfigured_error(self, mock_settings):
        # Setting key to false/unconfigured
        mock_settings.is_provider_configured.return_value = False
        
        messages = [ChatMessage(role="user", content="Hello")]
        
        with self.assertRaises(ValueError):
            await self.router.generate(
                messages=messages,
                model="groq/llama-3.1-8b-instant"
            )
