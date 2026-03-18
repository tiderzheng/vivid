#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="$("${SCRIPT_DIR}/ensure_venv.sh" "${REPO_ROOT}")"

if [[ -z "${VENV_PYTHON}" ]]; then
    echo "Could not resolve the virtual environment Python executable." >&2
    exit 1
fi

FIX_MODE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        -Fix|--fix)
            FIX_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

run_doctor_json() {
    "${VENV_PYTHON}" -m app.control_cli doctor
}

DOCTOR_JSON="$(run_doctor_json)"

if [[ "${FIX_MODE}" == "true" ]]; then
    if ! printf '%s' "${DOCTOR_JSON}" | "${VENV_PYTHON}" -c "import json, sys; raise SystemExit(0 if json.load(sys.stdin)['ok'] else 1)"; then
        "${VENV_PYTHON}" -m pip install -r "${REPO_ROOT}/requirements.txt"
        DOCTOR_JSON="$(run_doctor_json)"
    fi
fi

printf '%s' "${DOCTOR_JSON}" | "${VENV_PYTHON}" -c '
import json
import sys

payload = json.load(sys.stdin)
checks = payload["checks"]
rows = [
    ("python", checks["python"]["available"], checks["python"]["required"], checks["python"]["install_hint"]),
    ("ffmpeg", checks["ffmpeg"]["available"], checks["ffmpeg"]["required"], checks["ffmpeg"]["install_hint"]),
    ("node", checks["node"]["available"], checks["node"]["required"], checks["node"]["install_hint"]),
    ("requests", checks["requests"]["available"], checks["requests"]["required"], checks["requests"]["install_hint"]),
    ("yt-dlp", checks["yt_dlp_python"]["available"], checks["yt_dlp_python"]["required"], checks["yt_dlp_python"]["install_hint"]),
    ("openai-whisper", checks["whisper"]["available"], checks["whisper"]["required"], checks["whisper"]["install_hint"]),
    ("torch", checks["torch"]["available"], checks["torch"]["required"], checks["torch"]["install_hint"]),
    ("opencv-python", checks["opencv"]["available"], checks["opencv"]["required"], checks["opencv"]["install_hint"]),
    ("bilibili helper", checks["bili_helper"]["exists"], checks["bili_helper"]["required"], checks["bili_helper"]["install_hint"]),
    ("douyin helper", checks["douyin_helper"]["exists"], checks["douyin_helper"]["required"], checks["douyin_helper"]["install_hint"]),
]

print("========================================")
print("              Vivid Doctor              ")
print("========================================")
print("")
for name, available, required, hint in rows:
    if available:
        status = "OK "
    elif required:
        status = "ERR"
    else:
        status = "OPT"
    label = "[required]" if required else "[optional]"
    print(f"{status} {name} {label}")
    if not available:
        print(f"    hint: {hint}")

print("")
if payload["ok"]:
    print("All required dependencies are ready.")
else:
    print("Some required dependencies are missing.")
print("")
print(json.dumps(payload, ensure_ascii=False, indent=2))
'
