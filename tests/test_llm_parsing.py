import pytest
import requests

from solution_video.llm.base import LLMError, RateLimitError, JsonProvider, extract_json, rate_limit_delay, retry_after_seconds


def test_fenced_json_is_accepted():
    assert extract_json("```json\n{\"answer\": \"42\"}\n```") == {"answer": "42"}


def test_non_json_is_rejected():
    with pytest.raises(LLMError):
        extract_json("not json")


def test_retry_after_parses_seconds_and_ignores_invalid_values():
    assert retry_after_seconds("4.5") == 4.5
    assert retry_after_seconds("not-a-delay") is None


def test_rate_limit_delay_honors_header_and_caps_exponential_backoff():
    assert rate_limit_delay(0, 3.0) == 3.0
    assert rate_limit_delay(1, 0.25) == 2.0
    assert rate_limit_delay(10, 0.0) == 30.0
    assert rate_limit_delay(10, 45.0) == 45.0


def test_groq_rate_limit_error_preserves_retry_after(monkeypatch):
    from solution_video.llm.groq import GroqProvider

    class _LimitedResponse:
        status_code = 429
        headers = {"Retry-After": "7"}

        def raise_for_status(self):
            raise requests.HTTPError("rate limited", response=self)

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _LimitedResponse())
    provider = GroqProvider(api_key="test-key")

    with pytest.raises(RateLimitError) as raised:
        provider.complete("prompt")

    assert raised.value.retry_after_s == 7
