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

action=""
args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -Action|--action)
      action="${2:-}"
      shift 2
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${action}" ]]; then
  echo "Missing -Action" >&2
  exit 2
fi

cd "${REPO_ROOT}"
export PYTHONUTF8=1
exec "${PYTHON_BIN}" -m app.control_cli "${action}" "${args[@]}"
