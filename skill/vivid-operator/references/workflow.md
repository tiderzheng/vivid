# Workflow（瞬知 / Vivid）

这是 `vivid-operator` 的推荐执行顺序。

## 0. 定位仓库

优先执行：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action paths
```

如果自动检测失败：

1. 先看 `skill/vivid-operator/state/skill_state.json`
2. 再看 `VIVID_REPO_ROOT`
3. 还不行再让用户提供 Vivid 仓库路径

一旦用户给出了有效路径并成功执行 wrapper，后续应优先复用状态文件，不要重复询问。

如果 `skill_state.json` 里还没有 `default_whisper_model` 或 `default_data_dir`：

1. 先问用户想把 Whisper 默认模型设成什么
2. 再问用户希望所有解析产物默认落到哪个输出根目录
3. 第一次成功执行后，让 wrapper 写回 `skill_state.json`

如果状态文件里已经有这两个值，agent 不要每次重问。

如果 `skill_state.json` 里还没有 `execution_mode` / `artifact_target` / `cloud_profile` / `cloud_base_url`：

1. 先问用户默认走本地还是云端
2. 如果选云端，再问产物默认只存本地、只存云端还是两边都存
3. 如果用户已经配置了命名 profile，再确认 profile 名
4. 如果没有 profile，就直接确认远端 Vivid Web API 地址
4. 成功执行一次后写回 `skill_state.json`

补充说明：

- 当前仓库内的云端模式默认直连远端 Vivid Web API
- 如果宿主环境已经有 MCP，可以让 MCP 在仓库外转发到这个 Web API
- agent 不要因为提到 MCP 就假设当前仓库里一定存在 MCP server

## 1. 环境检查

执行：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action doctor
```

如果自动建环境步骤检测到 **NVIDIA GPU** 并中止：

- 先确认用户是想走 CPU 还是 CUDA
- CPU：设置 `VIVID_TORCH_MODE=cpu` 后重试
- CUDA：先手动安装 CUDA 版 `torch`，再继续 `doctor` / `quickread`

重点看：

- `python`
- `ffmpeg`
- `bilibili helper`
- `douyin helper`
- 可选：`node`

`opencv: false` 不一定是问题。
默认音频转录路径不依赖 `opencv`。

## 2. 执行 quickread

执行：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接"
```

如果用户已经确认过默认模型或默认输出目录，也可以显式这样执行一次来写入状态文件：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接" -Model large -DataDir "/path/to/vivid-data"
```

如果用户已经确认过云端模式，也可以显式这样执行一次来写入状态文件：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "视频链接" --execution-mode cloud --artifact-target both --cloud-base-url "https://cloud.example"
```

`quickread` 内部会处理：

1. 平台识别
2. 标题获取
3. 字幕 / 媒体获取
4. 转录或 OCR
5. 摘要生成
6. 产物写入

执行 `quickread` 后，skill 应优先检查：

1. `ok`
2. `error_code`
3. `requires_user_input`
4. `error_summary`
5. `failure_chain`

如果成功拿到摘要，向用户返回时必须完整覆盖：

1. 标题
2. 内容概览
3. 核心观点
4. 争议点
5. 行动建议
6. 俏皮点评

## 3. Bilibili `SESSDATA` 规则

如果是 Bilibili：

1. 有 `SESSDATA` 时，先尝试官方字幕
2. 如果返回 `error_code = "bili_sessdata_expired"`：
   - 先问用户是否提供新的 `SESSDATA`
   - 提供了：用 `-Sessdata/--sessdata` 重试
   - 不提供：用 `-NoSessdata/--no-sessdata` 重试

不要再写成“清空环境变量后继续”这种模糊动作。
对 skill 来说，正确动作是显式重试并传参。

## 4. 读取产物

成功后读取：

- `./data/项目名/artifacts/`
- `./data/项目名/vector_source/`

重点文件：

- `quickread.md`
- `transcript.txt`
- `summary.md`
- `metadata.json`
- `vector_source/document.json`
- `vector_source/chunks.jsonl`
- `vector_source/manifest.json`

如果目标是后续向量化 / embedding / RAG / 知识库入库，优先使用 `vector_source/`。
