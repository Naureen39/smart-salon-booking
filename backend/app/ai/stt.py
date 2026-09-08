"""Speech-to-text via faster-whisper (docs plan §9.5) — a CTranslate2 port of
Whisper, int8-quantized for fast CPU inference at no per-call cost.
"""

import io
import wave
from functools import lru_cache

from faster_whisper import WhisperModel

from app.core.config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    return WhisperModel(settings.whisper_model_size, compute_type=settings.whisper_compute_type, device="cpu")


def transcribe_wav_bytes(audio: bytes) -> str:
    """Transcribes a complete WAV file's bytes (mono 16-bit PCM) to text."""
    model = _get_model()
    with io.BytesIO(audio) as buffer:
        segments, _ = model.transcribe(buffer, language="en")
        return " ".join(segment.text.strip() for segment in segments).strip()


def pcm16_to_wav_bytes(pcm_audio: bytes, *, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wraps raw 16-bit PCM samples (as streamed over the voice WebSocket) in
    a minimal WAV header so faster-whisper can read them."""
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_audio)
        return buffer.getvalue()
