import unittest
from config.settings import settings
from config.providers import parse_model_string, PROVIDERS

class TestConfigEngine(unittest.TestCase):
    def test_settings_load(self):
        # Env default overrides should match what's in our .env or fallback
        self.assertIsNotNone(settings.default_openrouter_model)
        self.assertIsNotNone(settings.default_gemini_model)
        self.assertIsNotNone(settings.ollama_base_url)

    def test_parse_model_string(self):
        # Standard provider/model format
        p, m = parse_model_string("openrouter/meta-llama/llama-3-8b-instruct:free")
        self.assertEqual(p, "openrouter")
        self.assertEqual(m, "meta-llama/llama-3-8b-instruct:free")

        p, m = parse_model_string("gemini/gemini-2.5-flash")
        self.assertEqual(p, "gemini")
        self.assertEqual(m, "gemini-2.5-flash")

        p, m = parse_model_string("ollama/qwen2.5-coder:7b")
        self.assertEqual(p, "ollama")
        self.assertEqual(m, "qwen2.5-coder:7b")

        # Fallback patterns
        p, m = parse_model_string("gemini-2.5-flash")
        self.assertEqual(p, "gemini")
        self.assertEqual(m, "gemini-2.5-flash")

        p, m = parse_model_string("llama-3.1-8b-instant")
        self.assertEqual(p, "groq")
        self.assertEqual(m, "llama-3.1-8b-instant")

    def test_providers_metadata(self):
        self.assertIn("openrouter", PROVIDERS)
        self.assertTrue(PROVIDERS["gemini"].supports_tools)
        self.assertTrue(PROVIDERS["ollama"].supports_streaming)

if __name__ == "__main__":
    unittest.main()
