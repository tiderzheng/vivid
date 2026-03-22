from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell_executable() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_operator_persists_and_reuses_repo_root_state(tmp_path):
    repo_root = tmp_path / "fake-repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "vivid_tool.ps1").write_text(
        "param([string]$Action)\n"
        "Write-Output (@{ ok = $true; action = $Action } | ConvertTo-Json -Compress)\n",
        encoding="utf-8",
    )

    skill_root = tmp_path / "external-skill" / "skill" / "vivid-operator"
    skill_scripts_dir = skill_root / "scripts"
    skill_scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        Path("skill/vivid-operator/scripts/vivid_operator.ps1"),
        skill_scripts_dir / "vivid_operator.ps1",
    )

    state_file = skill_root / "state" / "repo_root.json"
    powershell = _powershell_executable()
    assert powershell is not None

    first = subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(skill_scripts_dir / "vivid_operator.ps1"),
            "-Action",
            "paths",
            "-VividRoot",
            str(repo_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert first.returncode == 0, first.stderr or first.stdout
    assert state_file.exists()
    cached = json.loads(state_file.read_text(encoding="utf-8"))
    assert cached["repo_root"] == str(repo_root)

    second = subprocess.run(
        [
            powershell,
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(skill_scripts_dir / "vivid_operator.ps1"),
            "-Action",
            "paths",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in os.environ.items() if key != "VIVID_REPO_ROOT"},
    )

    assert second.returncode == 0, second.stderr or second.stdout
    assert '"action":"paths"' in second.stdout.replace(" ", "")
