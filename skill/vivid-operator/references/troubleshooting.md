# Troubleshooting（瞬知 / Vivid）

## 找不到 Vivid 仓库

按下面顺序检查：

1. `skill/vivid-operator/state/skill_state.json`
2. `VIVID_REPO_ROOT`
3. `-VividRoot` / `--vivid-root=...`

如果用户刚刚提供过仓库路径，但 agent 又忘了，优先回到状态文件里找，不要重复索要。

注意：状态文件里只能存这些稳定项：

- `repo_root`
- `default_whisper_model`
- `default_data_dir`
- `execution_mode`
- `artifact_target`
- `cloud_profile`
- `cloud_base_url`

不能存 `SESSDATA`、API Key 之类的敏感信息。

## Agent 又忘了默认模型或默认输出目录

按下面顺序处理：

1. 先看 `skill/vivid-operator/state/skill_state.json`
2. 再看 `VIVID_DEFAULT_MODEL` / `VIVID_DATA_DIR`
3. 只有前两者都没有时，才重新问用户

如果用户重新指定了值，下一次成功执行 wrapper 后应把它们写回 `skill_state.json`。

## agent 忘了本地模式还是云端模式

按下面顺序处理：

1. 先看 `skill/vivid-operator/state/skill_state.json`
2. 再看 `VIVID_EXECUTION_MODE` / `VIVID_ARTIFACT_TARGET`
3. 如果是云端，再看 `VIVID_CLOUD_BASE_URL`
4. 如果用户走的是 profile 模式，再看 `VIVID_CLOUD_PROFILE_<PROFILE>_BASE_URL`
4. 只有这些都没有时，才重新问用户

如果用户已经明确选过云端，就不要擅自回退到本地，除非云端配置失效并再次得到用户确认。

补充边界：

- 当前仓库里的云端模式默认直连远端 Vivid Web API
- 如果某个宿主平台通过 MCP 来调用，也应由 MCP 在仓库外转发到这个 Web API
- 不要把“当前没有内建 MCP server”误判成“cloud 模式不可用”

## `python` 不存在

先安装 Python 3.10+。

## `node` 不存在

先安装 Node.js。

抖音下载依赖 `tools/douyin/douyin.js`。

## `ffmpeg` 不存在

把 `ffmpeg` 加进 `PATH`，或者设置：

- `VIVID_FFMPEG_BIN`

## `torch` 不存在

内部 `Whisper` 转录依赖 `torch`。

如果 `doctor` 里 `torch=false`：

- CPU 环境通常可以先执行 `pip install -r requirements.txt`
- GPU / CUDA 环境建议先按官方 `PyTorch` 说明安装匹配版本的 `torch`
- 然后再重新执行 `doctor`

如果脚本检测到 **NVIDIA GPU** 并直接停止，不是报错逻辑坏了，而是在防止你把 `torch` 静默装成 CPU 版。

这时二选一：

1. 明确接受 CPU

```powershell
$env:VIVID_TORCH_MODE = "cpu"
```

```bash
export VIVID_TORCH_MODE=cpu
```

2. 明确安装 CUDA 版 `torch`

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

装完后再执行 `doctor`，确认 `torch` 可用且 `torch.cuda.is_available()` 为真。

## `opencv` 缺失 / `doctor` 显示 `opencv: false`

**这是正常的！** `opencv` **仅在 OCR 路径时需要**，音频转录（默认路径）**完全不需要**。

### 什么情况下需要担心 opencv？

只有当你明确使用以下参数时才需要：
- `--prefer-ocr`
- `--force-ocr`
- `VIVID_ACQUISITION_MODE=prefer_ocr` 或 `force_ocr`

### 默认路径（不需要 opencv）

1. **音频转录**（Whisper）- 默认
2. 失败 → **自动回退到 OCR** - 这时才需要 opencv

### 如果确实需要 opencv

程序会自动尝试执行：

`pip install opencv-python -i https://mirrors.aliyun.com/pypi/simple/`

**总结**：`doctor` 显示 `opencv: false` 但你能正常跑 quickread，**完全不用理会**。

## 内嵌下载器路径不存在

正常情况下不应该出现，因为下载器已内嵌到 `tools/` 目录。

如果确实出现：

- 检查是否正确克隆了仓库
- 检查 `tools/bilibili/` 和 `tools/douyin/` 目录是否存在

如需使用自定义下载器，可设置：

- `VIVID_BILI_SCRIPT`
- `VIVID_DOUYIN_SCRIPT`

## Bilibili 受限内容失败

检查：

- `BILI_SESSDATA`

如果 `quickread` 返回：

- `error_code = "bili_sessdata_expired"`

说明当前 `SESSDATA` 很可能已经失效。

这时 agent 应该先问用户要不要提供新的 `SESSDATA`：

- 提供了：用新的 `-Sessdata/--sessdata` 重试
- 不提供：改用 `-NoSessdata/--no-sessdata` 重试，显式忽略环境中的 `BILI_SESSDATA`

如果用户不知道怎么拿 `SESSDATA`，可以让他这样做：

1. 登录 `bilibili.com`
2. 按 `F12` 打开开发者工具
3. 打开 `Application` 或 `Storage`
4. 进入 `Cookies` -> `https://www.bilibili.com`
5. 复制 `SESSDATA` 的值

来源优先级也要说明清楚：

1. `-Sessdata` / `--sessdata`
2. `-NoSessdata` / `--no-sessdata`
3. `BILI_SESSDATA`

## `quickread.result = null`

说明 CLI 没有返回可解析 JSON。

优先看：

- `ok`
- `exit_code`
- `error`
- `error_code`
- `error_summary`
- `failure_chain`

## `Ears4` 或 `Eyes` 不可用

检查：

- `EARS4_API`
- `EYES_API`

但要先确认你是否真的需要回退模式。
