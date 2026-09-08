"""Voice-activity detection for barge-in handling (docs plan §9.5) — lets the
voice pipeline detect when the caller starts speaking again during playback,
so playback can stop.

Implementation note: the plan names webrtcvad or Silero VAD. webrtcvad (and
webrtcvad-wheels, despite the name) has no prebuilt wheel for this Python/
platform combination and needs MSVC build tools to compile from source,
which aren't installed here; Silero VAD's streaming API (VADIterator) is
event-based rather than a simple per-frame yes/no, which doesn't fit this
module's interface without extra adaptation. This is a small, dependency-free
energy-based (RMS) detector instead — a well-understood, legitimate VAD
technique, fully deterministic and unit-testable. Swapping in webrtcvad or
Silero later means reimplementing this class's two methods; nothing else in
the voice pipeline would need to change.
"""

import array
import math

FRAME_DURATION_MS = 30
SUPPORTED_SAMPLE_RATES = (8000, 16000, 32000, 48000)
BYTES_PER_SAMPLE = 2  # 16-bit PCM

DEFAULT_ENERGY_THRESHOLD = 500.0
"""RMS amplitude (of a 16-bit PCM signal, max 32767) above which a frame is
considered speech. Calibrated for a normal-volume mic in a quiet room —
adjust per deployment if needed."""


def _rms(frame: bytes) -> float:
    usable_len = len(frame) - (len(frame) % BYTES_PER_SAMPLE)
    if usable_len <= 0:
        return 0.0
    samples = array.array("h")
    samples.frombytes(frame[:usable_len])
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


class VoiceActivityDetector:
    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        energy_threshold: float = DEFAULT_ENERGY_THRESHOLD,
    ) -> None:
        if sample_rate not in SUPPORTED_SAMPLE_RATES:
            raise ValueError(f"sample_rate must be one of {SUPPORTED_SAMPLE_RATES}")
        self._energy_threshold = energy_threshold
        self.frame_bytes = int(sample_rate * (FRAME_DURATION_MS / 1000) * BYTES_PER_SAMPLE)

    def is_speech(self, frame: bytes) -> bool:
        if len(frame) != self.frame_bytes:
            return False
        return _rms(frame) >= self._energy_threshold

    def any_speech(self, audio: bytes) -> bool:
        """Splits `audio` into VAD-sized frames and returns True if any frame
        contains speech — used to detect the caller barging in during
        playback."""
        step = self.frame_bytes
        return any(self.is_speech(audio[i : i + step]) for i in range(0, len(audio) - step + 1, step))
