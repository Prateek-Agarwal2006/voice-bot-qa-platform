from __future__ import annotations

"""Postgres LISTEN/NOTIFY channel names and helpers.

``eval_jobs`` — Orchestrator NOTIFYs after enqueue; Eval Worker LISTENs to
wake immediately instead of waiting for the backup poll interval.

NOTIFY is a doorbell only. The ``recordings`` table remains the durable queue
and source of truth. Missed notifications are recovered by backup polling.
"""

EVAL_JOBS_CHANNEL = "eval_jobs"


async def notify(conn, channel: str, payload: str) -> None:
    """Emit NOTIFY on ``channel`` with a small string payload (recording_id)."""
    await conn.execute("SELECT pg_notify($1, $2)", channel, payload)
