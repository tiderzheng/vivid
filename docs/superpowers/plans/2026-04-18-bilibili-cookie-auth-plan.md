# Bilibili Cookie Auth Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 恢复 Bilibili 完整 cookie 输入与传递链路，让 `Vivid` 在完整 cookie 优先、`SESSDATA` 兼容的前提下重新稳定下载 Bilibili 内容。

**Architecture:** 运行时层恢复 Bilibili 凭证字段，但只在内部传递，不进入公开 job request。adapter 统一通过环境变量向 helper 传递凭证；helper 负责解析完整 cookie、兼容 `SESSDATA`、并自动补充匿名指纹 cookie。CLI 与 Web UI 同时恢复输入入口，并严格脱敏。

**Tech Stack:** Python, argparse, FastAPI, requests, pytest

---

### Task 1: 锁定运行时优先级与公开请求边界

**Files:**
- Modify: `tests/test_runtime_factory.py`
- Modify: `tests/test_web_ui.py`
- Modify: `tests/test_control_cli.py`
- Modify: `app/models/runtime.py`
- Modify: `app/config.py`
- Modify: `app/runtime_factory.py`
- Modify: `app/web.py`

- [ ] **Step 1: Write the failing runtime tests**

新增运行时测试，覆盖：

- `bili_cookie` 明确传入时优先于 `sessdata`
- 未显式传入时，`VIVID_BILI_COOKIE` 优先于 `BILI_SESSDATA`
- 仅有 `sessdata` 时仍能构建运行时对象

- [ ] **Step 2: Write the failing Web public-request tests**

新增 Web/UI 测试，断言：

- 表单允许接收 `bili_cookie` / `sessdata`
- `job["request"]`、bootstrap defaults、公开 payload 中都没有这两个字段

- [ ] **Step 3: Run focused tests to verify they fail**

Run:
- `python -m pytest tests/test_runtime_factory.py -q`
- `python -m pytest tests/test_web_ui.py -q`
- `python -m pytest tests/test_control_cli.py -q`

Expected: FAIL because current runtime model does not carry `bili_cookie`, and current Web/CLI layer has no restored complete-cookie support.

- [ ] **Step 4: Write minimal runtime/config implementation**

实现：

- `Settings` 增加 `bili_cookie`
- `RuntimeOptions` 增加 `bili_cookie` / `sessdata`
- `build_runtime_options()` 实现优先级解析
- `app/web.py` 继续过滤敏感字段，不公开回显

- [ ] **Step 5: Re-run focused tests**

Run:
- `python -m pytest tests/test_runtime_factory.py -q`
- `python -m pytest tests/test_web_ui.py -q`
- `python -m pytest tests/test_control_cli.py -q`

Expected: PASS

### Task 2: 锁定 adapter 的环境注入与 helper 调用方式

**Files:**
- Modify: `tests/test_download_adapters.py`
- Modify: `app/adapters/bilibili.py`
- Modify: `app/pipeline/acquisition.py`
- Modify: `app/pipeline/orchestrator.py`

- [ ] **Step 1: Write the failing adapter tests**

新增测试覆盖：

- 完整 cookie 存在时，adapter 通过环境变量传递 `VIVID_BILI_COOKIE`
- 仅 `sessdata` 存在时，adapter 保留 `BILI_SESSDATA`
- helper 命令默认不带敏感 `--bili-cookie` / `--sessdata`

- [ ] **Step 2: Run the adapter tests to verify failure**

Run:
- `python -m pytest tests/test_download_adapters.py -q`

Expected: FAIL because current adapter 会删掉 `BILI_SESSDATA`，且不支持完整 cookie 传递。

- [ ] **Step 3: Write minimal adapter/orchestrator implementation**

实现：

- `BilibiliAdapter.get_video_title()` / `download_media()` 接收 `bili_cookie` 与 `sessdata`
- `_helper_env()` 只注入有效凭证，不再盲删 `BILI_SESSDATA`
- `acquisition.py` / `orchestrator.py` 把运行时凭证传给 adapter

- [ ] **Step 4: Re-run adapter tests**

Run:
- `python -m pytest tests/test_download_adapters.py -q`

Expected: PASS

### Task 3: 锁定 helper 的完整 cookie 解析与匿名指纹补全

**Files:**
- Modify: `tests/test_download_adapters.py`
- Modify: `tools/bilibili/bili23_agent_cli.py`

- [ ] **Step 1: Write the failing helper-focused tests**

为 helper 增加最小单元覆盖，至少验证：

- 完整 cookie 字符串可被解析为 session cookies
- 仅 `SESSDATA` 时能包装成 cookie
- 自动补 `_uuid`、`b_lsid`、`b_nut`
- 已提供的 cookie 不被覆盖

- [ ] **Step 2: Run targeted tests to verify failure**

Run:
- `python -m pytest tests/test_download_adapters.py -q`

Expected: FAIL because helper currently only sets `SESSDATA` and has no完整 cookie parsing/补全逻辑。

- [ ] **Step 3: Write minimal helper implementation**

在 `tools/bilibili/bili23_agent_cli.py` 中增加：

```python
cookie_header = a.bili_cookie or os.environ.get("VIVID_BILI_COOKIE", "")
sessdata = a.sessdata or os.environ.get("BILI_SESSDATA", "")
```

并补充：

- cookie header 解析函数
- 匿名 cookie 生成函数
- `buvid3` / `buvid4` 拉取函数

- [ ] **Step 4: Re-run targeted tests**

Run:
- `python -m pytest tests/test_download_adapters.py -q`

Expected: PASS

### Task 4: 恢复 CLI / Web UI 输入入口并做回归验证

**Files:**
- Modify: `app/cli.py`
- Modify: `app/web.py`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `tests/test_control_cli.py`
- Modify: `tests/test_web_ui.py`
- Modify: `tests/test_windows_script_compat.py`

- [ ] **Step 1: Write the failing CLI/Web tests**

新增或调整测试，覆盖：

- CLI 接受 `--bili-cookie`
- 旧 `--sessdata` 仍兼容
- Web UI 表单接收 `bili_cookie`
- Windows wrapper 兼容旧 `--sessdata`，但不把完整 cookie 暴露到公开记录

- [ ] **Step 2: Run focused interface tests to verify failure**

Run:
- `python -m pytest tests/test_control_cli.py -q`
- `python -m pytest tests/test_web_ui.py -q`
- `python -m pytest tests/test_windows_script_compat.py -q`

Expected: FAIL because current interface only保留遗留 `sessdata` 兼容壳，且没有完整 cookie 输入。

- [ ] **Step 3: Write minimal interface/docs implementation**

实现：

- CLI 增加 `--bili-cookie`
- Web UI 增加完整 cookie 输入
- `.env.example` 与 `README.md` 文档化 `VIVID_BILI_COOKIE`

- [ ] **Step 4: Re-run focused interface tests**

Run:
- `python -m pytest tests/test_control_cli.py -q`
- `python -m pytest tests/test_web_ui.py -q`
- `python -m pytest tests/test_windows_script_compat.py -q`

Expected: PASS

### Task 5: 做整体回归验证

**Files:**
- Test: `tests/test_runtime_factory.py`
- Test: `tests/test_download_adapters.py`
- Test: `tests/test_control_cli.py`
- Test: `tests/test_web_ui.py`
- Test: `tests/test_windows_script_compat.py`

- [ ] **Step 1: Run the focused regression suite**

Run:
- `python -m pytest tests/test_runtime_factory.py tests/test_download_adapters.py tests/test_control_cli.py tests/test_web_ui.py tests/test_windows_script_compat.py -q`

Expected: PASS

- [ ] **Step 2: Run full suite**

Run:
- `python -m pytest -q`

Expected: PASS
