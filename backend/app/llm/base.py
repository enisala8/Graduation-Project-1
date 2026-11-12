from typing import Protocol


class LLMError(Exception):
    """Sağlayıcı hatası (ağ, kota, güvenlik engeli, boş yanıt)."""


class LLMClient(Protocol):
    def generate_json(self, system: str, user: str, schema: dict) -> str:
        """JSON Schema'ya uyması beklenen yanıtı ham JSON metni olarak döndürür."""
        ...
