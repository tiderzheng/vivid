from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..adapters.bilibili import BilibiliAdapter
from ..adapters.douyin import DouyinAdapter
from ..adapters.ears4 import Ears4Adapter
from ..adapters.eyes import EyesAdapter
from ..adapters.ytdlp import YtDlpAdapter
from ..exceptions import VividError
from ..models.runtime import RuntimeOptions
from ..models.transcript import TranscriptResult
from ..subsystems import InternalTranscriptionEngine, build_transcription_request_config, detect_hard_subtitles
from ..subsystems.vision import InternalVisionEngine, build_vision_request_config
from ..services.media_store import copy_into_dir, is_video_file
from ..utils.logging_utils import log_exception

QuickreadEventCallback = Callable[[str, str, dict[str, Any] | None], None]
CheckpointCallback = Callable[[dict[str, Any]], None]


def create_media_path(
    source: str,
    platform: str,
    workdir: Path,
    options: RuntimeOptions,
    event_callback: QuickreadEventCallback | None = None,
) -> Path:
    if platform == "local":
        path = Path(source).expanduser().resolve()
        if not path.exists():
            raise VividError(f"Local file does not exist: {path}")
        _emit_event(event_callback, "source_ready", "使用本地媒体文件", {"path": str(path)})
        return path
    if platform == "bilibili":
        _emit_event(event_callback, "download", "开始下载 Bilibili 媒体")
        return BilibiliAdapter(options.bili_script).download_media(
            source,
            workdir,
            options.ffmpeg_bin,
            bili_cookie=options.bili_cookie,
            sessdata=options.sessdata,
        )
    if platform == "douyin":
        _emit_event(event_callback, "download", "开始下载 Douyin 媒体")
        return DouyinAdapter(options.douyin_script).download_media(source, workdir)
    _emit_event(event_callback, "download", "开始下载通用媒体")
    return YtDlpAdapter().download_media(source, workdir)


def acquire_transcript(
    options: RuntimeOptions,
    platform: str,
    workdir: Path,
    event_callback: QuickreadEventCallback | None = None,
    *,
    checkpoint_callback: CheckpointCallback | None = None,
    resume_media_path: Path | None = None,
) -> TranscriptResult:
    if resume_media_path is not None:
        media_path = resume_media_path.expanduser()
        if not media_path.exists():
            raise VividError(f"checkpoint media does not exist: {media_path}")
        _emit_event(event_callback, "media_ready", "已加载断点媒体", {"path": str(media_path)})
    else:
        media_path = create_media_path(options.source, platform, workdir, options, event_callback)
    _emit_event(event_callback, "media_ready", "媒体准备完成", {"path": str(media_path)})
    _emit_checkpoint(
        checkpoint_callback,
        {
            "media_path": str(media_path),
            "last_completed_stage": "media_ready",
        },
    )
    effective_mode = _resolve_effective_acquisition_mode(options, media_path, event_callback)
    if effective_mode == "force_ocr":
        _emit_event(event_callback, "ocr", "按 force_ocr 模式执行 OCR")
        result = _acquire_by_force_ocr(options, media_path, workdir, event_callback)
        _emit_checkpoint(
            checkpoint_callback,
            {
                "last_completed_stage": "transcription",
                "transcript": _transcript_payload(result),
            },
        )
        return result
    if effective_mode == "prefer_ocr" and is_video_file(media_path):
        try:
            mode_label = "smart" if options.acquisition_mode == "smart" else "prefer_ocr"
            _emit_event(event_callback, "ocr", f"按 {mode_label} 模式优先执行 OCR")
            result = TranscriptResult(
                text=_extract_video_text(options, media_path, workdir, event_callback),
                acquisition_method="Smart OCR" if options.acquisition_mode == "smart" else "Preferred OCR",
                media_path=media_path,
            )
            _emit_checkpoint(
                checkpoint_callback,
                {
                    "last_completed_stage": "transcription",
                    "transcript": _transcript_payload(result),
                },
            )
            return result
        except Exception as exc:
            _emit_event(event_callback, "ocr_failed", "优先 OCR 失败，回退到转录", {"error": str(exc)})
            log_exception("preferred_ocr_failed", exc, source=options.source, mode=mode_label)
    transcription_config = build_transcription_request_config(options)
    try:
        _emit_event(
            event_callback,
            "transcription",
            "开始内部 Whisper 转录",
            {"model": transcription_config.model},
        )
        internal_result = _transcribe_internal(options, media_path, workdir, transcription_config)
        _emit_event(
            event_callback,
            "transcription_completed",
            "内部 Whisper 转录完成",
            {"model": transcription_config.model},
        )
        result = TranscriptResult(
            text=internal_result.transcript,
            acquisition_method=f"Internal Whisper {transcription_config.model}",
            media_path=media_path,
            audio_path=copy_into_dir(internal_result.audio_path, workdir / "media" / "audio"),
        )
        _emit_checkpoint(
            checkpoint_callback,
            {
                "last_completed_stage": "transcription",
                "transcript": _transcript_payload(result),
            },
        )
        return result
    except Exception as exc:
        log_exception("internal_transcription_failed", exc, source=options.source, backend=options.transcription_backend)
        if options.transcription_backend == "internal":
            if is_video_file(media_path):
                _emit_event(event_callback, "ocr_fallback", "内部转录失败，改走内部 OCR")
                transcript = _extract_video_text(options, media_path, workdir, event_callback)
                result = TranscriptResult(
                    text=transcript,
                    acquisition_method="Internal OCR fallback",
                    media_path=media_path,
                )
                _emit_checkpoint(
                    checkpoint_callback,
                    {
                        "last_completed_stage": "transcription",
                        "transcript": _transcript_payload(result),
                    },
                )
                return result
            raise VividError(
                f"Internal transcription failed and OCR fallback is unavailable for non-video media: {media_path}"
            ) from exc
        if options.transcription_backend == "auto":
            try:
                _emit_event(event_callback, "transcription_fallback", "内部转录失败，改走 Ears4 API")
                ears4_result = Ears4Adapter(options.ears4_api).transcribe(
                    media_path,
                    options.transcribe_timeout,
                    transcription_config,
                )
                _emit_event(event_callback, "transcription_completed", "Ears4 转录完成")
                audio_path = copy_into_dir(ears4_result.audio_path, workdir / "media" / "audio")
                result = TranscriptResult(
                    text=ears4_result.transcript,
                    acquisition_method=f"Ears4 Whisper {transcription_config.model}",
                    media_path=media_path,
                    audio_path=audio_path,
                )
                _emit_checkpoint(
                    checkpoint_callback,
                    {
                        "last_completed_stage": "transcription",
                        "transcript": _transcript_payload(result),
                    },
                )
                return result
            except Exception as fallback_exc:
                _emit_event(
                    event_callback,
                    "transcription_failed",
                    "Ears4 转录失败，尝试 OCR 兜底",
                    {"error": str(fallback_exc)},
                )
                log_exception("ears4_transcription_failed", fallback_exc, source=options.source)
        if is_video_file(media_path):
            _emit_event(event_callback, "ocr_fallback", "转录失败，改走 OCR 兜底")
            transcript = _extract_video_text(options, media_path, workdir, event_callback)
            result = TranscriptResult(
                text=transcript,
                acquisition_method="Eyes OCR fallback",
                media_path=media_path,
            )
            _emit_checkpoint(
                checkpoint_callback,
                {
                    "last_completed_stage": "transcription",
                    "transcript": _transcript_payload(result),
                },
            )
            return result
        raise VividError(
            f"Transcription failed and OCR fallback is unavailable for non-video media: {media_path}"
        ) from exc


def _acquire_by_force_ocr(
    options: RuntimeOptions,
    media_path: Path,
    workdir: Path,
    event_callback: QuickreadEventCallback | None = None,
) -> TranscriptResult:
    if not is_video_file(media_path):
        raise VividError(f"force_ocr mode requires a video input: {media_path}")
    return TranscriptResult(
        text=_extract_video_text(options, media_path, workdir, event_callback),
        acquisition_method="Forced OCR",
        media_path=media_path,
    )


def _transcribe_internal(
    options: RuntimeOptions,
    media_path: Path,
    workdir: Path,
    transcription_config,
):
    if options.transcription_backend == "ears4_api":
        raise VividError("Internal transcription disabled by transcription backend setting.")
    return InternalTranscriptionEngine(
        ffmpeg_bin=options.ffmpeg_bin,
        whisper_root=options.whisper_root,
    ).transcribe(
        media_path,
        workdir,
        options.transcribe_timeout,
        transcription_config,
    )


def _extract_video_text(
    options: RuntimeOptions,
    media_path: Path,
    workdir: Path,
    event_callback: QuickreadEventCallback | None = None,
) -> str:
    vision_config = build_vision_request_config(options)
    if options.vision_backend != "eyes_api":
        try:
            _emit_event(event_callback, "ocr", "开始内部 OCR", {"backend": "internal"})
            return InternalVisionEngine().extract_text(
                media_path,
                workdir,
                options.ocr_timeout,
                vision_config,
            ).transcript
        except Exception as exc:
            _emit_event(event_callback, "ocr_failed", "内部 OCR 失败", {"error": str(exc)})
            log_exception("internal_ocr_failed", exc, source=options.source, backend="internal")
            if options.vision_backend == "internal":
                raise
    _emit_event(event_callback, "ocr", "开始 Eyes API OCR", {"backend": "eyes_api"})
    return EyesAdapter(options.eyes_api).extract_text(
        media_path,
        workdir,
        options.ocr_timeout,
        vision_config,
    )


def _emit_event(
    callback: QuickreadEventCallback | None,
    stage: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    if callback is None:
        return
    callback(stage, message, data or None)


def _resolve_effective_acquisition_mode(
    options: RuntimeOptions,
    media_path: Path,
    event_callback: QuickreadEventCallback | None = None,
) -> str:
    if options.acquisition_mode != "smart":
        return options.acquisition_mode
    if not is_video_file(media_path):
        _emit_event(
            event_callback,
            "strategy",
            "智能推荐：检测到非视频输入，优先转录",
            {"recommended_mode": "auto", "reason": "non_video"},
        )
        return "auto"
    try:
        probe = detect_hard_subtitles(media_path)
    except Exception as exc:
        _emit_event(
            event_callback,
            "strategy",
            "智能推荐：硬字幕探测失败，回退到常规转录",
            {"recommended_mode": "auto", "reason": "probe_failed", "error": str(exc)},
        )
        return "auto"
    if probe.has_hard_subtitles:
        _emit_event(
            event_callback,
            "strategy",
            "智能推荐：检测到硬字幕，优先 OCR",
            {
                "recommended_mode": "prefer_ocr",
                "reason": "hard_subtitles",
                "matched_frames": probe.matched_frames,
                "sampled_frames": probe.sampled_frames,
                "ratio": probe.ratio,
            },
        )
        return "prefer_ocr"
    _emit_event(
        event_callback,
        "strategy",
        "智能推荐：未检测到明显硬字幕，优先转录",
        {
            "recommended_mode": "auto",
            "reason": "voice_or_soft_subtitles",
            "matched_frames": probe.matched_frames,
            "sampled_frames": probe.sampled_frames,
            "ratio": probe.ratio,
        },
    )
    return "auto"


def _emit_checkpoint(callback: CheckpointCallback | None, payload: dict[str, Any]) -> None:
    if callback is None:
        return
    callback(payload)


def _transcript_payload(transcript: TranscriptResult) -> dict[str, Any]:
    return {
        "text": transcript.text,
        "acquisition_method": transcript.acquisition_method,
        "media_path": str(transcript.media_path) if transcript.media_path else None,
        "audio_path": str(transcript.audio_path) if transcript.audio_path else None,
    }
