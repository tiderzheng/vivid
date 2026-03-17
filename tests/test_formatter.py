from app.models.source import SourceInfo
from app.models.summary import SummaryResult
from app.models.transcript import TranscriptResult
from app.pipeline.formatter import render_quickread


def test_render_quickread_contains_sections():
    rendered = render_quickread(
        SourceInfo(raw_source="demo", platform="local", title="demo"),
        TranscriptResult(text="hello", acquisition_method="scaffold"),
        SummaryResult(one_line="one", detailed="detail", key_points=["a", "b"]),
        "both",
    )
    assert "原文逐字稿" in rendered
    assert "内容摘要" in rendered
