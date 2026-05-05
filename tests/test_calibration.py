from __future__ import annotations

import json
from pathlib import Path

from app.adapters.llm import fallback_calibration
from app.models.calibration import CalibrationResult
from app.models.runtime import RuntimeOptions
from app.pipeline.calibration import calibrate_transcript
from app.subsystems.summary.resolver import build_calibration_prompt_configs


def test_calibration_result_model():
    result = CalibrationResult(cn_text="中文文本", en_text="English text", provider="test")
    assert result.cn_text == "中文文本"
    assert result.en_text == "English text"
    assert result.provider == "test"
    payload = result.to_payload()
    assert payload["cn_text"] == "中文文本"
    assert payload["en_text"] == "English text"
    assert payload["provider"] == "test"


def test_calibration_result_default_provider():
    result = CalibrationResult(cn_text="a", en_text="b")
    assert result.provider == "scaffold"


def test_fallback_calibration():
    result = fallback_calibration("test transcript content")
    assert result.provider == "rule-based fallback"
    assert result.cn_text == "test transcript content"
    assert "Calibration unavailable" in result.en_text
    assert "test transcript content" in result.en_text


def test_build_calibration_prompt_configs_from_store(tmp_path):
    prompts_path = tmp_path / "prompts.json"
    prompts_path.parent.mkdir(exist_ok=True)
    prompts_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "cn",
                        "name": "中文校准",
                        "system_prompt": "cn system",
                        "user_prompt_template": "cn user {transcript}",
                    },
                    {
                        "id": "en",
                        "name": "英文校准",
                        "system_prompt": "en system",
                        "user_prompt_template": "en user {transcript}",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    options = _make_options(tmp_path, calibration_prompts_path=prompts_path)
    cn_config, en_config = build_calibration_prompt_configs(options)
    assert cn_config.system_prompt == "cn system"
    assert cn_config.user_prompt_template == "cn user {transcript}"
    assert en_config.system_prompt == "en system"
    assert en_config.user_prompt_template == "en user {transcript}"


def test_build_calibration_prompt_configs_prefers_runtime_overrides(tmp_path):
    prompts_path = tmp_path / "prompts.json"
    prompts_path.parent.mkdir(exist_ok=True)
    prompts_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "cn",
                        "name": "中文校准",
                        "system_prompt": "cn store",
                        "user_prompt_template": "cn store template",
                    },
                    {
                        "id": "en",
                        "name": "英文校准",
                        "system_prompt": "en store",
                        "user_prompt_template": "en store template",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    options = _make_options(
        tmp_path,
        calibration_system_prompt="overridden system",
        calibration_user_prompt="overridden user",
        calibration_prompts_path=prompts_path,
    )
    cn_config, en_config = build_calibration_prompt_configs(options)
    assert cn_config.system_prompt == "overridden system"
    assert cn_config.user_prompt_template == "overridden user"
    assert en_config.system_prompt == "overridden system"
    assert en_config.user_prompt_template == "overridden user"


def test_calibrate_transcript_two_calls(tmp_path, monkeypatch):
    call_count = 0

    class FakeResponse:
        def __init__(self, text):
            self._text = text

        def raise_for_status(self):
            pass

        def json(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"choices": [{"message": {"content": "这是校准后的中文文章。"}}]}
            return {"choices": [{"message": {"content": "This is the calibrated English article."}}]}

    requests_made: list[dict] = []

    def fake_post(url, **kwargs):
        requests_made.append({"url": url, **kwargs})
        if len(requests_made) == 1:
            return FakeResponse("cn")
        return FakeResponse("en")

    monkeypatch.setattr("requests.post", fake_post)
    prompts_path = tmp_path / "prompts.json"
    prompts_path.parent.mkdir(exist_ok=True)
    prompts_path.write_text(
        json.dumps(
            {
                "items": [
                    {"id": "cn", "name": "cn", "system_prompt": "cn", "user_prompt_template": "cn {transcript}"},
                    {"id": "en", "name": "en", "system_prompt": "en", "user_prompt_template": "en {transcript}"},
                ],
            }
        ),
        encoding="utf-8",
    )
    options = _make_options(tmp_path, calibration_prompts_path=prompts_path)
    result = calibrate_transcript(options, "原始逐字稿内容")
    assert result.cn_text == "这是校准后的中文文章。"
    assert result.en_text == "This is the calibrated English article."
    assert result.provider == "SiliconFlow"
    assert len(requests_made) == 2


def test_calibrate_transcript_resume_cn_skips_first_call(tmp_path, monkeypatch):
    requests_made: list[dict] = []

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "English from second call."}}]}

    def fake_post(url, **kwargs):
        requests_made.append({"url": url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr("requests.post", fake_post)
    prompts_path = tmp_path / "prompts.json"
    prompts_path.parent.mkdir(exist_ok=True)
    prompts_path.write_text(
        json.dumps(
            {
                "items": [
                    {"id": "cn", "name": "cn", "system_prompt": "cn", "user_prompt_template": "cn {transcript}"},
                    {"id": "en", "name": "en", "system_prompt": "en", "user_prompt_template": "en {transcript}"},
                ],
            }
        ),
        encoding="utf-8",
    )
    options = _make_options(tmp_path, calibration_prompts_path=prompts_path)
    result = calibrate_transcript(options, "原始逐字稿内容", resume_cn_text="已恢复的中文")
    assert result.cn_text == "已恢复的中文"
    assert result.en_text == "English from second call."
    assert len(requests_made) == 1


def _make_options(tmp_path, **overrides):
    defaults = dict(
        source="test",
        project_name=None,
        data_dir=tmp_path,
        output_format="both",
        whisper_model="base",
        forced_platform=None,
        ffmpeg_bin="ffmpeg",
        whisper_root=None,
        ears4_api="http://localhost",
        eyes_api="http://localhost",
        language="zh",
        transcription_preset_id=None,
        acquisition_mode="auto",
        transcription_backend="auto",
        transcription_device=None,
        transcription_task=None,
        transcription_extract_audio=None,
        transcription_output_dir=None,
        transcribe_timeout=1800,
        ocr_timeout=1800,
        llm_max_chars=8000,
        siliconflow_api_key="test-key",
        dashscope_api_key=None,
        siliconflow_base_url="https://api.example.com",
        dashscope_base_url="https://api.example.com",
        siliconflow_model="test-model",
        dashscope_model="test-model",
        bili_script=None,
        douyin_script=None,
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
        vision_api_configs_path=tmp_path / "vision_configs.json",
        vision_prompts_path=tmp_path / "vision_prompts.json",
        transcription_presets_path=tmp_path / "transcription.json",
        keep_files=True,
        calibration_prompt_id=None,
        calibration_system_prompt=None,
        calibration_user_prompt=None,
        calibration_prompts_path=None,
    )
    defaults.update(overrides)
    return RuntimeOptions(**defaults)