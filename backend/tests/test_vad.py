import array

import pytest

from app.ai.vad import VoiceActivityDetector


def _tone_frame(vad: VoiceActivityDetector, amplitude: int) -> bytes:
    num_samples = vad.frame_bytes // 2
    samples = array.array("h", [amplitude] * num_samples)
    return samples.tobytes()


def test_silence_frame_is_not_speech() -> None:
    vad = VoiceActivityDetector(sample_rate=16000)
    assert vad.is_speech(_tone_frame(vad, 0)) is False


def test_loud_frame_is_speech() -> None:
    vad = VoiceActivityDetector(sample_rate=16000)
    assert vad.is_speech(_tone_frame(vad, 5000)) is True


def test_wrong_size_frame_is_not_speech() -> None:
    vad = VoiceActivityDetector(sample_rate=16000)
    assert vad.is_speech(b"\x00\x01") is False


def test_any_speech_detects_speech_anywhere_in_longer_audio() -> None:
    vad = VoiceActivityDetector(sample_rate=16000)
    silence = _tone_frame(vad, 0)
    speech = _tone_frame(vad, 5000)
    audio = silence + silence + speech + silence
    assert vad.any_speech(audio) is True


def test_any_speech_false_for_all_silence() -> None:
    vad = VoiceActivityDetector(sample_rate=16000)
    audio = _tone_frame(vad, 0) * 5
    assert vad.any_speech(audio) is False


def test_invalid_sample_rate_raises() -> None:
    with pytest.raises(ValueError):
        VoiceActivityDetector(sample_rate=12345)
