"""FFmpeg raw-frame streaming encoder."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from PIL import Image


class EncodeError(RuntimeError):
    """Raised when FFmpeg is absent or rejects a render."""


def ffmpeg_path() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise EncodeError("ffmpeg is required but was not found on PATH. Install ffmpeg and retry.")
    return path


def encode_frames(frames: Iterable[Image.Image], width: int, height: int, fps: int, audio_path: Path, output_path: Path, duration_s: float) -> None:
    """Pipe RGB frames directly to FFmpeg; never write temporary image frames."""
    if width <= 0 or height <= 0 or fps <= 0 or duration_s <= 0:
        raise EncodeError("width, height, fps, and duration must be positive")
    command = [
        ffmpeg_path(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps), "-i", "-", "-i", str(audio_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", "-shortest", str(output_path),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame in frames:
            if frame.size != (width, height):
                raise EncodeError(f"Frame size {frame.size} does not match {width}x{height}")
            process.stdin.write(frame.convert("RGB").tobytes())
        process.stdin.close()
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        if process.wait() != 0:
            raise EncodeError(f"ffmpeg failed: {stderr.strip() or 'unknown error'}")
    except BrokenPipeError as exc:
        raise EncodeError("ffmpeg stopped accepting raw frames") from exc
    finally:
        if process.poll() is None:
            process.kill()
