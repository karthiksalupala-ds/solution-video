from solution_video.scenes import SCENE_REGISTRY


def test_all_phase_two_scene_types_are_registered():
    assert set(SCENE_REGISTRY) == {"title", "question", "step", "answer", "tip", "outro"}
