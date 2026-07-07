from __future__ import annotations

from dataclasses import dataclass

from latency_dashboard.config import ProbeConfig, get_llm_config


@dataclass(frozen=True)
class CollectionScope:
    interval_seconds: int
    target_ids: list[str]


def resolve_collection_scope(config: ProbeConfig) -> CollectionScope:
    if config.collect_llm_configs:
        target_ids = []
        for target_id in config.collect_llm_configs:
            get_llm_config(config, target_id)
            target_ids.append(target_id)
    else:
        target_ids = [entry.target_id for entry in config.llm_configs]

    return CollectionScope(
        interval_seconds=config.collect_interval_seconds,
        target_ids=target_ids,
    )
