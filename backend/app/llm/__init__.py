from app.config import settings
from app.llm.base import LLMClient, LLMError


def get_llm_client() -> LLMClient:
    """Sağlayıcıyı .env'deki LLM_PROVIDER'a göre seçer; geri kalan kod hangisi olduğunu bilmez."""
    if settings.llm_provider == "gemini":
        from app.llm.gemini import GeminiClient

        return GeminiClient(settings.llm_api_key, settings.llm_model)
    raise LLMError(f"Desteklenmeyen LLM_PROVIDER: {settings.llm_provider}")
