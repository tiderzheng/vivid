import json

from app.models.runtime import RuntimeOptions
from app.subsystems.summary import build_summary_prompt_config
from app.subsystems.summary.resolver import build_summary_provider_configs


def test_build_summary_prompt_config_from_store(tmp_path):
    prompts_path = tmp_path / "summary-prompts.json"
    prompts_path.write_text(
        json.dumps(
            {
                "selected_id": "brief",
                "items": [
                    {
                        "id": "brief",
                        "name": "简洁",
                        "system_prompt": "system-brief",
                        "user_prompt_template": "brief:\n{transcript}",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    options = RuntimeOptions(
        source="https://example.com/video",
        project_name="summary",
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
        vision_sample_ms=900,
        vision_min_duration_ms=1300,
        vision_api_configs_path=tmp_path / "api-configs.json",
        vision_prompts_path=tmp_path / "vision-prompts.json",
        transcription_presets_path=tmp_path / "presets.json",
        keep_files=True,
        summary_prompts_path=prompts_path,
    )

    resolved = build_summary_prompt_config(options)

    assert resolved.prompt_id == "brief"
    assert resolved.system_prompt == "system-brief"
    assert resolved.user_prompt_template == "brief:\n{transcript}"


def test_build_summary_prompt_config_prefers_runtime_overrides(tmp_path):
    prompts_path = tmp_path / "summary-prompts.json"
    prompts_path.write_text(
        json.dumps(
            {
                "selected_id": "brief",
                "items": [
                    {
                        "id": "brief",
                        "name": "简洁",
                        "system_prompt": "system-brief",
                        "user_prompt_template": "brief:\n{transcript}",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    options = RuntimeOptions(
        source="https://example.com/video",
        project_name="summary",
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
        vision_sample_ms=900,
        vision_min_duration_ms=1300,
        vision_api_configs_path=tmp_path / "api-configs.json",
        vision_prompts_path=tmp_path / "vision-prompts.json",
        transcription_presets_path=tmp_path / "presets.json",
        keep_files=True,
        summary_prompt_id="brief",
        summary_system_prompt="runtime-system",
        summary_user_prompt="runtime:\n{transcript}",
        summary_prompts_path=prompts_path,
    )

    resolved = build_summary_prompt_config(options)

    assert resolved.prompt_id == "brief"
    assert resolved.system_prompt == "runtime-system"
    assert resolved.user_prompt_template == "runtime:\n{transcript}"


def test_build_summary_provider_configs_from_store(tmp_path, monkeypatch):
    prompts_path = tmp_path / "summary-prompts.json"
    prompts_path.write_text('{"selected_id":"default","items":[]}', encoding="utf-8")
    providers_path = tmp_path / "summary-providers.json"
    providers_path.write_text(
        json.dumps(
            {
                "selected_id": "custom",
                "items": [
                    {
                        "id": "custom",
                        "name": "Custom OpenAI",
                        "base_url": "https://example.com/v1/chat/completions",
                        "model": "gpt-4.1-mini",
                        "api_key_env": "CUSTOM_API_KEY",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CUSTOM_API_KEY", "sk-custom")
    options = RuntimeOptions(
        source="https://example.com/video",
        project_name="summary",
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
        vision_sample_ms=900,
        vision_min_duration_ms=1300,
        vision_api_configs_path=tmp_path / "api-configs.json",
        vision_prompts_path=tmp_path / "vision-prompts.json",
        transcription_presets_path=tmp_path / "presets.json",
        keep_files=True,
        summary_prompts_path=prompts_path,
        summary_providers_path=providers_path,
    )

    resolved = build_summary_provider_configs(options)

    assert len(resolved) == 1
    assert resolved[0].provider_id == "custom"
    assert resolved[0].provider_name == "Custom OpenAI"
    assert resolved[0].base_url == "https://example.com/v1/chat/completions"
    assert resolved[0].model == "gpt-4.1-mini"
    assert resolved[0].api_key == "sk-custom"


def test_build_summary_provider_configs_falls_back_to_legacy_settings(tmp_path):
    options = RuntimeOptions(
        source="https://example.com/video",
        project_name="summary",
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
        siliconflow_api_key="sk-sf",
        dashscope_api_key="sk-ds",
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
        vision_sample_ms=900,
        vision_min_duration_ms=1300,
        vision_api_configs_path=tmp_path / "api-configs.json",
        vision_prompts_path=tmp_path / "vision-prompts.json",
        transcription_presets_path=tmp_path / "presets.json",
        keep_files=True,
    )

    resolved = build_summary_provider_configs(options)

    assert [item.provider_id for item in resolved] == ["siliconflow", "dashscope"]
    assert resolved[0].api_key == "sk-sf"
    assert resolved[1].api_key == "sk-ds"
