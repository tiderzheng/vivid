# Vivid Operator Reference

## Wrapper Parameters

### 通用参数

| 参数 | Windows | Linux/macOS | 说明 |
|---|---|---|---|
| Action | `-Action` | `-Action` | `doctor / quickread / paths / web-ui / bili-auth-qrcode / bili-auth-poll / bili-auth-status / bili-auth-logout` |
| Source | `-Source` | `-Source` | 视频链接或本地媒体路径 |
| VividRoot | `-VividRoot` | `--vivid-root` | Vivid 仓库路径 |
| Model | `-Model` | `-Model` | Whisper 模型：`tiny/base/small/medium/large` |
| DataDir | `-DataDir` | `-DataDir` | 输出根目录 |
| ProjectName | `-ProjectName` | `-ProjectName` | 项目名 |
| Format | `-Format` | `-Format` | `transcript / summary / both` |
| Platform | `-Platform` | `-Platform` | `bilibili / douyin / youtube / generic / local` |
| AcquisitionMode | `-AcquisitionMode` | `-AcquisitionMode` | `auto / smart / prefer_ocr / force_ocr` |
| PreferOcr | `-PreferOcr` | `--prefer-ocr` | 标志参数 |
| ForceOcr | `-ForceOcr` | `--force-ocr` | 标志参数 |
| TranscriptionBackend | `-TranscriptionBackend` | `--transcription-backend` | `auto / internal / ears4_api` |
| VisionBackend | `-VisionBackend` | `--vision-backend` | `auto / internal / eyes_api` |
| FfmpegBin | `-FfmpegBin` | `--ffmpeg-bin` | 覆盖 ffmpeg 路径 |
| WhisperRoot | `-WhisperRoot` | `--whisper-root` | 覆盖 whisper 根路径 |
| TranscribeTimeout | `-TranscribeTimeout` | `--transcribe-timeout` | 转录超时（秒） |
| OcrTimeout | `-OcrTimeout` | `--ocr-timeout` | OCR 超时（秒） |
| NoKeepFiles | `-NoKeepFiles` | `--no-keep-files` | 执行后清理中间文件 |
| ExecutionMode | `-ExecutionMode` | `--execution-mode` | `local / cloud` |
| ArtifactTarget | `-ArtifactTarget` | `--artifact-target` | `local_only / cloud_only / both` |
| CloudProfile | `-CloudProfile` | `--cloud-profile` | 云端配置名 |
| CloudBaseUrl | `-CloudBaseUrl` | `--cloud-base-url` | 远端 Vivid Web API 地址 |
| BiliCookie | `-BiliCookie` | `--bili-cookie` | `Bilibili` 完整 `Cookie`，登录失败时优先传入；应用层会保存到项目 secret 文件 |
| Sessdata | `-Sessdata` | `--sessdata` | 兼容旧链路，仅在拿不到完整 `Cookie` 时使用 |
| NoSessdata | `-NoSessdata` | `--no-sessdata` | 禁用 `SESSDATA` 回退 |
| QrcodeKey | `-QrcodeKey` | `--qrcode-key` | `bili-auth-poll` 的二维码轮询 key |

### OCR / Vision 参数

| 参数 | Windows | Linux/macOS | 说明 |
|---|---|---|---|
| VisionApiConfigId | `-VisionApiConfigId` | `--vision-api-config-id` | OCR 配置 ID |
| VisionTimeout | `-VisionTimeout` | `--vision-timeout` | OCR 超时（秒） |
| VisionSampleMs | `-VisionSampleMs` | `--vision-sample-ms` | 采样间隔（毫秒） |
| VisionMinDurationMs | `-VisionMinDurationMs` | `--vision-min-duration-ms` | 最小时长（毫秒） |

### 摘要参数

| 参数 | Windows | Linux/macOS | 说明 |
|---|---|---|---|
| SummaryPromptId | `-SummaryPromptId` | `--summary-prompt-id` | 摘要 prompt 预设 ID |
| SummarySystemPrompt | `-SummarySystemPrompt` | `--summary-system-prompt` | 覆盖系统 prompt |
| SummaryUserPrompt | `-SummaryUserPrompt` | `--summary-user-prompt` | 覆盖用户 prompt |
| SummaryPromptsFile | `-SummaryPromptsFile` | `--summary-prompts-file` | 覆盖 prompts 文件路径 |
| SummaryProvidersFile | `-SummaryProvidersFile` | `--summary-providers-file` | 覆盖 providers 文件路径 |

## Source Shapes

支持的输入形态：

- 视频 URL
- 音频 URL
- 本地视频路径
- 本地音频路径

`Bilibili` 现在按直接下载媒体处理，不恢复官方字幕优先。helper 会优先使用完整 `Cookie`，其次兼容 `SESSDATA`，没有凭据时自动补匿名指纹 `Cookie`。

支持常见 `Bilibili` 链接形态：`BV`、`av`、`ep`、`ss`、`md`。

匿名请求画像会补 `_uuid`、`b_lsid`、`b_nut`、`buvid3`、`buvid4`、`buvid_fp`，并尽量获取 `bili_ticket` / 调用 `ExClimbWuzhi`。helper 按 `Bili23` 模型维护这些匿名字段；用户传入的完整 `Cookie` 如果带有旧匿名字段，会被 helper 刷新覆盖。这些增强失败不应被直接解释为登录失败。

下载前 helper 会用 `HEAD` 跳过文本响应或过小 CDN 错误页，减少把风控错误页当成视频文件的概率。

## Bilibili Auth Priority

1. `-BiliCookie` / `--bili-cookie`
2. `VIVID_BILI_COOKIE`
3. 二维码登录或手动 Cookie 写入的 `configs/secrets/bilibili_cookie.json`
4. `-Sessdata` / `--sessdata`
5. `BILI_SESSDATA`
6. 匿名指纹模式

用户通过 `-BiliCookie` / `--bili-cookie` 或 Web 表单显式提供完整 `Cookie` 时，Vivid 会保存到项目目录 `configs/secrets/bilibili_cookie.json`。`VIVID_BILI_COOKIE` 环境变量优先于该文件；不要把该文件内容复制到回答、日志、prompt 或 `skill_state.json`。

二维码登录命令：

```powershell
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action bili-auth-qrcode
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action bili-auth-poll -QrcodeKey "<qrcode_key>"
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action bili-auth-status
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action bili-auth-logout
```

轮询成功后只报告 `saved = true`，不回显 Cookie 明文。

`-NoSessdata` / `--no-sessdata` 会禁用第 4、5 步的回退。

匿名指纹模式不是“无需任何请求状态”。它仍会生成本次请求画像，并尽力补充 `bili_ticket` 等短期票据；只有明确返回登录错误时才需要转向用户提供完整 `Cookie`。

## Success Payload

常用字段：

```json
{
  "ok": true,
  "result": {
    "source": { "raw_source": "...", "platform": "bilibili", "title": "..." },
    "transcript": { "acquisition_method": "...", "text": "..." },
    "summary": {
      "title": "...",
      "overview": "...",
      "core_points": ["..."],
      "controversies": ["..."],
      "action_suggestions": ["..."],
      "playful_comment": "...",
      "provider": "..."
    },
    "artifacts": {
      "workdir": "...",
      "artifacts_dir": "...",
      "vector_source_dir": "..."
    },
    "failure_chain": [],
    "error_summary": { "has_issues": false }
  }
}
```

## Failure Payload

常用字段：

```json
{
  "ok": false,
  "error": "...",
  "error_code": "...",
  "error_summary": { "has_issues": true, "headline": "...", "items": ["..."] },
  "failure_chain": [{ "stage": "...", "error": "..." }]
}
```

## State File

`skill/vivid-operator/state/skill_state.json` 允许保存：

- `repo_root`
- `source`（repo_root 的来源，例如 `argument / environment / auto_detect / legacy_repo_state`）
- `default_whisper_model`
- `default_data_dir`
- `execution_mode`
- `artifact_target`
- `cloud_profile`
- `cloud_base_url`

禁止保存：

- Cookie
- `SESSDATA`
- API Key
- Token

例外：Bilibili 完整 `Cookie` 的持久化由 Vivid 应用层写入项目目录 `configs/secrets/bilibili_cookie.json`，不属于 skill 状态文件，agent 不应直接读取、展示或改写其中内容。

## Repo Resolution Priority

1. `-VividRoot` / `--vivid-root`
2. `VIVID_REPO_ROOT`
3. `skill_state.json` 的 `repo_root`
4. skill 目录自动检测

## Default Priority

### Whisper 模型

1. `-Model`
2. `VIVID_DEFAULT_MODEL`
3. `skill_state.json.default_whisper_model`
4. 主程序默认值

### 输出目录

1. `-DataDir`
2. `VIVID_DATA_DIR`
3. `skill_state.json.default_data_dir`
4. 主程序默认值

### 执行模式

1. `-ExecutionMode`
2. `VIVID_EXECUTION_MODE`
3. `skill_state.json.execution_mode`
4. 默认 `local`
