from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import wave

from solution_video.engine.audio import write_wav
from solution_video.engine.theme import load_theme
from solution_video.pipeline import _speech_inputs, render
from solution_video.schema import SolutionSpec
from solution_video.voice.runtime import VoiceClip, VoiceRender


ROOT = Path(__file__).resolve().parents[1]


def test_speech_inputs_keep_title_and_intro_but_skip_question_and_options():
    spec = SolutionSpec.from_payload(
        json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8"))
    )
    inputs = _speech_inputs(spec)
    texts = [item.text for item in inputs if item.text is not None]

    assert inputs[0].text == "Day 10. Speed, Time & Distance. Let's work this out together."
    assert inputs[1].name == "question"
    assert inputs[1].text is None
    assert spec.question_input.question not in texts
    assert "Option B: 90." not in texts


def test_elevenlabs_attribution_is_theme_controlled():
    from solution_video.pipeline import _voice_theme

    theme = load_theme()
    sample = VoiceClip(Path("cached.wav"), 1.0, "elevenlabs", "eleven_v3", 20, 20, "speech")

    public_theme = _voice_theme(theme, VoiceRender((sample,), (), "elevenlabs", "eleven_v3", 20, 20))
    assert public_theme.branding["voice_attribution_text"] == "Voice: ElevenLabs"
    private_theme = replace(theme, voice={**theme.voice, "public_facing": False})
    assert "voice_attribution_text" not in _voice_theme(
        private_theme, VoiceRender((sample,), (), "elevenlabs", "eleven_v3", 20, 20)
    ).branding


def test_render_mixes_mocked_voice_aligns_scenes_and_writes_safe_metadata(tmp_path, monkeypatch):
    import solution_video.pipeline as pipeline

    spec = SolutionSpec.from_payload(json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    theme = load_theme()
    theme = replace(theme, voice={**theme.voice, "captions": True, "scene_padding_s": 0.25})
    clip_dir = tmp_path / "voice"
    clip_dir.mkdir()
    observed = {}

    def fake_synthesize(inputs, **kwargs):
        clips = []
        for index, item in enumerate(inputs):
            if item.text is None:
                clips.append(None)
                continue
            path = clip_dir / f"{index}.wav"
            time = np.arange(15_435) / 44_100
            write_wav(path, 0.12 * np.sin(2 * np.pi * 220 * time))
            clips.append(VoiceClip(path, 0.35, "edge_tts", "en-IN-NeerjaNeural", len(item.text), 0, item.text))
        voiced = [clip for clip in clips if clip is not None]
        return VoiceRender(tuple(clips), (), "edge_tts", "en-IN-NeerjaNeural", sum(c.characters for c in voiced), 0)

    def fake_encode(frames, width, height, fps, audio_path, output_path, duration_s):
        rendered_frames = list(frames)
        observed.update({
            "frame_count": len(rendered_frames),
            "frame_size": rendered_frames[0].size,
            "audio_path": audio_path,
            "duration_s": duration_s,
        })
        with wave.open(str(audio_path), "rb") as mixed:
            observed["audio_rate"] = mixed.getframerate()
            observed["audio_frames"] = mixed.getnframes()
        output_path.write_bytes(b"mocked encoded output")

    monkeypatch.setattr(pipeline, "synthesize_voice", fake_synthesize)
    monkeypatch.setattr(pipeline, "encode_frames", fake_encode)
    monkeypatch.setattr(pipeline, "validate_output", lambda *args, **kwargs: None)
    output_path = tmp_path / "solution.mp4"

    meta = render(spec, theme, output_path)

    assert meta.answer_verified
    assert meta.voice_provider == "edge_tts"
    assert meta.voice_model == "en-IN-NeerjaNeural"
    assert meta.voice_credits == 0
    assert meta.voice_characters > 0
    assert len(meta.voice_clips) == len(spec.steps) + 3
    assert all(clip.duration_s == 0.35 for clip in meta.voice_clips)
    assert meta.duration_s == observed["duration_s"] <= 75
    assert observed["frame_size"] == (theme.canvas.width, theme.canvas.height)
    assert observed["audio_rate"] == 44_100
    assert observed["audio_frames"] == round(meta.duration_s * 44_100)
    assert observed["frame_count"] > 0
    assert not output_path.with_suffix(".phase2.wav").exists()
    assert not output_path.with_suffix(".phase5.wav").exists()
    stored = json.loads(output_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert "test-key" not in json.dumps(stored)


def test_complete_narration_may_exceed_requested_time_target_but_not_75_seconds(tmp_path, monkeypatch):
    import solution_video.pipeline as pipeline

    spec = SolutionSpec.from_payload(json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    clip_path = tmp_path / "voice.wav"
    clip_path.write_bytes(b"mock audio")

    def fake_synthesize(inputs, **_kwargs):
        clips = tuple(
            None if item.text is None else VoiceClip(
                clip_path, 10.0, "edge_tts", "en-IN-NeerjaNeural", len(item.text), 0, item.text
            )
            for item in inputs
        )
        return VoiceRender(
            clips,
            (),
            "edge_tts",
            "en-IN-NeerjaNeural",
            sum(clip.characters for clip in clips if clip is not None),
            0,
        )

    class FakeMixer:
        def __init__(self, *_args):
            pass

        def add_whoosh(self, *_args):
            pass

        def add_tick(self, *_args):
            pass

        def add_ding(self, *_args):
            pass

        def mix(self):
            return np.zeros(0)

    monkeypatch.setattr(pipeline, "synthesize_voice", fake_synthesize)
    monkeypatch.setattr(pipeline, "AudioMixer", FakeMixer)
    monkeypatch.setattr(pipeline, "write_wav", lambda path, *_args: Path(path).write_bytes(b"mock effects"))
    monkeypatch.setattr(
        pipeline,
        "mix_voice_tracks",
        lambda _effects, _tracks, output, _duration: Path(output).write_bytes(b"mock mixed audio"),
    )
    monkeypatch.setattr(pipeline, "normalize_final_mix", lambda *_args, **_kwargs: SimpleNamespace(mean_db=-18.0))
    monkeypatch.setattr(pipeline, "encode_frames", lambda *_args, **_kwargs: Path(_args[5]).write_bytes(b"mock video"))
    monkeypatch.setattr(pipeline, "validate_output", lambda *_args, **_kwargs: None)

    meta = render(spec, load_theme(), tmp_path / "complete.mp4")

    assert meta.duration_s > spec.question_input.time_sec
    assert meta.duration_s <= 75
