#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
STATE_FILE="$SKILL_ROOT/state/skill_state.json"
LEGACY_STATE_FILE="$SKILL_ROOT/state/repo_root.json"

is_valid_repo_root() {
    local candidate="${1:-}"
    [[ -n "$candidate" && -f "$candidate/scripts/vivid_tool.sh" ]]
}

json_escape() {
    local value="${1:-}"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '%s' "$value"
}

read_state_value() {
    local key="$1"
    local source_file="$STATE_FILE"
    if [[ ! -f "$source_file" && -f "$LEGACY_STATE_FILE" ]]; then
        source_file="$LEGACY_STATE_FILE"
    fi
    if [[ ! -f "$source_file" ]]; then
        return 1
    fi
    sed -n "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$source_file" | head -n 1
}

save_skill_state() {
    local repo_root="${1:-}"
    local source="${2:-}"
    local default_whisper_model="${3:-}"
    local default_data_dir="${4:-}"
    local existing_repo_root existing_source existing_model existing_data_dir
    existing_repo_root="$(read_state_value repo_root || true)"
    existing_source="$(read_state_value source || true)"
    existing_model="$(read_state_value default_whisper_model || true)"
    existing_data_dir="$(read_state_value default_data_dir || true)"

    if [[ -n "$repo_root" ]]; then existing_repo_root="$repo_root"; fi
    if [[ -n "$source" ]]; then existing_source="$source"; fi
    if [[ -n "$default_whisper_model" ]]; then existing_model="$default_whisper_model"; fi
    if [[ -n "$default_data_dir" ]]; then existing_data_dir="$default_data_dir"; fi

    mkdir -p "$(dirname "$STATE_FILE")"
    printf '{\n  "repo_root": "%s",\n  "source": "%s",\n  "default_whisper_model": "%s",\n  "default_data_dir": "%s",\n  "updated_at_utc": "%s"\n}\n' \
        "$(json_escape "$existing_repo_root")" \
        "$(json_escape "$existing_source")" \
        "$(json_escape "$existing_model")" \
        "$(json_escape "$existing_data_dir")" \
        "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$STATE_FILE"
}

load_cached_repo_root() {
    local cached_root
    if [[ -f "$STATE_FILE" ]]; then
        cached_root="$(read_state_value repo_root || true)"
        if is_valid_repo_root "$cached_root"; then
            printf '%s\n' "$cached_root"
            return 0
        fi
        echo -e "\033[33m忽略失效的 Vivid 仓库缓存: ${cached_root:-<empty>}\033[0m" >&2
        return 1
    fi

    if [[ -f "$LEGACY_STATE_FILE" ]]; then
        cached_root="$(read_state_value repo_root || true)"
        if is_valid_repo_root "$cached_root"; then
            save_skill_state "$cached_root" "legacy_repo_state" "" ""
            printf '%s\n' "$cached_root"
            return 0
        fi
        echo -e "\033[33m忽略失效的旧版 Vivid 仓库缓存: ${cached_root:-<empty>}\033[0m" >&2
    fi
    return 1
}

contains_option() {
    local target="$1"
    shift
    for arg in "$@"; do
        if [[ "$arg" == "$target" ]]; then
            return 0
        fi
    done
    return 1
}

contains_prefix_option() {
    local prefix="$1"
    shift
    for arg in "$@"; do
        if [[ "$arg" == "$prefix"* ]]; then
            return 0
        fi
    done
    return 1
}

to_absolute_path() {
    local candidate="${1:-}"
    if [[ -z "$candidate" ]]; then
        return 0
    fi
    case "$candidate" in
        /*) printf '%s\n' "$candidate" ;;
        ~*) printf '%s\n' "${HOME}${candidate#"~"}" ;;
        *) printf '%s\n' "$(pwd)/$candidate" ;;
    esac
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
    save_skill_state "$REPO_ROOT" "argument" "" ""
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
    save_skill_state "$REPO_ROOT" "environment" "" ""
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
        save_skill_state "$REPO_ROOT" "auto_detect" "" ""
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

action=""
args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -Action|--action)
            action="${2:-}"
            args+=("$1" "$2")
            shift 2
            ;;
        *)
            args+=("$1")
            shift
            ;;
    esac
done

if [[ "$action" == "quickread" ]]; then
    explicit_model=""
    explicit_data_dir=""
    explicit_execution_mode=""
    explicit_artifact_target=""
    explicit_cloud_profile=""
    explicit_cloud_base_url=""
    if contains_option "-Model" "${args[@]}" || contains_option "--model" "${args[@]}" || contains_prefix_option "--model=" "${args[@]}"; then
        for ((i=0; i<${#args[@]}; i++)); do
            if [[ "${args[$i]}" == "-Model" || "${args[$i]}" == "--model" ]]; then
                explicit_model="${args[$((i+1))]:-}"
                break
            fi
            if [[ "${args[$i]}" == --model=* ]]; then
                explicit_model="${args[$i]#--model=}"
                break
            fi
        done
    fi
    if contains_option "-DataDir" "${args[@]}" || contains_option "--data-dir" "${args[@]}" || contains_prefix_option "--data-dir=" "${args[@]}"; then
        for ((i=0; i<${#args[@]}; i++)); do
            if [[ "${args[$i]}" == "-DataDir" || "${args[$i]}" == "--data-dir" ]]; then
                explicit_data_dir="${args[$((i+1))]:-}"
                break
            fi
            if [[ "${args[$i]}" == --data-dir=* ]]; then
                explicit_data_dir="${args[$i]#--data-dir=}"
                break
            fi
        done
    fi
    if contains_option "-ExecutionMode" "${args[@]}" || contains_option "--execution-mode" "${args[@]}" || contains_prefix_option "--execution-mode=" "${args[@]}"; then
        for ((i=0; i<${#args[@]}; i++)); do
            if [[ "${args[$i]}" == "-ExecutionMode" || "${args[$i]}" == "--execution-mode" ]]; then
                explicit_execution_mode="${args[$((i+1))]:-}"
                break
            fi
            if [[ "${args[$i]}" == --execution-mode=* ]]; then
                explicit_execution_mode="${args[$i]#--execution-mode=}"
                break
            fi
        done
    fi
    if contains_option "-ArtifactTarget" "${args[@]}" || contains_option "--artifact-target" "${args[@]}" || contains_prefix_option "--artifact-target=" "${args[@]}"; then
        for ((i=0; i<${#args[@]}; i++)); do
            if [[ "${args[$i]}" == "-ArtifactTarget" || "${args[$i]}" == "--artifact-target" ]]; then
                explicit_artifact_target="${args[$((i+1))]:-}"
                break
            fi
            if [[ "${args[$i]}" == --artifact-target=* ]]; then
                explicit_artifact_target="${args[$i]#--artifact-target=}"
                break
            fi
        done
    fi
    if contains_option "-CloudProfile" "${args[@]}" || contains_option "--cloud-profile" "${args[@]}" || contains_prefix_option "--cloud-profile=" "${args[@]}"; then
        for ((i=0; i<${#args[@]}; i++)); do
            if [[ "${args[$i]}" == "-CloudProfile" || "${args[$i]}" == "--cloud-profile" ]]; then
                explicit_cloud_profile="${args[$((i+1))]:-}"
                break
            fi
            if [[ "${args[$i]}" == --cloud-profile=* ]]; then
                explicit_cloud_profile="${args[$i]#--cloud-profile=}"
                break
            fi
        done
    fi
    if contains_option "-CloudBaseUrl" "${args[@]}" || contains_option "--cloud-base-url" "${args[@]}" || contains_prefix_option "--cloud-base-url=" "${args[@]}"; then
        for ((i=0; i<${#args[@]}; i++)); do
            if [[ "${args[$i]}" == "-CloudBaseUrl" || "${args[$i]}" == "--cloud-base-url" ]]; then
                explicit_cloud_base_url="${args[$((i+1))]:-}"
                break
            fi
            if [[ "${args[$i]}" == --cloud-base-url=* ]]; then
                explicit_cloud_base_url="${args[$i]#--cloud-base-url=}"
                break
            fi
        done
    fi

    if [[ -z "$explicit_model" && -z "${VIVID_DEFAULT_MODEL:-}" ]]; then
        cached_model="$(read_state_value default_whisper_model || true)"
        if [[ -n "$cached_model" ]]; then
            args+=("--model" "$cached_model")
        fi
    fi
    if [[ -z "$explicit_data_dir" && -z "${VIVID_DATA_DIR:-}" ]]; then
        cached_data_dir="$(read_state_value default_data_dir || true)"
        if [[ -n "$cached_data_dir" ]]; then
            args+=("--data-dir" "$cached_data_dir")
        fi
    fi
    if [[ -z "$explicit_execution_mode" && -z "${VIVID_EXECUTION_MODE:-}" ]]; then
        cached_execution_mode="$(read_state_value execution_mode || true)"
        if [[ -n "$cached_execution_mode" ]]; then
            args+=("--execution-mode" "$cached_execution_mode")
        fi
    fi
    if [[ -z "$explicit_artifact_target" && -z "${VIVID_ARTIFACT_TARGET:-}" ]]; then
        cached_artifact_target="$(read_state_value artifact_target || true)"
        if [[ -n "$cached_artifact_target" ]]; then
            args+=("--artifact-target" "$cached_artifact_target")
        fi
    fi
    if [[ -z "$explicit_cloud_profile" && -z "${VIVID_CLOUD_PROFILE:-}" ]]; then
        cached_cloud_profile="$(read_state_value cloud_profile || true)"
        if [[ -n "$cached_cloud_profile" ]]; then
            args+=("--cloud-profile" "$cached_cloud_profile")
        fi
    fi
    if [[ -z "$explicit_cloud_base_url" && -z "${VIVID_CLOUD_BASE_URL:-}" ]]; then
        cached_cloud_base_url="$(read_state_value cloud_base_url || true)"
        if [[ -n "$cached_cloud_base_url" ]]; then
            args+=("--cloud-base-url" "$cached_cloud_base_url")
        fi
    fi

    if [[ -n "$explicit_model" || -n "$explicit_data_dir" || -n "$explicit_execution_mode" || -n "$explicit_artifact_target" || -n "$explicit_cloud_profile" || -n "$explicit_cloud_base_url" ]]; then
        if [[ -n "$explicit_data_dir" ]]; then
            explicit_data_dir="$(to_absolute_path "$explicit_data_dir")"
        fi
        existing_repo_root="$(read_state_value repo_root || true)"
        existing_source="$(read_state_value source || true)"
        save_skill_state "$existing_repo_root" "$existing_source" "$explicit_model" "$explicit_data_dir"
        if [[ -n "$explicit_execution_mode" || -n "$explicit_artifact_target" || -n "$explicit_cloud_profile" || -n "$explicit_cloud_base_url" ]]; then
            python - <<'PY' "$STATE_FILE" "$explicit_execution_mode" "$explicit_artifact_target" "$explicit_cloud_profile" "$explicit_cloud_base_url"
import json, sys, pathlib
path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
if sys.argv[2]:
    payload["execution_mode"] = sys.argv[2]
if sys.argv[3]:
    payload["artifact_target"] = sys.argv[3]
if sys.argv[4]:
    payload["cloud_profile"] = sys.argv[4]
if sys.argv[5]:
    payload["cloud_base_url"] = sys.argv[5]
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
        fi
    fi
fi

exec "$TOOL_PATH" "${args[@]}"
