# Contributing（瞬知 / Vivid）

感谢你关注 **瞬知**（Vivid）。

## 贡献范围

欢迎以下类型的贡献：

- 修复 bug
- 改进文档
- 增强下载 / 转录 / OCR / 摘要链路
- 增加测试
- 提升脚本与 Skill 的稳定性

## 开始之前

建议先阅读：

- `README.md`
- `docs/安装与依赖.md`
- `docs/配置说明.md`
- `docs/项目目录设计与模块拆分.md`

## 本地开发

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
```

## 提交建议

推荐保持变更小而聚焦：

- 一次只解决一个明确问题
- 避免把“重构 + 新功能 + 样式调整”混在同一提交里
- 优先补充或更新相关文档

推荐提交信息风格：

- `feat(cli): add quickread json flag`
- `fix(adapters): handle empty eyes result`
- `docs(readme): clarify setup steps`

## 代码与文档原则

- 不把真实密钥提交到仓库
- 不把本地产物提交到仓库
- 尽量复用已有模块，不新增重复逻辑
- 外部依赖优先通过适配器接入
- 面向 Agent 的输出尽量保持稳定和结构化

## 测试要求

在提交前至少执行：

```powershell
python -m pytest -q
```

如果你修改了：

- `scripts/`：请手动验证 PowerShell 命令
- `skill/`：请检查说明和脚本是否一致
- `app/adapters/`：请尽量避免把测试强耦合到真实在线服务

## 文档同步

以下场景请同步更新文档：

- 新增环境变量
- 新增脚本参数
- 新增产物文件
- 更改 Skill 调用方式
- 更改外部依赖路径或默认行为

## 尚未确定的事项

以下内容后续会进一步规范：

- 开源许可证
- 版本发布流程
- CI 配置
