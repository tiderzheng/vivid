# Summary Outline Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 AI 总结升级为六段式结构，并要求 skill/agent 完整返回这些内容。

**Architecture:** 扩展 `SummaryResult` 为新结构，同时保留旧别名兼容层；更新默认 summary prompt、LLM 解析、fallback summary、run_state、formatter、artifact writer、Web 展示和 skill 规范。

**Tech Stack:** Python, pytest, FastAPI, existing summary subsystem and skill docs

---

### Task 1: 锁定新摘要结构

**Files:**
- Modify: `tests/test_fallback_summary.py`
- Modify: `tests/test_formatter.py`

- [ ] **Step 1: Write the failing tests**

新增断言：
- LLM 返回的新 JSON key 能被解析到 `title` / `overview` / `core_points` / `controversies` / `action_suggestions` / `playful_comment`
- formatter 输出包含“内容概览 / 核心观点 / 争议点 / 行动建议 / 俏皮点评”
- 旧别名 `one_line / detailed / key_points` 仍可读取

- [ ] **Step 2: Run tests to verify they fail**

Run:
- `python -m pytest tests/test_fallback_summary.py tests/test_formatter.py -q`

- [ ] **Step 3: Implement minimal summary schema changes**

更新：
- `app/models/summary.py`
- `app/adapters/llm.py`
- `app/subsystems/summary/models.py`

- [ ] **Step 4: Re-run focused tests**

Run:
- `python -m pytest tests/test_fallback_summary.py tests/test_formatter.py -q`

### Task 2: 同步产物与展示层

**Files:**
- Modify: `app/services/run_state.py`
- Modify: `app/pipeline/orchestrator.py`
- Modify: `app/services/artifact_writer.py`
- Modify: `app/web.py`

- [ ] **Step 1: Extend serialization and resume compatibility**

让 run_state / API 返回同时支持新字段和旧别名。

- [ ] **Step 2: Update UI and artifact rendering**

让 `summary.md`、`summary.json`、Web 详情页按六段式展示。

- [ ] **Step 3: Run relevant tests**

Run:
- `python -m pytest tests/test_web_ui.py tests/test_orchestrator_smoke.py -q`

### Task 3: 收口 skill 规范

**Files:**
- Modify: `skill/vivid-operator/SKILL.md`
- Modify: `skill/vivid-operator/README.md`
- Modify: `skill/vivid-operator/references/workflow.md`
- Modify: `skill/vivid-operator/references/api-reference.md`
- Modify: `skill/vivid-operator/agents/openai.yaml`

- [ ] **Step 1: Update skill contract**

明确 agent 读取到 summary 后，必须完整返回六段式内容，不允许只摘标题或核心观点。

- [ ] **Step 2: Run full suite**

Run:
- `python -m pytest -q`
