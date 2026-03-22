# Vivid Skill Cloud Mode Design

## 背景

当前 `vivid-operator` skill 只有一种执行方式：

- 本地 wrapper
- 本地 `scripts/vivid_tool.*`
- 本机 Python / ffmpeg / Whisper / OCR / 下载器

这适合单机使用，但不适合：

- 希望把 Whisper / OCR / 下载算力放到云服务器
- 本机环境不想装全套依赖
- 需要在本地与云端之间切换执行方式

目标是在 **不拆 skill** 的前提下，把 `vivid-operator` 扩展成双模式：

- `local`
- `cloud`

其中 `cloud` 的目标是调用云服务器上的 Vivid。
当前仓库内已经实现的是“直连远端 Vivid Web API”的执行端；
如果某个 agent 平台需要 MCP，可以在仓库外再加一层 MCP bridge 去转发到这个 Web API。

## 目标

新增一套可持久化的 skill 执行模式选择，使 agent 即使上下文丢失，也能先从 skill 状态文件恢复：

- 默认是本地执行还是云端执行
- 默认产物存储策略
- 默认云端连接配置

同时保持：

- 本地模式继续兼容现在的 wrapper / control surface
- skill 文档明确 agent 何时问用户、何时直接复用状态
- 远端返回仍尽量保持和本地 `quickread` 一致的 JSON 结构

## 非目标

这次设计不包含：

- 直接把 Vivid 重写成 MCP Server
- 直接对接向量数据库
- 云端多租户鉴权系统
- 大规模任务调度平台

本次只解决：

- skill 如何选本地或云端
- skill 如何调用云端 Vivid
- 产物如何落本地、云端或两边

## 推荐方案

保留单一 skill `vivid-operator`，新增第二执行后端：

- `local` -> 本地 wrapper 调 `scripts/vivid_tool.*`
- `cloud` -> skill 直接调用远端 Vivid Web API

如果外部运行环境本身采用 MCP，也建议 MCP 最终转发到 **Vivid Web API**，而不是直接远程 CLI。原因：

- JSON 协议更稳定
- 更容易返回任务状态
- 更适合下载、导出、轮询、同步产物
- 比远程执行 shell 命令更可控

## Skill 状态文件

继续使用单一状态文件：

- `skill/vivid-operator/state/skill_state.json`

在现有字段基础上新增：

- `execution_mode`
  - `local`
  - `cloud`
- `artifact_target`
  - `local_only`
  - `cloud_only`
  - `both`
- `cloud_profile`
  - 由 skill 使用的命名云端地址配置
- `cloud_base_url`
  - 远端 Vivid Web API 地址

保留现有字段：

- `repo_root`
- `default_whisper_model`
- `default_data_dir`

禁止写入：

- `SESSDATA`
- API Key
- 用户 token
- 任何一次性密钥

## 选择优先级

### 执行模式

1. 显式参数
2. 环境变量
3. `skill_state.json`
4. 缺值时询问用户

### 云端配置

1. 显式参数
2. 环境变量
3. `skill_state.json.cloud_profile` / `skill_state.json.cloud_base_url`
4. 当 `execution_mode = cloud` 且缺值时询问用户

### 产物策略

1. 显式参数
2. 环境变量
3. `skill_state.json.artifact_target`
4. 缺值时询问用户

### Whisper 模型与输出目录

保持现有规则：

1. 显式参数
2. 环境变量
3. `skill_state.json`
4. 程序默认值

## 用户交互规则

agent 必须先看 `skill_state.json`，只有缺值时才问。

第一次新增的交互顺序：

1. 先确认执行模式
   - 本地
   - 云端
2. 如果选云端，再确认远端地址
   - 如果用户已经配置了命名 profile，再确认 profile 名
   - 否则直接确认 `cloud_base_url`
3. 再确认产物策略
   - 本地
   - 云端
   - 两边
4. 如果缺默认 Whisper 模型，再问一次
5. 如果缺默认输出目录，再问一次

成功执行一次后，把这些稳定选择写回 `skill_state.json`。

## 云端执行协议

### 推荐链路

当前仓库内默认链路：

`vivid-operator skill` -> `Cloud Vivid Web API`

可选的外部集成链路：

`vivid-operator skill` -> `MCP bridge` -> `Cloud Vivid Web API`

### Web API 最小能力

云端需要至少提供：

- 提交任务
  - `POST /api/quickread`
- 查任务
  - `GET /api/jobs/{job_id}`
- 任务事件
  - `GET /api/jobs/{job_id}/events`
- 重试 / 继续
  - `POST /api/jobs/{job_id}/retry`
  - `POST /api/jobs/{job_id}/continue`
- 导出产物
  - `POST /api/jobs/export`
- 下载文件
  - `GET /api/download-file`

### MCP bridge 最小能力（可选，仓库外组件）

bridge 不做业务计算，只做转发：

- 提交云端 quickread
- 查询云端任务状态
- 拉取导出包或指定文件
- 返回结构化 JSON 给 skill

## 产物策略

### `local_only`

- 云端执行
- 结果完成后下载必要产物到本地
- skill 最终向用户报告本地路径

### `cloud_only`

- 云端执行
- 不主动同步本地文件
- skill 返回云端任务信息和云端产物引用

### `both`

- 云端执行
- 云端保留
- 同时下载一份到本地默认输出目录

## 本地同步范围

为了兼容当前工作流，建议先同步最核心产物：

- `artifacts/`
- `vector_source/`
- `metadata.json`

如果后端已有批量导出 ZIP，优先直接导出整个工作目录包，再本地解压到默认输出根目录。

## 对 skill 的影响

skill 文档需要增加：

- 本地 / 云端两种执行模式说明
- 缺值时如何问用户
- `skill_state.json` 新字段说明
- 当用户启用云端后，agent 不能擅自回落本地，除非云端配置失效并得到用户确认

## 对实现的影响

建议分 3 层实现：

1. skill 状态与文档层
   - 新增 `execution_mode` / `artifact_target` / `cloud_profile`
2. 执行抽象层
   - 将当前 wrapper 逻辑拆成 `local executor` / `cloud executor`
3. 云端桥接层
   - 当前仓库内直连云端 Web API
   - 如果宿主平台需要 MCP，则在仓库外增加 MCP bridge

## 风险

### 风险1：本地和云端返回结构不一致

要求 bridge 尽量透传本地 Web API 的 JSON 结构，避免 skill 写两套解析逻辑。

### 风险2：云端产物同步路径混乱

只有当 `artifact_target` 包含本地时才下载到本地，并统一落到 `default_data_dir`。

### 风险3：agent 忘记当前模式

通过 `skill_state.json` 持久化解决，agent 文档必须要求优先读取状态文件。

## 验证标准

满足以下行为即算成功：

1. skill 可在 `local` / `cloud` 之间稳定切换
2. 首次用户确认后，状态写回 `skill_state.json`
3. 上下文丢失后，agent 能从状态文件恢复执行模式
4. 云端成功时，能按 `artifact_target` 正确保留产物
5. 本地模式原有测试不回归
