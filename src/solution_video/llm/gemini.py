"""Gemini REST JSON adapter without a heavyweight SDK dependency."""

from __future__ import annotations

import os

import requests

from .base import JsonProvider, LLMError


class GeminiProvider(JsonProvider):
    def __init__(self, api_key: str | None = None, model: str = "gemini-3.8-flash", timeout_s: int = 25) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model, self.timeout_s = model, timeout_s
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not configured")

    def complete(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        try:
            response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}, timeout=self.timeout_s)
            response.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            raise LLMError(f"Gemini request failed (HTTP {status})") from exc
        except requests.RequestException as exc:
            raise LLMError("Gemini request failed") from exc
        try:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("Gemini response did not contain assistant content") from exc
