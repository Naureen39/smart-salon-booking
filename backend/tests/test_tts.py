from pathlib import Path

import pytest

import app.ai.tts as tts_module
from app.ai.tts import OpenVoiceEngine, PyttsxEngine


def test_pyttsx_engine_produces_nonempty_wav_bytes() -> None:
    engine = PyttsxEngine()
    audio = engine.synthesize("hello")
    assert isinstance(audio, bytes)
    assert len(audio) > 0
    assert audio[:4] == b"RIFF"


def test_get_tts_engine_defaults_to_pyttsx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts_module.settings, "tts_engine", "pyttsx3")
    assert isinstance(tts_module.get_tts_engine(), PyttsxEngine)


def test_get_tts_engine_returns_openvoice_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tts_module.settings, "tts_engine", "openvoice_v2")
    assert isinstance(tts_module.get_tts_engine(), OpenVoiceEngine)


def test_openvoice_engine_fails_fast_when_checkpoint_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tts_module.settings, "tts_checkpoint_dir", str(tmp_path / "does_not_exist"))
    engine = OpenVoiceEngine()
    with pytest.raises(RuntimeError, match="checkpoint"):
        engine.synthesize("hello")


def test_openvoice_engine_fails_fast_when_reference_clip_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkpoint_dir = tmp_path / "checkpoint"
    checkpoint_dir.mkdir()
    monkeypatch.setattr(tts_module.settings, "tts_checkpoint_dir", str(checkpoint_dir))
    monkeypatch.setattr(tts_module.settings, "tts_reference_voice_path", str(tmp_path / "missing.wav"))

    engine = OpenVoiceEngine()
    with pytest.raises(RuntimeError, match="reference clip"):
        engine.synthesize("hello")
