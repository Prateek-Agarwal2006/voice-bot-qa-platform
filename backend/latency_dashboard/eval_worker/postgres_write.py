from __future__ import annotations

import json

from latency_dashboard.postgres_client import get_pool


async def update_recording_status(
    recording_id: str,
    status: str,
    *,
    error_message: str | None = None,
) -> None:
    """Update current status and append a durable stage-history event."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE recordings
                SET status = $1, error_message = $2, updated_at = NOW()
                WHERE recording_id = $3
                """,
                status,
                error_message,
                recording_id,
            )
            await conn.execute(
                """
                INSERT INTO recording_stage_events (recording_id, stage, detail)
                VALUES ($1, $2, $3)
                """,
                recording_id,
                status,
                error_message if status == "failed" else None,
            )


async def write_conversation(recording_id: str, conversation: dict) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (recording_id, turns, derived_signals, turn_count)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (recording_id) DO UPDATE SET
                turns           = EXCLUDED.turns,
                derived_signals = EXCLUDED.derived_signals,
                turn_count      = EXCLUDED.turn_count
            """,
            recording_id,
            json.dumps(conversation["turns"]),
            json.dumps(conversation["derived_signals"]),
            conversation["turn_count"],
        )


async def write_evaluation(recording_id: str, result: dict, *, evaluation_id: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO evaluations (evaluation_id, recording_id, judge_model, dimensions, evaluated_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (evaluation_id) DO UPDATE SET
                judge_model  = EXCLUDED.judge_model,
                dimensions   = EXCLUDED.dimensions,
                evaluated_at = EXCLUDED.evaluated_at
            """,
            evaluation_id,
            recording_id,
            result["judge_model"],
            json.dumps(result["dimensions"]),
            result["evaluated_at"],
        )
