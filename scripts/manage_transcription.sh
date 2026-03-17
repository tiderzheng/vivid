#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    echo "python or python3 is required" >&2
    exit 127
  fi
fi

COMMAND=""
ID=""
NAME=""
MODEL="base"
DEVICE="auto"
LANGUAGE="zh"
TASK="transcribe"
NOTE=""
EXTRACT_AUDIO="false"
NO_EXTRACT_AUDIO="false"
PRESETS_FILE="${VIVID_TRANSCRIPTION_PRESETS_FILE:-${REPO_ROOT}/configs/transcription/presets.json}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Command|--command) COMMAND="${2:-}"; shift 2 ;;
    -Id|--id) ID="${2:-}"; shift 2 ;;
    -Name|--name) NAME="${2:-}"; shift 2 ;;
    -Model|--model) MODEL="${2:-base}"; shift 2 ;;
    -Device|--device) DEVICE="${2:-auto}"; shift 2 ;;
    -Language|--language) LANGUAGE="${2:-zh}"; shift 2 ;;
    -Task|--task) TASK="${2:-transcribe}"; shift 2 ;;
    -Note|--note) NOTE="${2:-}"; shift 2 ;;
    -ExtractAudio|--extract-audio) EXTRACT_AUDIO="true"; shift ;;
    -NoExtractAudio|--no-extract-audio) NO_EXTRACT_AUDIO="true"; shift ;;
    -PresetsFile|--presets-file) PRESETS_FILE="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${COMMAND}" ]]; then
  echo "Missing -Command" >&2
  exit 2
fi

ARGS=(-m app.tools.transcription_admin --presets-file "${PRESETS_FILE}" "${COMMAND}")
case "${COMMAND}" in
  select-preset)
    ARGS+=(--id "${ID}")
    ;;
  upsert-preset)
    ARGS+=(--id "${ID}" --name "${NAME}" --model "${MODEL}" --device "${DEVICE}" --language "${LANGUAGE}" --task "${TASK}")
    [[ "${EXTRACT_AUDIO}" == "true" ]] && ARGS+=(--extract-audio)
    [[ "${NO_EXTRACT_AUDIO}" == "true" ]] && ARGS+=(--no-extract-audio)
    [[ -n "${NOTE}" ]] && ARGS+=(--note "${NOTE}")
    ;;
esac

cd "${REPO_ROOT}"
export PYTHONUTF8=1
exec "${PYTHON_BIN}" "${ARGS[@]}"
