import pytest

from solution_video.llm.base import LLMError, extract_json


def test_fenced_json_is_accepted():
    assert extract_json("```json\n{\"answer\": \"42\"}\n```") == {"answer": "42"}


def test_non_json_is_rejected():
    with pytest.raises(LLMError):
        extract_json("not json")
