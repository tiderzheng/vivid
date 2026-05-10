from __future__ import annotations

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3-turbo", "large"]
PARAFORMER_MODELS = ["paraformer-zh"]
TRANSCRIPTION_MODELS = [*WHISPER_MODELS, *PARAFORMER_MODELS]

TRANSCRIPTION_MODEL_INFO = {
    "tiny": {"size": "~39 MB", "speed": "最快", "accuracy": "较低", "best_for": "快速测试"},
    "base": {"size": "~74 MB", "speed": "快", "accuracy": "一般", "best_for": "日常使用"},
    "small": {"size": "~244 MB", "speed": "中等", "accuracy": "较好", "best_for": "平衡选择"},
    "medium": {"size": "~769 MB", "speed": "较慢", "accuracy": "好", "best_for": "高质量需求"},
    "large-v3-turbo": {"size": "~1.5 GB", "speed": "快", "accuracy": "很好", "best_for": "默认推荐"},
    "large": {"size": "~1.5 GB", "speed": "最慢", "accuracy": "最好", "best_for": "专业场景"},
    "paraformer-zh": {"size": "~1.1 GB", "speed": "快", "accuracy": "中文优化", "best_for": "中文语音"},
}
