from __future__ import annotations

from .models import TranscriptionRequestConfig
from .store import load_transcription_store
from ...models.runtime import RuntimeOptions


def build_transcription_request_config(options: RuntimeOptions) -> TranscriptionRequestConfig:
    store = load_transcription_store(options.transcription_presets_path)
    preset = store.get_preset(options.transcription_preset_id)
    return TranscriptionRequestConfig(
        model=options.whisper_model or (preset.model if preset else "base"),
        device=options.transcription_device or (preset.device if preset else "auto"),
        language=options.language or (preset.language if preset else "zh"),
        task=options.transcription_task or (preset.task if preset else "transcribe"),
        extract_audio=options.transcription_extract_audio if options.transcription_extract_audio is not None else (preset.extract_audio if preset else True),
        output_dir=options.transcription_output_dir,
    )
