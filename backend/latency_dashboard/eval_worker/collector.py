from __future__ import annotations

import asyncio
import os

import asyncpg

from latency_dashboard.db_migrate import ensure_stage_events_table
from latency_dashboard.eval_worker import eval
from latency_dashboard.pg_notify import EVAL_JOBS_CHANNEL, RECORDING_UPDATED_CHANNEL, notify
from latency_dashboard.postgres_client import get_pool

# Backup poll when idle — recovers jobs if NOTIFY was missed (worker restart, etc.).
# Primary wake-up is LISTEN on eval_jobs; this interval is only the safety net.
_BACKUP_POLL_INTERVAL_S = float(os.getenv("EVAL_POLL_INTERVAL_S", "60"))


async def _claim_next_job() -> tuple[str, str, str, str, str] | None:
    """Atomically claim one pending recording (status → downloading) via SKIP LOCKED."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE recordings
                SET status = 'downloading', updated_at = NOW()
                WHERE recording_id = (
                    SELECT recording_id
                    FROM recordings
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING recording_id, source_url, judge_model, url_provider, ingestion_source
                """
            )
            if not row:
                return None
            await conn.execute(
                """
                INSERT INTO recording_stage_events (recording_id, stage)
                VALUES ($1, 'downloading')
                """,
                row["recording_id"],
            )
            await notify(conn, RECORDING_UPDATED_CHANNEL, row["recording_id"])
            return (
                row["recording_id"],
                row["source_url"],
                row["judge_model"],
                row["url_provider"],
                row["ingestion_source"],
            )


async def _run_job(job: tuple[str, str, str, str, str]) -> None:
    recording_id, source_url, judge_model, url_provider, ingestion_source = job
    await eval.run(
        recording_id,
        source_url,
        judge_model,
        url_provider,
        ingestion_source=ingestion_source,
    )


async def run_collector(*, once: bool = False) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await ensure_stage_events_table(conn)

    if once:
        job = await _claim_next_job()
        if job:
            await _run_job(job)
        return

    wake = asyncio.Event()

    def _on_eval_job(
        _connection: asyncpg.Connection,
        _pid: int,
        _channel: str,
        _payload: str,
    ) -> None:
        wake.set()

    dsn = os.environ["POSTGRES_DSN"]
    listener: asyncpg.Connection | None = None

    try:
        listener = await asyncpg.connect(dsn)
        await listener.add_listener(EVAL_JOBS_CHANNEL, _on_eval_job)
        print(
            f"[eval-worker] LISTEN {EVAL_JOBS_CHANNEL} "
            f"(backup poll every {_BACKUP_POLL_INTERVAL_S}s)",
            flush=True,
        )

        while True:
            # Drain any pending work first (covers backlog + missed NOTIFY).
            while True:
                job = await _claim_next_job()
                if not job:
                    break
                await _run_job(job)

            wake.clear()
            try:
                await asyncio.wait_for(wake.wait(), timeout=_BACKUP_POLL_INTERVAL_S)
            except asyncio.TimeoutError:
                # Backup poll path — same claim logic as above.
                pass
    finally:
        if listener is not None and not listener.is_closed():
            try:
                await listener.remove_listener(EVAL_JOBS_CHANNEL, _on_eval_job)
            except Exception:
                pass
            await listener.close()


def main() -> None:
    once = os.getenv("COLLECT_ONCE", "").lower() in {"1", "true", "yes"}
    asyncio.run(run_collector(once=once))
