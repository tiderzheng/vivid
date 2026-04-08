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

不保存 Cookie、Token、API Key。

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

- 当前项目已移除 `Bilibili` 的 `SESSDATA` 和官方字幕优先逻辑
- `Bilibili` 现在和 `Douyin` 一样：直接下载媒体，再由 `Whisper / OCR` 处理
- agent 不应要求用户提供 `SESSDATA`
- agent 不应建议 `--sessdata`、`--no-sessdata`

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
