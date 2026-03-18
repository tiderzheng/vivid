# Repository Guidelines

## Project Structure & Module Organization
`app/` contains the main Python application: CLI entrypoints, web UI, pipeline orchestration, adapters, and subsystem code for transcription and vision. `tests/` mirrors core behaviors with `pytest` coverage for pipeline, services, resolvers, and the web UI. `scripts/` holds PowerShell and Bash wrappers for setup, doctor checks, quickread runs, and config management. `configs/vision/` and `configs/transcription/` store editable JSON-based runtime presets. `tools/` contains bundled platform download helpers for Bilibili and Douyin. `data/` is runtime output only; do not commit generated artifacts.

## Build, Test, and Development Commands
Create a local environment with `python -m venv .venv` and install deps via `pip install -r requirements.txt`.

- `python -m pytest -q`: run the full test suite.
- `python -m app.cli "<source>" --json`: run the core CLI directly.
- `python -m uvicorn app.web:app --host 127.0.0.1 --port 8765`: start the web UI.
- `.\scripts\vivid_tool.ps1 -Action doctor`: validate local runtime dependencies on Windows.
- `.\scripts\vivid_tool.ps1 -Action quickread -Source "<url-or-path>"`: run the wrapper workflow with auto-venv support.

Use the matching `.sh` scripts on Linux/macOS.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, type hints where already used, small focused functions, and standard-library-first imports. Use `snake_case` for modules, functions, variables, and test files; use `PascalCase` for dataclasses and models. There is no enforced formatter in the repo today, so keep changes consistent with surrounding code and avoid style-only churn.

## Testing Guidelines
Write tests with `pytest` under `tests/` using the `test_*.py` naming pattern. Prefer fast unit tests with `tmp_path` and `monkeypatch` instead of real network calls or external binaries. When changing `scripts/`, verify the relevant PowerShell or shell entrypoint manually. When changing adapters or fallback logic, add a regression test that covers the failure path.

## Commit & Pull Request Guidelines
Current history is minimal, but `CONTRIBUTING.md` establishes the expected format: `feat(cli): ...`, `fix(adapters): ...`, `docs(readme): ...`. Keep each commit scoped to one concern. PRs should include a short problem statement, the affected modules, test evidence (`python -m pytest -q` output summary), and screenshots when the Web UI changes.

## Security & Configuration Tips
Start from `.env.example` and the `*.example.json` files in `configs/`. Never commit API keys, local media, `.venv/`, or generated files under `data/`. If you add a new env var, script flag, preset key, or artifact, update `README.md` or the relevant file in `docs/` in the same change.
