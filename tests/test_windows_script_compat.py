from __future__ import annotations

import os
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
def test_vivid_tool_ps1_forwards_bili_auth_poll_action(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("scripts/vivid_tool.ps1"), scripts_dir / "vivid_tool.ps1")
    capture_file = tmp_path / "vivid_tool_bili_auth_args.txt"
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
            "bili-auth-poll",
            "-QrcodeKey",
            "abc",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    recorded = capture_file.read_text(encoding="utf-8")
    assert "-m app.control_cli bili-auth-poll" in recorded
    assert "--qrcode-key abc" in recorded


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_tool_ps1_returns_busy_when_quickread_lock_exists(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("scripts/vivid_tool.ps1"), scripts_dir / "vivid_tool.ps1")
    capture_file = tmp_path / "vivid_tool_busy_args.txt"
    fake_python = scripts_dir / "fake_python.cmd"
    _fake_python_script(fake_python, capture_file)
    _fake_ensure_venv_script(scripts_dir / "ensure_venv.ps1", fake_python)
    data_dir = repo_root / "data"
    lock_path = data_dir / ".vivid" / "quickread.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(
        f'{{"pid": {os.getpid()}, "source": "https://example.com/old"}}',
        encoding="utf-8",
    )

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
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 73
    assert not capture_file.exists()
    assert '"error_code":"quickread_busy"' in result.stdout.replace(" ", "")
    assert "quickread.lock" in result.stdout


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_tool_ps1_skips_quickread_lock_for_cloud_mode(tmp_path):
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path("scripts/vivid_tool.ps1"), scripts_dir / "vivid_tool.ps1")
    capture_file = tmp_path / "vivid_tool_cloud_args.txt"
    fake_python = scripts_dir / "fake_python.cmd"
    _fake_python_script(fake_python, capture_file)
    _fake_ensure_venv_script(scripts_dir / "ensure_venv.ps1", fake_python)
    data_dir = repo_root / "data"
    lock_path = data_dir / ".vivid" / "quickread.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(
        f'{{"pid": {os.getpid()}, "source": "https://example.com/local"}}',
        encoding="utf-8",
    )

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
            "-ExecutionMode",
            "cloud",
            "-CloudBaseUrl",
            "https://cloud.example",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    recorded = capture_file.read_text(encoding="utf-8")
    assert "-m app.control_cli quickread" in recorded
    assert "--execution-mode cloud" in recorded
    assert "--cloud-base-url https://cloud.example" in recorded


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
