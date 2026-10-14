import json
from pathlib import Path

from solution_video.engine.theme import load_theme
from solution_video.scenes.hello import HelloScene, HelloSpec


ROOT = Path(__file__).resolve().parents[1]


def test_hello_scene_outputs_expected_frame_shape():
    payload = json.loads((ROOT / "examples" / "hello.json").read_text(encoding="utf-8"))
    theme = load_theme()
    frame = HelloScene(HelloSpec.from_mapping(payload), theme).render_frame(1.5)
    assert frame.mode == "RGB"
    assert frame.size == (720, 1280)
