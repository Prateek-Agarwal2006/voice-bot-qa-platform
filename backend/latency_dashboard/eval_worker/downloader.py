from __future__ import annotations

import httpx


async def download(url: str, *, timeout_s: int = 120) -> bytes:
    """Fetch audio bytes from an HTTP/HTTPS URL."""
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content
