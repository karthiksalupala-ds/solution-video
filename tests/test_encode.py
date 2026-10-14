import shutil
from pathlib import Path

import pytest
from PIL import Image

from solution_video.engine.encode import EncodeError, encode_frames, ffmpeg_path


def test_missing_ffmpeg_has_clear_error(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(EncodeError, match="not found on PATH"):
        ffmpeg_path()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed locally")
def test_encode_smoke(tmp_path: Path):
    audio = tmp_path / "silence.wav"
    import wave
    with wave.open(str(audio), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44_100)
        output.writeframes(b"\x00\x00" * 4_410)
    output_path = tmp_path / "smoke.mp4"
    encode_frames((Image.new("RGB", (64, 64), "black") for _ in range(3)), 64, 64, 30, audio, output_path, 0.1)
    assert output_path.exists() and output_path.stat().st_size > 0
