# 6. Sprinklr Gen AI Router as the sole real Provider Adapter

Date: 2026-06-22

## Status

Accepted. Supersedes [ADR 0003](0003-litellm-library-sole-adapter.md).

## Context

Stakeholder direction: probe workers must call LLMs **only through the Sprinklr Gen AI Router** (`generateWithRequest`), not direct Azure / Bedrock / Vertex SDKs or LiteLLM. TTFB still requires **streaming** responses.

Direct cloud credentials and `target_endpoints` (api_base, deployment maps, etc.) are no longer owned by this project. Sprinklr supplies router URL, auth, `partnerId`, `provider`, `model`, `requestMetadata.src_env`, and `client_identifier`.

## Decision

1. **`GenAIRouterAdapter`** — single real adapter. POST streaming request to `GEN_AI_ROUTER_URL` with the router JSON envelope (`genAIRequest`, `partnerId`, `provider`).

2. **Catalog fields** (Sprinklr-owned values default to `??????` in prod):
   - Per model: `router_provider`, `router_model`, `partner_id`
   - Per pod (env): `SOURCE_REGION`, `REQUEST_SRC_ENV`, `GEN_AI_ROUTER_URL`, `GEN_AI_CLIENT_IDENTIFIER`, optional `GEN_AI_ROUTER_AUTH`
   - Catalog-level: `client_identifier` (removed — use `GEN_AI_CLIENT_IDENTIFIER` env)

3. **Env vars** on the collector pod:
   - `GEN_AI_ROUTER_URL` — required for real calls
   - `REQUEST_SRC_ENV` — router `src_env` for this pod
   - `GEN_AI_CLIENT_IDENTIFIER` — router client id for this pod
   - `GEN_AI_ROUTER_AUTH` — optional Authorization header

4. **Remove LiteLLM path** — delete `litellm_adapter.py`, `target_endpoints`, cloud credential docs, and `litellm` dependency.

5. **Keep `FakeProviderAdapter`** for local dev (`PROVIDER=fake`).

## Stakeholder answers (2026-06-22)

| # | Question | Answer | Implication |
|---|----------|--------|-------------|
| 1 | How called from qa6? | **HTTP POST only** (same `generateWithRequest` shape as curl) | Keep `httpx` POST; no separate SDK. URL/auth from pod env. |
| 2 | How to distinguish targets? (`provider` + `partnerId` only) | **Mapping will be provided** | Do not invent target routing. Wait for Sprinklr mapping; catalog `target_regions` → router fields TBD. UI can show `provider` / `partnerId` / `model` per sample until labels exist. |
| 3 | Streaming flag? | **Implicit** — no `stream: true` in request | Request body matches non-streaming curl; client still reads response as a stream for TTFB. |
| 4 | Sample output for first byte? | **Pending** | Replace `_chunk_has_content` guesswork with parser from real sample lines. |

## Consequences

- `PROVIDER=gen-ai-router` (aliases: `router`, `gen_ai_router`) selects the real adapter.
- Unconfigured Sprinklr fields fail fast with a clear client error (no fake placeholder calls).
- **Target matrix blocked** until mapping (Q2) lands — `COLLECT_TARGETS` may not change router payload yet.
- **Stream parser blocked** until sample output (Q4) lands.
- Open items: target mapping table, stream response sample, in-cluster router URL, auth scheme.

## Test strategy

Unit tests mock `httpx.AsyncClient.stream` — assert request body shape, streaming chunk parsing, and config validation without live router access.
