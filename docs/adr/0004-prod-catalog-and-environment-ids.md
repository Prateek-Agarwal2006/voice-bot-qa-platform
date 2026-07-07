# ADR 0004: Production catalog and environment IDs

## Status

Accepted (partially superseded). Worker URLs and `target_endpoints` removed in ADR 0005; LiteLLM routing superseded by ADR 0006. Prod IDs and dual-catalog layout remain.

## Context

Production stacks are named `prod`, `prod2`, … (not cloud region codes alone). Multiple prods share a region (`prod`, `prod6`, `prod12` in `us-east-1`). Models differ per cloud (Azure, Bedrock, Vertex).

## Decisions

1. **Primary IDs** — prod names (`prod2`) with metadata: `cloud`, `region_code`, `provider`, optional `env_type`.
2. **Separate catalogs** — `config/catalog.json` (fake dev) and `config/catalog.prod.json` (real prods), selected via `CATALOG_PATH`.
3. **Full matrix** — all 13 prods in `target_regions`; separate models per cloud; source comes from pod `SOURCE_REGION`; UI compares runs by stored source id/label.
4. **Worker URLs** — `worker_url_env` per prod (e.g. `PROBE_WORKER_URL_PROD2`); resolved at orchestrator run time.
5. **Seed models** — `azure-gpt-4o-mini`, `bedrock-claude-haiku`, `vertex-gemini-flash` with placeholder deployment IDs.

## Consequences

- `TargetEndpointConfig` gains `provider`, AWS and Vertex fields.
- `LiteLLMProviderAdapter` routes Azure / Bedrock / Vertex from `target_endpoints`.
- Operators set env vars for endpoints, keys, worker URLs, and deployment names before real runs.
