from pathlib import Path

from app.adapters.ears4 import Ears4Response
from app.models.runtime import RuntimeOptions
from app.pipeline.acquisition import acquire_transcript
from app.subsystems.transcription.engine import InternalTranscriptionResult
from app.subsystems.vision import HardSubtitleProbeResult


def _build_options(tmp_path, backend: str = "auto", acquisition_mode: str = "auto") -> RuntimeOptions:
    return RuntimeOptions(
        source=str(tmp_path / "input.mp4"),
        project_name="case",
        data_dir=tmp_path,
        output_format="both",
        whisper_model="base",
        forced_platform="local",
        ffmpeg_bin="ffmpeg",
        whisper_root=None,
        ears4_api="http://127.0.0.1:7860",
        eyes_api="http://127.0.0.1:9531",
        language="zh",
        transcription_preset_id=None,
        acquisition_mode=acquisition_mode,
        transcription_backend=backend,
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
        transcription_presets_path=tmp_path / "presets.json",
        keep_files=True,
    )


def test_acquire_transcript_prefers_internal_engine(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    audio_path = workdir / "media" / "audio" / "input.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_text("wav", encoding="utf-8")

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: InternalTranscriptionResult(
            transcript="内部转录成功",
            audio_path=audio_path,
            runtime_device="cpu",
        ),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.Ears4Adapter.transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call ears4")),
    )

    result = acquire_transcript(_build_options(tmp_path, backend="auto"), "local", workdir)
    assert result.text == "内部转录成功"
    assert result.acquisition_method == "Internal Whisper base"


def test_acquire_transcript_falls_back_to_ears4_in_auto_mode(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("internal failed")),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.Ears4Adapter.transcribe",
        lambda *_args, **_kwargs: Ears4Response(transcript="ears4 ok", audio_path=None),
    )

    result = acquire_transcript(_build_options(tmp_path, backend="auto"), "local", workdir)
    assert result.text == "ears4 ok"
    assert result.acquisition_method == "Ears4 Whisper base"


def test_acquire_transcript_uses_internal_ocr_fallback(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="internal")

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("internal failed")),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalVisionEngine.extract_text",
        lambda *_args, **_kwargs: type("Result", (), {"transcript": "ocr ok"})(),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.EyesAdapter.extract_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call eyes")),
    )

    result = acquire_transcript(options, "local", workdir)
    assert result.text == "ocr ok"
    assert result.acquisition_method == "Internal OCR fallback"


def test_acquire_transcript_prefers_ocr_when_requested(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="prefer_ocr")

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalVisionEngine.extract_text",
        lambda *_args, **_kwargs: type("Result", (), {"transcript": "ocr first"})(),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not transcribe first")),
    )

    result = acquire_transcript(options, "local", workdir)
    assert result.text == "ocr first"
    assert result.acquisition_method == "Preferred OCR"


def test_acquire_transcript_forces_ocr(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="force_ocr")

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalVisionEngine.extract_text",
        lambda *_args, **_kwargs: type("Result", (), {"transcript": "ocr only"})(),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not transcribe in force_ocr")),
    )

    result = acquire_transcript(options, "local", workdir)
    assert result.text == "ocr only"
    assert result.acquisition_method == "Forced OCR"


def test_acquire_transcript_force_ocr_rejects_audio(tmp_path, monkeypatch):
    media_path = tmp_path / "input.wav"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="force_ocr")
    options.source = str(media_path)

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)

    try:
        acquire_transcript(options, "local", workdir)
    except Exception as exc:  # noqa: BLE001
        assert "force_ocr mode requires a video input" in str(exc)
    else:
        raise AssertionError("force_ocr should reject non-video input")


def test_acquire_transcript_smart_prefers_ocr_when_hard_subtitles_detected(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="smart")

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.detect_hard_subtitles",
        lambda *_args, **_kwargs: HardSubtitleProbeResult(True, 6, 4, 0.667),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalVisionEngine.extract_text",
        lambda *_args, **_kwargs: type("Result", (), {"transcript": "smart ocr"})(),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not transcribe first in smart OCR path")),
    )

    result = acquire_transcript(options, "local", workdir)
    assert result.text == "smart ocr"
    assert result.acquisition_method == "Smart OCR"


def test_acquire_transcript_smart_prefers_transcription_when_no_hard_subtitles(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="smart")
    audio_path = workdir / "media" / "audio" / "input.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_text("wav", encoding="utf-8")

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.detect_hard_subtitles",
        lambda *_args, **_kwargs: HardSubtitleProbeResult(False, 6, 1, 0.167),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalVisionEngine.extract_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not OCR first in smart transcription path")),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: InternalTranscriptionResult(
            transcript="smart transcribe",
            audio_path=audio_path,
            runtime_device="cpu",
        ),
    )

    result = acquire_transcript(options, "local", workdir)
    assert result.text == "smart transcribe"
    assert result.acquisition_method == "Internal Whisper base"


def test_acquire_transcript_smart_prefers_bilibili_official_subtitle(tmp_path, monkeypatch):
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="smart")
    options.source = "https://www.bilibili.com/video/BV1xx"

    class FakeBilibiliAdapter:
        def __init__(self, *_args, **_kwargs):
            pass

        def export_subtitles(self, *_args, **_kwargs):
            return "官方字幕"

    monkeypatch.setattr("app.pipeline.acquisition.BilibiliAdapter", FakeBilibiliAdapter)
    monkeypatch.setattr(
        "app.pipeline.acquisition.create_media_path",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not download media")),
    )

    result = acquire_transcript(options, "bilibili", workdir)

    assert result.text == "官方字幕"
    assert result.acquisition_method == "Bilibili official subtitle"
    assert result.media_path is None


def test_acquire_transcript_smart_downloads_media_when_bilibili_subtitle_is_unavailable(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="smart")
    options.source = "https://www.bilibili.com/video/BV1xx"
    audio_path = workdir / "media" / "audio" / "input.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_text("wav", encoding="utf-8")

    class FakeBilibiliAdapter:
        def __init__(self, *_args, **_kwargs):
            pass

        def export_subtitles(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("app.pipeline.acquisition.BilibiliAdapter", FakeBilibiliAdapter)
    monkeypatch.setattr(
        "app.pipeline.acquisition.create_media_path",
        lambda *_args, **_kwargs: media_path,
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.detect_hard_subtitles",
        lambda *_args, **_kwargs: HardSubtitleProbeResult(False, 6, 1, 0.167),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: InternalTranscriptionResult(
            transcript="smart transcribe",
            audio_path=audio_path,
            runtime_device="cpu",
        ),
    )

    result = acquire_transcript(options, "bilibili", workdir)
    assert result.text == "smart transcribe"
    assert result.acquisition_method == "Internal Whisper base"


def test_acquire_transcript_reports_ocr_failure_reason_before_fallback(tmp_path, monkeypatch):
    media_path = tmp_path / "input.mp4"
    media_path.write_text("x", encoding="utf-8")
    workdir = tmp_path / "work"
    options = _build_options(tmp_path, backend="auto", acquisition_mode="prefer_ocr")
    audio_path = workdir / "media" / "audio" / "input.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_text("wav", encoding="utf-8")
    events = []

    monkeypatch.setattr("app.pipeline.acquisition.create_media_path", lambda *_args: media_path)
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalVisionEngine.extract_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("ocr unavailable")),
    )
    monkeypatch.setattr(
        "app.pipeline.acquisition.InternalTranscriptionEngine.transcribe",
        lambda *_args, **_kwargs: InternalTranscriptionResult(
            transcript="fallback ok",
            audio_path=audio_path,
            runtime_device="cpu",
        ),
    )

    result = acquire_transcript(options, "local", workdir, event_callback=lambda stage, message, data=None: events.append((stage, message, data)))

    assert result.text == "fallback ok"
    ocr_failed = [item for item in events if item[0] == "ocr_failed"]
    assert ocr_failed
    assert ocr_failed[0][2]["error"] == "ocr unavailable"
