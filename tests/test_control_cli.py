import json
from pathlib import Path

from app.cli import build_parser as build_app_parser
from app.cli import main as app_cli_main
from app.config import Settings
from app.control_cli import _handle_bili_auth_action, _run_quickread, build_doctor_payload, build_parser, build_paths_payload
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
        default_model="large-v3-turbo",
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


def test_build_doctor_payload_reports_faster_whisper_and_helpers(tmp_path, monkeypatch):
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
    monkeypatch.setattr("app.control_cli._module_imports", lambda name: True)
    payload = build_doctor_payload(settings)
    assert payload["ok"] is True
    assert payload["checks"]["faster_whisper"]["available"] is True
    assert payload["checks"]["faster_whisper"]["required"] is True
    assert payload["checks"]["ctranslate2"]["available"] is True
    assert payload["checks"]["ctranslate2"]["required"] is True
    assert payload["checks"]["funasr"]["available"] is True
    assert payload["checks"]["funasr"]["required"] is True
    assert payload["checks"]["modelscope"]["available"] is True
    assert payload["checks"]["modelscope"]["required"] is True
    assert payload["checks"]["torch"]["available"] is True
    assert payload["checks"]["torch"]["required"] is True
    assert payload["checks"]["torchaudio"]["available"] is True
    assert payload["checks"]["torchaudio"]["required"] is True
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
    monkeypatch.setattr("app.control_cli._module_imports", lambda name: True)
    payload = build_doctor_payload(settings)
    assert payload["ok"] is True
    assert payload["checks"]["node"]["required"] is False
    assert payload["checks"]["opencv"]["required"] is False


def test_build_doctor_payload_requires_ctranslate2(tmp_path, monkeypatch):
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
        return name != "ctranslate2"

    monkeypatch.setattr("app.control_cli.shutil.which", lambda name: name)
    monkeypatch.setattr("app.control_cli._module_available", fake_module_available)
    monkeypatch.setattr("app.control_cli._module_imports", lambda name: True)
    payload = build_doctor_payload(settings)

    assert payload["ok"] is False
    assert payload["checks"]["ctranslate2"]["available"] is False
    assert payload["checks"]["ctranslate2"]["required"] is True


def test_build_doctor_payload_requires_funasr_for_paraformer(tmp_path, monkeypatch):
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
        return name != "funasr"

    monkeypatch.setattr("app.control_cli.shutil.which", lambda name: name)
    monkeypatch.setattr("app.control_cli._module_available", fake_module_available)
    monkeypatch.setattr("app.control_cli._module_imports", lambda name: True)
    payload = build_doctor_payload(settings)

    assert payload["ok"] is False
    assert payload["checks"]["funasr"]["available"] is False
    assert payload["checks"]["funasr"]["required"] is True


def test_build_doctor_payload_requires_importable_torchaudio(tmp_path, monkeypatch):
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
    monkeypatch.setattr("app.control_cli.shutil.which", lambda name: name)
    monkeypatch.setattr("app.control_cli._module_available", lambda name: True)
    monkeypatch.setattr("app.control_cli._module_imports", lambda name: name != "torchaudio")
    payload = build_doctor_payload(settings)

    assert payload["ok"] is False
    assert payload["checks"]["torchaudio"]["available"] is False
    assert payload["checks"]["torchaudio"]["required"] is True


def test_quickread_parser_accepts_legacy_sessdata_flags():
    parser = build_parser()
    args = parser.parse_args(
        [
            "quickread",
            "--source",
            "https://www.bilibili.com/video/BV1xx",
            "--sessdata",
            "expired",
            "--no-sessdata",
        ]
    )

    assert args.sessdata == "expired"
    assert args.no_sessdata is True


def test_app_cli_parser_accepts_bili_cookie_flag():
    parser = build_app_parser()
    args = parser.parse_args(
        [
            "https://www.bilibili.com/video/BV1xx",
            "--bili-cookie",
            "SESSDATA=demo; bili_jct=token",
        ]
    )

    assert args.bili_cookie == "SESSDATA=demo; bili_jct=token"


def test_app_cli_parser_accepts_legacy_sessdata_flag():
    parser = build_app_parser()
    args = parser.parse_args(
        [
            "https://www.bilibili.com/video/BV1xx",
            "--sessdata",
            "expired",
            "--no-sessdata",
        ]
    )

    assert args.sessdata == "expired"
    assert args.no_sessdata is True


def test_app_cli_persists_explicit_bili_cookie(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    captured = {}

    def fake_build_runtime_options(_settings, values):
        captured["values"] = values
        return object()

    monkeypatch.setattr(
        "sys.argv",
        [
            "vivid",
            "https://www.bilibili.com/video/BV1xx",
            "--bili-cookie",
            "SESSDATA=demo; bili_jct=token",
            "--json",
        ],
    )
    monkeypatch.setattr("app.cli.load_settings", lambda: settings)
    monkeypatch.setattr("app.cli.ensure_opencv_dependency", lambda raise_on_failure=False: {"ok": True})
    monkeypatch.setattr("app.cli.build_runtime_options", fake_build_runtime_options)
    monkeypatch.setattr(
        "app.cli.save_bili_cookie",
        lambda repo_root, cookie, source="unknown": captured.update(
            {
                "saved_repo_root": repo_root,
                "saved_cookie": cookie,
                "saved_source": source,
            }
        ),
    )
    monkeypatch.setattr(
        "app.cli.run_quickread",
        lambda _options: type("Result", (), {"to_dict": lambda self: {"ok": True}})(),
    )

    exit_code = app_cli_main()

    assert exit_code == 0
    assert captured["values"]["bili_cookie"] == "SESSDATA=demo; bili_jct=token"
    assert captured["saved_repo_root"] == tmp_path
    assert captured["saved_cookie"] == "SESSDATA=demo; bili_jct=token"
    assert captured["saved_source"] == "cli"
    assert "SESSDATA=demo" not in capsys.readouterr().out


def test_app_cli_keeps_running_when_bili_cookie_persistence_fails(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    captured = {}

    def fake_build_runtime_options(_settings, values):
        captured["values"] = values
        return object()

    monkeypatch.setattr(
        "sys.argv",
        [
            "vivid",
            "https://www.bilibili.com/video/BV1xx",
            "--bili-cookie",
            "SESSDATA=demo; bili_jct=token",
            "--json",
        ],
    )
    monkeypatch.setattr("app.cli.load_settings", lambda: settings)
    monkeypatch.setattr("app.cli.ensure_opencv_dependency", lambda raise_on_failure=False: {"ok": True})
    monkeypatch.setattr("app.cli.build_runtime_options", fake_build_runtime_options)
    monkeypatch.setattr(
        "app.cli.save_bili_cookie",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("secret file is locked")),
    )
    monkeypatch.setattr(
        "app.cli.run_quickread",
        lambda _options: type("Result", (), {"to_dict": lambda self: {"ok": True}})(),
    )

    exit_code = app_cli_main()

    assert exit_code == 0
    assert captured["values"]["bili_cookie"] == "SESSDATA=demo; bili_jct=token"
    assert "secret file is locked" not in capsys.readouterr().out


def test_quickread_parser_accepts_bili_cookie_flag():
    parser = build_parser()
    args = parser.parse_args(
        [
            "quickread",
            "--source",
            "https://www.bilibili.com/video/BV1xx",
            "--bili-cookie",
            "SESSDATA=demo; bili_jct=token",
        ]
    )

    assert args.bili_cookie == "SESSDATA=demo; bili_jct=token"


def test_run_quickread_forwards_bili_cookie_without_exposing_it(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(
        [
            "quickread",
            "--source",
            "https://www.bilibili.com/video/BV1xx",
            "--bili-cookie",
            "SESSDATA=demo; bili_jct=token",
        ]
    )
    captured = {}

    def fake_build_runtime_options(_settings, values):
        captured["values"] = values
        return object()

    monkeypatch.setattr("app.control_cli.build_runtime_options", fake_build_runtime_options)
    monkeypatch.setattr(
        "app.control_cli.save_bili_cookie",
        lambda repo_root, cookie, source="unknown": captured.update(
            {
                "saved_repo_root": repo_root,
                "saved_cookie": cookie,
                "saved_source": source,
            }
        ),
    )
    monkeypatch.setattr(
        "app.control_cli.run_quickread",
        lambda *args, **kwargs: type("Result", (), {"to_dict": lambda self: {"error_summary": None}})(),
    )

    exit_code = _run_quickread(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["values"]["bili_cookie"] == "SESSDATA=demo; bili_jct=token"
    assert captured["saved_repo_root"] == tmp_path
    assert captured["saved_cookie"] == "SESSDATA=demo; bili_jct=token"
    assert captured["saved_source"] == "control_cli"
    assert "bili_cookie" not in payload
    assert "sessdata" not in captured["values"]
    assert "no_sessdata" not in captured["values"]


def test_run_quickread_forwards_legacy_sessdata_without_exposing_it(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(
        [
            "quickread",
            "--source",
            "https://www.bilibili.com/video/BV1xx",
            "--sessdata",
            "fresh-cookie",
            "--no-sessdata",
        ]
    )
    captured = {}

    def fake_build_runtime_options(_settings, values):
        captured["values"] = values
        return object()

    monkeypatch.setattr("app.control_cli.build_runtime_options", fake_build_runtime_options)
    monkeypatch.setattr(
        "app.control_cli.run_quickread",
        lambda *args, **kwargs: type("Result", (), {"to_dict": lambda self: {"error_summary": None}})(),
    )

    exit_code = _run_quickread(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert captured["values"]["sessdata"] == "fresh-cookie"
    assert captured["values"]["no_sessdata"] is True
    assert "sessdata" not in payload
    assert "no_sessdata" not in payload


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
                    "error": "remote unavailable",
                    "error_code": "cloud_unavailable",
                }
            )
        ),
    )

    exit_code = _run_quickread(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["execution_mode"] == "cloud"
    assert payload["error_code"] == "cloud_unavailable"
    assert "can_continue_without_sessdata" not in payload


def test_bili_auth_status_cli_outputs_public_payload(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(["bili-auth-status"])

    class FakeStatus:
        def to_public_dict(self):
            return {
                "is_login": True,
                "cookie_present": True,
                "uname": "tester",
                "mid": 42,
            }

    monkeypatch.setattr("app.control_cli.get_bili_login_status", lambda repo_root: FakeStatus())

    exit_code = _handle_bili_auth_action(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {
        "action": "bili-auth-status",
        "ok": True,
        "status": {
            "is_login": True,
            "cookie_present": True,
            "uname": "tester",
            "mid": 42,
        },
    }
    assert "SESSDATA" not in json.dumps(payload)


def test_bili_auth_qrcode_cli_outputs_key_and_url(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(["bili-auth-qrcode"])

    class FakeQrCode:
        def to_public_dict(self):
            return {
                "qrcode_key": "abc",
                "url": "https://passport.bilibili.com/login?qrcode_key=abc",
                "status": "waiting_for_scan",
            }

    monkeypatch.setattr("app.control_cli.generate_bili_qrcode", lambda: FakeQrCode())

    exit_code = _handle_bili_auth_action(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["action"] == "bili-auth-qrcode"
    assert payload["ok"] is True
    assert payload["qrcode"]["qrcode_key"] == "abc"


def test_bili_auth_poll_cli_reports_pending_without_error(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(["bili-auth-poll", "--qrcode-key", "abc"])

    from app.services.bili_auth import BiliQrCodePending

    monkeypatch.setattr(
        "app.control_cli.poll_bili_qrcode",
        lambda repo_root, qrcode_key: (_ for _ in ()).throw(BiliQrCodePending("waiting for scan")),
    )

    exit_code = _handle_bili_auth_action(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {
        "action": "bili-auth-poll",
        "ok": False,
        "status": "waiting_for_scan",
        "message": "waiting for scan",
    }


def test_bili_auth_logout_cli_clears_cookie(tmp_path, monkeypatch, capsys):
    settings = _build_settings(tmp_path)
    args = build_parser().parse_args(["bili-auth-logout"])

    class FakeLogout:
        def to_public_dict(self):
            return {"ok": True, "cleared": True, "message": "ok"}

    monkeypatch.setattr("app.control_cli.logout_bili", lambda repo_root: FakeLogout())

    exit_code = _handle_bili_auth_action(args, settings)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {
        "action": "bili-auth-logout",
        "ok": True,
        "logout": {"ok": True, "cleared": True, "message": "ok"},
    }
