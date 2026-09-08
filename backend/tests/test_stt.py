import pytest

import app.ai.stt as stt_module
from app.ai.stt import pcm16_to_wav_bytes, transcribe_wav_bytes


def test_pcm16_to_wav_bytes_produces_valid_wav_header() -> None:
    pcm = b"\x00\x01" * 100
    wav_bytes = pcm16_to_wav_bytes(pcm, sample_rate=16000)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"


def test_transcribe_wav_bytes_joins_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    # The real faster-whisper model is a large download and slow to run in a
    # test suite — this exercises the actual joining/formatting logic against
    # a fake model instead, while `_get_model()` itself still loads the real
    # one for actual dev/prod use.
    class FakeSegment:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeModel:
        def transcribe(self, buffer: object, language: str) -> tuple[list[FakeSegment], None]:
            return [FakeSegment(" hello "), FakeSegment("world ")], None

    monkeypatch.setattr(stt_module, "_get_model", lambda: FakeModel())

    result = transcribe_wav_bytes(b"fake wav bytes")
    assert result == "hello world"


def test_transcribe_wav_bytes_returns_empty_string_for_no_segments(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModel:
        def transcribe(self, buffer: object, language: str) -> tuple[list, None]:
            return [], None

    monkeypatch.setattr(stt_module, "_get_model", lambda: FakeModel())

    assert transcribe_wav_bytes(b"fake wav bytes") == ""
