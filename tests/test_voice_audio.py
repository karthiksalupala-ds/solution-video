import wave

import numpy as np
import pytest

from solution_video.engine.audio import mix_voice_tracks, write_wav


def test_narration_is_mixed_and_sfx_are_ducked_while_speaking(tmp_path):
    sample_rate = 100
    effects = tmp_path / "effects.wav"
    speech = tmp_path / "speech.wav"
    output = tmp_path / "mixed.wav"
    write_wav(effects, np.full(sample_rate, 0.4), sample_rate)
    write_wav(speech, np.full(50, 0.3), sample_rate)

    mix_voice_tracks(effects, ((speech, 0.25),), output, 1.0, sample_rate)

    with wave.open(str(output), "rb") as mixed:
        samples = np.frombuffer(mixed.readframes(mixed.getnframes()), dtype=np.int16) / 32768
    assert len(samples) == sample_rate
    assert np.mean(np.abs(samples[:20])) == pytest.approx(0.4, abs=0.01)
    assert np.mean(np.abs(samples[30:70])) == pytest.approx(0.4, abs=0.02)
