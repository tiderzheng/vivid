# Vivid Requirements

这份文档定义的是 `Vivid` 这个项目当前要解决什么问题、提供什么能力，以及后续往哪里收口。

它不是实现细节文档，而是项目范围说明。

## 1. 项目定位

`Vivid` 是一个统一的视频速看项目。

它要解决的问题是：

- 给用户一个统一入口
- 给 AI agent 一个统一 skill
- 把“下载、取字幕、转录、OCR、摘要、落盘”这些步骤串成一条稳定工作流

当前项目定位可以概括为：

- `Vivid` = 主程序
- `vivid-operator` = 调用 `Vivid` 的统一 skill

## 2. 目标用户

项目主要面向三类用户：

- 想把视频快速转成文字和摘要的普通用户
- 想批量整理视频资料的高级用户
- 想让 AI agent 稳定调用视频速看流程的开发者

## 3. 核心输入输出

### 输入

项目至少要支持：

- `Bilibili` 视频链接
- `Douyin` 视频链接
- 其他常见视频站点链接
- 本地视频文件
- 本地音频文件

### 输出

项目至少要稳定产出：

- `quickread.md`
- `transcript.txt`
- `summary.md`
- `summary.json`
- `metadata.json`

输出目录应支持：

- 默认输出目录
- 指定本次输出目录
- Web UI 中设置默认目录

## 4. 核心工作流要求

项目必须能完成下面这条主链路。

### 1. 来源识别

根据用户输入识别来源：

- 本地
- `Bilibili`
- `Douyin`
- 其他站点

### 2. 媒体或字幕获取

不同平台要走固定策略：

- `Bilibili`
  - 优先尝试直接拿字幕
  - 拿不到字幕再下载媒体
  - 下载器固定使用 `bili-downloader-agent`
- `Douyin`
  - 下载器固定使用 `douyin-download-1.2.0`
- `Generic`
  - 使用 `yt_dlp` 兜底
- `Local`
  - 直接使用本地文件

### 3. 文本获取

项目必须能把媒体转成文本。

默认优先路径：

- 使用内部 `Whisper` 做音频转录

当视频字幕无法通过音频路径稳定得到时：

- 允许走 OCR 路线

支持的采集模式：

- `auto`
- `prefer_ocr`
- `force_ocr`

### 4. OCR 能力

项目必须支持视频 OCR。

要求：

- 本地抽帧
- OpenAI 兼容视觉 API
- 可配置模型、API、Prompt、timeout、采样间隔

当前 `opencv` 是这条链路的本地抽帧依赖。

### 5. 摘要能力

项目必须支持摘要生成。

要求：

- 一句话总结
- 详细摘要
- 关键要点
- 至少有主备模型策略
- 当外部模型不可用时有兜底逻辑

## 5. 用户入口要求

项目必须同时提供三种入口。

### 1. CLI

适合：

- 本地直接运行
- 脚本调用

### 2. PowerShell 控制面

适合：

- Windows 环境
- Agent 稳定调用
- JSON 输出

### 3. Web UI

适合：

- 普通用户
- 文件拖拽上传
- 参数可视化设置

Web UI 至少要支持：

- 本地文件上传
- 视频链接输入
- Whisper 模型选择
- 输出目录设置
- OCR API 配置
- 任务历史
- 任务日志
- 结果查看

## 6. skill 要求

项目必须提供一个统一 skill：

- `vivid-operator`

要求：

- Agent 侧优先只加载这一个 skill
- skill 不负责重写业务逻辑
- skill 只负责调用 `Vivid` 稳定控制面

### skill 背后的下载要求

虽然 agent 只需要一个 skill，但下载链路必须遵守：

- `Bilibili -> bili-downloader-agent`
- `Douyin -> douyin-download-1.2.0`

这两个是运行时 helper，不是给 agent 再单独加载的 skill。

## 7. 配置要求

项目必须尽量把配置收口到 `Vivid` 内部。

至少包括：

- 输出目录
- `ffmpeg`
- 下载器路径
- 转录模型和策略
- OCR API 和 Prompt
- 摘要模型

### 摘要配置

应由 `Vivid` 自己管理。

### OCR 配置

应优先由 `Vivid` 自己管理，并支持 OpenAI 兼容格式。

### 转录配置

应优先由 `Vivid` 自己管理。

## 8. 回退能力要求

当前版本允许保留兼容回退，但不应让回退路径成为默认解释方式。

允许存在：

- `Ears4` 回退
- `Eyes` 回退

但项目对外口径应始终是：

- 主路径在 `Vivid`
- 回退只是兼容手段

## 9. 依赖要求

必须依赖：

- `python`
- `ffmpeg`
- `node`
- `requests`
- `openai-whisper`

条件依赖：

- `opencv`
  - 用于内部 OCR
  - 缺失时允许自动安装
- `yt_dlp`
  - 仅通用站点兜底

## 10. 自动安装要求

当前至少要满足：

- `opencv` 缺失时可自动尝试安装

当前默认行为：

- 自动执行 `pip install opencv-python -i https://mirrors.aliyun.com/pypi/simple/`

并允许通过环境变量覆盖镜像地址。

## 11. 质量要求

项目至少要做到：

- 主流程可重复运行
- 控制面输出稳定 JSON
- Web UI 可用
- 文档可直接指导用户上手
- 自动化测试覆盖关键流程

## 12. 当前阶段与后续方向

### 当前阶段

当前项目已经具备：

- 主工作流
- 单 skill 控制面
- Web UI
- 内部 Whisper
- 内部 OCR
- 摘要能力
- 标准产物输出

### 后续方向

后续方向不是再拆更多项目，而是继续收口：

- 进一步把转录能力统一到 `Vivid`
- 进一步把 OCR 能力统一到 `Vivid`
- 继续简化用户理解成本

