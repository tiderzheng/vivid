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

### 方式1：自动检测（推荐）

如果skill目录位于Vivid仓库的 `skill/vivid-operator/` 路径下，会自动检测主程序位置。

### 方式2：环境变量

设置环境变量 `VIVID_REPO_ROOT`：

```powershell
$env:VIVID_REPO_ROOT = "D:\ai\quicker_video\Vivid"
```

```bash
export VIVID_REPO_ROOT=/home/user/vivid
```

### 方式3：参数指定

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

如果成功，说明已自动检测到Vivid仓库，可以继续使用。

### 步骤2：如果自动检测失败

如果提示"无法找到Vivid仓库"，请**询问用户**：

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
5. **摘要** - AI生成一句话总结、详细摘要、关键要点
6. **落盘产物** - 输出结构化文档

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

主要文件：

- `quickread.md`
- `transcript.txt`
- `summary.md`
- `summary.json`
- `metadata.json`

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
