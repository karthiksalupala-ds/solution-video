"""Small deterministic synthesized SFX mixer."""

from __future__ import annotations

import math
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np


class AudioMixer:
    """Mono float mixer; events are added by value and normalized only at export."""

    def __init__(self, sample_rate: int, duration_s: float, seed: int) -> None:
        self.sample_rate = sample_rate
        self.samples = np.zeros(round(sample_rate * duration_s), dtype=np.float64)
        self.rng = np.random.default_rng(seed)

    def _add(self, start_s: float, signal: np.ndarray, gain: float) -> None:
        start = max(0, round(start_s * self.sample_rate))
        stop = min(len(self.samples), start + len(signal))
        if stop > start:
            self.samples[start:stop] += signal[: stop - start] * gain

    def add_pop(self, start_s: float) -> None:
        time = np.arange(round(self.sample_rate * 0.12)) / self.sample_rate
        self._add(start_s, np.sin(2 * math.pi * (450 * time + 1800 * time**2)) * np.exp(-30 * time), 0.20)

    def add_whoosh(self, start_s: float) -> None:
        length = round(self.sample_rate * 0.45)
        time = np.arange(length) / self.sample_rate
        noise = self.rng.standard_normal(length)
        smooth = np.convolve(noise, np.ones(10) / 10, mode="same")
        envelope = np.sin(np.linspace(0, math.pi, length)) ** 2
        self._add(start_s, smooth * envelope, 0.035)

    def add_tick(self, start_s: float) -> None:
        time = np.arange(round(self.sample_rate * 0.04)) / self.sample_rate
        self._add(start_s, np.sin(2 * math.pi * 1500 * time) * np.exp(-75 * time), 0.08)

    def add_ding(self, start_s: float) -> None:
        time = np.arange(round(self.sample_rate * 0.75)) / self.sample_rate
        signal = (np.sin(2 * math.pi * 880 * time) + 0.45 * np.sin(2 * math.pi * 1320 * time)) * np.exp(-4 * time)
        self._add(start_s, signal, 0.08)

    def mix(self) -> np.ndarray:
        peak = float(np.max(np.abs(self.samples)))
        return self.samples if peak == 0 else self.samples / peak * 0.32


class LoudnessError(RuntimeError):
    """Raised when a final mix cannot meet the delivery loudness floor."""


@dataclass(frozen=True)
class LoudnessInfo:
    mean_db: float
    max_db: float


def normalize_final_mix(source: Path, destination: Path, *, narration_exists: bool) -> LoudnessInfo:
    """Apply a conservative final peak limiter while preserving source mean within gain."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise LoudnessError("ffmpeg is required to normalize the final audio mix")
    source_info = measure_loudness(source)
    gain_db = min(0.0, -1.5 - source_info.max_db)
    filters = "aresample=192k"
    if gain_db < 0.0:
        filters += f",volume={gain_db:.3f}dB"
    filters += ",alimiter=limit=-1.5dB:attack=5:release=50:level=disabled"
    command = [
        ffmpeg, "-y", "-v", "error", "-i", str(source), "-af", filters,
        "-ac", "1", "-ar", "44100", str(destination),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise LoudnessError(f"final loudness normalization failed: {exc}") from exc
    info = measure_loudness(destination)
    if info.max_db > -1.5:
        raise LoudnessError(
            f"final mix peak remains {info.max_db:.1f} dB after the true-peak limiter "
            "(limit -1.5 dB)"
        )
    if narration_exists and info.mean_db < -40.0:
        raise LoudnessError(f"narrated mix mean volume is {info.mean_db:.1f} dB, below -40 dB")
    return info


def measure_loudness(path: Path) -> LoudnessInfo:
    """Read ffmpeg volumedetect metrics without printing provider or media details."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise LoudnessError("ffmpeg is required to measure final audio loudness")
    try:
        completed = subprocess.run(
            [ffmpeg, "-v", "info", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
            check=True, capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LoudnessError(f"final loudness measurement failed: {exc}") from exc
    mean = re.search(r"mean_volume:\s*([-+0-9.]+) dB", completed.stderr)
    maximum = re.search(r"max_volume:\s*([-+0-9.]+) dB", completed.stderr)
    if not mean or not maximum:
        raise LoudnessError("ffmpeg did not return volumedetect metrics")
    return LoudnessInfo(float(mean.group(1)), float(maximum.group(1)))


def write_wav(path: str | Path, samples: np.ndarray, sample_rate: int = 44_100) -> None:
    """Write mono signed-16-bit PCM with no external codec dependency."""
    clipped = np.clip(samples, -1.0, 1.0)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes((clipped * 32767).astype(np.int16).tobytes())


def mix_voice_tracks(
    effects_path: Path,
    voice_tracks: Sequence[tuple[Path, float]],
    output_path: Path,
    duration_s: float,
    sample_rate: int = 44_100,
) -> None:
    """Mix narration over SFX, ducking effects while speech is active."""
    length = round(sample_rate * duration_s)
    effects = _read_mono_wav(effects_path, sample_rate, length)
    voice = np.zeros(length, dtype=np.float64)
    speech_mask = np.zeros(length, dtype=bool)
    for path, start_s in voice_tracks:
        samples = _read_mono_wav(path, sample_rate)
        start = max(0, round(start_s * sample_rate))
        stop = min(length, start + len(samples))
        if stop <= start:
            continue
        voice[start:stop] += samples[: stop - start]
        speech_mask[start:stop] = True
    effects[speech_mask] *= 0.25
    mixed = effects + voice
    peak = float(np.max(np.abs(mixed))) if len(mixed) else 0.0
    if peak > 0.95:
        mixed *= 0.95 / peak
    write_wav(output_path, mixed, sample_rate)


def _read_mono_wav(path: Path, sample_rate: int, length: int | None = None) -> np.ndarray:
    with wave.open(str(path), "rb") as audio:
        channels = audio.getnchannels()
        width = audio.getsampwidth()
        rate = audio.getframerate()
        frames = audio.readframes(audio.getnframes())
    if width != 2 or rate != sample_rate:
        raise ValueError(f"Audio track {path} must be 16-bit PCM at {sample_rate} Hz")
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float64) / 32768
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if length is not None:
        if len(samples) < length:
            samples = np.pad(samples, (0, length - len(samples)))
        else:
            samples = samples[:length]
    return samples
