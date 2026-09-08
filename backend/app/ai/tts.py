"""Text-to-speech (docs plan §9.5).

OpenVoice V2 is the plan's named engine — zero-shot voice cloning from a
short reference clip of the salon's chosen brand voice — but it ships as a
research repo with a manually-downloaded checkpoint and no clean pip wheel,
so it can't be a default dependency here. OpenVoiceEngine below is a real
integration point (it checks for the actual checkpoint, reference clip, and
`openvoice` package, and fails fast with setup instructions if any are
missing) rather than a fake stub — it activates for real once those are
provisioned in a deployment.

PyttsxEngine is the default: a fully working, zero-cost, offline fallback
(SAPI5 on Windows / espeak on Linux via pyttsx3) so the voice pipeline is
genuinely runnable and testable today without OpenVoice's checkpoint.
"""

import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

import pyttsx3

from app.core.config import get_settings

settings = get_settings()


class TTSEngine(Protocol):
    def synthesize(self, text: str) -> bytes: ...


@contextmanager
def _temp_wav_path() -> Generator[Path, None, None]:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        path = Path(handle.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


class PyttsxEngine:
    """Offline TTS via the OS's native speech engine — no model download,
    works out of the box."""

    def synthesize(self, text: str) -> bytes:
        engine = pyttsx3.init()
        with _temp_wav_path() as path:
            engine.save_to_file(text, str(path))
            engine.runAndWait()
            return path.read_bytes()


class OpenVoiceEngine:
    """Zero-shot voice cloning from settings.tts_reference_voice_path (docs
    plan §9.5). Requires the OpenVoice V2 checkpoint directory, a reference
    clip, and the `openvoice` package — see README for one-time setup.
    """

    def __init__(self) -> None:
        self._checkpoint_dir = Path(settings.tts_checkpoint_dir)
        self._reference_voice_path = Path(settings.tts_reference_voice_path)

    def synthesize(self, text: str) -> bytes:
        if not self._checkpoint_dir.exists():
            raise RuntimeError(
                f"OpenVoice V2 checkpoint not found at {self._checkpoint_dir}. Download it from "
                "https://huggingface.co/myshell-ai/OpenVoiceV2, set TTS_CHECKPOINT_DIR, or use "
                "TTS_ENGINE=pyttsx3 for the zero-setup offline fallback."
            )
        if not self._reference_voice_path.exists():
            raise RuntimeError(
                f"No brand-voice reference clip found at {self._reference_voice_path}. Record a "
                "10-15s sample (docs plan §9.5) and set TTS_REFERENCE_VOICE_PATH."
            )
        try:
            from openvoice.api import ToneColorConverter  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "The `openvoice` package isn't installed (no prebuilt PyPI wheel — install from "
                "https://github.com/myshell-ai/OpenVoice with `pip install -e .`), then retry."
            ) from exc

        raise NotImplementedError(
            "OpenVoice V2 checkpoint, reference clip, and package are all present, but the actual "
            "inference call isn't wired up in this environment — implement it here against your "
            "provisioned checkpoint."
        )


def get_tts_engine() -> TTSEngine:
    if settings.tts_engine == "openvoice_v2":
        return OpenVoiceEngine()
    return PyttsxEngine()
