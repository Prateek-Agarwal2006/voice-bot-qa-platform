# Architecture & product decisions

Record of decisions taken for the Voice Bot QA Platform: what we chose, what we rejected, why, and trade-offs. Domain vocabulary lives in [`CONTEXT.md`](../CONTEXT.md).

---

## Problem statement

**Goal:** A unified platform that answers two complementary questions about a deployed voice bot:

1. **Is it fast?** — Measure TTFB across LLM Models and cloud regions continuously.
2. **Is it good?** — Score recorded Customer ↔ Voice Bot conversations across 7 quality dimensions using an LLM-as-judge.

Neither question alone is sufficient. A fast bot that gives wrong answers fails customers. A bot with excellent rubric scores that times out in production is unusable.

**Pipelines:**

```
Probe Workers   → probe LLM endpoints on schedule → latency_runs (Postgres)
Eval Workers    → download audio → Scribe → structure → judge → conversations + evaluations (Postgres)
Orchestrator    → read Postgres → serve React dashboard
```

---

## Decision summary

### Latency measurement (original platform)

| # | Decision | Choice | Status |
|---|----------|--------|--------|
| LD1 | Source region as data | Location-agnostic Probe; `SOURCE_REGION` from env | ✅ Locked — [ADR-0001](adr/0001-location-agnostic-probe.md) |
| LD2 | Worker trigger | Self-scheduled collection; no inbound dispatch | ✅ Locked — [ADR-0005](adr/0005-scheduled-collection-and-result-sink.md) |
| LD3 | Result transport | Result Sink seam (`RESULT_SINK` env); Postgres sink replaces Snowflake | ✅ Locked — [ADR-0005](adr/0005-scheduled-collection-and-result-sink.md) |
| LD4 | Real provider | Sprinklr Gen AI Router (not direct cloud SDKs) | ✅ Locked — [ADR-0006](adr/0006-gen-ai-router-adapter.md) |
| LD5 | UI exposure | nginx UI pod is sole external entry point; Orchestrator is ClusterIP only | ✅ Locked |

### Call evaluation (VoiceBotEval)

| # | Decision | Choice | Status |
|---|----------|--------|--------|
| VBE1 | Problem lane | Offline call QA on recordings (not simulation benchmarks) | ✅ Locked |
| VBE2 | Transcription | ElevenLabs Scribe v2 multichannel, word timestamps | ✅ Locked |
| VBE3 | Speaker separation | Stereo channels (L=Customer, R=Voice Bot); no diarization | ✅ Locked |
| VBE4 | Evaluation method | LLM-as-judge with rubrics (one Judge call per dimension) | ✅ Locked |
| VBE5 | Judge framework | DeepEval GEval + VoiceGEval subclass; voice-bot-first | ✅ Locked |
| VBE6 | Judge LLM provider | OpenAI / Anthropic / Google / Vertex AI via LiteLLM | ✅ Locked |

### Merged platform

| # | Decision | Choice | Status |
|---|----------|--------|--------|
| M1 | Platform direction | Latency Dashboard is base repo; VoiceBotEval absorbed into it | ✅ Locked |
| M2 | Database | Postgres only — replaces Snowflake and filesystem JSON | ✅ Locked |
| M3 | Snowflake migration | 4-file swap via existing Result Sink / read seams | ✅ Locked |
| M4 | URL-based ingestion | `recordings` table as Job queue; HTTP URLs first; SKIP LOCKED polling | ✅ Locked |
| M5 | Pod architecture | 4 pods: nginx UI + Orchestrator + Probe Worker(s) + Eval Worker(s) | ✅ Locked |
| M6 | Eval worker execution | Separate pod (not FastAPI background task) | ✅ Locked |
| M7 | Frontend | Extend Latency Dashboard React app; retire Streamlit | ✅ Locked |
| M8 | Result Sink abstraction | Removed — `collector.py` calls `postgres_write` directly; no `RESULT_SINK` env var | ✅ Locked |
| M9 | Provider Adapter abstraction | Removed — Gen AI Router + Fake folded into `probe.py`; no `ProviderAdapter` Protocol | ✅ Locked |
| M10 | `runs_store.py` passthrough layer | Removed — routes import `probe_read` directly; no intermediate store module | ✅ Locked |
| M11 | Eval completion notification | Postgres `LISTEN/NOTIFY` — Eval Worker notifies Orchestrator; Orchestrator pushes SSE to React | 🔜 Future work |

---

## LD1 — Location-agnostic Probe

See [ADR-0001](adr/0001-location-agnostic-probe.md).

**Summary:** The Probe takes `SOURCE_REGION` from its environment. Every Sample records it as a first-class field. Adding a new source region is a deployment action, not a code change.

**Why:** Network round-trip is physical — to measure from region X, code must run in region X. Encoding the source in data rather than in the codebase means the dashboard treats it as a real dimension from day one.

---

## LD2 — Self-scheduled collection; no inbound dispatch

See [ADR-0005](adr/0005-scheduled-collection-and-result-sink.md).

**Summary:** Probe Workers trigger themselves on a configurable interval. The original `POST /measure` inbound contract (ADR-0002) was removed because locked-down FedRAMP prod clusters block all inbound connections to worker pods.

**Consequence:** The Orchestrator stops orchestrating in any active sense — it only reads and serves. The name is kept for continuity.

---

## LD3 — Result Sink seam

See [ADR-0005](adr/0005-scheduled-collection-and-result-sink.md).

**Summary:** Workers call `sink.export(run)` and never know the transport. Selected by `RESULT_SINK` env var. Original implementations: `snowflake`, `stdout`, `noop`.

**Current status (M8):** The `ResultSink` abstraction and `EvalSink` abstraction have been removed. `collector.py` now calls `postgres_write.merge_run()` directly. There is no `RESULT_SINK` env var. The platform is Postgres-only and the indirection was not earning its complexity at current scale.

**If the pattern is needed again:** If a second database target is required in future (e.g. a cloud data warehouse alongside Postgres, or a multi-tenant write path), the `ResultSink` Protocol should be reintroduced: define `Protocol.export(run: RunRecord)`, create concrete implementations per target, and select via env var. The same pattern applies for `EvalSink` in `eval_worker`. Doing it then, when there is a real second target, is cheaper than maintaining it now against a hypothetical.

---

## LD4 — Sprinklr Gen AI Router as sole real adapter

See [ADR-0006](adr/0006-gen-ai-router-adapter.md).

**Summary:** Real Calls go through Sprinklr's Gen AI Router (`generateWithRequest`), not direct Azure/Bedrock/Vertex SDKs. Sprinklr supplies router credentials. Kind sim uses `FakeProviderAdapter`.

**Why:** Direct cloud credentials are not owned by this project. The Router is the single approved egress path for Sprinklr's AI traffic.

---

## LD5 — nginx UI pod as sole external entry point; separate from Orchestrator

### Choice

The UI pod (nginx) is the only pod with external exposure (NodePort in kind, Ingress in prod). The Orchestrator is a ClusterIP service — it has no external port and is reachable only via nginx's internal proxy. UI and Orchestrator run as **separate pods**, not combined into one.

### Why separate pods (not one combined pod)

**Different runtimes, different jobs.** The UI pod is nginx serving pre-built static files (HTML/CSS/JS). The Orchestrator is a live Python/uvicorn process. Running both in one container requires a process supervisor (supervisord) — an anti-pattern in containers where each container should do one thing.

**Independent deploys.** A CSS fix or copy change requires rebuilding and redeploying only the UI pod. The Orchestrator keeps running with zero downtime. Combined, every frontend change restarts the Python API.

**Independent scaling.** Under high API load the Orchestrator can scale to multiple replicas without touching the UI pod. nginx handles thousands of static-file requests per second on a single pod — it does not need replicas for that purpose.

**Crash isolation.** If the Orchestrator crashes or restarts (e.g. during a DB reconnect), the UI pod continues serving the React shell. Users see the app, not a blank screen. Combined, one process failure kills both.

**FedRAMP cluster constraint.** Worker pods have strictly outbound-only connections (ADR-0005). Applying the same principle to the Orchestrator reduces external attack surface — the Orchestrator has no external port; nginx is the only pod the internet touches.

### Why nginx specifically (not Apache, Caddy, or Python StaticFiles)

**SPA routing.** React Router handles `/evaluations`, `/ingest`, etc. on the client side. A direct request to `/evaluations` hits the server, which must return `index.html` — not 404. nginx's `try_files $uri $uri/ /index.html` does this in one directive. Apache requires `.htaccess` rewrite rules; Python `StaticFiles` has no equivalent.

**Reverse proxy in one block.** The `location /api { proxy_pass http://orchestrator-svc:8000; }` directive is the entire API proxy configuration. nginx was designed for this pattern; Python `StaticFiles` cannot proxy upstream at all.

**Performance on static files.** nginx serves files directly from the filesystem with `sendfile`, kernel-level zero-copy, `gzip_static`, and `expires` headers. Python/uvicorn reads files into memory and serialises them — measurably slower and wastes pod RAM on audio/image assets.

**Tiny image.** `nginx:alpine` is ~23 MB. Adding a Python process to serve static files would double the image size and add a Python runtime with its own CVE surface.

**TLS termination and header injection** (prod). nginx handles TLS at the edge and sets `X-Forwarded-For`, `X-Real-IP` without touching FastAPI code. Python `StaticFiles` requires `uvicorn --ssl-*` flags or a separate TLS wrapper.

### How nginx works in this pod

When you run `npm run build`, React produces plain files on disk — `index.html`, `main.js`, `styles.css`. These are dead files. No process, no port, nothing running. A browser cannot get them unless something is sitting there that:
1. Listens on a port
2. Gets the browser's request
3. Reads the file from disk
4. Sends it back

nginx is that something. It is just a file server with one extra trick — the proxy rule. It helps in routing bwtween pods like FastAPI .

FastAPI could technically serve files too, but that is not what it is for. FastAPI is for running Python logic — reading from a database, returning JSON. Using FastAPI to hand over a CSS file is like hiring a chef to deliver pizza. They can do it, but it is the wrong person for the job.

```
UI pod                         Orchestrator pod
──────────────────             ──────────────────
nginx                          FastAPI + uvicorn
serves files from disk         runs Python logic
no DB, no secrets              has DB connection and secrets
starts in milliseconds         needs Python runtime to boot
```

### The two rules in our nginx config

Our entire `nginx-ui.conf` has only two rules.

**Rule 1 — the proxy rule**

```nginx
location /api/ {
    proxy_pass http://${ORCHESTRATOR_UPSTREAM}/api/;
}
```

Proxy means: "this is not my job, send it to someone else." When the browser calls `/api/jobs/abc123`, nginx does not try to find a file called that. Instead it passes the request straight to the Orchestrator pod and sends the response back. The browser never knows the Orchestrator exists — it thinks it is talking to one server the whole time.

```
Browser  →  GET /api/jobs/abc123
            nginx sees /api/ → forwards to Orchestrator
            Orchestrator returns JSON
            nginx sends it back
Browser  ←  {"status": "done"}
```

**Rule 2 — the React fallback**

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

This means: try to find the file → if it does not exist, serve `index.html` instead.

This is needed because React handles page navigation itself inside the browser. When someone opens `/evaluations` directly, there is no file called `evaluations` on disk. Without this rule nginx returns 404. With it, nginx hands back `index.html`, React boots up, reads the URL, and shows the Evaluations tab. Works perfectly.

### Rejected alternative

Serve the React build from FastAPI using `StaticFiles`. One fewer pod to manage, but: the Orchestrator would need an external port (security risk), the React fallback rule does not exist in FastAPI, and you mix file serving with API logic in one process — if the API crashes, the UI goes down too.

---

## VBE1 — Offline call QA (not simulation)

### Choice

Evaluate **existing Recordings** — real archived MP3s. Do not spin up bot-to-bot simulations.

### Why

Production calls already happened. Real customer behavior (accents, hold music, barge-in, domain-specific flows) cannot be replicated by scripts. Scores reflect the actual deployed bot, not a controlled scenario.

### Rejected alternatives

| Alternative | Why rejected |
|---|---|
| EVA-Bench, VoiceAgentBench | Pre-deployment simulation frameworks; wrong input (generated calls, not archives) |
| ElevenAgents Success Evaluation | Only for calls that ran on ElevenAgents; we ingest arbitrary MP3s |

---

## VBE2 — ElevenLabs Scribe v2 for transcription

### Choice

Scribe v2 with `use_multi_channel=True`, `timestamps_granularity="word"`, `multichannel_output_style="combined"`, `diarize=False`.

### Why

Scribe is the only readily available transcription service that delivers **word-level timestamps with stereo channel separation** in a single API call. Word timestamps are not optional — the three timing evaluation dimensions (Response Latency, Dead Air, Interruptions) verify their scores against per-word evidence, not turn-level aggregates.

### Trade-offs

- Vendor dependency: only one transcription provider supported
- Cost: billed per audio minute
- 1-hour multichannel cap per file — production files must be ≤ 1 hour

### Rejected alternative

faster-whisper + pyannote (OSS diarization). Unnecessary on stereo files — channels already identify speakers. Adds local GPU dependency and diarization error modes we don't need.

---

## VBE3 — Stereo channel map; no diarization

| Channel | Speaker |
|---|---|
| 0 (left) | Customer |
| 1 (right) | Voice Bot |

Turns split on speaker (channel) change only. **Derived Signals** (bot response latency, customer hesitation, dead air, interruptions) computed from word timestamps — not from Scribe metadata.

**Why no diarization:** Stereo recording already separates speakers. Diarization would add an error-prone step to a problem already solved by the recording format.

---

## VBE4 — LLM-as-judge with rubrics

### Choice

Each of the 7 evaluation dimensions scored by a **separate Judge call** using a **Rubric** (criteria + 0–10 scale + evidence requirement). Not a single mega-prompt covering all dimensions.

### Why

- Aligns with contact-center QA practice and EMNLP 2024 findings (clear rubrics → higher human agreement)
- One dimension per call means failures are isolated — a bad Response Alignment score doesn't corrupt Task Success
- Rubrics in git (`rubrics/*.md`) — version-controlled, tunable without code changes

### Pros

- Captures nuance (disappointment, alignment) that regex cannot
- Rubric schema can evolve without a DB migration (dimensions stored as JSONB)

### Cons

- 2 LLM calls per dimension (GEval: step generation + scoring) → 14 calls per Recording
- Judge can disagree with humans without calibration against a golden set
- Bad transcripts → bad scores (garbage in, garbage out)

### Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Rule-only scoring | Cannot cover Task Success or User Disappointment reliably |
| Single combined judge prompt | Harder to tune and debug per dimension |
| Langfuse-managed judge | Rubrics live in UI; fights filesystem-first design (v1) |

---

## VBE5 — DeepEval GEval with VoiceGEval subclass

### Choice

**DeepEval** as judge engine. All 7 dimensions use **`VoiceGEval`** — a subclass of DeepEval's `GEval` that overrides prompt templates with voice-tuned versions.

**Two transcript shapes:**
- **Narrative** (4 dimensions: Task Success, Conversation Quality, Response Alignment, User Disappointment) — turn text + turn-level `[start–end]`
- **Timing** (3 dimensions: Response Latency, Dead Air, Interruptions) — same + per-word timestamps + Derived Signals appendix

### Why VoiceGEval over ConversationalGEval

DeepEval's `ConversationalGEval` treats a conversation as a list of chatbot turns. Barge-in and interruptions create many short turns → judge penalises each fragment individually → artificially low scores on natural voice calls. `VoiceGEval` wraps the entire call as a single `LLMTestCase`, scoring it holistically.

### Score shape

DeepEval normalises to **0–1** (`score`). Rubrics ask the Judge for **0–10** (`judge_score`). Both are stored in `evaluations.dimensions` JSONB so the UI can display either.

### Rejected alternatives

| Alternative | Why rejected |
|---|---|
| ConversationalGEval | Turn-list framing depresses scores on interrupted calls |
| Raw OpenAI calls | Reinvents GEval step parsing, test harness, metric structure |
| Langfuse-only evaluation | Wrong tool for batch filesystem pipeline as primary |

---

## VBE6 — Judge LLM provider

### Choice

Standard chat/completions API via **LiteLLM**: OpenAI, Anthropic, Google AI Studio, or **Vertex AI** (`vertex_ai/...`). Provider detected from model ID at runtime. API keys from env (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`). Vertex uses `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`, and `GOOGLE_APPLICATION_CREDENTIALS` (mounted SA JSON) — no API key.

### Why not Cursor SDK

Cursor SDK is an agent runtime, not a drop-in LLM judge endpoint. DeepEval expects a normal chat API.

### Why LiteLLM

Single abstraction over providers. Swapping judge models (e.g. GPT-4o → Claude Sonnet → Vertex Gemini) is a model-id / env change — no metric code change.

---

## M1 — Latency Dashboard is the base repo

### Choice

VoiceBotEval is absorbed into the Latency Dashboard repo (renamed to the unified platform name). The Latency Dashboard's architecture (multi-pod Helm, Docker, CI/CD) becomes the skeleton. VoiceBotEval's pipeline logic becomes a new worker type.

### Why

The two systems measure **complementary things** about the same voice bot: is it fast? is it good? Running them as separate products requires switching between two UIs to answer one question. A merged platform gives a single place to QA end-to-end.

The Latency Dashboard architecture was explicitly built for extensibility (adapter pattern, pluggable sinks, worker pods, Helm). VoiceBotEval's pure pipeline logic (`conversation.py`, `scribe.py`) slots into the same worker pattern without reworking the core.

### Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Keep two separate repos, link via nav bar | Duplicate infra; patterns diverge over time |
| VoiceBotEval as base repo | Weaker infrastructure skeleton (no Helm, no multi-pod, no CI/CD) |
| New repo from scratch | Migration cost; no advantage over renaming Latency Dashboard |

---

## M2 — Postgres as single database

### Choice

One Postgres instance (GCP Cloud SQL) is the sole persistent store for both latency runs and eval artifacts. Snowflake is removed. Filesystem JSON (`output/*.json`) is removed as the source of truth.

### Why Postgres replaces Snowflake

Snowflake is a columnar data warehouse optimised for analytical queries — not transactional writes from concurrent worker replicas, and not job queue semantics. Postgres gives us:
- `INSERT ... ON CONFLICT DO UPDATE` for atomic upserts (replaces Snowflake `MERGE`)
- `SELECT ... FOR UPDATE SKIP LOCKED` for safe Job queue polling from multiple Eval Worker replicas
- Standard TCP connection (not Snowflake's HTTP REST API) — lower latency, simpler auth
- Cost: significantly cheaper at dashboard scale

### Why Postgres replaces filesystem JSON

Container pods on GKE have no persistent volume mounted — `output/` is destroyed on every redeploy. Filesystem JSON also cannot survive horizontal scaling: two Eval Worker replicas would write to separate local filesystems.

### Schema (4 tables)

| Table | Replaces | Notes |
|---|---|---|
| `latency_runs` | Snowflake `LATENCY_RUNS` | Direct column-for-column translation; `VARIANT` → `JSONB` |
| `recordings` | Nothing (new) | Job tracker: status lifecycle + ingestion metadata |
| `conversations` | `conversation.json` | Turns + Derived Signals as JSONB |
| `evaluations` | `evaluation.json` | 7 dimension scores as JSONB; multiple judges per Recording allowed |

### Why JSONB for turns, signals, and dimensions

These blobs are never queried column-by-column from SQL — Python reads and processes them whole. Storing as JSONB avoids a 20-column flat schema that would require a migration every time a rubric adds a new dimension.

### Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Keep Snowflake for latency + add Postgres for eval | Two DBs, two credential sets, two connection pools |
| PVC on GKE for filesystem JSON | Solves data loss but not horizontal scaling; blocks Job queue |
| SQLite | Single-writer; incompatible with multiple Eval Worker replicas |

---

## M3 — Snowflake → Postgres via existing seams

### Choice

Replace Snowflake with Postgres by writing **4 new files** and changing **1 import**. No changes to probe logic, scheduling, schemas, or the React frontend.

### The 4 files

| New file | Replaces | What changes |
|---|---|---|
| `postgres_client.py` | `snowflake_client.py` | HTTP REST → TCP connection via psycopg2/asyncpg |
| `worker/postgres_write.py` | `worker/snowflake_write.py` | `MERGE INTO` → `INSERT ... ON CONFLICT DO UPDATE` |
| `worker/sinks/postgres.py` | `worker/sinks/snowflake.py` | Calls `postgres_write` |
| `orchestrator/postgres_read.py` | `orchestrator/snowflake_read.py` | `QUALIFY ROW_NUMBER()` → `SELECT DISTINCT ON (...)` |

### Key SQL translations

```sql
-- Upsert (was MERGE INTO)
INSERT INTO latency_runs (...) VALUES (...)
ON CONFLICT (run_id) DO UPDATE SET collected_at = EXCLUDED.collected_at, ...;

-- Latest row per target (was QUALIFY ROW_NUMBER())
SELECT DISTINCT ON (source_region, model, target_id) ...
FROM latency_runs
ORDER BY source_region, model, target_id, collected_at DESC;
```

### Why this is low-risk

The Latency Dashboard was designed with two explicit extension points documented in ADR-0005: the `ResultSink` Protocol (write seam) and the `snowflake_read` module (read seam). A `PostgresSink` implementing the same one-method Protocol is a drop-in. The FastAPI app imports `list_runs` and `get_run` by name — swapping the import is a one-line change.

---

## M4 — `recordings` table as Job queue; HTTP URLs first

### Choice

URL-based ingestion (user selects Ingestion Source, pastes URLs) is implemented via the `recordings` table as a Job queue. The Eval Worker polls:

```sql
SELECT recording_id FROM recordings
WHERE status = 'pending'
ORDER BY created_at ASC
FOR UPDATE SKIP LOCKED;
```

HTTP/HTTPS URLs supported first. S3/GCS added later as new `ingestion_source` enum values.

### Why `recordings` table as queue (not Redis/Celery)

At this scale (tens to hundreds of Recordings per day), Postgres `SKIP LOCKED` is the correct primitive. It avoids:
- An extra infrastructure component (Redis, RabbitMQ) to operate and secure
- Distributed transaction problems (job dequeued from Redis but DB write fails)
- At-least-once delivery complexity

`SKIP LOCKED` ensures multiple Eval Worker replicas never duplicate-process the same Job.

### Why HTTP/HTTPS first

S3 and GCS require IAM credentials per cluster. Scoping v1 URL ingestion to plain HTTPS means no credential management for the download step. Recordings can be served from any CDN, internal file server, or presigned URL.

### Job status lifecycle

```
pending       → Job created (URL received by Orchestrator API)
downloading   → Eval Worker fetching audio bytes via httpx
transcribing  → ElevenLabs Scribe API call in progress
structuring   → build_conversation() running
evaluating    → Judge calls in progress (14 LLM calls)
done          → conversations + evaluations rows written
failed        → error_message populated; terminal state
```

### Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Celery + Redis | Extra infrastructure; overkill for this scale |
| FastAPI BackgroundTasks | Shares process with API; Scribe/LLM hangs degrade API responsiveness |
| Cloud Tasks / Pub/Sub | Vendor lock-in; adds IAM complexity |

---

## M5 — 4-pod architecture

### Choice

```
UI pod (nginx)             — sole external entry point; SPA routing; proxies /api internally
Orchestrator pod (FastAPI) — ClusterIP; extended with /api/eval/* and /api/jobs/*
Probe Worker pod(s)        — outbound only; existing; unchanged
Eval Worker pod(s)         — new; polls recordings table; outbound only
```

### Why extend the existing layout rather than redesign

The Latency Dashboard 3-pod layout (UI + Orchestrator + Probe Workers) was designed for exactly this kind of extension: ADR-0001 documents location-agnostic workers, ADR-0005 documents the outbound-only constraint. The same reasoning applies to the Eval Worker — it does CPU/IO-heavy work (audio download, Scribe API, LLM calls) that must not block the API process.

---

## M6 — Eval Worker as separate pod

### Choice

The eval pipeline runs in a **dedicated Eval Worker pod**, not as a FastAPI background task.

### Why

**Crash isolation:** ElevenLabs Scribe can hang on large files. LLM Judge calls can timeout after 30–60 seconds. In a FastAPI `BackgroundTask`, either can exhaust the event loop's thread pool and make the API unresponsive. In a separate pod, the API stays healthy regardless.

**Independent scaling:** URL ingestion can queue many Recordings simultaneously. `replicas: N` in Helm scales Eval Workers independently of the Orchestrator — no code change.

**Resource separation:** Eval is memory-heavy (audio bytes, deepeval loading). API is I/O-light (DB reads, JSON serialization). Mixing them forces the Orchestrator pod to be over-provisioned.

### Rejected alternatives

| Alternative | Why rejected |
|---|---|
| FastAPI `BackgroundTasks` | Shares event loop; Scribe/LLM hangs degrade API |
| `asyncio.create_task` | Same problem; shares process crash boundary |
| Thread pool in FastAPI | Isolates CPU but not memory; same crash boundary |

---

## M7 — Extend React frontend; retire Streamlit

### Choice

The Latency Dashboard React app (React 18 + Vite + TypeScript + Bootstrap 5) becomes the sole frontend, extended with:
- **Evaluations tab** — browse Recordings, view Conversation transcript, dimension scores, rationale
- **Ingest tab** — paste URLs or upload MP3, select Ingestion Source, track Job status

Streamlit (`ui/app.py`) is retired.

### Why

Streamlit was VoiceBotEval v1's choice because it required no frontend work. That tradeoff no longer holds — a production-grade React app already exists. Running both means two UIs for the same product.

### What must be preserved from Streamlit

| Streamlit feature | React equivalent |
|---|---|
| MP3 file upload | Ingest tab file uploader |
| Browse `output/` artifacts | Evaluations tab reads from Postgres via API |
| Re-run evaluation | "Re-evaluate" button → `POST /api/jobs` |
| Judge model selector | Evaluations tab settings panel |

### Rejected alternative

Keep Streamlit alongside React as a transitional period. Rejected because two UIs for the same data creates confusion about which is authoritative and doubles maintenance burden.

---

## M8 — Remove Result Sink and Provider Adapter abstractions

### Choice

Both the `ResultSink` Protocol (`worker/sinks/`) and the `ProviderAdapter` Protocol (`worker/adapters/`) have been removed.

- `collector.py` calls `postgres_write.merge_run()` directly — no `RESULT_SINK` env var, no sink registry.
- `GenAIRouterAdapter`, `_FakeAdapter`, and all call result types are folded into `probe.py` — no `ProviderAdapter` Protocol, no adapter registry.
- The same applies to `eval_worker`: `collector.py` calls `postgres_write` directly; no `EvalSink` abstraction.

### Why

Both abstractions were designed for a system with multiple concrete implementations that needed to be swapped at runtime:
- Sinks: `snowflake | stdout | noop` — now Postgres-only, no env var switch needed.
- Adapters: `gen-ai-router | fake` — the `fake` adapter is now selected inside `probe.py` based on `config.provider`; no Protocol needed for two concrete types.

An abstraction that exists to swap between two things, where one of those things is a test double, is better handled by mocking. The Protocol, registry, and env-var selection were maintaining complexity for no runtime benefit.

### If the pattern is needed again

**For a second database:** Reintroduce `ResultSink(Protocol)` with `export(run: RunRecord)`. Create `PostgresSink` and the new target's sink. Select via `RESULT_SINK` env var. The same applies for `EvalSink` if eval worker needs a second write target.

**For a second provider:** Reintroduce `ProviderAdapter(Protocol)` with `measure_ttfb(...)`. Extract `GenAIRouterAdapter` back out of `probe.py`. Select via `config.provider`. The abstraction is cheap to rebuild — do it when there is a real second provider, not before.

---

## M10 — Remove `runs_store.py` passthrough layer

### Choice

`runs_store.py` has been deleted. `probe_routes.py` imports `list_runs` and `get_run` directly from `probe_read.py`. The same will apply to `eval_routes.py` → `eval_read.py`.

### Why it existed

`runs_store.py` was the backend-switch seam — when Snowflake was the only read backend, it selected the backend via `RUNS_STORE` env var and wrapped the underlying read functions. This made sense when a swap was plausible.

### Why it was removed

After M2 (Postgres-only) and M3 (Snowflake removed), the backend switch disappeared. The file became a pure passthrough with zero logic:

```python
# entire file — no value added
async def list_runs(...): return await probe_read.list_runs(...)
async def get_run(run_id): return await probe_read.get_run(run_id)
```

A passthrough that adds no logic, no error handling, and no indirection value is noise — you must open two files to trace one call. The same argument removed `ResultSink` (M8) and `ProviderAdapter` (M9).

### Route → read is the correct dependency

```
probe_routes.py  →  probe_read.py      ✓ flat, honest
eval_routes.py   →  eval_read.py       ✓ symmetric
```

No `*_store.py` layer needed. If a cache or multi-backend read path is required in future, add the seam then with a real second implementation — not before.

### Trade-off accepted

One fewer indirection point for swapping the read backend at runtime. Cost of adding it back when a real second backend exists: low (one new file, one import change in routes). Cost of maintaining a passthrough with no logic: permanent noise for every reader.

---

## M11 — Eval Worker → Orchestrator completion notification

### Intent

When an Eval Worker finishes scoring a Recording (`status='done'`), the React UI should know immediately — without polling every 3 seconds forever. The worker needs to signal the Orchestrator, which then pushes the update to connected browser clients.

### Current state (v1)

React polls `GET /api/jobs/{recording_id}` on an interval. Works, but adds latency between "scoring done" and "UI updates", and wastes requests when the queue is idle.

### Chosen approach for v2: Postgres `LISTEN/NOTIFY`

```
eval_worker/postgres_write.py
    → after writing evaluations row:
    → NOTIFY evaluation_ready, '<recording_id>'

orchestrator/app.py
    → background asyncio task listening on 'evaluation_ready'
    → on notification: broadcast SSE event to all connected React clients

React IngestTab / EvaluationsTab
    → EventSource('/api/events') — one persistent SSE connection
    → on 'evaluation_ready' event: refresh the recording row
```

### Why Postgres LISTEN/NOTIFY (not HTTP callback or Redis pub/sub)

| Option | Why rejected |
|---|---|
| Eval Worker HTTP POST to Orchestrator | Worker needs to know Orchestrator's internal URL; pods are not guaranteed to know each other's addresses within the namespace without a Service name; adds coupling |
| Redis pub/sub | Extra infrastructure component to operate and secure; overkill when Postgres is already the source of truth |
| Polling only (current) | Works but UI latency = poll interval; wastes connections when idle |
| WebSocket | Heavier protocol; SSE is one-directional (server → client) and sufficient for status updates |

Postgres `NOTIFY` is zero extra infrastructure — the same connection pool already open in the Orchestrator gets a background listener task. The Eval Worker emits one `NOTIFY` per completed job. The Orchestrator fans it out to however many SSE clients are connected.

### Implementation sketch

```python
# eval_worker/postgres_write.py — after write_evaluation()
await conn.execute("SELECT pg_notify('evaluation_ready', $1)", recording_id)

# orchestrator/app.py — in lifespan, after get_pool()
asyncio.create_task(_listen_for_completions())

# orchestrator/sse_routes.py — new file
@router.get("/api/events")
async def sse_stream(request: Request):
    async def event_generator():
        queue = subscribe()           # register this client
        try:
            while not await request.is_disconnected():
                recording_id = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"data: {recording_id}\n\n"
        finally:
            unsubscribe(queue)
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Trade-off accepted

Adds one background asyncio task to the Orchestrator and one SSE route. If the Orchestrator restarts between `NOTIFY` and client receipt, the notification is lost — the React client falls back to one final poll on reconnect. Acceptable: `status='done'` is already written to Postgres, so the data is never lost, only the push signal.

### When to implement

After the React frontend `EvaluationsTab` and `IngestTab` are built and the basic polling flow is working end-to-end. The notification layer is an enhancement, not a prerequisite.

---

## Document index

| Doc | Purpose |
|---|---|
| [`CONTEXT.md`](../CONTEXT.md) | Domain glossary (merged platform) |
| [`docs/architecture.md`](architecture.md) | System diagrams (Latency Dashboard — needs update for merged platform) |
| [`docs/adr/0001`](adr/0001-location-agnostic-probe.md) | Location-agnostic Probe |
| [`docs/adr/0002`](adr/0002-orchestrator-and-probe-workers.md) | Orchestrator + Probe Workers (superseded) |
| [`docs/adr/0003`](adr/0003-litellm-library-sole-adapter.md) | LiteLLM adapter (superseded) |
| [`docs/adr/0004`](adr/0004-prod-catalog-and-environment-ids.md) | Prod catalog and environment IDs |
| [`docs/adr/0005`](adr/0005-scheduled-collection-and-result-sink.md) | Scheduled collection + Result Sink |
| [`docs/adr/0006`](adr/0006-gen-ai-router-adapter.md) | Gen AI Router adapter |
