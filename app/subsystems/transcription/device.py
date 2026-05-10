from __future__ import annotations


def resolve_runtime_device(preference: str | None) -> str:
    normalized = (preference or "auto").strip().lower()
    if normalized in {"cpu"}:
        return "cpu"
    if normalized in {"cuda", "gpu", "discrete_gpu", "discrete"}:
        return "cuda" if _cuda_available() else "cpu"
    if normalized in {"integrated_gpu", "integrated"}:
        return "cpu"
    return "cuda" if _cuda_available() else "cpu"


def resolve_torch_runtime_device(preference: str | None) -> str:
    normalized = (preference or "auto").strip().lower()
    if normalized in {"cpu", "integrated_gpu", "integrated"}:
        return "cpu"
    if normalized in {"cuda", "gpu", "discrete_gpu", "discrete"}:
        return "cuda" if _torch_cuda_available() else "cpu"
    return "cuda" if _torch_cuda_available() else "cpu"


def _cuda_available() -> bool:
    try:
        import ctranslate2  # type: ignore
    except Exception:
        return False

    try:
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _torch_cuda_available() -> bool:
    try:
        import torch  # type: ignore
    except Exception:
        return False

    try:
        return bool(torch.cuda.is_available())
    except Exception:
        return False
