from __future__ import annotations

from pathlib import Path
from typing import Any

import requests


class CloudQuickreadError(Exception):
    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(payload.get("error") or "cloud quickread failed")
        self.payload = payload


def _profile_base_url_env_key(profile: str) -> str:
    sanitized = "".join(char if char.isalnum() else "_" for char in profile.strip().upper())
    return f"VIVID_CLOUD_PROFILE_{sanitized}_BASE_URL"


def _resolve_cloud_base_url(args) -> str:
    explicit = (getattr(args, "cloud_base_url", None) or "").strip()
    if explicit:
        return explicit
    env_default = __import__("os").environ.get("VIVID_CLOUD_BASE_URL", "").strip()
    if env_default:
        return env_default
    profile = (getattr(args, "cloud_profile", None) or "").strip()
    if profile:
        profile_env = __import__("os").environ.get(_profile_base_url_env_key(profile), "").strip()
        if profile_env:
            return profile_env
    return ""


def _allocate_sync_workdir(local_data_dir: Path, workdir_name: str) -> Path:
    root = local_data_dir.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / workdir_name
    if not candidate.exists():
        return candidate
    if candidate.is_dir() and not any(candidate.iterdir()):
        return candidate
    suffix = 2
    while True:
        next_candidate = root / f"{workdir_name}-{suffix}"
        if not next_candidate.exists():
            return next_candidate
        suffix += 1


def run_cloud_quickread(args, settings) -> dict[str, Any]:
    base_url = _resolve_cloud_base_url(args)
    if not base_url:
        raise ValueError("cloud_base_url is required when execution_mode=cloud")

    payload = {
        "source": args.source,
        "project_name": args.project_name or "",
        "platform": args.platform or "",
        "whisper_model": args.model or "",
        "acquisition_mode": args.acquisition_mode or "",
        "transcription_backend": args.transcription_backend or "",
        "vision_backend": args.vision_backend or "",
        "vision_api_config_id": args.vision_api_config_id or "",
        "vision_timeout": args.vision_timeout or "",
        "vision_sample_ms": args.vision_sample_ms or "",
        "vision_min_duration_ms": args.vision_min_duration_ms or "",
    }
    suppress_sessdata = bool(getattr(args, "no_sessdata", False))
    bili_cookie = _optional_text(getattr(args, "bili_cookie", None)) or _optional_text(getattr(settings, "bili_cookie", None))
    sessdata = (
        None
        if suppress_sessdata
        else _optional_text(getattr(args, "sessdata", None)) or _optional_text(getattr(settings, "sessdata", None))
    )
    if bili_cookie:
        payload["bili_cookie"] = bili_cookie
    if sessdata:
        payload["sessdata"] = sessdata
    if suppress_sessdata:
        payload["no_sessdata"] = True

    with requests.Session() as session:
        response = session.post(f"{base_url.rstrip('/')}/api/quickread", data=payload, timeout=30)
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise ValueError("cloud quickread returned a non-JSON response") from None
        if response.status_code >= 400 or not data.get("ok", False):
            raise CloudQuickreadError(data)

    data.pop("ok", None)
    data["execution_mode"] = "cloud"
    artifact_target = getattr(args, "artifact_target", "local_only")
    data["artifact_target"] = artifact_target
    data["cloud_profile"] = getattr(args, "cloud_profile", None)
    data["cloud_base_url"] = base_url
    return sync_cloud_result_files(
        base_url,
        data,
        Path(args.data_dir).expanduser() if getattr(args, "data_dir", None) else settings.data_dir,
        artifact_target=artifact_target,
    )


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def download_cloud_file(base_url: str, remote_path: str, destination: Path, timeout: int = 60) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        response = session.get(
            f"{base_url.rstrip('/')}/files",
            params={"path": remote_path},
            timeout=timeout,
        )
        response.raise_for_status()
        destination.write_bytes(response.content)
    return destination


def sync_cloud_result_files(
    base_url: str,
    payload: dict[str, Any],
    local_data_dir: Path,
    *,
    artifact_target: str,
) -> dict[str, Any]:
    files = payload.get("files")
    if not isinstance(files, dict) or artifact_target == "cloud_only":
        return payload

    remote_files = dict(files)
    remote_workdir = remote_files.get("workdir")
    if not remote_workdir:
        return payload

    workdir_name = Path(str(remote_workdir)).name
    local_workdir = _allocate_sync_workdir(local_data_dir, workdir_name)
    local_artifacts_dir = local_workdir / "artifacts"
    local_vector_dir = local_workdir / "vector_source"

    file_targets = {
        "quickread_markdown": local_artifacts_dir / "quickread.md",
        "transcript_text": local_artifacts_dir / "transcript.txt",
        "summary_markdown": local_artifacts_dir / "summary.md",
        "summary_json": local_artifacts_dir / "summary.json",
        "metadata_json": local_artifacts_dir / "metadata.json",
        "vector_document_json": local_vector_dir / "document.json",
        "vector_chunks_jsonl": local_vector_dir / "chunks.jsonl",
        "vector_manifest_json": local_vector_dir / "manifest.json",
        "calibrated_cn_markdown": local_artifacts_dir / "calibrated_cn.md",
        "calibrated_en_markdown": local_artifacts_dir / "calibrated_en.md",
    }

    rewritten = dict(remote_files)
    rewritten["workdir"] = str(local_workdir)
    rewritten["artifacts_dir"] = str(local_artifacts_dir)
    rewritten["vector_source_dir"] = str(local_vector_dir)

    for key, destination in file_targets.items():
        remote_path = remote_files.get(key)
        if not remote_path:
            rewritten[key] = None
            continue
        download_cloud_file(base_url, str(remote_path), destination)
        rewritten[key] = str(destination)

    if artifact_target == "both":
        payload["remote_files"] = remote_files
    payload["files"] = rewritten
    artifacts = payload.get("artifacts")
    if isinstance(artifacts, dict):
        artifacts = dict(artifacts)
        artifacts["workdir"] = str(local_workdir)
        artifacts["artifacts_dir"] = str(local_artifacts_dir)
        artifacts["vector_source_dir"] = str(local_vector_dir)
        if rewritten.get("vector_document_json"):
            artifacts["vector_document_json"] = rewritten.get("vector_document_json")
        if rewritten.get("vector_chunks_jsonl"):
            artifacts["vector_chunks_jsonl"] = rewritten.get("vector_chunks_jsonl")
        if rewritten.get("vector_manifest_json"):
            artifacts["vector_manifest_json"] = rewritten.get("vector_manifest_json")
        payload["artifacts"] = artifacts
    return payload
