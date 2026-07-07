from __future__ import annotations

from urllib.parse import urlparse, urlencode


def normalize(url: str, provider: str) -> str:
    """Return a directly downloadable URL for the given provider."""
    if provider == "google_drive":
        return _google_drive(url)
    return url  # "direct" or any future provider not yet implemented


def _google_drive(url: str) -> str:
    parsed = urlparse(url)

    file_id = _extract_drive_file_id(parsed)
    if file_id:
        # Go directly to drive.usercontent.google.com — skips the /uc 303 redirect
        # that can return HTML instead of bytes depending on cookies/session.
        return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"

    # unrecognised Google Drive URL shape — pass through and let ElevenLabs fail loudly
    return url


def _extract_drive_file_id(parsed) -> str | None:
    parts = [p for p in parsed.path.split("/") if p]

    # /file/d/{FILE_ID}/view
    if len(parts) >= 3 and parts[0] == "file" and parts[1] == "d":
        return parts[2]

    # /uc?id={FILE_ID} or /uc?export=download&id={FILE_ID}
    if parsed.path.startswith("/uc"):
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        ids = qs.get("id", [])
        return ids[0] if ids else None

    # drive.usercontent.google.com/download?id={FILE_ID}
    if "usercontent" in parsed.netloc and parsed.path.startswith("/download"):
        from urllib.parse import parse_qs
        qs = parse_qs(parsed.query)
        ids = qs.get("id", [])
        return ids[0] if ids else None

    return None
