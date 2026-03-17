from app.pipeline.detector import detect_platform


def test_detect_bilibili():
    assert detect_platform("https://www.bilibili.com/video/BV1xx") == "bilibili"


def test_detect_local(tmp_path):
    sample = tmp_path / "demo.mp4"
    sample.write_text("x", encoding="utf-8")
    assert detect_platform(str(sample)) == "local"
