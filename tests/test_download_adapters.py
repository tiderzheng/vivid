import importlib.util
from pathlib import Path
import subprocess

from app.adapters.bilibili import BilibiliAdapter
from app.adapters.douyin import DouyinAdapter
from app.adapters.ytdlp import YtDlpAdapter, _extra_args_to_options
from app.exceptions import VividError


def _load_bilibili_helper():
    helper_path = Path(__file__).resolve().parents[1] / "tools" / "bilibili" / "bili23_agent_cli.py"
    spec = importlib.util.spec_from_file_location("bili23_agent_cli", helper_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bilibili_adapter_calls_helper_for_media_without_helper_cli_flags(tmp_path, monkeypatch):
    captured = {}
    target = tmp_path / "media" / "bilibili" / "video.mp4"
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")
    monkeypatch.setattr("app.adapters.bilibili.shutil.which", lambda name: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setenv("VIVID_BILI_COOKIE", "SESSDATA=stale-cookie; buvid3=stale")
    monkeypatch.setenv("BILI_SESSDATA", "stale-cookie")

    def fake_run(command, cwd=None, retries=1, env=None):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("ok", encoding="utf-8")

    monkeypatch.setattr("app.adapters.bilibili.run_command", fake_run)

    adapter = BilibiliAdapter(helper)
    result = adapter.download_media(
        "https://www.bilibili.com/video/BV1x",
        tmp_path,
        "ffmpeg",
        bili_cookie="SESSDATA=fresh-cookie; buvid3=abc",
        sessdata="legacy-cookie",
    )

    assert result == target
    assert "python" in Path(captured["command"][0]).name.lower()
    assert Path(captured["command"][1]) == helper
    assert "--content" in captured["command"]
    assert "video_audio" in captured["command"]
    assert "--ffmpeg" in captured["command"]
    assert "--sessdata" not in captured["command"]
    assert captured["env"] is not None
    assert captured["env"]["VIVID_BILI_COOKIE"] == "SESSDATA=fresh-cookie; buvid3=abc"
    assert captured["env"]["BILI_SESSDATA"] == "legacy-cookie"
    assert "BILI_COOKIE" not in captured["env"]
    assert "BILI_COOKIE_HEADER" not in captured["env"]


def test_bilibili_adapter_reads_title_from_probe_episodes_without_helper_cli_flags(tmp_path, monkeypatch):
    helper = tmp_path / "bili.py"
    helper.write_text("# helper", encoding="utf-8")
    captured = {}
    monkeypatch.setenv("VIVID_BILI_COOKIE", "SESSDATA=stale-cookie; buvid3=stale")
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
    result = adapter.get_video_title(
        "https://www.bilibili.com/video/BV1x",
        bili_cookie="SESSDATA=fresh-cookie; buvid3=abc",
        sessdata="legacy-cookie",
    )

    assert result == "第二P"
    assert "--sessdata" not in captured["command"]
    assert captured["env"] is not None
    assert captured["env"]["VIVID_BILI_COOKIE"] == "SESSDATA=fresh-cookie; buvid3=abc"
    assert captured["env"]["BILI_SESSDATA"] == "legacy-cookie"


def test_bilibili_helper_prefers_full_cookie_and_fills_missing_fields(monkeypatch):
    helper = _load_bilibili_helper()
    monkeypatch.setattr(helper.time, "time", lambda: 1700000000.0)
    monkeypatch.setattr(helper, "_fetch_spi_buvids", lambda _session: {"buvid4": "from-spi"})

    cookies = helper._build_cookie_values(
        "SESSDATA=full-cookie; buvid3=from-cookie; foo=bar",
        "legacy-sessdata",
        helper.requests.Session(),
    )

    assert cookies["SESSDATA"] == "full-cookie"
    assert cookies["buvid3"] == "from-cookie"
    assert cookies["buvid4"] == "from-spi"
    assert cookies["foo"] == "bar"
    assert cookies["_uuid"].endswith("00000infoc")
    assert cookies["b_lsid"].endswith("_6553F100")
    assert cookies["b_nut"] == "1700000000"
    assert cookies["CURRENT_FNVAL"] == "4048"
    assert cookies["CURRENT_QUALITY"] == "0"


def test_bilibili_helper_uses_sessdata_when_full_cookie_missing(monkeypatch):
    helper = _load_bilibili_helper()
    monkeypatch.setattr(helper.time, "time", lambda: 1700000000.0)
    monkeypatch.setattr(
        helper,
        "_fetch_spi_buvids",
        lambda _session: {"buvid3": "spi-buvid3", "buvid4": "spi-buvid4"},
    )

    cookies = helper._build_cookie_values("", "legacy-sessdata", helper.requests.Session())

    assert cookies["SESSDATA"] == "legacy-sessdata"
    assert cookies["_uuid"].endswith("00000infoc")
    assert cookies["b_lsid"].endswith("_6553F100")
    assert cookies["b_nut"] == "1700000000"
    assert cookies["buvid3"] == "spi-buvid3"
    assert cookies["buvid4"] == "spi-buvid4"


def test_bilibili_helper_generates_anonymous_fingerprint_without_auth(monkeypatch):
    helper = _load_bilibili_helper()
    monkeypatch.setattr(helper.time, "time", lambda: 1700000000.0)
    monkeypatch.setattr(
        helper,
        "_fetch_spi_buvids",
        lambda _session: {"buvid3": "spi-buvid3", "buvid4": "spi-buvid4"},
    )

    cookies = helper._build_cookie_values("", "", helper.requests.Session())

    assert "SESSDATA" not in cookies
    assert cookies["_uuid"].endswith("00000infoc")
    assert cookies["b_lsid"].endswith("_6553F100")
    assert cookies["b_nut"] == "1700000000"
    assert cookies["CURRENT_FNVAL"] == "4048"
    assert cookies["CURRENT_QUALITY"] == "0"
    assert cookies["buvid3"] == "spi-buvid3"
    assert cookies["buvid4"] == "spi-buvid4"


def test_bilibili_helper_resolves_cookie_from_new_flag_and_env(monkeypatch):
    helper = _load_bilibili_helper()
    monkeypatch.setenv("VIVID_BILI_COOKIE", "SESSDATA=env-cookie")
    monkeypatch.setenv("BILI_SESSDATA", "env-sessdata")

    args = helper.build().parse_args(
        [
            "probe",
            "--url",
            "https://www.bilibili.com/video/BV1x",
            "--bili-cookie",
            "SESSDATA=cli-cookie; bili_jct=token",
        ]
    )

    cookie, sessdata = helper._resolve_cookie_inputs(args)

    assert cookie == "SESSDATA=cli-cookie; bili_jct=token"
    assert sessdata == "env-sessdata"


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
