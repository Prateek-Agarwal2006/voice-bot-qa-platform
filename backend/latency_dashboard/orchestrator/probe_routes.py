from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from latency_dashboard.config import load_config, resolve_config_path
from latency_dashboard.orchestrator.probe_read import get_run, list_runs
from latency_dashboard.schemas import RunDTO

router = APIRouter()


@router.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/config")
async def get_config() -> dict:
    data = load_config()
    return {
        "config_version": data.config_version,
        "config_path": str(resolve_config_path()),
        "default_n": data.default_n,
        "default_timeout_ms": data.default_timeout_ms,
        "llm_configs": [entry.model_dump() for entry in data.llm_configs],
    }


@router.get("/api/runs", response_model=list[RunDTO])
async def runs(
    limit: int = 50,
    source_region: Optional[str] = None,
    model: Optional[str] = None,
) -> list[RunDTO]:
    return await list_runs(limit=limit, source_region=source_region, model=model)


@router.get("/api/runs/{run_id}", response_model=RunDTO)
async def run_detail(run_id: str) -> RunDTO:
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
