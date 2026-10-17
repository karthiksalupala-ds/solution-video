from __future__ import annotations

from pathlib import Path

import pytest

from solution_video.voice import runtime
from solution_video.voice.listening_test import VoiceTestError
from solution_video.voice.runtime import VoiceInput, estimate_voice, synthesize_voice


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


class FakeProvider:
    def __init__(self, directory: Path, text: str):
        self.path = directory / "speech.mp3"
        self.path.write_text(text, encoding="utf-8")

    def synthesize(self, text: str) -> Path:
        self.path.write_text(text, encoding="utf-8")
        return self.path


def _processor(source: Path, destination: Path) -> float:
    destination.write_bytes(source.read_bytes())
    return 1.25


def test_provider_order_respects_opt_in_and_fallback_flag():
    assert runtime.provider_order({}) == ("hf_space", "edge_tts", "none")
    assert runtime.provider_order({}, "elevenlabs") == ("elevenlabs", "none")
    assert runtime.provider_order(
        {"VOICE_ELEVENLABS_FALLBACK": "1"}, "elevenlabs"
    ) == ("elevenlabs", "hf_space", "edge_tts", "none")
    with pytest.raises(runtime.VoiceRuntimeError, match="selected with --voice-provider"):
        runtime.provider_order({
            "VOICE_PROVIDER_ORDER": "elevenlabs,edge_tts",
            "VOICE_ELEVENLABS_FALLBACK": "1",
        })
    with pytest.raises(runtime.VoiceRuntimeError, match="none provider must be last"):
        runtime.provider_order({"VOICE_PROVIDER_ORDER": "none,edge_tts"})


def test_cache_hit_skips_second_synthesis_and_reports_no_credits(tmp_path, monkeypatch):
    calls = []

    def factory(provider_name, environment, temp_dir):
        calls.append(provider_name)
        return FakeProvider(temp_dir, "audio")

    monkeypatch.setattr(runtime, "probe_audio_duration", lambda _path: 1.25)
    kwargs = {
        "environment": {"VOICE_PROVIDER_ORDER": "edge_tts,none"},
        "cache_dir": tmp_path / "cache",
        "audio_processor": _processor,
        "provider_factory": factory,
    }
    inputs = (VoiceInput("step-1", "The answer is 72."),)
    first = synthesize_voice(inputs, **kwargs)
    second = synthesize_voice(inputs, **kwargs)

    assert calls == ["edge_tts"]
    assert first.clips[0] is not None
    assert second.clips[0] is not None
    assert second.credits == 0
    assert second.clips[0].path == first.clips[0].path


def test_edge_word_boundaries_are_scaled_and_cached(tmp_path, monkeypatch):
    calls = []

    class TimedProvider(FakeProvider):
        def synthesize_with_word_boundaries(self, text):
            calls.append(text)
            return self.synthesize(text), (("seventy", 0.5), ("two", 0.75))

    monkeypatch.setattr(
        runtime,
        "probe_audio_duration",
        lambda path: 1.0 if path.suffix == ".mp3" else 2.0,
    )

    def process(source, destination, *, preserve_leading_silence=False):
        assert preserve_leading_silence
        destination.write_bytes(source.read_bytes())
        return 2.0

    monkeypatch.setattr(runtime, "normalize_audio_file", process)
    result = synthesize_voice(
        (VoiceInput("answer", "The answer is 72."),),
        environment={"EDGE_TTS_RATE": "-8%"},
        provider_override="edge_tts",
        cache_dir=tmp_path / "cache",
        provider_factory=lambda _name, _environment, directory: TimedProvider(directory, "audio"),
    )
    cached = synthesize_voice(
        (VoiceInput("answer", "The answer is 72."),),
        environment={"EDGE_TTS_RATE": "-8%"},
        provider_override="edge_tts",
        cache_dir=tmp_path / "cache",
        audio_processor=lambda *_args: pytest.fail("cache hit must not process audio"),
        provider_factory=lambda *_args: pytest.fail("cache hit must not synthesize"),
    )

    assert calls == ["The answer is seventy two."]
    assert result.clips[0].word_boundaries == (("seventy", 1.0), ("two", 1.5))
    assert cached.clips[0].word_boundaries == result.clips[0].word_boundaries


def test_edge_rate_is_validated_and_passed_to_provider(tmp_path):
    result = synthesize_voice(
        (VoiceInput("answer", "Answer."),),
        environment={"EDGE_TTS_RATE": "very slow"},
        provider_override="edge_tts",
        cache_dir=tmp_path / "invalid-cache",
        provider_factory=lambda *_args: pytest.fail("invalid rate must block provider creation"),
    )
    assert result.provider == "none"
    assert any("EDGE_TTS_RATE" in warning for warning in result.warnings)


def test_edge_audio_normalization_preserves_leading_word_offsets(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(runtime.shutil, "which", lambda _name: "ffmpeg.exe")
    monkeypatch.setattr(
        runtime.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(command),
    )
    monkeypatch.setattr(runtime, "probe_audio_duration", lambda _path: 1.0)

    runtime.normalize_audio_file(
        tmp_path / "source.mp3",
        tmp_path / "normalized.wav",
        preserve_leading_silence=True,
    )
    filter_value = commands[0][commands[0].index("-af") + 1]

    assert "stop_periods=1" in filter_value
    assert "start_periods=1" not in filter_value


def test_provider_failure_falls_back_to_edge_and_surfaces_warning(tmp_path):
    calls = []

    def factory(provider_name, environment, temp_dir):
        calls.append(provider_name)
        if provider_name == "hf_space":
            raise VoiceTestError("HF cold start failed")
        return FakeProvider(temp_dir, "audio")

    result = synthesize_voice(
        (VoiceInput("answer", "Answer."),),
        environment={
            "HF_TTS_SPACE": "owner/private",
            "HF_TOKEN": "not-a-real-token",
            "VOICE_PROVIDER_ORDER": "hf_space,edge_tts,none",
        },
        cache_dir=tmp_path / "cache",
        audio_processor=_processor,
        provider_factory=factory,
    )

    assert calls == ["hf_space", "edge_tts"]
    assert result.provider == "edge_tts"
    assert any("HF cold start failed" in warning for warning in result.warnings)


def test_hf_space_error_text_is_preserved_in_runtime_warnings(tmp_path):
    def factory(provider_name, _environment, _temp_dir):
        assert provider_name == "hf_space"

        class FailedSpace:
            def synthesize(self, _text):
                raise VoiceTestError("HTTP 400: 'meta' field must be explicitly provided")

        return FailedSpace()

    result = synthesize_voice(
        (VoiceInput("question", "A question."), VoiceInput("answer", "An answer.")),
        environment={
            "HF_TTS_SPACE": "owner/mock-space",
            "HF_TOKEN": "mock-token",
            "VOICE_PROVIDER_ORDER": "hf_space,none",
        },
        provider_override="hf_space",
        cache_dir=tmp_path / "cache",
        audio_processor=_processor,
        provider_factory=factory,
    )

    assert result.provider == "none"
    assert any("HTTP 400" in warning and "'meta' field must be explicitly provided" in warning
               for warning in result.warnings), result.warnings


def test_hf_factory_resolves_reference_and_configures_request_budget(tmp_path, monkeypatch):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"audio")
    observed = {}

    class FakeSpace:
        def __init__(self, space_id, token, resolved_reference, **kwargs):
            observed.update({
                "space_id": space_id,
                "token": token,
                "reference": resolved_reference,
                **kwargs,
            })

    monkeypatch.setattr(runtime, "HFSpaceProvider", FakeSpace)
    runtime._make_provider(
        "hf_space",
        {
            "HF_TTS_SPACE": "owner/mock-space",
            "HF_TOKEN": "mock-token",
            "HF_TTS_REFERENCE_AUDIO": str(reference),
            "HF_TTS_REQUEST_LIMIT": "2",
            "HF_TTS_REQUEST_PAUSE_S": "5",
        },
        tmp_path,
    )

    assert observed["reference"] == reference.resolve()
    assert observed["request_limit"] == 2
    assert observed["request_pause_s"] == 5


def test_elevenlabs_checks_remaining_credits_before_synthesis(tmp_path):
    session = FakeSession({"character_count": 200, "character_limit": 10_000})
    calls = []

    def factory(provider_name, environment, temp_dir):
        calls.append(provider_name)
        return FakeProvider(temp_dir, "audio")

    result = synthesize_voice(
        (VoiceInput("answer", "The answer is 72."),),
        environment={
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_VOICE_ID": "test-voice",
            "ELEVENLABS_RESERVE_CREDITS": "1500",
        },
        provider_override="elevenlabs",
        cache_dir=tmp_path / "cache",
        audio_processor=_processor,
        credit_session=session,
        provider_factory=factory,
    )

    assert session.calls[0][0] == runtime.SUBSCRIPTION_URL
    assert calls == ["elevenlabs"]
    assert result.credits == result.characters


def test_elevenlabs_fails_closed_when_credit_reserve_would_be_crossed(tmp_path):
    session = FakeSession({"character_count": 8500, "character_limit": 10_000})
    calls = []

    def factory(provider_name, environment, temp_dir):
        calls.append(provider_name)
        return FakeProvider(temp_dir, "audio")

    result = synthesize_voice(
        (VoiceInput("answer", "Answer."),),
        environment={
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_VOICE_ID": "test-voice",
        },
        provider_override="elevenlabs",
        cache_dir=tmp_path / "cache",
        audio_processor=_processor,
        credit_session=session,
        provider_factory=factory,
    )

    assert calls == []
    assert result.provider == "none"
    assert any("reserve would be crossed" in warning for warning in result.warnings)


def test_elevenlabs_fails_closed_on_invalid_subscription_usage(tmp_path):
    session = FakeSession({"character_count": True, "character_limit": 10_000})

    result = synthesize_voice(
        (VoiceInput("answer", "Answer."),),
        environment={
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_VOICE_ID": "test-voice",
        },
        provider_override="elevenlabs",
        cache_dir=tmp_path / "cache",
        audio_processor=_processor,
        credit_session=session,
        provider_factory=lambda *args: pytest.fail("invalid usage must block synthesis"),
    )

    assert result.provider == "none"
    assert any("invalid character usage fields" in warning for warning in result.warnings)


def test_elevenlabs_synthesis_failure_uses_configured_fallback_only_when_enabled(tmp_path):
    session = FakeSession({"character_count": 200, "character_limit": 10_000})
    calls = []

    def factory(provider_name, environment, temp_dir):
        calls.append(provider_name)
        if provider_name == "elevenlabs":
            raise VoiceTestError("ElevenLabs request failed")
        return FakeProvider(temp_dir, "audio")

    result = synthesize_voice(
        (VoiceInput("answer", "Answer."),),
        environment={
            "ELEVENLABS_API_KEY": "test-key",
            "ELEVENLABS_VOICE_ID": "test-voice",
            "VOICE_ELEVENLABS_FALLBACK": "1",
        },
        provider_override="elevenlabs",
        cache_dir=tmp_path / "cache",
        audio_processor=_processor,
        credit_session=session,
        provider_factory=factory,
    )

    assert calls == ["elevenlabs", "edge_tts"]
    assert result.provider == "edge_tts"
    assert any("ElevenLabs request failed" in warning for warning in result.warnings)


def test_edge_failure_gracefully_degrades_to_no_voice(tmp_path):
    calls = []

    def factory(provider_name, environment, temp_dir):
        calls.append(provider_name)
        raise VoiceTestError(f"{provider_name} failed")

    result = synthesize_voice(
        (VoiceInput("answer", "Answer."),),
        environment={},
        provider_override="edge_tts",
        cache_dir=tmp_path / "cache",
        audio_processor=_processor,
        provider_factory=factory,
    )

    assert calls == ["edge_tts"]
    assert result.provider == "none"
    assert any("narration unavailable" in warning for warning in result.warnings)


def test_dry_run_estimate_has_no_provider_calls():
    result = estimate_voice(
        (VoiceInput("answer", "The answer is 72."),),
        environment={"ELEVENLABS_MODEL_ID": "eleven_v3"},
        provider_override="elevenlabs",
    )
    assert result == ("elevenlabs", "eleven_v3", len("The answer is seventy two."), len("The answer is seventy two."))
