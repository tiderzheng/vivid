#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
VENV_PYTHON="$("${SCRIPT_DIR}/ensure_venv.sh" "${REPO_ROOT}")"
if [[ -z "${VENV_PYTHON}" ]]; then
  echo "Could not resolve the virtual environment Python executable." >&2
  exit 1
fi

COMMAND=""
ID=""
NAME=""
API_BASE=""
API_PATH="/v1/chat/completions"
MODEL=""
TIMEOUT="30"
GROUP="default"
NOTE=""
PROMPT=""
SYSTEM_PROMPT=""
API_KEY_ENV=""
CONTENT=""
API_CONFIGS_FILE="${VIVID_VISION_API_CONFIGS_FILE:-${REPO_ROOT}/configs/vision/api_configs.json}"
PROMPTS_FILE="${VIVID_VISION_PROMPTS_FILE:-${REPO_ROOT}/configs/vision/prompts.json}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Command|--command) COMMAND="${2:-}"; shift 2 ;;
    -Id|--id) ID="${2:-}"; shift 2 ;;
    -Name|--name) NAME="${2:-}"; shift 2 ;;
    -ApiBase|--api-base) API_BASE="${2:-}"; shift 2 ;;
    -ApiPath|--api-path) API_PATH="${2:-}"; shift 2 ;;
    -Model|--model) MODEL="${2:-}"; shift 2 ;;
    -Timeout|--timeout) TIMEOUT="${2:-30}"; shift 2 ;;
    -Group|--group) GROUP="${2:-default}"; shift 2 ;;
    -Note|--note) NOTE="${2:-}"; shift 2 ;;
    -Prompt|--prompt) PROMPT="${2:-}"; shift 2 ;;
    -SystemPrompt|--system-prompt) SYSTEM_PROMPT="${2:-}"; shift 2 ;;
    -ApiKeyEnv|--api-key-env) API_KEY_ENV="${2:-}"; shift 2 ;;
    -Content|--content) CONTENT="${2:-}"; shift 2 ;;
    -ApiConfigsFile|--api-configs-file) API_CONFIGS_FILE="${2:-}"; shift 2 ;;
    -PromptsFile|--prompts-file) PROMPTS_FILE="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${COMMAND}" ]]; then
  echo "Missing -Command" >&2
  exit 2
fi

ARGS=(-m app.tools.vision_admin --api-configs-file "${API_CONFIGS_FILE}" --prompts-file "${PROMPTS_FILE}" "${COMMAND}")
case "${COMMAND}" in
  select-config)
    ARGS+=(--id "${ID}")
    ;;
  upsert-config)
    ARGS+=(--id "${ID}" --name "${NAME}" --api-base "${API_BASE}" --api-path "${API_PATH}" --timeout "${TIMEOUT}" --group "${GROUP}")
    [[ -n "${MODEL}" ]] && ARGS+=(--model "${MODEL}")
    [[ -n "${NOTE}" ]] && ARGS+=(--note "${NOTE}")
    [[ -n "${PROMPT}" ]] && ARGS+=(--prompt "${PROMPT}")
    [[ -n "${SYSTEM_PROMPT}" ]] && ARGS+=(--system-prompt "${SYSTEM_PROMPT}")
    [[ -n "${API_KEY_ENV}" ]] && ARGS+=(--api-key-env "${API_KEY_ENV}")
    ;;
  upsert-prompt)
    ARGS+=(--id "${ID}" --name "${NAME}" --content "${CONTENT}")
    ;;
esac

cd "${REPO_ROOT}"
export PYTHONUTF8=1
exec "${VENV_PYTHON}" "${ARGS[@]}"
