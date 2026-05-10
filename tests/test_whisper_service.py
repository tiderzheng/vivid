from __future__ import annotations

import sys
import types

from app.subsystems.transcription.whisper_service import WhisperService


def test_whisper_service_uses_faster_whisper_model(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    calls = []

    class FakeSegment:
        id = 0
        start = 0.0
        end = 1.0
        text = " 你好"

    class FakeInfo:
        language = "zh"

    class FakeWhisperModel:
        def __init__(self, model_name, **kwargs):
            calls.append((model_name, kwargs))

        def transcribe(self, audio, **kwargs):
            assert audio == str(audio_path)
            assert kwargs == {"language": "zh", "task": "transcribe"}
            return [FakeSegment()], FakeInfo()

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    service = WhisperService(whisper_root=tmp_path / "models")
    result = service.transcribe(
        audio_path,
        model_name="large-v3-turbo",
        device="cpu",
        language="zh",
        task="transcribe",
    )

    assert calls == [
        (
            "large-v3-turbo",
            {
                "device": "cpu",
                "compute_type": "int8",
                "download_root": str(tmp_path / "models"),
            },
        )
    ]
    assert result["text"] == "你好"
    assert result["language"] == "zh"
    assert result["segments"] == [{"id": 0, "start": 0.0, "end": 1.0, "text": " 你好"}]


def test_whisper_service_uses_float16_on_cuda(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    calls = []

    class FakeWhisperModel:
        def __init__(self, model_name, **kwargs):
            calls.append((model_name, kwargs))

        def transcribe(self, *_args, **_kwargs):
            return [], type("Info", (), {"language": "zh"})()

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    service = WhisperService()
    service.transcribe(audio_path, "large-v3-turbo", "cuda", None, "transcribe")

    assert calls == [
        (
            "large-v3-turbo",
            {
                "device": "cuda",
                "compute_type": "float16",
            },
        )
    ]
