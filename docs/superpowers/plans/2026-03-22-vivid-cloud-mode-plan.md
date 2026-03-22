# Vivid Cloud Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `vivid-operator` skill 增加可持久化的本地/云端双模式入口，并通过 MCP 转发到云服务器上的 Vivid Web API，同时支持本地、云端或双端产物保留策略。

**Architecture:** 先扩展 skill 状态文件与文档，让 agent 能稳定恢复 `execution_mode` / `artifact_target` / `cloud_profile`；再在 skill 执行链上抽象出 `local` 与 `cloud` 两个 executor；最后补最小的云端桥接客户端与产物同步逻辑。保持本地模式不回归，云端模式优先复用现有 Web API JSON 协议。

**Tech Stack:** Python, PowerShell, Bash, pytest, Markdown

---

### Task 1: 锁定 cloud 模式状态字段与 `paths` 暴露

**Files:**
- Modify: `tests/test_skill_wrapper_state.py`
- Modify: `tests/test_control_cli.py`
- Modify: `app/control_cli.py`

- [ ] **Step 1: Write the failing test**

新增断言覆盖：
- `skill_state.json` 允许包含 `execution_mode` / `artifact_target` / `cloud_profile`
- `paths` 输出能暴露这些字段的说明或默认值入口

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_skill_wrapper_state.py tests/test_control_cli.py -q`
Expected: FAIL because current code only exposes repo root / model / data dir defaults.

- [ ] **Step 3: Write minimal implementation**

扩展状态读取与 `build_paths_payload()` 输出，先把模式元数据打通。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_skill_wrapper_state.py tests/test_control_cli.py -q`
Expected: PASS

### Task 2: 抽象 skill 执行模式

**Files:**
- Modify: `skill/vivid-operator/scripts/vivid_operator.ps1`
- Modify: `skill/vivid-operator/scripts/vivid_operator.sh`
- Modify: `tests/test_skill_wrapper_state.py`

- [ ] **Step 1: Write the failing test**

新增断言覆盖：
- 当 `execution_mode = local` 时仍调用本地 `scripts/vivid_tool.*`
- 当 `execution_mode = cloud` 时转到 cloud executor
- 显式参数可覆盖状态文件

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_skill_wrapper_state.py -q`
Expected: FAIL because wrapper currently只有本地执行分支。

- [ ] **Step 3: Write minimal implementation**

为 wrapper 加入本地 / 云端分支路由，但云端分支先只调用一个占位命令或内部函数。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_skill_wrapper_state.py -q`
Expected: PASS

### Task 3: 增加云端桥接客户端

**Files:**
- Create: `app/services/cloud_bridge.py`
- Modify: `tests/test_control_cli.py`
- Modify: `tests/test_web_ui.py`

- [ ] **Step 1: Write the failing test**

新增断言覆盖：
- 可向云端 Web API 提交 `quickread`
- 可获取结构化返回
- 失败时保留 `error_code` / `requires_user_input`

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_control_cli.py tests/test_web_ui.py -q`
Expected: FAIL because cloud bridge does not exist yet.

- [ ] **Step 3: Write minimal implementation**

新增最小 cloud bridge 客户端，先支持：
- `submit_quickread`
- `get_job`
- `export_job_bundle`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_control_cli.py tests/test_web_ui.py -q`
Expected: PASS

### Task 4: 接上产物同步策略

**Files:**
- Create: `app/services/cloud_artifact_sync.py`
- Modify: `tests/test_orchestrator_smoke.py`
- Modify: `tests/test_web_ui.py`

- [ ] **Step 1: Write the failing test**

新增断言覆盖：
- `artifact_target = local_only` 时本地有导出产物
- `artifact_target = cloud_only` 时只返回云端信息
- `artifact_target = both` 时两边都有

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator_smoke.py tests/test_web_ui.py -q`
Expected: FAIL because current code没有云端产物同步层。

- [ ] **Step 3: Write minimal implementation**

增加最小同步器，先以“导出 ZIP 到本地解压”为主，不直接逐文件拼装。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator_smoke.py tests/test_web_ui.py -q`
Expected: PASS

### Task 5: 统一 skill 文档与交互规则

**Files:**
- Modify: `skill/vivid-operator/SKILL.md`
- Modify: `skill/vivid-operator/README.md`
- Modify: `skill/vivid-operator/references/workflow.md`
- Modify: `skill/vivid-operator/references/troubleshooting.md`
- Modify: `skill/vivid-operator/references/api-reference.md`
- Modify: `skill/vivid-operator/agents/openai.yaml`

- [ ] **Step 1: Update docs**

补充：
- `execution_mode`
- `artifact_target`
- `cloud_profile`
- 用户只在缺值时才需要被询问
- agent 优先从 `skill_state.json` 恢复

- [ ] **Step 2: Verify references**

Run: `rg -n "execution_mode|artifact_target|cloud_profile|skill_state.json|cloud" skill\\vivid-operator`
Expected: 所有关键文档都覆盖到。

### Task 6: 全量回归

**Files:**
- Modify: none

- [ ] **Step 1: Run focused tests**

Run: `python -m pytest tests/test_skill_wrapper_state.py tests/test_control_cli.py tests/test_web_ui.py -q`
Expected: PASS

- [ ] **Step 2: Run full suite**

Run: `python -m pytest -q`
Expected: PASS
