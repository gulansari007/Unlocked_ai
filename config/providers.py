from typing import Dict, Any, Tuple, Optional, List
from pydantic import BaseModel

class ProviderMetadata(BaseModel):
    name: str
    requires_api_key: bool
    default_model: str
    available_models: List[str]
    supports_tools: bool
    supports_streaming: bool

# Metadata definition for supported providers
PROVIDERS: Dict[str, ProviderMetadata] = {
    "openrouter": ProviderMetadata(
        name="OpenRouter",
        requires_api_key=True,
        default_model="meta-llama/llama-3-8b-instruct:free",
        available_models=[
            "meta-llama/llama-3-8b-instruct:free",
            "google/gemini-2.5-flash",
            "google/gemini-2.5-pro",
            "anthropic/claude-3-5-sonnet:beta",
            "deepseek/deepseek-chat"
        ],
        supports_tools=True,
        supports_streaming=True
    ),
    "opencode": ProviderMetadata(
        name="OpenCode Proxy",
        requires_api_key=True,
        default_model="qwen/qwen-2.5-coder-32b",
        available_models=[
            "qwen/qwen-2.5-coder-32b",
            "qwen/qwen-2.5-coder-7b",
            "deepseek-coder:33b"
        ],
        supports_tools=True,
        supports_streaming=True
    ),
    "ollama": ProviderMetadata(
        name="Ollama (Local)",
        requires_api_key=False,
        default_model="qwen2.5-coder:7b",
        available_models=[
            "qwen2.5-coder:7b",
            "qwen2.5-coder:1.5b",
            "llama3:latest",
            "mistral:latest",
            "phi3:latest"
        ],
        supports_tools=True,
        supports_streaming=True
    ),
    "gemini": ProviderMetadata(
        name="Google Gemini",
        requires_api_key=True,
        default_model="gemini-2.5-flash",
        available_models=[
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro"
        ],
        supports_tools=True,
        supports_streaming=True
    ),
    "groq": ProviderMetadata(
        name="Groq",
        requires_api_key=True,
        default_model="llama-3.1-8b-instant",
        available_models=[
            "llama-3.3-70b-specdec",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ],
        supports_tools=True,
        supports_streaming=True
    ),
    "openai": ProviderMetadata(
        name="OpenAI",
        requires_api_key=True,
        default_model="gpt-4o-mini",
        available_models=[
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ],
        supports_tools=True,
        supports_streaming=True
    ),
    "anthropic": ProviderMetadata(
        name="Anthropic",
        requires_api_key=True,
        default_model="claude-3-5-sonnet-latest",
        available_models=[
            "claude-3-5-sonnet-latest",
            "claude-3-5-haiku-latest",
            "claude-3-opus-latest"
        ],
        supports_tools=True,
        supports_streaming=True
    )
}


def parse_model_string(model_str: str) -> Tuple[str, str]:
    """
    Parses a combined model string like:
      - 'openrouter/meta-llama/llama-3-8b-instruct:free' -> ('openrouter', 'meta-llama/llama-3-8b-instruct:free')
      - 'ollama/qwen2.5-coder:7b' -> ('ollama', 'qwen2.5-coder:7b')
      - 'openai/gpt-4o' -> ('openai', 'gpt-4o')
      - 'anthropic/claude-3-5-sonnet' -> ('anthropic', 'claude-3-5-sonnet')
      - 'gemini-2.5-flash' -> ('gemini', 'gemini-2.5-flash')
      
    Returns a tuple of (provider, model_name).
    """
    # Check if format is provider/model_name
    if "/" in model_str:
        parts = model_str.split("/", 1)
        potential_provider = parts[0].lower()
        if potential_provider in PROVIDERS:
            return potential_provider, parts[1]
            
    # Try custom prefix matches or fallback
    m_lower = model_str.lower()
    if m_lower.startswith("gemini-") or m_lower.startswith("gemini/"):
        model_name = model_str[7:] if m_lower.startswith("gemini/") else model_str
        return "gemini", model_name
    elif m_lower.startswith("groq/") or m_lower.startswith("llama-") or m_lower.startswith("gemma-"):
        model_name = model_str[5:] if m_lower.startswith("groq/") else model_str
        return "groq", model_name
    elif m_lower.startswith("openai/"):
        return "openai", model_str[7:]
    elif m_lower.startswith("anthropic/") or m_lower.startswith("claude-"):
        model_name = model_str[10:] if m_lower.startswith("anthropic/") else model_str
        return "anthropic", model_name
    elif m_lower.startswith("ollama/"):
        return "ollama", model_str[7:]
    elif m_lower.startswith("openrouter/"):
        return "openrouter", model_str[11:]
    elif m_lower.startswith("opencode/"):
        return "opencode", model_str[9:]
        
    # Default fallback
    return "openrouter", model_str

