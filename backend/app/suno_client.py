from __future__ import annotations

import os
from typing import Any

import httpx


class SunoClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        callback_url: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("SUNO_API_KEY")
        if not self.api_key:
            raise RuntimeError("SUNO_API_KEY is missing in environment/.env")

        self.base_url = (base_url or os.getenv("SUNO_API_BASE") or "https://api.sunoapi.org").rstrip("/")
        self.callback_url = callback_url or os.getenv("SUNO_CALLBACK_URL")
        if not self.callback_url:
            raise RuntimeError("SUNO_CALLBACK_URL is missing in environment/.env")

        self.default_model = default_model or os.getenv("SUNO_MODEL", "V4_5ALL")
        self.timeout_seconds = timeout_seconds or float(os.getenv("SUNO_TIMEOUT_SECONDS", "15"))

    def generate_music(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/generate"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def model_limits(model: str) -> dict[str, int]:
        model_upper = model.upper()
        if model_upper in {"V4_5ALL", "V4_5PLUS", "V4_5", "V5"}:
            return {"title": 80, "style": 1000, "prompt": 5000, "prompt_non_custom": 500}
        if model_upper in {"V4", "V3_5"}:
            return {"title": 80, "style": 200, "prompt": 3000, "prompt_non_custom": 500}
        return {"title": 80, "style": 1000, "prompt": 5000, "prompt_non_custom": 500}
