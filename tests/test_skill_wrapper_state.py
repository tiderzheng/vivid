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

    state_file = skill_root / "state" / "skill_state.json"
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


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_operator_uses_persisted_default_model_and_data_dir(tmp_path):
    repo_root = tmp_path / "fake-repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "vivid_tool.ps1").write_text(
        "param(\n"
        "  [string]$Action,\n"
        "  [string]$Source,\n"
        "  [string]$DataDir,\n"
        "  [string]$Model\n"
        ")\n"
        "Write-Output (@{ ok = $true; action = $Action; source = $Source; data_dir = $DataDir; model = $Model } | ConvertTo-Json -Compress)\n",
        encoding="utf-8",
    )

    skill_root = tmp_path / "external-skill" / "skill" / "vivid-operator"
    skill_scripts_dir = skill_root / "scripts"
    skill_scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        Path("skill/vivid-operator/scripts/vivid_operator.ps1"),
        skill_scripts_dir / "vivid_operator.ps1",
    )

    state_file = skill_root / "state" / "skill_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "repo_root": str(repo_root),
                "default_whisper_model": "large",
                "default_data_dir": str(tmp_path / "saved-output"),
            },
            ensure_ascii=False,
        ),
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
            str(skill_scripts_dir / "vivid_operator.ps1"),
            "-Action",
            "quickread",
            "-Source",
            "https://example.com/demo",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in os.environ.items() if key != "VIVID_REPO_ROOT"},
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["model"] == "large"
    assert payload["data_dir"] == str(tmp_path / "saved-output")


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_operator_explicit_model_and_data_dir_override_persisted_defaults(tmp_path):
    repo_root = tmp_path / "fake-repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "vivid_tool.ps1").write_text(
        "param(\n"
        "  [string]$Action,\n"
        "  [string]$Source,\n"
        "  [string]$DataDir,\n"
        "  [string]$Model\n"
        ")\n"
        "Write-Output (@{ ok = $true; action = $Action; source = $Source; data_dir = $DataDir; model = $Model } | ConvertTo-Json -Compress)\n",
        encoding="utf-8",
    )

    skill_root = tmp_path / "external-skill" / "skill" / "vivid-operator"
    skill_scripts_dir = skill_root / "scripts"
    skill_scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        Path("skill/vivid-operator/scripts/vivid_operator.ps1"),
        skill_scripts_dir / "vivid_operator.ps1",
    )

    state_file = skill_root / "state" / "skill_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "repo_root": str(repo_root),
                "default_whisper_model": "large",
                "default_data_dir": str(tmp_path / "saved-output"),
            },
            ensure_ascii=False,
        ),
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
            str(skill_scripts_dir / "vivid_operator.ps1"),
            "-Action",
            "quickread",
            "-Source",
            "https://example.com/demo",
            "-Model",
            "small",
            "-DataDir",
            str(tmp_path / "explicit-output"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in os.environ.items() if key != "VIVID_REPO_ROOT"},
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["model"] == "small"
    assert payload["data_dir"] == str(tmp_path / "explicit-output")


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_operator_uses_persisted_cloud_mode_settings(tmp_path):
    repo_root = tmp_path / "fake-repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "vivid_tool.ps1").write_text(
        "param(\n"
        "  [string]$Action,\n"
        "  [string]$Source,\n"
        "  [string]$ExecutionMode,\n"
        "  [string]$ArtifactTarget,\n"
        "  [string]$CloudProfile,\n"
        "  [string]$CloudBaseUrl\n"
        ")\n"
        "Write-Output (@{ ok = $true; action = $Action; source = $Source; execution_mode = $ExecutionMode; artifact_target = $ArtifactTarget; cloud_profile = $CloudProfile; cloud_base_url = $CloudBaseUrl } | ConvertTo-Json -Compress)\n",
        encoding="utf-8",
    )

    skill_root = tmp_path / "external-skill" / "skill" / "vivid-operator"
    skill_scripts_dir = skill_root / "scripts"
    skill_scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        Path("skill/vivid-operator/scripts/vivid_operator.ps1"),
        skill_scripts_dir / "vivid_operator.ps1",
    )

    state_file = skill_root / "state" / "skill_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "repo_root": str(repo_root),
                "execution_mode": "cloud",
                "artifact_target": "both",
                "cloud_profile": "prod",
                "cloud_base_url": "https://cloud.example",
            },
            ensure_ascii=False,
        ),
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
            str(skill_scripts_dir / "vivid_operator.ps1"),
            "-Action",
            "quickread",
            "-Source",
            "https://example.com/demo",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in os.environ.items() if key != "VIVID_REPO_ROOT"},
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["execution_mode"] == "cloud"
    assert payload["artifact_target"] == "both"
    assert payload["cloud_profile"] == "prod"
    assert payload["cloud_base_url"] == "https://cloud.example"


@pytest.mark.skipif(_powershell_executable() is None, reason="PowerShell is not available")
def test_vivid_operator_explicit_execution_mode_overrides_persisted_cloud_settings(tmp_path):
    repo_root = tmp_path / "fake-repo"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "vivid_tool.ps1").write_text(
        "param(\n"
        "  [string]$Action,\n"
        "  [string]$Source,\n"
        "  [string]$ExecutionMode,\n"
        "  [string]$ArtifactTarget,\n"
        "  [string]$CloudProfile,\n"
        "  [string]$CloudBaseUrl\n"
        ")\n"
        "Write-Output (@{ ok = $true; action = $Action; source = $Source; execution_mode = $ExecutionMode; artifact_target = $ArtifactTarget; cloud_profile = $CloudProfile; cloud_base_url = $CloudBaseUrl } | ConvertTo-Json -Compress)\n",
        encoding="utf-8",
    )

    skill_root = tmp_path / "external-skill" / "skill" / "vivid-operator"
    skill_scripts_dir = skill_root / "scripts"
    skill_scripts_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        Path("skill/vivid-operator/scripts/vivid_operator.ps1"),
        skill_scripts_dir / "vivid_operator.ps1",
    )

    state_file = skill_root / "state" / "skill_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "repo_root": str(repo_root),
                "execution_mode": "cloud",
                "artifact_target": "both",
                "cloud_profile": "prod",
                "cloud_base_url": "https://cloud.example",
            },
            ensure_ascii=False,
        ),
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
            str(skill_scripts_dir / "vivid_operator.ps1"),
            "-Action",
            "quickread",
            "-Source",
            "https://example.com/demo",
            "-ExecutionMode",
            "local",
            "-ArtifactTarget",
            "local_only",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={key: value for key, value in os.environ.items() if key != "VIVID_REPO_ROOT"},
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["execution_mode"] == "local"
    assert payload["artifact_target"] == "local_only"
