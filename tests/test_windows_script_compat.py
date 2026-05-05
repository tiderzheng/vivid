from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _fake_python_script(path: Path, output_path: Path) -> None:
    path.write_text(
        "@echo off\n"
        f'echo %* > "{output_path}"\n'
        "exit /b 0\n",
        encoding="utf-8",
    )


def _fake_ensure_venv_script(path: Path, fake_python: Path) -> None:
    path.write_text(
        "param([string]$RepoRoot)\n"
        f'Write-Output "{fake_python}"\n',
        encoding="utf-8",
    )


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_tool_ps1_forwards_legacy_sessdata_flags(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("scripts/vivid_tool.ps1"), scripts_dir / "vivid_tool.ps1")
    capture_file = tmp_path / "vivid_tool_args.txt"
    fake_python = scripts_dir / "fake_python.cmd"
    _fake_python_script(fake_python, capture_file)
    _fake_ensure_venv_script(scripts_dir / "ensure_venv.ps1", fake_python)

    powershell = _powershell_executable()
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts_dir / "vivid_tool.ps1"),
            "-Action",
            "quickread",
            "-Source",
            "https://example.com/demo",
            "-Sessdata",
            "expired",
            "-NoSessdata",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    recorded = capture_file.read_text(encoding="utf-8")
    assert "--sessdata" in recorded
    assert "expired" in recorded
    assert "--no-sessdata" in recorded
    assert "-m app.control_cli quickread" in recorded


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_run_quickread_ps1_forwards_legacy_sessdata_flags(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("scripts/run_quickread.ps1"), scripts_dir / "run_quickread.ps1")
    capture_file = tmp_path / "run_quickread_args.txt"
    fake_python = scripts_dir / "fake_python.cmd"
    _fake_python_script(fake_python, capture_file)
    _fake_ensure_venv_script(scripts_dir / "ensure_venv.ps1", fake_python)

    powershell = _powershell_executable()
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts_dir / "run_quickread.ps1"),
            "-Source",
            "https://example.com/demo",
            "-Sessdata",
            "expired",
            "-NoSessdata",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    recorded = capture_file.read_text(encoding="utf-8")
    assert "--sessdata" in recorded
    assert "expired" in recorded
    assert "--no-sessdata" in recorded
    assert "-m app.cli https://example.com/demo --format both" in recorded


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_tool_ps1_forwards_bili_cookie_flag(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("scripts/vivid_tool.ps1"), scripts_dir / "vivid_tool.ps1")
    capture_file = tmp_path / "vivid_tool_cookie_args.txt"
    fake_python = scripts_dir / "fake_python.cmd"
    _fake_python_script(fake_python, capture_file)
    _fake_ensure_venv_script(scripts_dir / "ensure_venv.ps1", fake_python)

    powershell = _powershell_executable()
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts_dir / "vivid_tool.ps1"),
            "-Action",
            "quickread",
            "-Source",
            "https://example.com/demo",
            "-BiliCookie",
            "SESSDATA=demo; bili_jct=token",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    recorded = capture_file.read_text(encoding="utf-8")
    assert "--bili-cookie" in recorded
    assert "SESSDATA=demo; bili_jct=token" in recorded


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_run_quickread_ps1_forwards_bili_cookie_flag(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("scripts/run_quickread.ps1"), scripts_dir / "run_quickread.ps1")
    capture_file = tmp_path / "run_quickread_cookie_args.txt"
    fake_python = scripts_dir / "fake_python.cmd"
    _fake_python_script(fake_python, capture_file)
    _fake_ensure_venv_script(scripts_dir / "ensure_venv.ps1", fake_python)

    powershell = _powershell_executable()
    assert powershell is not None

    result = subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scripts_dir / "run_quickread.ps1"),
            "-Source",
            "https://example.com/demo",
            "-BiliCookie",
            "SESSDATA=demo; bili_jct=token",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    recorded = capture_file.read_text(encoding="utf-8")
    assert "--bili-cookie" in recorded
    assert "SESSDATA=demo; bili_jct=token" in recorded
