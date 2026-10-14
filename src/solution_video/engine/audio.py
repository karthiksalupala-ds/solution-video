"""Small deterministic synthesized SFX mixer."""

from __future__ import annotations

import math
import wave
from pathlib import Path

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
        self._add(start_s, smooth * envelope, 0.055)

    def add_tick(self, start_s: float) -> None:
        time = np.arange(round(self.sample_rate * 0.04)) / self.sample_rate
        self._add(start_s, np.sin(2 * math.pi * 1500 * time) * np.exp(-75 * time), 0.13)

    def add_ding(self, start_s: float) -> None:
        time = np.arange(round(self.sample_rate * 0.75)) / self.sample_rate
        signal = (np.sin(2 * math.pi * 880 * time) + 0.45 * np.sin(2 * math.pi * 1320 * time)) * np.exp(-4 * time)
        self._add(start_s, signal, 0.12)

    def mix(self) -> np.ndarray:
        peak = float(np.max(np.abs(self.samples)))
        return self.samples if peak == 0 else self.samples / peak * 0.80


def write_wav(path: str | Path, samples: np.ndarray, sample_rate: int = 44_100) -> None:
    """Write mono signed-16-bit PCM with no external codec dependency."""
    clipped = np.clip(samples, -1.0, 1.0)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes((clipped * 32767).astype(np.int16).tobytes())
