from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from latency_dashboard.postgres_client import get_pool

router = APIRouter()


class IngestRequest(BaseModel):
    source_url: str
    judge_model: str = "gpt-4o-mini"
    url_provider: str = "direct"
    ingestion_source: Literal["https", "upload"] = "https"


class JobStatusResponse(BaseModel):
    recording_id: str
    status: str
    error_message: str | None = None


@router.post("/api/jobs", response_model=JobStatusResponse, status_code=201)
async def create_job(body: IngestRequest) -> JobStatusResponse:
    recording_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO recordings (recording_id, status, ingestion_source, source_url, judge_model, url_provider)
            VALUES ($1, 'pending', $2, $3, $4, $5)
            """,
            recording_id,
            body.ingestion_source,
            body.source_url,
            body.judge_model,
            body.url_provider,
        )
    return JobStatusResponse(recording_id=recording_id, status="pending")


@router.get("/api/jobs/{recording_id}", response_model=JobStatusResponse)
async def get_job(recording_id: str) -> JobStatusResponse:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT recording_id, status, error_message FROM recordings WHERE recording_id = $1",
            recording_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        recording_id=row["recording_id"],
        status=row["status"],
        error_message=row["error_message"],
    )
