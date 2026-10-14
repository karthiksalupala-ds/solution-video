from pathlib import Path

import pytest

from solution_video.engine.text import fit_text


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "fonts" / "Poppins-Regular.ttf"


@pytest.mark.parametrize("text", ["short", "one two three four", "long " * 30])
def test_fit_never_returns_below_minimum_font(text):
    try:
        layout = fit_text(text, str(FONT), 560, 240, 50, 36, 4)
        assert layout.font_size >= 36 and len(layout.lines) <= 4
    except ValueError:
        assert len(text) > 100
