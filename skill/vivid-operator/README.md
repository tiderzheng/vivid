# 瞬知 / Vivid Operator Skill

这个 skill 面向 Codex、OpenClaw 和其他自动化 Agent。

它的职责很单一：

- 用一个稳定入口调用 **瞬知 / Vivid**
- 不在 skill 层重写下载、转录、OCR、摘要逻辑
- 把 Bilibili、Douyin、通用站点、本地文件都交给主程序处理

## 推荐入口

优先使用 skill wrapper：

- Windows: `skill/vivid-operator/scripts/vivid_operator.ps1`
- Linux/macOS: `skill/vivid-operator/scripts/vivid_operator.sh`

底层主控制脚本是：

- Windows: `scripts/vivid_tool.ps1`
- Linux/macOS: `scripts/vivid_tool.sh`

## 仓库路径持久化

skill wrapper 会把最近一次确认成功的 Vivid 仓库根目录写入：

- `skill/vivid-operator/state/repo_root.json`

解析优先级是：

1. `-VividRoot` / `--vivid-root=...`
2. `VIVID_REPO_ROOT`
3. `skill/vivid-operator/state/repo_root.json`
4. skill 目录内自动检测

这个状态文件只缓存仓库路径，不会存 `SESSDATA`、API Key 或其他敏感信息。

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

如果这是用户第一次告诉 agent 仓库路径，成功执行一次后，后续应优先复用 `skill/vivid-operator/state/repo_root.json`，不要反复问同一个问题。

再检查环境：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action doctor
```

最后执行：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"
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
