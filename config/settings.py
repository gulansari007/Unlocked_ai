import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Settings schema for Unlocked AI using Pydantic Settings.
    Loads values from environment variables or a local .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # API Keys
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    opencode_api_key: Optional[str] = Field(default=None, alias="OPENCODE_API_KEY")
    opencode_base_url: str = Field(default="https://api.opencode.example.com/v1", alias="OPENCODE_BASE_URL")
    
    # Ollama Local endpoint
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    
    # Native Free Tiers / Standard APIs
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(default="https://api.anthropic.com/v1", alias="ANTHROPIC_BASE_URL")
    
    # Integration Keys
    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")


    # Default Models per Provider
    default_openrouter_model: str = Field(default="meta-llama/llama-3-8b-instruct:free", alias="DEFAULT_OPENROUTER_MODEL")
    default_opencode_model: str = Field(default="qwen/qwen-2.5-coder-32b", alias="DEFAULT_OPENCODE_MODEL")
    default_ollama_model: str = Field(default="qwen2.5-coder:7b", alias="DEFAULT_OLLAMA_MODEL")
    default_gemini_model: str = Field(default="gemini-2.5-flash", alias="DEFAULT_GEMINI_MODEL")
    default_groq_model: str = Field(default="llama-3.1-8b-instant", alias="DEFAULT_GROQ_MODEL")
    default_openai_model: str = Field(default="gpt-4o-mini", alias="DEFAULT_OPENAI_MODEL")
    default_anthropic_model: str = Field(default="claude-3-5-sonnet-latest", alias="DEFAULT_ANTHROPIC_MODEL")

    def is_provider_configured(self, provider: str) -> bool:
        """
        Check if a provider is configured with the necessary credentials.
        """
        p = provider.lower()
        if p == "openrouter":
            return bool(self.openrouter_api_key and self.openrouter_api_key != "mock_openrouter_key")
        elif p == "opencode":
            return bool(self.opencode_api_key and self.opencode_api_key != "mock_opencode_key")
        elif p == "ollama":
            # Ollama is local, we just check if base url is present (it's always defaulted)
            return bool(self.ollama_base_url)
        elif p == "gemini":
            return bool(self.gemini_api_key and self.gemini_api_key != "mock_gemini_key")
        elif p == "groq":
            return bool(self.groq_api_key and self.groq_api_key != "mock_groq_key")
        elif p == "openai":
            return bool(self.openai_api_key and self.openai_api_key != "mock_openai_key")
        elif p == "anthropic":
            return bool(self.anthropic_api_key and self.anthropic_api_key != "mock_anthropic_key")
        return False

# Export a single global instance of Settings
settings = Settings()

