# Workflow（瞬知 / Vivid）

这是 `vivid-operator` 的推荐执行顺序。

## 0. 定位仓库

优先执行：

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action paths
```

如果自动检测失败：

1. 先看 `skill/vivid-operator/state/repo_root.json`
2. 再看 `VIVID_REPO_ROOT`
3. 还不行再让用户提供 Vivid 仓库路径

一旦用户给出了有效路径并成功执行 wrapper，后续应优先复用状态文件，不要重复询问。

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
