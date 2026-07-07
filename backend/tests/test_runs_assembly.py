from __future__ import annotations

import pytest

from latency_dashboard.config import LLMConfigEntry, ProbeConfig
from latency_dashboard.orchestrator.probe_read import AtomicRunRow, _assemble, snapshot_id
from latency_dashboard.schemas import Sample


def _config() -> ProbeConfig:
    return ProbeConfig(
        config_version="v1-test",
        source_region="prod4",
        prompt="ok",
        temperature=0,
        max_tokens=1,
        llm_configs=[
            LLMConfigEntry(target_id="cfg-a", label="Config A"),
            LLMConfigEntry(target_id="cfg-b", label="Config B"),
        ],
    )


def _sample(target_id: str, *, avg_ms: float) -> Sample:
    return Sample(
        target_region=target_id,
        target_label=target_id.upper(),
        avg_ms=avg_ms, min_ms=avg_ms, p50_ms=avg_ms, p95_ms=avg_ms, max_ms=avg_ms,
        success_count=10, total_count=10, errors={},
    )


def test_snapshot_id_format() -> None:
    assert snapshot_id(source_region="prod4", model="gpt-4.1") == "prod4::gpt-4.1"


def test_assemble_groups_latest_targets() -> None:
    rows = [
        AtomicRunRow(
            run_id="1", collected_at="2026-06-22T10:00:00+00:00",
            source_region="prod4", target_id="cfg-a", model="gpt-4.1",
            config_version="v1", n=10, timeout_ms=10000,
            sample=_sample("cfg-a", avg_ms=100.0),
        ),
        AtomicRunRow(
            run_id="2", collected_at="2026-06-22T10:00:01+00:00",
            source_region="prod4", target_id="cfg-b", model="gpt-4.1",
            config_version="v1", n=10, timeout_ms=10000,
            sample=_sample("cfg-b", avg_ms=200.0),
        ),
    ]

    snapshots = _assemble(rows, config=_config(), limit=10)

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.id == "prod4::gpt-4.1"
    assert snapshot.source_region == "prod4"
    assert snapshot.model == "gpt-4.1"
    assert len(snapshot.samples) == 2
    assert {s.target_region for s in snapshot.samples} == {"cfg-a", "cfg-b"}
