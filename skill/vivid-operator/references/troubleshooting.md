# Troubleshooting

## `python` 不存在

先安装 Python 3.10+。

## `node` 不存在

先安装 Node.js。

抖音下载依赖 `douyin.js`。

## `ffmpeg` 不存在

把 `ffmpeg` 加进 `PATH`，或者设置：

- `VIVID_FFMPEG_BIN`

## `torch` 不存在

内部 `Whisper` 转录依赖 `torch`。

如果 `doctor` 里 `torch=false`：

- CPU 环境通常可以先执行 `pip install -r requirements.txt`
- GPU / CUDA 环境建议先按官方 `PyTorch` 说明安装匹配版本的 `torch`
- 然后再重新执行 `doctor`

## `opencv` 缺失

程序会自动尝试执行：

`pip install opencv-python -i https://mirrors.aliyun.com/pypi/simple/`

## `bili-downloader-agent` 路径不存在

检查：

- `VIVID_BILI_SCRIPT`

## `douyin-download-1.2.0` 路径不存在

检查：

- `VIVID_DOUYIN_SCRIPT`

## Bilibili 受限内容失败

检查：

- `BILI_SESSDATA`

## `quickread.result = null`

说明 CLI 没有返回可解析 JSON。

优先看：

- `raw_output`
- `error`

## `Ears4` 或 `Eyes` 不可用

检查：

- `EARS4_API`
- `EYES_API`

但要先确认你是否真的需要回退模式。
