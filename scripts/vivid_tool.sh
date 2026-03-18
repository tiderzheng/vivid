#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

VENV_PYTHON="$("${SCRIPT_DIR}/ensure_venv.sh" "${REPO_ROOT}")"
if [[ -z "${VENV_PYTHON}" ]]; then
    echo "Could not resolve the virtual environment Python executable." >&2
    exit 1
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
    echo "Missing -Action." >&2
    exit 2
fi

cd "${REPO_ROOT}"
export PYTHONUTF8=1
exec "${VENV_PYTHON}" -m app.control_cli "${action}" "${args[@]}"
