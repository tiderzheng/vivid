from __future__ import annotations

import contextlib
import io
import os
import threading
from pathlib import Path
from typing import Any


class ParaformerService:
    MODEL_NAME = "paraformer-zh"
    MODEL_ID = "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    VAD_MODEL_NAME = "fsmn-vad"
    VAD_MODEL_ID = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    PUNC_MODEL_NAME = "ct-punc"
    PUNC_MODEL_ID = "iic/punc_ct-transformer_cn-en-common-vocab471067-large"

    def __init__(self, model_root: Path | None = None) -> None:
        self._model_root = model_root
        self._model_class: Any | None = None
        self._models: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _ensure_model_class(self) -> Any:
        if self._model_class is not None:
            return self._model_class

        try:
            from funasr import AutoModel  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Cannot import funasr/torchaudio runtime. Install compatible funasr, torch, and torchaudio "
                "from requirements.txt to use paraformer-zh."
            ) from exc

        self._model_class = AutoModel
        return AutoModel

    def _get_model(self, device: str) -> Any:
        funasr_device = _funasr_device(device)
        if funasr_device in self._models:
            return self._models[funasr_device]

        with self._lock:
            if funasr_device in self._models:
                return self._models[funasr_device]
            auto_model = self._ensure_model_class()
            kwargs: dict[str, Any] = {
                "model": _resolve_model_argument(
                    self.MODEL_NAME,
                    self.MODEL_ID,
                    self._model_root,
                ),
                "device": funasr_device,
                "disable_update": True,
            }
            vad_model = _resolve_optional_model_argument(self.VAD_MODEL_ID, self._model_root)
            if vad_model is not None:
                kwargs["vad_model"] = vad_model
            punc_model = _resolve_optional_model_argument(self.PUNC_MODEL_ID, self._model_root)
            if punc_model is not None:
                kwargs["punc_model"] = punc_model
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                model = auto_model(**kwargs)
            self._models[funasr_device] = model
            return model

    def transcribe(
        self,
        audio_path: Path,
        device: str,
        language: str | None = None,
        task: str = "transcribe",
    ) -> dict[str, Any]:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if task != "transcribe":
            raise ValueError("paraformer-zh only supports transcribe task")

        model = self._get_model(device)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = model.generate(
                input=str(audio_path),
                batch_size_s=300,
                language=language or "zh",
            )
        return _normalize_result(result)


def _normalize_result(result: Any) -> dict[str, Any]:
    items = result if isinstance(result, list) else [result]
    texts: list[str] = []
    segments: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            texts.append(text)
            segments.append(
                {
                    "id": item.get("key", index),
                    "start": None,
                    "end": None,
                    "text": text,
                }
            )
            continue
        text = str(item).strip()
        texts.append(text)
        segments.append({"id": index, "start": None, "end": None, "text": text})
    return {
        "text": " ".join(text for text in texts if text).strip(),
        "segments": segments,
        "language": "zh",
    }


def _funasr_device(device: str) -> str:
    return "cuda:0" if device == "cuda" else "cpu"


def _resolve_model_argument(alias: str, model_id: str, model_root: Path | None) -> str:
    cached_dir = _find_cached_model_dir(model_id, model_root)
    if cached_dir is not None:
        return str(cached_dir)
    return alias


def _resolve_optional_model_argument(model_id: str, model_root: Path | None) -> str | None:
    cached_dir = _find_cached_model_dir(model_id, model_root)
    if cached_dir is None:
        return None
    return str(cached_dir)


def _find_cached_model_dir(model_id: str, model_root: Path | None) -> Path | None:
    relative = Path(*model_id.split("/"))
    candidates: list[Path] = []
    for root in _candidate_cache_roots(model_root):
        candidates.append(root / "models" / relative)
        candidates.append(root / relative)
    for candidate in candidates:
        if _is_funasr_model_dir(candidate):
            return candidate
    return None


def _candidate_cache_roots(model_root: Path | None) -> list[Path]:
    roots: list[Path] = []
    if model_root is not None:
        roots.extend(
            [
                model_root,
                model_root / "modelscope",
                model_root / "modelscope" / "hub",
            ]
        )
    configured = os.environ.get("MODELSCOPE_CACHE")
    if configured:
        roots.append(Path(configured).expanduser())
    else:
        roots.append(Path.home() / ".cache" / "modelscope" / "hub")
    return roots


def _is_funasr_model_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "configuration.json").is_file() or (path / "config.yaml").is_file()
