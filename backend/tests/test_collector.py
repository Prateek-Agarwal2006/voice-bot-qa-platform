from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from latency_dashboard.config import LLMConfigEntry, ProbeConfig
from latency_dashboard.schemas import RunRecord, Sample
from latency_dashboard.probe_worker.collection import CollectionScope
from latency_dashboard.probe_worker.collector import collect_once


def _config() -> ProbeConfig:
    return ProbeConfig(
        config_version="v1-test",
        source_region="eastus",
        prompt="Respond with the single word: ok",
        temperature=0,
        max_tokens=1,
        default_n=2,
        default_timeout_ms=5000,
        llm_configs=[
            LLMConfigEntry(target_id="cfg-a", label="Config A", deployment="model-a"),
            LLMConfigEntry(target_id="cfg-b", label="Config B", deployment="model-b"),
            LLMConfigEntry(target_id="cfg-c", label="Config C", deployment="model-c"),
        ],
    )


def _sample(target_id: str) -> Sample:
    return Sample(
        target_region=target_id,
        avg_ms=50.0, min_ms=40.0, p50_ms=50.0, p95_ms=60.0, max_ms=70.0,
        success_count=2, total_count=2, errors={},
    )


@pytest.mark.asyncio
async def test_collect_once_writes_one_run_per_target() -> None:
    scope = CollectionScope(interval_seconds=300, target_ids=["cfg-a", "cfg-b"])

    with patch(
        "latency_dashboard.probe_worker.collector.run_measurement",
        new=AsyncMock(side_effect=lambda **kwargs: _sample(kwargs["target_id"])),
    ), patch("latency_dashboard.probe_worker.collector.merge_run") as mock_merge:
        await collect_once(config=_config(), scope=scope)

    assert mock_merge.call_count == 2
    records: list[RunRecord] = [call.args[0] for call in mock_merge.call_args_list]
    assert {r.target_id for r in records} == {"cfg-a", "cfg-b"}
    assert {r.model for r in records} == {"model-a", "model-b"}
    for r in records:
        assert r.source_region == "eastus"
        assert r.run_id
        assert r.collected_at
        assert r.n == 2
        assert r.timeout_ms == 5000
        assert r.sample.target_region == r.target_id
