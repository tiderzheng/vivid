# API Reference

主脚本：

`D:\ai\quicker_video\Vivid\scripts\vivid_tool.ps1`

## `paths`

作用：

- 返回项目路径
- 返回脚本路径
- 返回 skill 路径
- 返回下载 helper 路径
- 返回配置路径

## `doctor`

作用：

- 检查运行环境
- 检查 helper 路径
- 检查关键配置文件
- 缺少 `opencv` 时自动尝试安装

## `quickread`

作用：

- 跑完整速看流程

必要参数：

- `-Source`

常用参数：

- `-ProjectName`
- `-DataDir`
- `-Platform`
- `-Model`
- `-PreferOcr`
- `-ForceOcr`
- `-TranscriptionBackend`
- `-VisionBackend`
- `-NoKeepFiles`

## `web-ui`

作用：

- 启动本地 Web UI

## 返回值

所有 action 都返回 JSON。

重点字段通常包括：

- `ok`
- `exit_code`
- `result`
- `raw_output`
- `error`

