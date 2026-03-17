import json
from dataclasses import replace
from pathlib import Path

from app.models.runtime import RuntimeOptions
from app.models.summary import SummaryResult
from app.models.transcript import TranscriptResult
from app.pipeline.orchestrator import run_quickread
from app.services.run_state import load_run_state


def test_orchestrator_smoke(tmp_path, monkeypatch):
    def fake_acquire(_options, _platform, workdir):
        media_path = workdir / "media" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text("x", encoding="utf-8")
        return TranscriptResult(
            text="这是测试转录。",
            acquisition_method="fake",
            media_path=media_path,
        )

    def fake_summarize(_options, _transcript):
        return SummaryResult(
            one_line="一句话",
            detailed="详细摘要",
            key_points=["要点1", "要点2"],
            provider="test",
        )

    monkeypatch.setattr("app.pipeline.orchestrator.acquire_transcript", fake_acquire)
    monkeypatch.setattr("app.pipeline.orchestrator.summarize_transcript", fake_summarize)

    result = run_quickread(
        RuntimeOptions(
            source="https://example.com/video",
            project_name="smoke",
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
            bili_script=Path("D:/fake/bili.py"),
            douyin_script=Path("D:/fake/douyin.js"),
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
            transcription_presets_path=tmp_path / "presets.json",
            keep_files=True,
        )
    )
    assert result.artifacts.quickread_markdown.exists()


def test_orchestrator_can_resume_from_summarize_checkpoint(tmp_path, monkeypatch):
    counters = {"acquire": 0, "summarize": 0}

    def fake_acquire(_options, _platform, workdir, **_kwargs):
        counters["acquire"] += 1
        media_path = workdir / "media" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text("x", encoding="utf-8")
        return TranscriptResult(
            text="这是测试转录。",
            acquisition_method="fake",
            media_path=media_path,
        )

    def fake_summarize(options, _transcript, **_kwargs):
        counters["summarize"] += 1
        if not options.resume_stage:
            raise RuntimeError("summary failed")
        return SummaryResult(
            one_line="一句话",
            detailed="详细摘要",
            key_points=["要点1"],
            provider="test",
        )

    monkeypatch.setattr("app.pipeline.orchestrator.acquire_transcript", fake_acquire)
    monkeypatch.setattr("app.pipeline.orchestrator.summarize_transcript", fake_summarize)

    base_options = RuntimeOptions(
        source="https://example.com/video",
        project_name="resume-smoke",
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
        bili_script=Path("D:/fake/bili.py"),
        douyin_script=Path("D:/fake/douyin.js"),
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
        transcription_presets_path=tmp_path / "presets.json",
        keep_files=True,
    )

    try:
        run_quickread(base_options)
    except RuntimeError as exc:
        assert str(exc) == "summary failed"
    else:
        raise AssertionError("expected summary failure")

    workdir = tmp_path / "resume-smoke"
    checkpoint = load_run_state(workdir)
    assert checkpoint["transcript"]["text"] == "这是测试转录。"
    assert checkpoint["last_completed_stage"] == "title"

    resumed = run_quickread(
        replace(
            base_options,
            resume_workdir=workdir,
            resume_stage="summarize",
        )
    )

    assert resumed.summary.provider == "test"
    assert counters["acquire"] == 1
    assert counters["summarize"] == 2
    assert resumed.artifacts.checkpoint_json and resumed.artifacts.checkpoint_json.exists()


def test_orchestrator_metadata_includes_diagnostics_and_failure_chain(tmp_path, monkeypatch):
    def fake_acquire(_options, _platform, workdir, event_callback=None, **_kwargs):
        if event_callback:
            event_callback("subtitle_failed", "字幕提取失败", {"error": "subtitle broken"})
            event_callback("transcription_fallback", "转入转录")
        media_path = workdir / "media" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text("x", encoding="utf-8")
        return TranscriptResult(
            text="这是测试转录。",
            acquisition_method="fake",
            media_path=media_path,
        )

    def fake_summarize(_options, _transcript, **_kwargs):
        return SummaryResult(
            one_line="一句话",
            detailed="详细摘要",
            key_points=["要点1"],
            provider="test",
        )

    monkeypatch.setattr("app.pipeline.orchestrator.acquire_transcript", fake_acquire)
    monkeypatch.setattr("app.pipeline.orchestrator.summarize_transcript", fake_summarize)

    result = run_quickread(
        RuntimeOptions(
            source="https://example.com/video",
            project_name="diag-smoke",
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
            bili_script=Path("D:/fake/bili.py"),
            douyin_script=Path("D:/fake/douyin.js"),
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
            transcription_presets_path=tmp_path / "presets.json",
            keep_files=True,
        )
    )

    metadata = json.loads(result.artifacts.metadata_json.read_text(encoding="utf-8"))
    assert metadata["diagnostics"]
    assert metadata["failure_chain"]
    assert metadata["failure_chain"][0]["stage"] == "subtitle_failed"
    assert metadata["error_summary"]["has_issues"] is True
    assert metadata["error_summary"]["items"]
