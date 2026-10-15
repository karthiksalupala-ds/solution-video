from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

import pytest
from PIL import Image

from solution_video.engine.encode import encode_frames
from solution_video.engine.output import (
    MAX_OUTPUT_BYTES,
    MediaInfo,
    OutputValidationError,
    _reencode_to_limit,
    validate_output,
)


def test_invalid_mp4_is_rejected(tmp_path, monkeypatch):
    output = tmp_path / "bad.mp4"
    output.write_bytes(b"not an mp4")
    monkeypatch.setattr("solution_video.engine.output.shutil.which", lambda _: "ffprobe")
    monkeypatch.setattr(
        "solution_video.engine.output.subprocess.run",
        lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "ffprobe")),
    )

    with pytest.raises(OutputValidationError, match="Unable to inspect"):
        validate_output(output)


def test_oversized_output_gets_reencoded_then_fails_if_still_too_large(tmp_path, monkeypatch):
    output = tmp_path / "large.mp4"
    with output.open("wb") as file:
        file.truncate(MAX_OUTPUT_BYTES + 1)
    valid_streams = MediaInfo("h264", "aac", "yuv420p", 720, 1280, 30.0, 10.0)
    calls = []
    monkeypatch.setattr("solution_video.engine.output._probe", lambda _: valid_streams)
    monkeypatch.setattr("solution_video.engine.output._reencode_to_limit", lambda path, duration: calls.append((path, duration)))

    with pytest.raises(OutputValidationError, match="remains larger than 16 MiB"):
        validate_output(output)
    assert calls == [(output, 10.0)]


def test_bitrate_reencode_replaces_original_with_smaller_file(tmp_path, monkeypatch):
    output = tmp_path / "large.mp4"
    output.write_bytes(b"x" * (MAX_OUTPUT_BYTES + 1))
    valid_streams = MediaInfo("h264", "aac", "yuv420p", 720, 1280, 30.0, 10.0)
    monkeypatch.setattr("solution_video.engine.output.shutil.which", lambda _: "ffmpeg")
    monkeypatch.setattr("solution_video.engine.output._probe", lambda _: valid_streams)
    commands = []

    def fake_ffmpeg(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"smaller valid mp4")

    monkeypatch.setattr("solution_video.engine.output.subprocess.run", fake_ffmpeg)

    _reencode_to_limit(output, 10.0)

    assert output.read_bytes() == b"smaller valid mp4"
    assert "-b:v" in commands[0]
    assert commands[0][commands[0].index("-c:a") + 1] == "aac"


def test_invalid_stream_constraints_are_reported(tmp_path, monkeypatch):
    output = tmp_path / "wrong.mp4"
    output.write_bytes(b"small")
    monkeypatch.setattr(
        "solution_video.engine.output._probe",
        lambda _: MediaInfo("mpeg4", "mp3", "yuv444p", 640, 480, 25.0, 3.0),
    )

    with pytest.raises(OutputValidationError, match="expected h264"):
        validate_output(output)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ffmpeg/ffprobe are required")
def test_valid_mp4_passes_output_validation(tmp_path):
    import wave

    audio = tmp_path / "silence.wav"
    with wave.open(str(audio), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44_100)
        output.writeframes(b"\x00\x00" * 4_410)
    video = tmp_path / "valid.mp4"
    encode_frames((Image.new("RGB", (720, 1280), "black") for _ in range(3)), 720, 1280, 30, audio, video, 0.1)

    info = validate_output(video)

    assert info.video_codec == "h264"
    assert info.audio_codec == "aac"
    assert (info.width, info.height) == (720, 1280)
    assert info.pixel_format == "yuv420p"
    assert info.fps == pytest.approx(30)
