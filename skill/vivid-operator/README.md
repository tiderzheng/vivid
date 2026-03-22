# 瞬知 / Vivid Operator Skill

这个 skill 面向 Codex、OpenClaw 和其他自动化 Agent。

它的职责很单一：

- 用一个稳定入口调用 **瞬知 / Vivid**
- 不在 skill 层重写下载、转录、OCR、摘要逻辑
- 把 Bilibili、Douyin、通用站点、本地文件都交给主程序处理

## 怎么把 skill 交给 Agent

可以，实际使用时你通常就是把这个 skill 的约束和一段任务说明直接发给 agent。

更具体一点：

- 先把 `vivid-operator` skill 放到 agent 能读取的位置
- 再把下面这些“标准说明话术”中的一段直接发给 agent
- agent 按 skill 里的规则先看状态文件，再决定是否询问你缺失项

如果第一次交互能成功跑通一次，wrapper 会把稳定默认值写进 `skill/vivid-operator/state/skill_state.json`。
后面即使 agent 丢了上下文，也应该先从这个状态文件恢复，而不是重新乱猜。

### 标准说明话术

#### 1. 最短通用版

适合：你已经把 skill 放好了，只想让 agent 直接开始。

```text
请使用 vivid-operator skill 调用 Vivid 来处理这个视频。
先执行 paths，再执行 doctor，再执行 quickread。
如果 skill 状态文件里缺少仓库路径、默认 Whisper 模型、默认输出目录、执行模式或云端地址，再向我询问一次；如果状态文件里已有值，优先复用，不要重复问。
```

#### 2. 本地模式首配版

适合：第一次让 agent 在本机跑。

```text
请使用 vivid-operator skill。
默认使用本地模式运行 Vivid。
Vivid 仓库路径是：D:\ai\quicker_video\Vivid
默认 Whisper 模型用：base
默认输出目录用：D:\ai\quicker_video\Vivid\data
先执行一次 quickread 让 wrapper 把这些值写入 skill_state.json，后续优先复用，不要重复问。
```

#### 3. 云端模式首配版

适合：第一次切到云服务器跑。

```text
请使用 vivid-operator skill。
默认使用云端模式运行 Vivid。
远端 Vivid Web API 地址是：http://你的服务器:8765
产物策略使用：both
默认输出目录用：D:\ai\quicker_video\Vivid\data
先执行一次 quickread，把 execution_mode、artifact_target、cloud_base_url 和默认输出目录写入 skill_state.json，后续优先复用。
```

#### 4. 命名 profile 版

适合：你已经配了命名云端地址。

```text
请使用 vivid-operator skill。
默认走云端模式。
我已经配置好了命名 cloud profile，请优先使用 profile：prod。
如果没有显式 cloud_base_url，就按 skill 规则解析 VIVID_CLOUD_PROFILE_<PROFILE>_BASE_URL。
产物策略用：both。
```

#### 5. Bilibili 会话交互版

适合：你知道这次是 B 站，而且可能需要 `SESSDATA`。

```text
请使用 vivid-operator skill 处理这个 Bilibili 链接。
如果 quickread 返回 error_code=bili_sessdata_expired，必须先问我是否提供新的 SESSDATA。
我提供了新值，就用 --sessdata 重试；
如果我不提供，就用 --no-sessdata 重试，显式忽略旧会话。
不要跳过这一步直接继续。
```

#### 6. 向量化产物版

适合：后续要做 embedding / RAG / 向量库导入。

```text
请使用 vivid-operator skill 处理这个视频。
完成后如果我要做向量化或知识库入库，请优先读取工作目录下的 vector_source/，不要优先从 quickread.md 或 summary.md 反解析。
```

#### 7. 强约束返回版

适合：你希望 agent 最后完整返回摘要而不是只说一句。

```text
请使用 vivid-operator skill 跑完整流程。
成功后必须完整返回这 6 段：标题、内容概览、核心观点、争议点、行动建议、俏皮点评。
不要只返回一句话标题，也不要只摘几点要点。
```

### 怎么组合使用

实际最常见的做法是把“通用版 + 当前场景版”一起发给 agent。

例如：

- 本地首次使用：`最短通用版 + 本地模式首配版`
- 云端首次使用：`最短通用版 + 云端模式首配版`
- B站链接：`最短通用版 + Bilibili 会话交互版`
- 要做 RAG：`最短通用版 + 向量化产物版`

## 推荐入口

优先使用 skill wrapper：

- Windows: `skill/vivid-operator/scripts/vivid_operator.ps1`
- Linux/macOS: `skill/vivid-operator/scripts/vivid_operator.sh`

底层主控制脚本是：

- Windows: `scripts/vivid_tool.ps1`
- Linux/macOS: `scripts/vivid_tool.sh`

## Skill 状态持久化

skill wrapper 会把稳定默认值写入：

- `skill/vivid-operator/state/skill_state.json`

目前持久化的字段有：

- `repo_root`
- `default_whisper_model`
- `default_data_dir`
- `execution_mode`
- `artifact_target`
- `cloud_profile`
- `cloud_base_url`

解析优先级是：

1. `-VividRoot` / `--vivid-root=...`
2. `VIVID_REPO_ROOT`
3. `skill/vivid-operator/state/skill_state.json`
4. skill 目录内自动检测

`quickread` 的默认 Whisper 模型和默认输出目录同样优先级为：

1. 显式参数 `-Model` / `-DataDir`
2. 环境变量 `VIVID_DEFAULT_MODEL` / `VIVID_DATA_DIR`
3. `skill/vivid-operator/state/skill_state.json`
4. 主程序自己的默认值

这个状态文件不会存 `SESSDATA`、API Key 或其他敏感信息。

执行模式相关优先级：

1. 显式参数 `-ExecutionMode` / `-ArtifactTarget` / `-CloudProfile` / `-CloudBaseUrl`
2. 环境变量 `VIVID_EXECUTION_MODE` / `VIVID_ARTIFACT_TARGET` / `VIVID_CLOUD_PROFILE` / `VIVID_CLOUD_BASE_URL`
3. `skill/vivid-operator/state/skill_state.json`
4. 本地模式默认值

模式说明：

- `local`：使用本机 Vivid、Python、ffmpeg、Whisper、OCR
- `cloud`：通过远端 Vivid Web API 执行，当前 skill 直接把请求发到云端

产物策略：

- `local_only`：云端执行后把核心产物同步回本地
- `cloud_only`：只保留云端产物引用
- `both`：云端保留，同时同步一份到本地

`cloud_profile` 是可选的命名配置。
如果没有显式传 `cloud_base_url`，程序会尝试用：

- `VIVID_CLOUD_BASE_URL`
- `VIVID_CLOUD_PROFILE_<PROFILE>_BASE_URL`

来解析实际的远端地址。

如果你的 agent 平台本身使用 MCP，也可以在仓库外增加一层 MCP bridge，再由 MCP 转发到这个远端 Vivid Web API。
这不要求当前 Vivid 仓库自身提供 MCP server。

## 环境前提

系统需要：

- Python 3.10+
- `ffmpeg`
- 可选：Node.js（仅抖音下载需要）

Python 依赖通常不需要手动安装。
脚本会自动创建 `.venv/` 并安装 `requirements.txt`。

如果检测到 **NVIDIA GPU**，脚本会先停止在 `torch` 安装前，避免把 `Whisper` 静默装成 CPU 版。

这时需要二选一：

- CPU 路径：先设置 `VIVID_TORCH_MODE=cpu`，再重跑
- CUDA 路径：先手动安装 CUDA 版 `torch`，再安装 `requirements.txt`

Windows:

```powershell
$env:VIVID_TORCH_MODE = "cpu"
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "视频链接"
```

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS:

```bash
export VIVID_TORCH_MODE=cpu
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"
```

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
./.venv/bin/python -m pip install -r requirements.txt
```

## 基本用法

先确认路径：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action paths
```

如果这是用户第一次告诉 agent 仓库路径、默认 Whisper 模型或默认输出目录，成功执行一次后，后续应优先复用 `skill/vivid-operator/state/skill_state.json`，不要反复问同一个问题。

再检查环境：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action doctor
```

最后执行：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"
```

如果用户第一次选择云端模式，建议执行一次：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接" --execution-mode cloud --artifact-target both --cloud-base-url "https://cloud.example"
```

这样后续即使 agent 丢上下文，也能先从 `skill_state.json` 恢复是本地还是云端。

如果用户已经配置了命名云端 profile，也可以这样：

```bash
export VIVID_CLOUD_PROFILE_PROD_BASE_URL="https://cloud.example"
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接" --execution-mode cloud --artifact-target both --cloud-profile prod
```

## Bilibili `SESSDATA`

如果是 Bilibili 链接：

- 有 `SESSDATA` 时，会先尝试拿官方字幕
- 如果返回 `error_code = "bili_sessdata_expired"`，先问用户是否提供新的 `SESSDATA`
- 用户提供了：用 `-Sessdata/--sessdata` 重试
- 用户不提供：用 `-NoSessdata/--no-sessdata` 重试，显式忽略环境中的旧 `BILI_SESSDATA`

来源优先级：

1. `-Sessdata` / `--sessdata`
2. `-NoSessdata` / `--no-sessdata`
3. `BILI_SESSDATA`

如果用户不知道怎么拿 `SESSDATA`：

1. 登录 `bilibili.com`
2. 按 `F12` 打开开发者工具
3. 打开 `Application` 或 `Storage`
4. 进入 `Cookies` -> `https://www.bilibili.com`
5. 复制 `SESSDATA` 的值

示例：

```powershell
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "https://www.bilibili.com/video/BVxxxx" -Sessdata "<new-sessdata>"
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "https://www.bilibili.com/video/BVxxxx" -NoSessdata
```

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "https://www.bilibili.com/video/BVxxxx" --sessdata "<new-sessdata>"
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "https://www.bilibili.com/video/BVxxxx" --no-sessdata
```

## 输出

默认输出目录：

- `./data/项目名/artifacts/`

如果用户已经在 skill 状态文件里确认过默认输出目录，agent 应优先使用那个目录，而不是临时猜测别的位置。

常见文件：

- `quickread.md`
- `transcript.txt`
- `summary.md`
- `summary.json`
- `metadata.json`

同一个工作目录下，还会额外生成：

- `vector_source/document.json`
- `vector_source/chunks.jsonl`
- `vector_source/manifest.json`

这组文件是面向未来向量化 / embedding / RAG / 知识库入库准备的程序消费产物。
如果 agent 的任务和向量数据库有关，优先读取 `vector_source/`，不要优先从 `quickread.md` 反解析。

## Agent 返回要求

当 agent 读取到摘要结果后，应完整返回以下 6 段：

1. 标题
2. 内容概览
3. 核心观点
4. 争议点
5. 行动建议
6. 俏皮点评

不要只摘一句标题或几条要点。尤其是 `行动建议`，要把推荐阅读、继续学习方向、以及证真/交叉验证建议一起带上。
