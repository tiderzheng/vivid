# Summary Prompts

`prompts.json` 用来配置总结阶段的提示词模板。

- `selected_id`：默认启用的模板 ID
- `system_prompt`：发给总结模型的 system prompt
- `user_prompt_template`：发给总结模型的 user prompt 模板，使用 `{transcript}` 作为逐字稿占位符

可通过以下环境变量覆盖默认配置：

- `VIVID_SUMMARY_PROMPT_ID`
- `VIVID_SUMMARY_SYSTEM_PROMPT`
- `VIVID_SUMMARY_USER_PROMPT`
- `VIVID_SUMMARY_PROMPTS_FILE`
