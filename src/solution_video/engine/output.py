"""Validate and, when needed, bitrate-constrain completed MP4 files."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


MAX_OUTPUT_BYTES = 16 * 1024 * 1024


class OutputValidationError(RuntimeError):
    """Raised when a rendered MP4 violates a delivery constraint."""


@dataclass(frozen=True)
class MediaInfo:
    video_codec: str
    audio_codec: str | None
    pixel_format: str | None
    width: int
    height: int
    fps: float
    duration_s: float


def validate_output(path: Path, *, expect_audio: bool = True) -> MediaInfo:
    """Validate a rendered MP4, trying one lower-bitrate encode if it is too large."""
    if not path.is_file():
        raise OutputValidationError(f"Rendered output does not exist: {path}")
    info = _probe(path)
    _validate_streams(info, expect_audio=expect_audio)
    if path.stat().st_size > MAX_OUTPUT_BYTES:
        _reencode_to_limit(path, info.duration_s)
        info = _probe(path)
        _validate_streams(info, expect_audio=expect_audio)
        if path.stat().st_size > MAX_OUTPUT_BYTES:
            raise OutputValidationError(
                f"Output remains larger than 16 MiB after bitrate reduction "
                f"({path.stat().st_size} bytes)"
            )
    return info


def _probe(path: Path) -> MediaInfo:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise OutputValidationError("ffprobe is required to validate MP4 output but was not found on PATH.")
    command = [
        ffprobe, "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate,avg_frame_rate",
        "-of", "json", str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        payload = json.loads(completed.stdout)
        streams = payload["streams"]
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        duration = float(payload["format"]["duration"])
        fps = float(Fraction(rate))
        return MediaInfo(
            video_codec=str(video.get("codec_name", "")),
            audio_codec=str(audio["codec_name"]) if audio else None,
            pixel_format=video.get("pix_fmt"),
            width=int(video.get("width", 0)),
            height=int(video.get("height", 0)),
            fps=fps,
            duration_s=duration,
        )
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError, StopIteration, TypeError, ValueError, ZeroDivisionError) as exc:
        raise OutputValidationError(f"Unable to inspect rendered MP4 with ffprobe: {exc}") from exc


def _validate_streams(info: MediaInfo, *, expect_audio: bool) -> None:
    failures = []
    if info.video_codec != "h264":
        failures.append(f"video codec is {info.video_codec or 'missing'}, expected h264")
    if info.audio_codec != "aac":
        if info.audio_codec is None and not expect_audio:
            pass
        else:
            failures.append(f"audio codec is {info.audio_codec or 'missing'}, expected aac")
    if info.pixel_format != "yuv420p":
        failures.append(f"pixel format is {info.pixel_format or 'missing'}, expected yuv420p")
    if (info.width, info.height) != (720, 1280):
        failures.append(f"frame size is {info.width}x{info.height}, expected 720x1280")
    if abs(info.fps - 30.0) > 0.01:
        failures.append(f"frame rate is {info.fps:g}, expected 30 fps")
    if info.duration_s <= 0:
        failures.append("duration must be positive")
    if failures:
        raise OutputValidationError("Output constraints failed: " + "; ".join(failures))


def _reencode_to_limit(path: Path, duration_s: float) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OutputValidationError("Output exceeds 16 MiB and ffmpeg was not found for bitrate reduction.")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=path.suffix, dir=path.parent)
    os.close(fd)
    Path(temp_name).unlink(missing_ok=True)
    try:
        temp_path = Path(temp_name)
        target_total_bps = MAX_OUTPUT_BYTES * 8 / duration_s * 0.82
        video_bps = max(100_000, int(target_total_bps - 64_000))
        command = [
            ffmpeg, "-y", "-v", "error", "-i", str(path),
            "-c:v", "libx264", "-b:v", str(video_bps), "-maxrate", str(video_bps),
            "-bufsize", str(video_bps * 2), "-pix_fmt", "yuv420p", "-r", "30",
            "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(temp_path),
        ]
        subprocess.run(command, check=True, capture_output=True, timeout=180)
        temp_info = _probe(temp_path)
        _validate_streams(temp_info, expect_audio=True)
        if temp_path.stat().st_size <= MAX_OUTPUT_BYTES:
            temp_path.replace(path)
    except (OSError, subprocess.SubprocessError) as exc:
        raise OutputValidationError(f"Bitrate reduction failed: {exc}") from exc
    finally:
        try:
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            pass
