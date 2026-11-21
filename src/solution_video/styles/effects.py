"""CPU-bounded visual style packs; post effects preserve the protected text mask."""

from __future__ import annotations

from functools import lru_cache
import math
import zlib

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from ..engine.canvas import Canvas
from ..engine.theme import Theme
from .base import StyleContext
from .helpers import fbm_noise, gaussian_blur, value_noise


def style_theme(theme: Theme, style: str) -> Theme:
    """Apply a style's contrast-checked palette without changing its layout."""
    from dataclasses import replace

    palette = theme.style_palettes.get(style, {})
    colors = palette.get("colors", {})
    return replace(theme, style=style, colors={**theme.colors, **colors})


def _style_palette(context: StyleContext) -> dict[str, object]:
    return context.theme.style_palettes.get(context.theme.style, {})


def _palette_color(context: StyleContext, key: str) -> tuple[int, int, int]:
    value = _style_palette(context)[key]
    return tuple(value)


def _style_motion(context: StyleContext, key: str) -> float:
    return float(_style_palette(context)["motion"][key])


def style_motion(theme: Theme, style: str, key: str) -> float:
    return float(theme.style_palettes[style]["motion"][key])


class _BaseStyle:
    tier = 1
    handles_background_fx = True
    requires_text_mask = False
    palette = ()
    sfx_profile = {"tick": 1.0, "ding": 1.0, "whoosh": 1.0}

    def begin_frame(self, context: StyleContext) -> None:
        del context

    def text_fx(self, canvas: Canvas, context: StyleContext, box: tuple[float, float, float, float]) -> None:
        del canvas, context, box

    def transition(self, outgoing: Image.Image, incoming: Image.Image, progress: float) -> Image.Image:
        return Image.blend(outgoing, incoming, max(0.0, min(1.0, progress)))

    def post(self, frame: Image.Image, context: StyleContext) -> Image.Image:
        del context
        return frame


class NeonGlowStyle(_BaseStyle):
    name = "neon_glow"
    tier = 3
    palette = ("cyan", "magenta", "yellow")
    sfx_profile = {"tick": 0.8, "ding": 1.0, "whoosh": 0.8}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])
        for index in range(1, 8):
            y = index * canvas.height / 8
            canvas.line(((0, y), (canvas.width, y)), (*_palette_color(context, "grid"), 35), width=1)

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        color = context.theme.colors["success"] if kind in {"answer", "result"} else context.theme.colors["accent"]
        fill_color = _palette_color(context, "result_surface" if kind in {"answer", "result"} else "surface")
        alpha = round((238 if kind in {"answer", "result"} else 232) * context.opacity)
        canvas.rounded_rect(box, radius, (*fill_color, alpha), (*color, round(245 * context.opacity)), 2)
        if kind in {"answer", "result"}:
            flicker = 0.96 + 0.04 * math.sin(context.time_s * _style_motion(context, "flicker_hz") + context.seed)
            _neon_outline(canvas, box, radius, color, flicker * context.opacity)


class GlassmorphismStyle(_BaseStyle):
    name = "glassmorphism"
    tier = 1
    palette = ("bg_top", "bg_bottom", "text", "accent", "success", "info")
    sfx_profile = {"tick": 0.9, "ding": 1.0, "whoosh": 0.85}
    _surface_count = 0

    def begin_frame(self, context: StyleContext) -> None:
        del context
        self._surface_count = 0

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])
        layer = Image.new("RGBA", canvas.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        phase = (context.time_s * _style_motion(context, "drift_rate") + context.seed * 0.013) % 1.0
        for index, name in enumerate(("accent", "info", "success")):
            x = canvas.image.width * (0.18 + 0.25 * index + 0.08 * math.sin(phase * math.tau + index))
            y = canvas.image.height * (0.20 + 0.22 * index + 0.08 * math.cos(phase * math.tau + index))
            radius = canvas.width * canvas.scale * (0.30 - index * 0.03)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*context.theme.colors[name], 62))
        canvas.composite(gaussian_blur(layer, 58 * canvas.scale))

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        if context.opacity <= 0:
            return
        self._surface_count += 1
        if self._surface_count > 6:
            _dark_surface(canvas, context, kind, box, radius)
            return
        left, top, right, bottom = (round(value * canvas.scale) for value in box)
        x0, y0 = max(0, left - 12), max(0, top - 12)
        x1, y1 = min(canvas.image.width, right + 12), min(canvas.image.height, bottom + 12)
        crop = canvas.image.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(12 * canvas.scale))
        shadow = Image.new("RGBA", crop.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        local_box = (left - x0, top - y0 + 5 * canvas.scale, right - x0, bottom - y0 + 5 * canvas.scale)
        shadow_draw.rounded_rectangle(local_box, radius=round(radius * canvas.scale), fill=(0, 0, 0, round(100 * context.opacity)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(8 * canvas.scale))
        canvas.image.alpha_composite(crop, (x0, y0))
        canvas.image.alpha_composite(shadow, (x0, y0))
        fill_alpha = round(
            _style_palette(context)["result_alpha" if kind in {"answer", "result"} else "surface_alpha"]
            * context.opacity
        )
        if fill_alpha <= 0:
            return
        fill = (*_palette_color(context, "result_surface" if kind in {"answer", "result"} else "surface"), fill_alpha)
        draw = ImageDraw.Draw(canvas.image)
        draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=round(radius * canvas.scale),
            fill=fill,
            outline=(232, 247, 255, round(175 * context.opacity)),
            width=max(1, canvas.scale),
        )


class GlitchStyle(_BaseStyle):
    name = "glitch"
    tier = 2
    requires_text_mask = True
    palette = ("cyan", "magenta", "lime")
    sfx_profile = {"tick": 0.85, "ding": 0.95, "whoosh": 0.9}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        _dark_surface(canvas, context, kind, box, radius)
        if kind in {"result", "answer"}:
            canvas.line(((box[0] + 8, box[3] - 5), (box[2] - 8, box[3] - 5)), (*context.theme.colors["accent"], 220), 3)

    def post(self, frame: Image.Image, context: StyleContext) -> Image.Image:
        if not context.cue_times:
            return frame
        fps = context.theme.canvas.fps
        frame_number = round(context.time_s * fps)
        seed_key = context.seed ^ zlib.crc32(context.scene_name.encode("utf-8"))
        for cue_time in context.cue_times:
            cue_frame = round(cue_time * fps)
            rng = np.random.default_rng(seed_key + cue_frame)
            minimum = round(_style_motion(context, "burst_min_frames"))
            maximum = round(_style_motion(context, "burst_max_frames"))
            burst_length = int(rng.integers(minimum, maximum + 1))
            if not cue_frame <= frame_number < cue_frame + burst_length:
                continue
            return _glitch_frame(frame, rng, context.theme.colors["accent"])
        return frame


class HalftoneDotsStyle(_BaseStyle):
    name = "halftone_dots"
    tier = 2
    palette = ("cyan", "magenta", "yellow")
    sfx_profile = {"tick": 0.9, "ding": 1.0, "whoosh": 0.8}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])
        overlay = _halftone_overlay(
            max(1, canvas.image.width // 2),
            max(1, canvas.image.height // 2),
            context.theme.colors["accent"],
            max(1, round(_style_palette(context)["dot_spacing"]) // 2),
            context.seed,
        ).resize(canvas.image.size, Image.Resampling.BILINEAR)
        canvas.composite(overlay)

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        fill_color = _palette_color(context, "result_surface" if kind in {"answer", "result"} else "surface")
        color = (*fill_color, round(242 * context.opacity))
        canvas.rounded_rect(box, radius, color, (*context.theme.colors["accent"], round(190 * context.opacity)), 2)
        left, top, right, bottom = (round(value * canvas.scale) for value in box)
        left //= 2
        top //= 2
        right //= 2
        bottom //= 2
        pattern = _halftone_overlay(
            right - left,
            bottom - top,
            context.theme.colors["accent"],
            max(1, round(_style_palette(context)["surface_dot_spacing"]) // 2),
            context.seed,
        ).resize((max(1, (right - left) * 2), max(1, (bottom - top) * 2)), Image.Resampling.BILINEAR)
        mask = Image.new("L", pattern.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, pattern.width - 1, pattern.height - 1),
            radius=round(radius * canvas.scale),
            fill=90,
        )
        pattern.putalpha(ImageChops.multiply(pattern.getchannel("A"), mask))
        canvas.image.alpha_composite(pattern, (left * 2, top * 2))


class DitheringStyle(_BaseStyle):
    name = "dithering"
    tier = 1
    palette = ("navy", "purple", "blue", "cyan", "cream")
    sfx_profile = {"tick": 0.9, "ding": 1.0, "whoosh": 0.9}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = canvas.image.size
        y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
        x = np.arange(width, dtype=np.int32)[None, :]
        bayer = np.asarray(
            ((0, 48, 12, 60, 3, 51, 15, 63),
             (32, 16, 44, 28, 35, 19, 47, 31),
             (8, 56, 4, 52, 11, 59, 7, 55),
             (40, 24, 36, 20, 43, 27, 39, 23),
             (2, 50, 14, 62, 1, 49, 13, 61),
             (34, 18, 46, 30, 33, 17, 45, 29),
             (10, 58, 6, 54, 9, 57, 5, 53),
             (42, 26, 38, 22, 41, 25, 37, 21)),
            dtype=np.float32,
        ) / 64.0
        threshold = bayer[np.arange(height)[:, None] % 8, x % 8]
        levels = np.clip(np.floor(y * 4 + threshold), 0, 4).astype(np.uint8)
        palette = np.asarray(_style_palette(context)["background_palette"], dtype=np.uint8)
        rgb = palette[levels]
        canvas.image = Image.fromarray(np.dstack((rgb, np.full((height, width), 255, dtype=np.uint8))))

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        _dark_surface(canvas, context, kind, box, radius)


class RisographPrintStyle(_BaseStyle):
    name = "risograph_print"
    tier = 2
    palette = ("fluorescent_pink", "blue", "yellow")
    sfx_profile = {"tick": 0.7, "ding": 0.9, "whoosh": 0.65}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = canvas.image.size
        rng = np.random.default_rng(context.seed)
        paper = np.asarray(context.theme.colors["bg_top"], dtype=np.int16)
        grain = rng.integers(-4, 5, (height, width, 1), dtype=np.int16)
        rgb = np.clip(paper + grain, 0, 255).astype(np.uint8)
        canvas.image = Image.fromarray(np.dstack((rgb, np.full((height, width), 255, dtype=np.uint8))))
        # Spot-color registration marks stay in the background layer, behind all content.
        layer = Image.new("RGBA", canvas.image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for index, color in enumerate(_style_palette(context)["inks"]):
            x = (0.16 + index * 0.34) * canvas.image.width
            y = (0.78 - index * 0.10) * canvas.image.height
            radius = 30 * canvas.scale
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*color, 35))
        canvas.composite(gaussian_blur(layer, 22 * canvas.scale))

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        frame_bucket = math.floor(context.time_s * _style_motion(context, "update_fps"))
        rng = np.random.default_rng(context.seed * 65537 + frame_bucket)
        jitter = int(rng.integers(-2, 3))
        pink = _palette_color(context, "pink")
        blue = _palette_color(context, "blue")
        shifted = (box[0] + jitter, box[1] - jitter, box[2] + jitter, box[3] - jitter)
        canvas.rounded_rect(shifted, radius, (*pink, round(155 * context.opacity)), None)
        canvas.rounded_rect((box[0] - 2, box[1] + 1, box[2] - 2, box[3] + 1), radius, (*blue, round(140 * context.opacity)), None)
        paper = (*context.theme.colors["bg_top"], round(248 * context.opacity))
        canvas.rounded_rect(box, radius, paper, (*context.theme.colors["text"], round(210 * context.opacity)), 2)


class PixelArtStyle(_BaseStyle):
    name = "pixel_art"
    tier = 1
    requires_text_mask = True
    palette = ("navy", "purple", "blue", "cyan", "yellow", "white")
    sfx_profile = {"tick": 0.8, "ding": 0.9, "whoosh": 0.7}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        color = _palette_color(context, "result_surface" if kind in {"answer", "result"} else "surface")
        alpha = round((250 if kind in {"answer", "result"} else 245) * context.opacity)
        canvas.rounded_rect(box, radius, (*color, alpha), (*context.theme.colors["accent"], round(240 * context.opacity)), 3)

    def post(self, frame: Image.Image, context: StyleContext) -> Image.Image:
        low = frame.resize((180, 320), Image.Resampling.NEAREST)
        palette = _pixel_palette(_style_palette(context)["pixel_palette"])
        pixelated = low.quantize(palette=palette, dither=Image.Dither.NONE).convert("RGB")
        pixelated = pixelated.resize(frame.size, Image.Resampling.NEAREST)
        return _restore_text(frame, pixelated, radius=5)


class AsciiArtStyle(_BaseStyle):
    name = "ascii_art"
    tier = 2
    palette = ("teal", "mint", "white")
    sfx_profile = {"tick": 0.8, "ding": 0.9, "whoosh": 0.7}

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        image = _ascii_background(
            canvas.image.width,
            canvas.image.height,
            context.seed,
            math.floor(context.time_s * _style_motion(context, "update_fps")),
            str(context.theme.fonts["pixel"]),
            context.theme.colors["bg_top"],
            _palette_color(context, "ascii_ink"),
            tuple(_style_palette(context)["atlas_cell"]),
            round(_style_palette(context)["atlas_font_px"]),
        )
        canvas.image = image.copy()

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        color = _palette_color(context, "result_surface" if kind in {"answer", "result"} else "surface")
        alpha = round((250 if kind in {"answer", "result"} else 242) * context.opacity)
        canvas.rounded_rect(box, radius, (*color, alpha), (*context.theme.colors["accent"], round(215 * context.opacity)), 2)

    def transition(self, outgoing: Image.Image, incoming: Image.Image, progress: float) -> Image.Image:
        width, height = outgoing.size
        noise = value_noise(width, height, zlib.crc32(b"ascii-transition"), cells=48)
        mask = Image.fromarray((noise < max(0.0, min(1.0, progress)) * 1.05).astype(np.uint8) * 255)
        return Image.composite(incoming, outgoing, mask)


class VaporwaveGridStyle(_BaseStyle):
    name = "vaporwave_grid"
    tier = 3
    palette = ("pink", "purple", "cyan")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 360, 640
        y, x = np.mgrid[0:height, 0:width].astype(np.float32)
        sky = np.clip(y / height, 0.0, 1.0)
        low = np.asarray(_palette_color(context, "sky_low"), dtype=np.float32)
        high = np.asarray(_palette_color(context, "sky_high"), dtype=np.float32)
        rgb = high * (1.0 - sky[..., None]) + low * sky[..., None]
        horizon = int(height * 0.50)
        floor_y = np.maximum(y - horizon, 0)
        floor_depth = np.clip(floor_y / max(1, height - horizon), 0.0, 1.0)
        floor = np.asarray(_palette_color(context, "floor"), dtype=np.float32)
        rgb = np.where(y[..., None] >= horizon, floor * (1.0 - 0.30 * floor_depth[..., None]) + rgb * 0.10, rgb)
        sun_y = int(height * 0.31)
        sun_x = int(width * 0.68)
        radius = int(width * 0.13)
        dy = y - sun_y
        dx = x - sun_x
        sun_mask = dx * dx + dy * dy <= radius * radius
        sun = _palette_color(context, "sun")
        stripe = ((dy.astype(np.int32) // 18) % 2 == 0)
        rgb = np.where((sun_mask & stripe)[..., None], sun, rgb)
        grid_phase = (context.time_s * _style_motion(context, "grid_speed") + context.seed * 0.01) % 1.0
        depth = np.clip((y - horizon) / max(1, height - horizon), 0.0, 1.0)
        horizontal_depth = np.mod(depth * 18.0 + grid_phase * 18.0, 1.0)
        horizontal = np.abs(horizontal_depth - 0.5) < (0.018 + 0.012 * depth)
        grid = np.asarray(_palette_color(context, "grid"), dtype=np.float32)
        rgb[horizon:, :, :] = np.where(horizontal[horizon:, :, None], grid, rgb[horizon:, :, :])
        center = width // 2
        world_x = np.mod((x - center) / max(1.0, width / 16.0) + 0.5, 1.0)
        vertical_x = center + ((x - center) * (0.20 + 0.80 * depth))
        vertical = np.abs(np.sin((vertical_x - center) / max(1.0, width / 18.0) * math.pi)) < 0.035
        vertical[:horizon, :] = False
        rgb = np.where(vertical[..., None], grid, rgb)
        scan = (np.arange(height)[:, None] % 4 == 0)
        rgb = np.where(scan[:, :, None], rgb * 0.76, rgb)
        image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
        canvas.image = image.resize(canvas.image.size, Image.Resampling.BILINEAR).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        surface = _palette_color(context, "card")
        accent = _palette_color(context, "outline")
        canvas.rounded_rect(box, radius, (*surface, round(230 * context.opacity)), (*accent, round(245 * context.opacity)), 3)


class TopographicLinesStyle(_BaseStyle):
    name = "topographic_lines"
    tier = 2
    requires_text_mask = True
    palette = ("earth", "sand", "forest")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 360, 640
        noise = fbm_noise(width, height, context.seed + round(context.time_s * 6), octaves=4)
        phase = context.time_s * _style_motion(context, "drift")
        y, x = np.mgrid[0:height, 0:width].astype(np.float32)
        field = noise + np.sin(x / 78.0 + phase) * 0.08 + np.cos(y / 96.0 - phase * 0.7) * 0.08
        scaled = field * _style_palette(context)["contour_frequency"]
        frac = np.abs(np.modf(scaled)[0] - 0.5)
        line = np.clip((0.16 - frac) / 0.055, 0.0, 1.0)
        base = np.asarray(_palette_color(context, "paper"), dtype=np.float32)
        ink = np.asarray(_palette_color(context, "contour"), dtype=np.float32)
        rgb = base[None, None, :] * (1.0 - line[:, :, None]) + ink[None, None, :] * line[:, :, None]
        rgb = rgb.repeat(2, axis=0).repeat(2, axis=1)
        canvas.image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        paper = (*_palette_color(context, "card"), round(238 * context.opacity))
        canvas.rounded_rect(box, radius, paper, (*_palette_color(context, "outline"), round(210 * context.opacity)), 2)

    def post(self, frame: Image.Image, context: StyleContext) -> Image.Image:
        return _flat_text_halo(frame, context.theme.colors["bg_top"], radius=19)


class FlowFieldsStyle(_BaseStyle):
    name = "flow_fields"
    tier = 2
    palette = ("cyan", "blue", "violet")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 360, 640
        rng = np.random.default_rng(context.seed ^ zlib.crc32(context.scene_name.encode()))
        count = int(_style_palette(context)["particle_count"])
        px = rng.random(count, dtype=np.float32) * (width - 1)
        py = rng.random(count, dtype=np.float32) * (height - 1)
        cy, cx = np.mgrid[0:height, 0:width].astype(np.float32)
        phase = context.time_s * _style_motion(context, "flow_speed")
        ax = np.sin(cy / 90.0 + phase) + np.cos((cx + cy) / 145.0 - phase * 0.6)
        ay = np.cos(cx / 105.0 - phase) - np.sin((cx - cy) / 170.0 + phase * 0.5)
        ix = np.clip(px.astype(np.int32), 0, width - 1)
        iy = np.clip(py.astype(np.int32), 0, height - 1)
        vx = ax[iy, ix] * 2.2
        vy = ay[iy, ix] * 2.2
        px = (px + vx) % width
        py = (py + vy) % height
        hist, _, _ = np.histogram2d(px, py, bins=(width, height), range=((0, width), (0, height)))
        field = np.clip(hist.T, 0, 4) / 4.0
        low = np.asarray(_palette_color(context, "low"), dtype=np.float32)
        high = np.asarray(_palette_color(context, "high"), dtype=np.float32)
        rgb = low[None, None, :] * (1.0 - field[:, :, None]) + high[None, None, :] * field[:, :, None]
        base = np.asarray(_palette_color(context, "base"), dtype=np.float32)
        rgb = np.clip(base * 0.55 + rgb * 0.75, 0, 255).astype(np.uint8)
        canvas.image = Image.fromarray(rgb.repeat(2, axis=0).repeat(2, axis=1)).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        canvas.rounded_rect(box, radius, (*_palette_color(context, "card"), round(220 * context.opacity)), (*context.theme.colors["accent"], round(180 * context.opacity)), 2)


class ParticleSwarmStyle(_BaseStyle):
    name = "particle_swarm"
    tier = 3
    palette = ("cyan", "white", "magenta")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 360, 640
        rng = np.random.default_rng(context.seed ^ zlib.crc32(context.scene_name.encode()))
        count = int(_style_palette(context)["particle_count"])
        px = rng.random(count, dtype=np.float32) * width
        py = rng.random(count, dtype=np.float32) * height
        morph = sum(1.0 for cue in context.cue_times if context.time_s >= cue)
        morph_phase = (math.sin(context.time_s * 1.8 + context.seed) + 1.0) * 0.5
        if context.cue_times:
            nearest = min(context.cue_times, key=lambda cue: abs(cue - context.time_s))
            morph_phase = float(np.clip((context.time_s - nearest + 0.8) / 1.6, 0.0, 1.0))
        mask = canvas.image.info.get("text_mask")
        if isinstance(mask, Image.Image):
            mask_small = np.asarray(mask.resize((width, height), Image.Resampling.BILINEAR), dtype=np.uint8)
            ys, xs = np.nonzero(mask_small > 96)
            if len(xs):
                target = rng.integers(0, len(xs), count)
                tx = xs[target].astype(np.float32)
                ty = ys[target].astype(np.float32)
                px = px * (1.0 - morph_phase) + tx * morph_phase
                py = py * (1.0 - morph_phase) + ty * morph_phase
        hist, _, _ = np.histogram2d(px, py, bins=(width, height), range=((0, width), (0, height)))
        density = np.clip(hist.T / 3.0, 0.0, 1.0)
        base = np.asarray(_palette_color(context, "base"), dtype=np.float32)
        high = np.asarray(_palette_color(context, "particle"), dtype=np.float32)
        rgb = base * (1.0 - density[..., None]) + high * density[..., None]
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
        canvas.image = Image.fromarray(rgb.repeat(2, axis=0).repeat(2, axis=1)).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        canvas.rounded_rect(box, radius, (*_palette_color(context, "card"), round(222 * context.opacity)), (*context.theme.colors["accent"], round(190 * context.opacity)), 2)


def _metaball_field(width: int, height: int, context: StyleContext) -> np.ndarray:
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    field = np.zeros((height, width), dtype=np.float32)
    for index in range(5):
        angle = context.time_s * (0.35 + index * 0.04) + index * 1.37
        cx = width * (0.5 + 0.34 * math.sin(angle + context.seed * 0.01))
        cy = height * (0.48 + 0.30 * math.cos(angle * 0.83 + index))
        radius = min(width, height) * (0.09 + 0.025 * math.sin(context.time_s * 1.7 + index))
        field += radius * radius / (1.0 + (x - cx) ** 2 + (y - cy) ** 2)
    return field


class MetaballsStyle(_BaseStyle):
    name = "metaballs"
    tier = 3
    palette = ("violet", "cyan", "pink")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 360, 640
        field = _metaball_field(width, height, context)
        threshold = float(_style_palette(context)["threshold"])
        mask = np.clip((field - threshold) * 1.8, 0.0, 1.0)
        base = np.asarray(_palette_color(context, "base"), dtype=np.float32)
        high = np.asarray(_palette_color(context, "blob"), dtype=np.float32)
        rgb = base * (1.0 - mask[:, :, None]) + high * mask[:, :, None]
        soft = np.clip(_metaball_field(width, height, context) * 0.18, 0.0, 0.45)
        rgb = np.clip(rgb + soft[:, :, None] * 255.0, 0, 255).astype(np.uint8)
        canvas.image = Image.fromarray(rgb.repeat(2, axis=0).repeat(2, axis=1)).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        canvas.rounded_rect(box, radius, (*_palette_color(context, "card"), round(232 * context.opacity)), (*_palette_color(context, "outline"), round(220 * context.opacity)), 2)


class LiquidMorphStyle(_BaseStyle):
    name = "liquid_morph"
    tier = 2
    palette = ("blue", "cyan", "violet")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 360, 640
        y, x = np.mgrid[0:height, 0:width].astype(np.float32)
        cx = width * 0.52 + 18 * math.sin(context.time_s * 0.45 + context.seed)
        cy = height * 0.48 + 12 * math.cos(context.time_s * 0.38)
        circle = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - min(width, height) * 0.23
        half_w, half_h = width * 0.25, height * 0.12
        rect = np.maximum(np.abs(x - cx) - half_w, np.abs(y - cy) - half_h)
        phase = context.time_s * _style_motion(context, "morph_rate")
        blend = (math.sin(phase + context.seed * 0.01) + 1.0) * 0.5
        h = circle * (1.0 - blend) + rect * blend
        k = 16.0
        distance = h - k * 0.08
        mask = np.clip((8.0 - distance) / 16.0, 0.0, 1.0)
        base = np.asarray(_palette_color(context, "base"), dtype=np.float32)
        liquid = np.asarray(_palette_color(context, "liquid"), dtype=np.float32)
        gloss = np.clip(1.0 - np.abs(y - cy - 45) / 180.0, 0.0, 1.0)
        rgb = base[None, None, :] * (1.0 - mask[:, :, None]) + liquid[None, None, :] * mask[:, :, None]
        rgb = rgb + gloss[:, :, None] * np.asarray(_palette_color(context, "gloss"), dtype=np.float32)[None, None, :] * 0.25
        canvas.image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8).repeat(2, 0).repeat(2, 1)).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        canvas.rounded_rect(box, radius, (*_palette_color(context, "card"), round(226 * context.opacity)), (*_palette_color(context, "outline"), round(220 * context.opacity)), 2)


class HolographicFoilStyle(_BaseStyle):
    name = "holographic_foil"
    tier = 2
    palette = ("iridescent", "silver", "violet")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 360, 640
        y, x = np.mgrid[0:height, 0:width].astype(np.float32)
        noise = fbm_noise(width, height, context.seed, octaves=3)
        hue = np.mod((x / width) * 0.72 + (y / height) * 0.35 + noise * 0.24 + context.time_s * 0.025, 1.0)
        chroma = np.stack((np.sin(hue * math.tau) * 0.5 + 0.5,
                           np.sin((hue + 1.0 / 3.0) * math.tau) * 0.5 + 0.5,
                           np.sin((hue + 2.0 / 3.0) * math.tau) * 0.5 + 0.5), axis=-1)
        base = np.asarray(_palette_color(context, "base"), dtype=np.float32)
        rgb = base * 0.58 + chroma * np.asarray(_palette_color(context, "foil"), dtype=np.float32) * 0.42
        band = np.clip(1.0 - np.abs((x / width - ((context.time_s * 0.08) % 1.2 - 0.1)) * 5.0), 0.0, 1.0)
        rgb = np.clip(rgb + band[:, :, None] * 45.0, 0, 255).astype(np.uint8)
        canvas.image = Image.fromarray(rgb.repeat(2, axis=0).repeat(2, axis=1)).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        canvas.rounded_rect(box, radius, (*_palette_color(context, "card"), round(238 * context.opacity)), (*_palette_color(context, "outline"), round(220 * context.opacity)), 2)


class KineticTypographyStyle(_BaseStyle):
    name = "kinetic_typography"
    tier = 1
    palette = ("accent", "success", "text")
    handles_background_fx = True

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(context.theme.colors["bg_top"], context.theme.colors["bg_bottom"])
        draw = ImageDraw.Draw(canvas.image)
        phase = context.time_s * _style_motion(context, "shape_speed") + context.seed * 0.01
        for index in range(5):
            x = (0.12 + index * 0.21 + 0.035 * math.sin(phase + index)) * canvas.image.width
            y = (0.15 + (index % 3) * 0.24) * canvas.image.height
            radius = (8 + index % 4 * 3) * canvas.scale
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*_palette_color(context, "shape"), 80))

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        fill = _palette_color(context, "result_surface" if kind in {"answer", "result"} else "surface")
        canvas.rounded_rect(box, radius, (*fill, round(246 * context.opacity)), (*_palette_color(context, "outline"), round(230 * context.opacity)), 2)


class BauhausShapesStyle(_BaseStyle):
    name = "bauhaus_shapes"
    tier = 1
    palette = ("red", "blue", "yellow", "black")
    handles_background_fx = True

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.image = Image.new("RGBA", canvas.image.size, (*_palette_color(context, "cream"), 255))
        draw = ImageDraw.Draw(canvas.image)
        phase = context.time_s * _style_motion(context, "shape_speed") + context.seed * 0.03
        w, h = canvas.image.size
        draw.rectangle((0, int(h * 0.72), w, h), fill=(*_palette_color(context, "blue"), 255))
        draw.ellipse((int(w * 0.62), int(h * 0.08), int(w * 0.98), int(h * 0.38)), fill=(*_palette_color(context, "red"), 255))
        draw.pieslice((int(w * 0.08), int(h * 0.58), int(w * 0.32), int(h * 0.82)), start=180, end=360, fill=(*_palette_color(context, "yellow"), 255))
        offset = round(24 * math.sin(phase))
        draw.polygon(((int(w * 0.82) + offset, int(h * 0.49)), (int(w * 0.93) + offset, int(h * 0.67)), (int(w * 0.72) + offset, int(h * 0.67))), fill=(*_palette_color(context, "black"), 230))
        draw.line((int(w * 0.05), int(h * 0.42), int(w * 0.42), int(h * 0.42)), fill=(*_palette_color(context, "black"), 255), width=5 * canvas.scale)

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        color = _palette_color(context, "result" if kind in {"answer", "result"} else "card")
        canvas.rounded_rect(box, radius, (*color, 255), (*_palette_color(context, "black"), 255), 4)


class PaperCutoutStyle(_BaseStyle):
    name = "paper_cutout"
    tier = 3
    palette = ("paper", "ink", "pink", "blue")
    handles_background_fx = True

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = canvas.image.size
        rng = np.random.default_rng(context.seed)
        grain = rng.normal(0.0, 2.2, (height, width, 1)).astype(np.float32)
        paper = np.asarray(_palette_color(context, "paper"), dtype=np.float32)
        pixels = np.clip(paper + grain, 0, 255).astype(np.uint8)
        canvas.image = Image.fromarray(np.dstack((pixels, np.full((height, width), 255, np.uint8))))
        draw = ImageDraw.Draw(canvas.image)
        phase = math.floor(context.time_s * _style_motion(context, "stop_motion_fps")) / _style_motion(context, "stop_motion_fps")
        drift = round(10 * math.sin(phase * 0.7 + context.seed))
        draw.polygon(((0, 0), (width * 0.48, 0), (width * 0.32 + drift, height * 0.28), (0, height * 0.36)), fill=(*_palette_color(context, "pink"), 70))
        draw.polygon(((width, height * 0.44), (width, height), (width * 0.72 - drift, height), (width * 0.84, height * 0.67)), fill=(*_palette_color(context, "blue"), 65))

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        left, top, right, bottom = (round(value * canvas.scale) for value in box)
        mask = Image.new("L", canvas.image.size, 0)
        draw = ImageDraw.Draw(mask)
        rng = np.random.default_rng(context.seed + round(top * 0.5))
        points = []
        for x in range(left, right + 1, max(8, 24 * canvas.scale)):
            points.append((x, top + int(rng.integers(-3, 4)) * canvas.scale))
        points.extend(((right, bottom), (left, bottom)))
        draw.polygon(points, fill=255)
        shadow = Image.new("RGBA", canvas.image.size, (0, 0, 0, 0))
        shadow.putalpha(mask.filter(ImageFilter.GaussianBlur(10 * canvas.scale)).point(lambda value: round(value * 0.24)))
        canvas.image.alpha_composite(shadow, (0, 7 * canvas.scale))
        color = _palette_color(context, "plate")
        plate = Image.new("RGBA", canvas.image.size, (*color, 255))
        plate.putalpha(mask)
        canvas.image.alpha_composite(plate)
        ImageDraw.Draw(canvas.image).line(points[:-1], fill=(*_palette_color(context, "ink"), 190), width=max(1, canvas.scale))


class Clay3DStyle(_BaseStyle):
    name = "clay_3d"
    tier = 2
    palette = ("pastel", "shadow", "highlight")

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        canvas.gradient(_palette_color(context, "bg_top"), _palette_color(context, "bg_bottom"))
        width, height = 360, 640
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        phase = context.time_s * _style_motion(context, "float_speed") + context.seed
        for index in range(4):
            x = width * (0.18 + index * 0.21) + 10 * math.sin(phase + index)
            y = height * (0.20 + (index % 2) * 0.48)
            radius = 30 + index * 4
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(*_palette_color(context, "orb"), 90))
        canvas.composite(layer.resize(canvas.image.size, Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(18 * canvas.scale)))

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        left, top, right, bottom = (round(value * canvas.scale) for value in box)
        width, height = max(1, right - left), max(1, bottom - top)
        if width < 8 or height < 8:
            return
        small_size = (max(1, width // 2), max(1, height // 2))
        mask = Image.new("L", small_size, 0)
        mask_box = (1, 1, max(1, small_size[0] - 2), max(1, small_size[1] - 2))
        clay_radius = min(
            max(1, round(radius * canvas.scale / 2)),
            max(1, (mask_box[2] - mask_box[0]) // 2),
            max(1, (mask_box[3] - mask_box[1]) // 2),
        )
        ImageDraw.Draw(mask).rounded_rectangle(mask_box, radius=clay_radius, fill=255)
        arr = np.asarray(mask, dtype=np.float32) / 255.0
        gy, gx = np.gradient(arr)
        normal_z = np.sqrt(np.maximum(0.01, 1.0 - gx * gx * 2 - gy * gy * 2))
        light = np.clip((-gx * 0.35 - gy * 0.45 + normal_z * 0.82), 0.15, 1.0)
        base = np.asarray(_palette_color(context, "result" if kind in {"answer", "result"} else "card"), dtype=np.float32)
        shaded = np.clip(base[None, None, :] * (0.62 + 0.48 * light[:, :, None]), 0, 255).astype(np.uint8)
        rgba = np.dstack((shaded, (arr * 255).astype(np.uint8)))
        slab = Image.fromarray(rgba).resize((width, height), Image.Resampling.BILINEAR)
        shadow = Image.new("RGBA", (width, height), (*_palette_color(context, "shadow"), 0))
        shadow.putalpha(mask.resize((width, height)).filter(ImageFilter.GaussianBlur(8 * canvas.scale)))
        canvas.image.alpha_composite(shadow, (left, top + 6 * canvas.scale))
        canvas.image.alpha_composite(slab, (left, top))


class RayMarchedFractalsStyle(_BaseStyle):
    name = "ray_marched_fractals"
    tier = 3
    palette = ("deep", "violet", "cyan")
    handles_background_fx = True

    def background(self, canvas: Canvas, context: StyleContext) -> None:
        width, height = 180, 320
        y, x = np.mgrid[-1.35:1.35:complex(height), -1.35:1.35:complex(width)].astype(np.float32)
        zoom = 1.0 + 0.06 * math.sin(context.time_s * _style_motion(context, "zoom_speed"))
        zx, zy = x * zoom, y * zoom
        cx = -0.72 + 0.035 * math.sin(context.time_s * 0.2 + context.seed)
        cy = 0.19
        iteration = np.zeros((height, width), dtype=np.float32)
        active = np.ones((height, width), dtype=bool)
        for index in range(32):
            xx = zx * zx - zy * zy + cx
            yy = 2.0 * zx * zy + cy
            escaped = (zx * zx + zy * zy) > 16.0
            newly = active & escaped
            iteration[newly] = index + 1
            zx = np.where(active, xx, zx)
            zy = np.where(active, yy, zy)
            active &= ~escaped
            if not active.any():
                break
        smooth = np.mod(iteration / 32.0 * 5.0 + context.time_s * 0.08, 1.0)
        palette = np.asarray(_style_palette(context)["gradient"], dtype=np.float32)
        indices = np.floor(smooth * (len(palette) - 1)).astype(np.int32)
        frac = (smooth * (len(palette) - 1) - indices)[..., None]
        next_indices = np.minimum(indices + 1, len(palette) - 1)
        rgb = palette[indices] * (1.0 - frac) + palette[next_indices] * frac
        rgb[active] = np.asarray(_palette_color(context, "deep"), dtype=np.float32)
        image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
        canvas.image = image.resize(canvas.image.size, Image.Resampling.LANCZOS).convert("RGBA")

    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
        fill = _palette_color(context, "card")
        canvas.rounded_rect(box, radius, (*fill, round(247 * context.opacity)), (*_palette_color(context, "outline"), round(210 * context.opacity)), 2)


def _dark_surface(canvas: Canvas, context: StyleContext, kind: str, box, radius: float) -> None:
    alpha = context.opacity
    fill_color = _palette_color(context, "result_surface" if kind in {"answer", "result"} else "surface")
    fill = (*fill_color, round(246 * alpha))
    outline = (*context.theme.colors["success" if kind in {"answer", "result"} else "accent"], round(230 * alpha))
    canvas.rounded_rect(box, radius, fill, outline, 2)


def _neon_outline(canvas: Canvas, box, radius: float, color: tuple[int, int, int], intensity: float) -> None:
    glow_size = (max(1, canvas.image.width // 4), max(1, canvas.image.height // 4))
    glow = Image.new("RGBA", glow_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    scaled_box = tuple(round(value * canvas.scale / 4) for value in box)
    draw.rounded_rectangle(scaled_box, radius=round(radius * canvas.scale / 4), outline=(*color, round(165 * intensity)), width=max(1, round(2 * canvas.scale / 4)))
    combined = Image.new("RGBA", glow.size, (0, 0, 0, 0))
    for radius_px in (2, 5):
        combined.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius_px)))
    glow = combined.resize(canvas.image.size, Image.Resampling.BILINEAR)
    canvas.image = _screen_blend(canvas.image, glow)


def _screen_blend(base: Image.Image, overlay: Image.Image) -> Image.Image:
    source = overlay.convert("RGBA")
    base_rgb = base.convert("RGB")
    screened = ImageChops.screen(base_rgb, source.convert("RGB"))
    result = Image.composite(screened, base_rgb, source.getchannel("A")).convert("RGBA")
    mask = base.info.get("text_mask")
    if isinstance(mask, Image.Image):
        result.info["text_mask"] = mask
    return result


def _halftone_overlay(width: int, height: int, color: tuple[int, int, int], spacing: int, seed: int) -> Image.Image:
    y, x = np.indices((height, width), dtype=np.float32)
    root2 = np.float32(math.sqrt(0.5))
    u = (x + y) * root2
    v = (x - y) * root2
    du = np.mod(u + seed % spacing, spacing) - spacing / 2
    dv = np.mod(v + (seed // max(1, spacing)) % spacing, spacing) - spacing / 2
    luminance = 0.42 + 0.35 * (y / max(1, height - 1))
    radius = 1.2 + luminance * (spacing * 0.22)
    dots = du * du + dv * dv <= radius * radius
    alpha = np.where(dots, 92, 0).astype(np.uint8)
    rgb = np.empty((height, width, 4), dtype=np.uint8)
    rgb[..., :3] = color
    rgb[..., 3] = alpha
    return Image.fromarray(rgb)


def _safe_text_mask(frame: Image.Image, radius: int) -> Image.Image | None:
    mask = frame.info.get("text_mask")
    if not isinstance(mask, Image.Image):
        return None
    mask = mask.convert("L")
    if radius >= 3:
        size = radius if radius % 2 else radius + 1
        padding = size // 2
        pixels = np.asarray(mask, dtype=np.uint8)
        horizontal = np.lib.stride_tricks.sliding_window_view(
            np.pad(pixels, ((0, 0), (padding, padding))), size, axis=1
        ).max(axis=-1)
        pixels = np.lib.stride_tricks.sliding_window_view(
            np.pad(horizontal, ((padding, padding), (0, 0))), size, axis=0
        ).max(axis=-1)
        mask = Image.fromarray(pixels)
    return mask


def _flat_text_halo(frame: Image.Image, color: tuple[int, int, int], radius: int) -> Image.Image:
    exact = frame.info.get("text_mask")
    if not isinstance(exact, Image.Image):
        return frame
    exact = exact.convert("L")
    dilated = _safe_text_mask(frame, radius)
    if dilated is None:
        dilated = exact
    halo = ImageChops.subtract(dilated, exact)
    if not halo.getbbox():
        return frame
    flat = Image.new("RGB", frame.size, color)
    result = Image.composite(flat, frame.convert("RGB"), halo)
    result.info["text_mask"] = exact
    return result


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for value in rgb:
        linear = value / 255.0
        channels.append(linear / 12.92 if linear <= 0.04045 else ((linear + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: tuple[int, int, int], background: tuple[int, int, int]) -> float:
    light = relative_luminance(foreground)
    dark = relative_luminance(background)
    return (max(light, dark) + 0.05) / (min(light, dark) + 0.05)


def _restore_text(original: Image.Image, effected: Image.Image, radius: int) -> Image.Image:
    mask = _safe_text_mask(original, radius)
    result = Image.composite(original.convert("RGB"), effected.convert("RGB"), mask) if mask else original.convert("RGB")
    if mask:
        result.info["text_mask"] = mask
    return result


def _glitch_frame(frame: Image.Image, rng: np.random.Generator, accent: tuple[int, int, int]) -> Image.Image:
    protected = _safe_text_mask(frame, 41)
    if protected is None:
        return frame
    original = np.asarray(frame.convert("RGB"), dtype=np.uint8)
    altered = original.copy()
    height, width = original.shape[:2]
    altered[..., 0] = np.roll(original[..., 0], 3, axis=1)
    altered[..., 2] = np.roll(original[..., 2], -3, axis=1)
    for y0 in range(0, height, max(12, height // 16)):
        y1 = min(height, y0 + max(12, height // 16))
        offset = int(rng.integers(-10, 11))
        altered[y0:y1] = np.roll(original[y0:y1], offset, axis=1)
    altered[::4] = (altered[::4].astype(np.uint16) * 232 // 255).astype(np.uint8)
    for _ in range(3):
        block_w = int(rng.integers(18, 70))
        block_h = int(rng.integers(3, 12))
        x0 = int(rng.integers(0, max(1, width - block_w)))
        y0 = int(rng.integers(0, max(1, height - block_h)))
        altered[y0:y0 + block_h, x0:x0 + block_w] = accent
    mask = np.asarray(protected, dtype=np.uint8)[..., None] > 0
    output = np.where(mask, original, altered)
    result = Image.fromarray(output.astype(np.uint8))
    result.info["text_mask"] = protected
    return result


@lru_cache(maxsize=4)
def _pixel_palette(colors: tuple[tuple[int, int, int], ...]) -> Image.Image:
    palette = Image.new("P", (1, 1))
    flat = [component for color in colors for component in color]
    palette.putpalette(flat + [0] * (768 - len(flat)))
    return palette


@lru_cache(maxsize=8)
def _glyph_atlas(font_path: str, cell_w: int, cell_h: int, font_size: int) -> tuple[np.ndarray, int, int]:
    chars = " .:-=+*#%@"
    font = ImageFont.truetype(font_path, font_size)
    atlas = np.zeros((len(chars), cell_h, cell_w), dtype=np.uint8)
    for index, char in enumerate(chars):
        glyph = Image.new("L", (cell_w, cell_h), 0)
        ImageDraw.Draw(glyph).text((0, -2), char, font=font, fill=255)
        atlas[index] = np.asarray(glyph)
    return atlas, cell_w, cell_h


@lru_cache(maxsize=24)
def _ascii_background(
    width: int,
    height: int,
    seed: int,
    frame_bucket: int,
    font_path: str,
    base_color: tuple[int, int, int],
    ink_color: tuple[int, int, int],
    cell: tuple[int, int],
    font_size: int,
) -> Image.Image:
    cell_w, cell_h = cell
    atlas, cell_w, cell_h = _glyph_atlas(font_path, cell_w, cell_h, font_size)
    columns = math.ceil(width / cell_w)
    rows = math.ceil(height / cell_h)
    field = fbm_noise(columns, rows, seed + frame_bucket * 997, octaves=3)
    indexes = np.clip((field * (len(atlas) - 1)).astype(np.intp), 0, len(atlas) - 1)
    tiles = atlas[indexes]
    gray = tiles.transpose(0, 2, 1, 3).reshape(rows * cell_h, columns * cell_w)[:height, :width]
    strength = np.minimum(gray.astype(np.uint16) * 3 // 4, 85).astype(np.uint8)
    base = np.asarray(base_color, dtype=np.uint16)
    ink = np.asarray(ink_color, dtype=np.uint16)
    rgb = ((base[None, None, :] * (255 - strength[..., None]) + ink[None, None, :] * strength[..., None]) // 255).astype(np.uint8)
    return Image.fromarray(np.dstack((rgb, np.full((height, width), 255, dtype=np.uint8))))
