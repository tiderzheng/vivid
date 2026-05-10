from __future__ import annotations

import sys
import types

from app.subsystems.transcription.device import resolve_runtime_device


def test_resolve_runtime_device_uses_ctranslate2_cuda_count(monkeypatch):
    fake_ctranslate2 = types.ModuleType("ctranslate2")
    fake_ctranslate2.get_cuda_device_count = lambda: 1
    monkeypatch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)

    assert resolve_runtime_device("auto") == "cuda"
    assert resolve_runtime_device("cuda") == "cuda"


def test_resolve_runtime_device_falls_back_to_cpu_without_ctranslate2_cuda(monkeypatch):
    fake_ctranslate2 = types.ModuleType("ctranslate2")
    fake_ctranslate2.get_cuda_device_count = lambda: 0
    monkeypatch.setitem(sys.modules, "ctranslate2", fake_ctranslate2)

    assert resolve_runtime_device("auto") == "cpu"
    assert resolve_runtime_device("cuda") == "cpu"
