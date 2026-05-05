# Vivid（瞬知）功能流程文档

## 项目概述

Vivid 是一个将视频内容转化为可读文本产物的全自动管道系统。输入视频链接或本地文件，经过下载、语音识别/OCR 字幕提取、AI 摘要、AI 文本校准等一系列步骤，最终生成结构化的速读文档。

支持平台：Bilibili、抖音、YouTube、本地视频/音频文件。

---

## 整体架构

```
用户输入 → RuntimeOptions 构建 → run_quickread() 主管道 → 产物写入磁盘
```

### 入口方式

| 入口 | 入口点 | 说明 |
|------|--------|------|
| CLI | `python -m app.cli "<url或文件路径>"` | 命令行单次执行 |
| Web UI | `uvicorn app.web:app --host 127.0.0.1 --port 8765` | 网页交互 + 后台任务队列 |
| Skill Wrapper | `scripts/vivid_tool.ps1 -Action quickread -Source "..."` | 供外部 Agent 调用 |

---

## 主管道流程图

```
                   ┌──────────────────────────────────────────────────────────────────┐
                   │                         run_quickread()                            │
                   └──────────────────────────────────────────────────────────────────┘
                                              │
         ┌────────────────────────────────────┼────────────────────────────────────┐
         │                                    │                                    │
    [CLI 调用]                          [Web 调用]                          [Skill 调用]
    argparse 解析                        WebJobManager                       PowerShell/Bash
    build_runtime_options()              submit/jobs API                     封装 CLI
         │                                    │                                    │
         └────────────────────────────────────┼────────────────────────────────────┘
                                              │
                                    ┌─────────▼─────────┐
                                    │  RuntimeOptions    │
                                    │  (统一配置模型)     │
                                    └─────────┬─────────┘
                                              │
                        ┌─────────────────────▼─────────────────────┐
                        │              主管道 10 阶段                │
                        └─────────────────────┬─────────────────────┘
                                              │
         ┌──────────┐  ┌──────────┐  ┌───────▼──────┐  ┌──────────┐  ┌──────────┐
         │ 1.PREPARE│─▶│ 2.DETECT │─▶│ 3.TITLE_FETCH│─▶│4.ACQUIRE │─▶│ 5.TITLE  │
         └──────────┘  └──────────┘  └──────────────┘  └──────────┘  └──────────┘
                                                                           │
         ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────▼──────┐
         │10.CLEANUP│◀─│9.ARTIFACTS│◀─│ 8.RENDER │◀─│7.CALIBRATE│◀─│ 6.SUMMARIZE │
         └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────────┘
              │
              ▼
      OrchestratorResult
```

---

## 各阶段详细说明

### 阶段 1：PREPARE（准备工作目录）

```
make_staging_workdir(data_dir, source)
  → data_dir/_staging/<timestamp>-<source_slug>-<uuid8>/
  → 创建 artifacts/ 和 media/ 子目录
```

- 如果是从断点恢复（resume），则加载已有工作目录
- 读取 `workdir/artifacts/run_state.json` 获取已保存的中间状态
- 初始化 diagnostics 事件收集器

### 阶段 2：DETECT（平台识别）

```
detect_platform(source, forced_platform) → 平台标识字符串
```

| 检测依据 | 判定结果 |
|----------|----------|
| `--platform` 手动指定 | 直接使用 |
| 本地文件路径存在 | `local` |
| 域名含 `bilibili.com` / `b23.tv` / `bili2233.cn` | `bilibili` |
| 域名含 `douyin.com` / `iesdouyin.com` / `v.douyin.com` | `douyin` |
| 域名含 `youtube.com` / `youtu.be` | `youtube` |
| 默认 | `generic` |

### 阶段 3：TITLE FETCH（获取视频标题）

仅在未手动指定项目名称时执行：

| 平台 | 方法 |
|------|------|
| Bilibili | `BilibiliAdapter(options.bili_script).get_video_title(source, bili_cookie, sessdata)` |
| 抖音 | `DouyinAdapter(options.douyin_script).get_video_title(source)` |
| 其他 | 不执行此阶段 |

获取失败不阻塞管道，仅记录事件并继续。

### 阶段 4：ACQUIRE（文本获取）

这是最复杂的阶段，负责从视频/音频中提取逐字稿文本。

```
acquire_transcript(options, platform, workdir)
  │
  ├── create_media_path() → 下载或解析本地文件位置
  │   ├── local: 直接验证文件存在
  │   ├── bilibili: BilibiliAdapter.download_media()
  │   ├── douyin: DouyinAdapter.download_media()
  │   └── 其他: YtDlpAdapter.download_media()
  │
  ├── _resolve_effective_acquisition_mode() → 决定提取策略
  │   ├── force_ocr      → 强制只用 OCR 提取
  │   ├── prefer_ocr     → 视频文件优先 OCR
  │   ├── auto           → 优先内部 Whisper
  │   └── smart          → 自动检测硬字幕，有则 prefer_ocr
  │
  └── 文本提取（含多重降级链）
      ├── 首选: InternalTranscriptionEngine (本地 Whisper)
      ├── 降级1: Ears4 API (远程 Whisper 服务)
      └── 降级2: OCR 提取 (InternalVisionEngine → EyesAdapter)
```

返回 `TranscriptResult`:
- `text`: 逐字稿文本
- `acquisition_method`: 获取方式标识
- `media_path`: 媒体文件路径
- `audio_path`: 提取的音频路径（如有）

然后经过 `normalize_transcript()` 做简单的首尾空白裁剪。

### 阶段 5：TITLE（确定项目名称）

```
标题优先级：
1. 断点恢复时保存的标题
2. 用户指定的 --project-name
3. 阶段 3 获取的 fetched_title
4. infer_video_title(source, media_path, workdir)
   → 优先 media_path.stem，否则从产物目录扫描字幕文件
```

确定标题后将临时目录移动到最终工作目录：
```
move_to_final_workdir(staging_dir, data_dir, title)
  → data_dir/<标题>/
  → 名称冲突时自动追加 -2, -3...
```

### 阶段 6：SUMMARIZE（AI 摘要生成）

```
summarize_transcript(options, transcript_text)
  │
  ├── build_summary_prompt_config(options)
  │   → 从 configs/summary/prompts.json 加载提示词预设
  │   → 支持环境变量 / CLI 参数覆盖
  │
  ├── build_summary_provider_configs(options)
  │   → 从 configs/summary/providers.json 加载 AI 服务商
  │   → 读取对应的 API Key 环境变量
  │
  └── LlmAdapter.summarize(transcript)
      → 逐字稿裁剪至 llm_max_chars (默认 8000)
      → POST 到 OpenAI 兼容 API (temperature=0.2, timeout=60s)
      → 解析 JSON 结构化输出
      → 服务商故障时自动切换下一个
      → 全部故障则使用 rule-based 降级摘要
```

返回 `SummaryResult`:
| 字段 | 说明 |
|------|------|
| `title` / `one_line` | 一句话标题 |
| `overview` / `detailed` | 内容概览 |
| `core_points` / `key_points` | 3-5 条核心观点 |
| `controversies` | 1-3 条争议点或核查角度 |
| `action_suggestions` | 3-5 条行动建议 |
| `playful_comment` | 俏皮点评 |
| `provider` | 使用的 AI 服务商标识 |

### 阶段 7：CALIBRATE（AI 文本校准）[新增]

将原始逐字稿转化为排版精美、适合阅读的文章，输出中英双语版本。

```
calibrate_transcript(options, transcript_text)
  │
  ├── build_calibration_prompt_configs(options)
  │   → 从 configs/calibration/prompts.json 加载中英文两套提示词
  │   → 支持环境变量 / CLI 参数覆盖
  │
  └── LlmAdapter.request_text() × 2
      ├── [第 1 次调用] 中文校准
      │   → 清理口语化表达、补全标点、组织段落
      │   → temperature=0.4, timeout=360s
      │   → 成功后立即保存 checkpoint（断点续跑用）
      │   → 失败 → 回退到 rule-based fallback
      │
      └── [第 2 次调用] 英文校准
          → 翻译 + 校准为自然流畅的英文文章
          → temperature=0.4, timeout=360s
          → 失败 → 英文留空，不影响整体流程
```

返回 `CalibrationResult`:
| 字段 | 说明 |
|------|------|
| `cn_text` | 校准后的中文文章 |
| `en_text` | 校准后的英文文章 |
| `provider` | 使用的 AI 服务商标识 |

**容错设计**：校准失败不会中断整个管道，降级方案会将原始逐字稿作为中文版输出。

### 阶段 8：RENDER（渲染输出）

```
render_quickread(source, transcript, summary, output_format, calibration) → 文本
```

组合所有数据生成统一的纯文本输出块，按 `output_format` 控制内容范围：

| output_format | 包含内容 |
|---------------|----------|
| `transcript` | 仅有原文逐字稿 |
| `summary` | 仅有 AI 摘要 |
| `both` | 逐字稿 + 摘要 + 校准文本（如有） |

### 阶段 9：ARTIFACTS（写入产物）

```
save_artifacts(workdir, source, transcript, summary, rendered, output_format, diagnostics, calibration)
```

在 `workdir/artifacts/` 下生成以下文件：

| 文件名 | 内容 |
|--------|------|
| `quickread.md` | 包含所有内容的速读文档 |
| `transcript.txt` | 原始逐字稿 |
| `summary.md` | 结构化摘要 (Markdown) |
| `summary.json` | 摘要数据 (JSON) |
| `metadata.json` | 完整元数据 |
| `calibrated_cn.md` | AI 校准中文文章 |
| `calibrated_en.md` | AI 校准英文文章 |
| `run_state.json` | 运行时状态（断点续跑用） |
| `vector_source/document.json` | 向量化源文档 |
| `vector_source/chunks.jsonl` | 向量化文本块 |
| `vector_source/manifest.json` | 向量化清单 |

### 阶段 10：CLEANUP（清理）

- 如果 `keep_files=True`（默认），保留媒体文件
- 如果 `--no-keep-files`（CLI）或 `keep_files=false`（Web），删除媒体文件释放空间
- 产物文件（artifacts/）始终保留

---

## 断点续跑机制

管道的每个关键阶段完成后都会保存状态到 `run_state.json`。

### Resume 阶段列表

| Resume 阶段 | 前提条件 | 从何处开始执行 |
|-------------|----------|----------------|
| `transcription` | media_path 存在 | 重新转录 |
| `summarize` | transcript 文本存在 | 重新摘要 |
| `calibrate` | transcript + summary 存在 | 重新校准 |
| `render` | transcript + summary + calibration 存在 | 重新渲染 |
| `artifacts` | transcript + summary + rendered 存在 | 重新写入文件 |

### 智能续跑建议

```
suggested_resume_stage(payload, failed_stage) → 推荐的 resume 阶段
```

根据失败发生在哪个阶段自动推荐最佳恢复点。例如：
- 在 `summarize` 阶段失败 → 建议 resume = `"summarize"`
- 在 `calibrate` 阶段失败 → 建议 resume = `"calibrate"`（已有中文则跳过 CN 直接续跑英文）

### 用法

```bash
# CLI 方式
python -m app.cli "<url>" --resume-workdir "data/项目名" --resume-stage calibrate

# Web 方式
# 在失败任务上点击"继续任务"，选择 resume 阶段
```

---

## 配置体系

### 配置层级

```
环境变量 (.env) → configs/ JSON 预设 → CLI/Web 参数覆盖 → RuntimeOptions
```

### AI 服务商配置

文件：`configs/summary/providers.json`

```json
{
  "items": [
    {
      "id": "siliconflow",
      "name": "SiliconFlow",
      "base_url": "https://api.siliconflow.cn/v1/chat/completions",
      "model": "deepseek-ai/DeepSeek-V4-Flash",
      "api_key_env": "SILICONFLOW_API_KEY",
      "enabled": true
    }
  ]
}
```

- 支持多个服务商，按 `enabled` 筛选后顺序调用
- 首个服务商失败自动切换下一个
- `model` 字段在 JSON 中定义即生效，无需重启；环境变量 `VIVID_SILICONFLOW_MODEL` 可覆盖
- API Key 从 `api_key_env` 指定的环境变量中读取

### 提示词配置

| 用途 | 配置文件 |
|------|----------|
| AI 摘要 | `configs/summary/prompts.json` |
| AI 校准（中文） | `configs/calibration/prompts.json` → `id: "cn"` |
| AI 校准（英文） | `configs/calibration/prompts.json` → `id: "en"` |
| OCR 提取 | `configs/vision/prompts.json` |
| 转录预设 | `configs/transcription/presets.json` |

### 关键环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VIVID_DATA_DIR` | `./data` | 数据输出根目录 |
| `VIVID_DEFAULT_MODEL` | `large` | Whisper 模型大小 |
| `VIVID_LANGUAGE` | `zh` | 默认语言 |
| `VIVID_LLM_MAX_CHARS` | `8000` | 送入 LLM 的最大字符数 |
| `VIVID_ACQUISITION_MODE` | `auto` | 文本获取策略 |
| `VIVID_TRANSCRIPTION_BACKEND` | `auto` | 转录后端 |
| `VIVID_VISION_BACKEND` | `auto` | OCR 后端 |
| `SILICONFLOW_API_KEY` | — | SiliconFlow API 密钥 |
| `DASHSCOPE_API_KEY` | — | DashScope API 密钥 |
| `VIVID_SILICONFLOW_MODEL` | — | 覆盖 providers.json 中的 model |
| `VIVID_BILI_COOKIE` | — | B 站完整 Cookie，优先于项目本地 `configs/secrets/bilibili_cookie.json` |
| `EARS4_API` | `http://127.0.0.1:7860` | Whisper API 地址 |
| `EYES_API` | `http://127.0.0.1:9531` | OCR API 地址 |
| `VIVID_CALIBRATION_PROMPTS_FILE` | `./configs/calibration/prompts.json` | 校准提示词文件 |

---

## Web UI 接口说明

### API 端点

| 路由 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 返回单页 Web 界面 |
| `/api/health` | GET | 健康检查 |
| `/api/bootstrap` | GET | 返回默认配置、选项列表、历史任务 |
| `/api/jobs` | GET | 列出历史任务（支持分页） |
| `/api/jobs` | POST | 创建新任务（支持批量 URL、文件上传） |
| `/api/jobs/{job_id}` | GET | 获取单个任务详情 |
| `/api/jobs/{job_id}/events` | GET | SSE 实时推送任务进度 |
| `/api/jobs/{job_id}/retry` | POST | 重试失败任务 |
| `/api/jobs/{job_id}/continue` | POST | 从断点继续任务 |
| `/api/jobs/{job_id}/cancel` | POST | 取消排队中的任务 |
| `/api/jobs/{job_id}` | DELETE | 删除任务（可选删除文件） |
| `/api/jobs/export` | POST | 批量导出任务为 ZIP |
| `/api/quickread` | POST | 同步快速执行（单源） |
| `/files` | GET | 下载产物文件 |
| `/api/open-folder` | POST | 在文件管理器中打开目录 |
| `/api/preferences/output-dir` | POST | 保存默认输出目录 |
| `/api/preferences/vision-openai` | POST | 保存默认 OCR API 配置 |

### 任务状态机

```
queued → running → completed
                 → failed
                 → cancelled
```

- 最多 2 个并行 Worker
- 任务状态持久化到 `data/web_ui/jobs.json`
- SSE 实时推送进度（含阶段和百分比）

---

## 产物目录结构

```
data/
└── <项目标题>/                         # 由项目命名策略确定
    ├── artifacts/                       # 所有产物
    │   ├── quickread.md                 # 完整速读文档
    │   ├── transcript.txt               # 原始逐字稿
    │   ├── summary.md                   # 结构化摘要
    │   ├── summary.json                 # 摘要 JSON
    │   ├── metadata.json                # 完整元数据
    │   ├── calibrated_cn.md             # AI 校准中文文章 [新增]
    │   ├── calibrated_en.md             # AI 校准英文文章 [新增]
    │   └── run_state.json              # 断点续跑状态
    ├── vector_source/                   # 向量化源数据
    │   ├── document.json
    │   ├── chunks.jsonl
    │   └── manifest.json
    └── media/                           # 下载的媒体文件（keep_files 模式下保留）
```

---

## 错误处理与降级链

系统设计为多重降级：

| 环节 | 首选方案 | 降级 1 | 降级 2 |
|------|----------|--------|--------|
| 文本获取 | 内部 Whisper | Ears4 API | OCR 提取 |
| OCR | 内部 Vision | Eyes API | — |
| 摘要 | SiliconFlow | DashScope | Rule-based |
| 校准 | SiliconFlow | — | Rule-based (原始逐字稿) |

**关键原则**：校准和摘要的失败不应阻塞管道，始终确保有产物输出。
