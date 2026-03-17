import json

from app.subsystems.transcription import load_transcription_store
from app.subsystems.transcription.models import TranscriptionPreset
from app.subsystems.transcription.store import save_transcription_store


def test_load_transcription_store(tmp_path):
    presets_path = tmp_path / "presets.json"
    presets_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "fast",
                        "name": "fast",
                        "model": "small",
                        "device": "auto",
                        "language": "zh",
                        "task": "transcribe",
                        "extract_audio": True,
                    }
                ],
                "selected_id": "fast",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    store = load_transcription_store(presets_path)
    assert store.selected_preset_id == "fast"
    assert store.get_preset(None) is not None


def test_save_and_select_transcription_store(tmp_path):
    presets_path = tmp_path / "presets.json"
    store = load_transcription_store(presets_path)
    store.upsert_preset(
        TranscriptionPreset(
            id="cpu",
            name="CPU 模式",
            model="base",
            device="cpu",
            language="zh",
            task="transcribe",
            extract_audio=True,
        )
    )
    assert store.select_preset("cpu") is True
    save_transcription_store(store, presets_path)
    reloaded = load_transcription_store(presets_path)
    assert reloaded.selected_preset_id == "cpu"
    assert reloaded.get_preset("cpu") is not None
