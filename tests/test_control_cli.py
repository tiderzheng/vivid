import json
from pathlib import Path

from app.config import Settings
from app.control_cli import _run_quickread, build_doctor_payload, build_parser, build_paths_payload
from app.exceptions import BilibiliSessdataExpiredError
from app.services.cloud_bridge import CloudQuickreadError


def _build_settings(tmp_path: Path) -> Settings:
    bili = tmp_path / "bili.py"
    douyin = tmp_path / "douyin.js"
    bili.write_text("# helper", encoding="utf-8")
    douyin.write_text("// helper", encoding="utf-8")
    vision_api_configs = tmp_path / "configs" / "vision" / "api_configs.json"
    vision_prompts = tmp_path / "configs" / "vision" / "prompts.json"
    transcription_presets = tmp_path / "configs" / "transcription" / "presets.json"
    summary_prompts = tmp_path / "configs" / "summary" / "prompts.json"
    summary_providers = tmp_path / "configs" / "summary" / "providers.json"
    for path in [vision_api_configs, vision_prompts, transcription_presets, summary_prompts, summary_providers]:
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
        summary_prompts_path=summary_prompts,
        summary_providers_path=summary_providers,
    )


def test_build_paths_payload_includes_shell_scripts(tmp_path):
    settings = _build_settings(tmp_path)
    payload = build_paths_payload(settings)
    assert payload["scripts"]["vivid_tool_sh"].endswith("vivid_tool.sh")
    assert payload["skill"]["wrapper_sh"].endswith("vivid_operator.sh")
    assert payload["skill"]["skill_state"].endswith("skill\\vivid-operator\\state\\skill_state.json")
    assert payload["skill"]["repo_root_state"].endswith("skill\\vivid-operator\\state\\skill_state.json")
    assert payload["skill"]["execution_modes"] == ["local", "cloud"]
    assert payload["skill"]["artifact_targets"] == ["local_only", "cloud_only", "both"]
    assert payload["tools"]["helper_paths"]["bili"].endswith("bili.py")
    assert payload["tools"]["helper_paths"]["douyin"].endswith("douyin.js")
    assert payload["configs"]["summary"]["providers"].endswith("configs\\summary\\providers.json")


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
    assert payload["checks"]["torch"]["required"] is False
    assert payload["checks"]["bili_helper"]["exists"] is True
    assert payload["checks"]["douyin_helper"]["exists"] is True


def test_build_doctor_payload_treats_node_and_opencv_as_optional(tmp_path, monkeypatch):
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
            "ok": False,
            "package": "opencv-python",
            "installed": False,
            "already_available": False,
            "index_url": "https://mirrors.aliyun.com/pypi/simple/",
        },
    )

    def fake_which(name: str) -> str | None:
        if name == "node":
            return None
        return name

    monkeypatch.setattr("app.control_cli.shutil.which", fake_which)
    monkeypatch.setattr("app.control_cli._module_available", lambda name: True)
    payload = build_doctor_payload(settings)
    assert payload["ok"] is True
    assert payload["checks"]["node"]["required"] is False
    assert payload["checks"]["opencv"]["required"] is False


def test_build_doctor_payload_treats_torch_as_optional(tmp_path, monkeypatch):
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
            "installed": True,
            "already_available": True,
            "index_url": "https://mirrors.aliyun.com/pypi/simple/",
        },
    )

    def fake_module_available(name: str) -> bool:
        return name != "torch"

    monkeypatch.setattr("app.control_cli.shutil.which", lambda name: name)
    monkeypatch.setattr("app.control_cli._module_available", fake_module_available)
    payload = build_doctor_payload(settings)

    assert payload["ok"] is True
    assert payload["checks"]["torch"]["available"] is False
    assert payload["checks"]["torch"]["required"] is False


def test_run_quickread_returns_structured_sessdata_refresh_payload(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(
        [
            "quickread",
            "--source",
            "https://www.bilibili.com/video/BV1xx",
            "--sessdata",
            "expired",
        ]
    )

    monkeypatch.setattr("app.control_cli.build_runtime_options", lambda *_args, **_kwargs: object())

    def fake_run_quickread(options, pause_on_bili_sessdata_expired=False):
        assert pause_on_bili_sessdata_expired is True
        raise BilibiliSessdataExpiredError("api error -101: 账号未登录")

    monkeypatch.setattr("app.control_cli.run_quickread", fake_run_quickread)

    exit_code = _run_quickread(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["error_code"] == "bili_sessdata_expired"
    assert payload["requires_user_input"] is True
    assert payload["can_continue_without_sessdata"] is True
    assert payload["sessdata_supplied"] is True


def test_run_quickread_payload_includes_no_sessdata_flag(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(
        [
            "quickread",
            "--source",
            "https://www.bilibili.com/video/BV1xx",
            "--no-sessdata",
        ]
    )

    monkeypatch.setattr("app.control_cli.build_runtime_options", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "app.control_cli.run_quickread",
        lambda *args, **kwargs: type("Result", (), {"to_dict": lambda self: {"error_summary": None}})(),
    )

    exit_code = _run_quickread(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["no_sessdata"] is True


def test_run_quickread_cloud_mode_uses_cloud_executor(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(
        [
            "quickread",
            "--source",
            "https://example.com/video",
            "--execution-mode",
            "cloud",
            "--artifact-target",
            "both",
            "--cloud-profile",
            "prod",
            "--cloud-base-url",
            "https://cloud.example",
        ]
    )

    monkeypatch.setattr(
        "app.control_cli.run_cloud_quickread",
        lambda args, settings: {
            "ok": True,
            "source": args.source,
            "execution_mode": args.execution_mode,
            "artifact_target": args.artifact_target,
            "cloud_profile": args.cloud_profile,
            "cloud_base_url": args.cloud_base_url,
        },
    )

    exit_code = _run_quickread(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["execution_mode"] == "cloud"
    assert payload["artifact_target"] == "both"
    assert payload["cloud_profile"] == "prod"
    assert payload["cloud_base_url"] == "https://cloud.example"


def test_run_quickread_cloud_mode_preserves_structured_remote_error(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(
        [
            "quickread",
            "--source",
            "https://www.bilibili.com/video/BV1xx",
            "--execution-mode",
            "cloud",
            "--cloud-base-url",
            "https://cloud.example",
        ]
    )

    monkeypatch.setattr(
        "app.control_cli.run_cloud_quickread",
        lambda args, settings: (_ for _ in ()).throw(
            CloudQuickreadError(
                {
                    "ok": False,
                    "error": "api error -101: 账号未登录",
                    "error_code": "bili_sessdata_expired",
                    "requires_user_input": True,
                    "user_prompt": "请提供新的 SESSDATA",
                    "can_continue_without_sessdata": True,
                }
            )
        ),
    )

    exit_code = _run_quickread(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["execution_mode"] == "cloud"
    assert payload["error_code"] == "bili_sessdata_expired"
    assert payload["requires_user_input"] is True
    assert payload["can_continue_without_sessdata"] is True
