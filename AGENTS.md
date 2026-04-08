# Repository Guidelines

## Project Overview
Vivid (瞬知) is a Python application that turns video sources into readable quickread artifacts via a pipeline: download -> transcription/OCR -> summarization. It exposes a CLI, a FastAPI web UI, and a skill wrapper for agent-driven usage.

## Project Structure & Module Organization
```
app/                        # Main application package
  adapters/                 # External service adapters (bilibili, douyin, ears4, eyes, llm, ytdlp)
  models/                   # Data models (artifact, runtime, source, summary, transcript)
  pipeline/                 # Core orchestration (acquisition, detector, formatter, orchestrator, summarization, transcription)
  services/                 # Shared services (artifact_writer, cleanup, cloud_bridge, diagnostics, ffmpeg_locator, media_store, pathing, project_naming, run_state)
  subsystems/               # Domain subsystems
    transcription/          # Whisper/Ears4 transcription engine, resolver, store, presets
    vision/                 # OCR/Eyes vision engine, resolver, store, probes
    summary/                # LLM summarization resolver, store, providers
  utils/                    # Utilities (json_utils, logging_utils, retry, subprocess_utils, text)
  cli.py                    # CLI entrypoint (argparse-based)
  config.py                 # Settings dataclass, env var loading
  constants.py              # App-wide constants and defaults
  exceptions.py             # VividError hierarchy
  runtime_factory.py        # Builds RuntimeOptions from Settings + CLI/web values
  web.py                    # FastAPI web UI with job management
configs/                    # JSON runtime presets
  vision/                   # api_configs.json, prompts.json
  transcription/            # presets.json
  summary/                  # prompts.json, providers.json
  web_ui/                   # preferences.json (gitignored)
tests/                      # pytest test suite (mirrors app/ structure)
scripts/                    # PowerShell (.ps1) and Bash (.sh) wrappers
tools/                      # Bundled platform download helpers (bilibili, douyin)
data/                       # Runtime output only; do not commit generated artifacts
skill/                      # Agent skill wrapper
```

## Build, Test, and Development Commands

### Setup
```bash
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate
pip install -r requirements.txt
```

Dev dependencies (pytest, httpx): `pip install -e ".[dev]"`

### Running Tests
```bash
python -m pytest -q                     # Full test suite (quiet)
python -m pytest                        # Full test suite (verbose)
python -m pytest tests/test_web_ui.py   # Single test file
python -m pytest tests/test_detector.py::test_detect_bilibili  # Single test
python -m pytest tests/test_formatter.py -v  # Verbose single file
python -m pytest -x                     # Stop on first failure
python -m pytest -k "bilibili"          # Run tests matching keyword
```

pytest config is in `pyproject.toml` under `[tool.pytest.ini_options]`: testpaths=["tests"], pythonpath=["."].

### Running the Application
```bash
python -m app.cli "<source>" --json     # CLI with JSON output
python -m uvicorn app.web:app --host 127.0.0.1 --port 8765  # Web UI
```

### Platform Scripts
```powershell
.\scripts\vivid_tool.ps1 -Action doctor                              # Validate dependencies
.\scripts\vivid_tool.ps1 -Action quickread -Source "<url-or-path>"   # Wrapper workflow
```
Use matching `.sh` scripts on Linux/macOS.

### Linting / Formatting
There is no enforced formatter or linter configured in the repo. Keep changes consistent with surrounding code. Avoid style-only churn. When in doubt, match the existing patterns.

## Coding Style & Naming Conventions

### Python Version
Requires Python >= 3.10. Uses `X | Y` union syntax (not `Optional`/`Union`), `match` statements where appropriate.

### Imports
- Always start with `from __future__ import annotations` in every module (enables deferred evaluation of type hints).
- Standard library imports first, then third-party, then local (relative) imports.
- Use relative imports within `app/` (e.g., `from ..exceptions import VividError`, `from .config import load_settings`).
- Keep imports focused; avoid importing entire modules when specific names suffice.

### Formatting
- 4-space indentation, no tabs.
- Lines wrap naturally; no strict line length enforced.
- Trailing commas in multi-line collections and dataclass fields are used consistently.

### Type Hints
- All function signatures use type hints.
- Use `str | None` (not `Optional[str]`), `dict[str, Any]` (not `Dict`), `list[str]` (not `List`).
- Use `from typing import Any` when needed; avoid importing `Dict`, `List`, `Optional` from typing.
- Dataclasses use `@dataclass(slots=True)` for all model classes.

### Naming
- Modules, functions, variables, test files: `snake_case`
- Dataclasses and classes: `PascalCase` (e.g., `RuntimeOptions`, `OrchestratorResult`, `BilibiliAdapter`)
- Constants at module level: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_MODEL`, `VIDEO_EXTS`)
- Private module-level helpers: `_leading_underscore` (e.g., `_text_or_none`, `_coerce_path`)
- Test functions: `test_<descriptive_name>` (e.g., `test_bilibili_adapter_calls_helper_for_subtitles`)

### Data Models
- Define dataclasses in `app/models/` or within subsystem `models.py` files.
- Use `@dataclass(slots=True)` for all data models.
- Optional fields use `field_name: Type | None = None` with defaults at the end.
- Models include `to_dict()` and/or `to_payload()` serialization methods when needed.

### Error Handling
- Custom exceptions inherit from `VividError(RuntimeError)` in `app/exceptions.py`.
- Specific sub-exceptions exist for known failure modes (e.g., `BilibiliSessdataExpiredError`).
- Adapters catch subprocess/network errors and re-raise as `VividError` with context.
- Top-level handlers (CLI `main()`, web endpoints) catch broad `Exception` with `# noqa: BLE001`.
- Use `raise ... from exc` to preserve exception chains.
- Logging goes to stderr via `app.utils.logging_utils` (`log_event`, `log_exception`), never print to stdout except for final output.

### Adapter Pattern
- Each external service has an adapter class in `app/adapters/` (e.g., `BilibiliAdapter`, `Ears4Adapter`).
- Adapters accept config in `__init__` and expose domain methods (e.g., `download_media`, `transcribe`).
- Adapters are instantiated with resolved paths/URLs, not raw environment variables.

### Functions
- Prefer small, focused functions.
- Private helpers prefixed with `_` at module level.
- Use keyword-only arguments for clarity in service functions (e.g., `def resolve_ffmpeg_bin(preferred=None, *, repo_root=None)`).

## Testing Guidelines

- Write tests with `pytest` under `tests/` using the `test_*.py` naming pattern.
- Test files mirror the app module they test (e.g., `test_download_adapters.py` for `app/adapters/`).
- Prefer fast unit tests with `tmp_path` and `monkeypatch` instead of real network calls or external binaries.
- Use `fastapi.testclient.TestClient` for web UI endpoint tests.
- Construct `Settings` objects directly in tests using helper functions (see `test_web_ui.py:_build_settings` for the full field list).
- When changing adapters or fallback logic, add a regression test that covers the failure path.
- When changing `scripts/`, manually verify the relevant PowerShell or shell entrypoint.

### Test Structure Example
```python
from pathlib import Path
from app.adapters.bilibili import BilibiliAdapter

def test_adapter_behavior(tmp_path, monkeypatch):
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")

    def fake_run(command, cwd=None, retries=1):
        ...  # set up fake results

    monkeypatch.setattr("app.adapters.bilibili.run_command", fake_run)
    adapter = BilibiliAdapter(helper)
    result = adapter.export_subtitles("https://...", tmp_path, "sess")
    assert result == "expected"
```

## Configuration

- Environment variables loaded in `app/config.py` via `os.environ.get()`.
- All env vars are documented in `.env.example`.
- JSON presets in `configs/` for vision, transcription, and summary subsystems.
- CLI args and web form values override settings via `app/runtime_factory.py`.
- Store classes (e.g., `VisionStore`, `TranscriptionStore`) load and query JSON preset files.

## Commit & Pull Request Guidelines

Conventional commit format with scope:
- `feat(cli): add quickread json flag`
- `fix(adapters): handle empty eyes result`
- `docs(readme): clarify setup steps`
- `test(pipeline): add acquisition mode coverage`

Keep each commit scoped to one concern. PRs should include:
1. Short problem statement
2. Affected modules
3. Test evidence (`python -m pytest -q` output)
4. Screenshots when the Web UI changes

## Security & Configuration

- Start from `.env.example` for environment config.
- Never commit API keys, credentials, `.env`, local media, `.venv/`, or generated files under `data/`.
- If you add a new env var, script flag, preset key, or artifact, update `.env.example`, `README.md`, and relevant docs in the same change.
- API keys are read from env vars at runtime; never hardcode or log them.

## Key Conventions Summary

| Aspect | Convention |
|---|---|
| Python version | >= 3.10 |
| Type unions | `X \| Y` (not `Optional`) |
| Dataclasses | `@dataclass(slots=True)` |
| Imports | `from __future__ import annotations` first; relative imports within app |
| Naming | `snake_case` for functions/vars, `PascalCase` for classes, `UPPER_SNAKE` for constants |
| Error hierarchy | `VividError(RuntimeError)` base in `app/exceptions.py` |
| Test framework | pytest with `tmp_path` and `monkeypatch` |
| Web framework | FastAPI with `TestClient` for tests |
| Formatting | No enforced tool; match surrounding code |
| Commit style | `feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...` |
