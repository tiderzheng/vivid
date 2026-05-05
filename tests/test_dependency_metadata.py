from __future__ import annotations

from pathlib import Path
import tomllib


def test_qrcode_runtime_dependency_is_declared_in_supported_install_paths():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert any(line.strip().startswith("qrcode[pil]>=") for line in requirements)
    assert any(
        dependency.startswith("qrcode[pil]>=")
        for dependency in pyproject["project"]["dependencies"]
    )
