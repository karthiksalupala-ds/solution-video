"""Alpha-safe Pillow drawing on a supersampled RGBA surface."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw


Color = tuple[int, int, int] | tuple[int, int, int, int]


@lru_cache(maxsize=16)
def _gradient_image(
    width: int,
    height: int,
    top: tuple[int, int, int, int],
    bottom: tuple[int, int, int, int],
) -> Image.Image:
    ratios = np.linspace(0.0, 1.0, height, dtype=np.float64)[:, None]
    start = np.asarray(top, dtype=np.float64)
    delta = np.asarray(bottom, dtype=np.float64) - start
    rows = np.rint(start + ratios * delta).astype(np.uint8)
    pixels = np.broadcast_to(rows[:, None, :], (height, width, 4))
    return Image.fromarray(pixels.copy())


def _rgba(color: Color, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*color[:3], int(color[3] if len(color) == 4 else alpha))


class Canvas:
    """Logical-pixel drawing facade. Draws at scale and downsamples only at output."""

    def __init__(
        self,
        width: int,
        height: int,
        scale: int = 1,
        background: Color = (0, 0, 0),
        *,
        track_text_mask: bool = False,
    ) -> None:
        self.width, self.height, self.scale = width, height, scale
        self.image = Image.new("RGBA", (width * scale, height * scale), _rgba(background))
        self.draw = ImageDraw.Draw(self.image)
        self.text_mask = (
            Image.new("L", self.image.size, 0) if track_text_mask else None
        )

    def gradient(self, top: Color, bottom: Color) -> None:
        gradient = _gradient_image(self.image.width, self.image.height, _rgba(top), _rgba(bottom))
        self.image.paste(gradient)

    def composite(self, layer: Image.Image, x: float = 0, y: float = 0) -> None:
        self.image.alpha_composite(layer, (round(x * self.scale), round(y * self.scale)))

    def _overlay(
        self,
        bounds: tuple[int, int, int, int],
    ) -> tuple[Image.Image, ImageDraw.ImageDraw, tuple[int, int]] | None:
        left = max(0, bounds[0])
        top = max(0, bounds[1])
        right = min(self.image.width, bounds[2])
        bottom = min(self.image.height, bounds[3])
        if right <= left or bottom <= top:
            return None
        layer = Image.new("RGBA", (right - left, bottom - top), (0, 0, 0, 0))
        return layer, ImageDraw.Draw(layer), (left, top)

    def _composite_overlay(self, overlay) -> None:
        if overlay is None:
            return
        layer, _, origin = overlay
        self.image.alpha_composite(layer, origin)

    def rounded_rect(self, box: tuple[float, float, float, float], radius: float, fill: Color, outline: Color | None = None, width: float = 1) -> None:
        scaled = tuple(round(value * self.scale) for value in box)
        stroke = max(1, round(width * self.scale))
        padding = stroke + 1
        overlay = self._overlay(
            (scaled[0] - padding, scaled[1] - padding, scaled[2] + padding + 1, scaled[3] + padding + 1)
        )
        if overlay is None:
            return
        _, draw, origin = overlay
        local_box = (scaled[0] - origin[0], scaled[1] - origin[1], scaled[2] - origin[0], scaled[3] - origin[1])
        draw.rounded_rectangle(
            local_box, radius=round(radius * self.scale), fill=_rgba(fill),
            outline=_rgba(outline) if outline else None, width=stroke,
        )
        self._composite_overlay(overlay)

    def ellipse(self, box: tuple[float, float, float, float], fill: Color, outline: Color | None = None, width: float = 1) -> None:
        scaled = tuple(round(value * self.scale) for value in box)
        padding = max(1, round(width * self.scale)) + 1
        overlay = self._overlay(
            (scaled[0] - padding, scaled[1] - padding, scaled[2] + padding + 1, scaled[3] + padding + 1)
        )
        if overlay is None:
            return
        _, draw, origin = overlay
        local_box = (scaled[0] - origin[0], scaled[1] - origin[1], scaled[2] - origin[0], scaled[3] - origin[1])
        draw.ellipse(local_box, fill=_rgba(fill), outline=_rgba(outline) if outline else None, width=max(1, round(width * self.scale)))
        self._composite_overlay(overlay)

    def line(self, points: Iterable[tuple[float, float]], fill: Color, width: float = 1) -> None:
        scaled = [(round(x * self.scale), round(y * self.scale)) for x, y in points]
        if not scaled:
            return
        padding = max(1, round(width * self.scale)) + 1
        overlay = self._overlay((
            min(x for x, _ in scaled) - padding,
            min(y for _, y in scaled) - padding,
            max(x for x, _ in scaled) + padding + 1,
            max(y for _, y in scaled) + padding + 1,
        ))
        if overlay is None:
            return
        _, draw, origin = overlay
        local_points = [(x - origin[0], y - origin[1]) for x, y in scaled]
        draw.line(local_points, fill=_rgba(fill), width=max(1, round(width * self.scale)), joint="curve")
        self._composite_overlay(overlay)

    def polygon(self, points: Iterable[tuple[float, float]], fill: Color) -> None:
        scaled = [(round(x * self.scale), round(y * self.scale)) for x, y in points]
        if not scaled:
            return
        padding = 1
        overlay = self._overlay((
            min(x for x, _ in scaled) - padding,
            min(y for _, y in scaled) - padding,
            max(x for x, _ in scaled) + padding + 1,
            max(y for _, y in scaled) + padding + 1,
        ))
        if overlay is None:
            return
        _, draw, origin = overlay
        local_points = [(x - origin[0], y - origin[1]) for x, y in scaled]
        draw.polygon(local_points, fill=_rgba(fill))
        self._composite_overlay(overlay)

    def text(self, xy: tuple[float, float], text: str, font, fill: Color, *, anchor: str = "la", stroke_width: int = 0, stroke_fill: Color | None = None) -> None:
        """Alpha-composite text rather than replacing pixels on the base layer."""
        position = (round(xy[0] * self.scale), round(xy[1] * self.scale))
        bounds = ImageDraw.Draw(self.image).textbbox(
            position, text, font=font, anchor=anchor, stroke_width=stroke_width
        )
        padding = max(2, stroke_width + 1)
        overlay = self._overlay(tuple(
            round(value) for value in (
                bounds[0] - padding, bounds[1] - padding,
                bounds[2] + padding + 1, bounds[3] + padding + 1,
            )
        ))
        if overlay is not None:
            _, draw, origin = overlay
            draw.text(
                (position[0] - origin[0], position[1] - origin[1]),
                text, font=font, fill=_rgba(fill), anchor=anchor,
                stroke_width=stroke_width, stroke_fill=_rgba(stroke_fill) if stroke_fill else None,
            )
            self._composite_overlay(overlay)
        if self.text_mask is not None:
            mask_draw = ImageDraw.Draw(self.text_mask)
            mask_draw.text(
                position,
                text,
                font=font,
                fill=255,
                anchor=anchor,
                stroke_width=stroke_width,
                stroke_fill=255 if stroke_fill else None,
            )

    def final_rgb(self) -> Image.Image:
        """Flatten and return exactly the configured output resolution."""
        image = self.image
        if self.scale != 1:
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)
        result = image.convert("RGB")
        if self.text_mask is not None:
            mask = self.text_mask
            if mask.size != result.size:
                mask = mask.resize(result.size, Image.Resampling.LANCZOS)
            result.info["text_mask"] = mask
        return result
