"""Style registry and deterministic selection."""

from __future__ import annotations

import os
import warnings

from .base import StyleContext, StylePack
from .classic import ClassicStyle
from .effects import (
    AsciiArtStyle,
    BauhausShapesStyle,
    Clay3DStyle,
    DitheringStyle,
    GlassmorphismStyle,
    GlitchStyle,
    HalftoneDotsStyle,
    FlowFieldsStyle,
    HolographicFoilStyle,
    LiquidMorphStyle,
    MetaballsStyle,
    KineticTypographyStyle,
    NeonGlowStyle,
    ParticleSwarmStyle,
    PaperCutoutStyle,
    PixelArtStyle,
    RisographPrintStyle,
    RayMarchedFractalsStyle,
    TopographicLinesStyle,
    VaporwaveGridStyle,
    style_motion,
    style_theme,
)


_GLASS_STYLE = GlassmorphismStyle()
_REGISTRY: dict[str, StylePack] = {
    "classic": ClassicStyle(),
    "glassmorphism": _GLASS_STYLE,
    "neon_glow": NeonGlowStyle(),
    "glitch": GlitchStyle(),
    "halftone_dots": HalftoneDotsStyle(),
    "dithering": DitheringStyle(),
    "risograph_print": RisographPrintStyle(),
    "pixel_art": PixelArtStyle(),
    "ascii_art": AsciiArtStyle(),
    "vaporwave_grid": VaporwaveGridStyle(),
    "topographic_lines": TopographicLinesStyle(),
    "flow_fields": FlowFieldsStyle(),
    "particle_swarm": ParticleSwarmStyle(),
    "metaballs": MetaballsStyle(),
    "liquid_morph": LiquidMorphStyle(),
    "holographic_foil": HolographicFoilStyle(),
    "kinetic_typography": KineticTypographyStyle(),
    "bauhaus_shapes": BauhausShapesStyle(),
    "paper_cutout": PaperCutoutStyle(),
    "clay_3d": Clay3DStyle(),
    "ray_marched_fractals": RayMarchedFractalsStyle(),
}
_ALIASES = {"glass_lite": _GLASS_STYLE}
_AUTO_ORDER = (
    "classic",
    "glassmorphism",
    "neon_glow",
    "bauhaus_shapes",
    "kinetic_typography",
    "vaporwave_grid",
    "pixel_art",
    "risograph_print",
    "paper_cutout",
    "clay_3d",
    "dithering",
    "holographic_foil",
    "halftone_dots",
    "ascii_art",
    "topographic_lines",
    "glitch",
    "liquid_morph",
    "flow_fields",
    "particle_swarm",
    "metaballs",
    "ray_marched_fractals",
)


def registered_styles() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def resolve_style(
    requested: str | None,
    day: int = 1,
    allowed_styles: tuple[str, ...] | None = None,
) -> StylePack:
    candidate = (requested or os.getenv("SOLUTION_VIDEO_STYLE") or "classic").strip().lower()
    allowed = {name.strip().lower() for name in allowed_styles or () if name.strip()}
    if not allowed:
        allowed = set(_REGISTRY)
    if candidate == "auto":
        auto_styles = [
            name for name in _AUTO_ORDER
            if name in allowed
            and (_REGISTRY[name].tier < 3 or os.getenv("STYLE_ALLOW_HEAVY") == "1")
        ]
        if not auto_styles:
            warnings.warn("No configured styles are eligible for auto; falling back to 'classic'", RuntimeWarning, stacklevel=2)
            return _REGISTRY["classic"]
        candidate = auto_styles[(max(1, day) - 1) % len(auto_styles)]
    style = _REGISTRY.get(candidate) or _ALIASES.get(candidate)
    if style is None:
        warnings.warn(f"Unknown style {candidate!r}; falling back to 'classic'", RuntimeWarning, stacklevel=2)
        return _REGISTRY["classic"]
    if style.name not in allowed:
        warnings.warn(f"Style {style.name!r} is excluded by the theme allowlist; falling back to 'classic'", RuntimeWarning, stacklevel=2)
        return _REGISTRY["classic"]
    return style


__all__ = ("StyleContext", "StylePack", "registered_styles", "resolve_style", "style_motion", "style_theme")
