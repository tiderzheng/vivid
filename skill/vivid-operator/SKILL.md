---
name: vivid-operator
description: Operate the Vivid project end-to-end through one stable command surface. Use when an agent needs to run the quickread workflow, validate the local environment, start the Web UI, or inspect outputs.
---

# Vivid Operator Skill

这个 skill 的职责只有一个：

**通过统一命令面去调用 **瞬知**（Vivid） 项目。**

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

## 主控制脚本

- Windows: `./scripts/vivid_tool.ps1`
- Linux/macOS: `./scripts/vivid_tool.sh`

## 常用动作

- `paths` - 查看路径配置
- `doctor` - 检查环境依赖
- `quickread` - 执行速看流程
- `web-ui` - 启动 Web UI

## quickread 的理解

`quickread` 是主动作。

它会把下面这些步骤串起来：

- 平台识别
- 下载 / 取字幕 / 取本地文件
- 转录或 OCR
- 摘要
- 落盘产物

## 依赖说明

这个 skill 不会自己实现视频处理。

它依赖：

- `python` (3.10+)
- `node` (仅 Douyin 下载需要)
- `ffmpeg`
- `torch` (内部 Whisper 转录需要)
- **瞬知**（Vivid） (主程序)

**注意**：Bilibili 和 Douyin 下载器已内嵌到 `tools/` 目录，开箱即用。

如果 `opencv` 缺失，**瞬知**（Vivid） 会自动尝试安装：

`pip install opencv-python -i https://mirrors.aliyun.com/pypi/simple/`

如果内部 `Whisper` 转录要运行，`torch` 也必须可用。

补充：

- CPU 环境通常直接执行 `pip install -r requirements.txt` 就够
- GPU / CUDA 环境建议先按官方 `PyTorch` 说明安装匹配版本的 `torch`
- 再安装 **瞬知**（Vivid） 其余依赖并跑 `doctor`

## 典型调用

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File "./scripts/vivid_tool.ps1" -Action paths
powershell -ExecutionPolicy Bypass -File "./scripts/vivid_tool.ps1" -Action doctor
powershell -ExecutionPolicy Bypass -File "./scripts/vivid_tool.ps1" -Action quickread -Source "<url-or-path>"
```

Linux/macOS:

```bash
./scripts/vivid_tool.sh -Action paths
./scripts/vivid_tool.sh -Action doctor
./scripts/vivid_tool.sh -Action quickread -Source "<url-or-path>"
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
