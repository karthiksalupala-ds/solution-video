"""Registry for generic JSON-driven scenes."""

from .answer import AnswerScene
from .outro import OutroScene
from .question import QuestionScene
from .step import StepScene
from .tip import TipScene
from .title import TitleScene

SCENE_REGISTRY = {
    "title": TitleScene,
    "question": QuestionScene,
    "step": StepScene,
    "answer": AnswerScene,
    "tip": TipScene,
    "outro": OutroScene,
}

__all__ = ["SCENE_REGISTRY", "AnswerScene", "OutroScene", "QuestionScene", "StepScene", "TipScene", "TitleScene"]
