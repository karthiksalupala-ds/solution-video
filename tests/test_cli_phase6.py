from __future__ import annotations

import json
from pathlib import Path

import pytest

from solution_video.cli import main
from solution_video.engine.encode import EncodeError
from solution_video.engine.output import OutputValidationError


ROOT = Path(__file__).resolve().parents[1]


def test_validate_question_and_solution_examples(capsys):
    assert main(["validate", "--input", str(ROOT / "examples" / "speed_train.json")]) == 0
    assert "accuracy gate passed" in capsys.readouterr().out

    raw_question = json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8"))
    raw_question.pop("expected_steps")
    input_path = ROOT / "out" / "phase6-question.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(raw_question), encoding="utf-8")
    try:
        assert main(["validate", "--input", str(input_path)]) == 0
        assert "Valid question input" in capsys.readouterr().out
    finally:
        input_path.unlink(missing_ok=True)


def test_dry_run_prints_plan_without_creating_video(tmp_path, capsys):
    output = tmp_path / "dry-run.mp4"
    result = main([
        "render", "--input", str(ROOT / "examples" / "di_average.json"),
        "--out", str(output), "--dry-run", "--seed", "17",
    ])

    plan = json.loads(capsys.readouterr().out)
    assert result == 0
    assert plan["renders"] is False
    assert plan["scenes"][0]["name"] == "title"
    assert plan["voice_estimate"]["provider"] == "hf_space"
    assert plan["voice_estimate"]["characters"] > 0
    assert not output.exists()


def test_dry_run_elevenlabs_estimate_does_not_need_or_call_credentials(tmp_path, capsys, monkeypatch):
    import requests

    monkeypatch.setattr(
        requests.Session,
        "get",
        lambda *args, **kwargs: pytest.fail("dry-run must not contact ElevenLabs"),
    )
    result = main([
        "render", "--input", str(ROOT / "examples" / "speed_train.json"),
        "--out", str(tmp_path / "dry-run.mp4"), "--dry-run",
        "--voice-provider", "elevenlabs",
    ])

    plan = json.loads(capsys.readouterr().out)
    assert result == 0
    assert plan["voice_estimate"]["provider"] == "elevenlabs"
    assert plan["voice_estimate"]["model"] == "eleven_multilingual_v2"
    assert plan["voice_estimate"]["estimated_credits"] == plan["voice_estimate"]["characters"]


def test_cli_maps_output_validation_failure_to_exit_5(tmp_path, monkeypatch, capsys):
    import solution_video.cli as cli

    monkeypatch.setattr(cli, "render", lambda *args, **kwargs: (_ for _ in ()).throw(OutputValidationError("bad file")))

    result = main([
        "render", "--input", str(ROOT / "examples" / "di_average.json"),
        "--out", str(tmp_path / "bad.mp4"), "--no-voice",
    ])

    assert result == 5
    assert "Output constraints failed" in capsys.readouterr().err


def test_cli_maps_render_failure_to_exit_4(tmp_path, monkeypatch, capsys):
    import solution_video.cli as cli

    monkeypatch.setattr(cli, "render", lambda *args, **kwargs: (_ for _ in ()).throw(EncodeError("ffmpeg failed")))

    result = main([
        "render", "--input", str(ROOT / "examples" / "di_average.json"),
        "--out", str(tmp_path / "failed.mp4"), "--no-voice",
    ])

    assert result == 4
    assert "Render failed" in capsys.readouterr().err


def test_voice_test_previews_approved_variants_without_network(capsys):
    assert main(["voice-test"]) == 0
    output = capsys.readouterr().out
    assert "Preview only; no provider/API calls made" in output
    assert "ElevenLabs total estimate:" in output
    assert "1.english:" in output


def test_package_version_is_semantic():
    from solution_video import __version__

    assert __version__ == "0.2.0"


def test_public_render_from_today_returns_typed_meta(monkeypatch, tmp_path):
    import solution_video.api as api
    from solution_video import Meta
    from solution_video.schema import SolutionSpec

    question_payload = json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8"))
    question_payload.pop("expected_steps")
    input_path = tmp_path / "today.json"
    input_path.write_text(json.dumps(question_payload), encoding="utf-8")
    expected_spec = SolutionSpec.from_payload(json.loads((ROOT / "examples" / "speed_train.json").read_text(encoding="utf-8")))
    expected_meta = Meta(path="solution.mp4", duration_s=10, size_bytes=100, answer_verified=True)
    monkeypatch.setattr(api, "GroqProvider", lambda: object())
    monkeypatch.setattr(api, "generate_steps", lambda question, provider, **kwargs: expected_spec)
    monkeypatch.setattr(api, "render_spec", lambda spec, theme, output_path, **kwargs: expected_meta)

    result = api.render_from_today(input_path, tmp_path / "solution.mp4", no_voice=True)

    assert result is expected_meta
