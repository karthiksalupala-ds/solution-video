"""Theme loading with repository-relative asset paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CanvasConfig:
    width: int
    height: int
    fps: int
    supersample: int


@dataclass(frozen=True)
class Theme:
    name: str
    canvas: CanvasConfig
    safe_margin_px: int
    min_body_font_px: int
    fonts: dict[str, Path]
    colors: dict[str, tuple[int, int, int]]
    sizes: dict[str, int]
    motion: dict[str, float]
    branding: dict[str, object]


def load_theme(path: Path | None = None) -> Theme:
    """Load and validate a theme without consulting system font directories."""
    root = _repo_root()
    source = path or root / "themes" / "default.json"
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load theme {source}: {exc}") from exc
    try:
        fonts = {name: root / relative for name, relative in data["fonts"].items()}
        colors = {name: tuple(value) for name, value in data["colors"].items()}
        canvas = data["canvas"]
        config = CanvasConfig(int(canvas["width"]), int(canvas["height"]), int(canvas["fps"]), int(canvas["supersample"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Theme {source} has an invalid required field: {exc}") from exc
    if config.width <= 0 or config.height <= 0 or config.fps <= 0 or config.supersample < 1:
        raise ValueError("Theme canvas dimensions, FPS, and supersample must be positive")
    missing = [str(font) for font in fonts.values() if not font.is_file()]
    if missing:
        raise ValueError(f"Theme font asset(s) missing: {', '.join(missing)}")
    return Theme(
        name=str(data.get("name", source.stem)), canvas=config,
        safe_margin_px=int(data["safe_margin_px"]), min_body_font_px=int(data["min_body_font_px"]),
        fonts=fonts, colors=colors, sizes={key: int(value) for key, value in data.get("sizes", {}).items()},
        motion={key: float(value) if isinstance(value, (int, float)) else value for key, value in data.get("motion", {}).items()},
        branding=dict(data.get("branding", {})),
    )
