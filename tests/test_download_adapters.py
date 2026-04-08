from pathlib import Path
import subprocess

from app.adapters.bilibili import BilibiliAdapter
from app.adapters.douyin import DouyinAdapter
from app.adapters.ytdlp import YtDlpAdapter, _extra_args_to_options
from app.exceptions import VividError


def test_bilibili_adapter_calls_helper_for_media_without_sessdata_flag(tmp_path, monkeypatch):
    captured = {}
    target = tmp_path / "media" / "bilibili" / "video.mp4"
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.bilibili.shutil.which", lambda name: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setenv("BILI_SESSDATA", "stale-cookie")

    def fake_run(command, cwd=None, retries=1, env=None):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok", encoding="utf-8")

    monkeypatch.setattr("app.adapters.bilibili.run_command", fake_run)

    adapter = BilibiliAdapter(helper)
    result = adapter.download_media("https://www.bilibili.com/video/BV1x", tmp_path, "ffmpeg")

    assert result == target
    assert "python" in Path(captured["command"][0]).name.lower()
    assert Path(captured["command"][1]) == helper
    assert "--content" in captured["command"]
    assert "video_audio" in captured["command"]
    assert "--ffmpeg" in captured["command"]
    assert "--sessdata" not in captured["command"]
    assert captured["env"] is not None
    assert "BILI_SESSDATA" not in captured["env"]


def test_bilibili_adapter_reads_title_from_probe_episodes_without_sessdata_flag(tmp_path, monkeypatch):
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")
    captured = {}
    monkeypatch.setenv("BILI_SESSDATA", "stale-cookie")

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

    def fake_run(command, *args, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        return DummyResult()

    monkeypatch.setattr("app.adapters.bilibili.subprocess.run", fake_run)

    adapter = BilibiliAdapter(helper)
    result = adapter.get_video_title("https://www.bilibili.com/video/BV1x")

    assert result == "第二P"
    assert "--sessdata" not in captured["command"]
    assert captured["env"] is not None
    assert "BILI_SESSDATA" not in captured["env"]


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


def test_douyin_title_fetch_times_out_quickly(tmp_path, monkeypatch):
    helper = tmp_path / "douyin.js"
    helper.write_text("// helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.douyin.shutil.which", lambda name: "C:/Program Files/nodejs/node.exe")

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=kwargs.get("args", "node"), timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr("app.adapters.douyin.subprocess.run", fake_run)

    adapter = DouyinAdapter(helper)

    try:
        adapter.get_video_title("https://v.douyin.com/abc/")
    except VividError as exc:
        assert "timed out after 8 seconds" in str(exc).lower()
    else:
        raise AssertionError("title fetch timeout should raise a dedicated timeout error")


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
