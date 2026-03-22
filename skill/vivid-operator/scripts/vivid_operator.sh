#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
STATE_FILE="$SKILL_ROOT/state/repo_root.json"

is_valid_repo_root() {
    local candidate="${1:-}"
    [[ -n "$candidate" && -f "$candidate/scripts/vivid_tool.sh" ]]
}

save_repo_root_state() {
    local repo_root="$1"
    local source="$2"
    local escaped_root="${repo_root//\\/\\\\}"
    local escaped_source="${source//\\/\\\\}"
    mkdir -p "$(dirname "$STATE_FILE")"
    printf '{\n  "repo_root": "%s",\n  "source": "%s",\n  "updated_at_utc": "%s"\n}\n' \
        "$escaped_root" \
        "$escaped_source" \
        "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$STATE_FILE"
}

load_cached_repo_root() {
    if [[ ! -f "$STATE_FILE" ]]; then
        return 1
    fi
    local cached_root
    cached_root="$(sed -n 's/.*"repo_root"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$STATE_FILE" | head -n 1)"
    if is_valid_repo_root "$cached_root"; then
        printf '%s\n' "$cached_root"
        return 0
    fi
    echo -e "\033[33m忽略失效的 Vivid 仓库缓存: ${cached_root:-<empty>}\033[0m" >&2
    return 1
}

# 确定Vivid仓库根目录
if [ -n "${1:-}" ] && [[ "$1" == --vivid-root=* ]]; then
    REPO_ROOT="${1#--vivid-root=}"
    if ! is_valid_repo_root "$REPO_ROOT"; then
        echo -e "\033[31m错误：无效的 --vivid-root 路径: $REPO_ROOT\033[0m"
        echo -e "\033[33m状态文件: $STATE_FILE\033[0m"
        exit 1
    fi
    echo -e "\033[32m使用参数指定路径: $REPO_ROOT\033[0m"
    save_repo_root_state "$REPO_ROOT" "argument"
    echo -e "\033[90m已缓存仓库路径: $STATE_FILE\033[0m"
    shift
elif [ -n "${VIVID_REPO_ROOT:-}" ]; then
    REPO_ROOT="$VIVID_REPO_ROOT"
    if ! is_valid_repo_root "$REPO_ROOT"; then
        echo -e "\033[31m错误：无效的 VIVID_REPO_ROOT: $REPO_ROOT\033[0m"
        echo -e "\033[33m状态文件: $STATE_FILE\033[0m"
        exit 1
    fi
    echo -e "\033[32m使用环境变量 VIVID_REPO_ROOT: $REPO_ROOT\033[0m"
    save_repo_root_state "$REPO_ROOT" "environment"
    echo -e "\033[90m已缓存仓库路径: $STATE_FILE\033[0m"
elif REPO_ROOT="$(load_cached_repo_root 2>/dev/null)"; then
    echo -e "\033[32m使用缓存的 Vivid 仓库: $REPO_ROOT\033[0m"
    echo -e "\033[90m缓存文件: $STATE_FILE\033[0m"
else
    # 尝试自动检测（相对于skill脚本的位置）
    DETECTED_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
    
    # 检查是否是有效的Vivid仓库
    if is_valid_repo_root "$DETECTED_ROOT"; then
        REPO_ROOT="$DETECTED_ROOT"
        echo -e "\033[32m自动检测到Vivid仓库: $REPO_ROOT\033[0m"
        save_repo_root_state "$REPO_ROOT" "auto_detect"
        echo -e "\033[90m已缓存仓库路径: $STATE_FILE\033[0m"
    else
        echo -e "\033[31m错误：无法找到Vivid仓库\033[0m"
        echo ""
        echo -e "\033[33m请通过以下方式之一指定Vivid仓库路径：\033[0m"
        echo -e "  1. \033[36m先查看状态文件: $STATE_FILE\033[0m"
        echo -e "  2. \033[36m设置环境变量: export VIVID_REPO_ROOT=/path/to/vivid\033[0m"
        echo -e "  3. \033[36m使用参数: --vivid-root=/path/to/vivid\033[0m"
        echo ""
        echo -e "\033[33m或者确保skill目录位于Vivid仓库的 skill/vivid-operator/ 路径下\033[0m"
        exit 1
    fi
fi

# 验证工具脚本存在
TOOL_PATH="$REPO_ROOT/scripts/vivid_tool.sh"
if [ ! -f "$TOOL_PATH" ]; then
    echo -e "\033[31m错误：找不到Vivid工具脚本: $TOOL_PATH\033[0m"
    echo -e "\033[33m请检查Vivid仓库路径是否正确\033[0m"
    exit 1
fi

exec "$TOOL_PATH" "$@"
