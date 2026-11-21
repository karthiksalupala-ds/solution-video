"""Style-pack contracts. Packs decorate semantic scene layouts; they do not own content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from ..engine.canvas import Canvas
from ..engine.theme import Theme


@dataclass(frozen=True)
class StyleContext:
    theme: Theme
    seed: int
    scene_index: int = 0
    scene_name: str = ""
    time_s: float = 0.0
    opacity: float = 1.0
    cue_times: tuple[float, ...] = ()


class StylePack(Protocol):
    """Pure visual treatment with no access to answers or narration text."""

    name: str
    tier: int
    palette: tuple[str, ...]
    sfx_profile: dict[str, float]

    def background(self, canvas: Canvas, context: StyleContext) -> None: ...
    def surface(self, canvas: Canvas, context: StyleContext, kind: str, box: tuple[float, float, float, float], radius: float) -> None: ...
    def text_fx(self, canvas: Canvas, context: StyleContext, box: tuple[float, float, float, float]) -> None: ...
    def transition(self, outgoing: Image.Image, incoming: Image.Image, progress: float) -> Image.Image: ...
    def post(self, frame: Image.Image, context: StyleContext) -> Image.Image: ...
