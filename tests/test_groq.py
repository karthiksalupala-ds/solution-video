import pytest

from solution_video.llm.groq import GroqProvider
from solution_video.cli import _load_local_env
from solution_video.llm.base import JsonModeValidationError


def test_groq_model_uses_environment_default(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "configured/model")

    provider = GroqProvider(api_key="test-key")

    assert provider.model == "configured/model"


def test_groq_http_error_includes_provider_detail_and_redacts_key(monkeypatch):
    import requests
    import pytest

    from solution_video.llm.base import LLMError

    class _Response:
        status_code = 400

        @staticmethod
        def json():
            return {"error": {"message": "invalid request test-secret"}}

        def raise_for_status(self):
            error = requests.HTTPError(response=self)
            raise error

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _Response())
    provider = GroqProvider(api_key="test-secret")

    with pytest.raises(LLMError, match=r"invalid request \[REDACTED\]") as error:
        provider.complete("prompt")
    assert "test-secret" not in str(error.value)


def test_groq_json_mode_validation_disables_format_for_one_retry(monkeypatch):
    import requests

    from solution_video.llm.groq import MAX_COMPLETION_TOKENS

    calls = []

    class _Response:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self.body = body
            self.headers = {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

        def json(self):
            return self.body

    def _post(_url, **kwargs):
        calls.append(kwargs["json"])
        if len(calls) == 1:
            return _Response(400, {
                "error": {
                    "code": "json_validate_failed",
                    "message": "JSON validation failed",
                    "failed_generation": "{\"steps\":",
                }
            })
        return _Response(200, {
            "choices": [{"message": {"content": "{\"ok\": true}"}}]
        })

    monkeypatch.setattr(requests, "post", _post)
    provider = GroqProvider(api_key="test-key")

    with pytest.raises(JsonModeValidationError) as raised:
        provider.complete("prompt")
    assert raised.value.failed_generation == "{\"steps\":"
    assert provider.json_mode_enabled is False
    assert provider.complete("prompt") == "{\"ok\": true}"
    assert "response_format" in calls[0]
    assert "response_format" not in calls[1]
    assert calls[0]["max_completion_tokens"] == MAX_COMPLETION_TOKENS
    assert calls[1]["max_completion_tokens"] == MAX_COMPLETION_TOKENS


def test_groq_json_mode_validation_without_failed_generation_is_explicit(monkeypatch):
    import requests
    import pytest

    class _Response:
        status_code = 400
        headers = {}

        @staticmethod
        def json():
            return {"error": {"code": "json_validate_failed", "message": "Invalid JSON"}}

        def raise_for_status(self):
            raise requests.HTTPError(response=self)

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: _Response())
    provider = GroqProvider(api_key="test-key")

    with pytest.raises(JsonModeValidationError) as raised:
        provider.complete("prompt")
    assert raised.value.failed_generation is None
    assert raised.value.fallback_available


def test_groq_reports_completion_limit_truncation(monkeypatch):
    import requests

    from solution_video.llm.base import JsonParseError
    from solution_video.llm.groq import MAX_COMPLETION_TOKENS

    class _Response:
        @staticmethod
        def json():
            return {"choices": [{
                "message": {"content": "{\"steps\": ["},
                "finish_reason": "length",
            }]}

        def raise_for_status(self):
            return None

    captured = {}

    def _post(_url, **kwargs):
        captured.update(kwargs["json"])
        return _Response()

    monkeypatch.setattr(requests, "post", _post)
    provider = GroqProvider(api_key="test-key")

    with pytest.raises(JsonParseError, match="reached the 4096-token limit"):
        provider.complete("prompt")
    assert captured["max_completion_tokens"] == MAX_COMPLETION_TOKENS


def test_explicit_groq_model_overrides_environment(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "configured/model")

    provider = GroqProvider(api_key="test-key", model="explicit/model")

    assert provider.model == "explicit/model"


def test_groq_model_loads_from_local_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("GROQ_MODEL=local/model\n", encoding="utf-8")

    _load_local_env()

    assert GroqProvider(api_key="test-key").model == "local/model"
