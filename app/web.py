from __future__ import annotations

import asyncio
import inspect
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

from .config import Settings, load_settings
from .pipeline.orchestrator import OrchestratorResult, run_quickread
from .runtime_factory import build_runtime_options
from .services.bili_auth import (
    BiliQrCodeExpiredError,
    BiliQrCodePending,
    BiliQrCodeWaitingForConfirmation,
    generate_bili_qrcode,
    get_bili_login_status,
    logout_bili,
    poll_bili_qrcode,
)
from .services.bili_cookie_store import save_bili_cookie
from .services.dependency_bootstrap import ensure_opencv_dependency
from .services.diagnostics import build_error_summary, extract_failure_chain
from .services.run_state import (
    available_resume_stages as checkpoint_available_resume_stages,
    load_run_state,
    suggested_resume_stage as checkpoint_suggested_resume_stage,
)
from .subsystems.transcription.store import load_transcription_store
from .subsystems.vision.store import load_vision_store

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]
WHISPER_MODEL_INFO = {
    "tiny": {"size": "~39 MB", "speed": "最快", "accuracy": "较低", "best_for": "快速测试"},
    "base": {"size": "~74 MB", "speed": "快", "accuracy": "一般", "best_for": "日常使用"},
    "small": {"size": "~244 MB", "speed": "中等", "accuracy": "较好", "best_for": "平衡选择"},
    "medium": {"size": "~769 MB", "speed": "较慢", "accuracy": "好", "best_for": "高质量需求"},
    "large": {"size": "~1.5 GB", "speed": "最慢", "accuracy": "最好", "best_for": "专业场景"},
}
TERMINAL_JOB_STATUSES = {"completed", "failed", "cancelled"}

app = FastAPI(title="Vivid Web UI")


@dataclass(slots=True)
class WebJobRecord:
    job_id: str
    status: str
    stage: str
    progress: int
    message: str
    created_at: str
    updated_at: str
    source: str
    request: dict[str, Any]
    project_name: str | None = None
    platform: str | None = None
    title: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    events: list[dict[str, Any]] | None = None
    workdir: str | None = None

    def to_dict(
        self,
        *,
        queue_position: int | None = None,
        can_cancel: bool = False,
        can_retry: bool = False,
        can_continue: bool = False,
        available_resume_stages: list[str] | None = None,
        suggested_resume_stage: str | None = None,
        failure_chain: list[dict[str, Any]] | None = None,
        error_summary: dict[str, Any] | None = None,
        error_code: str | None = None,
        requires_user_input: bool = False,
        user_prompt: str | None = None,
        can_continue_without_sessdata: bool = False,
    ) -> dict[str, Any]:
        payload = asdict(self)
        payload["queue_position"] = queue_position
        payload["can_cancel"] = can_cancel
        payload["can_retry"] = can_retry
        payload["can_continue"] = can_continue
        payload["available_resume_stages"] = available_resume_stages or []
        payload["suggested_resume_stage"] = suggested_resume_stage
        payload["failure_chain"] = failure_chain or []
        payload["error_summary"] = error_summary or {"has_issues": False, "headline": "", "items": []}
        payload["error_code"] = error_code
        payload["requires_user_input"] = requires_user_input
        payload["user_prompt"] = user_prompt
        payload["can_continue_without_sessdata"] = can_continue_without_sessdata
        return payload


class WebJobManager:
    def __init__(self, history_path: Path, max_workers: int = 1) -> None:
        self.history_path = history_path
        self.lock = Lock()
        self.executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix="vivid-web")
        self.records: dict[str, WebJobRecord] = {}
        self.order: list[str] = []
        self._load()

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.lock:
            job_ids = list(reversed(self.order[-limit:]))
            return [self._record_to_dict(self.records[job_id]) for job_id in job_ids if job_id in self.records]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.lock:
            record = self.records.get(job_id)
            return self._record_to_dict(record) if record else None

    def stats(self) -> dict[str, int]:
        with self.lock:
            queued = sum(1 for record in self.records.values() if record.status == "queued")
            running = sum(1 for record in self.records.values() if record.status == "running")
            completed = sum(1 for record in self.records.values() if record.status == "completed")
            failed = sum(1 for record in self.records.values() if record.status == "failed")
            cancelled = sum(1 for record in self.records.values() if record.status == "cancelled")
            return {
                "queued": queued,
                "running": running,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
            }

    def submit(self, settings: Settings, values: dict[str, Any]) -> dict[str, Any]:
        now = _now_iso()
        job_id = uuid4().hex[:12]
        source = str(values.get("source") or "")
        record = WebJobRecord(
            job_id=job_id,
            status="queued",
            stage="queued",
            progress=5,
            message="任务已排队",
            created_at=now,
            updated_at=now,
            source=source,
            request=_public_request(values),
            project_name=_text_or_none(values.get("project_name")),
            workdir=_text_or_none(values.get("resume_workdir")),
            events=[_build_event("queued", "任务已创建并进入队列", {"source": source})],
        )
        with self.lock:
            self.records[job_id] = record
            self.order.append(job_id)
            self._save_locked()
        self.executor.submit(self._run_job, settings, job_id, values)
        with self.lock:
            return self._record_to_dict(self.records[job_id])

    def submit_many(self, settings: Settings, payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.submit(settings, dict(values)) for values in payloads]

    def retry(
        self,
        settings: Settings,
        job_id: str,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            record = self.records.get(job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status not in TERMINAL_JOB_STATUSES:
                raise RuntimeError("job is not in terminal state")
            values = dict(record.request)
        if overrides:
            values.update(overrides)
        source = _text_or_none(values.get("source"))
        if not source:
            raise ValueError("job source is missing")
        source_path = Path(source).expanduser()
        if _looks_like_local_path(source) and not source_path.exists():
            raise FileNotFoundError(f"source not found: {source}")
        return self.submit(settings, values)

    def continue_job(self, settings: Settings, job_id: str, resume_stage: str | None = None) -> dict[str, Any]:
        with self.lock:
            record = self.records.get(job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status not in TERMINAL_JOB_STATUSES:
                raise RuntimeError("job is not in terminal state")
            values = dict(record.request)
            workdir = self._resolve_record_workdir(record)
            resume_details = self._resume_details(record, workdir)
        if not workdir:
            raise ValueError("job workdir is missing")
        workdir_path = Path(workdir).expanduser()
        if not workdir_path.exists():
            raise FileNotFoundError(f"resume workdir not found: {workdir}")
        stage = resume_stage or resume_details["suggested_resume_stage"]
        if not stage:
            raise ValueError("no resumable stage found for this job")
        if stage not in (resume_details["available_resume_stages"] or []):
            raise ValueError(f"resume stage '{stage}' is unavailable for this job")
        values["resume_workdir"] = str(workdir_path)
        values["resume_stage"] = stage
        return self.submit(settings, values)

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            record = self.records.get(job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status != "queued":
                raise RuntimeError("only queued jobs can be cancelled")
            now = _now_iso()
            record.status = "cancelled"
            record.stage = "cancelled"
            record.progress = 0
            record.message = "任务已取消"
            record.updated_at = now
            record.finished_at = now
            if record.events is None:
                record.events = []
            record.events.append(_build_event("cancelled", "任务已从队列取消"))
            self._save_locked()
            return self._record_to_dict(record)

    def delete(self, settings: Settings, job_id: str, delete_files: bool = False) -> dict[str, Any]:
        with self.lock:
            record = self.records.get(job_id)
            if record is None:
                raise KeyError(job_id)
            if record.status == "running":
                raise RuntimeError("running job cannot be deleted")
            self.records.pop(job_id, None)
            self.order = [item for item in self.order if item != job_id]
            self._save_locked()
        if delete_files:
            _delete_job_files(settings, record)
        return record.to_dict()

    def _run_job(self, settings: Settings, job_id: str, values: dict[str, Any]) -> None:
        started_at = _now_iso()
        started_perf = time.perf_counter()
        with self.lock:
            record = self.records.get(job_id)
            if record is None or record.status == "cancelled":
                return
        self._update(
            job_id,
            status="running",
            stage="preparing",
            progress=15,
            message="正在准备执行环境",
            started_at=started_at,
            updated_at=started_at,
        )
        self._append_event(job_id, "preparing", "工作线程已接管任务")
        try:
            options = build_runtime_options(settings, values)
            self._update(
                job_id,
                status="running",
                stage="processing",
                progress=55,
                message="正在采集、转录和总结内容",
                updated_at=_now_iso(),
            )
            result = _invoke_run_quickread(options, self._make_event_callback(job_id))
            finished_at = _now_iso()
            self._update(
                job_id,
                status="completed",
                stage="completed",
                progress=100,
                message="任务完成",
                finished_at=finished_at,
                updated_at=finished_at,
                duration_seconds=round(time.perf_counter() - started_perf, 3),
                platform=result.source.platform,
                title=result.source.title,
                project_name=result.source.title,
                workdir=str(result.artifacts.workdir),
                result=_serialize_result(result),
                error=None,
            )
            self._append_event(job_id, "completed", "任务执行完成")
        except Exception as exc:  # noqa: BLE001
            finished_at = _now_iso()
            self._update(
                job_id,
                status="failed",
                stage="failed",
                progress=100,
                message="任务失败",
                finished_at=finished_at,
                updated_at=finished_at,
                duration_seconds=round(time.perf_counter() - started_perf, 3),
                error=str(exc),
            )
            self._append_event(job_id, "failed", f"任务失败：{exc}")

    def _update(self, job_id: str, **changes: Any) -> None:
        with self.lock:
            record = self.records[job_id]
            for key, value in changes.items():
                setattr(record, key, value)
            self._save_locked()

    def _append_event(self, job_id: str, stage: str, message: str, data: dict[str, Any] | None = None) -> None:
        with self.lock:
            record = self.records[job_id]
            if record.events is None:
                record.events = []
            record.events.append(_build_event(stage, message, data))
            workdir = _text_or_none((data or {}).get("workdir")) if isinstance(data, dict) else None
            if workdir:
                record.workdir = workdir
            record.updated_at = _now_iso()
            record.stage = stage
            progress = _progress_for_stage(stage, record.progress)
            if progress is not None:
                record.progress = progress
            record.message = message
            if len(record.events) > 200:
                record.events = record.events[-200:]
            self._save_locked()

    def _make_event_callback(self, job_id: str):
        def callback(stage: str, message: str, data: dict[str, Any] | None = None) -> None:
            self._append_event(job_id, stage, message, data)

        return callback

    def _record_to_dict(self, record: WebJobRecord) -> dict[str, Any]:
        queue_position = self._queue_position_locked(record.job_id)
        workdir = self._resolve_record_workdir(record)
        resume_details = self._resume_details(record, workdir)
        error_code = _extract_job_error_code(record.events, record.error)
        return record.to_dict(
            queue_position=queue_position,
            can_cancel=record.status == "queued",
            can_retry=record.status in TERMINAL_JOB_STATUSES,
            can_continue=resume_details["can_continue"],
            available_resume_stages=resume_details["available_resume_stages"],
            suggested_resume_stage=resume_details["suggested_resume_stage"],
            failure_chain=extract_failure_chain(record.events),
            error_summary=build_error_summary(record.events),
            error_code=error_code,
            requires_user_input=False,
            user_prompt=None,
            can_continue_without_sessdata=False,
        )

    def _resolve_record_workdir(self, record: WebJobRecord) -> str | None:
        if record.workdir:
            return record.workdir
        if record.result:
            files = record.result.get("files") or {}
            return _text_or_none(files.get("workdir"))
        return None

    def _resume_details(self, record: WebJobRecord, workdir: str | None) -> dict[str, Any]:
        if record.status not in TERMINAL_JOB_STATUSES or not workdir:
            return {"can_continue": False, "available_resume_stages": [], "suggested_resume_stage": None}
        checkpoint = load_run_state(Path(workdir).expanduser())
        if not checkpoint:
            return {"can_continue": False, "available_resume_stages": [], "suggested_resume_stage": None}
        stages = checkpoint_available_resume_stages(checkpoint)
        suggested = checkpoint_suggested_resume_stage(checkpoint, record.stage)
        return {
            "can_continue": bool(stages),
            "available_resume_stages": stages,
            "suggested_resume_stage": suggested,
        }

    def _queue_position_locked(self, job_id: str) -> int | None:
        queued_job_ids = [item for item in self.order if self.records.get(item) and self.records[item].status == "queued"]
        if job_id not in queued_job_ids:
            return None
        return queued_job_ids.index(job_id) + 1

    def _load(self) -> None:
        if not self.history_path.exists():
            return
        try:
            payload = json.loads(self.history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                record = WebJobRecord(
                    job_id=str(item["job_id"]),
                    status=str(item.get("status", "unknown")),
                    stage=str(item.get("stage", item.get("status", "unknown"))),
                    progress=int(item.get("progress", 100 if item.get("status") in TERMINAL_JOB_STATUSES else 0)),
                    message=str(item.get("message", "")),
                    created_at=str(item.get("created_at", "")),
                    updated_at=str(item.get("updated_at", "")),
                    source=str(item.get("source", "")),
                    request=dict(item.get("request", {})),
                    project_name=_text_or_none(item.get("project_name")),
                    platform=_text_or_none(item.get("platform")),
                    title=_text_or_none(item.get("title")),
                    started_at=_text_or_none(item.get("started_at")),
                    finished_at=_text_or_none(item.get("finished_at")),
                    duration_seconds=item.get("duration_seconds"),
                    error=_text_or_none(item.get("error")),
                    result=item.get("result"),
                    events=list(item.get("events", []) or []),
                    workdir=_text_or_none(item.get("workdir")),
                )
            except KeyError:
                continue
            self.records[record.job_id] = record
            self.order.append(record.job_id)

    def _save_locked(self) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        data = [self.records[job_id].to_dict() for job_id in self.order if job_id in self.records]
        self.history_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


_JOB_MANAGERS: dict[str, WebJobManager] = {}
_JOB_MANAGERS_LOCK = Lock()


def get_job_manager(settings: Settings) -> WebJobManager:
    history_path = (settings.data_dir / "web_ui" / "jobs.json").resolve()
    key = str(history_path)
    with _JOB_MANAGERS_LOCK:
        manager = _JOB_MANAGERS.get(key)
        if manager is None:
            manager = WebJobManager(history_path, max_workers=settings.web_max_workers)
            _JOB_MANAGERS[key] = manager
        return manager


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _render_index()


@app.get("/api/health")
async def health() -> dict[str, Any]:
    settings = load_settings()
    return {
        "ok": True,
        "data_dir": str(settings.data_dir),
        "web_history": str(settings.data_dir / "web_ui" / "jobs.json"),
    }


@app.get("/api/bootstrap")
async def bootstrap() -> dict[str, Any]:
    settings = load_settings()
    manager = get_job_manager(settings)
    preferred_output_dir = load_preferred_output_dir(settings)
    preferred_vision_openai = load_preferred_vision_openai(settings)
    dependency_status = ensure_opencv_dependency(raise_on_failure=False)
    return {
        "ok": True,
        "defaults": _settings_defaults(settings, preferred_output_dir, preferred_vision_openai),
        "options": _options_payload(settings),
        "dependencies": {"opencv": dependency_status},
        "stats": manager.stats(),
        "jobs": manager.list_jobs(limit=20),
    }


@app.get("/api/jobs")
async def list_jobs(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    settings = load_settings()
    manager = get_job_manager(settings)
    return {"ok": True, "jobs": manager.list_jobs(limit=limit)}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    settings = load_settings()
    manager = get_job_manager(settings)
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"ok": True, "job": job}


@app.get("/api/jobs/{job_id}/events")
async def stream_job_events(job_id: str) -> StreamingResponse:
    settings = load_settings()
    manager = get_job_manager(settings)
    job = manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def event_stream():
        previous_signature = None
        while True:
            current = manager.get_job(job_id)
            if current is None:
                yield _format_sse("deleted", {"ok": False, "job_id": job_id})
                break
            signature = _job_signature(current)
            if signature != previous_signature:
                yield _format_sse("job", {"ok": True, "job": current})
                previous_signature = signature
            if current["status"] in TERMINAL_JOB_STATUSES:
                break
            await asyncio.sleep(0.4)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: str, request: Request) -> dict[str, Any]:
    settings = load_settings()
    manager = get_job_manager(settings)
    try:
        job = manager.retry(settings, job_id, overrides=await _collect_retry_overrides(request, settings))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "job": job}


@app.post("/api/jobs/{job_id}/continue")
async def continue_job(job_id: str, request: Request) -> dict[str, Any]:
    settings = load_settings()
    manager = get_job_manager(settings)
    form = await request.form()
    resume_stage = _clean_form_value(form.get("resume_stage"))
    try:
        job = manager.continue_job(settings, job_id, resume_stage)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "job": job}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict[str, Any]:
    settings = load_settings()
    manager = get_job_manager(settings)
    try:
        job = manager.cancel(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "job": job}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str, delete_files: bool = Query(False)) -> dict[str, Any]:
    settings = load_settings()
    manager = get_job_manager(settings)
    try:
        job = manager.delete(settings, job_id, delete_files=delete_files)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"ok": True, "job": job}


@app.post("/api/jobs")
async def create_job(request: Request) -> dict[str, Any]:
    settings = load_settings()
    payloads = await _collect_request_payloads(request, settings)
    manager = get_job_manager(settings)
    jobs = manager.submit_many(settings, payloads)
    return {
        "ok": True,
        "job": jobs[0],
        "jobs": jobs,
        "batch": {"count": len(jobs)},
    }


@app.post("/api/jobs/export")
async def export_jobs(request: Request) -> FileResponse:
    settings = load_settings()
    manager = get_job_manager(settings)
    job_ids = await _collect_export_job_ids(request)
    if not job_ids:
        raise HTTPException(status_code=400, detail="job_ids is required")
    try:
        archive_path = build_jobs_export_archive(settings, manager, job_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=archive_path.name,
    )


@app.post("/api/quickread")
async def quickread(request: Request) -> JSONResponse:
    settings = load_settings()
    payloads = await _collect_request_payloads(request, settings)
    if len(payloads) != 1:
        raise HTTPException(status_code=400, detail="quickread endpoint does not support batch sources")
    values = payloads[0]
    temp_upload_path = _text_or_none(values.get("_temp_upload_path"))
    try:
        options = build_runtime_options(settings, values)
        result = run_quickread(options)
        payload = {"ok": True, **_serialize_result(result)}
        return JSONResponse(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    finally:
        if temp_upload_path:
            _delete_file_quietly(Path(temp_upload_path))


@app.post("/api/bilibili/auth/qrcode")
async def bilibili_auth_qrcode() -> dict[str, Any]:
    qrcode = generate_bili_qrcode()
    return {"ok": True, "qrcode": qrcode.to_public_dict()}


@app.get("/api/bilibili/auth/poll")
async def bilibili_auth_poll(qrcode_key: str = Query(...)) -> dict[str, Any]:
    settings = load_settings()
    try:
        result = poll_bili_qrcode(settings.repo_root, qrcode_key)
    except BiliQrCodePending as exc:
        return {"ok": False, "status": "waiting_for_scan", "message": str(exc)}
    except BiliQrCodeWaitingForConfirmation as exc:
        return {"ok": False, "status": "waiting_for_confirmation", "message": str(exc)}
    except BiliQrCodeExpiredError as exc:
        return {"ok": False, "status": "expired", "message": str(exc)}
    return {"ok": True, **result.to_public_dict()}


@app.get("/api/bilibili/auth/status")
async def bilibili_auth_status() -> dict[str, Any]:
    settings = load_settings()
    status = get_bili_login_status(settings.repo_root)
    return {"ok": True, "status": status.to_public_dict()}


@app.post("/api/bilibili/auth/logout")
async def bilibili_auth_logout() -> dict[str, Any]:
    settings = load_settings()
    result = logout_bili(settings.repo_root)
    payload = result.to_public_dict()
    return {"ok": bool(payload.get("ok")), "logout": payload}


@app.get("/files")
async def download_file(path: str) -> FileResponse:
    settings = load_settings()
    file_path = Path(path).expanduser().resolve()
    data_root = settings.data_dir.resolve()
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    try:
        file_path.relative_to(data_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="forbidden path") from exc
    return FileResponse(file_path)


@app.post("/api/open-folder")
async def open_folder(path: str) -> dict[str, Any]:
    settings = load_settings()
    folder_path = Path(path).expanduser().resolve()
    data_root = settings.data_dir.resolve()
    if folder_path.is_file():
        folder_path = folder_path.parent
    if not folder_path.is_dir():
        raise HTTPException(status_code=404, detail="folder not found")
    try:
        folder_path.relative_to(data_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="forbidden path") from exc
    command = build_open_folder_command(folder_path)
    if not command:
        raise HTTPException(status_code=500, detail="no supported folder opener found on this platform")
    subprocess.Popen(command)
    return {"ok": True, "path": str(folder_path)}


@app.post("/api/preferences/output-dir")
async def set_default_output_dir(request: Request) -> dict[str, Any]:
    settings = load_settings()
    form = await request.form()
    path_text = _clean_form_value(form.get("data_dir"))
    if not path_text:
        raise HTTPException(status_code=400, detail="data_dir is required")
    try:
        path = ensure_output_dir(Path(path_text).expanduser())
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_preferred_output_dir(settings, path)
    return {"ok": True, "data_dir": str(path)}


@app.post("/api/preferences/vision-openai")
async def set_default_vision_openai(request: Request) -> dict[str, Any]:
    settings = load_settings()
    form = await request.form()
    payload = {
        "vision_api_base": _clean_form_value(form.get("vision_api_base")),
        "vision_api_path": _clean_form_value(form.get("vision_api_path")) or "/v1/chat/completions",
        "vision_api_key": _clean_form_value(form.get("vision_api_key")),
        "vision_model": _clean_form_value(form.get("vision_model")),
        "vision_prompt": _clean_form_value(form.get("vision_prompt")),
        "vision_system_prompt": _clean_form_value(form.get("vision_system_prompt")),
        "vision_timeout": _clean_form_value(form.get("vision_timeout")),
    }
    if not payload["vision_api_base"]:
        raise HTTPException(status_code=400, detail="vision_api_base is required")
    save_preferred_vision_openai(settings, payload)
    return {"ok": True, **payload}


async def _collect_request_values(request: Request, settings: Settings) -> dict[str, Any]:
    payloads = await _collect_request_payloads(request, settings)
    if len(payloads) != 1:
        raise HTTPException(status_code=400, detail="multiple sources are not supported here")
    return payloads[0]


async def _collect_request_payloads(request: Request, settings: Settings) -> list[dict[str, Any]]:
    form = await request.form()
    values = _collect_base_request_values(form, settings)
    sources = _collect_sources_from_form(form)
    upload = form.get("media_file")
    if _is_upload(upload):
        if sources:
            raise HTTPException(status_code=400, detail="uploaded file cannot be combined with source URLs")
        upload_path = await _save_upload_file(settings, upload)
        values["source"] = str(upload_path)
        values["_temp_upload_path"] = str(upload_path)
        return [values]
    if not sources:
        raise HTTPException(status_code=400, detail="source is required")
    return [{**values, "source": source} for source in sources]


def _collect_base_request_values(form: Any, settings: Settings) -> dict[str, Any]:
    preferred_output_dir = load_preferred_output_dir(settings)
    preferred_vision_openai = load_preferred_vision_openai(settings)
    bili_cookie = _clean_form_value(form.get("bili_cookie"))
    _persist_bili_cookie_if_present(settings.repo_root, bili_cookie, source="web")
    values = {
        "project_name": _clean_form_value(form.get("project_name")),
        "data_dir": _clean_form_value(form.get("data_dir")) or str(preferred_output_dir or settings.data_dir),
        "bili_cookie": bili_cookie,
        "output_format": _clean_form_value(form.get("output_format")),
        "whisper_model": _clean_form_value(form.get("whisper_model")),
        "forced_platform": _clean_form_value(form.get("platform")),
        "language": _clean_form_value(form.get("language")),
        "transcription_preset_id": _clean_form_value(form.get("transcription_preset_id")),
        "acquisition_mode": _clean_form_value(form.get("acquisition_mode")),
        "transcription_backend": _clean_form_value(form.get("transcription_backend")),
        "vision_backend": _clean_form_value(form.get("vision_backend")),
        "vision_api_config_id": _clean_form_value(form.get("vision_api_config_id")),
        "vision_prompt_id": _clean_form_value(form.get("vision_prompt_id")),
        "vision_api_base": _clean_form_value(form.get("vision_api_base")) or preferred_vision_openai.get("vision_api_base"),
        "vision_api_path": _clean_form_value(form.get("vision_api_path")) or preferred_vision_openai.get("vision_api_path"),
        "vision_api_key": _clean_form_value(form.get("vision_api_key")) or preferred_vision_openai.get("vision_api_key"),
        "vision_model": _clean_form_value(form.get("vision_model")) or preferred_vision_openai.get("vision_model"),
        "vision_prompt": _clean_form_value(form.get("vision_prompt")) or preferred_vision_openai.get("vision_prompt"),
        "vision_system_prompt": _clean_form_value(form.get("vision_system_prompt")) or preferred_vision_openai.get("vision_system_prompt"),
        "transcribe_timeout": _clean_form_value(form.get("transcribe_timeout")),
        "ocr_timeout": _clean_form_value(form.get("ocr_timeout")),
        "vision_timeout": _clean_form_value(form.get("vision_timeout")) or preferred_vision_openai.get("vision_timeout"),
        "vision_sample_ms": _clean_form_value(form.get("vision_sample_ms")),
        "vision_min_duration_ms": _clean_form_value(form.get("vision_min_duration_ms")),
        "prefer_ocr": _bool_value(form.get("prefer_ocr")),
        "force_ocr": _bool_value(form.get("force_ocr")),
        "no_keep_files": _checkbox_to_no_keep_files(form),
    }
    sessdata = _clean_form_value(form.get("sessdata"))
    if sessdata:
        values["sessdata"] = sessdata
    return values


async def _collect_retry_overrides(request: Request, settings: Settings | None = None) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    payload: Any
    if "application/json" in content_type:
        payload = await request.json()
    else:
        payload = await request.form()
    if not isinstance(payload, dict) and not hasattr(payload, "get"):
        return {}
    overrides: dict[str, Any] = {}
    bili_cookie = _clean_form_value(payload.get("bili_cookie"))
    if bili_cookie:
        overrides["bili_cookie"] = bili_cookie
        if settings is not None:
            _persist_bili_cookie_if_present(settings.repo_root, bili_cookie, source="web-retry")
    sessdata = _clean_form_value(payload.get("sessdata"))
    if sessdata:
        overrides["sessdata"] = sessdata
    if _bool_value(payload.get("no_sessdata")):
        overrides["no_sessdata"] = True
    return overrides


def _persist_bili_cookie_if_present(repo_root: Path, bili_cookie: str | None, *, source: str) -> None:
    if not bili_cookie:
        return
    try:
        save_bili_cookie(repo_root, bili_cookie, source=source)
    except (OSError, ValueError):
        return


def _collect_sources_from_form(form: Any) -> list[str]:
    candidates = [
        form.get("source"),
        form.get("source_url"),
        form.get("source_urls"),
    ]
    sources: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = _clean_form_value(candidate)
        if not text:
            continue
        for item in text.splitlines():
            source = item.strip()
            if not source or source in seen:
                continue
            seen.add(source)
            sources.append(source)
    return sources


async def _save_upload_file(settings: Settings, upload: UploadFile) -> Path:
    uploads_root = settings.data_dir / "web_ui" / "uploads"
    uploads_root.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(upload.filename or "upload.bin")
    target = uploads_root / f"{uuid4().hex[:12]}-{filename}"
    with target.open("wb") as stream:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            stream.write(chunk)
    await upload.close()
    return target


def _settings_defaults(
    settings: Settings,
    preferred_output_dir: Path | None = None,
    preferred_vision_openai: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preferred_vision_openai = preferred_vision_openai or {}
    vision_store = load_vision_store(settings.vision_api_configs_path, settings.vision_prompts_path)
    selected_config = vision_store.get_api_config(settings.vision_api_config_id)
    selected_prompt = vision_store.get_prompt(settings.vision_prompt_id)
    return {
        "data_dir": str(preferred_output_dir or settings.data_dir),
        "output_format": settings.default_format,
        "whisper_model": settings.default_model,
        "language": settings.language,
        "acquisition_mode": settings.acquisition_mode,
        "transcription_backend": settings.transcription_backend,
        "transcription_preset_id": settings.transcription_preset_id,
        "vision_backend": settings.vision_backend,
        "vision_api_config_id": settings.vision_api_config_id,
        "vision_prompt_id": settings.vision_prompt_id,
        "vision_api_base": preferred_vision_openai.get("vision_api_base") or (selected_config.api_base if selected_config else settings.vision_api_base),
        "vision_api_path": preferred_vision_openai.get("vision_api_path") or (selected_config.api_path if selected_config else settings.vision_api_path) or "/v1/chat/completions",
        "vision_api_key": preferred_vision_openai.get("vision_api_key") or settings.vision_api_key,
        "vision_model": preferred_vision_openai.get("vision_model") or (selected_config.model if selected_config else settings.vision_model),
        "transcribe_timeout": settings.transcribe_timeout,
        "ocr_timeout": settings.ocr_timeout,
        "vision_timeout": preferred_vision_openai.get("vision_timeout") or (selected_config.timeout if selected_config else settings.vision_timeout),
        "vision_prompt": preferred_vision_openai.get("vision_prompt") or (selected_prompt.content if selected_prompt else None) or (selected_config.prompt if selected_config else settings.vision_prompt),
        "vision_system_prompt": preferred_vision_openai.get("vision_system_prompt") or (selected_config.system_prompt if selected_config else settings.vision_system_prompt),
        "vision_sample_ms": settings.vision_sample_ms,
        "vision_min_duration_ms": settings.vision_min_duration_ms,
        "keep_files": True,
    }


def _options_payload(settings: Settings) -> dict[str, Any]:
    vision_store = load_vision_store(settings.vision_api_configs_path, settings.vision_prompts_path)
    transcription_store = load_transcription_store(settings.transcription_presets_path)
    return {
        "whisper_models": WHISPER_MODELS,
        "whisper_model_info": WHISPER_MODEL_INFO,
        "platforms": ["", "local", "douyin", "bilibili", "youtube", "generic"],
        "output_formats": ["transcript", "summary", "both"],
        "acquisition_modes": ["auto", "smart", "prefer_ocr", "force_ocr"],
        "transcription_backends": ["auto", "internal", "ears4_api"],
        "vision_backends": ["auto", "internal", "eyes_api"],
        "vision_api_configs": vision_store.to_api_payload(),
        "vision_prompts": vision_store.to_prompt_payload(),
        "transcription_presets": transcription_store.to_payload(),
    }


def _serialize_result(result: OrchestratorResult) -> dict[str, Any]:
    payload = result.to_dict()
    payload["files"] = {
        "workdir": str(result.artifacts.workdir),
        "artifacts_dir": str(result.artifacts.artifacts_dir),
        "quickread_markdown": str(result.artifacts.quickread_markdown),
        "transcript_text": str(result.artifacts.transcript_text),
        "vector_source_dir": str(result.artifacts.vector_source_dir) if result.artifacts.vector_source_dir else None,
        "vector_document_json": str(result.artifacts.vector_document_json) if result.artifacts.vector_document_json else None,
        "vector_chunks_jsonl": str(result.artifacts.vector_chunks_jsonl) if result.artifacts.vector_chunks_jsonl else None,
        "vector_manifest_json": str(result.artifacts.vector_manifest_json) if result.artifacts.vector_manifest_json else None,
        "summary_markdown": str(result.artifacts.summary_markdown),
        "summary_json": str(result.artifacts.summary_json),
        "metadata_json": str(result.artifacts.metadata_json),
        "checkpoint_json": str(result.artifacts.checkpoint_json) if result.artifacts.checkpoint_json else None,
        "calibrated_cn_markdown": str(result.artifacts.calibrated_cn_markdown) if result.artifacts.calibrated_cn_markdown else None,
        "calibrated_en_markdown": str(result.artifacts.calibrated_en_markdown) if result.artifacts.calibrated_en_markdown else None,
    }
    payload["diagnostics"] = result.diagnostics
    payload["failure_chain"] = extract_failure_chain(result.diagnostics)
    payload["error_summary"] = build_error_summary(result.diagnostics)
    return payload


def _public_request(values: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "source",
        "data_dir",
        "project_name",
        "output_format",
        "whisper_model",
        "forced_platform",
        "language",
        "transcription_preset_id",
        "acquisition_mode",
        "transcription_backend",
        "vision_backend",
        "vision_api_config_id",
        "vision_prompt_id",
        "transcribe_timeout",
        "ocr_timeout",
        "vision_timeout",
        "vision_sample_ms",
        "vision_min_duration_ms",
        "prefer_ocr",
        "force_ocr",
        "no_keep_files",
    ]
    return {key: values.get(key) for key in keys if values.get(key) not in {None, ""}}


def _render_index() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vivid Web UI</title>
  <style>
    :root { color-scheme: dark; --bg:#111827; --panel:#1f2937; --muted:#94a3b8; --line:#334155; --text:#e5e7eb; --accent:#38bdf8; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }
    .page { padding:20px; display:grid; grid-template-columns:420px 1fr 360px; gap:16px; min-height:100vh; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; overflow:auto; }
    h1,h2,h3 { margin:0 0 12px; }
    .muted { color:var(--muted); font-size:13px; }
    form { display:grid; gap:12px; }
    label { display:grid; gap:6px; font-size:13px; }
    input,select,textarea,button { width:100%; border-radius:10px; border:1px solid var(--line); background:#0f172a; color:var(--text); padding:10px 12px; }
    button { cursor:pointer; background:#0ea5e9; border:none; font-weight:600; }
    button.secondary { background:#334155; }
    .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .dropzone { border:1px dashed #64748b; border-radius:12px; padding:16px; text-align:center; background:#0b1220; }
    .dropzone.dragover { border-color:var(--accent); background:#0c1a2b; }
    .row { display:flex; align-items:center; justify-content:space-between; gap:8px; }
    .status { display:inline-flex; border-radius:999px; padding:4px 10px; font-size:12px; font-weight:700; }
    .status.queued { background:rgba(245,158,11,.15); color:var(--warn); }
    .status.running { background:rgba(56,189,248,.15); color:var(--accent); }
    .status.completed { background:rgba(34,197,94,.15); color:var(--ok); }
    .status.failed { background:rgba(239,68,68,.15); color:var(--bad); }
    .status.cancelled { background:rgba(148,163,184,.15); color:var(--muted); }
    .list { display:grid; gap:10px; }
    .job-card { border:1px solid var(--line); border-radius:12px; padding:12px; background:#0f172a; cursor:pointer; }
    .job-card.active { border-color:var(--accent); }
    .job-card.disabled { opacity:.7; }
    .pre { white-space:pre-wrap; word-break:break-word; border:1px solid var(--line); border-radius:10px; padding:12px; background:#0b1220; }
    .links { display:flex; flex-wrap:wrap; gap:8px; }
    .links a { color:var(--accent); text-decoration:none; }
    .hint { font-size:12px; color:var(--muted); }
    .toolbar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:10px 0; }
    .toolbar button { width:auto; padding:8px 12px; }
    .check { width:auto; margin:0; }
    .auth-panel { border:1px solid var(--line); border-radius:12px; padding:12px; background:#0b1220; display:grid; gap:10px; }
    .auth-actions { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
    .qrcode { width:100%; min-height:160px; display:grid; place-items:center; border:1px solid var(--line); border-radius:10px; background:#fff; color:#0f172a; overflow:hidden; }
    .qrcode svg { width:150px; height:150px; }
    .stats { display:grid; grid-template-columns:repeat(5,1fr); gap:8px; margin-bottom:12px; }
    .stat { border:1px solid var(--line); border-radius:10px; padding:10px; background:#0f172a; }
    .stat strong { display:block; font-size:18px; }
    .progress { width:100%; height:10px; background:#0b1220; border:1px solid var(--line); border-radius:999px; overflow:hidden; }
    .progress > span { display:block; height:100%; background:linear-gradient(90deg,#38bdf8,#22c55e); }
    .events { display:grid; gap:8px; max-height:280px; overflow:auto; }
    .event { border:1px solid var(--line); border-radius:10px; padding:10px; background:#0f172a; }
    .event .row { align-items:flex-start; }
    @media (max-width: 1400px) { .page { grid-template-columns:380px 1fr; } .history { grid-column:1 / -1; } }
    @media (max-width: 980px) { .page { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <div class="page">
    <section class="panel">
      <h1>Vivid Web UI</h1>
      <p class="muted">支持链接和本地拖拽文件，提交后后台执行，结果保留到历史。</p>
      <form id="quickread-form">
        <label>视频链接
          <input name="source_url" placeholder="https://..." />
        </label>
        <label>批量 URL
          <textarea name="source_urls" placeholder="每行一个链接。批量模式下，同一套配置会应用到所有任务。"></textarea>
        </label>
        <div id="dropzone" class="dropzone">
          <div>拖入本地视频/音频文件，或点击选择</div>
          <div id="file-name" class="hint">未选择文件</div>
          <input id="media-file" name="media_file" type="file" accept="video/*,audio/*" style="margin-top:10px;" />
        </div>
        <div class="grid2">
          <label>输出目录
            <input name="data_dir" placeholder="./data" />
          </label>
          <label>默认输出目录
            <button id="save-output-dir-btn" class="secondary" type="button">设为默认输出目录</button>
          </label>
        </div>
        <div class="grid2">
          <label>项目名<input name="project_name" placeholder="可选" /></label>
          <label>平台<select name="platform"></select></label>
        </div>
        <div class="grid2">
          <label>Whisper 模型<select name="whisper_model"></select></label>
          <label>输出格式<select name="output_format"></select></label>
        </div>
        <div id="whisper-model-info" class="hint" style="margin-top: -10px; margin-bottom: 10px; color: #666;"></div>
        <div class="grid2">
          <label>采集策略<select name="acquisition_mode"></select></label>
          <label>转录预设<select name="transcription_preset_id"></select></label>
        </div>
        <div class="grid2">
          <label>转录后端<select name="transcription_backend"></select></label>
          <label>OCR 后端<select name="vision_backend"></select></label>
        </div>
        <div class="grid2">
          <label>OCR 配置<select name="vision_api_config_id"></select></label>
          <label>OCR Prompt<select name="vision_prompt_id"></select></label>
        </div>
        <div class="grid2">
          <label>OCR API Base
            <input name="vision_api_base" placeholder="https://api.example.com" />
          </label>
          <label>OCR API Path
            <input name="vision_api_path" placeholder="/v1/chat/completions" />
          </label>
        </div>
        <div class="grid2">
          <label>OCR API Key
            <input name="vision_api_key" placeholder="sk-..." />
          </label>
          <label>OCR 模型
            <input name="vision_model" placeholder="Qwen/Qwen2.5-VL-7B-Instruct" />
          </label>
        </div>
        <label>OCR Prompt
          <textarea name="vision_prompt" placeholder="只返回画面中的可读字幕文本。"></textarea>
        </label>
        <label>OCR System Prompt
          <textarea name="vision_system_prompt" placeholder="可选"></textarea>
        </label>
        <label>Bilibili Cookie
          <textarea name="bili_cookie" rows="3" placeholder="SESSDATA=...; bili_jct=..."></textarea>
        </label>
        <label>兼容 SESSDATA（可选）
          <input name="sessdata" placeholder="只填 SESSDATA 值；完整 Cookie 优先" />
        </label>
        <div class="auth-panel">
          <div class="row">
            <strong>扫码登录 Bilibili</strong>
            <span id="bili-auth-status" class="status queued">未检测</span>
          </div>
          <div id="bili-qrcode" class="qrcode"><span class="muted">生成后用 Bilibili App 扫码</span></div>
          <div class="auth-actions">
            <button id="bili-qrcode-btn" class="secondary" type="button">生成二维码</button>
            <button id="bili-status-btn" class="secondary" type="button">校验登录态</button>
            <button id="bili-logout-btn" class="secondary" type="button">注销清除</button>
            <button id="bili-clear-qr-btn" class="secondary" type="button">清空二维码</button>
          </div>
          <div id="bili-auth-message" class="hint"></div>
        </div>
        <div class="grid2">
          <div class="hint">OCR API 按 OpenAI 兼容格式配置：`base + path + api_key + model`。</div>
          <button id="save-vision-openai-btn" class="secondary" type="button">设为默认 OCR API 配置</button>
        </div>
        <div class="grid2">
          <label>语言<input name="language" placeholder="zh" /></label>
          <label>保留中间文件<select name="keep_files"><option value="true">保留</option><option value="false">清理</option></select></label>
        </div>
        <div class="grid2">
          <label>转录超时（秒）<input name="transcribe_timeout" type="number" min="1" /></label>
          <label>OCR 超时（秒）<input name="ocr_timeout" type="number" min="1" /></label>
        </div>
        <div class="grid2">
          <label>Vision 超时（秒）<input name="vision_timeout" type="number" min="1" /></label>
          <label>采样间隔（毫秒）<input name="vision_sample_ms" type="number" min="1" /></label>
        </div>
        <label>最小时长（毫秒）<input name="vision_min_duration_ms" type="number" min="1" /></label>
        <div class="grid2">
          <button type="submit">提交任务</button>
          <button id="refresh-btn" class="secondary" type="button">刷新历史</button>
        </div>
      </form>
      <p id="form-message" class="hint"></p>
    </section>
    <section class="panel">
      <div class="row">
        <h2>任务详情</h2>
        <span id="job-status" class="status queued">未选择</span>
      </div>
      <div id="job-progress" class="progress" style="margin:12px 0;"><span style="width:0%"></span></div>
      <div id="job-detail" class="list">
        <div class="muted">提交后这里会显示状态、摘要、逐字稿和产物下载。</div>
      </div>
      <h3 style="margin-top:14px;">任务日志</h3>
      <div id="job-events" class="events">
        <div class="muted">任务开始后会持续追加下载、转录、OCR、总结等事件。</div>
      </div>
    </section>
    <section class="panel history">
      <div class="row">
        <h2>历史任务</h2>
        <span id="history-count" class="muted">0 条</span>
      </div>
      <div id="history-stats" class="stats"></div>
      <input id="history-filter" placeholder="按标题、来源或状态过滤" style="margin-bottom:10px;" />
      <div class="toolbar">
        <span id="selection-count" class="hint">已选 0 条</span>
        <button id="select-visible-btn" class="secondary" type="button">选中当前筛选</button>
        <button id="clear-selection-btn" class="secondary" type="button">清空选择</button>
        <button id="export-selected-btn" class="secondary" type="button">导出选中任务</button>
      </div>
      <div id="job-history" class="list"></div>
    </section>
  </div>
  <script>
    const state = { bootstrap: null, activeJobId: null, pollTimer: null, eventSource: null, file: null, jobs: [], selectedJobIds: new Set(), biliQrCodeKey: null, biliAuthTimer: null };
    const storageKey = "vivid-web-ui-form";
    document.addEventListener("DOMContentLoaded", async () => {
      bindDropzone();
      document.getElementById("quickread-form").addEventListener("submit", submitJob);
      document.getElementById("refresh-btn").addEventListener("click", refreshHistory);
      document.getElementById("save-output-dir-btn").addEventListener("click", saveDefaultOutputDir);
      document.getElementById("save-vision-openai-btn").addEventListener("click", saveDefaultVisionOpenAi);
      document.getElementById("media-file").addEventListener("change", onFilePicked);
      document.getElementById("history-filter").addEventListener("input", () => renderHistory(state.jobs));
      document.getElementById("select-visible-btn").addEventListener("click", selectVisibleJobs);
      document.getElementById("clear-selection-btn").addEventListener("click", clearSelectedJobs);
      document.getElementById("export-selected-btn").addEventListener("click", exportSelectedJobs);
      document.getElementById("bili-qrcode-btn").addEventListener("click", createBiliQrCode);
      document.getElementById("bili-status-btn").addEventListener("click", refreshBiliAuthStatus);
      document.getElementById("bili-logout-btn").addEventListener("click", logoutBiliAuth);
      document.getElementById("bili-clear-qr-btn").addEventListener("click", clearBiliQrCode);
      await loadBootstrap();
      restoreForm();
      await refreshBiliAuthStatus();
    });

    async function loadBootstrap() {
      const response = await fetch("/api/bootstrap");
      const payload = await response.json();
      state.bootstrap = payload;
      fillSelect("platform", payload.options.platforms);
      fillSelect("whisper_model", payload.options.whisper_models);
      fillSelect("output_format", payload.options.output_formats);
      fillSelect("acquisition_mode", payload.options.acquisition_modes);
      fillSelect("transcription_backend", payload.options.transcription_backends);
      fillSelect("vision_backend", payload.options.vision_backends);
      fillSelectFromItems("transcription_preset_id", payload.options.transcription_presets.items, payload.options.transcription_presets.selected_id);
      fillSelectFromItems("vision_api_config_id", payload.options.vision_api_configs.items, payload.options.vision_api_configs.selected_id);
      fillSelectFromItems("vision_prompt_id", payload.options.vision_prompts, payload.defaults.vision_prompt_id);
      applyDefaults(payload.defaults);
      renderStats(payload.stats || {});
      state.jobs = payload.jobs || [];
      pruneSelectedJobs();
      renderHistory(state.jobs);
      
      // 初始化Whisper模型信息展示
      setupWhisperModelInfo(payload.options.whisper_model_info);
    }
    
    function setupWhisperModelInfo(modelInfo) {
      const select = document.querySelector('[name="whisper_model"]');
      const infoDiv = document.getElementById('whisper-model-info');
      
      function updateInfo() {
        const model = select.value;
        const info = modelInfo[model];
        if (info) {
          infoDiv.innerHTML = `
            <strong>${model}</strong> 模型: ${info.size} | ${info.speed} | 准确度: ${info.accuracy} | 适用: ${info.best_for}
            <br><span style="color: #2196F3;">💡 首次使用会自动下载模型文件，请确保网络畅通</span>
          `;
        }
      }
      
      select.addEventListener('change', updateInfo);
      updateInfo(); // 初始显示
    }

    function fillSelect(name, items) {
      const select = document.querySelector(`[name="${name}"]`);
      select.innerHTML = "";
      for (const item of items) {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = item || "自动";
        select.appendChild(option);
      }
    }

    function fillSelectFromItems(name, items, selectedId) {
      const select = document.querySelector(`[name="${name}"]`);
      select.innerHTML = '<option value="">自动</option>';
      for (const item of items || []) {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = item.name || item.id;
        if (selectedId && item.id === selectedId) option.selected = true;
        select.appendChild(option);
      }
    }

    function applyDefaults(defaults) {
      for (const [key, value] of Object.entries(defaults)) {
        const field = document.querySelector(`[name="${key}"]`);
        if (!field || value === null || value === undefined) continue;
        field.value = String(value);
      }
    }

    function bindDropzone() {
      const dropzone = document.getElementById("dropzone");
      const input = document.getElementById("media-file");
      ["dragenter", "dragover"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.classList.add("dragover");
        });
      });
      ["dragleave", "drop"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.classList.remove("dragover");
        });
      });
      dropzone.addEventListener("drop", (event) => {
        const file = event.dataTransfer.files[0];
        if (!file) return;
        const dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        state.file = file;
        renderPickedFile();
      });
    }

    function onFilePicked(event) {
      state.file = event.target.files[0] || null;
      renderPickedFile();
    }

    function renderPickedFile() {
      document.getElementById("file-name").textContent = state.file ? state.file.name : "未选择文件";
    }

    async function submitJob(event) {
      event.preventDefault();
      setFormMessage("提交中...");
      const form = document.getElementById("quickread-form");
      const formData = new FormData(form);
      const sources = collectSourceInputs(formData);
      if (state.file && sources.length) {
        setFormMessage("本地文件不能和链接批量一起提交。", true);
        return;
      }
      if (!state.file && !sources.length) {
        setFormMessage("需要填写视频链接或选择本地文件。", true);
        return;
      }
      persistForm();
      const response = await fetch("/api/jobs", { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "提交失败", true);
        return;
      }
      const createdJobs = payload.jobs || (payload.job ? [payload.job] : []);
      if (!createdJobs.length) {
        setFormMessage("服务端未返回任务。", true);
        return;
      }
      state.activeJobId = createdJobs[0].job_id;
      if (createdJobs.length > 1) {
        setFormMessage(`批量任务已提交：${createdJobs.length} 条`);
      } else {
        setFormMessage(`任务已提交：${createdJobs[0].job_id}`);
      }
      await loadJob(createdJobs[0].job_id, true);
      await refreshHistory();
    }

    async function refreshHistory() {
      const response = await fetch("/api/jobs");
      const payload = await response.json();
      renderStats(buildStats(payload.jobs || []));
      state.jobs = payload.jobs || [];
      pruneSelectedJobs();
      renderHistory(state.jobs);
    }

    function renderStats(stats) {
      const container = document.getElementById("history-stats");
      const ordered = [
        ["queued", "排队"],
        ["running", "运行"],
        ["completed", "完成"],
        ["failed", "失败"],
        ["cancelled", "取消"],
      ];
      container.innerHTML = ordered.map(([key, label]) => `
        <div class="stat">
          <div class="hint">${label}</div>
          <strong>${Number(stats[key] || 0)}</strong>
        </div>
      `).join("");
    }

    function buildStats(jobs) {
      const stats = { queued: 0, running: 0, completed: 0, failed: 0, cancelled: 0 };
      for (const job of jobs) {
        if (stats[job.status] !== undefined) stats[job.status] += 1;
      }
      return stats;
    }

    function renderHistory(jobs) {
      const container = document.getElementById("job-history");
      const count = document.getElementById("history-count");
      const filteredJobs = getFilteredJobs(jobs);
      count.textContent = `${filteredJobs.length} 条`;
      updateSelectionCount(filteredJobs);
      container.innerHTML = "";
      if (!filteredJobs.length) {
        container.innerHTML = '<div class="muted">暂无历史任务。</div>';
        return;
      }
      for (const job of filteredJobs) {
        const exportable = isJobExportable(job);
        const checked = state.selectedJobIds.has(job.job_id);
        const item = document.createElement("div");
        item.className = `job-card ${state.activeJobId === job.job_id ? "active" : ""} ${exportable ? "" : "disabled"}`;
        item.innerHTML = `
          <div class="row">
            <div class="row" style="justify-content:flex-start; gap:10px;">
              <input class="check" type="checkbox" ${checked ? "checked" : ""} ${exportable ? "" : "disabled"} />
              <strong>${escapeHtml(job.title || job.project_name || job.job_id)}</strong>
            </div>
            <span class="status ${job.status}">${escapeHtml(job.status)}</span>
          </div>
          <div class="hint">进度：${Number(job.progress || 0)}%${job.queue_position ? ` · 队列第 ${job.queue_position} 位` : ""}</div>
          <div class="hint">${escapeHtml(job.source || "")}</div>
          <div class="hint">${escapeHtml(job.updated_at || "")}</div>
        `;
        const checkbox = item.querySelector('input[type="checkbox"]');
        checkbox.addEventListener("click", (event) => event.stopPropagation());
        checkbox.addEventListener("change", (event) => {
          toggleSelectedJob(job.job_id, event.target.checked);
        });
        item.addEventListener("click", () => loadJob(job.job_id, true));
        container.appendChild(item);
      }
    }

    async function loadJob(jobId, autoPoll = false) {
      state.activeJobId = jobId;
      const response = await fetch(`/api/jobs/${jobId}`);
      const payload = await response.json();
      if (!payload.ok) return;
      renderJob(payload.job);
      await refreshHistory();
      subscribeJob(jobId, payload.job, autoPoll);
    }

    function renderJob(job) {
      const statusNode = document.getElementById("job-status");
      statusNode.className = `status ${job.status}`;
      statusNode.textContent = job.status;
      document.querySelector("#job-progress > span").style.width = `${Number(job.progress || 0)}%`;
      const container = document.getElementById("job-detail");
      const lines = [];
      lines.push(`<div class="hint">任务 ID：${escapeHtml(job.job_id)}</div>`);
      lines.push(`<div class="hint">来源：${escapeHtml(job.source || "")}</div>`);
      lines.push(`<div class="hint">阶段：${escapeHtml(job.stage || "")}</div>`);
      lines.push(`<div class="hint">进度：${Number(job.progress || 0)}%${job.queue_position ? ` · 队列第 ${job.queue_position} 位` : ""}</div>`);
      lines.push(`<div class="hint">状态说明：${escapeHtml(job.message || "")}</div>`);
      lines.push(`<div class="links">
        ${job.can_retry ? `<a href="#" onclick="retryJob('${escapeAttr(job.job_id)}', collectRetryOverrides()); return false;">重试</a>` : ""}
        ${job.can_cancel ? `<a href="#" onclick="cancelJob('${escapeAttr(job.job_id)}'); return false;">取消排队</a>` : ""}
        <a href="#" onclick="deleteJob('${escapeAttr(job.job_id)}'); return false;">删除历史</a>
      </div>`);
      if (job.can_continue && (job.available_resume_stages || []).length) {
        const options = (job.available_resume_stages || [])
          .map((stage) => `<option value="${escapeAttr(stage)}" ${job.suggested_resume_stage === stage ? "selected" : ""}>${escapeHtml(stage)}</option>`)
          .join("");
        lines.push(`
          <div class="row" style="justify-content:flex-start; align-items:end; margin-top:8px;">
            <label style="min-width:180px;">继续阶段
              <select id="resume-stage-select">${options}</select>
            </label>
            <button type="button" class="secondary" style="width:auto;" onclick="continueJob('${escapeAttr(job.job_id)}'); return false;">继续任务</button>
          </div>
        `);
      }
      if (job.error_summary && job.error_summary.has_issues) {
        lines.push(`<h3>错误摘要</h3>`);
        lines.push(`<div class="pre">${escapeHtml([job.error_summary.headline, ...(job.error_summary.items || []).map((item) => `- ${item}`)].join("\\n"))}</div>`);
      }
      if ((job.failure_chain || []).length) {
        lines.push(`<h3>失败链</h3>`);
        lines.push(`<div class="pre">${escapeHtml(job.failure_chain.map((item) => {
          const error = item.error ? ` | ${item.error}` : "";
          return `[${item.timestamp || ""}] ${item.stage || ""} - ${item.message || ""}${error}`;
        }).join("\\n"))}</div>`);
      }
      if (job.error) lines.push(`<div class="pre">${escapeHtml(job.error)}</div>`);
      if (job.result) {
        const result = job.result;
        const summary = result.summary || {};
        lines.push(`<h3>${escapeHtml(result.source.title || "未命名任务")}</h3>`);
        lines.push(`<div class="hint">平台：${escapeHtml(result.source.platform || "")}</div>`);
        lines.push(`<div class="pre">${escapeHtml([`标题：${summary.title || summary.one_line || ""}`, "", "内容概览", summary.overview || "", "", "核心观点", ...((summary.core_points || summary.key_points || []).map((item) => `- ${item}`)), "", "争议点", ...((summary.controversies || []).map((item) => `- ${item}`)), "", "行动建议", ...((summary.action_suggestions || []).map((item) => `- ${item}`)), "", "俏皮点评", summary.playful_comment || ""].join("\\n"))}</div>`);
        lines.push(`<div class="pre">${escapeHtml(result.transcript.text || "")}</div>`);
        const files = result.files || {};
        if (files.workdir) {
          lines.push(`<div class="links"><a href="#" onclick="openFolder('${escapeAttr(files.workdir)}'); return false;">打开输出目录</a></div>`);
        }
        const links = Object.entries(files)
          .filter(([, value]) => value)
          .map(([key, value]) => `<a href="/files?path=${encodeURIComponent(value)}" target="_blank">${escapeHtml(key)}</a>`)
          .join("");
        if (links) lines.push(`<div class="links">${links}</div>`);
      }
      container.innerHTML = lines.join("");
      renderEvents(job.events || []);
    }

    function renderEvents(events) {
      const container = document.getElementById("job-events");
      if (!events.length) {
        container.innerHTML = '<div class="muted">暂无事件日志。</div>';
        return;
      }
      container.innerHTML = events.slice().reverse().map((event) => `
        <div class="event">
          <div class="row">
            <strong>${escapeHtml(event.message || event.stage || "")}</strong>
            <span class="hint">${escapeHtml(event.timestamp || "")}</span>
          </div>
          <div class="hint">阶段：${escapeHtml(event.stage || "")}</div>
          ${event.data ? `<div class="hint">${escapeHtml(JSON.stringify(event.data, null, 2))}</div>` : ""}
        </div>
      `).join("");
    }

    function persistForm() {
      const form = document.getElementById("quickread-form");
      const sensitiveFields = new Set(["bili_cookie", "sessdata"]);
      const data = {};
      for (const element of form.elements) {
        if (!element.name || element.type === "file" || sensitiveFields.has(element.name)) continue;
        data[element.name] = element.value;
      }
      localStorage.setItem(storageKey, JSON.stringify(data));
    }

    function restoreForm() {
      const text = localStorage.getItem(storageKey);
      if (!text) return;
      try {
        const data = JSON.parse(text);
        const sensitiveFields = new Set(["bili_cookie", "sessdata"]);
        for (const [key, value] of Object.entries(data)) {
          if (sensitiveFields.has(key)) continue;
          const field = document.querySelector(`[name="${key}"]`);
          if (field && value !== null && value !== undefined && value !== "") {
            field.value = value;
          }
        }
      } catch (_) {}
    }

    function setFormMessage(message, isError = false) {
      const node = document.getElementById("form-message");
      node.textContent = message;
      node.style.color = isError ? "#ef4444" : "#94a3b8";
    }

    function collectRetryOverrides() {
      const form = document.getElementById("quickread-form");
      if (!form) return null;
      const overrides = {};
      for (const name of ["bili_cookie", "sessdata"]) {
        const field = form.querySelector(`[name="${name}"]`);
        const value = String(field?.value || "").trim();
        if (value) {
          overrides[name] = value;
        }
      }
      return Object.keys(overrides).length ? overrides : null;
    }

    async function retryJob(jobId, overrides = null) {
      const formData = new FormData();
      if (overrides) {
        for (const [key, value] of Object.entries(overrides)) {
          if (value === undefined || value === null) continue;
          formData.set(key, String(value));
        }
      }
      const response = await fetch(`/api/jobs/${jobId}/retry`, { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "重试失败", true);
        return;
      }
      state.activeJobId = payload.job.job_id;
      setFormMessage(`已重新提交：${payload.job.job_id}`);
      await loadJob(payload.job.job_id, true);
    }

    async function cancelJob(jobId) {
      const response = await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "取消失败", true);
        return;
      }
      setFormMessage(`任务已取消：${jobId}`);
      await loadJob(jobId, false);
      await refreshHistory();
    }

    async function continueJob(jobId) {
      const select = document.getElementById("resume-stage-select");
      const resumeStage = select ? String(select.value || "").trim() : "";
      const formData = new FormData();
      if (resumeStage) formData.set("resume_stage", resumeStage);
      const response = await fetch(`/api/jobs/${jobId}/continue`, { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "继续任务失败", true);
        return;
      }
      state.activeJobId = payload.job.job_id;
      setFormMessage(`已继续任务：${payload.job.job_id}`);
      await loadJob(payload.job.job_id, true);
      await refreshHistory();
    }

    async function deleteJob(jobId) {
      if (!window.confirm("删除该任务历史并清理对应输出目录？")) return;
      const response = await fetch(`/api/jobs/${jobId}?delete_files=true`, { method: "DELETE" });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "删除失败", true);
        return;
      }
      if (state.activeJobId === jobId) {
        closeJobStream();
        state.activeJobId = null;
        document.getElementById("job-detail").innerHTML = '<div class="muted">任务已删除。</div>';
        document.getElementById("job-events").innerHTML = '<div class="muted">任务已删除。</div>';
        document.getElementById("job-status").className = "status queued";
        document.getElementById("job-status").textContent = "未选择";
      }
      state.selectedJobIds.delete(jobId);
      setFormMessage("任务已删除");
      await refreshHistory();
    }

    async function openFolder(path) {
      const response = await fetch(`/api/open-folder?path=${encodeURIComponent(path)}`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "打开目录失败", true);
        return;
      }
      setFormMessage(`已打开目录：${payload.path}`);
    }

    async function saveDefaultOutputDir() {
      const input = document.querySelector('[name="data_dir"]');
      const dataDir = String(input.value || "").trim();
      if (!dataDir) {
        setFormMessage("需要先填写输出目录。", true);
        return;
      }
      const formData = new FormData();
      formData.set("data_dir", dataDir);
      const response = await fetch("/api/preferences/output-dir", { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "保存默认目录失败", true);
        return;
      }
      document.querySelector('[name="data_dir"]').value = payload.data_dir;
      persistForm();
      setFormMessage(`默认输出目录已保存：${payload.data_dir}`);
    }

    async function saveDefaultVisionOpenAi() {
      const formData = new FormData();
      for (const name of [
        "vision_api_base",
        "vision_api_path",
        "vision_api_key",
        "vision_model",
        "vision_prompt",
        "vision_system_prompt",
        "vision_timeout",
      ]) {
        const field = document.querySelector(`[name="${name}"]`);
        formData.set(name, field ? field.value : "");
      }
      const response = await fetch("/api/preferences/vision-openai", { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setFormMessage(payload.detail || payload.error || "保存默认 OCR API 配置失败", true);
        return;
      }
      persistForm();
      setFormMessage("默认 OCR API 配置已保存");
    }

    async function createBiliQrCode() {
      setBiliAuthMessage("正在生成二维码...");
      window.clearTimeout(state.biliAuthTimer);
      const response = await fetch("/api/bilibili/auth/qrcode", { method: "POST" });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setBiliAuthMessage(payload.detail || payload.error || "二维码生成失败", true);
        return;
      }
      const qrcode = payload.qrcode || {};
      state.biliQrCodeKey = qrcode.qrcode_key || null;
      const box = document.getElementById("bili-qrcode");
      if (qrcode.qrcode_svg) {
        box.innerHTML = qrcode.qrcode_svg;
      } else {
        box.innerHTML = `<a href="${escapeAttr(qrcode.url || "#")}" target="_blank">打开二维码链接</a>`;
      }
      setBiliAuthBadge("waiting_for_scan");
      setBiliAuthMessage("等待扫码...");
      scheduleBiliAuthPoll();
    }

    async function pollBiliAuth() {
      if (!state.biliQrCodeKey) return;
      const response = await fetch(`/api/bilibili/auth/poll?qrcode_key=${encodeURIComponent(state.biliQrCodeKey)}`);
      const payload = await response.json();
      if (!response.ok) {
        setBiliAuthMessage(payload.detail || payload.error || "二维码轮询失败", true);
        return;
      }
      setBiliAuthBadge(payload.status || (payload.ok ? "success" : ""));
      if (payload.ok) {
        setBiliAuthMessage("登录态已保存到项目 secret 文件");
        state.biliQrCodeKey = null;
        window.clearTimeout(state.biliAuthTimer);
        await refreshBiliAuthStatus();
        return;
      }
      if (payload.status === "expired") {
        setBiliAuthMessage(payload.message || "二维码已过期", true);
        state.biliQrCodeKey = null;
        return;
      }
      setBiliAuthMessage(payload.message || "等待扫码确认...");
      scheduleBiliAuthPoll();
    }

    function scheduleBiliAuthPoll() {
      window.clearTimeout(state.biliAuthTimer);
      state.biliAuthTimer = window.setTimeout(pollBiliAuth, 2000);
    }

    async function refreshBiliAuthStatus() {
      const response = await fetch("/api/bilibili/auth/status");
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setBiliAuthMessage(payload.detail || payload.error || "登录态校验失败", true);
        return;
      }
      const status = payload.status || {};
      if (status.is_login) {
        setBiliAuthBadge("completed", status.uname ? `已登录：${status.uname}` : "已登录");
        setBiliAuthMessage(status.mid ? `mid: ${status.mid}` : "登录态有效");
      } else if (status.cookie_present) {
        setBiliAuthBadge("failed", "已失效");
        setBiliAuthMessage("本地存在 Bilibili cookie，但校验未登录", true);
      } else {
        setBiliAuthBadge("queued", "未登录");
        setBiliAuthMessage("未检测到本地 Bilibili 登录态");
      }
    }

    async function logoutBiliAuth() {
      window.clearTimeout(state.biliAuthTimer);
      const response = await fetch("/api/bilibili/auth/logout", { method: "POST" });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        setBiliAuthMessage(payload.detail || payload.error || "注销失败", true);
        return;
      }
      clearBiliQrCode();
      setBiliAuthBadge("queued", "未登录");
      setBiliAuthMessage(payload.logout?.cleared ? "已注销并清除本地登录态" : "本地没有可清除的登录态");
    }

    function clearBiliQrCode() {
      window.clearTimeout(state.biliAuthTimer);
      state.biliQrCodeKey = null;
      document.getElementById("bili-qrcode").innerHTML = '<span class="muted">生成后用 Bilibili App 扫码</span>';
    }

    function setBiliAuthBadge(status, text = "") {
      const node = document.getElementById("bili-auth-status");
      const className = status === "success" || status === "completed" ? "completed" : status === "expired" || status === "failed" ? "failed" : status === "waiting_for_confirmation" ? "running" : "queued";
      node.className = `status ${className}`;
      node.textContent = text || status || "未检测";
    }

    function setBiliAuthMessage(message, isError = false) {
      const node = document.getElementById("bili-auth-message");
      node.textContent = message;
      node.style.color = isError ? "#ef4444" : "#94a3b8";
    }

    function collectSourceInputs(formData) {
      const sources = [];
      const seen = new Set();
      for (const key of ["source_url", "source_urls"]) {
        const text = String(formData.get(key) || "").trim();
        if (!text) continue;
        for (const line of text.split(/\\r?\\n/)) {
          const source = line.trim();
          if (!source || seen.has(source)) continue;
          seen.add(source);
          sources.push(source);
        }
      }
      return sources;
    }

    function getFilteredJobs(jobs) {
      const keyword = String(document.getElementById("history-filter").value || "").trim().toLowerCase();
      return !keyword ? jobs : jobs.filter((job) => {
        const text = [job.title, job.project_name, job.source, job.status].filter(Boolean).join(" ").toLowerCase();
        return text.includes(keyword);
      });
    }

    function isJobExportable(job) {
      return Boolean(job && job.result && job.result.files && job.result.files.artifacts_dir);
    }

    function toggleSelectedJob(jobId, checked) {
      if (checked) {
        state.selectedJobIds.add(jobId);
      } else {
        state.selectedJobIds.delete(jobId);
      }
      updateSelectionCount(getFilteredJobs(state.jobs));
    }

    function pruneSelectedJobs() {
      const validIds = new Set(state.jobs.filter(isJobExportable).map((job) => job.job_id));
      state.selectedJobIds = new Set([...state.selectedJobIds].filter((jobId) => validIds.has(jobId)));
    }

    function updateSelectionCount(filteredJobs) {
      const filteredIds = new Set(filteredJobs.filter(isJobExportable).map((job) => job.job_id));
      const visibleSelected = [...state.selectedJobIds].filter((jobId) => filteredIds.has(jobId)).length;
      document.getElementById("selection-count").textContent = `已选 ${state.selectedJobIds.size} 条 · 当前筛选命中 ${visibleSelected} 条`;
    }

    function selectVisibleJobs() {
      const filteredJobs = getFilteredJobs(state.jobs).filter(isJobExportable);
      for (const job of filteredJobs) {
        state.selectedJobIds.add(job.job_id);
      }
      renderHistory(state.jobs);
      setFormMessage(`已选中 ${filteredJobs.length} 条可导出任务`);
    }

    function clearSelectedJobs() {
      state.selectedJobIds.clear();
      renderHistory(state.jobs);
      setFormMessage("已清空批量选择");
    }

    async function exportSelectedJobs() {
      const jobIds = [...state.selectedJobIds];
      if (!jobIds.length) {
        setFormMessage("需要先选择要导出的任务。", true);
        return;
      }
      const response = await fetch("/api/jobs/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: jobIds }),
      });
      if (!response.ok) {
        const contentType = response.headers.get("content-type") || "";
        let message = "批量导出失败";
        if (contentType.includes("application/json")) {
          const payload = await response.json();
          message = payload.detail || payload.error || message;
        }
        setFormMessage(message, true);
        return;
      }
      await downloadBlobResponse(response, "vivid-batch-export.zip");
      setFormMessage(`批量导出完成：${jobIds.length} 条任务`);
    }

    async function downloadBlobResponse(response, fallbackName) {
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
      const filename = match ? decodeURIComponent(match[1]) : fallbackName;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function subscribeJob(jobId, job, autoPoll) {
      closeJobStream();
      window.clearTimeout(state.pollTimer);
      if (!autoPoll || ["completed", "failed", "cancelled"].includes(job.status)) {
        return;
      }
      if (window.EventSource) {
        const source = new EventSource(`/api/jobs/${jobId}/events`);
        state.eventSource = source;
        source.addEventListener("job", async (event) => {
          const payload = JSON.parse(event.data);
          if (!payload.ok || payload.job.job_id !== state.activeJobId) return;
          renderJob(payload.job);
          await refreshHistory();
          if (["completed", "failed", "cancelled"].includes(payload.job.status)) {
            closeJobStream();
          }
        });
        source.addEventListener("deleted", () => {
          closeJobStream();
        });
        source.onerror = () => {
          closeJobStream();
          schedulePollFallback(jobId);
        };
        return;
      }
      schedulePollFallback(jobId);
    }

    function schedulePollFallback(jobId) {
      window.clearTimeout(state.pollTimer);
      state.pollTimer = window.setTimeout(() => loadJob(jobId, true), 2000);
    }

    function closeJobStream() {
      if (state.eventSource) {
        state.eventSource.close();
        state.eventSource = null;
      }
    }

    function escapeHtml(value) {
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll("'", "&#39;");
    }
  </script>
</body>
</html>"""


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", Path(filename).name, flags=re.UNICODE)
    return cleaned or "upload.bin"


def _checkbox_to_no_keep_files(form: Any) -> bool:
    keep_files = form.get("keep_files")
    if keep_files is None:
        return False
    return not _bool_value(keep_files)


def _is_upload(value: Any) -> bool:
    return hasattr(value, "filename") and hasattr(value, "read") and bool(getattr(value, "filename", ""))


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _clean_form_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_job_error_code(events: list[dict[str, Any]] | None, error: str | None) -> str | None:
    for event in reversed(events or []):
        data = event.get("data") if isinstance(event.get("data"), dict) else None
        code = _text_or_none((data or {}).get("error_code"))
        if code:
            return code
    return None


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _delete_file_quietly(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError:
        return


def _delete_job_files(settings: Settings, record: WebJobRecord) -> None:
    workdir = _extract_workdir(record)
    if workdir and _is_under_data_root(settings, workdir):
        try:
            shutil.rmtree(workdir, ignore_errors=True)
        except OSError:
            pass
    source = _text_or_none(record.request.get("source"))
    if not source:
        return
    source_path = Path(source).expanduser()
    uploads_root = (settings.data_dir / "web_ui" / "uploads").resolve()
    try:
        resolved = source_path.resolve()
        resolved.relative_to(uploads_root)
    except (OSError, ValueError):
        return
    _delete_file_quietly(resolved)


def build_jobs_export_archive(settings: Settings, manager: WebJobManager, job_ids: list[str]) -> Path:
    exports_root = (settings.data_dir / "web_ui" / "exports").resolve()
    exports_root.mkdir(parents=True, exist_ok=True)
    archive_path = exports_root / f"vivid-batch-export-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}.zip"

    manifest_jobs: list[dict[str, Any]] = []
    added_files = 0
    unique_job_ids = list(dict.fromkeys(job_ids))
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as bundle:
        for job_id in unique_job_ids:
            job = manager.get_job(job_id)
            if not job:
                continue
            result = job.get("result") or {}
            files = result.get("files") or {}
            artifacts_dir_text = _text_or_none(files.get("artifacts_dir"))
            if not artifacts_dir_text:
                continue
            artifacts_dir = Path(artifacts_dir_text).expanduser().resolve()
            if not artifacts_dir.is_dir() or not _is_under_data_root(settings, artifacts_dir):
                continue
            archive_prefix = _build_job_archive_prefix(job)
            job_files = 0
            for path in artifacts_dir.rglob("*"):
                if not path.is_file():
                    continue
                relative = path.relative_to(artifacts_dir).as_posix()
                bundle.write(path, arcname=f"{archive_prefix}/artifacts/{relative}")
                job_files += 1
                added_files += 1
            if not job_files:
                continue
            manifest_jobs.append(
                {
                    "job_id": job_id,
                    "title": job.get("title") or job.get("project_name"),
                    "status": job.get("status"),
                    "source": job.get("source"),
                    "archive_prefix": archive_prefix,
                    "artifacts_dir": str(artifacts_dir),
                    "file_count": job_files,
                }
            )
        if not added_files:
            raise ValueError("no exportable job artifacts found")
        manifest = {
            "created_at": _now_iso(),
            "job_count": len(manifest_jobs),
            "jobs": manifest_jobs,
        }
        bundle.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
    return archive_path


def _extract_workdir(record: WebJobRecord) -> Path | None:
    if not record.result:
        return None
    files = record.result.get("files") or {}
    workdir = _text_or_none(files.get("workdir"))
    if not workdir:
        return None
    return Path(workdir).expanduser().resolve()


async def _collect_export_job_ids(request: Request) -> list[str]:
    content_type = request.headers.get("content-type", "")
    raw_values: list[Any]
    if "application/json" in content_type:
        payload = await request.json()
        raw_values = payload.get("job_ids", []) if isinstance(payload, dict) else []
    else:
        form = await request.form()
        raw_values = list(form.getlist("job_ids"))
    job_ids: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        value = _clean_form_value(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        job_ids.append(value)
    return job_ids


def _is_under_data_root(settings: Settings, path: Path) -> bool:
    try:
        path.resolve().relative_to(settings.data_dir.resolve())
    except ValueError:
        return False
    return True


def _looks_like_local_path(value: str) -> bool:
    return "://" not in value and not value.startswith("magnet:")


def _build_job_archive_prefix(job: dict[str, Any]) -> str:
    name = _safe_filename(str(job.get("title") or job.get("project_name") or job.get("job_id") or "job"))
    return f"{name}-{job.get('job_id', 'unknown')}"


def _invoke_run_quickread(
    options,
    event_callback,
):
    parameters = inspect.signature(run_quickread).parameters
    if "event_callback" in parameters:
        return run_quickread(options, event_callback=event_callback)
    return run_quickread(options)


def _build_event(stage: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "timestamp": _now_iso(),
        "stage": stage,
        "message": message,
        "data": data or None,
    }


def _progress_for_stage(stage: str, fallback: int) -> int | None:
    progress_map = {
        "queued": 5,
        "prepare": 10,
        "preparing": 15,
        "detect_platform": 20,
        "subtitle": 25,
        "download": 30,
        "source_ready": 30,
        "media_ready": 35,
        "transcription": 45,
        "transcription_completed": 65,
        "ocr": 55,
        "ocr_fallback": 58,
        "ocr_failed": 60,
        "acquire_completed": 70,
        "title": 74,
        "summarize": 78,
        "summary_provider": 80,
        "summary_provider_completed": 82,
        "summarize_completed": 82,
        "calibrate": 84,
        "calibration_cn_provider": 86,
        "calibration_cn_completed": 88,
        "calibration_en_provider": 90,
        "calibration_en_completed": 92,
        "calibration_provider_completed": 93,
        "calibrate_completed": 94,
        "calibration_failed": 94,
        "render": 94,
        "artifacts": 97,
        "completed": 100,
        "failed": 100,
        "cancelled": 0,
    }
    return progress_map.get(stage, fallback)


def web_preferences_path(settings: Settings) -> Path:
    return settings.repo_root / "configs" / "web_ui" / "preferences.json"


def load_web_preferences(settings: Settings) -> dict[str, Any]:
    path = web_preferences_path(settings)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_web_preferences(settings: Settings, payload: dict[str, Any]) -> None:
    preference_path = web_preferences_path(settings)
    preference_path.parent.mkdir(parents=True, exist_ok=True)
    preference_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_preferred_output_dir(settings: Settings) -> Path | None:
    payload = load_web_preferences(settings)
    text = _text_or_none(payload.get("default_output_dir"))
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute():
        return path
    return (settings.repo_root / path).resolve()


def save_preferred_output_dir(settings: Settings, path: Path) -> None:
    payload = load_web_preferences(settings)
    payload["default_output_dir"] = _serialize_preference_path(settings, path)
    save_web_preferences(settings, payload)


def load_preferred_vision_openai(settings: Settings) -> dict[str, Any]:
    payload = load_web_preferences(settings)
    vision = payload.get("default_vision_openai")
    return vision if isinstance(vision, dict) else {}


def save_preferred_vision_openai(settings: Settings, vision_payload: dict[str, Any]) -> None:
    payload = load_web_preferences(settings)
    payload["default_vision_openai"] = {
        key: value
        for key, value in vision_payload.items()
        if value not in {None, ""}
    }
    save_web_preferences(settings, payload)


def _serialize_preference_path(settings: Settings, path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(settings.repo_root.resolve())
    except ValueError:
        return str(resolved)
    relative_text = relative.as_posix() or "."
    return f"./{relative_text}"


def ensure_output_dir(path: Path) -> Path:
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    if not resolved.is_dir():
        raise OSError(f"not a directory: {resolved}")
    return resolved


def build_open_folder_command(folder_path: Path) -> list[str] | None:
    target = str(folder_path)
    if sys.platform.startswith("win"):
        return ["explorer.exe", target]
    if sys.platform == "darwin":
        return ["open", target] if shutil.which("open") else None
    return ["xdg-open", target] if shutil.which("xdg-open") else None


def _format_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _job_signature(job: dict[str, Any]) -> tuple[Any, ...]:
    events = job.get("events") or []
    return (
        job.get("status"),
        job.get("stage"),
        job.get("progress"),
        job.get("updated_at"),
        len(events),
        events[-1]["timestamp"] if events else None,
    )
