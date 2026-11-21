"""Vectorized, deterministic helpers shared by future style packs."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from PIL import Image, ImageFilter


def float32_rgba(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0


def alpha_composite(base: np.ndarray, overlay: np.ndarray) -> np.ndarray:
    source_alpha = overlay[..., 3:4]
    destination_alpha = base[..., 3:4]
    output_alpha = source_alpha + destination_alpha * (1.0 - source_alpha)
    output_rgb = overlay[..., :3] * source_alpha + base[..., :3] * destination_alpha * (1.0 - source_alpha)
    output_rgb = np.divide(output_rgb, output_alpha, out=np.zeros_like(output_rgb), where=output_alpha > 1e-6)
    return np.concatenate((output_rgb, output_alpha), axis=-1)


def gaussian_blur(image: Image.Image, radius: float) -> Image.Image:
    return image.filter(ImageFilter.GaussianBlur(max(0.0, radius)))


def value_noise(width: int, height: int, seed: int, cells: int = 12) -> np.ndarray:
    rng = np.random.default_rng(seed)
    coarse = rng.random((max(2, cells), max(2, cells)), dtype=np.float32)
    layer = Image.fromarray(np.round(coarse * 255).astype(np.uint8)).resize((width, height), Image.Resampling.BILINEAR)
    return np.asarray(layer, dtype=np.float32) / 255.0


def fbm_noise(width: int, height: int, seed: int, octaves: int = 4) -> np.ndarray:
    total = np.zeros((height, width), dtype=np.float32)
    amplitude, weight = 1.0, 0.0
    for octave in range(max(1, octaves)):
        total += amplitude * value_noise(width, height, seed + octave * 104729, 4 * (2**octave))
        weight += amplitude
        amplitude *= 0.5
    return total / weight


def palette_lut(values: np.ndarray, low: tuple[int, int, int], high: tuple[int, int, int], alpha: int = 255) -> Image.Image:
    values = np.clip(values, 0.0, 1.0)[..., None]
    rgb = np.asarray(low, dtype=np.float32) + (np.asarray(high, dtype=np.float32) - np.asarray(low, dtype=np.float32)) * values
    rgba = np.concatenate((rgb, np.full((*values.shape[:2], 1), alpha, dtype=np.float32)), axis=-1)
    return Image.fromarray(np.round(rgba).astype(np.uint8))


def half_res_layer(width: int, height: int, draw: Callable[[int, int], Image.Image]) -> Image.Image:
    small = draw(max(1, width // 2), max(1, height // 2)).convert("RGBA")
    return small.resize((width, height), Image.Resampling.BICUBIC)
