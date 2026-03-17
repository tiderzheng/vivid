# Vision Configs

这里是 `Vivid` 内部 `vision` 子系统的第一轮配置落点。

当前阶段用途：

- 给 `Vivid` 自己的内部 OCR 执行链提供统一配置目录
- 为兼容回退到 `Eyes API` 时提供可迁移的配置语义

当前仓库默认已包含：

- 本地 OpenAI 兼容视觉模型预设
- `SiliconFlow PaddleOCR-VL` 云端预设

建议优先在这里维护：

- OCR provider endpoint
- model
- prompt
- timeout
- `api_key_env`

建议把可提交到仓库的内容限制为：

- 示例配置
- 默认 Prompt

不要把真实 API Key 提交到这里。
