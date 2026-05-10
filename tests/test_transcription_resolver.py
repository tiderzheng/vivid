import json

from app.models.runtime import RuntimeOptions
from app.subsystems.transcription import build_transcription_request_config
from app.subsystems.transcription.store import load_transcription_store


def test_build_transcription_request_config(tmp_path):
    presets_path = tmp_path / "presets.json"
    presets_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "fast",
                        "name": "fast",
                        "model": "small",
                        "device": "cuda",
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
    options = RuntimeOptions(
        source="https://example.com/video",
        project_name="tx",
        data_dir=tmp_path,
        output_format="both",
        whisper_model="small",
        forced_platform=None,
        ffmpeg_bin="ffmpeg",
        whisper_root=None,
        ears4_api="http://127.0.0.1:7860",
        eyes_api="http://127.0.0.1:9531",
        language="zh",
        transcription_preset_id="fast",
        acquisition_mode="auto",
        transcription_backend="auto",
        transcription_device=None,
        transcription_task=None,
        transcription_extract_audio=None,
        transcription_output_dir=None,
        transcribe_timeout=30,
        ocr_timeout=30,
        llm_max_chars=8000,
        siliconflow_api_key=None,
        dashscope_api_key=None,
        siliconflow_base_url="https://example.com/sf",
        dashscope_base_url="https://example.com/ds",
        siliconflow_model="model-a",
        dashscope_model="model-b",
        bili_script=tmp_path / "bili.py",
        douyin_script=tmp_path / "douyin.js",
        vision_api_config_id=None,
        vision_backend="auto",
        vision_api_base=None,
        vision_api_path=None,
        vision_api_key=None,
        vision_model=None,
        vision_timeout=None,
        vision_prompt_id=None,
        vision_prompt=None,
        vision_system_prompt=None,
        vision_sample_ms=800,
        vision_min_duration_ms=1200,
        vision_api_configs_path=tmp_path / "api_configs.json",
        vision_prompts_path=tmp_path / "prompts.json",
        transcription_presets_path=presets_path,
        keep_files=True,
    )
    resolved = build_transcription_request_config(options)
    assert resolved.model == "small"
    assert resolved.device == "cuda"
    assert resolved.task == "transcribe"
    assert resolved.extract_audio is True


def test_transcription_store_defaults_missing_model_to_large_v3_turbo(tmp_path):
    presets_path = tmp_path / "presets.json"
    presets_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "default",
                        "name": "default",
                    }
                ],
                "selected_id": "default",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    store = load_transcription_store(presets_path)

    assert store.get_preset("default").model == "large-v3-turbo"
