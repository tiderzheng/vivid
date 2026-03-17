import json

from app.models.runtime import RuntimeOptions
from app.subsystems.vision import build_vision_request_config


def test_build_vision_request_config(tmp_path):
    api_configs_path = tmp_path / "api_configs.json"
    prompts_path = tmp_path / "prompts.json"
    api_configs_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "cfg-1",
                        "name": "cfg",
                        "api_base": "http://localhost:1234",
                        "api_path": "/v1/chat/completions",
                        "model": "file-model",
                        "timeout": 15,
                        "prompt": "file-prompt",
                        "system_prompt": "file-system",
                    }
                ],
                "selected_id": "cfg-1",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    prompts_path.write_text(
        json.dumps(
            [
                {"id": "strict", "name": "严格", "content": "strict-prompt"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    options = RuntimeOptions(
        source="https://example.com/video",
        project_name="vision",
        data_dir=tmp_path,
        output_format="both",
        whisper_model="base",
        forced_platform=None,
        sessdata=None,
        ffmpeg_bin="ffmpeg",
        whisper_root=None,
        ears4_api="http://127.0.0.1:7860",
        eyes_api="http://127.0.0.1:9531",
        language="zh",
        transcription_preset_id=None,
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
        vision_api_config_id="cfg-1",
        vision_backend="auto",
        vision_api_base=None,
        vision_api_path=None,
        vision_api_key="k",
        vision_model=None,
        vision_timeout=None,
        vision_prompt_id="strict",
        vision_prompt=None,
        vision_system_prompt=None,
        vision_sample_ms=900,
        vision_min_duration_ms=1300,
        vision_api_configs_path=api_configs_path,
        vision_prompts_path=prompts_path,
        transcription_presets_path=tmp_path / "presets.json",
        keep_files=True,
    )
    resolved = build_vision_request_config(options)
    assert resolved.api_config_id == "cfg-1"
    assert resolved.api_base == "http://localhost:1234"
    assert resolved.model == "file-model"
    assert resolved.prompt == "strict-prompt"
    assert resolved.sample_ms == 900
    assert resolved.min_duration_ms == 1300
