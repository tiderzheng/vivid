from __future__ import annotations

import time
from pathlib import Path

import requests

from ..exceptions import VividError
from ..subsystems.vision.models import VisionRequestConfig
from ..services.media_store import read_text_file
from ..utils.text import clean_transcript


class EyesAdapter:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def extract_text(
        self,
        video_path: Path,
        workdir: Path,
        timeout_seconds: int,
        vision_config: VisionRequestConfig | None = None,
    ) -> str:
        session = requests.Session()
        session.get(f"{self.base_url}/api/v1/health", timeout=10).raise_for_status()
        output_path = (workdir / "artifacts" / f"{video_path.stem}.ocr.srt").resolve()
        payload = (
            vision_config.to_eyes_payload(video_path, output_path)
            if vision_config
            else {
                "video_path": str(video_path),
                "sample_ms": 800,
                "min_duration_ms": 1200,
                "output_path": str(output_path),
                "prompt": "只返回画面中的可读字幕文本。如果没有字幕，返回空字符串。",
            }
        )
        response = session.post(f"{self.base_url}/api/v1/tasks", json=payload, timeout=30)
        response.raise_for_status()
        task_id = response.json()["task_id"]
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            task_resp = session.get(f"{self.base_url}/api/v1/tasks/{task_id}", timeout=30)
            task_resp.raise_for_status()
            task = task_resp.json()
            status = str(task.get("status", "")).lower()
            if status == "completed":
                result_resp = session.get(
                    f"{self.base_url}/api/v1/tasks/{task_id}/result",
                    params={"include_entries": 1},
                    timeout=30,
                )
                result_resp.raise_for_status()
                result = result_resp.json()
                entries = result.get("entries") or []
                if entries:
                    text = "\n".join(
                        str(item.get("text", "")).strip()
                        for item in entries
                        if str(item.get("text", "")).strip()
                    )
                    transcript = clean_transcript(text)
                    if transcript:
                        return transcript
                txt_output = result.get("txt_output_path")
                if txt_output and Path(txt_output).exists():
                    transcript = clean_transcript(read_text_file(Path(txt_output)))
                    if transcript:
                        return transcript
                raise VividError("Eyes OCR completed but returned empty text.")
            if status in {"error", "failed", "stopped"}:
                raise VividError(task.get("error") or "Eyes OCR failed.")
            time.sleep(3)
        raise VividError(f"Eyes OCR timed out after {timeout_seconds}s.")
