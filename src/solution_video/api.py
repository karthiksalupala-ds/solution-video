"""Public Phase-1 rendering API."""

from pathlib import Path

from .pipeline import render_from_file
from .schema import Meta


def render(input_path: str | Path, output_path: str | Path, *, theme_path: str | Path | None = None, no_voice: bool = False) -> Meta:
    """Render a validated content-driven solution JSON."""
    del no_voice
    return render_from_file(Path(input_path), Path(output_path), theme_path=theme_path)
