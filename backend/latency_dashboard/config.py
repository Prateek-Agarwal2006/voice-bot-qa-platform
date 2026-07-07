from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel, Field

SPRINKLR_PLACEHOLDER = "??????"


class LLMConfigEntry(BaseModel):
    """One routable LLM backend — all router fields live on the entry."""

    target_id: str
    label: str
    streamEnabled: bool = False
    group: str = SPRINKLR_PLACEHOLDER
    # Router request model today. Snowflake `model` column is written from this until
    # we add an optional logical `model` field when deployment != dashboard model.
    deployment: str = SPRINKLR_PLACEHOLDER
    provider: str = SPRINKLR_PLACEHOLDER
    llm_config_id: str = SPRINKLR_PLACEHOLDER
    partnerId: Union[int, str] = SPRINKLR_PLACEHOLDER
    useDynamicRouting: bool = False
    routerUrl: str = SPRINKLR_PLACEHOLDER
    routerAuth: Optional[str] = None
    client_identifier: str = SPRINKLR_PLACEHOLDER
    user: str = "latency-probe"
    streamOptions: dict[str, Any] = Field(default_factory=lambda: {"include_usage": True})
    CASE_NUMBER: Optional[int] = None
    ST_FEATURE_ID: Optional[str] = None


class ProbeConfig(BaseModel):
    config_version: str
    source_region: str
    prompt: str
    temperature: float
    max_tokens: int
    default_n: int = 10
    default_timeout_ms: int = 10000
    collect_interval_seconds: int = 300
    collect_llm_configs: list[str] = Field(default_factory=list)
    provider: str = "fake"
    llm_configs: list[LLMConfigEntry] = Field(default_factory=list)
    region_latency_ms: dict[str, dict[str, int]] = Field(default_factory=dict)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_config_path(path: Optional[str] = None) -> Path:  #path optional if given use it else use the env variable CONFIG_PATH 
    if path:
        config_path = Path(path)
    else:
        env_path = os.getenv("CONFIG_PATH")
        if env_path:
            config_path = Path(env_path)
        else:
            return _project_root() / "config" / "config.json"

    if not config_path.is_absolute():
        config_path = _project_root() / config_path
    return config_path


@lru_cache
def _load_config_cached(path_str: str, mtime_ns: int) -> ProbeConfig: #path_str: path to the config file, mtime_ns: modification time of the config file , this is used to cache the config file so that we don't have to load it from the file system every time
    del mtime_ns
    data = json.loads(Path(path_str).read_text())
    return ProbeConfig.model_validate(data)   #return the ProbeConfig object


def load_config(path: Optional[str] = None) -> ProbeConfig:
    config_path = resolve_config_path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config not found: {config_path}")
    mtime_ns = config_path.stat().st_mtime_ns
    return _load_config_cached(str(config_path.resolve()), mtime_ns)


def get_llm_config(config: ProbeConfig, target_id: str) -> LLMConfigEntry:
    for entry in config.llm_configs:
        if entry.target_id == target_id:
            return entry
    raise KeyError(f"Unknown target_id: {target_id}")


def get_llm_config_label(config: ProbeConfig, target_id: str) -> str:
    try:
        return get_llm_config(config, target_id).label
    except KeyError:
        return target_id


def get_stored_model(entry: LLMConfigEntry) -> str:
    """Value written to the runs `model` column; uses deployment until logical model exists."""
    return entry.deployment


def get_source_label(config: ProbeConfig, source_region_id: str) -> str:
    del config
    return source_region_id
