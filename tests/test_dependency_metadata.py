from __future__ import annotations

from pathlib import Path
import tomllib


def test_runtime_dependencies_are_declared_in_supported_install_paths():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert any(line.strip().startswith("qrcode[pil]>=") for line in requirements)
    assert any(
        dependency.startswith("qrcode[pil]>=")
        for dependency in pyproject["project"]["dependencies"]
    )
    assert any(line.strip().startswith("faster-whisper>=") for line in requirements)
    assert any(
        dependency.startswith("faster-whisper>=")
        for dependency in pyproject["project"]["dependencies"]
    )
    assert any(line.strip().startswith("funasr>=") for line in requirements)
    assert any(
        dependency.startswith("funasr>=")
        for dependency in pyproject["project"]["dependencies"]
    )
    assert any(line.strip().startswith("modelscope>=") for line in requirements)
    assert any(
        dependency.startswith("modelscope>=")
        for dependency in pyproject["project"]["dependencies"]
    )
    assert any(line.strip().startswith("torch>=") for line in requirements)
    assert any(
        dependency.startswith("torch>=")
        for dependency in pyproject["project"]["dependencies"]
    )
    assert any(line.strip().startswith("torchaudio>=") for line in requirements)
    assert any(
        dependency.startswith("torchaudio>=")
        for dependency in pyproject["project"]["dependencies"]
    )
    assert all("openai-whisper" not in line for line in requirements)
    assert all(
        "openai-whisper" not in dependency
        for dependency in pyproject["project"]["dependencies"]
    )
