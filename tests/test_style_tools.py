from pathlib import Path
import json
import re

import pytest

from solution_video.cli import main
from solution_video.engine.theme import load_theme
from solution_video.pipeline import _apply_voice_durations, _cue_word_offset, format_sync_report, plan_scenes
from solution_video.schema import SolutionSpec
from solution_video.styles import style_theme
from solution_video.voice.normalization import normalize_speech
from solution_video.voice.runtime import VoiceClip, VoiceRender


ROOT = Path(__file__).resolve().parents[1]


def test_bench_runs_without_voice(capsys):
    assert main(["bench", "--style", "classic", "--example", str(ROOT / "examples" / "speed_train.json"), "--frames", "2"]) == 0
    output = capsys.readouterr().out
    assert "ms_per_frame" in output
    assert "PASS" in output


def test_bench_supports_two_render_workers(capsys):
    assert main([
        "bench", "--style", "classic",
        "--example", str(ROOT / "examples" / "speed_train.json"),
        "--frames", "2", "--workers", "2",
    ]) == 0
    output = capsys.readouterr().out
    assert "| 2 |" in output
    assert "60s render estimate" in output


def test_bench_fails_when_single_worker_exceeds_tier_budget(monkeypatch, capsys):
    monkeypatch.setattr(
        "solution_video.cli._benchmark_style",
        lambda _example, name, _frames, workers: {
            "style": name, "tier": 1, "workers": workers, "ms_per_frame": 100.0,
            "projected_60_s": 180.0, "budget_s": 120.0, "status": "FAIL",
        },
    )
    assert main([
        "bench", "--style", "all", "--example", str(ROOT / "examples" / "speed_train.json"),
        "--frames", "2",
    ]) == 5
    assert "FAIL" in capsys.readouterr().out


def test_gallery_writes_sheets_reel_and_index(tmp_path, monkeypatch):
    def fake_bench(example, style_name, frame_count, workers):
        return {
            "style": style_name, "tier": 1, "ms_per_frame": 2.0,
            "projected_60_s": 3.6, "budget_s": 120.0, "status": "PASS",
        }

    def fake_reel(example, styles, output_dir):
        (output_dir / "style-reel.mp4").write_bytes(b"reel")
        return {name: 100 for name in styles}

    monkeypatch.setattr("solution_video.cli._benchmark_style", fake_bench)
    monkeypatch.setattr("solution_video.cli._write_gallery_reel", fake_reel)
    assert main(["gallery", "--example", str(ROOT / "examples" / "time_work.json"), "--styles", "classic,glassmorphism", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "time_work-classic.png").is_file()
    assert (tmp_path / "time_work-glassmorphism.png").is_file()
    assert (tmp_path / "style-reel.mp4").is_file()
    assert "Preview MP4 bytes" in (tmp_path / "index.md").read_text(encoding="utf-8")


def test_auto_skips_heavy_styles_and_obeys_allowlist(monkeypatch):
    from solution_video.styles import resolve_style

    monkeypatch.delenv("STYLE_ALLOW_HEAVY", raising=False)
    assert resolve_style("auto", 1, ("ray_marched_fractals", "classic")).name == "classic"
    monkeypatch.setenv("STYLE_ALLOW_HEAVY", "1")
    assert resolve_style("auto", 1, ("ray_marched_fractals",)).name == "ray_marched_fractals"


def test_scene_styles_are_applied_only_when_explicitly_enabled():
    payload = (ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")
    spec = SolutionSpec.from_payload(json.loads(payload))
    theme = load_theme()
    from dataclasses import replace

    configured = replace(theme, scene_styles={"title": "neon_glow", "step": "glassmorphism"})
    default_plan = plan_scenes(spec, style_theme(configured, "classic"))
    override_plan = plan_scenes(spec, style_theme(configured, "classic"), allow_scene_styles=True)
    assert default_plan[0].scene.theme.style == "classic"
    assert override_plan[0].scene.theme.style == "neon_glow"
    assert override_plan[2].scene.theme.style == "glassmorphism"


def test_unavailable_scene_style_falls_back_to_video_style():
    from dataclasses import replace

    spec = SolutionSpec.from_payload(json.loads(
        (ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")
    ))
    theme = replace(
        style_theme(load_theme(), "glassmorphism"),
        style_allowlist=("glassmorphism",),
        scene_styles={"title": "bauhaus_shapes"},
    )
    with pytest.warns(RuntimeWarning, match="using video style 'glassmorphism'"):
        plan = plan_scenes(spec, theme, allow_scene_styles=True)
    assert plan[0].scene.theme.style == "glassmorphism"


def test_background_style_crash_falls_back_to_classic(monkeypatch):
    from solution_video.scenes import common

    class BrokenStyle:
        name = "broken"
        requires_text_mask = False
        handles_background_fx = True

        def background(self, _canvas, _context):
            raise AttributeError("synthetic effect crash")

        def begin_frame(self, _context):
            return None

    monkeypatch.setattr(common, "resolve_style", lambda *_args, **_kwargs: BrokenStyle())
    with pytest.warns(RuntimeWarning, match="background failed.*using classic"):
        canvas = common.make_canvas(load_theme(), 0.5, 7)
    assert canvas.final_rgb().size == (720, 1280)


def test_post_style_crash_falls_back_to_classic(monkeypatch):
    from solution_video import pipeline
    from solution_video.scenes import common

    class BrokenStyle:
        name = "broken"

        def post(self, frame, _context):
            raise KeyError("synthetic effect crash")

    monkeypatch.setattr(pipeline, "resolve_style", lambda *_args, **_kwargs: BrokenStyle())
    spec = SolutionSpec.from_payload(json.loads(
        (ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")
    ))
    theme = style_theme(load_theme(), "classic")
    plan = pipeline.plan_scenes(spec, theme)
    with pytest.warns(RuntimeWarning, match="post-effect failed.*using classic"):
        frame = plan[0].render_frame(1.0, theme)
    assert frame.size == (720, 1280)


def test_style_does_not_move_cached_word_cues():
    from solution_video.pipeline import _speech_inputs

    payload = (ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")
    spec = SolutionSpec.from_payload(json.loads(payload))
    base = load_theme()
    reports = []
    for style_name in ("classic", "glassmorphism", "kinetic_typography"):
        theme = style_theme(base, style_name)
        plan = plan_scenes(spec, theme)
        inputs = _speech_inputs(spec)
        clips = []
        for item, voice_input in zip(plan, inputs):
            words = re.findall(r"[a-z0-9]+", normalize_speech(voice_input.text).casefold())
            boundaries = tuple((word, index * 0.1) for index, word in enumerate(words))
            clips.append(VoiceClip(Path("cached.wav"), max(1.0, len(words) * 0.1), "edge_tts", "test", 0, 0, voice_input.text, boundaries))
        voice = VoiceRender(tuple(clips), (), "edge_tts", "test", 0, 0)
        aligned = _apply_voice_durations(plan, voice, 0.45)
        report = format_sync_report(aligned, voice)
        assert "Sync table (video time)" in report
        assert "proportional fallback" not in report
        checks = []
        for item, clip in zip(aligned, clips):
            for cue in item.reveal_cues:
                expected = _cue_word_offset(item, cue.name, clip.word_boundaries)
                if expected is not None:
                    actual = item.cue_time(cue.name)
                    checks.append(actual >= expected - 0.15 - 1e-6)
        assert checks and all(checks)
        reports.append(report)
    assert reports[0] == reports[1] == reports[2]


def test_noisy_style_size_retry_raises_crf_and_fails_clearly(tmp_path, monkeypatch):
    from solution_video import pipeline
    from solution_video.engine.output import OutputValidationError

    theme = load_theme()
    audio = tmp_path / "silence.wav"
    output = tmp_path / "large.mp4"
    output.write_bytes(b"")
    monkeypatch.setattr(pipeline, "MAX_OUTPUT_BYTES", 10)
    attempts = []

    def fake_encode(_frames, _width, _height, _fps, _audio, target, _duration, *, crf=23):
        attempts.append(crf)
        target.write_bytes(b"x" * (20 if crf == 23 else 15))

    monkeypatch.setattr(pipeline, "encode_frames", fake_encode)
    with pytest.raises(OutputValidationError, match="after CRF 29"):
        pipeline._encode_with_size_retry(lambda: (), theme, audio, output, 10.0, "glitch")
    assert attempts == [23, 29]
    assert not output.exists()
