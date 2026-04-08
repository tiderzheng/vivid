from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from .config import Settings, load_settings
from .pipeline.orchestrator import run_quickread
from .runtime_factory import build_runtime_options
from .services.cloud_bridge import CloudQuickreadError, run_cloud_quickread
from .services.dependency_bootstrap import ensure_opencv_dependency
from .services.ffmpeg_locator import inspect_ffmpeg
from .subsystems.transcription import TranscriptionPreset, load_transcription_store
from .subsystems.transcription.store import save_transcription_store
from .subsystems.vision import VisionApiConfig, VisionPromptItem, load_vision_store
from .subsystems.vision.store import save_vision_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vivid cross-platform control surface.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("paths")
    subparsers.add_parser("doctor")

    web_parser = subparsers.add_parser("web-ui")
    web_parser.add_argument("-UiHost", "--host", default="127.0.0.1")
    web_parser.add_argument("-Port", "--port", type=int, default=8765)

    quickread = subparsers.add_parser("quickread")
    quickread.add_argument("-Source", "--source", required=True)
    quickread.add_argument("-ProjectName", "--project-name")
    quickread.add_argument("-Format", "--format", default="both", choices=["transcript", "summary", "both"])
    quickread.add_argument("-DataDir", "--data-dir")
    quickread.add_argument("-Platform", "--platform", choices=["bilibili", "douyin", "youtube", "generic", "local"])
    quickread.add_argument("-Model", "--model", choices=["tiny", "base", "small", "medium", "large"])
    quickread.add_argument("-ExecutionMode", "--execution-mode", choices=["local", "cloud"], default="local")
    quickread.add_argument(
        "-ArtifactTarget",
        "--artifact-target",
        choices=["local_only", "cloud_only", "both"],
        default="local_only",
    )
    quickread.add_argument("-CloudProfile", "--cloud-profile")
    quickread.add_argument("-CloudBaseUrl", "--cloud-base-url")
    quickread.add_argument("-Sessdata", "--sessdata", help=argparse.SUPPRESS)
    quickread.add_argument("-NoSessdata", "--no-sessdata", action="store_true", help=argparse.SUPPRESS)
    quickread.add_argument("-FfmpegBin", "--ffmpeg-bin")
    quickread.add_argument("-WhisperRoot", "--whisper-root")
    quickread.add_argument("-AcquisitionMode", "--acquisition-mode", choices=["auto", "smart", "prefer_ocr", "force_ocr"])
    quickread.add_argument("-PreferOcr", "--prefer-ocr", action="store_true")
    quickread.add_argument("-ForceOcr", "--force-ocr", action="store_true")
    quickread.add_argument("-TranscriptionBackend", "--transcription-backend", choices=["auto", "internal", "ears4_api"])
    quickread.add_argument("-VisionBackend", "--vision-backend", choices=["auto", "internal", "eyes_api"])
    quickread.add_argument("-TranscribeTimeout", "--transcribe-timeout", type=int)
    quickread.add_argument("-OcrTimeout", "--ocr-timeout", type=int)
    quickread.add_argument("-SummaryPromptId", "--summary-prompt-id")
    quickread.add_argument("-SummarySystemPrompt", "--summary-system-prompt")
    quickread.add_argument("-SummaryUserPrompt", "--summary-user-prompt")
    quickread.add_argument("-SummaryPromptsFile", "--summary-prompts-file")
    quickread.add_argument("-SummaryProvidersFile", "--summary-providers-file")
    quickread.add_argument("-VisionApiConfigId", "--vision-api-config-id")
    quickread.add_argument("-VisionTimeout", "--vision-timeout", type=int)
    quickread.add_argument("-VisionSampleMs", "--vision-sample-ms", type=int)
    quickread.add_argument("-VisionMinDurationMs", "--vision-min-duration-ms", type=int)
    quickread.add_argument("-NoKeepFiles", "--no-keep-files", action="store_true")

    subparsers.add_parser("vision-configs")
    subparsers.add_parser("vision-prompts")

    vision_select = subparsers.add_parser("vision-select-config")
    vision_select.add_argument("-Id", "--id", required=True)

    vision_upsert = subparsers.add_parser("vision-upsert-config")
    vision_upsert.add_argument("-Id", "--id", required=True)
    vision_upsert.add_argument("-Name", "--name", required=True)
    vision_upsert.add_argument("-ApiBase", "--api-base", required=True)
    vision_upsert.add_argument("-ApiPath", "--api-path", default="/v1/chat/completions")
    vision_upsert.add_argument("-Model", "--model", default="")
    vision_upsert.add_argument("-Timeout", "--timeout", type=int, default=30)
    vision_upsert.add_argument("-Group", "--group", default="default")
    vision_upsert.add_argument("-Note", "--note", default="")
    vision_upsert.add_argument("-Prompt", "--prompt", default="")
    vision_upsert.add_argument("-SystemPrompt", "--system-prompt", default="")
    vision_upsert.add_argument("-ApiKeyEnv", "--api-key-env", default="")

    vision_prompt = subparsers.add_parser("vision-upsert-prompt")
    vision_prompt.add_argument("-Id", "--id", required=True)
    vision_prompt.add_argument("-Name", "--name", required=True)
    vision_prompt.add_argument("-Content", "--content", required=True)

    subparsers.add_parser("transcription-presets")

    transcription_select = subparsers.add_parser("transcription-select-preset")
    transcription_select.add_argument("-Id", "--id", required=True)

    transcription_upsert = subparsers.add_parser("transcription-upsert-preset")
    transcription_upsert.add_argument("-Id", "--id", required=True)
    transcription_upsert.add_argument("-Name", "--name", required=True)
    transcription_upsert.add_argument("-Model", "--model", default="base")
    transcription_upsert.add_argument("-Device", "--device", default="auto")
    transcription_upsert.add_argument("-Language", "--language", default="zh")
    transcription_upsert.add_argument("-Task", "--task", default="transcribe")
    transcription_upsert.add_argument("-ExtractAudio", "--extract-audio", action="store_true")
    transcription_upsert.add_argument("-NoExtractAudio", "--no-extract-audio", action="store_true")
    transcription_upsert.add_argument("-Note", "--note", default="")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    settings = load_settings()

    if args.action == "paths":
        print(json.dumps(build_paths_payload(settings), ensure_ascii=False, indent=2))
        return 0
    if args.action == "doctor":
        print(json.dumps(build_doctor_payload(settings), ensure_ascii=False, indent=2))
        return 0
    if args.action == "web-ui":
        ensure_opencv_dependency(raise_on_failure=False)
        import uvicorn

        uvicorn.run("app.web:app", host=args.host, port=args.port)
        return 0
    if args.action == "quickread":
        return _run_quickread(args, settings)
    if args.action.startswith("vision-"):
        return _handle_vision_action(args, settings)
    if args.action.startswith("transcription-"):
        return _handle_transcription_action(args, settings)
    parser.error(f"Unsupported action: {args.action}")
    return 2


def build_paths_payload(settings: Settings) -> dict[str, Any]:
    scripts_root = settings.repo_root / "scripts"
    skill_root = settings.repo_root / "skill" / "vivid-operator"
    return {
        "action": "paths",
        "repo_root": str(settings.repo_root),
        "scripts": {
            "vivid_tool_ps1": str(scripts_root / "vivid_tool.ps1"),
            "vivid_tool_sh": str(scripts_root / "vivid_tool.sh"),
            "doctor_ps1": str(scripts_root / "doctor.ps1"),
            "doctor_sh": str(scripts_root / "doctor.sh"),
            "run_quickread_ps1": str(scripts_root / "run_quickread.ps1"),
            "run_quickread_sh": str(scripts_root / "run_quickread.sh"),
            "run_web_ui_ps1": str(scripts_root / "run_web_ui.ps1"),
            "run_web_ui_sh": str(scripts_root / "run_web_ui.sh"),
            "manage_vision_ps1": str(scripts_root / "manage_vision.ps1"),
            "manage_vision_sh": str(scripts_root / "manage_vision.sh"),
            "manage_transcription_ps1": str(scripts_root / "manage_transcription.ps1"),
            "manage_transcription_sh": str(scripts_root / "manage_transcription.sh"),
        },
        "skill": {
            "root": str(skill_root),
            "skill_md": str(skill_root / "SKILL.md"),
            "wrapper_ps1": str(skill_root / "scripts" / "vivid_operator.ps1"),
            "wrapper_sh": str(skill_root / "scripts" / "vivid_operator.sh"),
            "skill_state": str(skill_root / "state" / "skill_state.json"),
            "repo_root_state": str(skill_root / "state" / "skill_state.json"),
            "execution_modes": ["local", "cloud"],
            "artifact_targets": ["local_only", "cloud_only", "both"],
        },
        "data": {"default_root": str(settings.data_dir)},
        "runtime": {
            "ffmpeg_bin": settings.ffmpeg_bin,
            "whisper_root": str(settings.whisper_root) if settings.whisper_root else None,
            "default_model": settings.default_model,
            "acquisition_mode": settings.acquisition_mode,
            "transcription_backend": settings.transcription_backend,
            "vision_backend": settings.vision_backend,
            "cloud_base_url_env": "VIVID_CLOUD_BASE_URL",
            "cloud_profile_env": "VIVID_CLOUD_PROFILE",
            "cloud_profile_base_url_env_pattern": "VIVID_CLOUD_PROFILE_<PROFILE>_BASE_URL",
        },
        "configs": {
            "vision": {
                "root": str(settings.repo_root / "configs" / "vision"),
                "api_configs": str(settings.vision_api_configs_path),
                "prompts": str(settings.vision_prompts_path),
            },
            "summary": {
                "root": str(settings.repo_root / "configs" / "summary"),
                "prompts": str(settings.summary_prompts_path) if settings.summary_prompts_path else None,
                "providers": str(settings.summary_providers_path) if settings.summary_providers_path else None,
            },
            "transcription": {
                "root": str(settings.repo_root / "configs" / "transcription"),
                "presets": str(settings.transcription_presets_path),
            },
        },
        "subsystems": {
            "vision": str(settings.repo_root / "app" / "subsystems" / "vision"),
            "transcription": str(settings.repo_root / "app" / "subsystems" / "transcription"),
        },
        "tools": {
            "downloader": {
                "bilibili": "bili-downloader-agent",
                "douyin": "douyin-download-1.2.0",
                "generic": "yt_dlp_python",
            },
            "helper_scripts_required": True,
            "helper_paths": {
                "bili": str(settings.bili_script) if settings.bili_script else None,
                "douyin": str(settings.douyin_script) if settings.douyin_script else None,
            },
        },
    }


def build_doctor_payload(settings: Settings) -> dict[str, Any]:
    ffmpeg_info = inspect_ffmpeg(preferred=None, repo_root=settings.repo_root, tools_root=settings.tools_root)
    opencv_info = ensure_opencv_dependency(raise_on_failure=False)
    checks = {
        "python": {
            "available": True,
            "path": sys.executable,
            "name": "python",
            "required": True,
            "install_hint": "Install Python 3.10+",
        },
        "node": {
            "available": shutil.which("node") is not None,
            "path": shutil.which("node"),
            "name": "node",
            "required": False,
            "install_hint": "Install Node.js only if you need Douyin downloads",
        },
        "ffmpeg": {
            "available": bool(ffmpeg_info.get("available")),
            "path": ffmpeg_info.get("resolved"),
            "source": ffmpeg_info.get("source"),
            "candidates": ffmpeg_info.get("candidates"),
            "name": "ffmpeg",
            "required": True,
            "install_hint": "Install ffmpeg and add it to PATH or set VIVID_FFMPEG_BIN",
        },
        "requests": {
            "available": _module_available("requests"),
            "name": "requests",
            "required": True,
            "install_hint": "Run pip install -r requirements.txt",
        },
        "yt_dlp_python": {
            "available": _module_available("yt_dlp"),
            "name": "yt-dlp",
            "required": False,
            "install_hint": "Run pip install yt-dlp if you need generic site downloads",
        },
        "whisper": {
            "available": _module_available("whisper"),
            "name": "openai-whisper",
            "required": True,
            "install_hint": "Run pip install -r requirements.txt",
        },
        "torch": {
            "available": _module_available("torch"),
            "name": "torch",
            "required": False,
            "install_hint": "Only required for internal Whisper transcription; external API transcription can run without it",
        },
        "opencv": {
            "available": bool(opencv_info.get("ok")),
            "package": opencv_info.get("package"),
            "installed": opencv_info.get("installed"),
            "already_available": opencv_info.get("already_available"),
            "index_url": opencv_info.get("index_url"),
            "name": opencv_info.get("package") or "opencv-python",
            "required": False,
            "install_hint": "Only required for OCR paths; the app can install it on demand",
        },
        "vivid_data_dir": {"path": str(settings.data_dir)},
        "ffmpeg_bin": {"value": settings.ffmpeg_bin},
        "whisper_root": {
            "value": str(settings.whisper_root) if settings.whisper_root else None,
            "exists": settings.whisper_root.exists() if settings.whisper_root else None,
        },
        "acquisition_mode": {"value": settings.acquisition_mode},
        "transcription_backend": {"value": settings.transcription_backend},
        "vision_backend": {"value": settings.vision_backend},
        "ears4_api": {"url": settings.ears4_api},
        "eyes_api": {"url": settings.eyes_api},
        "bili_helper": {
            "exists": bool(settings.bili_script and settings.bili_script.exists()),
            "path": str(settings.bili_script) if settings.bili_script else None,
            "name": "bilibili helper",
            "required": True,
            "install_hint": "Ensure tools/bilibili/bili23_agent_cli.py exists or set VIVID_BILI_SCRIPT",
        },
        "douyin_helper": {
            "exists": bool(settings.douyin_script and settings.douyin_script.exists()),
            "path": str(settings.douyin_script) if settings.douyin_script else None,
            "name": "douyin helper",
            "required": True,
            "install_hint": "Ensure tools/douyin/douyin.js exists or set VIVID_DOUYIN_SCRIPT",
        },
        "vision_configs": {
            "api_configs": {
                "exists": settings.vision_api_configs_path.exists(),
                "path": str(settings.vision_api_configs_path),
            },
            "prompts": {
                "exists": settings.vision_prompts_path.exists(),
                "path": str(settings.vision_prompts_path),
            },
        },
        "transcription_configs": {
            "presets": {
                "exists": settings.transcription_presets_path.exists(),
                "path": str(settings.transcription_presets_path),
            }
        },
        "summary_configs": {
            "prompts": {
                "exists": bool(settings.summary_prompts_path and settings.summary_prompts_path.exists()),
                "path": str(settings.summary_prompts_path) if settings.summary_prompts_path else None,
            },
            "providers": {
                "exists": bool(settings.summary_providers_path and settings.summary_providers_path.exists()),
                "path": str(settings.summary_providers_path) if settings.summary_providers_path else None,
            },
        },
    }
    ok = all(
        [
            checks["python"]["available"],
            checks["ffmpeg"]["available"],
            checks["requests"]["available"],
            checks["whisper"]["available"],
            checks["bili_helper"]["exists"],
            checks["douyin_helper"]["exists"],
        ]
    )
    return {
        "action": "doctor",
        "ok": ok,
        "repo_root": str(settings.repo_root),
        "tools_root": str(settings.tools_root),
        "checks": checks,
    }


def _run_quickread(args: argparse.Namespace, settings: Settings) -> int:
    ensure_opencv_dependency(raise_on_failure=False)
    try:
        if args.execution_mode == "cloud":
            result = run_cloud_quickread(args, settings)
            payload = _quickread_payload(args, result, None, True)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        options = build_runtime_options(
            settings,
            {
                "source": args.source,
                "project_name": args.project_name,
                "data_dir": args.data_dir,
                "output_format": args.format,
                "whisper_model": args.model,
                "forced_platform": args.platform,
                "ffmpeg_bin": args.ffmpeg_bin,
                "whisper_root": args.whisper_root,
                "acquisition_mode": args.acquisition_mode,
                "prefer_ocr": args.prefer_ocr,
                "force_ocr": args.force_ocr,
                "transcription_backend": args.transcription_backend,
                "vision_backend": args.vision_backend,
                "transcribe_timeout": args.transcribe_timeout,
                "ocr_timeout": args.ocr_timeout,
                "summary_prompt_id": args.summary_prompt_id,
                "summary_system_prompt": args.summary_system_prompt,
                "summary_user_prompt": args.summary_user_prompt,
                "summary_prompts_path": args.summary_prompts_file,
                "summary_providers_path": args.summary_providers_file,
                "vision_api_config_id": args.vision_api_config_id,
                "vision_timeout": args.vision_timeout,
                "vision_sample_ms": args.vision_sample_ms,
                "vision_min_duration_ms": args.vision_min_duration_ms,
                "no_keep_files": args.no_keep_files,
            },
        )
        result = run_quickread(options)
        payload = _quickread_payload(args, result.to_dict(), None, True)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except CloudQuickreadError as exc:
        remote = exc.payload
        payload = _quickread_payload(
            args,
            remote.get("result"),
            remote.get("error") or str(exc),
            False,
            error_code=remote.get("error_code"),
            requires_user_input=bool(remote.get("requires_user_input", False)),
            user_prompt=remote.get("user_prompt"),
            next_action_hint=remote.get("next_action_hint"),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    except Exception as exc:  # noqa: BLE001
        payload = _quickread_payload(args, None, str(exc), False)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1


def _quickread_payload(
    args: argparse.Namespace,
    result: dict[str, Any] | None,
    error: str | None,
    ok: bool,
    *,
    error_code: str | None = None,
    requires_user_input: bool = False,
    user_prompt: str | None = None,
    next_action_hint: str | None = None,
) -> dict[str, Any]:
    return {
        "action": "quickread",
        "ok": ok,
        "source": args.source,
        "project_name": args.project_name,
        "format": args.format,
        "data_dir": args.data_dir,
        "platform": args.platform,
        "model": args.model,
        "execution_mode": getattr(args, "execution_mode", "local"),
        "artifact_target": getattr(args, "artifact_target", "local_only"),
        "cloud_profile": getattr(args, "cloud_profile", None),
        "cloud_base_url": getattr(args, "cloud_base_url", None),
        "no_keep_files": bool(args.no_keep_files),
        "exit_code": 0 if ok else 1,
        "result": result,
        "raw_output": None,
        "error": error,
        "error_code": error_code,
        "ffmpeg_bin": args.ffmpeg_bin,
        "whisper_root": args.whisper_root,
        "acquisition_mode": args.acquisition_mode,
        "prefer_ocr": bool(args.prefer_ocr),
        "force_ocr": bool(args.force_ocr),
        "transcription_backend": args.transcription_backend,
        "vision_backend": args.vision_backend,
        "transcribe_timeout": args.transcribe_timeout or 0,
        "ocr_timeout": args.ocr_timeout or 0,
        "vision_api_config_id": args.vision_api_config_id,
        "vision_timeout": args.vision_timeout or 0,
        "vision_sample_ms": args.vision_sample_ms or 0,
        "vision_min_duration_ms": args.vision_min_duration_ms or 0,
        "error_summary": (result or {}).get("error_summary") if result else None,
        "requires_user_input": requires_user_input,
        "user_prompt": user_prompt,
        "next_action_hint": next_action_hint,
    }


def _handle_vision_action(args: argparse.Namespace, settings: Settings) -> int:
    store = load_vision_store(settings.vision_api_configs_path, settings.vision_prompts_path)
    if args.action == "vision-configs":
        print(json.dumps({"items": store.to_api_payload()["items"], "selected_id": store.selected_api_config_id}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "vision-prompts":
        print(json.dumps(store.to_prompt_payload(), ensure_ascii=False, indent=2))
        return 0
    if args.action == "vision-select-config":
        ok = store.select_api_config(args.id)
        if not ok:
            print(json.dumps({"ok": False, "error": f"config not found: {args.id}"}, ensure_ascii=False, indent=2))
            return 1
        save_vision_store(store, settings.vision_api_configs_path, settings.vision_prompts_path)
        print(json.dumps({"ok": True, "selected_id": store.selected_api_config_id}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "vision-upsert-config":
        store.upsert_api_config(
            VisionApiConfig(
                id=args.id,
                name=args.name,
                api_base=args.api_base,
                api_path=args.api_path,
                model=args.model,
                timeout=args.timeout,
                group=args.group,
                note=args.note,
                prompt=args.prompt,
                system_prompt=args.system_prompt,
                api_key_env=args.api_key_env or None,
            )
        )
        save_vision_store(store, settings.vision_api_configs_path, settings.vision_prompts_path)
        print(json.dumps({"ok": True, "id": args.id}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "vision-upsert-prompt":
        store.upsert_prompt(VisionPromptItem(id=args.id, name=args.name, content=args.content))
        save_vision_store(store, settings.vision_api_configs_path, settings.vision_prompts_path)
        print(json.dumps({"ok": True, "id": args.id}, ensure_ascii=False, indent=2))
        return 0
    return 2


def _handle_transcription_action(args: argparse.Namespace, settings: Settings) -> int:
    store = load_transcription_store(settings.transcription_presets_path)
    if args.action == "transcription-presets":
        print(json.dumps(store.to_payload(), ensure_ascii=False, indent=2))
        return 0
    if args.action == "transcription-select-preset":
        ok = store.select_preset(args.id)
        if not ok:
            print(json.dumps({"ok": False, "error": f"preset not found: {args.id}"}, ensure_ascii=False, indent=2))
            return 1
        save_transcription_store(store, settings.transcription_presets_path)
        print(json.dumps({"ok": True, "selected_id": store.selected_preset_id}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "transcription-upsert-preset":
        extract_audio = True
        if args.no_extract_audio:
            extract_audio = False
        elif args.extract_audio:
            extract_audio = True
        store.upsert_preset(
            TranscriptionPreset(
                id=args.id,
                name=args.name,
                model=args.model,
                device=args.device,
                language=args.language or None,
                task=args.task,
                extract_audio=extract_audio,
                note=args.note,
            )
        )
        save_transcription_store(store, settings.transcription_presets_path)
        print(json.dumps({"ok": True, "id": args.id}, ensure_ascii=False, indent=2))
        return 0
    return 2


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


if __name__ == "__main__":
    raise SystemExit(main())
