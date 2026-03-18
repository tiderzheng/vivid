#!/usr/bin/env bash
set -euo pipefail

HOST="127.0.0.1"
PORT="8765"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -Host|--host|-UiHost)
      HOST="${2:-127.0.0.1}"
      shift 2
      ;;
    -Port|--port)
      PORT="${2:-8765}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# 确保虚拟环境存在（使用统一的ensure_venv脚本）
VENV_PYTHON=$("${SCRIPT_DIR}/ensure_venv.sh" "${REPO_ROOT}")
if [[ -z "${VENV_PYTHON}" ]]; then
    echo "无法获取虚拟环境Python路径" >&2
    exit 1
fi

cd "${REPO_ROOT}"
export PYTHONUTF8=1
exec "${VENV_PYTHON}" -m uvicorn app.web:app --host "${HOST}" --port "${PORT}"
