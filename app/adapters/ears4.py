from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import requests

from ..exceptions import VividError
from ..subsystems.transcription.models import TranscriptionRequestConfig
from ..utils.text import clean_transcript


@dataclass(slots=True)
class Ears4Response:
    transcript: str
    audio_path: Path | None = None


class Ears4Adapter:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def transcribe(
        self,
        source_path: Path,
        timeout_seconds: int,
        request_config: TranscriptionRequestConfig,
    ) -> Ears4Response:
        session = requests.Session()
        session.get(f"{self.base_url}/api/v1/health", timeout=10).raise_for_status()
        payload = request_config.to_ears4_payload(source_path)
        response = session.post(f"{self.base_url}/api/v1/jobs/pipeline", json=payload, timeout=30)
        response.raise_for_status()
        job_id = response.json()["job_id"]
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            job_resp = session.get(f"{self.base_url}/api/v1/jobs/{job_id}", timeout=30)
            job_resp.raise_for_status()
            data = job_resp.json()
            status = str(data.get("status", "")).lower()
            if status == "completed":
                audio_path = Path(data["audio_path"]).resolve() if data.get("audio_path") else None
                text = data.get("transcript_text")
                if not text:
                    text_resp = session.get(f"{self.base_url}/api/v1/jobs/{job_id}/text", timeout=30)
                    text_resp.raise_for_status()
                    text = text_resp.json().get("text", "")
                transcript = clean_transcript(text or "")
                if not transcript:
                    raise VividError("Ears4 completed but returned empty transcript.")
                return Ears4Response(transcript=transcript, audio_path=audio_path)
            if status == "failed":
                raise VividError(data.get("error") or data.get("message") or "Ears4 transcription failed.")
            time.sleep(3)
        raise VividError(f"Ears4 transcription timed out after {timeout_seconds}s.")
