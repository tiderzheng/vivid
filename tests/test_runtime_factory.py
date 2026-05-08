from pathlib import Path

from app.config import Settings, load_settings
from app.runtime_factory import build_runtime_options
from app.services.bili_cookie_store import save_bili_cookie


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
        bili_cookie=None,
        sessdata=None,
    )


def test_load_settings_reads_bili_cookie_and_sessdata_env(monkeypatch):
    monkeypatch.setenv("VIVID_BILI_COOKIE", "cookie-from-env")
    monkeypatch.setenv("BILI_SESSDATA", "sessdata-from-env")

    settings = load_settings()

    assert settings.bili_cookie == "cookie-from-env"
    assert settings.sessdata == "sessdata-from-env"


def test_load_settings_reads_persisted_bili_cookie_when_env_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("VIVID_BILI_COOKIE", raising=False)
    monkeypatch.delenv("BILI_SESSDATA", raising=False)
    import app.config as config

    monkeypatch.setattr(config, "__file__", str(tmp_path / "app" / "config.py"))
    save_bili_cookie(tmp_path, "SESSDATA=persisted; bili_jct=token", source="test")

    settings = config.load_settings()

    assert settings.repo_root == tmp_path
    assert settings.bili_cookie == "SESSDATA=persisted; bili_jct=token"


def test_load_settings_prefers_env_bili_cookie_over_persisted_cookie(monkeypatch, tmp_path):
    monkeypatch.setenv("VIVID_BILI_COOKIE", "SESSDATA=env; bili_jct=token")
    import app.config as config

    monkeypatch.setattr(config, "__file__", str(tmp_path / "app" / "config.py"))
    save_bili_cookie(tmp_path, "SESSDATA=persisted; bili_jct=token", source="test")

    settings = config.load_settings()

    assert settings.bili_cookie == "SESSDATA=env; bili_jct=token"


def test_runtime_factory_prefers_explicit_bili_cookie_over_sessdata_sources(tmp_path):
    settings = _build_settings(tmp_path)

    options = build_runtime_options(
        settings,
        {
            "source": "https://www.bilibili.com/video/BV1xx",
            "forced_platform": "bilibili",
            "acquisition_mode": "smart",
            "bili_cookie": "cookie-from-values",
            "sessdata": "sessdata-from-values",
        },
    )

    assert options.forced_platform == "bilibili"
    assert options.acquisition_mode == "smart"
    assert options.bili_cookie == "cookie-from-values"
    assert options.sessdata == "sessdata-from-values"


def test_runtime_factory_maps_summary_openai_to_shared_llm_provider(tmp_path):
    settings = _build_settings(tmp_path)

    options = build_runtime_options(
        settings,
        {
            "source": "https://example.com/video",
            "summary_api_base": "https://llm.example.com/v1/chat/completions",
            "summary_api_key": "sk-summary",
            "summary_model": "demo-summary-model",
        },
    )

    assert options.siliconflow_base_url == "https://llm.example.com/v1/chat/completions"
    assert options.siliconflow_api_key == "sk-summary"
    assert options.siliconflow_model == "demo-summary-model"


def test_runtime_factory_uses_env_bili_cookie_before_explicit_sessdata(tmp_path):
    settings = _build_settings(tmp_path)
    settings.bili_cookie = "cookie-from-settings"
    settings.sessdata = "sessdata-from-settings"

    options = build_runtime_options(
        settings,
        {
            "source": "https://www.bilibili.com/video/BV1xx",
            "sessdata": "sessdata-from-values",
        },
    )

    assert options.bili_cookie == "cookie-from-settings"
    assert options.sessdata == "sessdata-from-values"


def test_runtime_factory_wraps_legacy_sessdata_into_bili_cookie(tmp_path):
    settings = _build_settings(tmp_path)
    settings.sessdata = "legacy-sessdata"

    options = build_runtime_options(
        settings,
        {
            "source": "https://www.bilibili.com/video/BV1xx",
        },
    )

    assert options.bili_cookie == "SESSDATA=legacy-sessdata"
    assert options.sessdata == "legacy-sessdata"


def test_runtime_factory_no_sessdata_disables_legacy_fallback(tmp_path):
    settings = _build_settings(tmp_path)
    settings.bili_cookie = None
    settings.sessdata = "legacy-sessdata"

    options = build_runtime_options(
        settings,
        {
            "source": "https://www.bilibili.com/video/BV1xx",
            "no_sessdata": True,
        },
    )

    assert options.bili_cookie is None
    assert options.sessdata == ""
