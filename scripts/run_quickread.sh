#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# 确保虚拟环境存在（使用统一的ensure_venv脚本）
VENV_PYTHON=$("${SCRIPT_DIR}/ensure_venv.sh" "${REPO_ROOT}")
if [[ -z "${VENV_PYTHON}" ]]; then
    echo "无法获取虚拟环境Python路径" >&2
    exit 1
fi

# 使用虚拟环境的Python
cd "${REPO_ROOT}"
export PYTHONUTF8=1
exec "${VENV_PYTHON}" -m app.cli "$@"
