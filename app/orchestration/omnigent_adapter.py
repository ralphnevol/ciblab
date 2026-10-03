from __future__ import annotations


def detect_omnigent() -> dict:
    try:
        import omnigent  # type: ignore

        version = getattr(omnigent, "__version__", "unknown")
        return {"available": True, "version": str(version), "mode": "native"}
    except Exception:
        return {"available": False, "version": None, "mode": "local_fallback"}
