# Vector Source Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在每个工作目录下新增 `vector_source/` 目录，并输出可直接用于未来向量化入库的 JSON/JSONL 文件。

**Architecture:** 扩展 `ArtifactBundle`，新增 `vector_source` 文件路径；在 artifact 写入阶段同步生成 `document.json`、`chunks.jsonl`、`manifest.json`；Web/结果序列化暴露这些文件；skill 规范要求向量化相关任务优先读取该目录。

**Tech Stack:** Python, pytest, existing artifact writer/web serialization/skill docs

---

### Task 1: 锁定 vector_source 产物

**Files:**
- Modify: `tests/test_orchestrator_smoke.py`
- Modify: `tests/test_web_ui.py`

- [ ] **Step 1: Write the failing tests**

新增断言：
- `run_quickread()` 成功后，`result.artifacts.vector_source_dir`、`vector_document_json`、`vector_chunks_jsonl`、`vector_manifest_json` 存在
- `document.json` 包含 summary 六段与 transcript
- `chunks.jsonl` 至少包含 summary chunk 和 transcript chunk
- Web `/api/quickread` 或序列化结果里能看到这些文件路径

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `python -m pytest tests/test_orchestrator_smoke.py tests/test_web_ui.py -q`

- [ ] **Step 3: Implement minimal artifact writing**

更新：
- `app/models/artifact.py`
- `app/services/artifact_writer.py`
- 如有必要新增 `app/services/vector_source_writer.py`
- `app/pipeline/orchestrator.py`
- `app/web.py`

- [ ] **Step 4: Re-run focused tests**

Run:
- `python -m pytest tests/test_orchestrator_smoke.py tests/test_web_ui.py -q`

### Task 2: 更新 skill 约束

**Files:**
- Modify: `skill/vivid-operator/SKILL.md`
- Modify: `skill/vivid-operator/README.md`
- Modify: `skill/vivid-operator/references/workflow.md`
- Modify: `skill/vivid-operator/references/api-reference.md`
- Modify: `skill/vivid-operator/agents/openai.yaml`

- [ ] **Step 1: Update skill guidance**

明确：
- `vector_source/` 是面向未来向量化/embedding 的目录
- 相关任务优先读取该目录，不优先反解析 `quickread.md`

- [ ] **Step 2: Run full suite**

Run:
- `python -m pytest -q`
