from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..subsystems.vision import VisionApiConfig, VisionPromptItem, load_vision_store
from ..subsystems.vision.store import save_vision_store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Vivid vision configs and prompts.")
    parser.add_argument("--api-configs-file", required=True)
    parser.add_argument("--prompts-file", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-configs")
    subparsers.add_parser("list-prompts")

    select_parser = subparsers.add_parser("select-config")
    select_parser.add_argument("--id", required=True)

    upsert_config = subparsers.add_parser("upsert-config")
    upsert_config.add_argument("--id", required=True)
    upsert_config.add_argument("--name", required=True)
    upsert_config.add_argument("--api-base", required=True)
    upsert_config.add_argument("--api-path", default="/v1/chat/completions")
    upsert_config.add_argument("--model", default="")
    upsert_config.add_argument("--timeout", type=int, default=30)
    upsert_config.add_argument("--group", default="default")
    upsert_config.add_argument("--note", default="")
    upsert_config.add_argument("--prompt", default="")
    upsert_config.add_argument("--system-prompt", default="")
    upsert_config.add_argument("--api-key-env", default="")

    upsert_prompt = subparsers.add_parser("upsert-prompt")
    upsert_prompt.add_argument("--id", required=True)
    upsert_prompt.add_argument("--name", required=True)
    upsert_prompt.add_argument("--content", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    api_configs_path = Path(args.api_configs_file).expanduser()
    prompts_path = Path(args.prompts_file).expanduser()
    store = load_vision_store(api_configs_path, prompts_path)

    if args.command == "list-configs":
        print(
            json.dumps(
                {
                    "items": store.to_api_payload()["items"],
                    "selected_id": store.selected_api_config_id,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.command == "list-prompts":
        print(json.dumps(store.to_prompt_payload(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "select-config":
        ok = store.select_api_config(args.id)
        if not ok:
            print(json.dumps({"ok": False, "error": f"config not found: {args.id}"}, ensure_ascii=False, indent=2))
            return 1
        save_vision_store(store, api_configs_path, prompts_path)
        print(json.dumps({"ok": True, "selected_id": store.selected_api_config_id}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "upsert-config":
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
        save_vision_store(store, api_configs_path, prompts_path)
        print(json.dumps({"ok": True, "id": args.id}, ensure_ascii=False, indent=2))
        return 0

    if args.command == "upsert-prompt":
        store.upsert_prompt(
            VisionPromptItem(
                id=args.id,
                name=args.name,
                content=args.content,
            )
        )
        save_vision_store(store, api_configs_path, prompts_path)
        print(json.dumps({"ok": True, "id": args.id}, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
