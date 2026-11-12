import time

import httpx

from app.llm.base import LLMError

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
RETRYABLE = {429, 503}


class GeminiClient:
    def __init__(self, api_key: str, model: str, timeout: float = 60.0, retries: int = 4):
        if not api_key or not model:
            raise LLMError("LLM_API_KEY ve LLM_MODEL .env dosyasında tanımlı olmalı")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.retries = retries

    def generate_json(self, system: str, user: str, schema: dict) -> str:
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        url = f"{BASE_URL}/{self.model}:generateContent"
        for attempt in range(self.retries + 1):
            try:
                r = httpx.post(url, headers={"x-goog-api-key": self.api_key}, json=body, timeout=self.timeout)
            except httpx.TimeoutException as e:
                if attempt < self.retries:
                    time.sleep(4 * 2**attempt)
                    continue
                raise LLMError("Gemini zaman aşımına uğradı") from e
            except httpx.HTTPError as e:
                raise LLMError(f"Gemini'ye ulaşılamadı: {type(e).__name__}") from e
            if r.status_code in RETRYABLE and attempt < self.retries:
                time.sleep(4 * 2**attempt)  # kota/yoğunluk: 4, 8, 16, 32 sn bekleyip tekrar dene
                continue
            if r.status_code != 200:
                msg = r.json().get("error", {}).get("message", "") if r.content else ""
                raise LLMError(f"Gemini hata {r.status_code}: {msg[:200]}")
            break
        try:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError("Gemini boş veya engellenmiş yanıt döndürdü") from e
