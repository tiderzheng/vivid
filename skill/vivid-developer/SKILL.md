---
name: vivid-developer
description: Use when working on the Vivid project codebase — understanding architecture, adding features, fixing bugs, refactoring, or extending the pipeline. Covers project structure, coding conventions, extension points, and testing patterns.
---

# Vivid Developer Skill

## When to Use

Invoke this skill whenever you need to modify or understand the Vivid codebase. This includes:

- Adding new pipeline stages
- Extending platform support (new adapters)
- Modifying the summarization or calibration subsystems
- Changing configuration or CLI options
- Writing tests
- Understanding how components connect

## Quick Start

```bash
# Setup
python -m venv .venv
.venv\Scripts\Activate.ps1  # or source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"     # pytest + httpx

# Run tests
python -m pytest -q                          # full suite
python -m pytest tests/test_calibration.py -v  # single file
python -m pytest -k "bilibili"              # keyword filter

# Run app
python -m app.cli "<url>" --json
python -m uvicorn app.web:app --host 127.0.0.1 --port 8765
```

## Architecture Decision Tree

When you need to make a change, use this map to find the right file:

```
What are you changing?
├── Pipeline logic (order of steps, new steps)
│   └── app/pipeline/orchestrator.py
├── Text extraction from video/audio
│   ├── Download media → app/pipeline/acquisition.py (create_media_path)
│   ├── Transcription → app/subsystems/transcription/
│   ├── OCR extraction → app/subsystems/vision/
│   └── Platform-specific downloaders → app/adapters/{bilibili,douyin}.py
├── AI calls (LLM)
│   ├── Summary → app/pipeline/summarization.py + app/adapters/llm.py
│   ├── Calibration → app/pipeline/calibration.py + app/adapters/llm.py
│   ├── Prompts → configs/summary/prompts.json, configs/calibration/prompts.json
│   └── Providers → configs/summary/providers.json
├── Data models
│   ├── Pipeline I/O → app/models/{source,transcript,summary,calibration,artifact}.py
│   └── Runtime config → app/models/runtime.py
├── Configuration
│   ├── Env vars + defaults → app/config.py (Settings dataclass)
│   ├── CLI flags → app/cli.py
│   ├── Web form → app/web.py
│   └── Merging values → app/runtime_factory.py
├── Output files
│   ├── What gets written → app/services/artifact_writer.py
│   └── Vector index data → app/services/vector_source_writer.py
├── Resume / checkpoint
│   └── app/services/run_state.py
├── Error handling / diagnostics
│   ├── Exception types → app/exceptions.py
│   └── Failure chain → app/services/diagnostics.py
└── Web UI
    └── app/web.py (single file: API + inline HTML/JS)
```

## How to Add a New Feature (Step-by-Step)

### Adding a New Pipeline Stage

1. **Model** — Create a result dataclass in `app/models/`
   ```python
   @dataclass(slots=True)
   class MyResult:
       field: str
       provider: str = "default"
       def to_payload(self) -> dict[str, object]: ...
   ```

2. **Pipeline step** — Create `app/pipeline/my_step.py` mirroring `summarization.py`/`calibration.py`
   - Import `LlmAdapter` if it calls LLM, or build custom logic
   - Accept `RuntimeOptions`, `event_callback`, optional resume params
   - Return the result model

3. **Config** — If it has prompts, add a JSON preset in `configs/my_step/`
   - Use `SummaryPromptStore` (reads `{selected_id, items}` JSON) — it's generic despite the name

4. **RuntimeOptions** — Add config fields to `app/models/runtime.py`
5. **Settings** — Add same fields + env var loading in `app/config.py`
6. **RuntimeFactory** — Pass fields through in `app/runtime_factory.py`
7. **Orchestrator** — Insert the new stage in `run_quickread()`:
   - Follow the pattern: load from resume, run if None, save checkpoint, graceful degradation on error
8. **Formatter** — Optionally render in `render_quickread()`
9. **ArtifactWriter** — Write output files in `save_artifacts()`
10. **ArtifactBundle** — Add file path fields if writing new files
11. **RunState** — Add `*_to_payload`/`*_from_payload` helpers if the result needs checkpointing
12. **CLI** — Add `--my-*` flags + pass through `values` dict
13. **Web** — Add file paths to `_serialize_result()`, add progress stages
14. **.env.example** — Document new env vars
15. **Tests** — Create `tests/test_my_step.py`

### Adding Platform Support

1. Create adapter in `app/adapters/my_platform.py`:
   ```python
   class MyPlatformAdapter:
       def __init__(self, script_path: Path | None = None) -> None: ...
       def download_media(self, source: str, workdir: Path) -> Path: ...
       def get_video_title(self, source: str) -> str | None: ...
   ```
2. Register in `app/pipeline/detector.py` — add domain keyword match
3. Add downloader tool in `tools/my_platform/`
4. Handle in `app/pipeline/acquisition.py` `create_media_path()`
5. Add to CLI `--platform` choices
6. Update `SUPPORTED_PLATFORMS` in `app/constants.py`

### Adding a New LLM Provider

1. Add entry to `configs/summary/providers.json`:
   ```json
   {"id": "my_provider", "name": "...", "base_url": "...", "model": "...", "api_key_env": "MY_API_KEY", "enabled": true}
   ```
2. Add model override env var to `app/config.py` (follow `siliconflow_model` pattern)
3. The fallback chain in `LlmAdapter` is automatic — providers are tried in order

## Coding Conventions (Mandatory)

### Every Module Must Start With
```python
from __future__ import annotations
```

### Imports
```python
# Standard library
# Third-party
# Local (relative)
from ..exceptions import VividError
```

### Types
```python
# Use: str | None, list[str], dict[str, Any]
# NOT: Optional[str], List[str], Dict[str, Any]
```

### Dataclasses
```python
@dataclass(slots=True)
class MyType:
    required_field: str
    optional_field: str | None = None
```

### Errors
```python
# Always subclass VividError(RuntimeError) for domain errors
# Always: raise VividError("...") from exc
# Never: raise bare Exception
```

### Logging
```python
from ..utils.logging_utils import log_event, log_exception
# Log to stderr, never print to stdout except final output
log_event("event_name", key=value)
log_exception("event_name", exc, key=value)
```

## Key Extension Points

| What | Where | Pattern |
|------|-------|---------|
| New pipeline stage | `app/pipeline/orchestrator.py` | Insert after summarization, follow calibrate pattern |
| New platform | `app/adapters/` | Implement `download_media()` + `get_video_title()` |
| Bilibili rule change | `tools/bilibili/bili23_agent_cli.py` | Compare against `bili23/Bili23-Downloader`; keep `app/adapters/bilibili.py` CLI contract stable unless wrapper args change |
| New LLM provider | `configs/summary/providers.json` | JSON entry + env var |
| New summary/calibration prompt | `configs/{summary,calibration}/prompts.json` | `{id, name, system_prompt, user_prompt_template}` |
| New output file | `app/services/artifact_writer.py` | `_write_text()` + ArtifactBundle field |
| New CLI flag | `app/cli.py` | `build_parser()` → `values` dict → `build_runtime_options()` |
| New env var | `app/config.py` | Settings field + `os.environ.get()` + `.env.example` doc |

## Testing Patterns

### Basic Unit Test
```python
def test_my_thing(tmp_path, monkeypatch):
    # Build minimal Settings
    settings = _build_settings(tmp_path)

    # Monkeypatch external dependencies at module import path
    monkeypatch.setattr("app.adapters.my_module.requests.post", fake_post)
    monkeypatch.setattr("app.adapters.my_module.shutil.which", lambda _: "/usr/bin/tool")

    # Construct adapter/options directly
    adapter = MyAdapter(tmp_path / "helper.py")
    result = adapter.my_method("https://example.com", tmp_path)

    # Assert
    assert result == expected
```

### Testing Pipeline Steps
```python
def test_pipeline_step_with_mocked_llm(tmp_path, monkeypatch):
    # Mock requests.post to return a FakeResponse
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "expected output"}}]}

    monkeypatch.setattr("requests.post", lambda *a, **kw: FakeResponse())

    # Write temp config
    prompts_path = tmp_path / "prompts.json"
    prompts_path.write_text(json.dumps({...}), encoding="utf-8")

    # Build RuntimeOptions (all fields required)
    options = RuntimeOptions(source="test", data_dir=tmp_path, ...)

    # Call
    result = my_pipeline_step(options, "transcript text")
    assert result.field == "expected output"
```

### Testing Orchestrator Integration
```python
# Mock run_quickread with a pre-built OrchestratorResult
monkeypatch.setattr(
    "app.web.run_quickread",
    lambda _options: OrchestratorResult(
        source=SourceInfo(...),
        transcript=TranscriptResult(...),
        summary=SummaryResult(...),
        artifacts=ArtifactBundle(...),
        rendered="rendered text",
        calibration=CalibrationResult(...),  # optional
    ),
)
```

### Expected Exception Testing
```python
try:
    my_func(bad_input)
except VividError as exc:
    assert "expected substring" in str(exc)
else:
    raise AssertionError("expected VividError was not raised")
```

## Common Pitfalls

1. **RuntimeOptions has ~50 required fields** — when constructing it in tests, provide all of them or use a helper like `test_calibration.py`'s `_make_options()`. The `slots=True` means you can't use `**kwargs` expansion.

2. **Adapters raise `VividError`** — always catch with `except Exception` at pipeline level and re-emit as diagnostics. The orchestrator uses try/except around calibration with `# noqa: BLE001`.

3. **`SummaryPromptStore` is generic** — despite living in `app/subsystems/summary/`, it's used to load both summary and calibration prompts. The `Summary` in its name is historical.

4. **Provider configs are shared** — summarization and calibration both use `build_summary_provider_configs()`. Adding a new provider automatically works for both.

5. **The `model` field priority** — `options.siliconflow_model` (from env var) overrides `providers.json`'s model. This changed recently — env var is now optional; when absent, the JSON value is used directly.

6. **Checkpoint keys accumulate** — `update_run_state()` skips `None` values but doesn't delete old keys. When resuming, all keys from previous runs remain.

7. **Web UI is a single file** — `app/web.py` contains the entire app: API routes, JobManager, inline HTML/CSS/JS. The HTML is inside a Python string returned by `_render_index()`.

8. **No formatter/linter** — the repo has no configured formatter. Match surrounding code style manually.

9. **Bilibili compatibility lives in the helper** — compare rule changes against `bili23/Bili23-Downloader`, then update `tools/bilibili/bili23_agent_cli.py` with regression coverage in `tests/test_download_adapters.py`. Do not use `tools/Bili23-Downloader` as the reference source; that path is not the maintained upstream checkout. Do not change `app/adapters/bilibili.py` unless the helper CLI contract or adapter-level error mapping must change.

## References

- `references/reference.md` — Full API reference: all models, adapters, services, utils, config shapes, and CLI flags with signatures
