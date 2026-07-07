from __future__ import annotations

import asyncio
import os

from latency_dashboard.eval_worker import eval
from latency_dashboard.postgres_client import get_pool

_POLL_INTERVAL_S = int(os.getenv("EVAL_POLL_INTERVAL_S", "5"))


async def _claim_next_job() -> tuple[str, str, str, str] | None:
    """Claim one pending recording. Returns (recording_id, source_url, judge_model, url_provider) or None."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT recording_id, source_url, judge_model, url_provider
                FROM recordings
                WHERE status = 'pending'
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            return (row["recording_id"], row["source_url"], row["judge_model"], row["url_provider"]) if row else None


async def run_collector(*, once: bool = False) -> None:
    while True:
        job = await _claim_next_job()
        if job:
            recording_id, source_url, judge_model, url_provider = job
            await eval.run(recording_id, source_url, judge_model, url_provider)
        else:
            await asyncio.sleep(_POLL_INTERVAL_S)
        if once:
            return


def main() -> None:
    once = os.getenv("COLLECT_ONCE", "").lower() in {"1", "true", "yes"}
    asyncio.run(run_collector(once=once))
