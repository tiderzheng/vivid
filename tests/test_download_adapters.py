from pathlib import Path
import subprocess

from app.adapters.bilibili import BilibiliAdapter
from app.adapters.douyin import DouyinAdapter
from app.adapters.ytdlp import YtDlpAdapter, _extra_args_to_options
from app.exceptions import BilibiliSessdataExpiredError, VividError


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


def test_bilibili_adapter_raises_expired_sessdata_error_for_subtitles(tmp_path, monkeypatch):
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")

    def fake_run(command, cwd=None, retries=1):
        raise VividError("Command failed: helper\n[error] api error -101: 账号未登录")

    monkeypatch.setattr("app.adapters.bilibili.run_command", fake_run)

    adapter = BilibiliAdapter(helper)

    try:
        adapter.export_subtitles("https://www.bilibili.com/video/BV1x", tmp_path, "expired")
    except BilibiliSessdataExpiredError as exc:
        assert "账号未登录" in str(exc)
    else:
        raise AssertionError("expired sessdata should raise a dedicated error")


def test_bilibili_adapter_raises_expired_sessdata_error_for_media(tmp_path, monkeypatch):
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.bilibili.shutil.which", lambda name: "C:/ffmpeg/bin/ffmpeg.exe")

    def fake_run(command, cwd=None, retries=1):
        raise VividError("Command failed: helper\n[error] api error -101: 账号未登录")

    monkeypatch.setattr("app.adapters.bilibili.run_command", fake_run)

    adapter = BilibiliAdapter(helper)

    try:
        adapter.download_media("https://www.bilibili.com/video/BV1x", tmp_path, "expired", "ffmpeg")
    except BilibiliSessdataExpiredError as exc:
        assert "账号未登录" in str(exc)
    else:
        raise AssertionError("expired sessdata should raise a dedicated error for media download")


def test_bilibili_adapter_reads_title_from_probe_episodes(tmp_path, monkeypatch):
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")

    class DummyResult:
        returncode = 0
        stdout = (
            '{'
            '"source_type":"video",'
            '"normalized_url":"https://www.bilibili.com/video/BV1x",'
            '"episode_count":2,'
            '"default_episode":2,'
            '"episodes":['
            '{"index":1,"title":"第一P","cid":1,"ep_id":0,"duration_sec":10},'
            '{"index":2,"title":"第二P","cid":2,"ep_id":0,"duration_sec":20}'
            ']'
            '}'
        )
        stderr = ""

    monkeypatch.setattr("app.adapters.bilibili.subprocess.run", lambda *args, **kwargs: DummyResult())

    adapter = BilibiliAdapter(helper)
    result = adapter.get_video_title("https://www.bilibili.com/video/BV1x", None)

    assert result == "第二P"


def test_bilibili_adapter_raises_expired_sessdata_error_for_title_probe(tmp_path, monkeypatch):
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")

    class DummyResult:
        returncode = 1
        stdout = ""
        stderr = "[error] api error -101: 账号未登录"

    monkeypatch.setattr("app.adapters.bilibili.subprocess.run", lambda *args, **kwargs: DummyResult())

    adapter = BilibiliAdapter(helper)

    try:
        adapter.get_video_title("https://www.bilibili.com/video/BV1x", "expired")
    except BilibiliSessdataExpiredError as exc:
        assert "账号未登录" in str(exc)
    else:
        raise AssertionError("expired sessdata during title probe should raise a dedicated error")


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


def test_douyin_title_fetch_requires_node(tmp_path, monkeypatch):
    helper = tmp_path / "douyin.js"
    helper.write_text("// helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.douyin.shutil.which", lambda name: None)

    adapter = DouyinAdapter(helper)

    try:
        adapter.get_video_title("https://v.douyin.com/abc/")
    except VividError as exc:
        assert "node" in str(exc).lower()
        assert "title fetch" in str(exc).lower()
    else:
        raise AssertionError("missing node should raise a dedicated title fetch error")


def test_douyin_title_fetch_surfaces_helper_failure(tmp_path, monkeypatch):
    helper = tmp_path / "douyin.js"
    helper.write_text("// helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.douyin.shutil.which", lambda name: "C:/Program Files/nodejs/node.exe")

    class DummyResult:
        returncode = 1
        stdout = ""
        stderr = "node helper boom"

    monkeypatch.setattr("app.adapters.douyin.subprocess.run", lambda *args, **kwargs: DummyResult())

    adapter = DouyinAdapter(helper)

    try:
        adapter.get_video_title("https://v.douyin.com/abc/")
    except VividError as exc:
        assert "title fetch failed" in str(exc).lower()
        assert "node helper boom" in str(exc)
    else:
        raise AssertionError("non-zero title fetch should raise a detailed error")


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
