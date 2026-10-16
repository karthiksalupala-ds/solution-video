from solution_video.voice.normalization import normalize_speech


def test_english_speech_expands_math_symbols_units_and_numbers():
    assert normalize_speech("20 x 18/5 = 72 km/h") == (
        "twenty times eighteen divided by five equals seventy two kilometres per hour"
    )


def test_english_speech_spells_decimal_digits_without_rounding():
    assert normalize_speech("1.25 m") == "one point two five metres"


def test_english_speech_reads_negative_values_as_minus():
    assert normalize_speech("-12 km") == "minus twelve kilometres"
