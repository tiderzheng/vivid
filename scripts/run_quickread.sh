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

cd "${REPO_ROOT}"
export PYTHONUTF8=1
"${PYTHON_BIN}" -c "from app.services.dependency_bootstrap import ensure_opencv_dependency; ensure_opencv_dependency(raise_on_failure=False)" >/dev/null
exec "${PYTHON_BIN}" -m app.cli "$@"
