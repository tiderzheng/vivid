#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${1:-$(cd -- "${SCRIPT_DIR}/.." && pwd)}"
VENV_PATH="${REPO_ROOT}/.venv"
LOCK_FILE="${VENV_PATH}/.creating_lock"
REQUIREMENTS_PATH="${REPO_ROOT}/requirements.txt"
TORCH_MODE="$(printf '%s' "${VIVID_TORCH_MODE:-}" | tr '[:upper:]' '[:lower:]')"

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

detect_venv_python() {
    if [[ -f "${VENV_PATH}/bin/python" ]]; then
        printf '%s\n' "${VENV_PATH}/bin/python"
        return 0
    fi

    if [[ -f "${VENV_PATH}/Scripts/python.exe" ]]; then
        printf '%s\n' "${VENV_PATH}/Scripts/python.exe"
        return 0
    fi

    return 1
}

native_path() {
    if [[ "${PYTHON_OS_NAME:-}" == "nt" ]] && command -v cygpath >/dev/null 2>&1; then
        cygpath -w "$1"
    else
        printf '%s\n' "$1"
    fi
}

has_nvidia_gpu() {
    if ! command -v nvidia-smi >/dev/null 2>&1; then
        return 1
    fi
    nvidia-smi >/dev/null 2>&1
}

show_torch_install_choice_and_exit() {
    local python_path="$1"
    local requirements_path="$2"
    echo "" >&2
    echo -e "${YELLOW}Detected an NVIDIA GPU.${NC}" >&2
    echo -e "${YELLOW}Install CUDA-matched torch and torchaudio before installing requirements.${NC}" >&2
    echo "" >&2
    echo -e "Choose one path and rerun:" >&2
    echo -e "  CPU path  : export VIVID_TORCH_MODE=cpu" >&2
    echo -e "  CUDA path :" >&2
    echo -e "    1. \"${python_path}\" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128" >&2
    echo -e "    2. \"${python_path}\" -m pip install -r \"${requirements_path}\"" >&2
    echo "" >&2
    echo -e "${RED}Stopped before installing dependencies so you can choose CPU or CUDA torch intentionally.${NC}" >&2
    exit 1
}

if VENV_PYTHON="$(detect_venv_python)"; then
    printf '%s\n' "${VENV_PYTHON}"
    exit 0
fi

mkdir -p "${VENV_PATH}"

if [[ -f "${LOCK_FILE}" ]]; then
    echo -e "${YELLOW}Virtual environment is being created. Waiting...${NC}" >&2
    timeout_seconds=300
    elapsed_seconds=0
    while [[ -f "${LOCK_FILE}" ]] && [[ ${elapsed_seconds} -lt ${timeout_seconds} ]]; do
        sleep 1
        elapsed_seconds=$((elapsed_seconds + 1))
    done

    if VENV_PYTHON="$(detect_venv_python)"; then
        printf '%s\n' "${VENV_PYTHON}"
        exit 0
    fi

    echo -e "${RED}Timed out waiting for the virtual environment to finish creating.${NC}" >&2
    exit 1
fi

touch "${LOCK_FILE}"
cleanup() {
    rm -f "${LOCK_FILE}"
}
trap cleanup EXIT

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo -e "${RED}Python 3.10+ is required.${NC}" >&2
    exit 1
fi

PYTHON_OS_NAME="$("${PYTHON_CMD}" -c 'import os; print(os.name)' 2>/dev/null || printf '')"

echo -e "${YELLOW}Creating virtual environment...${NC}" >&2
if ! "${PYTHON_CMD}" -m venv "$(native_path "${VENV_PATH}")"; then
    echo -e "${RED}Failed to create the virtual environment.${NC}" >&2
    exit 1
fi

if ! VENV_PYTHON="$(detect_venv_python)"; then
    echo -e "${RED}Virtual environment was created but no Python executable was found.${NC}" >&2
    exit 1
fi

echo -e "${YELLOW}Installing runtime dependencies...${NC}" >&2
if ! "${VENV_PYTHON}" -m pip install --upgrade pip; then
    echo -e "${RED}Failed to upgrade pip in the virtual environment.${NC}" >&2
    exit 1
fi

# Stop here on NVIDIA systems unless the user explicitly accepts CPU torch.
if [[ "${TORCH_MODE}" != "cpu" ]] && has_nvidia_gpu; then
    show_torch_install_choice_and_exit "${VENV_PYTHON}" "$(native_path "${REQUIREMENTS_PATH}")"
fi

if ! "${VENV_PYTHON}" -m pip install -r "$(native_path "${REQUIREMENTS_PATH}")"; then
    echo -e "${RED}Failed to install runtime dependencies.${NC}" >&2
    exit 1
fi

printf '%s\n' "${VENV_PYTHON}"
