"""Theme loading with repository-relative asset paths."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    source_root = Path(__file__).resolve().parents[3]
    candidates = (source_root, Path(__file__).resolve().parents[2], Path(sys.prefix))
    for root in candidates:
        if (root / "themes").is_dir() and (root / "fonts").is_dir():
            return root
    raise FileNotFoundError("Packaged themes and fonts are missing; reinstall solution-video with package data.")


def _immutable_theme_value(value: object) -> object:
    if isinstance(value, dict):
        return {key: _immutable_theme_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_immutable_theme_value(item) for item in value)
    return value


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
    style_palettes: dict[str, dict[str, object]]
    sizes: dict[str, int]
    motion: dict[str, float]
    branding: dict[str, object]
    voice: dict[str, object]
    style: str
    style_allowlist: tuple[str, ...]
    scene_styles: dict[str, str]


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
        fonts.setdefault("pixel", root / "fonts" / "PressStart2P-Regular.ttf")
        colors = {name: tuple(value) for name, value in data["colors"].items()}
        style_palettes = {
            style: {name: _immutable_theme_value(value) for name, value in palette.items()}
            for style, palette in data.get("style_palettes", {}).items()
        }
        canvas = data["canvas"]
        config = CanvasConfig(int(canvas["width"]), int(canvas["height"]), int(canvas["fps"]), int(canvas["supersample"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Theme {source} has an invalid required field: {exc}") from exc
    if config.width <= 0 or config.height <= 0 or config.fps <= 0 or config.supersample < 1:
        raise ValueError("Theme canvas dimensions, FPS, and supersample must be positive")
    missing = [str(font) for font in fonts.values() if not font.is_file()]
    if missing:
        raise ValueError(f"Theme font asset(s) missing: {', '.join(missing)}")
    style_allowlist = data.get("style_allowlist", ())
    scene_styles = data.get("scene_styles", {})
    if not isinstance(style_allowlist, (list, tuple)) or any(not isinstance(style, str) or not style.strip() for style in style_allowlist):
        raise ValueError(f"Theme {source} style_allowlist must be a list of non-empty style names")
    if not isinstance(scene_styles, dict) or any(
        not isinstance(scene, str) or not isinstance(style, str)
        or not scene.strip() or not style.strip()
        for scene, style in scene_styles.items()
    ):
        raise ValueError(f"Theme {source} scene_styles must map scene names to non-empty style names")
    return Theme(
        name=str(data.get("name", source.stem)), canvas=config,
        safe_margin_px=int(data["safe_margin_px"]), min_body_font_px=int(data["min_body_font_px"]),
        fonts=fonts, colors=colors, style_palettes=style_palettes,
        sizes={key: int(value) for key, value in data.get("sizes", {}).items()},
        motion={key: float(value) if isinstance(value, (int, float)) else value for key, value in data.get("motion", {}).items()},
        branding=dict(data.get("branding", {})),
        voice=dict(data.get("voice", {})),
        style=str(data.get("style", "classic")),
        style_allowlist=tuple(style.strip().lower() for style in style_allowlist),
        scene_styles={scene.strip().lower(): style.strip().lower() for scene, style in scene_styles.items()},
    )
