# 3. LiteLLM library as the sole real Provider Adapter

Date: 2026-06-19

## Status

Superseded by [ADR 0006](0006-gen-ai-router-adapter.md) (2026-06-22). Real calls use the Sprinklr Gen AI Router, not LiteLLM.

## Context

The probe must call hosted LLMs on Azure, AWS Bedrock, and GCP Vertex through one interface. Hand-writing a separate SDK adapter per cloud duplicates translation logic. Industry tools (LiteLLM, Portkey, Bifrost) solve provider normalization; we chose **LiteLLM as a Python library** inside the probe worker (not a separate proxy server) to avoid an extra network hop for synthetic probes.

Multi-region measurement splits into two dimensions: **source region** (where the probe worker runs — ADR 0001) and **target region** (which regional LLM endpoint is called). LiteLLM handles target routing via per-call parameters; source routing remains orchestrator → regional probe worker.

## Decision

Use a single **`LiteLLMProviderAdapter`** for all real provider calls. Azure, Bedrock, and Vertex are configured via **`catalog.json`** (`target_endpoints`, model entries) and environment credentials — no per-cloud adapter files.

Keep **`FakeProviderAdapter`** for local dev and tests without credentials.

Remove/replace hand-written provider adapters (e.g. `azure.py`) when LiteLLM is implemented.

Implementation follows **grill → test → code → test → push**; this ADR records the decision only.

## Considered options

- **B — LiteLLM for Azure only, hand-write Bedrock/Vertex later:** Rejected; duplicates work as soon as the second cloud is added.
- **C — Stay on custom `azure.py` until creds land:** Rejected; delays the unified multi-cloud shape we need anyway.
- **LiteLLM proxy server:** Rejected for the probe path; extra infra and latency without benefit for on-demand benchmarking.

## Consequences

- `ProviderAdapter` seam in `base.py` stays stable; only the implementation swaps.
- `catalog.json` gains **`target_endpoints`** mapping target region → LiteLLM model params (`api_base`, deployment, provider-specific fields).
- `target_region` in `measure_ttfb` becomes meaningful for real calls (no longer ignored).
- Orchestrator, worker, `probe.py`, schemas, and UI unchanged.

## Test strategy (Decision 15)

First implementation slice uses **unit tests with mocked `litellm.acompletion`** — no credentials required. Tests assert target-region routing, streaming success, and error mapping before the adapter exists (RED), then drive implementation (GREEN).
