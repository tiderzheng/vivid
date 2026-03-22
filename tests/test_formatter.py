from app.models.source import SourceInfo
from app.models.summary import SummaryResult
from app.models.transcript import TranscriptResult
from app.pipeline.formatter import render_quickread


def test_render_quickread_contains_sections():
    rendered = render_quickread(
        SourceInfo(raw_source="demo", platform="local", title="demo"),
        TranscriptResult(text="hello", acquisition_method="scaffold"),
        SummaryResult(
            title="标题",
            overview="概览",
            core_points=["观点1", "观点2"],
            controversies=["争议1"],
            action_suggestions=["建议1", "建议2"],
            playful_comment="俏皮一下",
        ),
        "both",
    )
    assert "原文逐字稿" in rendered
    assert "内容概览" in rendered
    assert "核心观点" in rendered
    assert "争议点" in rendered
    assert "行动建议" in rendered
    assert "俏皮点评" in rendered
