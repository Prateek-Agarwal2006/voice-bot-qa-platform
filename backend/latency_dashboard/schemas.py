from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Sample(BaseModel):
    """Aggregate stats for one (Run, target). Worker produces it; API serves it."""
    target_region: str
    target_label: str = ""
    avg_ms: Optional[float]
    min_ms: Optional[float]
    p50_ms: Optional[float]
    p95_ms: Optional[float]
    max_ms: Optional[float]
    success_count: int
    total_count: int
    errors: Dict[str, int]


class RunRecord(BaseModel):
    """One atomic DB row — Probe Worker → Postgres."""
    run_id: str
    source_region: str
    target_id: str
    model: str
    config_version: str
    n: int
    timeout_ms: int
    collected_at: str
    sample: Sample


class RunDTO(BaseModel):
    """Assembled run — Postgres → React."""
    id: str
    created_at: str
    model: str
    model_label: str
    source_region: str
    source_label: str
    config_version: str
    n: int
    timeout_ms: int
    samples: List[Sample]


class StageEventDTO(BaseModel):
    """One pipeline stage for the UI timeline — recording_stage_events → API."""
    stage: str
    state: str  # completed | active | failed
    label: str
    detail: Optional[str] = None
    at: str


class RecordingDTO(BaseModel):
    """Job status + metadata — recordings table → API."""
    recording_id: str
    status: str
    ingestion_source: str
    source_url: Optional[str] = None
    source_filename: Optional[str] = None
    judge_model: str = "gpt-4o-mini"
    url_provider: str = "direct"
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    stages: List[StageEventDTO] = []


class ConversationDTO(BaseModel):
    """Structured turns + derived signals — conversations table → API."""
    recording_id: str
    turns: List[Any]
    derived_signals: Dict[str, Any]
    turn_count: int


class EvaluationDTO(BaseModel):
    """Judge scores per dimension — evaluations table → API."""
    recording_id: str
    judge_model: str
    dimensions: Dict[str, Any]
    evaluated_at: str
