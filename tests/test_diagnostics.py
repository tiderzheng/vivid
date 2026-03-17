from app.services.diagnostics import build_error_summary


def test_build_error_summary_deduplicates_and_formats_items():
    events = [
        {"stage": "subtitle_failed", "message": "字幕提取失败", "data": {"error": "network timeout"}},
        {"stage": "subtitle_failed", "message": "字幕提取失败", "data": {"error": "network timeout"}},
        {"stage": "transcription_fallback", "message": "改走转录", "data": None},
    ]

    summary = build_error_summary(events)

    assert summary["has_issues"] is True
    assert summary["headline"] == "本次任务出现 2 个失败/回退节点"
    assert summary["items"] == [
        "字幕提取失败：network timeout",
        "改走转录",
    ]
