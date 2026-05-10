from __future__ import annotations

from app.subsystems.transcription.engine import InternalTranscriptionEngine
from app.subsystems.transcription.models import TranscriptionRequestConfig


def test_internal_engine_routes_paraformer_model(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    calls = []

    engine = InternalTranscriptionEngine()
    monkeypatch.setattr(
        engine.paraformer,
        "transcribe",
        lambda path, device, language=None, task="transcribe": calls.append((path, device, language, task))
        or {"text": "中文转写", "segments": [], "language": "zh"},
    )
    monkeypatch.setattr(
        engine.whisper,
        "transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call faster-whisper")),
    )

    result = engine.transcribe(
        audio_path,
        tmp_path / "work",
        30,
        TranscriptionRequestConfig(
            model="paraformer-zh",
            language="zh",
            task="transcribe",
            extract_audio=False,
        ),
    )

    assert result.transcript == "中文转写"
    assert result.audio_path == audio_path
    assert calls == [(audio_path, result.runtime_device, "zh", "transcribe")]


def test_internal_engine_uses_torch_device_for_paraformer(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")

    engine = InternalTranscriptionEngine()
    monkeypatch.setattr(
        "app.subsystems.transcription.engine.resolve_torch_runtime_device",
        lambda preference: "cuda",
    )
    monkeypatch.setattr(
        "app.subsystems.transcription.engine.resolve_runtime_device",
        lambda preference: (_ for _ in ()).throw(AssertionError("should not use ctranslate2 device resolver")),
    )
    monkeypatch.setattr(
        engine.paraformer,
        "transcribe",
        lambda path, device, language=None, task="transcribe": {"text": device, "segments": [], "language": "zh"},
    )

    result = engine.transcribe(
        audio_path,
        tmp_path / "work",
        30,
        TranscriptionRequestConfig(
            model="paraformer-zh",
            language="zh",
            task="transcribe",
            extract_audio=False,
        ),
    )

    assert result.transcript == "cuda"
    assert result.runtime_device == "cuda"


def test_internal_engine_routes_whisper_model(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    calls = []

    engine = InternalTranscriptionEngine()
    monkeypatch.setattr(
        engine.whisper,
        "transcribe",
        lambda path, model, device, language, task: calls.append((path, model, device, language, task))
        or {"text": "whisper text", "segments": [], "language": "en"},
    )
    monkeypatch.setattr(
        engine.paraformer,
        "transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call paraformer")),
    )

    result = engine.transcribe(
        audio_path,
        tmp_path / "work",
        30,
        TranscriptionRequestConfig(
            model="large-v3-turbo",
            language="en",
            task="transcribe",
            extract_audio=False,
        ),
    )

    assert result.transcript == "whisper text"
    assert calls == [(audio_path, "large-v3-turbo", result.runtime_device, "en", "transcribe")]
