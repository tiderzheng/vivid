from __future__ import annotations

import sys
import types

from app.subsystems.transcription.paraformer_service import ParaformerService


def test_paraformer_service_uses_funasr_automodel(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    monkeypatch.setenv("MODELSCOPE_CACHE", str(tmp_path / "empty-modelscope-cache"))
    calls = []

    class FakeAutoModel:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            return [{"key": "audio", "text": "你好，世界"}]

    fake_module = types.ModuleType("funasr")
    fake_module.AutoModel = FakeAutoModel
    monkeypatch.setitem(sys.modules, "funasr", fake_module)

    service = ParaformerService(model_root=tmp_path / "models")
    result = service.transcribe(audio_path, device="cuda", language="zh", task="transcribe")

    assert calls == [
        (
            "init",
                {
                    "model": "paraformer-zh",
                    "device": "cuda:0",
                    "disable_update": True,
                },
        ),
        (
            "generate",
            {
                "input": str(audio_path),
                "batch_size_s": 300,
                "language": "zh",
            },
        ),
    ]
    assert result["text"] == "你好，世界"
    assert result["language"] == "zh"


def test_paraformer_service_prefers_cached_model_paths(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    cache_root = tmp_path / "modelscope"
    model_dir = (
        cache_root
        / "models"
        / "iic"
        / "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )
    vad_dir = cache_root / "models" / "iic" / "speech_fsmn_vad_zh-cn-16k-common-pytorch"
    punc_dir = cache_root / "models" / "iic" / "punc_ct-transformer_cn-en-common-vocab471067-large"
    for path in (model_dir, vad_dir, punc_dir):
        path.mkdir(parents=True)
        (path / "configuration.json").write_text("{}", encoding="utf-8")
    calls = []

    class FakeAutoModel:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs))

        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            return [{"key": "audio", "text": "缓存路径"}]

    fake_module = types.ModuleType("funasr")
    fake_module.AutoModel = FakeAutoModel
    monkeypatch.setitem(sys.modules, "funasr", fake_module)

    service = ParaformerService(model_root=cache_root)
    result = service.transcribe(audio_path, device="cuda", language="zh", task="transcribe")

    assert calls[0] == (
        "init",
        {
            "model": str(model_dir),
            "vad_model": str(vad_dir),
            "punc_model": str(punc_dir),
            "device": "cuda:0",
            "disable_update": True,
        },
    )
    assert result["text"] == "缓存路径"


def test_paraformer_service_rejects_translate_task(tmp_path, monkeypatch):
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"wav")
    service = ParaformerService()

    try:
        service.transcribe(audio_path, device="cpu", task="translate")
    except ValueError as exc:
        assert "only supports transcribe" in str(exc)
    else:
        raise AssertionError("paraformer should reject translate task")
