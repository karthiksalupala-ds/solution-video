"""Alpha-safe Pillow drawing on a supersampled RGBA surface."""

from __future__ import annotations

from typing import Iterable

from PIL import Image, ImageDraw


Color = tuple[int, int, int] | tuple[int, int, int, int]


def _rgba(color: Color, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*color[:3], int(color[3] if len(color) == 4 else alpha))


class Canvas:
    """Logical-pixel drawing facade. Draws at scale and downsamples only at output."""

    def __init__(self, width: int, height: int, scale: int = 1, background: Color = (0, 0, 0)) -> None:
        self.width, self.height, self.scale = width, height, scale
        self.image = Image.new("RGBA", (width * scale, height * scale), _rgba(background))
        self.draw = ImageDraw.Draw(self.image)

    def gradient(self, top: Color, bottom: Color) -> None:
        pixels = self.image.load()
        top_rgba, bottom_rgba = _rgba(top), _rgba(bottom)
        height = self.image.height
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(round(top_rgba[i] + (bottom_rgba[i] - top_rgba[i]) * ratio) for i in range(4))
            for x in range(self.image.width):
                pixels[x, y] = color

    def composite(self, layer: Image.Image, x: float = 0, y: float = 0) -> None:
        self.image.alpha_composite(layer, (round(x * self.scale), round(y * self.scale)))

    def _overlay(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        layer = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
        return layer, ImageDraw.Draw(layer)

    def rounded_rect(self, box: tuple[float, float, float, float], radius: float, fill: Color, outline: Color | None = None, width: float = 1) -> None:
        scaled = tuple(round(value * self.scale) for value in box)
        layer, draw = self._overlay()
        draw.rounded_rectangle(scaled, radius=round(radius * self.scale), fill=_rgba(fill), outline=_rgba(outline) if outline else None, width=max(1, round(width * self.scale)))
        self.image.alpha_composite(layer)

    def ellipse(self, box: tuple[float, float, float, float], fill: Color, outline: Color | None = None, width: float = 1) -> None:
        scaled = tuple(round(value * self.scale) for value in box)
        layer, draw = self._overlay()
        draw.ellipse(scaled, fill=_rgba(fill), outline=_rgba(outline) if outline else None, width=max(1, round(width * self.scale)))
        self.image.alpha_composite(layer)

    def line(self, points: Iterable[tuple[float, float]], fill: Color, width: float = 1) -> None:
        layer, draw = self._overlay()
        draw.line([(round(x * self.scale), round(y * self.scale)) for x, y in points], fill=_rgba(fill), width=max(1, round(width * self.scale)), joint="curve")
        self.image.alpha_composite(layer)

    def polygon(self, points: Iterable[tuple[float, float]], fill: Color) -> None:
        layer, draw = self._overlay()
        draw.polygon([(round(x * self.scale), round(y * self.scale)) for x, y in points], fill=_rgba(fill))
        self.image.alpha_composite(layer)

    def text(self, xy: tuple[float, float], text: str, font, fill: Color, *, anchor: str = "la", stroke_width: int = 0, stroke_fill: Color | None = None) -> None:
        """Alpha-composite text rather than replacing pixels on the base layer."""
        layer, draw = self._overlay()
        draw.text((round(xy[0] * self.scale), round(xy[1] * self.scale)), text, font=font, fill=_rgba(fill), anchor=anchor, stroke_width=stroke_width, stroke_fill=_rgba(stroke_fill) if stroke_fill else None)
        self.image.alpha_composite(layer)

    def final_rgb(self) -> Image.Image:
        """Flatten and return exactly the configured output resolution."""
        image = self.image
        if self.scale != 1:
            image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)
        return image.convert("RGB")
