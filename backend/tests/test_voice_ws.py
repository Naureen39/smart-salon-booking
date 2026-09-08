import pytest

from app.api.v1.voice import UtteranceBuffer, _authenticate
from app.core.security import create_access_token, create_refresh_token
from app.db.models.user import User


def test_utterance_not_complete_while_speaking() -> None:
    buf = UtteranceBuffer(silence_threshold_ms=90)
    assert buf.add_frame(b"\x00" * 10, is_speech=True, frame_duration_ms=30) is False
    assert buf.add_frame(b"\x00" * 10, is_speech=True, frame_duration_ms=30) is False


def test_utterance_completes_after_enough_trailing_silence() -> None:
    buf = UtteranceBuffer(silence_threshold_ms=90)
    assert buf.add_frame(b"\x01" * 10, is_speech=True, frame_duration_ms=30) is False
    assert buf.add_frame(b"\x00" * 10, is_speech=False, frame_duration_ms=30) is False
    assert buf.add_frame(b"\x00" * 10, is_speech=False, frame_duration_ms=30) is False
    assert buf.add_frame(b"\x00" * 10, is_speech=False, frame_duration_ms=30) is True


def test_utterance_does_not_complete_without_any_speech() -> None:
    buf = UtteranceBuffer(silence_threshold_ms=30)
    assert buf.add_frame(b"\x00" * 10, is_speech=False, frame_duration_ms=30) is False
    assert buf.add_frame(b"\x00" * 10, is_speech=False, frame_duration_ms=30) is False


def test_pop_returns_buffered_audio_and_resets_state() -> None:
    buf = UtteranceBuffer(silence_threshold_ms=30)
    buf.add_frame(b"\x01\x02", is_speech=True, frame_duration_ms=30)
    buf.add_frame(b"\x03\x04", is_speech=False, frame_duration_ms=30)

    audio = buf.pop()

    assert audio == b"\x01\x02\x03\x04"
    assert buf.has_speech is False
    assert buf.silence_ms == 0
    assert buf.buffer == bytearray()


@pytest.mark.parametrize("bad_token", ["not-a-real-token", ""])
async def test_authenticate_rejects_invalid_token(bad_token: str) -> None:
    assert await _authenticate(bad_token) is None


async def test_authenticate_accepts_valid_access_token(client_user: User) -> None:
    token = create_access_token(client_user.id, client_user.role)
    result = await _authenticate(token)
    assert result is not None
    assert result.id == client_user.id


async def test_authenticate_rejects_refresh_token(client_user: User) -> None:
    refresh_token, _ = create_refresh_token(client_user.id, client_user.role)
    assert await _authenticate(refresh_token) is None
