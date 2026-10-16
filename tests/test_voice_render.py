from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import wave

from solution_video.engine.audio import write_wav
from solution_video.engine.theme import load_theme
from solution_video.pipeline import render
from solution_video.schema import SolutionSpec
from solution_video.voice.runtime import VoiceClip, VoiceRender


ROOT = Path(__file__).resolve().parents[1]


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
            path = clip_dir / f"{index}.wav"
            time = np.arange(15_435) / 44_100
            write_wav(path, 0.12 * np.sin(2 * np.pi * 220 * time))
            clips.append(VoiceClip(path, 0.35, "edge_tts", "en-IN-NeerjaNeural", len(item.text), 0, item.text))
        return VoiceRender(tuple(clips), (), "edge_tts", "en-IN-NeerjaNeural", sum(c.characters for c in clips), 0)

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
    assert len(meta.voice_clips) == len(spec.steps) + 4
    assert meta.duration_s == observed["duration_s"] <= 75
    assert observed["frame_size"] == (theme.canvas.width, theme.canvas.height)
    assert observed["audio_rate"] == 44_100
    assert observed["audio_frames"] == round(meta.duration_s * 44_100)
    assert observed["frame_count"] > 0
    assert not output_path.with_suffix(".phase2.wav").exists()
    assert not output_path.with_suffix(".phase5.wav").exists()
    stored = json.loads(output_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert "test-key" not in json.dumps(stored)
