from pathlib import Path

from app.config import Settings
from app.control_cli import build_doctor_payload, build_paths_payload


def _build_settings(tmp_path: Path) -> Settings:
    bili = tmp_path / "bili.py"
    douyin = tmp_path / "douyin.js"
    bili.write_text("# helper", encoding="utf-8")
    douyin.write_text("// helper", encoding="utf-8")
    vision_api_configs = tmp_path / "configs" / "vision" / "api_configs.json"
    vision_prompts = tmp_path / "configs" / "vision" / "prompts.json"
    transcription_presets = tmp_path / "configs" / "transcription" / "presets.json"
    for path in [vision_api_configs, vision_prompts, transcription_presets]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    return Settings(
        repo_root=tmp_path,
        tools_root=tmp_path.parent,
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
        bili_sessdata=None,
        bili_script=bili,
        douyin_script=douyin,
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
        vision_api_configs_path=vision_api_configs,
        vision_prompts_path=vision_prompts,
        transcription_presets_path=transcription_presets,
    )


def test_build_paths_payload_includes_shell_scripts(tmp_path):
    settings = _build_settings(tmp_path)
    payload = build_paths_payload(settings)
    assert payload["scripts"]["vivid_tool_sh"].endswith("vivid_tool.sh")
    assert payload["skill"]["wrapper_sh"].endswith("vivid_operator.sh")
    assert payload["tools"]["helper_paths"]["bili"].endswith("bili.py")


def test_build_doctor_payload_reports_torch_and_helpers(tmp_path, monkeypatch):
    settings = _build_settings(tmp_path)
    monkeypatch.setattr(
        "app.control_cli.inspect_ffmpeg",
        lambda preferred, repo_root, tools_root: {
            "available": True,
            "resolved": "ffmpeg",
            "source": "path",
            "candidates": ["ffmpeg"],
        },
    )
    monkeypatch.setattr(
        "app.control_cli.ensure_opencv_dependency",
        lambda raise_on_failure=False: {
            "ok": True,
            "package": "opencv-python",
            "installed": False,
            "already_available": True,
            "index_url": "https://mirrors.aliyun.com/pypi/simple/",
        },
    )
    monkeypatch.setattr("app.control_cli.shutil.which", lambda name: name)
    monkeypatch.setattr("app.control_cli._module_available", lambda name: True)
    payload = build_doctor_payload(settings)
    assert payload["ok"] is True
    assert payload["checks"]["torch"]["available"] is True
    assert payload["checks"]["bili_helper"]["exists"] is True
    assert payload["checks"]["douyin_helper"]["exists"] is True
