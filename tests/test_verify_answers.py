from solution_video.verify.answers import answers_match, normalise_answer


def test_answer_normalization_handles_units_and_percentages():
    assert answers_match("72 km/h", "72")
    assert answers_match("25%", "25 percent")
    assert normalise_answer("1/ 2") == "1/2"
