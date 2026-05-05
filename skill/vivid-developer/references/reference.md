# Vivid Developer Reference

Full API reference for developers working on the Vivid codebase.

---

## Pipeline Orchestrator

### `app/pipeline/orchestrator.py`

**`run_quickread(options: RuntimeOptions, event_callback: QuickreadEventCallback | None = None) -> OrchestratorResult`**

Master pipeline function. Runs 10 stages in sequence, each check-pointed via `run_state.json`.

Stages: `prepare → detect_platform → title_fetch → acquire → title → summarize → calibrate → render → artifacts → cleanup`

**`OrchestratorResult`** (dataclass):
| Field | Type | Notes |
|-------|------|-------|
| `source` | `SourceInfo` | Resolved source metadata |
| `transcript` | `TranscriptResult` | Raw transcript |
| `summary` | `SummaryResult` | AI summary |
| `artifacts` | `ArtifactBundle` | Output file paths |
| `rendered` | `str` | Formatted quickread text |
| `diagnostics` | `list[dict[str, Any]]` | Diagnostic events |
| `calibration` | `CalibrationResult \| None` | AI calibration (optional) |

Methods: `to_dict() -> dict`, `to_json() -> str`.

---

## Pipeline Steps

### `app/pipeline/detector.py`

**`detect_platform(source: str, forced_platform: str | None = None) -> str`**

Returns one of: `"local"`, `"bilibili"`, `"douyin"`, `"youtube"`, `"generic"`.

### `app/pipeline/acquisition.py`

**`acquire_transcript(options, platform, workdir, event_callback=None, checkpoint_callback=None, resume_media_path=None) -> TranscriptResult`**

Full transcript acquisition with multi-level fallback:
- Internal Whisper → Ears4 API → OCR extraction
- OCR path: Internal Vision Engine → Eyes API

**`create_media_path(source, platform, workdir, options, event_callback) -> Path`**

Downloads or resolves media file path.

### `app/pipeline/transcription.py`

**`normalize_transcript(result: TranscriptResult) -> TranscriptResult`**

Strips whitespace from transcript text.

### `app/pipeline/summarization.py`

**`summarize_transcript(options: RuntimeOptions, transcript: str, event_callback=None) -> SummaryResult`**

Calls LLM to produce structured summary.

### `app/pipeline/calibration.py`

**`calibrate_transcript(options, transcript, event_callback=None, resume_cn_text=None, checkpoint_callback=None) -> CalibrationResult`**

Two-phase LLM calibration (CN then EN). Calls `LlmAdapter.request_text()` twice.

### `app/pipeline/formatter.py`

**`render_quickread(source, transcript, summary, output_format, calibration=None) -> str`**

Assembles all data into a human-readable text block.

---

## Data Models

All in `app/models/`. All use `@dataclass(slots=True)`.

### `SourceInfo`
```python
raw_source: str      # original URL or file path
platform: str        # "bilibili", "douyin", "youtube", "local", "generic"
title: str           # resolved project title
```

### `TranscriptResult`
```python
text: str                         # transcript body
acquisition_method: str           # e.g. "Internal Whisper large", "Forced OCR"
media_path: Path | None           # downloaded media file
audio_path: Path | None           # extracted audio
```

### `SummaryResult`
```python
title: str                        # one-line summary title
overview: str                     # detailed overview
core_points: list[str]            # 3-5 bullet points
controversies: list[str]          # 1-3 dispute/verification angles
action_suggestions: list[str]     # 3-5 reading/learning actions
playful_comment: str              # witty remark
provider: str                     # AI provider label
```
Aliases: `one_line` → `title`, `key_points` → `core_points`, `detailed` → formatted text.
Constructor accepts these aliases as kwargs for backward compatibility.
Method: `to_payload() -> dict[str, object]`.

### `CalibrationResult`
```python
cn_text: str         # polished Chinese article
en_text: str         # polished English article
provider: str        # AI provider label (default "scaffold")
```
Method: `to_payload() -> dict[str, object]`.

### `ArtifactBundle`
```python
workdir: Path
artifacts_dir: Path
quickread_markdown: Path
transcript_text: Path
summary_markdown: Path
summary_json: Path
metadata_json: Path
checkpoint_json: Path | None
vector_source_dir: Path | None
vector_document_json: Path | None
vector_chunks_jsonl: Path | None
vector_manifest_json: Path | None
calibrated_cn_markdown: Path | None
calibrated_en_markdown: Path | None
```

### `RuntimeOptions`
```python
# Required (no defaults)
source: str                                        # URL or file path
data_dir: Path                                     # output root directory
output_format: str                                 # "transcript" | "summary" | "both"
whisper_model: str                                 # "tiny"|"base"|"small"|"medium"|"large"
ffmpeg_bin: str                                    # path to ffmpeg
ears4_api: str                                     # Whisper API URL
eyes_api: str                                      # OCR API URL
language: str                                      # e.g. "zh"
acquisition_mode: str                              # "auto"|"smart"|"prefer_ocr"|"force_ocr"
transcription_backend: str                         # "auto"|"internal"|"ears4_api"
vision_backend: str                                # "auto"|"internal"|"eyes_api"
transcribe_timeout: int
ocr_timeout: int
llm_max_chars: int                                 # default 8000
siliconflow_base_url: str
dashscope_base_url: str
vision_sample_ms: int
vision_min_duration_ms: int
vision_api_configs_path: Path
vision_prompts_path: Path
transcription_presets_path: Path
keep_files: bool

# Optional (default None)
project_name: str | None
forced_platform: str | None
whisper_root: Path | None
transcription_preset_id: str | None
transcription_device: str | None
transcription_task: str | None
transcription_extract_audio: bool | None
transcription_output_dir: Path | None
siliconflow_api_key: str | None
dashscope_api_key: str | None
siliconflow_model: str | None
dashscope_model: str | None
bili_script: Path | None
douyin_script: Path | None
vision_api_config_id: str | None
vision_api_base: str | None
vision_api_path: str | None
vision_api_key: str | None
vision_model: str | None
vision_timeout: int | None
vision_prompt_id: str | None
vision_prompt: str | None
vision_system_prompt: str | None
bili_cookie: str | None          # default None
sessdata: str | None              # default None
resume_workdir: Path | None       # default None
resume_stage: str | None          # default None
summary_prompt_id: str | None
summary_system_prompt: str | None
summary_user_prompt: str | None
summary_prompts_path: Path | None
summary_providers_path: Path | None
calibration_prompt_id: str | None
calibration_system_prompt: str | None
calibration_user_prompt: str | None
calibration_prompts_path: Path | None
```

---

## Adapters

### `BilibiliAdapter` (`app/adapters/bilibili.py`)
```python
class BilibiliAdapter:
    def __init__(self, script_path: Path | None = None) -> None
    def get_video_title(self, source: str, bili_cookie: str | None = None, sessdata: str | None = None) -> str | None
    def download_media(self, source: str, workdir: Path, ffmpeg_bin: str, *, bili_cookie: str | None = None, sessdata: str | None = None) -> Path
```
Delegates to `tools/bilibili/bili23_agent_cli.py`. Requires ffmpeg.

Bilibili rule updates generally belong in the helper, not the adapter. Compare behavior against `bili23/Bili23-Downloader`, keep the adapter subprocess contract stable unless wrapper arguments or error classification need to change, and cover helper behavior in `tests/test_download_adapters.py`.

### `DouyinAdapter` (`app/adapters/douyin.py`)
```python
class DouyinAdapter:
    def __init__(self, script_path: Path | None = None) -> None
    def get_video_title(self, source: str) -> str | None   # 8s timeout
    def download_media(self, source: str, workdir: Path) -> Path
```
Delegates to `tools/douyin/douyin.js` via Node.js. Requires `node` on PATH.

### `LlmAdapter` (`app/adapters/llm.py`)
```python
class LlmAdapter:
    def __init__(self, *, providers: list[SummaryProviderConfig], llm_max_chars: int, summary_system_prompt: str, summary_user_prompt: str) -> None
    def summarize(self, transcript: str) -> SummaryResult
    def request_text(self, *, system_prompt: str, user_prompt_template: str, transcript: str) -> str
```

**`summarize()`** — provider-fallback loop; returns rule-based fallback on total failure.
**`request_text()`** — general-purpose LLM call returning raw text; raises `VividError` on total failure. Used by calibration.

Temperature/timeout: summarize uses 0.2/60s; request_text uses 0.4/360s.

Module-level functions:
```python
def fallback_summary(transcript: str) -> SummaryResult     # heuristic summary
def fallback_calibration(transcript: str) -> CalibrationResult  # wraps raw transcript
```

---

## Services

### `app/services/run_state.py`

```python
def checkpoint_path(workdir: Path) -> Path                  # workdir/artifacts/run_state.json
def load_run_state(workdir: Path) -> dict[str, Any]         # returns {} on missing/corrupt
def save_run_state(workdir: Path, payload: dict[str, Any]) -> Path
def update_run_state(workdir: Path, **changes: Any) -> dict  # merges non-None changes

def transcript_to_payload(transcript: TranscriptResult) -> dict[str, Any]
def transcript_from_payload(payload: dict[str, Any]) -> TranscriptResult
def summary_to_payload(summary: SummaryResult) -> dict[str, Any]
def summary_from_payload(payload: dict[str, Any]) -> SummaryResult
def calibration_to_payload(calibration: CalibrationResult) -> dict[str, Any]
def calibration_from_payload(payload: dict[str, Any]) -> CalibrationResult

def available_resume_stages(payload: dict[str, Any]) -> list[str]
def suggested_resume_stage(payload: dict[str, Any], failed_stage: str | None = None) -> str | None
```

### `app/services/pathing.py`

```python
def make_staging_workdir(data_root: Path, source: str) -> Path    # _staging/<ts>-<slug>-<uuid>
def move_to_final_workdir(staging_dir: Path, data_root: Path, title: str) -> Path  # data_dir/<title>
def relocate_path(path: Path | None, old_root: Path, new_root: Path) -> Path | None
```

### `app/services/project_naming.py`

```python
def sanitize_name(value: str, fallback: str = "video") -> str    # safe dir name, max 120 chars
def derive_title(source: str, project_name: str | None = None) -> str
def source_stem(source: str) -> str                              # extract filename stem
def infer_video_title(source: str, media_path: Path | None, workdir: Path) -> str
```

### `app/services/artifact_writer.py`

```python
def save_artifacts(workdir, source, transcript, summary, rendered, output_format="both", diagnostics=None, calibration=None) -> ArtifactBundle
```

Writes: quickread.md, transcript.txt, summary.md, summary.json, metadata.json, calibrated_cn.md, calibrated_en.md, vector source bundle.

### `app/services/vector_source_writer.py`

```python
def write_vector_source_bundle(workdir, source, transcript, summary, artifacts_dir, calibration=None) -> dict[str, Path]
```

Returns `{vector_source_dir, vector_document_json, vector_chunks_jsonl, vector_manifest_json}`.

### `app/services/cleanup.py`

```python
def cleanup_media(workdir: Path) -> None    # rmtree workdir/media/
```

### `app/services/cloud_bridge.py`

```python
def run_cloud_quickread(args, settings) -> dict[str, Any]           # POST to remote /api/quickread
def sync_cloud_result_files(base_url, payload, local_data_dir, *, artifact_target) -> dict[str, Any]
def download_cloud_file(base_url: str, remote_path: str, destination: Path, timeout: int = 60) -> Path
```

### `app/services/diagnostics.py`

```python
FAILURE_LIKE_STAGES: set[str]    # {"subtitle_failed", "ocr_failed", "ocr_fallback", "transcription_failed", "transcription_fallback", "summary_provider_failed", "failed"}

def build_diagnostic_event(stage: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]
def extract_failure_chain(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]
def build_error_summary(events: list[dict[str, Any]] | None) -> dict[str, Any]  # {has_issues, headline, items}
```

---

## Configuration

### `app/config.py` — `Settings` dataclass

All Settings fields mirror `RuntimeOptions` fields (Settings is the env-var-loaded base; RuntimeOptions is the per-run resolved config).

Key env var loading in `load_settings()`:
```python
data_dir = Path(os.environ.get("VIVID_DATA_DIR", "data"))
llm_max_chars = int(os.environ.get("VIVID_LLM_MAX_CHARS", "8000"))
siliconflow_model = os.environ.get("VIVID_SILICONFLOW_MODEL") or None
calibration_prompts_path = Path(os.environ.get("VIVID_CALIBRATION_PROMPTS_FILE", repo_root / "configs" / "calibration" / "prompts.json"))
# ... etc
```

### `app/runtime_factory.py`

```python
def build_runtime_options(settings: Settings, values: Mapping[str, Any]) -> RuntimeOptions
```

Merges Settings defaults with user-provided values (from CLI args or web form). Uses helpers `_text_or_none()`, `_coerce_path()`, `_bool_value()`.

### `app/constants.py`

```python
DEFAULT_FORMAT = "both"
DEFAULT_MODEL = "large"
SUPPORTED_PLATFORMS = ("bilibili", "douyin", "youtube", "generic", "local")
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".flv", ".m4v"}
MEDIA_EXTS = VIDEO_EXTS | {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}
```

---

## Subsystems

### Summary Subsystem (`app/subsystems/summary/`)

**`models.py`:**
```python
SummaryPromptConfig(prompt_id, system_prompt, user_prompt_template)    # prompt config
SummaryProviderConfig(provider_id, provider_name, base_url, model, api_key)  # resolved provider
SummaryPromptItem(id, name, system_prompt, user_prompt_template)      # store item
SummaryProviderItem(id, name, base_url, model, api_key_env, enabled=True)  # store item
```

**`store.py`:**
```python
SummaryPromptStore(prompts: list[SummaryPromptItem], selected_prompt_id: str | None = None)
    .get_prompt(prompt_id: str | None) -> SummaryPromptItem | None
    .to_payload() -> dict

SummaryProviderStore(providers: list[SummaryProviderItem], selected_provider_id: str | None = None)
    .get_providers() -> list[SummaryProviderItem]   # reordered (selected first), enabled-only
    .to_payload() -> dict

load_summary_store(path: Path | None) -> SummaryPromptStore
load_summary_provider_store(path: Path | None) -> SummaryProviderStore
```

**`resolver.py`:**
```python
build_summary_prompt_config(options: RuntimeOptions) -> SummaryPromptConfig
build_summary_provider_configs(options: RuntimeOptions) -> list[SummaryProviderConfig]
build_calibration_prompt_configs(options: RuntimeOptions) -> tuple[SummaryPromptConfig, SummaryPromptConfig]  # (cn, en)
```

---

## Utilities

### `app/utils/logging_utils.py`

```python
def log(message: str) -> None                                    # print to stderr
def log_event(event: str, **fields: Any) -> None                 # JSON event to stderr
def log_exception(event: str, exc: BaseException, **fields: Any) -> None  # + error_type, error fields
```

### `app/utils/text.py`

```python
def trim_text(value: str, max_chars: int) -> str                 # truncate, no marker
def trim_for_llm(text: str, max_chars: int) -> str               # truncate + "[TRUNCATED]"
def clean_transcript(text: str) -> str                           # normalize newlines
def sentence_split(text: str) -> list[str]                       # split on punctuation
def is_video_file(path: Path) -> bool                            # check suffix ∈ VIDEO_EXTS
```

### `app/utils/json_utils.py`

```python
def extract_json_block(text: str) -> dict                        # parse LLM JSON response, handles ``` fences
def to_pretty_json(payload: dict) -> str                         # indent=2 dump
```

---

## Exception Hierarchy

### `app/exceptions.py`

```python
class VividError(RuntimeError): pass                             # Base for all domain errors
class BilibiliSessdataExpiredError(VividError):                  # + self.detail field
```

---

## Config Files

### `configs/summary/providers.json`
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

### `configs/summary/prompts.json`
```json
{
  "selected_id": "default",
  "items": [
    {"id": "default", "name": "...", "system_prompt": "...", "user_prompt_template": "..."}
  ]
}
```

### `configs/calibration/prompts.json`
```json
{
  "items": [
    {"id": "cn", "name": "中文校准", "system_prompt": "...", "user_prompt_template": "..."},
    {"id": "en", "name": "英文校准", "system_prompt": "...", "user_prompt_template": "..."}
  ]
}
```

### `configs/vision/api_configs.json`, `configs/vision/prompts.json`, `configs/transcription/presets.json`

Follow the same store pattern with `{selected_id, items}`. Items have `id, name` plus domain-specific fields.

---

## CLI

### `app/cli.py`

```bash
python -m app.cli "<source>" [options]

Key flags:
  --project-name TEXT          Override project folder name
  --data-dir PATH              Override data directory
  -f, --format {transcript|summary|both}
  -m, --model {tiny|base|small|medium|large}
  --platform {bilibili|douyin|youtube|generic|local}
  --bili-cookie TEXT           Bilibili cookie for helper auth
  --sessdata TEXT               (hidden, legacy)
  --acquisition-mode {auto|smart|prefer_ocr|force_ocr}
  --transcription-backend {auto|internal|ears4_api}
  --vision-backend {auto|internal|eyes_api}
  --llm-max-chars N
  --siliconflow-model TEXT
  --dashscope-model TEXT
  --summary-prompt-id TEXT
  --summary-system-prompt TEXT
  --summary-user-prompt TEXT
  --calibration-prompt-id TEXT
  --calibration-system-prompt TEXT
  --calibration-user-prompt TEXT
  --calibration-prompts-file PATH
  --no-keep-files              Delete media after run
  --json                       Print JSON output
  # + flags for all vision, transcription, summary, and calibration overrides
```

---

## Web API

### `app/web.py`

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | SPA HTML |
| `/api/health` | GET | `{ok, data_dir, web_history}` |
| `/api/bootstrap` | GET | Defaults, options, stats, jobs |
| `/api/jobs` | GET | Job list (query: `limit`) |
| `/api/jobs` | POST | Create job(s) (source_urls, file upload) |
| `/api/jobs/{id}` | GET | Job detail |
| `/api/jobs/{id}/events` | GET | SSE progress stream |
| `/api/jobs/{id}/retry` | POST | Retry terminal job |
| `/api/jobs/{id}/continue` | POST | Resume from checkpoint |
| `/api/jobs/{id}/cancel` | POST | Cancel queued job |
| `/api/jobs/{id}` | DELETE | Delete job (query: `delete_files`) |
| `/api/jobs/export` | POST | Batch export ZIP |
| `/api/quickread` | POST | Synchronous quickread |
| `/files` | GET | Serve artifact file (query: `path`) |
| `/api/open-folder` | POST | Open folder in OS |
| `/api/preferences/output-dir` | POST | Save default output dir |
| `/api/preferences/vision-openai` | POST | Save default OCR API config |

Job states: `queued → running → completed | failed | cancelled`. Max 2 parallel workers.

---

## Testing

### Setup
```bash
pip install -e ".[dev]"   # pytest>=8, httpx>=0.27
# Config in pyproject.toml: testpaths=["tests"], pythonpath=["."]
```

### Key Fixtures
- `tmp_path` — `pathlib.Path` to a temp directory. Use for writing temp config files, checking output files.
- `monkeypatch` — `monkeypatch.setattr("module.path.function", replacement)` to mock external calls.

### Mock Patterns

**Mock requests.post:**
```python
class FakeResponse:
    def raise_for_status(self): pass
    def json(self):
        return {"choices": [{"message": {"content": "fake output"}}]}

monkeypatch.setattr("requests.post", lambda *a, **kw: FakeResponse())
```

**Mock subprocess:**
```python
def fake_run(cmd, **kwargs):
    return subprocess.CompletedProcess(cmd, 0, stdout="output", stderr="")

monkeypatch.setattr("app.adapters.bilibili.subprocess.run", fake_run)
```

**Mock run_quickread for web tests:**
```python
monkeypatch.setattr(
    "app.web.run_quickread",
    lambda _options: OrchestratorResult(source=..., transcript=..., summary=..., artifacts=..., rendered=...),
)
```

**Build settings for tests:**
```python
def _build_settings(tmp_path):
    return type("Settings", (), {"data_dir": tmp_path / "data", ...})()
```

**Build RuntimeOptions for tests:**
```python
def _make_options(tmp_path, **overrides):
    return RuntimeOptions(source="test", data_dir=tmp_path, ...)  # all required fields + overrides
```

### Assertion Patterns
```python
# Direct assertion
assert result.field == "expected"

# Exception assertion
try:
    func(bad_input)
except VividError as exc:
    assert "expected message" in str(exc)
else:
    raise AssertionError("VividError not raised")

# Check file was written
assert (tmp_path / "output.md").read_text(encoding="utf-8") == expected_content
```
