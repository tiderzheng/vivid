from pathlib import Path

from app.adapters.bilibili import BilibiliAdapter
from app.adapters.douyin import DouyinAdapter
from app.adapters.ytdlp import YtDlpAdapter, _extra_args_to_options


def test_bilibili_adapter_calls_helper_for_subtitles(tmp_path, monkeypatch):
    captured = {}
    subtitle_dir = tmp_path / "artifacts" / "bilibili-subtitle"
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")

    def fake_run(command, cwd=None, retries=1):
        captured["command"] = command
        captured["cwd"] = cwd
        subtitle_dir.mkdir(parents=True, exist_ok=True)
        (subtitle_dir / "demo.srt").write_text("字幕文本", encoding="utf-8")

    monkeypatch.setattr("app.adapters.bilibili.run_command", fake_run)

    adapter = BilibiliAdapter(helper)
    result = adapter.export_subtitles("https://www.bilibili.com/video/BV1x", tmp_path, "sess")

    assert result == "字幕文本"
    assert "python" in Path(captured["command"][0]).name.lower()
    assert Path(captured["command"][1]) == helper
    assert "--subtitle-format" in captured["command"]
    assert "--sessdata" in captured["command"]


def test_bilibili_adapter_calls_helper_for_media(tmp_path, monkeypatch):
    target = tmp_path / "media" / "bilibili" / "video.mp4"
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.bilibili.shutil.which", lambda name: "C:/ffmpeg/bin/ffmpeg.exe")

    captured = {}

    def fake_run(command, cwd=None, retries=1):
        captured["command"] = command
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok", encoding="utf-8")

    monkeypatch.setattr("app.adapters.bilibili.run_command", fake_run)

    adapter = BilibiliAdapter(helper)
    result = adapter.download_media("https://www.bilibili.com/video/BV1x", tmp_path, "sess", "ffmpeg")

    assert result == target
    assert "--content" in captured["command"]
    assert "video_audio" in captured["command"]
    assert "--ffmpeg" in captured["command"]


def test_douyin_adapter_calls_helper(tmp_path, monkeypatch):
    target = tmp_path / "media" / "douyin" / "123.mp4"
    helper = tmp_path / "douyin.js"
    helper.write_text("// helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.douyin.shutil.which", lambda name: "C:/Program Files/nodejs/node.exe")
    captured = {}

    def fake_run(command, cwd=None, retries=1):
        captured["command"] = command
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok", encoding="utf-8")

    monkeypatch.setattr("app.adapters.douyin.run_command", fake_run)

    adapter = DouyinAdapter(helper)
    result = adapter.download_media("https://v.douyin.com/abc/", tmp_path)

    assert result == target
    assert captured["command"][0] == "node"
    assert Path(captured["command"][1]) == helper
    assert captured["command"][2] == "download"


def test_ytdlp_extra_headers_are_converted():
    options = _extra_args_to_options(
        ["--add-header", "Referer: https://www.bilibili.com/", "--add-header", "Cookie: SESSDATA=abc"],
    )
    assert options["http_headers"]["Referer"] == "https://www.bilibili.com/"
    assert options["http_headers"]["Cookie"] == "SESSDATA=abc"


def test_ytdlp_adapter_uses_python_library(tmp_path, monkeypatch):
    captured = {}
    outdir = tmp_path / "media" / "generic"
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / "demo.mp4"
    target.write_text("ok", encoding="utf-8")

    class FakeYoutubeDL:
        def __init__(self, options):
            captured["options"] = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def download(self, sources):
            captured["sources"] = sources

    monkeypatch.setattr("app.adapters.ytdlp.YoutubeDL", FakeYoutubeDL)

    result = YtDlpAdapter().download_media("https://example.com/video", tmp_path)

    assert result == target
    assert captured["sources"] == ["https://example.com/video"]
    assert captured["options"]["format"] == "best"
