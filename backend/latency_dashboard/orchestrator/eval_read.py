from __future__ import annotations

import json
from typing import Any

from latency_dashboard.postgres_client import get_pool
from latency_dashboard.schemas import ConversationDTO, EvaluationDTO, RecordingDTO


async def list_recordings(
    *,
    limit: int = 50,
    status: str | None = None,
) -> list[RecordingDTO]:
    pool = await get_pool()
    conditions = []
    params: list[Any] = []

    if status:
        params.append(status)
        conditions.append(f"status = ${len(params)}")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
    SELECT recording_id, status, ingestion_source, source_url, judge_model,
           url_provider, error_message, created_at, updated_at
    FROM recordings
    {where}
    ORDER BY created_at DESC
    LIMIT {limit}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    return [
        RecordingDTO(
            recording_id=row["recording_id"],
            status=row["status"],
            ingestion_source=row["ingestion_source"],
            source_url=row["source_url"],
            judge_model=row["judge_model"],
            url_provider=row["url_provider"],
            error_message=row["error_message"],
            created_at=row["created_at"].isoformat(),
            updated_at=row["updated_at"].isoformat(),
        )
        for row in rows
    ]


async def get_conversation(recording_id: str) -> ConversationDTO | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT recording_id, turns, derived_signals, turn_count FROM conversations WHERE recording_id = $1",
            recording_id,
        )
    if row is None:
        return None
    turns = row["turns"] if isinstance(row["turns"], list) else json.loads(row["turns"])
    signals = row["derived_signals"] if isinstance(row["derived_signals"], dict) else json.loads(row["derived_signals"])
    return ConversationDTO(
        recording_id=row["recording_id"],
        turns=turns,
        derived_signals=signals,
        turn_count=row["turn_count"],
    )


async def get_evaluation(recording_id: str) -> EvaluationDTO | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT recording_id, judge_model, dimensions, evaluated_at
            FROM evaluations
            WHERE recording_id = $1
            ORDER BY evaluated_at DESC
            LIMIT 1
            """,
            recording_id,
        )
    if row is None:
        return None
    dimensions = row["dimensions"] if isinstance(row["dimensions"], dict) else json.loads(row["dimensions"])
    return EvaluationDTO(
        recording_id=row["recording_id"],
        judge_model=row["judge_model"],
        dimensions=dimensions,
        evaluated_at=row["evaluated_at"].isoformat(),
    )
