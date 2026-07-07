from __future__ import annotations

import pytest

from latency_dashboard.probe_worker.collection import resolve_collection_scope
from latency_dashboard.config import LLMConfigEntry, ProbeConfig


def _config(**overrides: object) -> ProbeConfig:
    base = dict(
        config_version="v1-test",
        source_region="eastus",
        prompt="ok",
        temperature=0,
        max_tokens=1,
        llm_configs=[
            LLMConfigEntry(target_id="cfg-a", label="Config A"),
            LLMConfigEntry(target_id="cfg-b", label="Config B"),
            LLMConfigEntry(target_id="cfg-c", label="Config C"),
        ],
    )
    base.update(overrides)
    return ProbeConfig(**base)


def test_resolve_scope_defaults_to_all_llm_configs() -> None:
    scope = resolve_collection_scope(_config())

    assert scope.interval_seconds == 300
    assert scope.target_ids == ["cfg-a", "cfg-b", "cfg-c"]


def test_resolve_scope_from_config_fields() -> None:
    scope = resolve_collection_scope(
        _config(collect_interval_seconds=120, collect_llm_configs=["cfg-a", "cfg-c"])
    )

    assert scope.interval_seconds == 120
    assert scope.target_ids == ["cfg-a", "cfg-c"]


def test_resolve_scope_rejects_unknown_llm_config() -> None:
    with pytest.raises(KeyError, match="Unknown target_id"):
        resolve_collection_scope(_config(collect_llm_configs=["missing-config"]))
