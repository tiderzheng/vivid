from __future__ import annotations

import argparse
import json
import sys

from .config import load_settings
from .pipeline.orchestrator import run_quickread
from .runtime_factory import build_runtime_options
from .services.bili_cookie_store import save_bili_cookie
from .services.dependency_bootstrap import ensure_opencv_dependency


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vivid video quickread CLI.")
    parser.add_argument("source", help="Video URL or local file path")
    parser.add_argument("--project-name", help="Override saved project folder name")
    parser.add_argument("--data-dir", help="Override root data directory")
    parser.add_argument(
        "-f",
        "--format",
        choices=["transcript", "summary", "both"],
        help="Output format",
    )
    parser.add_argument(
        "-m",
        "--model",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model for Ears4",
    )
    parser.add_argument("--platform", choices=["bilibili", "douyin", "youtube", "generic", "local"])
    parser.add_argument("--sessdata", help=argparse.SUPPRESS)
    parser.add_argument("--no-sessdata", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--bili-cookie", help="Bilibili cookie for helper auth")
    parser.add_argument("--ffmpeg-bin", help="Override ffmpeg executable path")
    parser.add_argument("--whisper-root", help="Override local whisper package root")
    parser.add_argument("--ears4-api", help="Override Ears4 base URL")
    parser.add_argument("--eyes-api", help="Override Eyes base URL")
    parser.add_argument("--language", help="Preferred transcription language")
    parser.add_argument("--transcription-preset-id", help="Select transcription preset id from Vivid configs")
    parser.add_argument(
        "--acquisition-mode",
        choices=["auto", "smart", "prefer_ocr", "force_ocr"],
        help="Choose default, smart recommendation, OCR-preferred, or OCR-only transcript acquisition mode",
    )
    acquisition_group = parser.add_mutually_exclusive_group()
    acquisition_group.add_argument("--prefer-ocr", action="store_true", help="Prefer OCR before transcription for video inputs")
    acquisition_group.add_argument("--force-ocr", action="store_true", help="Use OCR only for video inputs")
    parser.add_argument(
        "--transcription-backend",
        choices=["auto", "internal", "ears4_api"],
        help="Choose local transcription or Ears4 API backend",
    )
    parser.add_argument("--transcription-device", help="Override transcription device")
    parser.add_argument("--transcription-task", help="Override transcription task")
    parser.add_argument("--transcription-extract-audio", action="store_true", help="Force audio extraction for transcription")
    parser.add_argument("--no-transcription-extract-audio", action="store_true", help="Disable audio extraction for transcription")
    parser.add_argument("--transcription-output-dir", help="Override transcription output directory")
    parser.add_argument("--transcribe-timeout", type=int, help="Ears4 timeout in seconds")
    parser.add_argument("--ocr-timeout", type=int, help="Eyes timeout in seconds")
    parser.add_argument("--llm-max-chars", type=int, help="Max transcript chars sent to LLM")
    parser.add_argument("--siliconflow-model", help="Primary summary model")
    parser.add_argument("--dashscope-model", help="Fallback summary model")
    parser.add_argument("--summary-prompt-id", help="Select summary prompt preset id from Vivid summary configs")
    parser.add_argument("--summary-system-prompt", help="Override summary system prompt")
    parser.add_argument("--summary-user-prompt", help="Override summary user prompt template; use {transcript} as placeholder")
    parser.add_argument("--summary-prompts-file", help="Override Vivid summary prompts file")
    parser.add_argument("--summary-providers-file", help="Override Vivid summary provider config file")
    parser.add_argument("--calibration-prompt-id", help="Select calibration prompt preset id")
    parser.add_argument("--calibration-system-prompt", help="Override calibration system prompt")
    parser.add_argument("--calibration-user-prompt", help="Override calibration user prompt template")
    parser.add_argument("--calibration-prompts-file", help="Override calibration prompts file")
    parser.add_argument("--vision-api-config-id", help="Override Eyes-side OCR config id")
    parser.add_argument(
        "--vision-backend",
        choices=["auto", "internal", "eyes_api"],
        help="Choose local OCR or Eyes API backend",
    )
    parser.add_argument("--vision-api-base", help="Override Eyes-side OCR API base")
    parser.add_argument("--vision-api-path", help="Override Eyes-side OCR API path")
    parser.add_argument("--vision-api-key", help="Override Eyes-side OCR API key")
    parser.add_argument("--vision-model", help="Override Eyes-side OCR model")
    parser.add_argument("--vision-timeout", type=int, help="Override Eyes-side OCR model timeout")
    parser.add_argument("--vision-prompt-id", help="Select OCR prompt preset id from Vivid vision configs")
    parser.add_argument("--vision-prompt", help="Override OCR prompt")
    parser.add_argument("--vision-system-prompt", help="Override OCR system prompt")
    parser.add_argument("--vision-sample-ms", type=int, help="OCR sample interval in milliseconds")
    parser.add_argument("--vision-min-duration-ms", type=int, help="OCR minimum subtitle duration in milliseconds")
    parser.add_argument("--vision-api-configs-file", help="Override Vivid vision api configs file")
    parser.add_argument("--vision-prompts-file", help="Override Vivid vision prompts file")
    parser.add_argument("--transcription-presets-file", help="Override Vivid transcription presets file")
    parser.add_argument("--no-keep-files", action="store_true", help="Delete transient media after run")
    parser.add_argument("--json", action="store_true", help="Print structured JSON output")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    ensure_opencv_dependency(raise_on_failure=False)
    settings = load_settings()
    _persist_bili_cookie_if_present(settings.repo_root, args.bili_cookie, source="cli")
    transcription_extract_audio = settings.transcription_extract_audio
    acquisition_mode = args.acquisition_mode or settings.acquisition_mode
    if args.prefer_ocr:
        acquisition_mode = "prefer_ocr"
    if args.force_ocr:
        acquisition_mode = "force_ocr"
    if args.transcription_extract_audio:
        transcription_extract_audio = True
    if args.no_transcription_extract_audio:
        transcription_extract_audio = False
    values = {
        "source": args.source,
        "project_name": args.project_name,
        "data_dir": args.data_dir,
        "bili_cookie": args.bili_cookie,
        "output_format": args.format,
        "whisper_model": args.model,
        "forced_platform": args.platform,
        "ffmpeg_bin": args.ffmpeg_bin,
        "whisper_root": args.whisper_root,
        "ears4_api": args.ears4_api,
        "eyes_api": args.eyes_api,
        "language": args.language,
        "transcription_preset_id": args.transcription_preset_id,
        "acquisition_mode": acquisition_mode,
        "transcription_backend": args.transcription_backend,
        "transcription_device": args.transcription_device,
        "transcription_task": args.transcription_task,
        "transcription_extract_audio": transcription_extract_audio,
        "transcription_output_dir": args.transcription_output_dir,
        "transcribe_timeout": args.transcribe_timeout,
        "ocr_timeout": args.ocr_timeout,
        "llm_max_chars": args.llm_max_chars,
        "siliconflow_model": args.siliconflow_model,
        "dashscope_model": args.dashscope_model,
        "summary_prompt_id": args.summary_prompt_id,
        "summary_system_prompt": args.summary_system_prompt,
        "summary_user_prompt": args.summary_user_prompt,
        "summary_prompts_path": args.summary_prompts_file,
        "summary_providers_path": args.summary_providers_file,
        "calibration_prompt_id": args.calibration_prompt_id,
        "calibration_system_prompt": args.calibration_system_prompt,
        "calibration_user_prompt": args.calibration_user_prompt,
        "calibration_prompts_path": args.calibration_prompts_file,
        "vision_api_config_id": args.vision_api_config_id,
        "vision_backend": args.vision_backend,
        "vision_api_base": args.vision_api_base,
        "vision_api_path": args.vision_api_path,
        "vision_api_key": args.vision_api_key,
        "vision_model": args.vision_model,
        "vision_timeout": args.vision_timeout,
        "vision_prompt_id": args.vision_prompt_id,
        "vision_prompt": args.vision_prompt,
        "vision_system_prompt": args.vision_system_prompt,
        "vision_sample_ms": args.vision_sample_ms,
        "vision_min_duration_ms": args.vision_min_duration_ms,
        "vision_api_configs_path": args.vision_api_configs_file,
        "vision_prompts_path": args.vision_prompts_file,
        "transcription_presets_path": args.transcription_presets_file,
        "no_keep_files": args.no_keep_files,
        "prefer_ocr": args.prefer_ocr,
        "force_ocr": args.force_ocr,
        "no_transcription_extract_audio": args.no_transcription_extract_audio,
    }
    if args.sessdata is not None:
        values["sessdata"] = args.sessdata
    if args.no_sessdata:
        values["no_sessdata"] = True
    options = build_runtime_options(settings, values)
    try:
        result = run_quickread(options)
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(result.rendered)
            error_summary = result.to_dict().get("error_summary") or {}
            if error_summary.get("has_issues"):
                print(f"\n[diagnostic] {error_summary.get('headline')}", file=sys.stderr)
                for item in error_summary.get("items", [])[:5]:
                    print(f"- {item}", file=sys.stderr)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}")
        return 1


def _persist_bili_cookie_if_present(repo_root, bili_cookie: str | None, *, source: str) -> None:
    if not bili_cookie:
        return
    try:
        save_bili_cookie(repo_root, bili_cookie, source=source)
    except (OSError, ValueError):
        return


if __name__ == "__main__":
    raise SystemExit(main())
