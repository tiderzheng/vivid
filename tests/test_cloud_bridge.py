from __future__ import annotations

import json
from pathlib import Path

from app.services.cloud_bridge import run_cloud_quickread, sync_cloud_result_files


def _remote_payload() -> dict:
    return {
        "ok": True,
        "result": {
            "source": {"title": "demo"},
        },
        "files": {
            "workdir": "/srv/vivid/data/demo",
            "artifacts_dir": "/srv/vivid/data/demo/artifacts",
            "quickread_markdown": "/srv/vivid/data/demo/artifacts/quickread.md",
            "transcript_text": "/srv/vivid/data/demo/artifacts/transcript.txt",
            "vector_source_dir": "/srv/vivid/data/demo/vector_source",
            "vector_document_json": "/srv/vivid/data/demo/vector_source/document.json",
            "vector_chunks_jsonl": "/srv/vivid/data/demo/vector_source/chunks.jsonl",
            "vector_manifest_json": "/srv/vivid/data/demo/vector_source/manifest.json",
            "summary_markdown": "/srv/vivid/data/demo/artifacts/summary.md",
            "summary_json": "/srv/vivid/data/demo/artifacts/summary.json",
            "metadata_json": "/srv/vivid/data/demo/artifacts/metadata.json",
            "checkpoint_json": "/srv/vivid/data/demo/artifacts/checkpoint.json",
        },
    }


def test_sync_cloud_result_files_local_only_downloads_to_local(tmp_path, monkeypatch):
    downloaded: list[tuple[str, Path]] = []

    def fake_download(base_url: str, remote_path: str, destination: Path, timeout: int = 60) -> Path:
        downloaded.append((remote_path, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"downloaded from {remote_path}", encoding="utf-8")
        return destination

    monkeypatch.setattr("app.services.cloud_bridge.download_cloud_file", fake_download)

    payload = sync_cloud_result_files(
        "https://cloud.example",
        _remote_payload(),
        tmp_path / "local-data",
        artifact_target="local_only",
    )

    assert payload["files"]["workdir"].endswith("local-data\\demo")
    assert payload["files"]["summary_json"].endswith("local-data\\demo\\artifacts\\summary.json")
    assert payload["files"]["vector_document_json"].endswith("local-data\\demo\\vector_source\\document.json")
    assert "remote_files" not in payload
    assert len(downloaded) == 8


def test_sync_cloud_result_files_both_keeps_remote_and_local_refs(tmp_path, monkeypatch):
    def fake_download(base_url: str, remote_path: str, destination: Path, timeout: int = 60) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"downloaded from {remote_path}", encoding="utf-8")
        return destination

    monkeypatch.setattr("app.services.cloud_bridge.download_cloud_file", fake_download)

    payload = sync_cloud_result_files(
        "https://cloud.example",
        _remote_payload(),
        tmp_path / "local-data",
        artifact_target="both",
    )

    assert payload["files"]["metadata_json"].endswith("local-data\\demo\\artifacts\\metadata.json")
    assert payload["remote_files"]["metadata_json"] == "/srv/vivid/data/demo/artifacts/metadata.json"


def test_sync_cloud_result_files_cloud_only_keeps_remote_refs(tmp_path, monkeypatch):
    called = {"downloaded": False}

    def fake_download(base_url: str, remote_path: str, destination: Path, timeout: int = 60) -> Path:
        called["downloaded"] = True
        return destination

    monkeypatch.setattr("app.services.cloud_bridge.download_cloud_file", fake_download)

    payload = sync_cloud_result_files(
        "https://cloud.example",
        _remote_payload(),
        tmp_path / "local-data",
        artifact_target="cloud_only",
    )

    assert payload["files"]["metadata_json"] == "/srv/vivid/data/demo/artifacts/metadata.json"
    assert "remote_files" not in payload
    assert called["downloaded"] is False


def test_sync_cloud_result_files_avoids_overwriting_existing_local_workdir(tmp_path, monkeypatch):
    existing = tmp_path / "local-data" / "demo"
    (existing / "artifacts").mkdir(parents=True, exist_ok=True)
    (existing / "artifacts" / "summary.json").write_text("old", encoding="utf-8")

    def fake_download(base_url: str, remote_path: str, destination: Path, timeout: int = 60) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(f"downloaded from {remote_path}", encoding="utf-8")
        return destination

    monkeypatch.setattr("app.services.cloud_bridge.download_cloud_file", fake_download)

    payload = sync_cloud_result_files(
        "https://cloud.example",
        _remote_payload(),
        tmp_path / "local-data",
        artifact_target="local_only",
    )

    assert payload["files"]["workdir"].endswith("local-data\\demo-2")
    assert (existing / "artifacts" / "summary.json").read_text(encoding="utf-8") == "old"


def test_run_cloud_quickread_uses_data_dir_only_for_local_sync_and_not_remote_request(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return _remote_payload()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data, timeout):
            captured["url"] = url
            captured["data"] = dict(data)
            captured["timeout"] = timeout
            return FakeResponse()

    monkeypatch.setattr("app.services.cloud_bridge.requests.Session", lambda: FakeSession())
    monkeypatch.setattr(
        "app.services.cloud_bridge.sync_cloud_result_files",
        lambda base_url, payload, local_data_dir, artifact_target: {
            "files": {"workdir": str(local_data_dir / "demo")},
            "base_url": base_url,
            "artifact_target": artifact_target,
        },
    )

    settings = type("Settings", (), {"data_dir": tmp_path / "default-data"})()
    args = type(
        "Args",
        (),
        {
            "source": "https://example.com/video",
            "project_name": None,
            "platform": None,
            "model": "large",
            "data_dir": str(tmp_path / "local-sync"),
            "acquisition_mode": None,
            "transcription_backend": None,
            "vision_backend": None,
            "vision_api_config_id": None,
            "vision_timeout": None,
            "vision_sample_ms": None,
            "vision_min_duration_ms": None,
            "sessdata": "expired",
            "no_sessdata": True,
            "artifact_target": "both",
            "cloud_profile": None,
            "cloud_base_url": "https://cloud.example",
        },
    )()

    payload = run_cloud_quickread(args, settings)

    assert "data_dir" not in captured["data"]
    assert "sessdata" not in captured["data"]
    assert "no_sessdata" not in captured["data"]
    assert payload["files"]["workdir"].endswith("local-sync\\demo")


def test_run_cloud_quickread_resolves_base_url_from_cloud_profile_env(tmp_path, monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return _remote_payload()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data, timeout):
            captured["url"] = url
            captured["data"] = dict(data)
            return FakeResponse()

    monkeypatch.setattr("app.services.cloud_bridge.requests.Session", lambda: FakeSession())
    monkeypatch.setattr(
        "app.services.cloud_bridge.sync_cloud_result_files",
        lambda base_url, payload, local_data_dir, artifact_target: {"base_url": base_url},
    )
    monkeypatch.setenv("VIVID_CLOUD_PROFILE_PROD_BASE_URL", "https://profile.example")

    settings = type("Settings", (), {"data_dir": tmp_path / "default-data"})()
    args = type(
        "Args",
        (),
        {
            "source": "https://example.com/video",
            "project_name": None,
            "platform": None,
            "model": None,
            "data_dir": None,
            "acquisition_mode": None,
            "transcription_backend": None,
            "vision_backend": None,
            "vision_api_config_id": None,
            "vision_timeout": None,
            "vision_sample_ms": None,
            "vision_min_duration_ms": None,
            "sessdata": "expired",
            "no_sessdata": True,
            "artifact_target": "cloud_only",
            "cloud_profile": "prod",
            "cloud_base_url": None,
        },
    )()

    payload = run_cloud_quickread(args, settings)

    assert payload["base_url"] == "https://profile.example"
    assert captured["url"] == "https://profile.example/api/quickread"
    assert "sessdata" not in captured["data"]
    assert "no_sessdata" not in captured["data"]
