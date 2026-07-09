from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from latency_dashboard.orchestrator.stage_read import fetch_stages_for_recording
from latency_dashboard.orchestrator.upload_storage import (
    delete_staged,
    internal_audio_url,
    save_staged,
    staged_exists,
    staged_path,
    validate_extension,
)
from latency_dashboard.postgres_client import get_pool
from latency_dashboard.schemas import StageEventDTO

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
    stages: list[StageEventDTO] = []


@router.post("/api/jobs", response_model=JobStatusResponse, status_code=201)
async def create_job(body: IngestRequest) -> JobStatusResponse:
    recording_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
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
            await conn.execute(
                """
                INSERT INTO recording_stage_events (recording_id, stage)
                VALUES ($1, 'pending')
                """,
                recording_id,
            )
        stages = await fetch_stages_for_recording(
            conn,
            recording_id,
            current_status="pending",
        )
    return JobStatusResponse(
        recording_id=recording_id,
        status="pending",
        stages=stages,
    )


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
        stages = await fetch_stages_for_recording(
            conn,
            recording_id,
            current_status=row["status"],
            error_message=row["error_message"],
        )
    return JobStatusResponse(
        recording_id=row["recording_id"],
        status=row["status"],
        error_message=row["error_message"],
        stages=stages,
    )


@router.post("/api/jobs/upload", response_model=JobStatusResponse, status_code=201)
async def create_upload_job(
    file: UploadFile = File(...),
    judge_model: str = Form("gpt-4o-mini"),
) -> JobStatusResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    try:
        validate_extension(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    recording_id = str(uuid.uuid4())
    source_url = internal_audio_url(recording_id)
    save_staged(recording_id, data)

    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO recordings (
                        recording_id, status, ingestion_source, source_url,
                        judge_model, url_provider, source_filename
                    )
                    VALUES ($1, 'pending', 'upload', $2, $3, 'direct', $4)
                    """,
                    recording_id,
                    source_url,
                    judge_model,
                    file.filename,
                )
                await conn.execute(
                    """
                    INSERT INTO recording_stage_events (recording_id, stage)
                    VALUES ($1, 'pending')
                    """,
                    recording_id,
                )
            stages = await fetch_stages_for_recording(
                conn,
                recording_id,
                current_status="pending",
            )
    except Exception:
        delete_staged(recording_id)
        raise

    return JobStatusResponse(
        recording_id=recording_id,
        status="pending",
        stages=stages,
    )


@router.get("/api/jobs/{recording_id}/audio")
async def get_staged_audio(recording_id: str) -> FileResponse:
    if not staged_exists(recording_id):
        raise HTTPException(status_code=404, detail="Staged audio not found")
    return FileResponse(
        path=staged_path(recording_id),
        media_type="application/octet-stream",
        filename=f"{recording_id}.audio",
    )


@router.delete("/api/jobs/{recording_id}/audio", status_code=204)
async def delete_staged_audio(recording_id: str) -> Response:
    delete_staged(recording_id)
    return Response(status_code=204)
