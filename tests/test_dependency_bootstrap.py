from app.services.dependency_bootstrap import ensure_opencv_dependency


def test_ensure_opencv_returns_existing(monkeypatch):
    monkeypatch.setattr("app.services.dependency_bootstrap._module_available", lambda name: True)

    result = ensure_opencv_dependency(raise_on_failure=False)

    assert result["ok"] is True
    assert result["already_available"] is True
    assert result["installed"] is False


def test_ensure_opencv_runs_pip_when_missing(monkeypatch):
    state = {"available": False, "command": None}

    def fake_module_available(name: str) -> bool:
        return state["available"]

    class Result:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(command, **kwargs):
        state["command"] = command
        state["available"] = True
        return Result()

    monkeypatch.setattr("app.services.dependency_bootstrap._module_available", fake_module_available)
    monkeypatch.setattr("app.services.dependency_bootstrap.subprocess.run", fake_run)

    result = ensure_opencv_dependency(raise_on_failure=False)

    assert result["ok"] is True
    assert result["installed"] is True
    assert "opencv-python" in state["command"]
