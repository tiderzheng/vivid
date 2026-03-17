from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from ...exceptions import VividError
from ...services.dependency_bootstrap import ensure_opencv_dependency
from ...utils.text import clean_transcript
from .models import VisionRequestConfig


@dataclass(slots=True)
class VisionEntry:
    start: int
    end: int
    text: str


@dataclass(slots=True)
class InternalVisionResult:
    transcript: str
    srt_path: Path | None
    txt_path: Path | None
    entries: list[VisionEntry]


class OpenAIOCREngine:
    def __init__(
        self,
        endpoint: str,
        api_key: str | None,
        model: str,
        prompt: str,
        system_prompt: str | None = None,
        api_path: str = "/v1/chat/completions",
        timeout: int = 30,
    ) -> None:
        self.endpoint = (endpoint or "").rstrip("/")
        self.api_path = api_path or "/v1/chat/completions"
        self.api_key = api_key or ""
        self.model = model
        self.prompt = prompt
        self.system_prompt = system_prompt or ""
        self.timeout = max(1, int(timeout or 30))
        self.session = requests.Session()

    def _chat_url(self) -> str:
        path = (self.api_path or "").strip()
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path:
            path = "/v1/chat/completions"
        if not self.endpoint:
            return path
        return self.endpoint + "/" + path.lstrip("/")

    def _encode_image(self, image_bgr) -> str:
        cv2 = _import_cv2()
        ok, buf = cv2.imencode(".png", image_bgr)
        if not ok:
            raise VividError("Failed to encode OCR frame.")
        return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")

    def recognize(self, image_bgr) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        messages: list[dict] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": self.prompt},
                    {"type": "image_url", "image_url": {"url": self._encode_image(image_bgr)}},
                ],
            }
        )
        response = self.session.post(
            self._chat_url(),
            headers=headers,
            json={"model": self.model, "messages": messages, "temperature": 0},
            timeout=self.timeout,
        )
        response.raise_for_status()
        content = (response.json().get("choices") or [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list) and content and isinstance(content[0], dict):
            return str(content[0].get("text", "")).strip()
        if isinstance(content, str):
            return content.strip()
        return ""


class InternalVisionEngine:
    def extract_text(
        self,
        video_path: Path,
        workdir: Path,
        timeout_seconds: int,
        request_config: VisionRequestConfig,
    ) -> InternalVisionResult:
        if not request_config.api_base or not request_config.model:
            raise VividError("Internal OCR requires api_base and model.")

        cv2 = _import_cv2()
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise VividError(f"Unable to open video for OCR: {video_path}")

        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step = max(1, int((fps or 25) * request_config.sample_ms / 1000))
        deadline = time.time() + timeout_seconds
        engine = OpenAIOCREngine(
            endpoint=request_config.api_base,
            api_key=request_config.api_key,
            model=request_config.model,
            prompt=request_config.prompt or "只返回画面中的可读字幕文本。如果没有字幕，返回空字符串。",
            system_prompt=request_config.system_prompt,
            api_path=request_config.api_path or "/v1/chat/completions",
            timeout=request_config.timeout or 30,
        )

        frame_index = 0
        prev_text: str | None = None
        start_ms: int | None = None
        current_ms = 0
        entries: list[VisionEntry] = []

        try:
            while True:
                if time.time() >= deadline:
                    raise VividError(f"Internal OCR timed out after {timeout_seconds}s.")
                ret, frame = capture.read()
                if not ret:
                    break
                if frame_index % step != 0:
                    frame_index += 1
                    continue
                current_ms = int((frame_index / max(1.0, fps or 25)) * 1000)
                text = _filter_subtitle_text(engine.recognize(frame))
                if text and prev_text is None:
                    prev_text = text
                    start_ms = current_ms
                elif text and prev_text is not None:
                    if _normalize_text(text) != _normalize_text(prev_text):
                        entries.append(
                            VisionEntry(
                                start=start_ms or current_ms,
                                end=max(current_ms, (start_ms or current_ms) + request_config.min_duration_ms),
                                text=prev_text,
                            )
                        )
                        prev_text = text
                        start_ms = current_ms
                elif not text and prev_text is not None:
                    entries.append(
                        VisionEntry(
                            start=start_ms or current_ms,
                            end=max(current_ms, (start_ms or current_ms) + request_config.min_duration_ms),
                            text=prev_text,
                        )
                    )
                    prev_text = None
                    start_ms = None
                frame_index += 1
        finally:
            capture.release()

        if prev_text is not None and start_ms is not None:
            entries.append(
                VisionEntry(
                    start=start_ms,
                    end=max(current_ms, start_ms + request_config.min_duration_ms),
                    text=prev_text,
                )
            )

        transcript = clean_transcript("\n".join(entry.text for entry in entries if entry.text.strip()))
        if not transcript:
            raise VividError("Internal OCR completed but returned empty text.")

        artifacts_dir = workdir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        srt_path = artifacts_dir / f"{video_path.stem}.ocr.srt"
        txt_path = artifacts_dir / f"{video_path.stem}.ocr.txt"
        _write_srt(entries, srt_path)
        txt_path.write_text(transcript, encoding="utf-8")
        return InternalVisionResult(
            transcript=transcript,
            srt_path=srt_path,
            txt_path=txt_path,
            entries=entries,
        )


def _import_cv2():
    try:
        ensure_opencv_dependency(raise_on_failure=True)
        import cv2  # type: ignore
    except Exception as exc:
        raise VividError("Internal OCR requires opencv-python or opencv-python-headless.") from exc
    return cv2


def _filter_subtitle_text(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    lowered = value.lower()
    no_subtitle_patterns = [
        "图中无",
        "没有字幕",
        "无字幕",
        "没有文字",
        "无文字",
        "没有可读",
        "无可读",
        "没有内容",
        "无内容",
        "图片中无",
        "图片中没有",
        "画面无",
        "画面中无",
        "未发现",
        "未找到",
        "不存在",
        "no subtitle",
        "no text",
        "no readable",
        "no content",
        "nothing",
        "empty",
        "图中",
        "图片中",
        "画面",
        "此图",
        "该图",
        "截图",
        "视频",
        "帧",
    ]
    for pattern in no_subtitle_patterns:
        if pattern in lowered and (len(value) <= 20 or lowered == pattern):
            return ""
    if len(value) <= 15 and any(token in lowered for token in ["字幕", "文字", "文本", "内容", "截图", "图片", "画面", "视频", "帧"]):
        return ""
    return value


def _normalize_text(text: str) -> str:
    return "".join(text.lower().split())


def _format_srt_timestamp(ms: int) -> str:
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def _write_srt(entries: list[VisionEntry], path: Path) -> None:
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        lines.append(str(index))
        lines.append(
            f"{_format_srt_timestamp(entry.start)} --> {_format_srt_timestamp(entry.end)}"
        )
        lines.append(entry.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
