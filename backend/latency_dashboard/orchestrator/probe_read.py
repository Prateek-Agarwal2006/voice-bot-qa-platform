from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from latency_dashboard.config import ProbeConfig, get_llm_config_label, get_source_label, load_config
from latency_dashboard.postgres_client import get_pool
from latency_dashboard.schemas import RunDTO, Sample


# ── row type ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AtomicRunRow:
    run_id: str
    collected_at: str
    source_region: str
    target_id: str
    model: str
    config_version: str
    n: int
    timeout_ms: int
    sample: Sample


# ── assembly ───────────────────────────────────────────────────────────────────

def snapshot_id(*, source_region: str, model: str) -> str:
    return f"{source_region}::{model}"


def _assemble(rows: list[AtomicRunRow], *, config: ProbeConfig, limit: int) -> list[RunDTO]:
    groups: dict[tuple[str, str], list[AtomicRunRow]] = {}
    for row in rows:
        key = (row.source_region, row.model)
        groups.setdefault(key, []).append(row)

    snapshots: list[RunDTO] = []
    for (source_region, model), group_rows in groups.items():
        latest_collected_at = max(row.collected_at for row in group_rows)
        samples = sorted(group_rows, key=lambda r: r.sample.target_label)
        snapshots.append(
            RunDTO(
                id=snapshot_id(source_region=source_region, model=model),
                created_at=latest_collected_at,
                model=model,
                model_label=model,
                source_region=source_region,
                source_label=get_source_label(config, source_region),
                config_version=group_rows[0].config_version,
                n=group_rows[0].n,
                timeout_ms=group_rows[0].timeout_ms,
                samples=[r.sample for r in samples],
            )
        )

    snapshots.sort(key=lambda run: run.created_at, reverse=True)
    return snapshots[:limit]


# ── DB read ────────────────────────────────────────────────────────────────────

def _parse_sample(raw: Any, *, target_id: str, config: ProbeConfig) -> Sample:
    if isinstance(raw, str):
        raw = json.loads(raw)
    item: dict[str, Any] = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, dict) else {})
    return Sample(
        target_region=item.get("target_region", target_id),
        target_label=get_llm_config_label(config, target_id),
        avg_ms=item.get("avg_ms"),
        min_ms=item.get("min_ms"),
        p50_ms=item.get("p50_ms"),
        p95_ms=item.get("p95_ms"),
        max_ms=item.get("max_ms"),
        success_count=item.get("success_count", 0),
        total_count=item.get("total_count", 0),
        errors=item.get("errors") or {},
    )


async def _fetch_rows(
    *,
    source_region: Optional[str] = None,
    model: Optional[str] = None,
) -> list[AtomicRunRow]:
    config = load_config()
    pool = await get_pool()

    conditions: list[str] = []
    params: list[Any] = []

    if source_region:
        params.append(source_region)
        conditions.append(f"source_region = ${len(params)}")
    if model:
        params.append(model)
        conditions.append(f"model = ${len(params)}")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # DISTINCT ON replaces Snowflake's QUALIFY ROW_NUMBER() OVER (PARTITION BY ...)
    sql = f"""
    SELECT run_id, collected_at, source_region, target_id, model,
           config_version, n, timeout_ms, samples
    FROM (
        SELECT DISTINCT ON (source_region, model, target_id)
            run_id, collected_at, source_region, target_id, model,
            config_version, n, timeout_ms, samples
        FROM latency_runs
        {where}
        ORDER BY source_region, model, target_id, collected_at DESC
    ) latest
    ORDER BY collected_at DESC
    """

    async with pool.acquire() as conn:
        db_rows = await conn.fetch(sql, *params)

    result: list[AtomicRunRow] = []
    for row in db_rows:
        collected_at = row["collected_at"]
        if hasattr(collected_at, "isoformat"):
            collected_at = collected_at.isoformat()
        result.append(
            AtomicRunRow(
                run_id=row["run_id"],
                collected_at=str(collected_at),
                source_region=row["source_region"],
                target_id=row["target_id"],
                model=row["model"],
                config_version=row["config_version"],
                n=int(row["n"]),
                timeout_ms=int(row["timeout_ms"]),
                sample=_parse_sample(row["samples"], target_id=row["target_id"], config=config),
            )
        )
    return result


# ── public API ─────────────────────────────────────────────────────────────────

async def list_runs(
    *,
    limit: int = 50,
    source_region: Optional[str] = None,
    model: Optional[str] = None,
) -> list[RunDTO]:
    config = load_config()
    rows = await _fetch_rows(source_region=source_region, model=model)
    return _assemble(rows, config=config, limit=limit)


async def get_run(run_id: str) -> RunDTO | None:
    if "::" not in run_id:
        return None
    source_region, model = run_id.split("::", 1)
    config = load_config()
    rows = await _fetch_rows(source_region=source_region, model=model)
    snapshots = _assemble(rows, config=config, limit=1)
    if not snapshots:
        return None
    snapshot = snapshots[0]
    if snapshot.id != snapshot_id(source_region=source_region, model=model):
        return None
    return snapshot
