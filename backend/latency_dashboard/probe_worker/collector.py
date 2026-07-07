from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

from latency_dashboard.config import ProbeConfig, get_llm_config, get_stored_model, load_config
from latency_dashboard.schemas import RunRecord
from latency_dashboard.probe_worker.collection import CollectionScope, resolve_collection_scope
from latency_dashboard.probe_worker.probe import CallPayload, run_measurement
from latency_dashboard.probe_worker.postgres_write import merge_run


async def collect_once(*, config: ProbeConfig, scope: CollectionScope) -> None:
    payload = CallPayload(
        prompt=config.prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    collected_at = datetime.now(timezone.utc).isoformat()

    for target_id in scope.target_ids:
        entry = get_llm_config(config, target_id)
        sample = await run_measurement(
            config=config,
            target_id=target_id,
            source_region=config.source_region,
            payload=payload,
            n=config.default_n,
            timeout_ms=config.default_timeout_ms,
        )
        await merge_run(
            RunRecord(
                run_id=str(uuid.uuid4()),
                source_region=config.source_region,
                target_id=target_id,
                model=get_stored_model(entry),
                config_version=config.config_version,
                n=config.default_n,
                timeout_ms=config.default_timeout_ms,
                collected_at=collected_at,
                sample=sample,
            )
        )


async def run_collector(*, once: bool = False) -> None:
    config = load_config()
    scope = resolve_collection_scope(config)

    while True:
        await collect_once(config=config, scope=scope)
        if once:
            return
        await asyncio.sleep(scope.interval_seconds)


def main() -> None:
    once = os.getenv("COLLECT_ONCE", "").lower() in {"1", "true", "yes"}
    asyncio.run(run_collector(once=once))


if __name__ == "__main__":
    main()
