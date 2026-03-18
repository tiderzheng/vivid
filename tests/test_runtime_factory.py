from pathlib import Path

from app.config import Settings
from app.runtime_factory import build_runtime_options


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
        siliconflow_base_url="https://example.com/sf",
        dashscope_base_url="https://example.com/ds",
        siliconflow_model="model-a",
        dashscope_model="model-b",
        siliconflow_api_key=None,
        dashscope_api_key=None,
        bili_sessdata="env-sessdata",
        bili_script=tmp_path / "bili.py",
        douyin_script=tmp_path / "douyin.js",
        vision_api_config_id=None,
        vision_backend="internal",
        vision_api_base=None,
        vision_api_path=None,
        vision_api_key=None,
        vision_model=None,
        vision_timeout=60,
        vision_prompt_id=None,
        vision_prompt=None,
        vision_system_prompt=None,
        vision_sample_ms=800,
        vision_min_duration_ms=1200,
        vision_api_configs_path=tmp_path / "configs" / "vision" / "api_configs.json",
        vision_prompts_path=tmp_path / "configs" / "vision" / "prompts.json",
        transcription_presets_path=tmp_path / "configs" / "transcription" / "presets.json",
    )


def test_runtime_factory_uses_env_sessdata_by_default(tmp_path):
    settings = _build_settings(tmp_path)

    options = build_runtime_options(settings, {"source": "https://www.bilibili.com/video/BV1xx"})

    assert options.sessdata == "env-sessdata"


def test_runtime_factory_prefers_explicit_sessdata_over_env(tmp_path):
    settings = _build_settings(tmp_path)

    options = build_runtime_options(
        settings,
        {"source": "https://www.bilibili.com/video/BV1xx", "sessdata": "explicit-sessdata"},
    )

    assert options.sessdata == "explicit-sessdata"


def test_runtime_factory_can_explicitly_disable_env_sessdata(tmp_path):
    settings = _build_settings(tmp_path)

    options = build_runtime_options(
        settings,
        {"source": "https://www.bilibili.com/video/BV1xx", "no_sessdata": True},
    )

    assert options.sessdata is None


def test_runtime_factory_treats_explicit_blank_sessdata_as_disabled(tmp_path):
    settings = _build_settings(tmp_path)

    options = build_runtime_options(
        settings,
        {"source": "https://www.bilibili.com/video/BV1xx", "sessdata": ""},
    )

    assert options.sessdata is None
