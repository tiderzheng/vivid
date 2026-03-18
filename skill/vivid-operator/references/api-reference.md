# API Reference（瞬知 / Vivid）

## Skill Wrapper

推荐 skill 入口：

- Windows: `skill/vivid-operator/scripts/vivid_operator.ps1`
- Linux/macOS: `skill/vivid-operator/scripts/vivid_operator.sh`

底层主控制脚本：

- Windows: `scripts/vivid_tool.ps1`
- Linux/macOS: `scripts/vivid_tool.sh`

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
  - `one_line`
  - `detailed`
  - `key_points`
  - `provider`
- `result.artifacts`
  - `workdir`
  - `artifacts_dir`
- `result.failure_chain`
- `result.error_summary`

说明：

- `result.artifacts.artifacts_dir` 是读取产物文件的主要目录
- 早期失败时，`result` 可能为 `null`

当 Bilibili 会话过期时，`quickread` 可能返回：

- `error_code = "bili_sessdata_expired"`
- `requires_user_input = true`
- `can_continue_without_sessdata = true`

此时 skill 应先问用户，再决定用 `-Sessdata` 还是 `-NoSessdata` 重试。
