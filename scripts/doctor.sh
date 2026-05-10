#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="$("${SCRIPT_DIR}/ensure_venv.sh" "${REPO_ROOT}")"
TORCH_MODE="$(printf '%s' "${VIVID_TORCH_MODE:-}" | tr '[:upper:]' '[:lower:]')"

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

has_nvidia_gpu() {
    if ! command -v nvidia-smi >/dev/null 2>&1; then
        return 1
    fi
    nvidia-smi >/dev/null 2>&1
}

torch_and_torchaudio_cuda_available() {
    "${VENV_PYTHON}" -c "import torch, torchaudio; print('1' if torch.cuda.is_available() else '0')" 2>/dev/null | grep -q '^1$'
}

DOCTOR_JSON="$(run_doctor_json)"

if [[ "${FIX_MODE}" == "true" ]]; then
    if ! printf '%s' "${DOCTOR_JSON}" | "${VENV_PYTHON}" -c "import json, sys; raise SystemExit(0 if json.load(sys.stdin)['ok'] else 1)"; then
        if [[ "${TORCH_MODE}" != "cpu" ]] && has_nvidia_gpu && ! torch_and_torchaudio_cuda_available; then
            echo "Detected an NVIDIA GPU." >&2
            echo "doctor --fix would reinstall 'requirements.txt' and may pull CPU-only torch/torchaudio." >&2
            echo "If you want CPU intentionally, run: export VIVID_TORCH_MODE=cpu" >&2
            echo "If you want CUDA, install CUDA torch and torchaudio first, then rerun doctor." >&2
            exit 1
        fi
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
    ("faster-whisper", checks["faster_whisper"]["available"], checks["faster_whisper"]["required"], checks["faster_whisper"]["install_hint"]),
    ("ctranslate2", checks["ctranslate2"]["available"], checks["ctranslate2"]["required"], checks["ctranslate2"]["install_hint"]),
    ("funasr", checks["funasr"]["available"], checks["funasr"]["required"], checks["funasr"]["install_hint"]),
    ("modelscope", checks["modelscope"]["available"], checks["modelscope"]["required"], checks["modelscope"]["install_hint"]),
    ("torch", checks["torch"]["available"], checks["torch"]["required"], checks["torch"]["install_hint"]),
    ("torchaudio", checks["torchaudio"]["available"], checks["torchaudio"]["required"], checks["torchaudio"]["install_hint"]),
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
