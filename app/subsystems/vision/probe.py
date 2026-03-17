from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...exceptions import VividError
from ...services.dependency_bootstrap import ensure_opencv_dependency


@dataclass(slots=True)
class HardSubtitleProbeResult:
    has_hard_subtitles: bool
    sampled_frames: int
    matched_frames: int
    ratio: float


def detect_hard_subtitles(
    video_path: Path,
    *,
    sample_count: int = 6,
    threshold_ratio: float = 0.45,
) -> HardSubtitleProbeResult:
    cv2 = _import_cv2()
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise VividError(f"Unable to open video for subtitle probe: {video_path}")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        capture.release()
        return HardSubtitleProbeResult(False, 0, 0, 0.0)

    indices = _sample_indices(total_frames, max(1, sample_count))
    sampled = 0
    matched = 0
    try:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            if not ok:
                continue
            sampled += 1
            if _frame_has_subtitle_like_text(cv2, frame):
                matched += 1
    finally:
        capture.release()

    ratio = matched / sampled if sampled else 0.0
    return HardSubtitleProbeResult(
        has_hard_subtitles=sampled > 0 and ratio >= threshold_ratio,
        sampled_frames=sampled,
        matched_frames=matched,
        ratio=round(ratio, 3),
    )


def _import_cv2():
    try:
        ensure_opencv_dependency(raise_on_failure=True)
        import cv2  # type: ignore
    except Exception as exc:
        raise VividError("Hard subtitle probe requires opencv-python or opencv-python-headless.") from exc
    return cv2


def _sample_indices(total_frames: int, sample_count: int) -> list[int]:
    if total_frames <= sample_count:
        return list(range(total_frames))
    margin = max(1, total_frames // (sample_count * 3))
    usable = max(1, total_frames - margin * 2)
    return [min(total_frames - 1, margin + int(usable * idx / sample_count)) for idx in range(sample_count)]


def _frame_has_subtitle_like_text(cv2, frame) -> bool:
    height, width = frame.shape[:2]
    if height <= 0 or width <= 0:
        return False

    roi = frame[int(height * 0.62) : height, int(width * 0.08) : int(width * 0.92)]
    if roi.size == 0:
        return False

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        21,
        12,
    )
    edges = cv2.Canny(thresh, 60, 180)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    merged = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    roi_height, roi_width = roi.shape[:2]
    text_like_boxes = 0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if area < 500:
            continue
        if w < roi_width * 0.18 or w > roi_width * 0.98:
            continue
        if h < 14 or h > roi_height * 0.3:
            continue
        if y < roi_height * 0.08 or y > roi_height * 0.9:
            continue
        aspect = w / max(1, h)
        if aspect < 3.0:
            continue
        text_like_boxes += 1
    return text_like_boxes > 0
