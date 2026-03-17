# Changelog（瞬知 / Vivid）

All notable changes to **瞬知**（Vivid） will be documented in this file.

The project currently follows a lightweight Keep a Changelog style.

## [0.1.0] - 2026-03-14

### Added

- Initial **瞬知**（Vivid） project scaffold
- Modular `app/` structure for adapters, pipeline, services, and utils
- CLI entrypoint and PowerShell control scripts
- `vivid-operator` skill and references
- Basic tests for detector, formatter, naming, fallback summary, and orchestrator smoke flow
- Installation, configuration, and usage documentation
- Example payload and output structure docs

### Changed

- Migrated core quickread orchestration from the previous single-file workflow into the **瞬知**（Vivid） project structure
- Upgraded PowerShell control surface to JSON-first outputs for agents
- Updated project positioning from a quickread-only wrapper to a unified large-project direction that will absorb former `Ears4` and `Eyes` capabilities over time

### Notes

- This version is suitable as a local development baseline
- Packaging, release process, and final open-source polish are still being refined
