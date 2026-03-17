# Workflow

这是 `vivid-operator` 的推荐调用顺序。

## 1. 看路径

先执行：

`paths`

目的：

- 确认项目根目录
- 确认默认输出目录
- 确认 `Bilibili` / `Douyin` helper 路径

## 2. 做环境检查

再执行：

`doctor`

重点确认：

- `python`
- `node`
- `ffmpeg`
- `opencv`
- `bili_helper`
- `douyin_helper`

## 3. 跑 quickread

再执行：

`quickread`

如果用户给的是：

- 视频链接
- 本地视频
- 本地音频

都应该优先走这个动作。

## 4. 读取产物

成功后去读：

`data\项目名\artifacts\`

重点文件：

- `quickread.md`
- `transcript.txt`
- `summary.md`
- `metadata.json`

