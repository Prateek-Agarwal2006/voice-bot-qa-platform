from __future__ import annotations

import os
import time
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/data/uploads"))
ORCHESTRATOR_BASE_URL = os.getenv("ORCHESTRATOR_BASE_URL", "http://localhost:8002").rstrip("/")
ORPHAN_TTL_HOURS = float(os.getenv("UPLOAD_ORPHAN_TTL_HOURS", "24"))

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a"}


def ensure_upload_dir() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def staged_path(recording_id: str) -> Path:
    return UPLOAD_DIR / recording_id


def internal_audio_url(recording_id: str) -> str:
    return f"{ORCHESTRATOR_BASE_URL}/api/jobs/{recording_id}/audio"


def validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file type '{ext or '(none)'}'. Allowed: {allowed}")
    return ext


def save_staged(recording_id: str, data: bytes) -> None:
    ensure_upload_dir()
    path = staged_path(recording_id)
    path.write_bytes(data)


def delete_staged(recording_id: str) -> bool:
    path = staged_path(recording_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


def staged_exists(recording_id: str) -> bool:
    return staged_path(recording_id).is_file()


def cleanup_orphaned_uploads() -> int:
    """Remove staged files older than ORPHAN_TTL_HOURS (best-effort startup hygiene)."""
    ensure_upload_dir()
    cutoff = time.time() - ORPHAN_TTL_HOURS * 3600
    removed = 0
    for path in UPLOAD_DIR.iterdir():
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed
