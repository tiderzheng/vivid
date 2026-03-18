from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .constants import (
    DEFAULT_DASHSCOPE_BASE,
    DEFAULT_EARS4_API,
    DEFAULT_EYES_API,
    DEFAULT_FORMAT,
    DEFAULT_MODEL,
    DEFAULT_SILICONFLOW_BASE,
)
from .services.ffmpeg_locator import resolve_ffmpeg_bin


@dataclass(slots=True)
class Settings:
    repo_root: Path
    tools_root: Path
    data_dir: Path
    ffmpeg_bin: str
    whisper_root: Path | None
    ears4_api: str
    eyes_api: str
    default_format: str
    default_model: str
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
    siliconflow_base_url: str
    dashscope_base_url: str
    siliconflow_model: str
    dashscope_model: str
    siliconflow_api_key: str | None
    dashscope_api_key: str | None
    bili_sessdata: str | None
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
    summary_prompt_id: str | None = None
    summary_system_prompt: str | None = None
    summary_user_prompt: str | None = None
    summary_prompts_path: Path | None = None


def load_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[1]
    tools_root = repo_root.parent
    data_dir = Path(os.environ.get("VIVID_DATA_DIR", "data")).expanduser()
    return Settings(
        repo_root=repo_root,
        tools_root=tools_root,
        data_dir=data_dir,
        ffmpeg_bin=resolve_ffmpeg_bin(
            os.environ.get("VIVID_FFMPEG_BIN"),
            repo_root=repo_root,
            tools_root=tools_root,
        ),
        whisper_root=Path(os.environ["VIVID_WHISPER_ROOT"]).expanduser()
        if os.environ.get("VIVID_WHISPER_ROOT")
        else None,
        ears4_api=os.environ.get("EARS4_API", DEFAULT_EARS4_API).rstrip("/"),
        eyes_api=os.environ.get("EYES_API", DEFAULT_EYES_API).rstrip("/"),
        default_format=os.environ.get("VIVID_DEFAULT_FORMAT", DEFAULT_FORMAT),
        default_model=os.environ.get("VIVID_DEFAULT_MODEL", DEFAULT_MODEL),
        language=os.environ.get("VIVID_LANGUAGE", "zh"),
        transcription_preset_id=os.environ.get("VIVID_TRANSCRIPTION_PRESET_ID") or None,
        acquisition_mode=os.environ.get("VIVID_ACQUISITION_MODE", "auto"),
        transcription_backend=os.environ.get("VIVID_TRANSCRIPTION_BACKEND", "auto"),
        transcription_device=os.environ.get("VIVID_TRANSCRIPTION_DEVICE") or None,
        transcription_task=os.environ.get("VIVID_TRANSCRIPTION_TASK") or None,
        transcription_extract_audio=(
            os.environ.get("VIVID_TRANSCRIPTION_EXTRACT_AUDIO", "").strip().lower() == "true"
            if os.environ.get("VIVID_TRANSCRIPTION_EXTRACT_AUDIO") is not None
            else None
        ),
        transcription_output_dir=Path(os.environ["VIVID_TRANSCRIPTION_OUTPUT_DIR"]).expanduser()
        if os.environ.get("VIVID_TRANSCRIPTION_OUTPUT_DIR")
        else None,
        transcribe_timeout=int(os.environ.get("VIVID_TRANSCRIBE_TIMEOUT", "1800")),
        ocr_timeout=int(os.environ.get("VIVID_OCR_TIMEOUT", "1800")),
        llm_max_chars=int(os.environ.get("VIVID_LLM_MAX_CHARS", "8000")),
        siliconflow_base_url=os.environ.get("SILICONFLOW_BASE_URL", DEFAULT_SILICONFLOW_BASE),
        dashscope_base_url=os.environ.get("DASHSCOPE_BASE_URL", DEFAULT_DASHSCOPE_BASE),
        siliconflow_model=os.environ.get("VIVID_SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3.2"),
        dashscope_model=os.environ.get("VIVID_DASHSCOPE_MODEL", "qwen-plus"),
        siliconflow_api_key=os.environ.get("SILICONFLOW_API_KEY") or None,
        dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY") or None,
        bili_sessdata=os.environ.get("BILI_SESSDATA") or None,
        bili_script=Path(
            os.environ.get(
                "VIVID_BILI_SCRIPT",
                str(repo_root / "tools" / "bilibili" / "bili23_agent_cli.py"),
            )
        ),
        douyin_script=Path(
            os.environ.get(
                "VIVID_DOUYIN_SCRIPT",
                str(repo_root / "tools" / "douyin" / "douyin.js"),
            )
        ),
        vision_api_config_id=os.environ.get("VIVID_VISION_API_CONFIG_ID") or None,
        vision_backend=os.environ.get("VIVID_VISION_BACKEND", "auto"),
        vision_api_base=os.environ.get("VIVID_VISION_API_BASE") or None,
        vision_api_path=os.environ.get("VIVID_VISION_API_PATH") or None,
        vision_api_key=os.environ.get("VIVID_VISION_API_KEY") or None,
        vision_model=os.environ.get("VIVID_VISION_MODEL") or None,
        vision_timeout=(
            int(os.environ["VIVID_VISION_TIMEOUT"])
            if os.environ.get("VIVID_VISION_TIMEOUT")
            else None
        ),
        vision_prompt_id=os.environ.get("VIVID_VISION_PROMPT_ID") or None,
        vision_prompt=os.environ.get("VIVID_VISION_PROMPT") or None,
        vision_system_prompt=os.environ.get("VIVID_VISION_SYSTEM_PROMPT") or None,
        vision_sample_ms=int(os.environ.get("VIVID_VISION_SAMPLE_MS", "800")),
        vision_min_duration_ms=int(os.environ.get("VIVID_VISION_MIN_DURATION_MS", "1200")),
        vision_api_configs_path=Path(
            os.environ.get(
                "VIVID_VISION_API_CONFIGS_FILE",
                str(repo_root / "configs" / "vision" / "api_configs.json"),
            )
        ),
        vision_prompts_path=Path(
            os.environ.get(
                "VIVID_VISION_PROMPTS_FILE",
                str(repo_root / "configs" / "vision" / "prompts.json"),
            )
        ),
        transcription_presets_path=Path(
            os.environ.get(
                "VIVID_TRANSCRIPTION_PRESETS_FILE",
                str(repo_root / "configs" / "transcription" / "presets.json"),
            )
        ),
        summary_prompt_id=os.environ.get("VIVID_SUMMARY_PROMPT_ID") or None,
        summary_system_prompt=os.environ.get("VIVID_SUMMARY_SYSTEM_PROMPT") or None,
        summary_user_prompt=os.environ.get("VIVID_SUMMARY_USER_PROMPT") or None,
        summary_prompts_path=Path(
            os.environ.get(
                "VIVID_SUMMARY_PROMPTS_FILE",
                str(repo_root / "configs" / "summary" / "prompts.json"),
            )
        ),
    )
