from pathlib import Path

from app.services.ffmpeg_locator import inspect_ffmpeg, resolve_ffmpeg_bin


def test_resolve_ffmpeg_bin_prefers_bundled_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.ffmpeg_locator.shutil.which", lambda _name: None)
    ffmpeg_name = "ffmpeg.exe" if __import__("os").name == "nt" else "ffmpeg"
    bundled = tmp_path / "vendor" / "ffmpeg" / "bin" / ffmpeg_name
    bundled.parent.mkdir(parents=True, exist_ok=True)
    bundled.write_text("bin", encoding="utf-8")

    resolved = resolve_ffmpeg_bin(None, repo_root=tmp_path, tools_root=tmp_path / "tools")

    assert Path(resolved).resolve() == bundled.resolve()


def test_inspect_ffmpeg_falls_back_to_path(monkeypatch):
    monkeypatch.setattr(
        "app.services.ffmpeg_locator.shutil.which",
        lambda name: r"C:\ffmpeg\bin\ffmpeg.exe" if name == "ffmpeg" else None,
    )

    info = inspect_ffmpeg(preferred=None, repo_root=Path("D:/repo"), tools_root=Path("D:/tools"))

    assert info["available"] is True
    assert info["source"] == "path"
    assert "ffmpeg" in info["resolved"].lower()
