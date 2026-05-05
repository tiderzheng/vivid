# Vivid Operator Skill

面向 OpenClaw、Codex 等 agent 的 Vivid 速看 skill。

## Human Setup

### 入口

- Windows: `skill/vivid-operator/scripts/vivid_operator.ps1`
- Linux/macOS: `skill/vivid-operator/scripts/vivid_operator.sh`

底层主控制脚本：

- `scripts/vivid_tool.ps1`
- `scripts/vivid_tool.sh`

### 基本用法

```powershell
# 检查路径
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action paths

# 检查环境
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action doctor

# 执行速看
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "视频链接或本地路径"

# Bilibili 二维码登录
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action bili-auth-qrcode
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action bili-auth-poll -QrcodeKey "<qrcode_key>"
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action bili-auth-status

# Bilibili 登录失败时，优先显式传完整 Cookie
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "https://www.bilibili.com/video/BV..." -BiliCookie "SESSDATA=...; bili_jct=...; DedeUserID=..."

# 只有拿不到完整 Cookie 时，再兼容旧的 SESSDATA
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "https://www.bilibili.com/video/BV..." -Sessdata "..."

# 启动 Web UI
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action web-ui
```

### 环境前提

- Python 3.10+
- ffmpeg
- 可选：Node.js（仅抖音下载）
- Bilibili/Douyin 下载器已内嵌到 `tools/`

### 状态持久化

`skill/vivid-operator/state/skill_state.json` 只保存稳定默认值：

- `repo_root`
- `default_whisper_model`
- `default_data_dir`
- `execution_mode`
- `artifact_target`
- `cloud_profile`
- `cloud_base_url`

不保存 Cookie、Token、API Key。`Bilibili` 完整 `Cookie` 如由用户显式传入，会由 Vivid 应用层保存到项目目录 `configs/secrets/bilibili_cookie.json`，不写入 skill 状态。

二维码登录成功后同样由 Vivid 应用层保存到 `configs/secrets/bilibili_cookie.json`，skill 状态只保存仓库路径和稳定默认值。

## Agent Behavior Contract

### 必须直接触发的场景

- 用户只贴一个支持的视频 URL
- 用户只给一个本地媒体路径
- 用户说“看看这个”“这个视频讲了啥”“总结下这个视频”
- 上一轮已经锁定视频源，这一轮只说“继续”“总结下”

### 禁止先问的问题

- “你想让我做什么”
- “是否需要使用 Vivid”
- “你要 transcript 还是 summary”
- “要不要先分析这个链接”

只要 `source` 已经足够，就先执行 `quickread`。

### 成功时必须怎么回

按固定顺序返回 6 段：

1. 标题
2. 内容概览
3. 核心观点
4. 争议点
5. 行动建议
6. 俏皮点评

不要只回一句短总结，也不要只给文件路径。

### 失败时必须怎么回

至少给出：

- 失败阶段
- 主错误
- 精简后的错误摘要
- 1 到 2 个下一步动作

不要直接把原始 JSON 丢给用户。

### Bilibili 规则

- `Bilibili` 仍然按“直接下载媒体 -> Whisper / OCR”处理，不恢复官方字幕优先
- helper 会先尝试完整 `Cookie`，其次兼容 `SESSDATA`，没有凭据时自动补匿名请求画像
- 支持先走二维码登录维护项目本地登录态：`bili-auth-qrcode`、`bili-auth-poll`、`bili-auth-status`、`bili-auth-logout`
- 匿名请求画像包括 `_uuid`、`b_lsid`、`b_nut`、`buvid3`、`buvid4`、`buvid_fp`，由 helper 按 `Bili23` 规则维护；即使完整 `Cookie` 里带了这些旧值，helper 也会刷新覆盖
- helper 会先写入基础登录态，再获取/刷新匿名画像、尽量获取 `bili_ticket` 与调用 `ExClimbWuzhi` 激活
- `bili_ticket` / `ExClimbWuzhi` 获取失败不等于需要登录；除非错误明确指向登录失败，不要因此要求用户提供 `Cookie`
- 支持常见 `Bilibili` 链接形态：`BV`、`av`、`ep`、`ss`、`md`
- agent 不应在首次尝试前就要求用户提供 `Cookie / SESSDATA`
- 只有在出现 `-101`、`账号未登录`、`login required` 之类登录错误后，才应引导用户刷新凭据
- 优先建议二维码登录；不方便扫码时再建议 `-BiliCookie` / `--bili-cookie` 或 `VIVID_BILI_COOKIE`
- 用户显式传入完整 `Cookie` 后，Vivid 会保存到项目目录 `configs/secrets/bilibili_cookie.json`，后续可自动回用；不要在回答、日志、prompt 或 `skill_state.json` 中回显该值
- 只有拿不到完整 `Cookie` 时，才兼容 `-Sessdata` / `--sessdata`
- 不要建议把 `Cookie / SESSDATA` 持久化到 `skill_state.json` 或非项目 secret 文件

### 云端模式

- 默认走本地
- 只有用户明确要求云端时才切换
- 如果缺 `cloud_base_url`，只问最短阻塞问题，不要展开盘问一堆可选项

## Notes for OpenClaw

如果你发现 agent 在“只贴链接”时没有触发 Vivid，优先检查：

- skill 是否真的被宿主加载
- 宿主是否会读取 `agents/openai.yaml`
- 宿主是否会把“只贴 URL”当作普通分享而不是执行请求

本 skill 现在的设计目标就是修正这类“弱意图不触发”的情况。

## References

- `SKILL.md`：行为契约
- `references/reference.md`：参数、返回字段、状态文件和默认值优先级
