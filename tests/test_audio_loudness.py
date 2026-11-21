from pathlib import Path

import pytest

from solution_video.engine.audio import LoudnessError, LoudnessInfo, normalize_final_mix


def test_loudnorm_uses_delivery_target(monkeypatch, tmp_path):
    commands = []
    monkeypatch.setattr("solution_video.engine.audio.shutil.which", lambda _: "ffmpeg")
    monkeypatch.setattr("solution_video.engine.audio.subprocess.run", lambda command, **kwargs: commands.append(command))
    monkeypatch.setattr("solution_video.engine.audio.measure_loudness", lambda _: LoudnessInfo(-16.1, -1.0))
    info = normalize_final_mix(tmp_path / "in.wav", tmp_path / "out.wav", narration_exists=True)
    assert info.mean_db == -16.1
    assert "loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=-1.5dB:level=0" in commands[0]


def test_quiet_narrated_mix_fails(monkeypatch, tmp_path):
    monkeypatch.setattr("solution_video.engine.audio.shutil.which", lambda _: "ffmpeg")
    monkeypatch.setattr("solution_video.engine.audio.subprocess.run", lambda *args, **kwargs: None)
    monkeypatch.setattr("solution_video.engine.audio.measure_loudness", lambda _: LoudnessInfo(-41.0, -2.0))
    with pytest.raises(LoudnessError, match="below -40"):
        normalize_final_mix(tmp_path / "in.wav", tmp_path / "out.wav", narration_exists=True)
