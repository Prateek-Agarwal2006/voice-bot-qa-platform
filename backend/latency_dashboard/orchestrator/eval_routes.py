from __future__ import annotations

from fastapi import APIRouter, HTTPException

from latency_dashboard.orchestrator.eval_read import (
    get_conversation,
    get_evaluation,
    list_recordings,
)
from latency_dashboard.schemas import ConversationDTO, EvaluationDTO, RecordingDTO

router = APIRouter()


@router.get("/api/evaluations", response_model=list[RecordingDTO])
async def evaluations(limit: int = 50, status: str | None = None) -> list[RecordingDTO]:
    return await list_recordings(limit=limit, status=status)


@router.get("/api/evaluations/{recording_id}/conversation", response_model=ConversationDTO)
async def conversation(recording_id: str) -> ConversationDTO:
    result = await get_conversation(recording_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@router.get("/api/evaluations/{recording_id}/scores", response_model=EvaluationDTO)
async def scores(recording_id: str) -> EvaluationDTO:
    result = await get_evaluation(recording_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return result
