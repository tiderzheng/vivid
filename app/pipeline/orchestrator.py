from __future__ import annotations

import json
from dataclasses import dataclass, field
import inspect
from pathlib import Path
from typing import Any, Callable

from ..exceptions import BilibiliSessdataExpiredError
from ..models.artifact import ArtifactBundle
from ..models.runtime import RuntimeOptions
from ..models.source import SourceInfo
from ..models.summary import SummaryResult
from ..models.transcript import TranscriptResult
from ..services.cleanup import cleanup_media
from ..services.diagnostics import build_diagnostic_event, build_error_summary, extract_failure_chain
from ..services.artifact_writer import save_artifacts
from ..services.pathing import make_staging_workdir, move_to_final_workdir, relocate_path
from ..services.project_naming import derive_title, infer_video_title
from ..services.run_state import (
    checkpoint_path,
    load_run_state,
    save_run_state,
    summary_from_payload,
    summary_to_payload,
    transcript_from_payload,
    transcript_to_payload,
    update_run_state,
)
from .acquisition import acquire_transcript
from .detector import detect_platform
from .formatter import render_quickread
from .summarization import summarize_transcript
from .transcription import normalize_transcript

QuickreadEventCallback = Callable[[str, str, dict[str, Any] | None], None]


@dataclass(slots=True)
class OrchestratorResult:
    source: SourceInfo
    transcript: TranscriptResult
    summary: SummaryResult
    artifacts: ArtifactBundle
    rendered: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source": {
                "raw_source": self.source.raw_source,
                "platform": self.source.platform,
                "title": self.source.title,
            },
            "transcript": {
                "acquisition_method": self.transcript.acquisition_method,
                "text": self.transcript.text,
            },
            "summary": {
                "one_line": self.summary.one_line,
                "detailed": self.summary.detailed,
                "key_points": self.summary.key_points,
                "provider": self.summary.provider,
            },
            "artifacts": {
                "workdir": str(self.artifacts.workdir),
                "artifacts_dir": str(self.artifacts.artifacts_dir),
            },
            "rendered": self.rendered,
            "diagnostics": self.diagnostics,
            "failure_chain": extract_failure_chain(self.diagnostics),
            "error_summary": build_error_summary(self.diagnostics),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def run_quickread(
    options: RuntimeOptions,
    event_callback: QuickreadEventCallback | None = None,
    *,
    pause_on_bili_sessdata_expired: bool = False,
) -> OrchestratorResult:
    diagnostics: list[dict[str, Any]] = []
    recording_callback = _build_recording_callback(event_callback, diagnostics)
    resume_mode = options.resume_workdir is not None
    workdir = options.resume_workdir.expanduser().resolve() if options.resume_workdir else make_staging_workdir(options.data_dir, options.source)
    resume_state = load_run_state(workdir) if resume_mode else {}
    initial_message = "加载断点工作目录" if resume_mode else "创建工作目录"
    _emit_event(
        recording_callback,
        "prepare",
        initial_message,
        {"source": options.source, "workdir": str(workdir), "resume_stage": options.resume_stage},
    )
    save_run_state(
        workdir,
        {
            **resume_state,
            "source": options.source,
            "project_name": options.project_name,
            "output_format": options.output_format,
            "workdir": str(workdir),
        },
    )
    try:
        platform = resume_state.get("platform") or detect_platform(options.source, options.forced_platform)
        update_run_state(workdir, platform=platform, last_completed_stage="detect_platform", workdir=str(workdir))
        _emit_event(recording_callback, "detect_platform", "识别平台完成", {"platform": platform})
        
        # 尝试获取视频标题（用于更好的项目命名）
        fetched_title: str | None = None
        saved_title = str(resume_state.get("title")).strip() if resume_state.get("title") else None
        if not options.project_name and not saved_title:
            try:
                if platform == "bilibili":
                    from ..adapters.bilibili import BilibiliAdapter
                    adapter = BilibiliAdapter(options.bili_script)
                    fetched_title = adapter.get_video_title(options.source, options.sessdata)
                elif platform == "douyin":
                    from ..adapters.douyin import DouyinAdapter
                    adapter = DouyinAdapter(options.douyin_script)
                    fetched_title = adapter.get_video_title(options.source)
                
                if fetched_title:
                    _emit_event(recording_callback, "title_fetch", "获取视频标题", {"title": fetched_title})
            except BilibiliSessdataExpiredError as exc:
                _emit_event(
                    recording_callback,
                    "sessdata_refresh_required",
                    "Bilibili SESSDATA 已失效，请先更新；若不更新，可清空后继续后续流程",
                    {
                        "error": str(exc),
                        "error_code": "bili_sessdata_expired",
                        "can_continue_without_sessdata": True,
                    },
                )
                if pause_on_bili_sessdata_expired:
                    raise
                options.sessdata = None
            except Exception as exc:
                _emit_event(
                    recording_callback,
                    "title_fetch_fallback",
                    "视频标题获取失败，将使用默认命名策略",
                    {"platform": platform, "error": str(exc)},
                )
        
        resume_stage = options.resume_stage
        transcript = _load_resumed_transcript(resume_state, resume_stage)
        if transcript is None:
            _emit_event(recording_callback, "acquire", "开始获取文本内容")
            transcript = normalize_transcript(
                _invoke_with_supported_kwargs(
                    acquire_transcript,
                    options,
                    platform,
                    workdir,
                event_callback=recording_callback,
                checkpoint_callback=_build_checkpoint_callback(workdir),
                resume_media_path=_resume_media_path(resume_state, resume_stage),
                pause_on_bili_sessdata_expired=pause_on_bili_sessdata_expired,
            ),
        )
            update_run_state(
                workdir,
                transcript=transcript_to_payload(transcript),
                media_path=str(transcript.media_path) if transcript.media_path else resume_state.get("media_path"),
                last_completed_stage="transcription",
            )
        else:
            _emit_event(
                recording_callback,
                "acquire_completed",
                "已从断点恢复文本内容",
                {"acquisition_method": transcript.acquisition_method},
            )
        if transcript is not None and resume_stage not in {"summarize", "render", "artifacts"}:
            _emit_event(
                recording_callback,
                "acquire_completed",
                "文本获取完成",
                {"acquisition_method": transcript.acquisition_method},
            )
        # 确定项目标题优先级：1. 用户指定 2. 获取的平台标题 3. 从媒体文件推断 4. 从URL提取
        title: str
        if saved_title:
            title = saved_title
        elif options.project_name:
            title = derive_title(options.source, options.project_name)
        elif fetched_title:
            title = fetched_title
        else:
            title = infer_video_title(options.source, transcript.media_path, workdir)
        _emit_event(recording_callback, "title", "确定项目名称", {"title": title})
        if (not resume_mode) or not resume_state.get("title"):
            final_workdir = move_to_final_workdir(workdir, options.data_dir, title)
            transcript.media_path = relocate_path(transcript.media_path, workdir, final_workdir)
            transcript.audio_path = relocate_path(transcript.audio_path, workdir, final_workdir)
            workdir = final_workdir
        update_run_state(
            workdir,
            title=title,
            platform=platform,
            workdir=str(workdir),
            media_path=str(transcript.media_path) if transcript.media_path else None,
            transcript=transcript_to_payload(transcript),
            last_completed_stage="title",
        )
        source = SourceInfo(raw_source=options.source, platform=platform, title=title)
        summary = _load_resumed_summary(resume_state, resume_stage)
        if summary is None:
            _emit_event(recording_callback, "summarize", "开始生成总结")
            summary = _invoke_with_supported_kwargs(
                summarize_transcript,
                options,
                transcript.text,
                event_callback=recording_callback,
            )
            update_run_state(workdir, summary=summary_to_payload(summary), last_completed_stage="summarize")
        else:
            _emit_event(recording_callback, "summarize", "已从断点恢复总结")
        _emit_event(recording_callback, "summarize_completed", "总结生成完成", {"provider": summary.provider})
        rendered = _load_resumed_rendered(resume_state, resume_stage)
        if rendered is None:
            _emit_event(recording_callback, "render", "开始渲染输出")
            rendered = render_quickread(source, transcript, summary, options.output_format)
            update_run_state(workdir, rendered=rendered, last_completed_stage="render")
        else:
            _emit_event(recording_callback, "render", "已从断点恢复渲染结果")
        _emit_event(recording_callback, "artifacts", "开始写入产物")
        artifacts = save_artifacts(
            workdir,
            source,
            transcript,
            summary,
            rendered,
            options.output_format,
            diagnostics=diagnostics,
        )
        update_run_state(
            workdir,
            last_completed_stage="artifacts",
            checkpoint_file=str(checkpoint_path(workdir)),
            transcript=transcript_to_payload(transcript),
            summary=summary_to_payload(summary),
            rendered=rendered,
        )
        _emit_event(recording_callback, "completed", "产物写入完成", {"workdir": str(workdir)})
        return OrchestratorResult(
            source=source,
            transcript=transcript,
            summary=summary,
            artifacts=artifacts,
            rendered=rendered,
            diagnostics=diagnostics,
        )
    finally:
        if not options.keep_files:
            cleanup_media(workdir)


def _emit_event(
    callback: QuickreadEventCallback | None,
    stage: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    if callback is None:
        return
    callback(stage, message, data or None)


def _build_recording_callback(
    callback: QuickreadEventCallback | None,
    diagnostics: list[dict[str, Any]],
):
    def wrapper(stage: str, message: str, data: dict[str, Any] | None = None) -> None:
        diagnostics.append(build_diagnostic_event(stage, message, data))
        if callback is not None:
            callback(stage, message, data or None)

    return wrapper


def _invoke_with_optional_callback(func, *args):
    parameters = inspect.signature(func).parameters
    if any(name == "event_callback" for name in parameters):
        return func(*args[:-1], event_callback=args[-1])
    return func(*args[:-1])


def _invoke_with_supported_kwargs(func, *args, **kwargs):
    parameters = inspect.signature(func).parameters
    supported = {key: value for key, value in kwargs.items() if key in parameters}
    return func(*args, **supported)


def _build_checkpoint_callback(workdir: Any):
    def callback(payload: dict[str, Any]) -> None:
        update_run_state(workdir, **payload)

    return callback


def _load_resumed_transcript(resume_state: dict[str, Any], resume_stage: str | None) -> TranscriptResult | None:
    if resume_stage not in {"summarize", "render", "artifacts"}:
        return None
    payload = resume_state.get("transcript")
    if not isinstance(payload, dict) or not payload.get("text"):
        raise ValueError(f"resume stage '{resume_stage}' requires a saved transcript checkpoint")
    return transcript_from_payload(payload)


def _load_resumed_summary(resume_state: dict[str, Any], resume_stage: str | None) -> SummaryResult | None:
    if resume_stage not in {"render", "artifacts"}:
        return None
    payload = resume_state.get("summary")
    if not isinstance(payload, dict) or not payload.get("detailed"):
        raise ValueError(f"resume stage '{resume_stage}' requires a saved summary checkpoint")
    return summary_from_payload(payload)


def _load_resumed_rendered(resume_state: dict[str, Any], resume_stage: str | None) -> str | None:
    if resume_stage != "artifacts":
        return None
    rendered = resume_state.get("rendered")
    if not isinstance(rendered, str) or not rendered.strip():
        raise ValueError("resume stage 'artifacts' requires a saved rendered checkpoint")
    return rendered


def _resume_media_path(resume_state: dict[str, Any], resume_stage: str | None) -> Path | None:
    if resume_stage != "transcription":
        return None
    media_path = resume_state.get("media_path")
    if not media_path:
        raise ValueError("resume stage 'transcription' requires a saved media checkpoint")
    return Path(str(media_path)).expanduser()
