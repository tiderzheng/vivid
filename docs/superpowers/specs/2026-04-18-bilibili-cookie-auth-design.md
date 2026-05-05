# Bilibili 完整 Cookie 恢复设计

## 背景

当前 `Vivid` 的 Bilibili 下载链路在 `2026-04-08` 的回归中移除了 `SESSDATA` 和相关登录态传递，导致 helper 只能以匿名模式访问接口。Bilibili 当前策略下，部分接口仅提供 `SESSDATA` 已不足以稳定通过鉴权，容易出现 `api error -101: 账号未登录`。

参考 `D:\ai\Bili23-Downloader-2.00.1\Bili23-Downloader-2.00.1` 可见，其请求层除登录态 cookie 外，还会补充 `_uuid`、`b_lsid`、`b_nut`、`buvid3`、`buvid4`、`bili_ticket` 等 cookie/指纹字段。因此本次修复不能停留在“恢复旧版 `SESSDATA` 参数”，而应恢复一条完整、可兼容旧输入的 cookie 注入链路。

## 目标

1. 同时恢复环境变量、CLI、Web UI 三种 Bilibili 凭证输入方式。
2. 以“完整 Cookie 字符串”为主输入，兼容旧 `SESSDATA` 输入。
3. helper 优先使用完整 cookie，并自动补齐匿名指纹 cookie，尽量贴近 `Bili23` 的请求画像。
4. 公开请求载荷、任务历史、Web UI 回显中不得保存或暴露敏感 cookie 明文。
5. 保持现有 Bilibili 下载、标题探测、Web job 提交链路的调用方式基本稳定，不做超出本次需求的登录系统重写。

## 非目标

- 不实现 `Bili23` 全量扫码登录、短信登录、票据长期刷新流程。
- 不在本次改动中新增独立的账号管理 UI。
- 不修改 Douyin、通用 `yt-dlp` 或本地文件链路。
- 不把凭证写入持久化配置文件或任务历史 JSON。

## 方案

### 1. 凭证模型

新增 `bili_cookie` 作为主凭证字段，语义为“完整 Cookie 请求头值”，例如：

`SESSDATA=...; bili_jct=...; DedeUserID=...`

兼容旧输入：

- 环境变量：保留 `BILI_SESSDATA`，新增 `VIVID_BILI_COOKIE`
- CLI：保留 `--sessdata`，新增 `--bili-cookie`
- Web UI：新增完整 cookie 和 `SESSDATA` 可选输入

优先级：

1. 显式 `bili_cookie`
2. 环境变量 `VIVID_BILI_COOKIE`
3. 显式 `sessdata`
4. 环境变量 `BILI_SESSDATA`

如果仅提供 `SESSDATA`，系统将自动包装为 `SESSDATA=<value>` 并继续执行。

### 2. adapter 与运行时传递

`RuntimeOptions` 恢复 Bilibili 凭证字段，但区分：

- `bili_cookie: str | None`
- `sessdata: str | None`

业务层只向 adapter 暴露解析后的有效凭证语义，不把敏感值带入 Web job 的 `request` 公共字段。

`BilibiliAdapter` 调用 helper 时，优先通过环境变量传递凭证：

- `VIVID_BILI_COOKIE`
- `BILI_SESSDATA`

避免默认把完整 cookie 暴露在进程命令行参数中。命令行 `--bili-cookie` / `--sessdata` 仅保留给直接调用 helper 的兼容用途。

### 3. helper 升级

`tools/bilibili/bili23_agent_cli.py` 增加以下能力：

1. 接受 `--bili-cookie` 参数和 `VIVID_BILI_COOKIE` 环境变量。
2. 解析完整 cookie 字符串并写入 `requests.Session().cookies`。
3. 如果只拿到 `SESSDATA`，则兼容旧逻辑。
4. 自动补齐匿名 cookie：
   - `_uuid`
   - `b_lsid`
   - `b_nut`
5. 尝试按 `Bili23` 思路获取或补齐：
   - `buvid3`
   - `buvid4`
6. 保持 `Referer` 和浏览器 `User-Agent`。

helper 的目标不是完整复刻 `Bili23` 登录模块，而是在不引入 GUI 登录系统的前提下，尽可能复用其“请求画像更完整”的关键部分。

### 4. Web UI 与脱敏

Web 表单新增两个可选字段：

- `bili_cookie`
- `sessdata`

这两个字段只用于当次提交，不进入：

- `_public_request()`
- `jobs.json`
- 前端 `defaults`
- 诊断事件明文数据

如果任务失败，错误信息可以说明“登录态失效/未登录”，但不得回显 cookie 内容。

## 风险控制

- 公开载荷过滤要覆盖 CLI/Web/job history 三层，避免凭证泄露。
- helper 自动补充匿名 cookie 时只补缺失项，不覆盖用户提供值。
- 变更范围聚焦在 Bilibili 链路和输入层，避免对现有 orchestrator 其他平台逻辑产生副作用。
- 用 pytest 回归以下行为：优先级、adapter 环境注入、helper cookie 解析、Web UI 脱敏、CLI 兼容。
