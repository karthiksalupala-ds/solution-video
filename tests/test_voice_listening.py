from __future__ import annotations

import json
from pathlib import Path

import pytest

from solution_video.voice.listening_test import (
    ELEVENLABS_TEST_CREDIT_LIMIT,
    EdgeTTSProvider,
    ElevenLabsProvider,
    HFSpaceProvider,
    VoiceTestError,
    character_count,
    list_elevenlabs_stock_voices,
    load_text_variants,
    run_listening_test,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "speed_train.json"
VARIANTS = ROOT / "examples" / "voice_tests" / "approved_variants.json"


def test_loads_twelve_approved_variants_from_source_steps():
    variants = load_text_variants(VARIANTS, SOURCE)

    assert len(variants) == 12
    assert character_count(variants) > 0
    assert {item.variant for item in variants} == {
        "english", "tanglish_latin", "telugu_script", "telugu_english",
    }


def test_rejects_variant_source_not_present_in_example_step(tmp_path):
    payload = json.loads(VARIANTS.read_text(encoding="utf-8"))
    payload["samples"][0]["source_text"] = "Not from the source"
    variants_path = tmp_path / "variants.json"
    variants_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(VoiceTestError, match="does not occur"):
        load_text_variants(variants_path, SOURCE)


def test_preview_never_calls_any_provider(tmp_path):
    variants = load_text_variants(VARIANTS, SOURCE)
    messages: list[str] = []

    assert run_listening_test(
        variants, tmp_path, {"hf_space", "elevenlabs", "edge_tts"},
        synthesize=False, text_approved=False, printer=messages.append,
    ) == 0
    assert any("no provider/API calls made" in message for message in messages)
    assert not (tmp_path / "INDEX.md").exists()


def test_hf_missing_own_reference_audio_is_skipped_without_client(tmp_path):
    variants = load_text_variants(VARIANTS, SOURCE)
    messages: list[str] = []

    result = run_listening_test(
        variants,
        tmp_path / "out",
        {"hf_space"},
        synthesize=True,
        text_approved=True,
        environment={
            "HF_TTS_SPACE": "owner/private-space",
            "HF_TOKEN": "secret",
            "HF_TTS_REFERENCE_AUDIO": str(tmp_path / "missing.wav"),
        },
        printer=messages.append,
    )

    assert result == 0
    assert any("own reference audio is missing" in message for message in messages)
    assert "secret" not in "\n".join(messages)


def test_hf_adapter_uses_inspected_schema_own_audio_and_retries_once(tmp_path):
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"own voice")
    returned_audio = tmp_path / "returned.wav"
    returned_audio.write_bytes(b"audio")
    clients: list[object] = []
    delays: list[float] = []
    file_inputs = []

    def api_schema(file_label="reference_audio_input"):
        return {
            "named_endpoints": {
                "/generate_tts_audio": {
                    "parameters": [
                        {"label": "text_input", "component": "Textbox"},
                        {"label": file_label, "component": "File"},
                        {"label": "exaggeration_input", "component": "Slider"},
                        {"label": "temperature_input", "component": "Slider"},
                        {"label": "seed_num_input", "component": "Number"},
                        {"label": "cfgw_input", "component": "Slider"},
                        {"label": "vad_trim_input", "component": "Checkbox"},
                    ]
                }
            }
        }

    class FakeClient:
        token = "secret-token"

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.calls = 0
            clients.append(self)

        def view_api(self, **kwargs):
            assert kwargs == {"print_info": False, "return_format": "dict"}
            return api_schema()

        def predict(self, *args, **kwargs):
            self.calls += 1
            assert isinstance(args[1], dict)
            assert args[1]["path"] == str(ref_audio.resolve())
            assert args[1]["meta"] == {"_type": "gradio.FileData"}
            assert kwargs["api_name"] == "/generate_tts_audio"
            if self.calls == 1:
                raise TimeoutError("cold start")
            return str(returned_audio)

    def file_handler(path):
        file_data = {"path": str(path), "meta": {"_type": "gradio.FileData"}}
        file_inputs.append(file_data)
        return file_data

    adapter = HFSpaceProvider(
        "owner/space", "secret-token", ref_audio,
        client_factory=FakeClient, sleep_fn=delays.append,
        file_handler=file_handler,
    )

    assert adapter.synthesize("test") == returned_audio
    assert clients[0].kwargs["token"] == "secret-token"
    assert clients[0].kwargs["httpx_kwargs"] == {"timeout": 600}
    assert clients[0].calls == 2
    assert file_inputs == [
        {"path": str(ref_audio.resolve()), "meta": {"_type": "gradio.FileData"}},
        {"path": str(ref_audio.resolve()), "meta": {"_type": "gradio.FileData"}},
    ]
    assert delays == [5.0]


def test_hf_adapter_uses_schema_to_find_file_input_not_a_guessed_name(tmp_path):
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"own voice")
    returned_audio = tmp_path / "returned.wav"
    returned_audio.write_bytes(b"audio")
    received = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def view_api(self, **_kwargs):
            return {
                "named_endpoints": {
                    "/generate_tts_audio": {
                        "parameters": [
                            {"label": "text_input", "component": "Textbox"},
                            {"label": "prompt_audio", "component": "Audio"},
                            {"label": "exaggeration_input", "component": "Slider"},
                            {"label": "temperature_input", "component": "Slider"},
                            {"label": "seed_num_input", "component": "Number"},
                            {"label": "cfgw_input", "component": "Slider"},
                            {"label": "vad_trim_input", "component": "Checkbox"},
                        ]
                    }
                }
            }

        def predict(self, *args, **_kwargs):
            received.append(args[1])
            return str(returned_audio)

    adapter = HFSpaceProvider(
        "owner/space",
        "token",
        ref_audio,
        client_factory=FakeClient,
        file_handler=lambda path: {"path": str(path), "meta": {"_type": "gradio.FileData"}},
    )

    assert adapter.synthesize("text") == returned_audio
    assert isinstance(received[0], dict)
    assert received[0]["meta"]["_type"] == "gradio.FileData"


def test_hf_adapter_request_limit_is_shared_across_scenes(tmp_path):
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"own voice")
    returned_audio = tmp_path / "returned.wav"
    returned_audio.write_bytes(b"audio")
    calls = []
    delays = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def view_api(self, **_kwargs):
            return {
                "named_endpoints": {
                    "/generate_tts_audio": {
                        "parameters": [
                            {"label": "text_input", "component": "Textbox"},
                            {"label": "audio_prompt_path_input", "component": "File"},
                            {"label": "exaggeration_input", "component": "Slider"},
                            {"label": "temperature_input", "component": "Slider"},
                            {"label": "seed_num_input", "component": "Number"},
                            {"label": "cfgw_input", "component": "Slider"},
                            {"label": "vad_trim_input", "component": "Checkbox"},
                        ]
                    }
                }
            }

        def predict(self, *_args, **_kwargs):
            calls.append(1)
            return str(returned_audio)

    adapter = HFSpaceProvider(
        "owner/space",
        "token",
        ref_audio,
        client_factory=FakeClient,
        sleep_fn=delays.append,
        file_handler=lambda path: {"path": str(path), "meta": {"_type": "gradio.FileData"}},
        request_limit=2,
        request_pause_s=3,
    )

    assert adapter.synthesize("first") == returned_audio
    assert adapter.synthesize("second") == returned_audio
    with pytest.raises(VoiceTestError, match="request limit reached"):
        adapter.synthesize("third")
    assert len(calls) == 2
    assert delays == [3]


def test_hf_adapter_surfaces_sanitized_space_error_after_retry(tmp_path):
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"own voice")
    delays = []

    class FakeClient:
        token = "private-token"

        def __init__(self, *_args, **_kwargs):
            self.calls = 0

        def view_api(self, **_kwargs):
            return {
                "named_endpoints": {
                    "/generate_tts_audio": {
                        "parameters": [
                            {"label": "text_input", "component": "Textbox"},
                            {"label": "audio_prompt_path_input", "component": "File"},
                            {"label": "exaggeration_input", "component": "Slider"},
                            {"label": "temperature_input", "component": "Slider"},
                            {"label": "seed_num_input", "component": "Number"},
                            {"label": "cfgw_input", "component": "Slider"},
                            {"label": "vad_trim_input", "component": "Checkbox"},
                        ]
                    }
                }
            }

        def predict(self, *_args, **_kwargs):
            self.calls += 1
            raise RuntimeError("HTTP 400: 'meta' field must be explicitly provided; private-token")

    adapter = HFSpaceProvider(
        "owner/space",
        "private-token",
        ref_audio,
        client_factory=FakeClient,
        sleep_fn=delays.append,
        file_handler=lambda path: {"path": str(path), "meta": {"_type": "gradio.FileData"}},
        request_limit=2,
    )
    with pytest.raises(VoiceTestError) as error:
        adapter.synthesize("text")
    assert "HTTP 400" in str(error.value)
    assert "'meta' field must be explicitly provided" in str(error.value)
    assert "private-token" not in str(error.value)
    assert adapter.client.calls == 2
    assert delays == [5.0]


def test_hf_adapter_rejects_uninspected_or_changed_endpoint(tmp_path):
    ref_audio = tmp_path / "ref.wav"
    ref_audio.write_bytes(b"own voice")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def view_api(self, **kwargs):
            return {"named_endpoints": {"/different": {"parameters": []}}}

    with pytest.raises(VoiceTestError, match="no longer exposes"):
        HFSpaceProvider("owner/space", "secret", ref_audio, client_factory=FakeClient)


def test_hf_adapter_rejects_missing_reference_audio_before_connecting(tmp_path):
    def no_client(*_args, **_kwargs):
        pytest.fail("missing reference audio must be detected before client construction")

    with pytest.raises(VoiceTestError, match="does not exist or cannot be resolved"):
        HFSpaceProvider(
            "owner/space",
            "secret",
            tmp_path / "missing.wav",
            client_factory=no_client,
        )


def test_edge_adapter_is_mocked_and_returns_audio_file(tmp_path):
    observed = {}

    class FakeCommunicate:
        def __init__(self, text, voice, **kwargs):
            self.text = text
            self.voice = voice
            observed.update(kwargs)

        async def stream(self):
            yield {"type": "audio", "data": b"fake mp3"}
            yield {"type": "WordBoundary", "offset": 15_000_000, "text": "hello"}

    audio = EdgeTTSProvider(
        "te-IN-ShrutiNeural", tmp_path, rate="-8%", communicate_factory=FakeCommunicate
    )
    path, boundaries = audio.synthesize_with_word_boundaries("approved text")

    assert path.suffix == ".mp3"
    assert path.read_bytes() == b"fake mp3"
    assert boundaries == (("hello", 1.5),)
    assert observed == {"rate": "-8%", "boundary": "WordBoundary"}


def test_edge_adapter_rejects_audio_without_word_boundaries(tmp_path):
    class FakeCommunicate:
        def __init__(self, *_args, **_kwargs):
            pass

        async def stream(self):
            yield {"type": "audio", "data": b"fake mp3"}

    provider = EdgeTTSProvider(
        "en-IN-NeerjaNeural", tmp_path, communicate_factory=FakeCommunicate
    )

    with pytest.raises(VoiceTestError, match="no WordBoundary metadata"):
        provider.synthesize_with_word_boundaries("approved text")


def test_elevenlabs_stock_voice_pagination_is_mocked():
    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self.payload

    class FakeSession:
        def __init__(self):
            self.params: list[dict] = []

        def get(self, url, **kwargs):
            self.params.append(kwargs["params"].copy())
            if len(self.params) == 1:
                return FakeResponse({
                    "voices": [{"voice_id": "one", "name": "Voice One"}],
                    "has_more": True,
                    "next_page_token": "next",
                })
            return FakeResponse({
                "voices": [{"voice_id": "two", "name": "Voice Two"}],
                "has_more": False,
            })

    session = FakeSession()
    voices = list_elevenlabs_stock_voices("secret", session=session)

    assert [voice["voice_id"] for voice in voices] == ["one", "two"]
    assert session.params[0]["category"] == "premade"
    assert session.params[1]["next_page_token"] == "next"


def test_elevenlabs_synthesis_uses_official_request_shape_and_is_mocked(tmp_path):
    class FakeResponse:
        content = b"fake mp3"

        def raise_for_status(self):
            pass

    class FakeSession:
        def post(self, url, **kwargs):
            assert url.endswith("/voice-id")
            assert kwargs["headers"] == {"xi-api-key": "secret"}
            assert kwargs["params"] == {"output_format": "mp3_44100_128"}
            assert kwargs["json"] == {"text": "approved text", "model_id": "eleven_v3"}
            return FakeResponse()

    audio = ElevenLabsProvider(
        "secret", "voice-id", "eleven_v3", tmp_path, session=FakeSession()
    ).synthesize("approved text")

    assert audio.suffix == ".mp3"
    assert audio.read_bytes() == b"fake mp3"


def test_elevenlabs_credit_budget_is_checked_before_voice_list(tmp_path):
    variants = load_text_variants(VARIANTS, SOURCE)
    oversized = ELEVENLABS_TEST_CREDIT_LIMIT + 1
    messages: list[str] = []

    from solution_video.voice import listening_test

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(listening_test, "print_estimates", lambda items, printer: oversized)
    monkeypatch.setattr(
        listening_test,
        "list_elevenlabs_stock_voices",
        lambda *args, **kwargs: pytest.fail("voice API must not be called over budget"),
    )
    try:
        with pytest.raises(VoiceTestError, match="exceeds"):
            run_listening_test(
                variants,
                tmp_path,
                {"elevenlabs"},
                synthesize=True,
                text_approved=True,
                environment={"ELEVENLABS_API_KEY": "secret"},
                printer=messages.append,
            )
    finally:
        monkeypatch.undo()


def test_whitespace_elevenlabs_key_skips_account_api(tmp_path, monkeypatch):
    variants = load_text_variants(VARIANTS, SOURCE)
    messages: list[str] = []

    from solution_video.voice import listening_test

    monkeypatch.setattr(
        listening_test,
        "list_elevenlabs_stock_voices",
        lambda *args, **kwargs: pytest.fail("blank API key must not make a request"),
    )
    result = run_listening_test(
        variants,
        tmp_path,
        {"elevenlabs"},
        synthesize=True,
        text_approved=True,
        environment={"ELEVENLABS_API_KEY": "   "},
        printer=messages.append,
    )

    assert result == 0
    assert any("ELEVENLABS_API_KEY is not configured" in message for message in messages)
