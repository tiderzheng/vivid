#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 确定Vivid仓库根目录
if [ -n "${VIVID_REPO_ROOT:-}" ]; then
    REPO_ROOT="$VIVID_REPO_ROOT"
    echo -e "\033[32m使用环境变量 VIVID_REPO_ROOT: $REPO_ROOT\033[0m"
elif [ -n "${1:-}" ] && [[ "$1" == --vivid-root=* ]]; then
    REPO_ROOT="${1#--vivid-root=}"
    echo -e "\033[32m使用参数指定路径: $REPO_ROOT\033[0m"
    shift
else
    # 尝试自动检测（相对于skill脚本的位置）
    DETECTED_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
    
    # 检查是否是有效的Vivid仓库
    if [ -f "$DETECTED_ROOT/scripts/vivid_tool.sh" ]; then
        REPO_ROOT="$DETECTED_ROOT"
        echo -e "\033[32m自动检测到Vivid仓库: $REPO_ROOT\033[0m"
    else
        echo -e "\033[31m错误：无法找到Vivid仓库\033[0m"
        echo ""
        echo -e "\033[33m请通过以下方式之一指定Vivid仓库路径：\033[0m"
        echo -e "  1. \033[36m设置环境变量: export VIVID_REPO_ROOT=/path/to/vivid\033[0m"
        echo -e "  2. \033[36m使用参数: --vivid-root=/path/to/vivid\033[0m"
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
