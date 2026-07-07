from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from latency_dashboard.config import LLMConfigEntry, ProbeConfig
from latency_dashboard.probe_worker.probe import (
    CallErrorKind,
    CallFailure,
    CallPayload,
    CallSuccess,
    GenAIRouterAdapter,
)


def _config() -> ProbeConfig:
    return ProbeConfig(
        config_version="v1-test",
        source_region="prod4",
        prompt="Respond with the single word: ok",
        temperature=0,
        max_tokens=1,
        llm_configs=[
            LLMConfigEntry(
                target_id="spain-central-dz-gpt41",
                label="Spain Central · GPT-4.1",
                streamEnabled=False,
                group="PRATHAM_23_JUN_SPAIN_CENTRAL_DATAZONE_AZURE_4_1_TEST",
                deployment="gpt-4.1-2025-04-14-spaincentral-datazone-standard",
                provider="AZURE_OPEN_AI",
                llm_config_id="6a3a550ec0c3ec15cdd089a5",
                partnerId=16000011,
                useDynamicRouting=False,
                routerUrl="https://router.example/generateWithRequest",
                client_identifier="backend-platform-dev",
                user="latency-probe",
            ),
        ],
    )


SIR_NON_STREAM_RESPONSE = {
    "type": "chat-completion",
    "trackingParams": {"statusCode": 200, "responseHeaders": {"azureai-fe-is-streaming": ["False"]}},
    "streaming": False,
    "trackingInfo": {
        "CHOICES": [{"message": {"role": "assistant", "content": "Hallo!"}, "index": 0, "finish_reason": "stop"}]
    },
    "response": {
        "choices": [{"message": {"role": "assistant", "content": "Hallo!"}, "index": 0, "finish_reason": "stop"}]
    },
}


class _MockStreamResponse:
    status_code = 200
    request = httpx.Request("POST", "https://router.example/generate")

    async def aread(self) -> bytes:
        return b""

    async def aiter_lines(self) -> AsyncIterator[str]:
        yield 'data: {"response":{"choices":[{"delta":{"content":"ok"}}]}}'


class _MockStreamContext:
    async def __aenter__(self) -> _MockStreamResponse:
        return _MockStreamResponse()

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_measure_ttfb_builds_sir_request_shape() -> None:
    adapter = GenAIRouterAdapter(_config())
    captured: dict[str, Any] = {}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.request = httpx.Request("POST", "https://router.example/generateWithRequest")
    mock_response.json.return_value = SIR_NON_STREAM_RESPONSE

    async def fake_post(*args: Any, **kwargs: Any) -> MagicMock:
        captured["json"] = kwargs.get("json")
        return mock_response

    mock_client = MagicMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("latency_dashboard.probe_worker.probe.httpx.AsyncClient", return_value=mock_client):
        result = await adapter.measure_ttfb(
            target_id="spain-central-dz-gpt41",
            source_region="prod4",
            payload=CallPayload(prompt="Respond with the single word: ok", temperature=0, max_tokens=1),
            timeout_ms=5000,
        )

    assert isinstance(result, CallSuccess)
    body = captured["json"]
    assert body["provider"] == "AZURE_OPEN_AI"
    assert body["partnerId"] == 16000011
    assert body["llm_config_id"] == "6a3a550ec0c3ec15cdd089a5"
    assert body["useDynamicRouting"] is False
    assert body["stream"] is False
    assert body["genAIRequest"]["type"] == "chat-completion"
    assert body["genAIRequest"]["request"]["model"] == "gpt-4.1-2025-04-14-spaincentral-datazone-standard"
    assert body["genAIRequest"]["request"]["stream"] is False
    assert body["genAIRequest"]["requestMetadata"]["ST_group"] == "PRATHAM_23_JUN_SPAIN_CENTRAL_DATAZONE_AZURE_4_1_TEST"
    assert body["genAIRequest"]["requestMetadata"]["client_identifier"] == "backend-platform-dev"
    assert "src_env" not in body["genAIRequest"]["requestMetadata"]


@pytest.mark.asyncio
async def test_measure_ttfb_parses_sir_non_stream_response() -> None:
    adapter = GenAIRouterAdapter(_config())

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.request = httpx.Request("POST", "https://router.example/generateWithRequest")
    mock_response.json.return_value = SIR_NON_STREAM_RESPONSE

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("latency_dashboard.probe_worker.probe.httpx.AsyncClient", return_value=mock_client):
        result = await adapter.measure_ttfb(
            target_id="spain-central-dz-gpt41",
            source_region="prod4",
            payload=CallPayload(prompt="ok", temperature=0, max_tokens=1),
            timeout_ms=5000,
        )

    assert isinstance(result, CallSuccess)


@pytest.mark.asyncio
async def test_measure_ttfb_streams_first_chunk() -> None:
    config = _config().model_copy(update={
        "llm_configs": [_config().llm_configs[0].model_copy(update={"streamEnabled": True})]
    })
    adapter = GenAIRouterAdapter(config)
    captured: dict[str, Any] = {}

    def fake_stream(*args: Any, **kwargs: Any) -> _MockStreamContext:
        captured["json"] = kwargs.get("json")
        return _MockStreamContext()

    mock_client = MagicMock()
    mock_client.stream = fake_stream
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("latency_dashboard.probe_worker.probe.httpx.AsyncClient", return_value=mock_client):
        result = await adapter.measure_ttfb(
            target_id="spain-central-dz-gpt41",
            source_region="prod4",
            payload=CallPayload(prompt="ok", temperature=0, max_tokens=1),
            timeout_ms=5000,
        )

    assert isinstance(result, CallSuccess)
    assert captured["json"]["stream"] is True
    assert captured["json"]["genAIRequest"]["request"]["stream"] is True
    assert captured["json"]["genAIRequest"]["request"]["streamOptions"] == {"include_usage": True}


@pytest.mark.asyncio
async def test_measure_ttfb_rejects_unconfigured_router_url() -> None:
    config = _config().model_copy(update={
        "llm_configs": [_config().llm_configs[0].model_copy(update={"routerUrl": "??????"})]
    })
    result = await GenAIRouterAdapter(config).measure_ttfb(
        target_id="spain-central-dz-gpt41",
        source_region="prod4",
        payload=CallPayload(prompt="ok", temperature=0, max_tokens=1),
        timeout_ms=5000,
    )
    assert isinstance(result, CallFailure)
    assert result.kind == CallErrorKind.CLIENT
    assert "routerUrl" in result.message


@pytest.mark.asyncio
async def test_measure_ttfb_rejects_placeholder_config_fields() -> None:
    config = ProbeConfig(
        config_version="v1-test",
        source_region="prod4",
        prompt="ok",
        temperature=0,
        max_tokens=1,
        llm_configs=[LLMConfigEntry(target_id="missing", label="Missing", routerUrl="https://router.example/generate")],
    )
    result = await GenAIRouterAdapter(config).measure_ttfb(
        target_id="missing",
        source_region="prod4",
        payload=CallPayload(prompt="ok", temperature=0, max_tokens=1),
        timeout_ms=5000,
    )
    assert isinstance(result, CallFailure)
    assert result.kind == CallErrorKind.CLIENT
    assert "??????" in result.message
