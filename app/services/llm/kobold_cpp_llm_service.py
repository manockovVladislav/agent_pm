import json
from urllib import request

from app.config import KOBOLD_CPP_TIMEOUT_SECONDS, KOBOLD_CPP_URL


class KoboldCppLLMService:
    """
    Домашний тестовый адаптер для KoboldCpp HTTP API.

    Файл изолирован: если он больше не нужен, его можно удалить.
    Qwen-адаптер и основной пайплайн от него не зависят.
    """

    def __init__(self, api_url: str | None = None):
        api_url = api_url or KOBOLD_CPP_URL
        self.api_url = self._normalize_api_url(api_url)
        self.timeout_seconds = KOBOLD_CPP_TIMEOUT_SECONDS

    def _normalize_api_url(self, api_url: str) -> str:
        api_url = str(api_url).rstrip("/")

        if api_url.endswith("/api/v1/generate"):
            return api_url

        if api_url.endswith("/api/v1"):
            return f"{api_url}/generate"

        if api_url.endswith("/generate"):
            return api_url

        return f"{api_url}/api/v1/generate"

    def generate(self, prompt: str, max_new_tokens: int = 1200) -> str:
        payload = {
            "prompt": prompt,
            "max_length": max_new_tokens,
            "temperature": 0,
        }

        data = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.api_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            raw_body = response.read().decode("utf-8")

        body = json.loads(raw_body)

        if "results" in body and body["results"]:
            return str(body["results"][0].get("text", "")).strip()

        return str(body.get("response", body.get("text", ""))).strip()
