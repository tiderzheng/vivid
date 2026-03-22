# API Reference（瞬知 / Vivid）

## Skill Wrapper

推荐 skill 入口：

- Windows: `skill/vivid-operator/scripts/vivid_operator.ps1`
- Linux/macOS: `skill/vivid-operator/scripts/vivid_operator.sh`

底层主控制脚本：

- Windows: `scripts/vivid_tool.ps1`
- Linux/macOS: `scripts/vivid_tool.sh`

wrapper 的仓库定位优先级：

1. `-VividRoot` / `--vivid-root=...`
2. `VIVID_REPO_ROOT`
3. `skill/vivid-operator/state/skill_state.json`
4. skill 目录内自动检测

wrapper 的默认值定位优先级：

1. `-Model` / `-DataDir`
2. `VIVID_DEFAULT_MODEL` / `VIVID_DATA_DIR`
3. `skill/vivid-operator/state/skill_state.json`
4. Vivid 主程序默认值

wrapper 的执行模式优先级：

1. `-ExecutionMode` / `-ArtifactTarget` / `-CloudProfile` / `-CloudBaseUrl`
2. `VIVID_EXECUTION_MODE` / `VIVID_ARTIFACT_TARGET` / `VIVID_CLOUD_PROFILE` / `VIVID_CLOUD_BASE_URL`
3. `skill/vivid-operator/state/skill_state.json`
4. 默认 `local`

`cloud_profile` 说明：

- `cloud_profile` 是可选的命名配置
- 如果没有显式 `cloud_base_url`，程序会尝试读取 `VIVID_CLOUD_PROFILE_<PROFILE>_BASE_URL`
- 如果没有 profile 映射，就直接使用 `cloud_base_url`
- 当前仓库里的 `cloud` 模式默认直连远端 Vivid Web API
- 如果外部运行环境需要 MCP，MCP 应该作为仓库外桥接层转发到这个 Web API

## `paths`

作用：

- 返回仓库路径
- 返回脚本路径
- 返回 skill 路径
- 返回内嵌下载器路径
- 返回配置路径

## `doctor`

作用：

- 检查运行环境
- 检查内嵌下载器路径
- 检查关键配置文件
- 返回结构化检查结果

## `quickread`

作用：

- 跑完整速看流程

说明：

- 下面列的是核心参数，适合作为 skill 调用参考
- 这不是控制面的完整参数枚举；完整能力以 `app.control_cli` 实际实现为准

必要参数：

- `-Source`

常用参数：

- `-ProjectName`
- `-DataDir`
- `-Platform`
- `-Model`
- `-ExecutionMode`
- `-ArtifactTarget`
- `-CloudProfile`
- `-CloudBaseUrl`
- `-AcquisitionMode`
- `-PreferOcr`
- `-ForceOcr`
- `-TranscriptionBackend`
- `-VisionBackend`
- `-NoKeepFiles`

摘要相关参数：

- `-SummaryPromptId` / `--summary-prompt-id`
- `-SummarySystemPrompt` / `--summary-system-prompt`
- `-SummaryUserPrompt` / `--summary-user-prompt`
- `-SummaryPromptsFile` / `--summary-prompts-file`

OCR / Vision 常用参数：

- `-VisionApiConfigId` / `--vision-api-config-id`
- `-VisionTimeout` / `--vision-timeout`
- `-VisionSampleMs` / `--vision-sample-ms`
- `-VisionMinDurationMs` / `--vision-min-duration-ms`

Bilibili 专用参数：

- `-Sessdata` / `--sessdata`
- `-NoSessdata` / `--no-sessdata`

规则：

- `-Sessdata` 用于显式提供新的会话，优先级高于 `BILI_SESSDATA`
- `-NoSessdata` 用于显式忽略环境中的 `BILI_SESSDATA`
- 如果两者都不传，才会回退到环境变量 `BILI_SESSDATA`
- 不要同时传 `-Sessdata` 和 `-NoSessdata`

skill 状态文件说明：

- `skill_state.json` 只持久化稳定默认值
- 当前字段：`repo_root`、`default_whisper_model`、`default_data_dir`、`execution_mode`、`artifact_target`、`cloud_profile`、`cloud_base_url`
- agent 只在这些字段缺值时才应该向用户询问

## `web-ui`

作用：

- 启动本地 Web UI

## 返回字段

控制面通常返回 JSON。

常见字段：

- `ok`
- `exit_code`
- `result`
- `error`
- `error_code`
- `requires_user_input`
- `can_continue_without_sessdata`

`result` 成功时通常包含：

- `result.source`
  - `raw_source`
  - `platform`
  - `title`
- `result.transcript`
  - `acquisition_method`
  - `text`
- `result.summary`
  - `title`
  - `overview`
  - `core_points`
  - `controversies`
  - `action_suggestions`
  - `playful_comment`
  - `provider`
- `result.artifacts`
  - `workdir`
  - `artifacts_dir`
  - `vector_source_dir`
  - `vector_document_json`
  - `vector_chunks_jsonl`
  - `vector_manifest_json`
- `result.failure_chain`
- `result.error_summary`

说明：

- `result.artifacts.artifacts_dir` 是读取产物文件的主要目录
- `result.artifacts.vector_source_dir` 是后续向量化 / embedding 的优先入口
- 早期失败时，`result` 可能为 `null`
- 为兼容旧调用方，`result.summary` 里仍可能同时出现 `one_line` / `detailed` / `key_points`，但新 agent 应优先读取新字段

当 Bilibili 会话过期时，`quickread` 可能返回：

- `error_code = "bili_sessdata_expired"`
- `requires_user_input = true`
- `can_continue_without_sessdata = true`

此时 skill 应先问用户，再决定用 `-Sessdata` 还是 `-NoSessdata` 重试。
