---
name: vivid-operator
description: Operate the Vivid project end-to-end through one stable command surface. Use when an agent needs to run the quickread workflow, validate the local environment, start the Web UI, or inspect outputs.
---

# Vivid Operator Skill

命令基准说明：

- 除非特别说明，下面的命令默认假设当前目录是 **Vivid 仓库根目录**
- 因此 wrapper 路径统一写成 `./skill/vivid-operator/scripts/vivid_operator.*`
- 如果当前目录已经是 `skill/vivid-operator/`，把前缀 `./skill/vivid-operator/` 去掉即可

这个 skill 的职责只有一个：

**通过统一命令面去调用瞬知（Vivid）项目。**

不要把它理解成"又一个下载 skill"。

正确关系是：

- `vivid-operator` = 统一 skill
- **瞬知**（Vivid） = 主程序（已内嵌 Bilibili 和 Douyin 下载器）
- `tools/bilibili/` / `tools/douyin/` = 内嵌的运行时下载器

## 当前下载器规则

这个 skill 在下载阶段使用以下下载器：

- `Bilibili` - 使用内嵌的 `tools/bilibili/bili23_agent_cli.py`
- `Douyin` - 使用内嵌的 `tools/douyin/douyin.js`
- `其他站点` - 使用 `yt_dlp`（通过 pip 安装）

所有下载器开箱即用，无需单独安装。

不要切换到其他单独 skill 去做下载。

## 标准流程

1. 先跑 `paths`
2. 再跑 `doctor`
3. 再跑 `quickread`
4. 最后读取 `artifacts`

## 项目位置

**瞬知 / Vivid** 主程序可以通过以下方式定位：

优先级：

1. `-VividRoot`
2. `VIVID_REPO_ROOT`
3. `skill/vivid-operator/state/skill_state.json`
4. skill 目录内自动检测
5. 询问用户

### 方式1：自动检测（推荐）

如果skill目录位于Vivid仓库的 `skill/vivid-operator/` 路径下，会自动检测主程序位置。

### 方式2：skill 状态文件

wrapper 会把稳定默认值写入：

- `skill/vivid-operator/state/skill_state.json`

当前持久化这些字段：

- `repo_root`
- `default_whisper_model`
- `default_data_dir`
- `execution_mode`
- `artifact_target`
- `cloud_profile`
- `cloud_base_url`

它们分别对应：

- Vivid 仓库根目录
- Whisper 默认模型
- 所有解析产物默认落到哪个输出根目录
- 默认走本地还是云端
- 云端执行后产物落本地、云端还是两边
- 云端连接配置名
- 远端 Vivid Web API 地址

agent 在上下文丢失后，必须优先从这个文件恢复这些稳定信息。

不要把下面这些敏感信息写进去：

- `SESSDATA`
- API Key
- 任何用户私密凭证

### 方式2.1：默认值优先级

默认 Whisper 模型和默认输出目录的选择顺序是：

1. 显式参数 `-Model` / `-DataDir`
2. 环境变量 `VIVID_DEFAULT_MODEL` / `VIVID_DATA_DIR`
3. `skill/vivid-operator/state/skill_state.json`
4. 主程序自己的默认值

只有当 `skill_state.json` 里缺少对应字段时，agent 才应该向用户询问一次。

执行模式的选择顺序是：

1. 显式参数 `-ExecutionMode` / `-ArtifactTarget` / `-CloudProfile` / `-CloudBaseUrl`
2. 环境变量 `VIVID_EXECUTION_MODE` / `VIVID_ARTIFACT_TARGET` / `VIVID_CLOUD_PROFILE` / `VIVID_CLOUD_BASE_URL`
3. `skill/vivid-operator/state/skill_state.json`
4. 默认 `local`

模式说明：

- `local`：使用本机资源、本机依赖、本机工作目录
- `cloud`：调用远端 Vivid Web API，由云端执行

产物策略：

- `local_only`：云端执行后把核心产物同步回本地
- `cloud_only`：只保留云端产物引用
- `both`：云端保留，本地也同步一份

`cloud_profile` 是可选项。
它只有在用户已经配置了命名云端地址时才有意义，例如：

- `VIVID_CLOUD_PROFILE_PROD_BASE_URL=https://cloud.example`

如果没有 profile 映射，agent 应该直接向用户要 `cloud_base_url`，不要把 `cloud_profile` 当成必填项。

补充边界：

- 当前仓库里的 `cloud` 模式是“skill 直接调用远端 Vivid Web API”
- 如果宿主平台本身走 MCP，可以在仓库外再加 MCP bridge 去转发到这个 Web API
- 不要把“外部 MCP bridge”理解成“当前 Vivid 仓库已经内建 MCP server”

### 方式3：环境变量

设置环境变量 `VIVID_REPO_ROOT`：

```powershell
$env:VIVID_REPO_ROOT = "D:\ai\quicker_video\Vivid"
```

```bash
export VIVID_REPO_ROOT=/home/user/vivid
```

### 方式4：参数指定

```powershell
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -VividRoot "D:\ai\quicker_video\Vivid" -Source "视频链接"
```

```bash
./skill/vivid-operator/scripts/vivid_operator.sh --vivid-root=/home/user/vivid -Action quickread -Source "视频链接"
```

### 主控制脚本

- Windows: `./scripts/vivid_tool.ps1`
- Linux/macOS: `./scripts/vivid_tool.sh`

## AI Agent 交互指南

如果你是AI Agent，请按以下步骤操作：

### 步骤1：尝试自动检测

首先尝试运行：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action paths
```

如果成功，说明 wrapper 已成功解析 Vivid 仓库位置。此时还应注意：

- wrapper 会把成功结果写入 `skill/vivid-operator/state/skill_state.json`
- 后续即使上下文丢失，agent 也应该优先从这个文件恢复仓库路径
- 不要反复向用户问同一个仓库路径问题

如果 `skill_state.json` 里还缺少 `default_whisper_model` 或 `default_data_dir`：

- 先分别向用户确认一次
- 然后用 `-Model` / `-DataDir` 执行一次，让 wrapper 把它们写入状态文件
- 之后 agent 应优先复用状态文件，不要重复问

如果 `skill_state.json` 里还缺少 `execution_mode` / `artifact_target` / `cloud_profile` / `cloud_base_url`：

- 先问用户默认走本地还是云端
- 如果用户选云端，再问产物只存本地、只存云端还是两边都存
- 如果用户已经有命名好的云端 profile，再问 profile 名
- 否则直接问远端 Vivid Web API 地址
- 成功执行一次后，把这些值写回状态文件

### 步骤2：如果自动检测失败

如果提示"无法找到Vivid仓库"，请按下面顺序处理：

1. 先检查 `skill/vivid-operator/state/skill_state.json`
2. 再检查 `VIVID_REPO_ROOT`
3. 如果两者都没有，才询问用户

询问用户时，用这类表达：

> "我需要使用瞬知/Vivid程序来处理视频，但没有找到它的安装位置。
> 
> 请提供Vivid仓库的路径，例如：
> - Windows: `D:\ai\quicker_video\Vivid`
> - Linux/macOS: `/home/user/vivid`
> 
> 或者您可以：
> 1. 设置环境变量 `VIVID_REPO_ROOT`
> 2. 将skill目录放到Vivid仓库的 `skill/vivid-operator/` 路径下"

### 步骤3：根据用户回答执行

**情况 A：skill 就在 Vivid 仓库里**

当前目录是 Vivid 仓库根目录时，直接用仓库内相对路径：

```powershell
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "视频链接"
```

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"
```

**情况 B：skill 安装在外部目录**

这时先告诉 wrapper 主程序仓库在哪里，再执行 skill 自己所在位置的脚本：

```powershell
$env:VIVID_REPO_ROOT = "D:\path\to\vivid"
C:\OpenClaw\skills\vivid-operator\scripts\vivid_operator.ps1 -Action quickread -Source "视频链接"
```

```bash
export VIVID_REPO_ROOT="/用户提供的/路径"
/opt/skills/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"
```

补充要求：

- 一旦用户提供了仓库路径，后续第一次成功执行 wrapper 后，这个路径就应该写入 `skill/vivid-operator/state/skill_state.json`
- 如果用户第一次确认了默认 Whisper 模型或默认输出目录，也应通过一次成功执行把它们写进去
- 如果用户第一次确认了云端模式、产物策略或远端地址，也应通过一次成功执行把它们写进去
- 如果用户使用的是 profile 模式，再把 `cloud_profile` 写进去
- 之后 agent 需要优先相信这个状态文件，而不是再次向用户确认
- 如果状态文件里的路径失效，再重新问用户
- 如果状态文件里缺的是模型或输出目录，只补问缺失项，不要整套重问
- 如果状态文件里缺的是执行模式或云端配置，也只补问缺失项

**如果用户说没有安装**：

> "Vivid尚未安装。我可以帮您：
> 1. 克隆仓库：`git clone https://github.com/tiderzheng/vivid.git`
> 2. 直接运行脚本，它会自动创建虚拟环境并安装依赖
> 3. 然后继续使用
> 
> 是否需要我帮您完成安装？"

### 前置条件检查

使用skill前，请确保：
1. 已克隆/下载 **瞬知 / Vivid** 仓库
2. 系统已安装：Python 3.10+、ffmpeg
3. 可选：Node.js（仅抖音下载需要）

**注意**：Python依赖会自动管理，无需手动安装！

### 自动虚拟环境（推荐）

**瞬知 / Vivid** 支持**自动虚拟环境管理**：

首次运行时，脚本会自动：
1. 创建虚拟环境（`.venv/`）
2. 安装所有Python依赖
3. 使用虚拟环境的Python运行

如果脚本检测到 **NVIDIA GPU**，会先在 `torch` 安装前停止，避免把 `Whisper` 静默装成 CPU 版。

这时需要二选一：

- CPU 路径：显式设置 `VIVID_TORCH_MODE=cpu` 后重跑
- CUDA 路径：先手动安装 CUDA 版 `torch`，再安装 `requirements.txt`

Windows 示例：

```powershell
# CPU
$env:VIVID_TORCH_MODE = "cpu"
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "视频链接"

# CUDA
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS 示例：

```bash
# CPU
export VIVID_TORCH_MODE=cpu
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"

# CUDA
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
./.venv/bin/python -m pip install -r requirements.txt
```

**直接使用**：
```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"
```

## Bilibili `SESSDATA` 交互规则

当 `Source` 是 **Bilibili** 链接时，按下面顺序处理：

### `SESSDATA` 获取方式

1. 登录 `bilibili.com`
2. 按 `F12` 打开开发者工具
3. 打开 `Application` 或 `Storage`
4. 进入 `Cookies` -> `https://www.bilibili.com`
5. 复制 `SESSDATA` 的值

### `SESSDATA` 来源优先级

1. `-Sessdata` / `--sessdata`
2. `-NoSessdata` / `--no-sessdata`
3. `BILI_SESSDATA` 环境变量

补充规则：

- `-Sessdata` 会覆盖环境变量里的 `BILI_SESSDATA`
- `-NoSessdata` 会显式忽略环境变量里的 `BILI_SESSDATA`
- 不要同时传 `-Sessdata` 和 `-NoSessdata`

### 交互流程

1. 如果当前已有 `BILI_SESSDATA`，或者用户明确提供了 `-Sessdata/--sessdata`，先用它尝试获取 **官方字幕**。
2. 如果 `quickread` 返回：
   - `error_code = "bili_sessdata_expired"`
   - `requires_user_input = true`
3. 你必须先询问用户：

> "当前 Bilibili 的 `SESSDATA` 可能已过期。请提供新的 `SESSDATA`。
>
> 如果你现在不提供，我会改用 `-NoSessdata/--no-sessdata` 重试，显式忽略旧会话，然后继续后续媒体下载 / 转录 / OCR 流程。"

4. 如果用户提供了新的 `SESSDATA`：

```powershell
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "B站链接" -Sessdata "<new-sessdata>"
```

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "B站链接" --sessdata "<new-sessdata>"
```

5. 如果用户不提供：
   - 不要再传 `-Sessdata/--sessdata`
   - 改为显式传 `-NoSessdata/--no-sessdata`
   - 然后重新执行同一个 `quickread`
   - 这次会跳过过期会话，继续媒体下载 / 转录 / OCR 兜底流程

不要在收到 `bili_sessdata_expired` 之后直接继续原来的结果。
这一步必须先问用户，再决定是“带新值重试”还是“清空后重试”。

### 环境检查（可选）

如果想检查环境状态：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action doctor
```

确认输出中包含：
- `python` - Python已安装
- `ffmpeg` - ffmpeg已安装
- `tools/bilibili/` - Bilibili下载器存在
- `tools/douyin/` - Douyin下载器存在

### 常见问题

**Whisper未安装错误**：
```
Cannot import whisper module. Install openai-whisper or set VIVID_WHISPER_ROOT
```

优先方案：

- 确保使用 `./skill/vivid-operator/scripts/vivid_operator.sh` 启动
- wrapper 会自动定位仓库并转发到主控制脚本

如果仍需手动修复：

```bash
./scripts/doctor.sh --fix

# 手动安装
pip install openai-whisper
```

安装完成后即可正常使用。

## 常用动作

- `paths` - 查看路径配置
- `doctor` - 检查环境依赖
- `quickread` - 执行速看流程
- `web-ui` - 启动 Web UI

## quickread 的理解

`quickread` 是主动作。

它会把下面这些步骤串起来：

1. **平台识别** - 自动识别Bilibili、抖音、本地文件等
2. **获取视频标题**（Bilibili/抖音）- 自动获取真实视频标题用于项目命名
3. **下载 / 取字幕 / 取本地文件**
4. **转录或 OCR** - 默认音频转录，失败自动回退OCR
5. **摘要** - AI生成标题、内容概览、核心观点、争议点、行动建议、俏皮点评
6. **落盘产物** - 输出结构化文档

## AI 总结返回规范

当 `quickread` 成功后，如果拿到了 `result.summary`、`summary.json` 或 `summary.md`，agent 必须按下面 6 段完整返回给用户：

1. 标题
2. 内容概览
3. 核心观点
4. 争议点
5. 行动建议
6. 俏皮点评

其中 `行动建议` 必须保留这些信息：

- 推荐相关阅读
- 继续学习什么
- 如何证真 / 交叉验证 / 辅助学习

禁止只返回下面这些残缺版本：

- 只摘标题
- 只摘核心观点
- 只给一段“简短总结”
- 只贴 `key_points`

如果控制面里同时有结构化字段和 `summary.md`，优先使用结构化字段；如果结构化字段缺失，再回退读取 `summary.md` / `summary.json`。

### 项目命名优化

对于 **Bilibili** 和 **抖音** 视频，**瞬知** 会自动获取视频真实标题作为项目名：

- **之前**：`BV1xx411c7mD`（视频ID）
- **之后**：`【官方双语】这才是最正确的学习方法...`（真实标题）

这样产物目录更清晰，方便后续查找和管理。

**注意**：如果用户指定了 `-ProjectName` 参数，会优先使用用户指定的名称。

## 依赖说明

这个 skill 不会自己实现视频处理。

### 核心依赖（必须）

- `python` (3.10+)
- `ffmpeg`
- **瞬知**（Vivid） (主程序)

### 可选依赖

- `node` - **仅 Douyin 下载需要**，不下载抖音视频可不装
- `torch` - **仅内部 Whisper 转录需要**，使用外部 API 转录可不装

### 关于 opencv

**重要说明**：`opencv` **仅在 OCR 路径（视频画面识别）时需要**。音频转录路径（默认）**不需要 opencv**。

- `doctor` 显示 `opencv: false` **完全正常**，不影响音频转录
- 只有当你明确使用 OCR 模式（`--prefer-ocr` 或 `--force-ocr`）时才需要
- 如果确实需要，**瞬知**（Vivid） 会自动尝试安装：
  - `pip install opencv-python -i https://mirrors.aliyun.com/pypi/simple/`

### 默认工作流程（无需 opencv）

1. **音频转录**（默认）- 使用 Whisper，不需要 opencv
2. 转录失败 → **自动回退到 OCR** - 这时才需要 opencv

所以大多数情况下，你**不需要关心 opencv**。

### 安装建议

- CPU 环境：直接执行 `pip install -r requirements.txt`
- GPU / CUDA 环境：先按官方 PyTorch 说明安装 `torch`，再执行 `pip install -r requirements.txt`
- 如果脚本检测到 `NVIDIA GPU`，又没有显式设置 `VIVID_TORCH_MODE=cpu`，它会主动停止并提示你做选择

**注意**：Bilibili 和 Douyin 下载器已内嵌到 `tools/` 目录，开箱即用。

## 典型调用

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "./skill/vivid-operator/scripts/vivid_operator.ps1" -Action paths
powershell -ExecutionPolicy Bypass -File "./skill/vivid-operator/scripts/vivid_operator.ps1" -Action doctor
powershell -ExecutionPolicy Bypass -File "./skill/vivid-operator/scripts/vivid_operator.ps1" -Action quickread -Source "<url-or-path>"
powershell -ExecutionPolicy Bypass -File "./skill/vivid-operator/scripts/vivid_operator.ps1" -Action quickread -Source "<bilibili-url>" -Sessdata "<sessdata>"
powershell -ExecutionPolicy Bypass -File "./skill/vivid-operator/scripts/vivid_operator.ps1" -Action quickread -Source "<bilibili-url>" -NoSessdata
```

Linux/macOS:

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action paths
./skill/vivid-operator/scripts/vivid_operator.sh -Action doctor
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "<url-or-path>"
```

## 产物目录

默认产物目录：

`./data/项目名/artifacts/`

同一个工作目录下，还会额外生成：

`./data/项目名/vector_source/`

主要文件：

- `quickread.md`
- `transcript.txt`
- `summary.md`
- `summary.json`
- `metadata.json`
- `vector_source/document.json`
- `vector_source/chunks.jsonl`
- `vector_source/manifest.json`

如果任务和下面这些目标有关：

- 向量化
- embedding
- RAG
- 知识库入库
- 向量数据库

agent 应优先读取 `vector_source/`，不要先从 `quickread.md`、`summary.md` 这类人类阅读版产物反解析。

## 补充说明

如果要给用户解释这套系统，优先这样说：

- 这是一个主程序 + 单 skill 项目
- skill 只负责统一调用
- 真正执行全流程的是 **瞬知**（Vivid）
- Bilibili 和 Douyin 下载器已内嵌，开箱即用

## References

- `references/workflow.md`
- `references/api-reference.md`
- `references/troubleshooting.md`
