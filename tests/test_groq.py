from solution_video.llm.groq import GroqProvider
from solution_video.cli import _load_local_env


def test_groq_model_uses_environment_default(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "configured/model")

    provider = GroqProvider(api_key="test-key")

    assert provider.model == "configured/model"


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
