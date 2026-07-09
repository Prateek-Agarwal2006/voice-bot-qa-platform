# Voice Bot QA Platform

End-to-end quality assurance platform for voice bot conversations. Combines two pipelines in one Kubernetes deployment:

- **Latency Dashboard** — continuous TTFB (time to first byte) probing across LLM providers and cloud regions
- **Call Evaluator** — upload a recording → auto-transcribe → LLM judge scores 7 quality dimensions

---

## Architecture

| Pod | Role |
|-----|------|
| `ui` | nginx + React; proxies `/api` → orchestrator |
| `orchestrator` | FastAPI — REST API for runs, evaluations, job submission |
| `probe-worker-*` | Scheduled TTFB probes → writes `latency_runs` to Postgres |
| `eval-worker` | Polls `recordings` queue → download → transcribe → judge → write |
| `postgres` | Postgres 16 — shared store for all pods |

**Storage:** Postgres (not Snowflake). DSN injected via Kubernetes Secret.

**Transcription:** ElevenLabs Scribe v2 (multichannel, speaker-separated).

**Judging:** DeepEval GEval with a selectable LLM judge per job (OpenAI / Anthropic / Google AI Studio / Vertex AI via LiteLLM).

### Evaluation dimensions

| Dimension | Input |
|-----------|-------|
| Task Success | Transcript |
| Conversation Quality | Transcript |
| Response Alignment | Transcript |
| User Disappointment | Transcript |
| Response Latency | Word timestamps |
| Dead Air | Word timestamps |
| Interruptions | Word timestamps |

---

## UI tabs

| Tab | What it does |
|-----|-------------|
| **Latency** | Live TTFB heatmap across regions and models |
| **Evaluations** | Table of all submitted recordings + scores |
| **Ingest** | Submit a recording URL, pick URL provider and judge model |

---

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Orchestrator health check |
| `/api/config` | GET | Probe config (models, regions) |
| `/api/runs` | GET | All TTFB probe runs |
| `/api/evaluations` | GET | All recordings (`?status=done\|failed\|pending`) |
| `/api/evaluations/{id}/conversation` | GET | Speaker-separated transcript |
| `/api/evaluations/{id}/scores` | GET | Dimension scores + rationales |
| `/api/jobs` | POST | Submit a new recording for evaluation |
| `/api/jobs/{id}` | GET | Poll job status |

---

## Local setup (kind)

### Prerequisites

```bash
brew install colima docker kubectl helm kind
colima start --cpu 4 --memory 6
kind create cluster --name voicebot-qa --config deploy/kind/kind-config.yaml
```

### 1. Build and load images

```bash
chmod +x deploy/kind/build-and-load.sh
./deploy/kind/build-and-load.sh
```

### 2. Create secrets

```bash
export POSTGRES_PASSWORD="voicebot"
export POSTGRES_DSN="postgresql://voicebot:voicebot@postgres-svc:5432/voicebot"
export ELEVENLABS_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"   # optional
export GEMINI_API_KEY="your-key"      # optional — Google AI Studio
# Optional — Vertex AI judge (also set vertex.enabled=true in Helm values):
# export VERTEXAI_PROJECT="your-gcp-project"
# export VERTEXAI_LOCATION="us-central1"
# export VERTEX_SA_JSON_FILE="/path/to/gcp-sa.json"

chmod +x deploy/kind/create-secrets.sh
./deploy/kind/create-secrets.sh
```

API keys live only in the K8s Secret — never committed to git.

For Vertex judges, after secrets are applied enable the SA mount:

```bash
helm upgrade --install voicebot-qa deploy/helm/latency-dashboard \
  -f deploy/helm/latency-dashboard/values-kind.yaml \
  --set vertex.enabled=true
```

### 3. Install with Helm

```bash
helm upgrade --install voicebot-qa deploy/helm/latency-dashboard \
  -f deploy/helm/latency-dashboard/values-kind.yaml
```

> If you already enabled Vertex in step 2 with `--set vertex.enabled=true`, you can skip a second install.

### 4. Open the UI

```bash
kubectl port-forward svc/voicebot-qa-ui 8080:80
open http://127.0.0.1:8080
```

### Teardown

```bash
helm uninstall voicebot-qa
kind delete cluster --name voicebot-qa
colima stop
```

---

## URL providers

The Ingest tab supports multiple audio source types:

| Provider | Use when |
|----------|----------|
| Direct URL | Public HTTP/HTTPS link to an audio file |
| Google Drive | Shared Google Drive file link (`/file/d/…/view`) |

---

## Judge models

Any of the following can be selected per job from the UI:

| Provider | Models |
|----------|--------|
| OpenAI | `gpt-4o-mini`, `gpt-4o` |
| Anthropic | `claude-sonnet-4-6`, `claude-opus-4-8` |
| Google | `gemini-2.0-flash`, `gemini-2.5-pro` |

---

## Tests

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -v
```

---

## Project layout

```
backend/latency_dashboard/
  orchestrator/        FastAPI app — runs, evaluations, job queue
  eval_worker/         Eval pipeline — download, transcribe, judge, write
  probe_worker/        TTFB probe collector
frontend/              React UI (Vite)
deploy/
  helm/                Helm chart (kind + prod values)
  kind/                Local cluster scripts and secrets
  docker/              Dockerfiles for each pod
config/                Probe JSON configs per region
docs/                  Architecture notes and ADRs
```

See [`docs/architecture.md`](docs/architecture.md) for deeper design notes and [`docs/adr/`](docs/adr/) for architectural decisions.
