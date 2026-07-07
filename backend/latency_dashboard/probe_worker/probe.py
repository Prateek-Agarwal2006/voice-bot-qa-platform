from __future__ import annotations

import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

import httpx

from latency_dashboard.config import (
    LLMConfigEntry,
    ProbeConfig,
    SPRINKLR_PLACEHOLDER,
    get_llm_config,
)
from latency_dashboard.schemas import Sample


# ── call result types ──────────────────────────────────────────────────────────

class CallErrorKind(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "429"
    SERVER = "5xx"
    CLIENT = "4xx"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CallPayload:
    prompt: str
    temperature: float
    max_tokens: int


@dataclass(frozen=True)
class CallSuccess:
    ttfb_ms: float


@dataclass(frozen=True)
class CallFailure:
    kind: CallErrorKind
    message: str


CallResult = Union[CallSuccess, CallFailure]


def _exception_to_failure(exc: Exception) -> CallFailure:
    message = str(exc)
    lowered = message.lower()
    if "429" in message or "rate limit" in lowered:
        return CallFailure(kind=CallErrorKind.RATE_LIMIT, message=message)
    if "timeout" in lowered or "timed out" in lowered:
        return CallFailure(kind=CallErrorKind.TIMEOUT, message=message)
    if "500" in message or "502" in message or "503" in message:
        return CallFailure(kind=CallErrorKind.SERVER, message=message)
    if "400" in message or "401" in message or "403" in message or "404" in message:
        return CallFailure(kind=CallErrorKind.CLIENT, message=message)
    return CallFailure(kind=CallErrorKind.UNKNOWN, message=message)


# ── internal raw types (never leave this module) ──────────────────────────────

@dataclass
class _RawCall:
    index: int
    success: bool
    ttfb_ms: float | None = None
    error_kind: str | None = None
    error_message: str | None = None


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _aggregate(calls: list[_RawCall], target_region: str) -> Sample:
    successes = [c.ttfb_ms for c in calls if c.success and c.ttfb_ms is not None]
    errors: dict[str, int] = {}
    for c in calls:
        if not c.success:
            key = c.error_kind or CallErrorKind.UNKNOWN.value
            errors[key] = errors.get(key, 0) + 1

    if not successes:
        return Sample(
            target_region=target_region,
            avg_ms=None, min_ms=None, p50_ms=None, p95_ms=None, max_ms=None,
            success_count=0,
            total_count=len(calls),
            errors=errors,
        )

    return Sample(
        target_region=target_region,
        avg_ms=statistics.mean(successes),
        min_ms=min(successes),
        p50_ms=_percentile(successes, 0.5),
        p95_ms=_percentile(successes, 0.95),
        max_ms=max(successes),
        success_count=len(successes),
        total_count=len(calls),
        errors=errors,
    )


# ── Gen AI Router ──────────────────────────────────────────────────────────────

_REQUIRED_FIELDS = (
    "routerUrl", "provider", "deployment", "llm_config_id",
    "partnerId", "group", "client_identifier",
)


class GenAIRouterAdapter:
    """Calls Sprinklr Gen AI Router (generateWithRequest)."""

    def __init__(self, config: ProbeConfig) -> None:
        self._config = config

    @staticmethod
    def _is_unconfigured(value: Optional[str]) -> bool:
        if value is None:
            return True
        stripped = str(value).strip()
        return not stripped or stripped == SPRINKLR_PLACEHOLDER

    @staticmethod
    def _resolve_partner_id(raw: Union[int, str]) -> Union[int, str]:
        if isinstance(raw, int):
            return raw
        if str(raw).isdigit():
            return int(raw)
        return raw

    @staticmethod
    def _build_headers(entry: LLMConfigEntry) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if entry.routerAuth and not GenAIRouterAdapter._is_unconfigured(entry.routerAuth):
            headers["Authorization"] = entry.routerAuth
        return headers

    def _build_request_body(self, entry: LLMConfigEntry, payload: CallPayload) -> dict[str, Any]:
        request_metadata: dict[str, Any] = {
            "ST_group": entry.group,
            "client_identifier": entry.client_identifier,
        }
        if entry.CASE_NUMBER is not None:
            request_metadata["CASE_NUMBER"] = entry.CASE_NUMBER
        if entry.ST_FEATURE_ID is not None:
            request_metadata["ST_FEATURE_ID"] = entry.ST_FEATURE_ID

        request: dict[str, Any] = {
            "model": entry.deployment,
            "n": 1,
            "temperature": payload.temperature,
            "messages": [{"role": "user", "content": payload.prompt}],
            "user": entry.user,
            "stream": entry.streamEnabled,
        }
        if entry.streamEnabled:
            request["streamOptions"] = entry.streamOptions

        return {
            "provider": entry.provider,
            "genAIRequest": {
                "type": "chat-completion",
                "request": request,
                "requestMetadata": request_metadata,
            },
            "partnerId": self._resolve_partner_id(entry.partnerId),
            "llm_config_id": entry.llm_config_id,
            "useDynamicRouting": entry.useDynamicRouting,
            "stream": entry.streamEnabled,
        }

    @staticmethod
    def _response_has_content(data: dict[str, Any]) -> bool:
        response = data.get("response")
        if isinstance(response, dict):
            choices = response.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    message = first.get("message")
                    if isinstance(message, dict) and message.get("content"):
                        return True
                    delta = first.get("delta")
                    if isinstance(delta, dict) and delta.get("content"):
                        return True
        tracking_info = data.get("trackingInfo")
        if isinstance(tracking_info, dict):
            choices = tracking_info.get("CHOICES")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    message = first.get("message")
                    if isinstance(message, dict) and message.get("content"):
                        return True
        return False

    @staticmethod
    def _chunk_has_content(raw_line: str) -> bool:
        line = raw_line.strip()
        if not line or line == "data: [DONE]":
            return False
        if line.startswith("data:"):
            line = line[5:].strip()
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            return bool(line)
        if isinstance(chunk, dict):
            return GenAIRouterAdapter._response_has_content(chunk)
        return False

    def _validate_entry(self, entry: LLMConfigEntry) -> CallFailure | None:
        for field_name in _REQUIRED_FIELDS:
            value = getattr(entry, field_name)
            if self._is_unconfigured(value if field_name != "partnerId" else str(value)):
                return CallFailure(
                    kind=CallErrorKind.CLIENT,
                    message=f"{field_name} is {SPRINKLR_PLACEHOLDER!r} — must be set on llm_configs entry",
                )
        return None

    async def _measure_non_stream(
        self, *, client: httpx.AsyncClient, entry: LLMConfigEntry,
        body: dict[str, Any], timeout_s: float,
    ) -> CallResult:
        started = time.perf_counter()
        response = await client.post(
            entry.routerUrl, json=body,
            headers=self._build_headers(entry), timeout=timeout_s,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if response.status_code >= 400:
            return _exception_to_failure(httpx.HTTPStatusError(
                f"HTTP {response.status_code}: {response.text}",
                request=response.request, response=response,
            ))
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            return CallFailure(kind=CallErrorKind.UNKNOWN, message=f"Invalid JSON response: {exc}")

        if self._response_has_content(data):
            return CallSuccess(ttfb_ms=elapsed_ms)
        return CallFailure(kind=CallErrorKind.UNKNOWN, message="Response missing choices[].message.content")

    async def _measure_stream(
        self, *, client: httpx.AsyncClient, entry: LLMConfigEntry,
        body: dict[str, Any], timeout_s: float,
    ) -> CallResult:
        started = time.perf_counter()
        async with client.stream(
            "POST", entry.routerUrl, json=body,
            headers=self._build_headers(entry), timeout=timeout_s,
        ) as response:
            if response.status_code >= 400:
                detail = (await response.aread()).decode("utf-8", errors="replace")
                return _exception_to_failure(httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {detail}",
                    request=response.request, response=response,
                ))
            async for line in response.aiter_lines():
                if self._chunk_has_content(line):
                    return CallSuccess(ttfb_ms=(time.perf_counter() - started) * 1000.0)
        return CallFailure(kind=CallErrorKind.UNKNOWN, message="Stream ended without content")

    async def measure_ttfb(
        self, *, target_id: str, source_region: str,
        payload: CallPayload, timeout_ms: int,
    ) -> CallResult:
        del source_region
        entry = get_llm_config(self._config, target_id)
        failure = self._validate_entry(entry)
        if failure:
            return failure

        body = self._build_request_body(entry, payload)
        timeout_s = timeout_ms / 1000.0
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                if entry.streamEnabled:
                    return await self._measure_stream(
                        client=client, entry=entry, body=body, timeout_s=timeout_s,
                    )
                return await self._measure_non_stream(
                    client=client, entry=entry, body=body, timeout_s=timeout_s,
                )
        except httpx.TimeoutException as exc:
            return CallFailure(kind=CallErrorKind.TIMEOUT, message=str(exc))
        except Exception as exc:  # noqa: BLE001
            return _exception_to_failure(exc)


# ── Fake adapter (kind / local dev — no real credentials needed) ───────────────

class _FakeAdapter:
    def __init__(self, config: ProbeConfig) -> None:
        self._config = config

    async def measure_ttfb(
        self, *, target_id: str, source_region: str,
        payload: CallPayload, timeout_ms: int,
    ) -> CallResult:
        del payload
        base = self._config.region_latency_ms.get(source_region, {}).get(target_id, 150)
        jitter = random.uniform(-0.15, 0.25)
        simulated_ms = max(5.0, base * (1.0 + jitter))

        roll = random.random()
        if roll < 0.03:
            return CallFailure(kind=CallErrorKind.RATE_LIMIT, message="Synthetic 429 from fake adapter")
        if roll < 0.05:
            return CallFailure(kind=CallErrorKind.SERVER, message="Synthetic 5xx from fake adapter")

        await asyncio.sleep(simulated_ms / 1000.0)
        if simulated_ms > timeout_ms:
            return CallFailure(kind=CallErrorKind.TIMEOUT, message=f"Exceeded timeout of {timeout_ms}ms")
        return CallSuccess(ttfb_ms=simulated_ms)


def _make_adapter(config: ProbeConfig) -> GenAIRouterAdapter | _FakeAdapter:
    if config.provider.lower() in {"gen-ai-router", "gen_ai_router", "router"}:
        return GenAIRouterAdapter(config)
    return _FakeAdapter(config)


# ── public entry point ─────────────────────────────────────────────────────────

async def run_measurement(
    *,
    config: ProbeConfig,
    target_id: str,
    source_region: str,
    payload: CallPayload,
    n: int,
    timeout_ms: int,
) -> Sample:
    """Run N TTFB calls against one target and return aggregate Sample."""
    adapter = _make_adapter(config)
    calls: list[_RawCall] = []

    for index in range(n):
        started = time.perf_counter()
        result = await adapter.measure_ttfb(
            target_id=target_id,
            source_region=source_region,
            payload=payload,
            timeout_ms=timeout_ms,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        if isinstance(result, CallSuccess):
            ttfb_ms = result.ttfb_ms if result.ttfb_ms > 0.0 else elapsed_ms
            calls.append(_RawCall(index=index + 1, success=True, ttfb_ms=ttfb_ms))
        elif isinstance(result, CallFailure):
            calls.append(_RawCall(
                index=index + 1, success=False,
                error_kind=result.kind.value, error_message=result.message,
            ))

    return _aggregate(calls, target_id)
