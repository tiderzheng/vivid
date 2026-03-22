# Douyin Summary Title Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让抖音链接在拿不到前置标题时，改用 AI 总结的一句话作为最终项目目录名。

**Architecture:** 保持现有前置标题探测不变，仅在抖音兜底命名路径上增加“摘要完成后二次重命名”。编排层负责决定何时触发、何时更新 checkpoint 和路径引用，其他平台完全不变。

**Tech Stack:** Python, pytest, existing orchestrator/pathing/run_state services

---

### Task 1: 锁定摘要后重命名行为

**Files:**
- Modify: `tests/test_orchestrator_smoke.py`
- Test: `tests/test_orchestrator_smoke.py`

- [ ] **Step 1: Write the failing test**

新增一个抖音用例，模拟：
- `DouyinAdapter.get_video_title()` 返回 `None`
- 获取文本成功
- 总结返回 `one_line="AI 总结标题"`

断言：
- `result.source.title == "AI 总结标题"`
- `result.artifacts.workdir.name == "AI 总结标题"`
- checkpoint 中的 `title` / `workdir` 已更新

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator_smoke.py::test_orchestrator_uses_summary_title_for_douyin_fallback -q`
Expected: FAIL because current code still uses source/media fallback naming.

- [ ] **Step 3: Write minimal implementation**

在 `app/pipeline/orchestrator.py` 中识别“抖音 + 无用户标题 + 无远端标题”的兜底场景；总结完成后使用 `summary.one_line` 重命名目录并更新运行状态。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator_smoke.py::test_orchestrator_uses_summary_title_for_douyin_fallback -q`
Expected: PASS

### Task 2: 做回归验证

**Files:**
- Modify: `app/pipeline/orchestrator.py`
- Test: `tests/test_orchestrator_smoke.py`

- [ ] **Step 1: Run focused regression tests**

Run:
- `python -m pytest tests/test_orchestrator_smoke.py -q`

Expected: all orchestrator smoke tests pass.

- [ ] **Step 2: Run full suite**

Run:
- `python -m pytest -q`

Expected: full suite passes.
