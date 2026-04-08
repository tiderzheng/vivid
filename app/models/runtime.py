from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RuntimeOptions:
    source: str
    project_name: str | None
    data_dir: Path
    output_format: str
    whisper_model: str
    forced_platform: str | None
    ffmpeg_bin: str
    whisper_root: Path | None
    ears4_api: str
    eyes_api: str
    language: str
    transcription_preset_id: str | None
    acquisition_mode: str
    transcription_backend: str
    transcription_device: str | None
    transcription_task: str | None
    transcription_extract_audio: bool | None
    transcription_output_dir: Path | None
    transcribe_timeout: int
    ocr_timeout: int
    llm_max_chars: int
    siliconflow_api_key: str | None
    dashscope_api_key: str | None
    siliconflow_base_url: str
    dashscope_base_url: str
    siliconflow_model: str
    dashscope_model: str
    bili_script: Path | None
    douyin_script: Path | None
    vision_api_config_id: str | None
    vision_backend: str
    vision_api_base: str | None
    vision_api_path: str | None
    vision_api_key: str | None
    vision_model: str | None
    vision_timeout: int | None
    vision_prompt_id: str | None
    vision_prompt: str | None
    vision_system_prompt: str | None
    vision_sample_ms: int
    vision_min_duration_ms: int
    vision_api_configs_path: Path
    vision_prompts_path: Path
    transcription_presets_path: Path
    keep_files: bool
    resume_workdir: Path | None = None
    resume_stage: str | None = None
    summary_prompt_id: str | None = None
    summary_system_prompt: str | None = None
    summary_user_prompt: str | None = None
    summary_prompts_path: Path | None = None
    summary_providers_path: Path | None = None
