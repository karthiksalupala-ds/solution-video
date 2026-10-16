"""Groq OpenAI-compatible JSON adapter."""

from __future__ import annotations

import os

import requests

from .base import (
    JsonModeValidationError,
    JsonParseError,
    JsonProvider,
    LLMError,
    RateLimitError,
    retry_after_seconds,
)


MAX_COMPLETION_TOKENS = 8192
_JSON_MODE_REJECTED = False


class GroqProvider(JsonProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout_s: int = 25) -> None:
        global _JSON_MODE_REJECTED
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b"
        self.timeout_s = timeout_s
        json_mode = os.getenv("GROQ_JSON_MODE", "1")
        if json_mode not in {"0", "1"}:
            raise LLMError("GROQ_JSON_MODE must be 0 or 1")
        self.json_mode_enabled = json_mode == "1" and not _JSON_MODE_REJECTED
        if not self.api_key:
            raise LLMError("GROQ_API_KEY is not configured")

    def complete(self, prompt: str) -> str:
        global _JSON_MODE_REJECTED
        request_body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
        }
        if self.json_mode_enabled:
            request_body["response_format"] = {"type": "json_object"}
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_body,
                timeout=self.timeout_s,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            if status == 429:
                headers = exc.response.headers if exc.response is not None else {}
                raise RateLimitError(
                    "Groq request was rate limited (HTTP 429)",
                    retry_after_seconds(headers.get("Retry-After")),
                ) from exc
            detail = ""
            error_code = ""
            failed_generation = None
            if exc.response is not None:
                try:
                    body = exc.response.json()
                    error = body.get("error", {}) if isinstance(body, dict) else {}
                    if isinstance(error, dict):
                        if isinstance(error.get("message"), str):
                            detail = error["message"]
                        if isinstance(error.get("code"), str):
                            error_code = error["code"]
                        if isinstance(error.get("failed_generation"), str):
                            failed_generation = error["failed_generation"]
                except ValueError:
                    pass
            if self.api_key and detail:
                detail = detail.replace(self.api_key, "[REDACTED]")
            if self.api_key and failed_generation:
                failed_generation = failed_generation.replace(self.api_key, "[REDACTED]")
            if error_code == "json_validate_failed" and self.json_mode_enabled:
                _JSON_MODE_REJECTED = True
                self.json_mode_enabled = False
                raise JsonModeValidationError(
                    f"Groq JSON mode validation failed (HTTP {status}, code {error_code})"
                    + (f": {detail}" if detail else ""),
                    failed_generation=failed_generation,
                    fallback_available=True,
                ) from exc
            suffix = f": {detail}" if detail else ""
            code_suffix = f", code {error_code}" if error_code else ""
            raise LLMError(f"Groq request failed (HTTP {status}{code_suffix}){suffix}") from exc
        except requests.RequestException as exc:
            raise LLMError("Groq request failed") from exc
        try:
            choice = response.json()["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise LLMError("Groq response did not contain assistant content") from exc
        if choice.get("finish_reason") == "length":
            raise JsonParseError(
                f"Groq completion reached the {MAX_COMPLETION_TOKENS}-token limit",
                content,
            )
        return content
