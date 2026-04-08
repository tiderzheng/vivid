from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .config import Settings
from .models.runtime import RuntimeOptions
from .services.ffmpeg_locator import resolve_ffmpeg_bin


def build_runtime_options(settings: Settings, values: Mapping[str, Any]) -> RuntimeOptions:
    transcription_extract_audio = settings.transcription_extract_audio
    if _bool_value(values.get("transcription_extract_audio")):
        transcription_extract_audio = True
    if _bool_value(values.get("no_transcription_extract_audio")):
        transcription_extract_audio = False

    acquisition_mode = values.get("acquisition_mode") or settings.acquisition_mode
    if _bool_value(values.get("prefer_ocr")):
        acquisition_mode = "prefer_ocr"
    if _bool_value(values.get("force_ocr")):
        acquisition_mode = "force_ocr"

    return RuntimeOptions(
        source=_require_text(values, "source"),
        project_name=_text_or_none(values.get("project_name")),
        data_dir=_coerce_path(values.get("data_dir")) or settings.data_dir,
        output_format=_text_or_none(values.get("output_format")) or settings.default_format,
        whisper_model=_text_or_none(values.get("whisper_model")) or settings.default_model,
        forced_platform=_text_or_none(values.get("forced_platform")),
        ffmpeg_bin=resolve_ffmpeg_bin(
            _text_or_none(values.get("ffmpeg_bin")) or settings.ffmpeg_bin,
            repo_root=settings.repo_root,
            tools_root=settings.tools_root,
        ),
        whisper_root=_coerce_path(values.get("whisper_root")) or settings.whisper_root,
        ears4_api=(_text_or_none(values.get("ears4_api")) or settings.ears4_api).rstrip("/"),
        eyes_api=(_text_or_none(values.get("eyes_api")) or settings.eyes_api).rstrip("/"),
        language=_text_or_none(values.get("language")) or settings.language,
        transcription_preset_id=(
            _text_or_none(values.get("transcription_preset_id")) or settings.transcription_preset_id
        ),
        acquisition_mode=acquisition_mode,
        transcription_backend=(
            _text_or_none(values.get("transcription_backend")) or settings.transcription_backend
        ),
        transcription_device=(
            _text_or_none(values.get("transcription_device")) or settings.transcription_device
        ),
        transcription_task=(
            _text_or_none(values.get("transcription_task")) or settings.transcription_task
        ),
        transcription_extract_audio=transcription_extract_audio,
        transcription_output_dir=(
            _coerce_path(values.get("transcription_output_dir")) or settings.transcription_output_dir
        ),
        transcribe_timeout=_int_or_default(values.get("transcribe_timeout"), settings.transcribe_timeout),
        ocr_timeout=_int_or_default(values.get("ocr_timeout"), settings.ocr_timeout),
        llm_max_chars=_int_or_default(values.get("llm_max_chars"), settings.llm_max_chars),
        siliconflow_api_key=settings.siliconflow_api_key,
        dashscope_api_key=settings.dashscope_api_key,
        siliconflow_base_url=settings.siliconflow_base_url,
        dashscope_base_url=settings.dashscope_base_url,
        siliconflow_model=_text_or_none(values.get("siliconflow_model")) or settings.siliconflow_model,
        dashscope_model=_text_or_none(values.get("dashscope_model")) or settings.dashscope_model,
        bili_script=_coerce_path(values.get("bili_script")) or settings.bili_script,
        douyin_script=_coerce_path(values.get("douyin_script")) or settings.douyin_script,
        vision_api_config_id=(
            _text_or_none(values.get("vision_api_config_id")) or settings.vision_api_config_id
        ),
        vision_backend=_text_or_none(values.get("vision_backend")) or settings.vision_backend,
        vision_api_base=_text_or_none(values.get("vision_api_base")) or settings.vision_api_base,
        vision_api_path=_text_or_none(values.get("vision_api_path")) or settings.vision_api_path,
        vision_api_key=_text_or_none(values.get("vision_api_key")) or settings.vision_api_key,
        vision_model=_text_or_none(values.get("vision_model")) or settings.vision_model,
        vision_timeout=_int_or_optional(values.get("vision_timeout"), settings.vision_timeout),
        vision_prompt_id=_text_or_none(values.get("vision_prompt_id")) or settings.vision_prompt_id,
        vision_prompt=_text_or_none(values.get("vision_prompt")) or settings.vision_prompt,
        vision_system_prompt=(
            _text_or_none(values.get("vision_system_prompt")) or settings.vision_system_prompt
        ),
        vision_sample_ms=_int_or_default(values.get("vision_sample_ms"), settings.vision_sample_ms),
        vision_min_duration_ms=_int_or_default(
            values.get("vision_min_duration_ms"),
            settings.vision_min_duration_ms,
        ),
        vision_api_configs_path=(
            _coerce_path(values.get("vision_api_configs_path")) or settings.vision_api_configs_path
        ),
        vision_prompts_path=(
            _coerce_path(values.get("vision_prompts_path")) or settings.vision_prompts_path
        ),
        transcription_presets_path=(
            _coerce_path(values.get("transcription_presets_path")) or settings.transcription_presets_path
        ),
        keep_files=not _bool_value(values.get("no_keep_files")),
        resume_workdir=_coerce_path(values.get("resume_workdir")),
        resume_stage=_text_or_none(values.get("resume_stage")),
        summary_prompt_id=_text_or_none(values.get("summary_prompt_id")) or settings.summary_prompt_id,
        summary_system_prompt=(
            _text_or_none(values.get("summary_system_prompt")) or settings.summary_system_prompt
        ),
        summary_user_prompt=(
            _text_or_none(values.get("summary_user_prompt")) or settings.summary_user_prompt
        ),
        summary_prompts_path=(
            _coerce_path(values.get("summary_prompts_path")) or settings.summary_prompts_path
        ),
        summary_providers_path=(
            _coerce_path(values.get("summary_providers_path")) or settings.summary_providers_path
        ),
    )


def _require_text(values: Mapping[str, Any], key: str) -> str:
    value = _text_or_none(values.get(key))
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_path(value: Any) -> Path | None:
    text = _text_or_none(value)
    if not text:
        return None
    return Path(text).expanduser()


def _int_or_default(value: Any, default: int) -> int:
    if value in {None, ""}:
        return default
    return int(value)


def _int_or_optional(value: Any, default: int | None) -> int | None:
    if value in {None, ""}:
        return default
    return int(value)


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "on"}
