from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..constants import DEFAULT_MODEL
from ..subsystems.transcription import TranscriptionPreset, load_transcription_store
from ..subsystems.transcription.catalog import TRANSCRIPTION_MODELS
from ..subsystems.transcription.store import save_transcription_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Vivid transcription presets.")
    parser.add_argument("--presets-file", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-presets")

    select_parser = subparsers.add_parser("select-preset")
    select_parser.add_argument("--id", required=True)

    upsert_parser = subparsers.add_parser("upsert-preset")
    upsert_parser.add_argument("--id", required=True)
    upsert_parser.add_argument("--name", required=True)
    upsert_parser.add_argument("--model", choices=TRANSCRIPTION_MODELS, default=DEFAULT_MODEL)
    upsert_parser.add_argument("--device", default="auto")
    upsert_parser.add_argument("--language", default="zh")
    upsert_parser.add_argument("--task", default="transcribe")
    upsert_parser.add_argument("--extract-audio", action="store_true")
    upsert_parser.add_argument("--no-extract-audio", action="store_true")
    upsert_parser.add_argument("--note", default="")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    presets_path = Path(args.presets_file).expanduser()
    store = load_transcription_store(presets_path)

    if args.command == "list-presets":
        print(json.dumps(store.to_payload(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "select-preset":
        ok = store.select_preset(args.id)
        if not ok:
            print(json.dumps({"ok": False, "error": f"preset not found: {args.id}"}, ensure_ascii=False, indent=2))
            return 1
        save_transcription_store(store, presets_path)
        print(json.dumps({"ok": True, "selected_id": store.selected_preset_id}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "upsert-preset":
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
        save_transcription_store(store, presets_path)
        print(json.dumps({"ok": True, "id": args.id}, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
