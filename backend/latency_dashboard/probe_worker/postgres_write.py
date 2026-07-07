from __future__ import annotations

import json
from datetime import datetime

from latency_dashboard.postgres_client import get_pool
from latency_dashboard.schemas import RunRecord


async def merge_run(run: RunRecord) -> None:
    """Upsert one atomic run row into latency_runs."""
    pool = await get_pool()
    collected_at = datetime.fromisoformat(run.collected_at)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO latency_runs (
                run_id, collected_at, source_region, target_id, model,
                config_version, n, timeout_ms, samples
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (run_id) DO UPDATE SET
                collected_at   = EXCLUDED.collected_at,
                source_region  = EXCLUDED.source_region,
                target_id      = EXCLUDED.target_id,
                model          = EXCLUDED.model,
                config_version = EXCLUDED.config_version,
                n              = EXCLUDED.n,
                timeout_ms     = EXCLUDED.timeout_ms,
                samples        = EXCLUDED.samples
            """,
            run.run_id,
            collected_at,
            run.source_region,
            run.target_id,
            run.model,
            run.config_version,
            run.n,
            run.timeout_ms,
            json.dumps(run.sample.model_dump()),
        )
