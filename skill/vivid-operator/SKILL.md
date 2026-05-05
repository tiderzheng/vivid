---
name: vivid-operator
description: Use when a user pastes a bilibili/douyin/youtube URL, a local video or audio path, or asks what a video says, even if they do not explicitly ask for summarization or mention Vivid.
---

# Vivid Operator Skill

## Overview

把“可执行的视频/音频来源”视为执行请求，不视为闲聊或普通分享。

只要 `source` 已经足够，就先运行 Vivid，再回答用户；不要先做确认式追问。

## When It Must Trigger

| 输入信号 | 正确动作 | 错误动作 |
|---|---|---|
| 只发一个支持的视频 URL | 直接执行 `quickread` | 问“你想让我做什么” |
| URL + 弱意图，如“看看这个”“这个讲啥” | 直接执行 `quickread` | 问“要不要总结” |
| 本地媒体路径，如 `.mp4` `.mov` `.mp3` `.wav` | 直接执行 `quickread` | 问“你是要转录还是摘要” |
| 上一轮已锁定 `source`，这一轮只说“继续”“总结下” | 复用已有 `source` 执行 | 假装上下文不存在，重新盘问 |
| 明确说“速看”“视频总结”“看视频”“用瞬知” | 只要有来源就直接执行 | 先解释功能，再等待确认 |

支持的弱意图包括但不限于：

- “看看这个视频讲了啥”
- “帮我过一下这个”
- “这个视频主要说什么”
- “总结下这个链接”

## When It Must Not Ask

当 `source` 已经足够时，禁止先问这些问题：

- “是否需要使用 Vivid”
- “你想让我做什么”
- “你要 transcript 还是 summary”
- “要不要我先分析一下这个链接”
- “你要不要先提供 Bilibili 的 Cookie / SESSDATA”
- “你想用哪个平台/模型/输出目录”

默认值优先级已经由 Vivid 和 `skill_state.json` 处理。来源足够时，先执行。`Bilibili` 首次尝试也一样，先走匿名/指纹模式，不要预设“必须先登录”。

## Default Action

1. 读取 `skill/vivid-operator/state/skill_state.json`
2. 定位 Vivid 仓库
3. 如有必要执行 `doctor`
4. 用已知 `source` 执行 `quickread`
5. 读取结果并按输出契约回复

Windows:

```powershell
./skill/vivid-operator/scripts/vivid_operator.ps1 -Action quickread -Source "<source>"
```

Linux/macOS:

```bash
./skill/vivid-operator/scripts/vivid_operator.sh -Action quickread -Source "<source>"
```

## Only Ask When Blocked

只有下面这些情况才允许提问，而且一次只问一个最短问题：

- 找不到 Vivid 仓库路径
- 本地媒体路径不存在
- 用户明确要求云端，但缺 `cloud_base_url`
- 用户一次发了多个来源，但没有说明“全部处理”还是“选一个”

如果用户明确说“都看一下”“都总结下”，就按多个来源逐个执行，不要再问是否批量。

## Output Contract

### 成功时

必须按固定顺序返回 6 段，不要压成一段 prose：

1. 标题
2. 内容概览
3. 核心观点
4. 争议点
5. 行动建议
6. 俏皮点评

可选补充：

- 平台
- 转录方式
- 产物路径

### 失败时

必须返回：

- 失败阶段
- 最关键的错误
- 如果存在，给出精简版 `error_summary`
- 1 到 2 个下一步动作

不要：

- 只说“失败了”
- 只贴原始 JSON
- 一次给出一长串排查方向

### 信息不完整但已执行时

仍然必须返回完整 6 段；缺失的部分用明确占位补齐，例如：

- “未提取到明显争议点”
- “当前摘要未给出可执行建议”

不要因为字段缺失就省略该段。

## Bilibili Rule

- `Bilibili` 仍然走“直接下载媒体 -> Whisper / OCR”链路，不恢复官方字幕优先
- helper 现在支持三层策略：完整 `Cookie` 优先，`SESSDATA` 兼容回退，无凭据时自动补匿名请求画像
- Vivid 支持二维码登录：`bili-auth-qrcode` 生成二维码，`bili-auth-poll -QrcodeKey ...` 轮询并持久化登录态，`bili-auth-status` 校验，`bili-auth-logout` 注销并清除本地 secret
- 匿名请求画像包括 `_uuid`、`b_lsid`、`b_nut`、`buvid3`、`buvid4`、`buvid_fp`，由 helper 按 `Bili23` 规则维护；即使完整 `Cookie` 里带了这些旧值，helper 也会刷新覆盖
- helper 会先写入基础登录态，再获取/刷新匿名画像、尽量获取 `bili_ticket` 与调用 `ExClimbWuzhi` 激活
- `bili_ticket` / `ExClimbWuzhi` 获取失败不等于需要登录；除非错误明确指向登录失败，不要因此要求用户提供 `Cookie`
- 支持常见 `Bilibili` 链接形态：`BV`、`av`、`ep`、`ss`、`md`
- 在首次尝试前，不要要求用户先提供 `Cookie / SESSDATA`
- 只有当错误明确指向 `-101`、`账号未登录`、`login required` 之类的登录失败时，才引导用户刷新凭据
- 发生登录失败时，优先让用户走二维码登录；不方便扫码时再要 `Bilibili` 完整 `Cookie`，使用 `-BiliCookie` / `--bili-cookie` 或 `VIVID_BILI_COOKIE`
- 用户通过 `-BiliCookie` / `--bili-cookie` 或 Web 表单显式提供完整 `Cookie` 时，Vivid 应用层会持久化到项目目录 `configs/secrets/bilibili_cookie.json`；该文件不属于 skill 状态，不要复制、展示或写入对话
- 只有拿不到完整 `Cookie` 时，才兼容 `-Sessdata` / `--sessdata` 或 `BILI_SESSDATA`
- `-NoSessdata` / `--no-sessdata` 只在用户明确要禁用回退时才提，不要默认建议
- 不要让用户把 `Cookie / SESSDATA` 写入 `skill_state.json`、文档、prompt 或日志；也不要在输出中回显持久化 Cookie 文件内容

如果用户问“为什么完整 Cookie 优先”，解释需要的不只是 `SESSDATA`，完整 `Cookie` 更容易覆盖 `bili_jct`、`DedeUserID` 等登录态，helper 也会自动补 `buvid_fp`、`bili_ticket`、`ExClimbWuzhi` 等匿名请求增强字段。

## Pressure Examples

| Input | Correct Action | Wrong Action |
|---|---|---|
| `https://www.bilibili.com/video/BV...` | 直接执行 `quickread` | 问“你想让我做什么” |
| `看看这个 https://v.douyin.com/...` | 直接执行 `quickread` | 问“要不要总结” |
| `D:\\clips\\demo.mp4` | 直接执行 `quickread` | 问 transcript 还是 summary |
| `这个视频讲啥 https://youtu.be/...` | 直接执行 `quickread` | 把它当成普通聊天 |
| 上一轮已给链接，这一轮说“继续” | 复用已有 `source` 执行 | 重新盘问视频来源 |
| `用瞬知看下这个 /path/to/demo.wav` | 直接执行 `quickread` | 先解释功能 |
| `走云端处理这个 https://...` 且没配置云端地址 | 只问远端 API 地址和产物策略 | 先追问一堆可选参数 |
| `Bilibili` 返回 `-101: 账号未登录` | 先引导二维码登录并校验；不方便扫码时再要完整 `Cookie`，最后才兼容 `SESSDATA` | 继续空跑，或让用户把凭据写进状态文件 |
| 两个链接 + “都看一下” | 逐个执行并分别返回结果 | 问“你到底想处理哪个” |
| 两个链接但没说是否都处理 | 问“都处理还是只处理一个？” | 擅自忽略其中一个 |

## References

- `references/reference.md` — 参数、返回字段、状态文件和默认值优先级
