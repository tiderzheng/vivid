# Skill State Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `vivid-operator` skill 在自身目录下持久化仓库路径、默认 Whisper 模型和默认输出目录，避免 agent 上下文丢失后重复询问或把文件乱存到错误位置。

**Architecture:** 用单一 `skill_state.json` 取代当前只存 `repo_root.json` 的做法，统一保存 `repo_root`、`default_whisper_model`、`default_data_dir` 和基础元数据。PowerShell / shell wrapper 负责读写该状态文件并在显式参数、环境变量缺失时复用默认值；`paths` 控制面和 skill 文档同步暴露状态文件位置与读取优先级。

**Tech Stack:** Python, PowerShell, Bash, pytest, Markdown

---

### Task 1: 锁定 skill 状态文件行为

**Files:**
- Modify: `tests/test_skill_wrapper_state.py`
- Modify: `tests/test_control_cli.py`

- [ ] **Step 1: Write the failing tests**

新增断言覆盖：
- wrapper 首次成功后写入 `skill/vivid-operator/state/skill_state.json`
- 状态文件包含 `repo_root`
- 后续运行能从状态文件复用 `repo_root`
- `paths` 输出暴露新的 `skill_state` 路径

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skill_wrapper_state.py tests/test_control_cli.py -q`
Expected: FAIL because the code still points to `repo_root.json` and does not expose the unified state file.

- [ ] **Step 3: Write minimal implementation**

改 wrapper 和控制面，让统一状态文件路径先通。

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_skill_wrapper_state.py tests/test_control_cli.py -q`
Expected: PASS

### Task 2: 锁定默认 Whisper 模型和默认输出目录的持久化

**Files:**
- Modify: `tests/test_skill_wrapper_state.py`

- [ ] **Step 1: Write the failing tests**

新增断言覆盖：
- 状态文件可保存 `default_whisper_model`
- 状态文件可保存 `default_data_dir`
- wrapper 读到状态文件后，会把这两个默认值传给 `scripts/vivid_tool.*`
- 显式参数优先于状态文件

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_skill_wrapper_state.py -q`
Expected: FAIL because wrapper currently only persists repo root and does not inject default model/data dir.

- [ ] **Step 3: Write minimal implementation**

扩展 PowerShell / shell wrapper 的状态读写与参数拼装逻辑，仅在未显式传参时回落到 `skill_state.json`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_skill_wrapper_state.py -q`
Expected: PASS

### Task 3: 统一 skill 文档口径

**Files:**
- Modify: `skill/vivid-operator/SKILL.md`
- Modify: `skill/vivid-operator/README.md`
- Modify: `skill/vivid-operator/references/workflow.md`
- Modify: `skill/vivid-operator/references/troubleshooting.md`
- Modify: `skill/vivid-operator/references/api-reference.md`
- Modify: `skill/vivid-operator/agents/openai.yaml`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing test surrogate**

整理文档要求：
- 统一写 `skill/vivid-operator/state/skill_state.json`
- 说明只在状态文件缺值时才询问用户
- 说明可持久化项只有 `repo_root`、`default_whisper_model`、`default_data_dir`
- 明确禁止写入 `SESSDATA` / API Key

- [ ] **Step 2: Update docs and ignore rules**

把旧的 `repo_root.json` 表述全部替换或兼容说明到位，并将 `skill_state.json` 加入 `.gitignore`。

- [ ] **Step 3: Run targeted verification**

Run: `rg -n "repo_root.json|skill_state.json|default_whisper_model|default_data_dir" skill README.md docs .gitignore`
Expected: only intentional references remain.

### Task 4: 全量回归验证

**Files:**
- Modify: none

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_skill_wrapper_state.py tests/test_control_cli.py -q`
Expected: PASS

- [ ] **Step 2: Run full suite**

Run: `python -m pytest -q`
Expected: PASS
