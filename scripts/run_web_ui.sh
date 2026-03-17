#!/usr/bin/env bash
set -euo pipefail

HOST="127.0.0.1"
PORT="8765"
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

cd "${REPO_ROOT}"
export PYTHONUTF8=1
"${PYTHON_BIN}" -c "from app.services.dependency_bootstrap import ensure_opencv_dependency; ensure_opencv_dependency(raise_on_failure=False)" >/dev/null
exec "${PYTHON_BIN}" -m uvicorn app.web:app --host "${HOST}" --port "${PORT}"
