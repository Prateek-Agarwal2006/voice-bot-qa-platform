from __future__ import annotations

import os

import httpx

ORCHESTRATOR_BASE_URL = os.getenv("ORCHESTRATOR_BASE_URL", "http://localhost:8002").rstrip("/")


async def delete_staged_audio(recording_id: str) -> None:
    """Best-effort removal of ephemeral staged upload after transcript is saved."""
    url = f"{ORCHESTRATOR_BASE_URL}/api/jobs/{recording_id}/audio"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(url)
            if response.status_code not in (204, 404):
                print(
                    f"[eval] staged audio delete returned {response.status_code} for {recording_id}",
                    flush=True,
                )
    except Exception as exc:
        print(f"[eval] staged audio delete failed for {recording_id}: {exc}", flush=True)
