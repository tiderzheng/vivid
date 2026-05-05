from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.exceptions import VividError
from app.models.runtime import RuntimeOptions
from app.models.summary import SummaryResult
from app.models.transcript import TranscriptResult
from app.pipeline.orchestrator import run_quickread
from app.services.quickread_lock import QuickreadLock


def _make_options(tmp_path: Path) -> RuntimeOptions:
    return RuntimeOptions(
        source="https://example.com/video",
        project_name="locked",
        data_dir=tmp_path,
        output_format="both",
        whisper_model="base",
        forced_platform=None,
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


def test_run_quickread_refuses_to_start_when_global_lock_is_held(tmp_path, monkeypatch):
    options = _make_options(tmp_path)
    lock_path = tmp_path / ".vivid" / "quickread.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(
        f'{{"pid": {os.getpid()}, "source": "https://example.com/other"}}\n',
        encoding="utf-8",
    )

    def fail_acquire(*_args, **_kwargs):
        raise AssertionError("acquire_transcript should not run while the global lock is held")

    monkeypatch.setattr("app.pipeline.orchestrator.acquire_transcript", fail_acquire)

    with pytest.raises(VividError) as exc_info:
        run_quickread(options)

    assert "Another Vivid quickread task is already running" in str(exc_info.value)
    assert "quickread.lock" in str(exc_info.value)


def test_run_quickread_removes_dead_pid_lock_without_waiting_for_stale_timeout(tmp_path, monkeypatch):
    options = _make_options(tmp_path)
    lock_path = tmp_path / ".vivid" / "quickread.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(
        '{"pid": 99999999, "source": "https://example.com/dead", "started_at": "2099-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )

    def fake_acquire(_options, _platform, workdir, **_kwargs):
        media_path = workdir / "media" / "demo.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text("x", encoding="utf-8")
        return TranscriptResult(text="ok", acquisition_method="fake", media_path=media_path)

    def fake_summarize(_options, _transcript, **_kwargs):
        return SummaryResult(one_line="一句话", detailed="详细", key_points=["a"], provider="test")

    monkeypatch.setattr("app.pipeline.orchestrator.acquire_transcript", fake_acquire)
    monkeypatch.setattr("app.pipeline.orchestrator.summarize_transcript", fake_summarize)

    result = run_quickread(options)

    assert result.summary.provider == "test"
    assert not lock_path.exists()


def test_quickread_lock_does_not_remove_replaced_lock_on_exit(tmp_path):
    data_dir = tmp_path / "data"
    lock_path = data_dir / ".vivid" / "quickread.lock"
    with QuickreadLock(data_dir, "first") as lock:
        assert lock_path.exists()
        lock_path.unlink()
        lock_path.write_text('{"pid": 12345, "source": "second", "token": "other"}\n', encoding="utf-8")

    assert lock_path.exists()
    assert "second" in lock_path.read_text(encoding="utf-8")
