import io
import time
from types import SimpleNamespace
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.config import Settings
from app.exceptions import BilibiliSessdataExpiredError
from app.pipeline.orchestrator import OrchestratorResult
from app.models.artifact import ArtifactBundle
from app.models.source import SourceInfo
from app.models.summary import SummaryResult
from app.models.transcript import TranscriptResult
from app.services.run_state import save_run_state
from app.web import app, build_open_folder_command


def _build_settings(tmp_path: Path) -> Settings:
    return Settings(
        repo_root=tmp_path,
        tools_root=tmp_path,
        data_dir=tmp_path / "data",
        ffmpeg_bin="ffmpeg",
        whisper_root=None,
        ears4_api="http://127.0.0.1:7860",
        eyes_api="http://127.0.0.1:9531",
        default_format="both",
        default_model="base",
        language="zh",
        transcription_preset_id=None,
        acquisition_mode="auto",
        transcription_backend="internal",
        transcription_device=None,
        transcription_task=None,
        transcription_extract_audio=True,
        transcription_output_dir=None,
        transcribe_timeout=1800,
        ocr_timeout=600,
        llm_max_chars=8000,
        siliconflow_base_url="https://api.siliconflow.cn/v1/chat/completions",
        dashscope_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        siliconflow_model="model-a",
        dashscope_model="model-b",
        siliconflow_api_key=None,
        dashscope_api_key=None,
        bili_script=tmp_path / "bili.py",
        douyin_script=tmp_path / "douyin.js",
        vision_api_config_id="cfg-1",
        vision_backend="internal",
        vision_api_base=None,
        vision_api_path=None,
        vision_api_key=None,
        vision_model=None,
        vision_timeout=60,
        vision_prompt_id="default",
        vision_prompt=None,
        vision_system_prompt=None,
        vision_sample_ms=1000,
        vision_min_duration_ms=1200,
        vision_api_configs_path=tmp_path / "configs" / "vision" / "api_configs.json",
        vision_prompts_path=tmp_path / "configs" / "vision" / "prompts.json",
        transcription_presets_path=tmp_path / "configs" / "transcription" / "presets.json",
    )


def _write_config_files(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.vision_api_configs_path.parent.mkdir(parents=True, exist_ok=True)
    settings.transcription_presets_path.parent.mkdir(parents=True, exist_ok=True)
    settings.vision_api_configs_path.write_text(
        '{"items":[{"id":"cfg-1","name":"cfg","api_base":"https://example.com","model":"vl","timeout":60}],"selected_id":"cfg-1"}',
        encoding="utf-8",
    )
    settings.vision_prompts_path.write_text(
        '[{"id":"default","name":"默认","content":"只返回字幕"}]',
        encoding="utf-8",
    )
    settings.transcription_presets_path.write_text(
        '{"items":[{"id":"preset-1","name":"默认","model":"base","device":"auto","task":"transcribe","extract_audio":true}],"selected_id":"preset-1"}',
        encoding="utf-8",
    )


def test_web_index_renders(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Vivid Web UI" in response.text
    assert "Whisper 模型" in response.text
    assert "历史任务" in response.text
    assert "批量 URL" in response.text
    assert 'name="bili_cookie"' in response.text
    assert 'name="sessdata"' in response.text


def test_web_bootstrap_returns_options(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    monkeypatch.setattr(
        "app.web.ensure_opencv_dependency",
        lambda raise_on_failure=False: {"ok": True, "package": "opencv-python", "installed": False},
    )
    client = TestClient(app)

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["defaults"]["whisper_model"] == "base"
    assert payload["options"]["vision_api_configs"]["selected_id"] == "cfg-1"
    assert payload["options"]["transcription_presets"]["selected_id"] == "preset-1"
    assert payload["dependencies"]["opencv"]["package"] == "opencv-python"
    assert payload["stats"]["queued"] == 0
    assert payload["defaults"]["data_dir"] == str(settings.data_dir)
    assert "sessdata" not in payload["defaults"]
    assert "no_sessdata" not in payload["defaults"]
    assert "bili_cookie" not in payload["defaults"]


def test_web_default_output_dir_can_be_saved(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    client = TestClient(app)
    custom_dir = tmp_path / "custom-output"

    response = client.post("/api/preferences/output-dir", data={"data_dir": str(custom_dir)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert Path(payload["data_dir"]).resolve() == custom_dir.resolve()
    assert custom_dir.exists()

    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert bootstrap_payload["defaults"]["data_dir"] == str(custom_dir.resolve())

    preferences_path = settings.repo_root / "configs" / "web_ui" / "preferences.json"
    preferences_payload = preferences_path.read_text(encoding="utf-8")
    assert '"default_output_dir": "./custom-output"' in preferences_payload


def test_web_default_vision_openai_can_be_saved(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    client = TestClient(app)

    response = client.post(
        "/api/preferences/vision-openai",
        data={
            "vision_api_base": "https://api.example.com",
            "vision_api_path": "/v1/chat/completions",
            "vision_api_key": "sk-test",
            "vision_model": "demo-vl",
            "vision_prompt": "只返回字幕",
            "vision_system_prompt": "system",
            "vision_timeout": "90",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["vision_model"] == "demo-vl"

    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    defaults = bootstrap_response.json()["defaults"]
    assert defaults["vision_api_base"] == "https://api.example.com"
    assert defaults["vision_api_key"] == "sk-test"
    assert defaults["vision_model"] == "demo-vl"
    assert defaults["vision_prompt"] == "只返回字幕"


def test_web_quickread_upload_works(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    workdir = settings.data_dir / "demo"
    artifacts_dir = workdir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    bundle = ArtifactBundle(
        workdir=workdir,
        artifacts_dir=artifacts_dir,
        quickread_markdown=artifacts_dir / "quickread.md",
        transcript_text=artifacts_dir / "transcript.txt",
        summary_markdown=artifacts_dir / "summary.md",
        summary_json=artifacts_dir / "summary.json",
        metadata_json=artifacts_dir / "metadata.json",
    )
    for path in [
        bundle.quickread_markdown,
        bundle.transcript_text,
        bundle.summary_markdown,
        bundle.summary_json,
        bundle.metadata_json,
    ]:
        path.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(
        "app.web.run_quickread",
        lambda _options: OrchestratorResult(
            source=SourceInfo(raw_source="local", platform="local", title="demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(
                one_line="一句话",
                detailed="详细",
                key_points=["a", "b"],
                provider="test",
            ),
            artifacts=bundle,
            rendered="rendered",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/quickread",
        data={
            "project_name": "demo",
            "whisper_model": "base",
            "output_format": "both",
            "platform": "local",
            "language": "zh",
            "acquisition_mode": "auto",
            "transcription_backend": "internal",
            "vision_backend": "internal",
        },
        files={"media_file": ("demo.mp4", b"123", "video/mp4")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["transcript"]["acquisition_method"] == "Internal Whisper base"
    assert "quickread_markdown" in payload["files"]


def test_web_quickread_returns_vector_source_files(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    workdir = settings.data_dir / "demo"
    artifacts_dir = workdir / "artifacts"
    vector_dir = workdir / "vector_source"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    vector_dir.mkdir(parents=True, exist_ok=True)
    file_map = {
        "quickread_markdown": artifacts_dir / "quickread.md",
        "transcript_text": artifacts_dir / "transcript.txt",
        "summary_markdown": artifacts_dir / "summary.md",
        "summary_json": artifacts_dir / "summary.json",
        "metadata_json": artifacts_dir / "metadata.json",
        "vector_document_json": vector_dir / "document.json",
        "vector_chunks_jsonl": vector_dir / "chunks.jsonl",
        "vector_manifest_json": vector_dir / "manifest.json",
    }
    for path in file_map.values():
        path.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(
        "app.web.run_quickread",
        lambda _options: OrchestratorResult(
            source=SourceInfo(raw_source="local", platform="local", title="demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(
                title="标题",
                overview="概览",
                core_points=["a"],
                controversies=["b"],
                action_suggestions=["c"],
                playful_comment="d",
                provider="test",
            ),
            artifacts=SimpleNamespace(
                workdir=workdir,
                artifacts_dir=artifacts_dir,
                quickread_markdown=file_map["quickread_markdown"],
                transcript_text=file_map["transcript_text"],
                summary_markdown=file_map["summary_markdown"],
                summary_json=file_map["summary_json"],
                metadata_json=file_map["metadata_json"],
                checkpoint_json=None,
                vector_source_dir=vector_dir,
                vector_document_json=file_map["vector_document_json"],
                vector_chunks_jsonl=file_map["vector_chunks_jsonl"],
                vector_manifest_json=file_map["vector_manifest_json"],
                calibrated_cn_markdown=None,
                calibrated_en_markdown=None,
            ),
            rendered="rendered",
            calibration=None,
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/quickread",
        data={
            "project_name": "demo",
            "whisper_model": "base",
            "output_format": "both",
            "platform": "local",
            "language": "zh",
            "acquisition_mode": "auto",
            "transcription_backend": "internal",
            "vision_backend": "internal",
        },
        files={"media_file": ("demo.mp4", b"123", "video/mp4")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["files"]["vector_source_dir"].endswith("vector_source")
    assert payload["files"]["vector_document_json"].endswith("document.json")
    assert payload["files"]["vector_chunks_jsonl"].endswith("chunks.jsonl")
    assert payload["files"]["vector_manifest_json"].endswith("manifest.json")


def test_web_quickread_collects_legacy_sessdata_without_echoing_it(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    captured = {}

    def fake_build_runtime_options(_settings, values):
        captured["values"] = values
        return object()

    monkeypatch.setattr("app.web.build_runtime_options", fake_build_runtime_options)
    monkeypatch.setattr(
        "app.web.run_quickread",
        lambda _options: OrchestratorResult(
            source=SourceInfo(raw_source="https://www.bilibili.com/video/BV1xx", platform="bilibili", title="demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=ArtifactBundle(
                workdir=settings.data_dir / "demo",
                artifacts_dir=settings.data_dir / "demo" / "artifacts",
                quickread_markdown=settings.data_dir / "demo" / "artifacts" / "quickread.md",
                transcript_text=settings.data_dir / "demo" / "artifacts" / "transcript.txt",
                summary_markdown=settings.data_dir / "demo" / "artifacts" / "summary.md",
                summary_json=settings.data_dir / "demo" / "artifacts" / "summary.json",
                metadata_json=settings.data_dir / "demo" / "artifacts" / "metadata.json",
            ),
            rendered="rendered",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/quickread",
        data={
            "source_url": "https://www.bilibili.com/video/BV1xx",
            "sessdata": "fresh-cookie",
        },
    )

    assert response.status_code == 200
    assert captured["values"]["sessdata"] == "fresh-cookie"
    assert "no_sessdata" not in captured["values"]
    assert "fresh-cookie" not in response.text


def test_web_quickread_collects_bili_cookie_without_echoing_it(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    captured = {}

    def fake_build_runtime_options(_settings, values):
        captured["values"] = values
        return object()

    monkeypatch.setattr("app.web.build_runtime_options", fake_build_runtime_options)
    monkeypatch.setattr(
        "app.web.run_quickread",
        lambda _options: OrchestratorResult(
            source=SourceInfo(raw_source="https://www.bilibili.com/video/BV1xx", platform="bilibili", title="demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=ArtifactBundle(
                workdir=settings.data_dir / "demo",
                artifacts_dir=settings.data_dir / "demo" / "artifacts",
                quickread_markdown=settings.data_dir / "demo" / "artifacts" / "quickread.md",
                transcript_text=settings.data_dir / "demo" / "artifacts" / "transcript.txt",
                summary_markdown=settings.data_dir / "demo" / "artifacts" / "summary.md",
                summary_json=settings.data_dir / "demo" / "artifacts" / "summary.json",
                metadata_json=settings.data_dir / "demo" / "artifacts" / "metadata.json",
            ),
            rendered="rendered",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/quickread",
        data={
            "source_url": "https://www.bilibili.com/video/BV1xx",
            "bili_cookie": "SESSDATA=demo; bili_jct=token",
        },
    )

    assert response.status_code == 200
    assert captured["values"]["bili_cookie"] == "SESSDATA=demo; bili_jct=token"
    assert "bili_cookie" not in response.text


def test_web_quickread_treats_bili_sessdata_errors_as_generic_failures(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    def fake_run(_options):
        raise BilibiliSessdataExpiredError("api error -101: 账号未登录")

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)

    response = client.post("/api/quickread", data={"source_url": "https://www.bilibili.com/video/BV1xx"})

    assert response.status_code == 500
    payload = response.json()
    assert payload["ok"] is False
    assert "api error -101: 账号未登录" in payload["error"]
    assert "error_code" not in payload


def test_web_jobs_request_omits_sessdata_from_history(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    monkeypatch.setattr("app.web.build_runtime_options", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "app.web._invoke_run_quickread",
        lambda *_args, **_kwargs: OrchestratorResult(
            source=SourceInfo(raw_source="https://www.bilibili.com/video/BV1xx", platform="bilibili", title="demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=ArtifactBundle(
                workdir=settings.data_dir / "demo",
                artifacts_dir=settings.data_dir / "demo" / "artifacts",
                quickread_markdown=settings.data_dir / "demo" / "artifacts" / "quickread.md",
                transcript_text=settings.data_dir / "demo" / "artifacts" / "transcript.txt",
                summary_markdown=settings.data_dir / "demo" / "artifacts" / "summary.md",
                summary_json=settings.data_dir / "demo" / "artifacts" / "summary.json",
                metadata_json=settings.data_dir / "demo" / "artifacts" / "metadata.json",
            ),
            rendered="rendered",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/jobs",
        data={
            "source_url": "https://www.bilibili.com/video/BV1xx",
            "sessdata": "fresh-cookie",
        },
    )

    assert response.status_code == 200
    job = response.json()["job"]
    assert "sessdata" not in job["request"]


def test_web_jobs_request_omits_bili_cookie_from_history(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    captured = {}

    def fake_build_runtime_options(_settings, values):
        captured["values"] = values
        return object()

    monkeypatch.setattr("app.web.build_runtime_options", fake_build_runtime_options)
    monkeypatch.setattr(
        "app.web._invoke_run_quickread",
        lambda *_args, **_kwargs: OrchestratorResult(
            source=SourceInfo(raw_source="https://www.bilibili.com/video/BV1xx", platform="bilibili", title="demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=ArtifactBundle(
                workdir=settings.data_dir / "demo",
                artifacts_dir=settings.data_dir / "demo" / "artifacts",
                quickread_markdown=settings.data_dir / "demo" / "artifacts" / "quickread.md",
                transcript_text=settings.data_dir / "demo" / "artifacts" / "transcript.txt",
                summary_markdown=settings.data_dir / "demo" / "artifacts" / "summary.md",
                summary_json=settings.data_dir / "demo" / "artifacts" / "summary.json",
                metadata_json=settings.data_dir / "demo" / "artifacts" / "metadata.json",
            ),
            rendered="rendered",
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/api/jobs",
        data={
            "source_url": "https://www.bilibili.com/video/BV1xx",
            "bili_cookie": "SESSDATA=demo; bili_jct=token",
        },
    )

    assert response.status_code == 200
    assert captured["values"]["bili_cookie"] == "SESSDATA=demo; bili_jct=token"
    job = response.json()["job"]
    assert "bili_cookie" not in job["request"]


def test_web_retry_job_forwards_auth_overrides(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    captured = {}

    class FakeManager:
        def retry(self, _settings, job_id, overrides=None):
            captured["job_id"] = job_id
            captured["overrides"] = overrides
            return {"job_id": "new-job"}

    monkeypatch.setattr("app.web.get_job_manager", lambda _settings: FakeManager())
    client = TestClient(app)

    response = client.post(
        "/api/jobs/job-1/retry",
        data={
            "sessdata": "fresh-cookie",
            "bili_cookie": "SESSDATA=demo; bili_jct=token",
            "no_sessdata": "true",
        },
    )

    assert response.status_code == 200
    assert captured["job_id"] == "job-1"
    assert captured["overrides"] == {
        "sessdata": "fresh-cookie",
        "bili_cookie": "SESSDATA=demo; bili_jct=token",
        "no_sessdata": True,
    }


def test_web_quickread_requires_source(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)
    client = TestClient(app)

    response = client.post("/api/quickread", data={})

    assert response.status_code == 400


def test_web_jobs_flow_works(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    workdir = settings.data_dir / "demo"
    artifacts_dir = workdir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    bundle = ArtifactBundle(
        workdir=workdir,
        artifacts_dir=artifacts_dir,
        quickread_markdown=artifacts_dir / "quickread.md",
        transcript_text=artifacts_dir / "transcript.txt",
        summary_markdown=artifacts_dir / "summary.md",
        summary_json=artifacts_dir / "summary.json",
        metadata_json=artifacts_dir / "metadata.json",
    )
    for path in [
        bundle.quickread_markdown,
        bundle.transcript_text,
        bundle.summary_markdown,
        bundle.summary_json,
        bundle.metadata_json,
    ]:
        path.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(
        "app.web.run_quickread",
        lambda _options: OrchestratorResult(
            source=SourceInfo(raw_source="local", platform="local", title="demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper small"),
            summary=SummaryResult(
                one_line="一句话",
                detailed="详细",
                key_points=["a", "b"],
                provider="test",
            ),
            artifacts=bundle,
            rendered="rendered",
        ),
    )

    client = TestClient(app)
    create_response = client.post(
        "/api/jobs",
        data={
            "project_name": "demo",
            "whisper_model": "small",
            "output_format": "both",
            "platform": "local",
            "language": "zh",
            "acquisition_mode": "auto",
            "transcription_backend": "internal",
            "vision_backend": "internal",
        },
        files={"media_file": ("demo.mp4", b"123", "video/mp4")},
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["ok"] is True
    job_id = create_payload["job"]["job_id"]

    job_payload = None
    for _ in range(40):
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        job_payload = response.json()["job"]
        if job_payload["status"] == "completed":
            break
        time.sleep(0.05)

    assert job_payload is not None
    assert job_payload["status"] == "completed"
    assert job_payload["result"]["transcript"]["acquisition_method"] == "Internal Whisper small"

    list_response = client.get("/api/jobs")
    assert list_response.status_code == 200
    jobs = list_response.json()["jobs"]
    assert any(item["job_id"] == job_id for item in jobs)


def test_web_job_retry_delete_and_open_folder(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    counter = {"value": 0}

    def fake_run(_options):
        counter["value"] += 1
        workdir = settings.data_dir / f"demo-{counter['value']}"
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text("ok", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source="local", platform="local", title=f"demo-{counter['value']}"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    popen_calls = []
    monkeypatch.setattr("app.web.run_quickread", fake_run)
    monkeypatch.setattr("app.web.subprocess.Popen", lambda args: popen_calls.append(args))

    client = TestClient(app)
    create_response = client.post(
        "/api/jobs",
        data={"project_name": "demo", "platform": "local", "whisper_model": "base"},
        files={"media_file": ("demo.mp4", b"123", "video/mp4")},
    )
    assert create_response.status_code == 200
    first_job_id = create_response.json()["job"]["job_id"]

    first_job = None
    for _ in range(40):
        response = client.get(f"/api/jobs/{first_job_id}")
        first_job = response.json()["job"]
        if first_job["status"] == "completed":
            break
        time.sleep(0.05)
    assert first_job is not None
    assert first_job["status"] == "completed"

    open_response = client.post(
        "/api/open-folder",
        params={"path": first_job["result"]["files"]["workdir"]},
    )
    assert open_response.status_code == 200
    assert popen_calls

    retry_response = client.post(f"/api/jobs/{first_job_id}/retry")
    assert retry_response.status_code == 200
    second_job_id = retry_response.json()["job"]["job_id"]
    assert second_job_id != first_job_id

    second_job = None
    for _ in range(40):
        response = client.get(f"/api/jobs/{second_job_id}")
        second_job = response.json()["job"]
        if second_job["status"] == "completed":
            break
        time.sleep(0.05)
    assert second_job is not None
    assert second_job["status"] == "completed"

    delete_response = client.delete(f"/api/jobs/{first_job_id}", params={"delete_files": "true"})
    assert delete_response.status_code == 200
    assert not Path(first_job["result"]["files"]["workdir"]).exists()

    missing_response = client.get(f"/api/jobs/{first_job_id}")
    assert missing_response.status_code == 404


def test_build_open_folder_command_cross_platform(monkeypatch, tmp_path):
    folder = tmp_path
    monkeypatch.setattr("app.web.sys.platform", "win32")
    assert build_open_folder_command(folder) == ["explorer.exe", str(folder)]

    monkeypatch.setattr("app.web.sys.platform", "darwin")
    monkeypatch.setattr("app.web.shutil.which", lambda name: "/usr/bin/open" if name == "open" else None)
    assert build_open_folder_command(folder) == ["open", str(folder)]

    monkeypatch.setattr("app.web.sys.platform", "linux")
    monkeypatch.setattr("app.web.shutil.which", lambda name: "/usr/bin/xdg-open" if name == "xdg-open" else None)
    assert build_open_folder_command(folder) == ["xdg-open", str(folder)]


def test_web_queue_progress_and_cancel(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    def slow_run(_options):
        time.sleep(0.25)
        workdir = settings.data_dir / f"job-{time.time_ns()}"
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text("ok", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source="local", platform="local", title="slow"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    monkeypatch.setattr("app.web.run_quickread", slow_run)
    client = TestClient(app)

    job_ids = []
    for _ in range(3):
        response = client.post(
            "/api/jobs",
            data={"project_name": "demo", "platform": "local", "whisper_model": "base"},
            files={"media_file": ("demo.mp4", b"123", "video/mp4")},
        )
        assert response.status_code == 200
        payload = response.json()["job"]
        job_ids.append(payload["job_id"])

    queued_job = None
    for _ in range(40):
        response = client.get(f"/api/jobs/{job_ids[2]}")
        queued_job = response.json()["job"]
        if queued_job["status"] == "queued":
            break
        time.sleep(0.02)

    assert queued_job is not None
    assert queued_job["status"] == "queued"
    assert queued_job["queue_position"] == 1
    assert queued_job["can_cancel"] is True
    assert queued_job["progress"] == 5

    cancel_response = client.post(f"/api/jobs/{job_ids[2]}/cancel")
    assert cancel_response.status_code == 200
    cancelled = cancel_response.json()["job"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["can_retry"] is True

    bootstrap_response = client.get("/api/bootstrap")
    assert bootstrap_response.status_code == 200
    stats = bootstrap_response.json()["stats"]
    assert stats["cancelled"] >= 1


def test_web_job_events_stream(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    def fake_run(_options, event_callback=None):
        if event_callback:
            event_callback("download", "开始下载媒体", {"platform": "douyin"})
            event_callback("transcription", "开始 Whisper 转录", {"model": "base"})
            event_callback("summarize", "开始生成总结")
        workdir = settings.data_dir / "events-demo"
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text("ok", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source="local", platform="douyin", title="events-demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)
    response = client.post(
        "/api/jobs",
        data={"project_name": "demo", "platform": "douyin"},
        files={"media_file": ("demo.mp4", b"123", "video/mp4")},
    )
    assert response.status_code == 200
    job_id = response.json()["job"]["job_id"]

    job = None
    for _ in range(40):
        detail = client.get(f"/api/jobs/{job_id}")
        job = detail.json()["job"]
        if job["status"] == "completed":
            break
        time.sleep(0.05)

    assert job is not None
    assert job["status"] == "completed"
    stages = [event["stage"] for event in job["events"]]
    assert "download" in stages
    assert "transcription" in stages
    assert "summarize" in stages


def test_web_job_sse_endpoint(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    def fake_run(_options, event_callback=None):
        if event_callback:
            event_callback("download", "开始下载媒体")
            event_callback("summarize", "开始生成总结")
        workdir = settings.data_dir / "sse-demo"
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text("ok", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source="local", platform="local", title="sse-demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)
    create_response = client.post(
        "/api/jobs",
        data={"project_name": "demo", "platform": "local"},
        files={"media_file": ("demo.mp4", b"123", "video/mp4")},
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["job"]["job_id"]

    with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "event: job" in body
    assert "\"status\": \"completed\"" in body


def test_web_batch_urls_create_multiple_jobs(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    calls = []

    def fake_run(options):
        calls.append((options.source, options.whisper_model, str(options.data_dir)))
        workdir = settings.data_dir / f"batch-{len(calls)}"
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text("ok", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source=options.source, platform="douyin", title=f"batch-{len(calls)}"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method=f"Internal Whisper {options.whisper_model}"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)
    response = client.post(
        "/api/jobs",
        data={
            "source_urls": "https://example.com/1\n\nhttps://example.com/2\nhttps://example.com/1",
            "project_name": "batch-demo",
            "platform": "douyin",
            "whisper_model": "small",
            "data_dir": str(settings.data_dir),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["batch"]["count"] == 2
    assert len(payload["jobs"]) == 2

    job_ids = [job["job_id"] for job in payload["jobs"]]
    completed = set()
    for _ in range(40):
        for job_id in job_ids:
            detail = client.get(f"/api/jobs/{job_id}")
            assert detail.status_code == 200
            job = detail.json()["job"]
            if job["status"] == "completed":
                completed.add(job_id)
                assert job["request"]["whisper_model"] == "small"
                assert Path(job["request"]["data_dir"]).resolve() == settings.data_dir.resolve()
        if len(completed) == 2:
            break
        time.sleep(0.05)

    assert len(completed) == 2
    assert {item[0] for item in calls} == {"https://example.com/1", "https://example.com/2"}
    assert all(item[1] == "small" for item in calls)


def test_web_batch_export_returns_zip(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    counter = {"value": 0}

    def fake_run(options):
        counter["value"] += 1
        workdir = settings.data_dir / f"export-{counter['value']}"
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text(f"{options.source}-{path.name}", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source=options.source, platform="douyin", title=f"export-{counter['value']}"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)
    create_response = client.post(
        "/api/jobs",
        data={
            "source_urls": "https://example.com/a\nhttps://example.com/b",
            "project_name": "export-demo",
            "platform": "douyin",
        },
    )
    assert create_response.status_code == 200
    job_ids = [job["job_id"] for job in create_response.json()["jobs"]]

    for _ in range(40):
        statuses = []
        for job_id in job_ids:
            detail = client.get(f"/api/jobs/{job_id}")
            statuses.append(detail.json()["job"]["status"])
        if all(status == "completed" for status in statuses):
            break
        time.sleep(0.05)

    export_response = client.post("/api/jobs/export", json={"job_ids": job_ids})

    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("application/zip")
    assert "attachment" in export_response.headers.get("content-disposition", "").lower()

    with ZipFile(io.BytesIO(export_response.content)) as archive:
        names = archive.namelist()

    assert "manifest.json" in names
    assert any(name.endswith("/artifacts/quickread.md") for name in names)
    assert any(name.endswith("/artifacts/transcript.txt") for name in names)


def test_web_job_continue_from_summarize(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    def fake_run(options, event_callback=None):
        if not options.resume_stage:
            workdir = settings.data_dir / "continue-demo"
            if event_callback:
                event_callback("prepare", "创建工作目录", {"workdir": str(workdir)})
            artifacts_dir = workdir / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            media_path = workdir / "media" / "demo.mp4"
            media_path.parent.mkdir(parents=True, exist_ok=True)
            media_path.write_text("video", encoding="utf-8")
            save_run_state(
                workdir,
                {
                    "source": options.source,
                    "platform": "douyin",
                    "title": "continue-demo",
                    "workdir": str(workdir),
                    "media_path": str(media_path),
                    "transcript": {
                        "text": "已有逐字稿",
                        "acquisition_method": "Internal Whisper base",
                        "media_path": str(media_path),
                        "audio_path": None,
                    },
                    "last_completed_stage": "title",
                },
            )
            raise RuntimeError("summary failed")
        assert options.resume_stage == "summarize"
        assert options.resume_workdir == settings.data_dir / "continue-demo"
        workdir = options.resume_workdir
        if event_callback:
            event_callback("prepare", "加载断点工作目录", {"workdir": str(workdir)})
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text("ok", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source=options.source, platform="douyin", title="continue-demo"),
            transcript=TranscriptResult(text="已有逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)

    create_response = client.post(
        "/api/jobs",
        data={"source_url": "https://example.com/demo", "project_name": "continue-demo", "platform": "douyin"},
    )
    assert create_response.status_code == 200
    failed_job_id = create_response.json()["job"]["job_id"]

    failed_job = None
    for _ in range(40):
        detail = client.get(f"/api/jobs/{failed_job_id}")
        failed_job = detail.json()["job"]
        if failed_job["status"] == "failed":
            break
        time.sleep(0.05)

    assert failed_job is not None
    assert failed_job["status"] == "failed"
    assert failed_job["can_continue"] is True
    assert "summarize" in failed_job["available_resume_stages"]

    continue_response = client.post(
        f"/api/jobs/{failed_job_id}/continue",
        data={"resume_stage": "summarize"},
    )
    assert continue_response.status_code == 200
    resumed_job_id = continue_response.json()["job"]["job_id"]
    assert resumed_job_id != failed_job_id

    resumed_job = None
    for _ in range(40):
        detail = client.get(f"/api/jobs/{resumed_job_id}")
        resumed_job = detail.json()["job"]
        if resumed_job["status"] == "completed":
            break
        time.sleep(0.05)

    assert resumed_job is not None
    assert resumed_job["status"] == "completed"


def test_web_job_exposes_failure_chain(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    def fake_run(_options, event_callback=None):
        if event_callback:
            event_callback("subtitle_failed", "字幕提取失败", {"error": "subtitle broken"})
            event_callback("transcription_fallback", "改走转录")
        workdir = settings.data_dir / "failure-chain-demo"
        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        bundle = ArtifactBundle(
            workdir=workdir,
            artifacts_dir=artifacts_dir,
            quickread_markdown=artifacts_dir / "quickread.md",
            transcript_text=artifacts_dir / "transcript.txt",
            summary_markdown=artifacts_dir / "summary.md",
            summary_json=artifacts_dir / "summary.json",
            metadata_json=artifacts_dir / "metadata.json",
        )
        for path in [
            bundle.quickread_markdown,
            bundle.transcript_text,
            bundle.summary_markdown,
            bundle.summary_json,
            bundle.metadata_json,
        ]:
            path.write_text("ok", encoding="utf-8")
        return OrchestratorResult(
            source=SourceInfo(raw_source="https://example.com/video", platform="bilibili", title="failure-chain-demo"),
            transcript=TranscriptResult(text="逐字稿", acquisition_method="Internal Whisper base"),
            summary=SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test"),
            artifacts=bundle,
            rendered="rendered",
        )

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)

    create_response = client.post(
        "/api/jobs",
        data={"source_url": "https://example.com/video", "project_name": "failure-chain-demo", "platform": "bilibili"},
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["job"]["job_id"]

    job = None
    for _ in range(40):
        detail = client.get(f"/api/jobs/{job_id}")
        job = detail.json()["job"]
        if job["status"] == "completed":
            break
        time.sleep(0.05)

    assert job is not None
    assert job["failure_chain"]
    assert job["failure_chain"][0]["stage"] == "subtitle_failed"
    assert job["failure_chain"][0]["error"] == "subtitle broken"
    assert job["error_summary"]["has_issues"] is True
    assert job["error_summary"]["items"]


def test_web_job_does_not_classify_sessdata_style_errors(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    _write_config_files(settings)
    monkeypatch.setattr("app.web.load_settings", lambda: settings)

    def fake_run(_options, event_callback=None):
        raise RuntimeError("sessdata expired while downloading")

    monkeypatch.setattr("app.web.run_quickread", fake_run)
    client = TestClient(app)

    create_response = client.post(
        "/api/jobs",
        data={"source_url": "https://www.bilibili.com/video/BV1xx", "platform": "bilibili"},
    )
    assert create_response.status_code == 200
    job_id = create_response.json()["job"]["job_id"]

    job = None
    for _ in range(40):
        detail = client.get(f"/api/jobs/{job_id}")
        job = detail.json()["job"]
        if job["status"] == "failed":
            break
        time.sleep(0.05)

    assert job is not None
    assert job["status"] == "failed"
    assert job["error_code"] is None
    assert job["requires_user_input"] is False
    assert job["can_continue_without_sessdata"] is False
    assert job["user_prompt"] is None
