from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from latency_dashboard.db_migrate import ensure_source_filename_column, ensure_stage_events_table
from latency_dashboard.orchestrator.eval_routes import router as eval_router
from latency_dashboard.orchestrator.jobs_routes import router as jobs_router
from latency_dashboard.orchestrator.probe_routes import router as probe_router
from latency_dashboard.orchestrator.upload_storage import cleanup_orphaned_uploads, ensure_upload_dir
from latency_dashboard.postgres_client import close_pool, get_pool


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_upload_dir()
    removed = cleanup_orphaned_uploads()
    if removed:
        print(f"[orchestrator] removed {removed} orphaned staged upload(s)", flush=True)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await ensure_stage_events_table(conn)
        await ensure_source_filename_column(conn)
    yield
    await close_pool()


app = FastAPI(title="Voice Bot QA Platform — Orchestrator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(probe_router)
app.include_router(eval_router)
app.include_router(jobs_router)
