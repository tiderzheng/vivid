# Vivid / 瞬知

> **瞬知**（英文名：**Vivid**）是一个面向视频"速看"的统一项目。  
> "瞬知"寓意：瞬间知晓视频内容，让信息获取更高效。

它的目标很直接：

- 输入一个视频链接，或一个本地视频 / 音频文件
- 自动拿到文本
- 自动生成摘要
- 输出一套可读、可存档、可继续处理的结果文件

这个项目同时提供两层入口：

- **程序入口**：给普通用户直接运行
- **skill 入口**：给 `OpenClaw`、`Codex` 这类 AI agent 调用

所以可以把它理解为：

- **瞬知 / Vivid** = 真正执行全流程的程序
- `vivid-operator` = 调用 **瞬知** 的统一 skill

### 入口边界

这两层入口面向的对象不同：

- 仓库级 `README` 和 `docs/` 默认面向普通用户或开发者，因此主入口写成 `scripts/vivid_tool.ps1` / `scripts/vivid_tool.sh`
- `skill/vivid-operator/` 下的文档默认面向 AI agent，因此主入口写成 `skill/vivid-operator/scripts/vivid_operator.ps1` / `skill/vivid-operator/scripts/vivid_operator.sh`

两者不是两套不同实现：

- `vivid_operator.*` 是 skill wrapper，负责定位仓库并转发参数
- `vivid_tool.*` 是仓库内的主控制脚本

## 这个项目能做什么

- 处理 `Bilibili` 视频链接
- 处理 `Douyin` 视频链接
- 处理其他常见视频站点链接
- 处理本地视频文件
- 处理本地音频文件
- 生成逐字稿
- 生成一句话总结
- 生成详细摘要
- 生成关键要点
- 保存标准化产物，方便继续加工

## 适合谁用

- 想把视频快速变成文字的人
- 想做视频资料整理的人
- 想让 AI agent 稳定调用速看流程的人
- 想把分散工具收口成一个项目的人

## 当前真实工作流

**瞬知** 现在的实际工作流如下。

### 1. 输入来源

支持两类输入：

- 视频链接
- 本地文件路径

### 2. 平台识别和媒体获取

不同来源会走不同的获取路径：

- **本地文件**
  - 直接使用本地视频 / 音频
- **Bilibili**
  - 优先尝试直接提取字幕
  - `SESSDATA` 来源优先级是：`--sessdata` > `--no-sessdata` > `BILI_SESSDATA`
  - 如果配置了 `SESSDATA`，会先用它尝试获取官方字幕
  - 如果控制面返回 `error_code = "bili_sessdata_expired"`，应先更新 `SESSDATA`；如果用户不提供，再用 `--no-sessdata` 显式忽略旧会话后继续媒体流程
  - 如果拿不到字幕，再下载媒体
  - 使用内嵌的下载器（位于 `tools/bilibili/`）
- **Douyin**
  - 使用内嵌的下载器（位于 `tools/douyin/`）下载视频
- **其他站点**
  - 使用 `yt_dlp` 作为通用兜底下载器

也就是说，当前下载链路的口径是：

- `Bilibili -> tools/bilibili/bili23_agent_cli.py`（已内嵌）
- `Douyin -> tools/douyin/douyin.js`（已内嵌）
- `Generic -> yt_dlp`（pip安装）

### 3. 文本获取

拿到媒体后，**瞬知** 会继续获取文本。

默认主路径是：

- **音频转录**
  - 使用内部 `Whisper`
  - 这条链路会用到 `torch`

当需要 OCR 时，会走：

- **视频 OCR**
  - `opencv` 负责抽帧
  - OpenAI 兼容视觉 API 负责识别字幕

可选回退路径：

- 内部转录失败时，可回退到 `Ears4`
- 内部 OCR 失败时，可回退到 `Eyes`

### 4. 摘要生成

在拿到文本后，**瞬知** 会生成摘要。

默认策略：

1. `SiliconFlow`
2. `DashScope`
3. 规则摘要兜底

摘要提示词现在也支持配置化：

- 默认文件：`configs/summary/prompts.json`
- 默认模板占位符：`{transcript}`
- 可用环境变量：
  - `VIVID_SUMMARY_PROMPT_ID`
  - `VIVID_SUMMARY_SYSTEM_PROMPT`
  - `VIVID_SUMMARY_USER_PROMPT`
  - `VIVID_SUMMARY_PROMPTS_FILE`

### 5. 产物输出

每次运行都会落盘一套标准产物：

- `quickread.md`
- `transcript.txt`
- `summary.md`
- `summary.json`
- `metadata.json`

默认输出目录形如：

- Windows: `.\data\项目名\artifacts\`
- Linux/macOS: `./data/项目名/artifacts/`

## 项目结构

- `app/`
  - 核心程序
- `tools/`
  - 内嵌的下载器（Bilibili、Douyin）
- `scripts/`
  - PowerShell 和 Bash 控制脚本
- `skill/vivid-operator/`
  - 给 AI agent 使用的 skill
- `configs/`
  - OCR / 转录等配置
- `docs/`
  - 安装、配置、示例、设计文档
- `tests/`
  - 自动化测试
- `data/`
  - 运行产物（已被gitignore排除）

## 快速开始

### 1. 系统依赖

**必需**：
- Python 3.10+
- ffmpeg

**可选**：
- Node.js（仅下载抖音视频时需要）

**注意**：Bilibili和Douyin下载器已内嵌到 `tools/` 目录，无需额外安装。

### 2. 开始使用（自动虚拟环境）

**瞬知 / Vivid** 现在支持**自动虚拟环境管理**！

如果你是直接在仓库里使用本项目，优先用这里的 `scripts/vivid_tool.*`。
如果你是在 skill / agent 场景里调用，请改看 `skill/vivid-operator/` 下的 wrapper 文档。

首次运行时，脚本会自动：
1. 创建虚拟环境（`.venv/`）
2. 安装所有Python依赖
3. 使用虚拟环境的Python运行

**Windows:**

```powershell
# 直接运行，自动创建虚拟环境并安装依赖
.\scripts\vivid_tool.ps1 -Action quickread -Source "https://www.bilibili.com/video/BVxxxx"
```

**Linux/macOS:**

```bash
# 直接运行，自动创建虚拟环境并安装依赖
./scripts/vivid_tool.sh -Action quickread -Source "https://www.bilibili.com/video/BVxxxx"
```

### 3. 手动安装（可选）

如果你想手动控制虚拟环境：

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境（Windows）
.venv\Scripts\Activate.ps1

# 激活虚拟环境（Linux/macOS）
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 依赖说明

- `opencv` 缺失时，**瞬知** 会在进入 OCR 路径时自动尝试安装
- `openai-whisper` 会间接拉起 `torch` 依赖；如果改用外部转录 API，可以不依赖本地 `torch`
- 首次使用某个Whisper模型时，会自动下载模型文件

### 2. 检查环境

Windows:

```powershell
.\scripts\vivid_tool.ps1 -Action paths
.\scripts\vivid_tool.ps1 -Action doctor
```

Linux/macOS:

```bash
./scripts/vivid_tool.sh -Action paths
./scripts/vivid_tool.sh -Action doctor
```

`doctor` 会检查：

- `python`
- `node`（Douyin下载需要）
- `ffmpeg`
- `whisper`（openai-whisper包）
- `torch`（仅内部 Whisper 转录需要）
- `opencv`（仅 OCR 路径需要，会自动安装）
- 内嵌下载器（`tools/bilibili/`、`tools/douyin/`）
- 内部配置文件

### 3. 跑一次速看

Windows:

```powershell
.\scripts\vivid_tool.ps1 -Action quickread -Source "https://www.bilibili.com/video/BVxxxx"
```

Linux/macOS:

```bash
./scripts/vivid_tool.sh -Action quickread -Source "https://www.bilibili.com/video/BVxxxx"
```

或本地文件：

```powershell
.\scripts\vivid_tool.ps1 -Action quickread -Source "D:\videos\demo.mp4" -Platform local
```

## Web UI

启动方式：

Windows:

```powershell
.\scripts\run_web_ui.ps1
```

Linux/macOS:

```bash
./scripts/run_web_ui.sh
```

或：

Windows:

```powershell
.\scripts\vivid_tool.ps1 -Action web-ui
```

Linux/macOS:

```bash
./scripts/vivid_tool.sh -Action web-ui
```

打开：

`http://127.0.0.1:8765`

Web UI 支持：

- 拖拽上传本地视频 / 音频
- 直接填写视频链接
- 在文本框中一次粘贴多个链接，按同一套参数批量提交
- 指定当前任务输出目录
- 保存默认输出目录
- 选择 `Whisper` 模型
- 设置采集策略，支持 `smart` 智能推荐
- 设置转录后端 / OCR 后端
- 填写 Bilibili `SESSDATA`，或显式忽略环境中的 `BILI_SESSDATA`
- 同一次任务里，表单显式填写的 `SESSDATA` 优先于环境变量；如果选择忽略 `SESSDATA`，则会显式跳过环境变量
- 选择或填写 OCR OpenAI 兼容 API 配置
- 保存默认 OCR API 配置
- 查看任务进度、日志、历史任务
- 在历史任务里批量选择并导出多个任务产物 zip
- 任务失败后根据 checkpoint 从 `transcription` / `summarize` / `render` / `artifacts` 继续
- Web 历史详情会展示结构化失败链；成功任务的 `metadata.json` 也会保留回退和失败轨迹
- 如果 Bilibili `SESSDATA` 过期，任务详情会直接提供“使用表单中的新 `SESSDATA` 重试”和“忽略 `SESSDATA` 继续”两个动作
- 下载产物
- 一键打开输出目录

`smart` 模式的规则是：

- `Bilibili` 能直接拿到官方字幕时，仍优先官方字幕
- 视频检测到明显硬字幕时，自动等效 `prefer_ocr`
- 未检测到明显硬字幕时，优先常规转录
- 如果前面的推荐路径失败，OCR 兜底仍保留

## AI 配置归属

这个点很重要。

### 摘要 AI

摘要模型由 **瞬知** 自己配置。

主要变量：

- `SILICONFLOW_API_KEY`
- `DASHSCOPE_API_KEY`
- `VIVID_SILICONFLOW_MODEL`
- `VIVID_DASHSCOPE_MODEL`
- `VIVID_SUMMARY_PROMPT_ID`
- `VIVID_SUMMARY_SYSTEM_PROMPT`
- `VIVID_SUMMARY_USER_PROMPT`

默认摘要模板文件：

- `configs/summary/prompts.json`

### OCR AI

OCR 默认也由 **瞬知** 自己配置。

主要变量：

- `VIVID_VISION_API_BASE`
- `VIVID_VISION_API_PATH`
- `VIVID_VISION_API_KEY`
- `VIVID_VISION_MODEL`
- `VIVID_VISION_PROMPT`
- `VIVID_VISION_SYSTEM_PROMPT`

当前支持标准 **OpenAI 兼容格式**。

### 转录

默认优先使用 **瞬知** 内部 `Whisper`。

主要变量：

- `VIVID_TRANSCRIPTION_BACKEND`
- `VIVID_TRANSCRIPTION_PRESET_ID`
- `VIVID_DEFAULT_MODEL`

### 回退服务

只有在你保留兼容回退时，才需要：

- `EARS4_API`
- `EYES_API`

## 下载器说明

当前项目已内嵌下载器，开箱即用：

- `Bilibili`
  - 内嵌路径：`tools/bilibili/bili23_agent_cli.py`
  - 来源项目：`bili-downloader-agent`（已内嵌）
- `Douyin`
  - 内嵌路径：`tools/douyin/douyin.js`
  - 来源项目：`douyin-download`（已内嵌）
- `其他站点`
  - 使用 `yt_dlp`（通过pip安装）

如需使用自定义下载器，可通过环境变量覆盖：

- `VIVID_BILI_SCRIPT` - 自定义Bilibili下载器路径
- `VIVID_DOUYIN_SCRIPT` - 自定义Douyin下载器路径

## skill 怎么理解

`vivid-operator` 是统一 skill。

这意味着：

- AI agent 侧通常只需要加载一个 skill
- 这个 skill 内部再去调用 **瞬知**
- **瞬知** 已内嵌 `bilibili` 和 `douyin` 下载器，开箱即用
- 同时支持 `Whisper`、OCR API、摘要 API

所以正确关系是：

- **一个 skill**
- **一个主程序（瞬知 / Vivid）**
- **若干运行时依赖**

不是一堆 skill 互相跳来跳去。

## 你最常用的几个命令

### 查看路径

```powershell
.\scripts\vivid_tool.ps1 -Action paths
```

### 环境检查

```powershell
.\scripts\vivid_tool.ps1 -Action doctor
```

### 跑 Bilibili

```powershell
.\scripts\vivid_tool.ps1 -Action quickread -Source "https://www.bilibili.com/video/BVxxxx"
```

### 跑 Douyin

```powershell
.\scripts\vivid_tool.ps1 -Action quickread -Source "https://v.douyin.com/xxxxx/"
```

### 跑本地文件

```powershell
.\scripts\vivid_tool.ps1 -Action quickread -Source "D:\videos\demo.mp4" -Platform local
```

### 启动 Web UI

```powershell
.\scripts\vivid_tool.ps1 -Action web-ui
```

## 常见问题

### 为什么会出现 `opencv`

因为内部视频 OCR 要先从视频抽帧，`opencv` 就是做这个的。

它不是下载器，不是总结模型，也不是 Whisper。
如果你只走默认音频转录路径，通常不需要手动关心它。

### 为什么会出现 `torch`

因为内部 `Whisper` 转录依赖 `torch`。

所以只要你使用：

- **瞬知** 内部转录

通常就会用到 `torch`。
如果你改用外部转录 API，`torch` 就不是主路径必需项。

### 为什么会出现 `Node.js`

因为 `Douyin` 下载器（`tools/douyin/douyin.js`）是 `Node.js` 脚本。该下载器已内嵌，但你仍需安装Node.js运行时。

### 为什么还会看到 `bili-downloader-agent`

因为 `Bilibili` 下载 helper 来源于这套工具。
当前用户真正接触到的是仓库里的 `tools/bilibili/bili23_agent_cli.py`，不是单独安装一个外部项目。

### 什么时候会用到 `Eyes` / `Ears4`

只有在你保留兼容回退时。

默认主路径已经优先在 **瞬知** 内部执行。

## 相关文档

- `docs/安装与依赖.md`
- `docs/配置说明.md`
- `docs/使用示例.md`
- `skill/vivid-operator/SKILL.md`
- `REQUIREMENTS.md`
