"""Groq OpenAI-compatible JSON adapter."""

from __future__ import annotations

import os

import requests

from .base import JsonProvider, LLMError, RateLimitError, retry_after_seconds


class GroqProvider(JsonProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_s: int = 25) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
        self.timeout_s = timeout_s
        if not self.api_key:
            raise LLMError("GROQ_API_KEY is not configured")

    def complete(self, prompt: str) -> str:
        try:
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}, "temperature": 0}, timeout=self.timeout_s)
            response.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            if status == 429:
                headers = exc.response.headers if exc.response is not None else {}
                raise RateLimitError(
                    "Groq request was rate limited (HTTP 429)",
                    retry_after_seconds(headers.get("Retry-After")),
                ) from exc
            raise LLMError(f"Groq request failed (HTTP {status})") from exc
        except requests.RequestException as exc:
            raise LLMError("Groq request failed") from exc
        try:
            return response.json()["choices"][0]["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise LLMError("Groq response did not contain assistant content") from exc
