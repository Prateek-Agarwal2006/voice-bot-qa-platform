# Kind local simulation — Voice Bot QA Platform

Simulates production K8s layout on your Mac: **probe worker pod(s)**, **eval worker**, **orchestrator**, **UI**, all talking to an in-cluster **Postgres pod** via `postgres-svc:5432` — same DNS as production.

## Prerequisites

```bash
brew install colima docker kubectl helm kind
colima start --cpu 4 --memory 6
kind create cluster --name voicebot-qa --config deploy/kind/kind-config.yaml
kubectl cluster-info --context kind-voicebot-qa
```

The config maps NodePort **30090** to your Mac.

## 1. Build images and load into kind

```bash
chmod +x deploy/kind/build-and-load.sh
./deploy/kind/build-and-load.sh
```

This also copies `backend/schema.sql` into the Helm chart's `files/` directory so it is embedded as a ConfigMap and run automatically by Postgres on first boot.

## 2. Create K8s Secret

```bash
# POSTGRES_USER and POSTGRES_DB are set in values.yaml (both "voicebot").
# POSTGRES_PASSWORD is what you choose — must match the DSN below.
export POSTGRES_PASSWORD="voicebot"
export POSTGRES_DSN="postgresql://voicebot:voicebot@postgres-svc:5432/voicebot"
export ELEVENLABS_API_KEY="..."
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."   # optional
export GEMINI_API_KEY="..."      # optional

chmod +x deploy/kind/create-secrets.sh
./deploy/kind/create-secrets.sh
```

API keys live only in the K8s Secret — never committed to git.

## 3. Helm install

```bash
helm upgrade --install voicebot-qa deploy/helm/latency-dashboard \
  -f deploy/helm/latency-dashboard/values-kind.yaml
```

Check pods:

```bash
kubectl get pods
kubectl logs deploy/voicebot-qa-orchestrator
kubectl logs deploy/voicebot-qa-eval-worker
```

## 4. Open the UI

NodePort **30090**:

```bash
open http://127.0.0.1:30090
```

Or port-forward:

```bash
kubectl port-forward svc/voicebot-qa-ui 8080:80
open http://127.0.0.1:8080
```

## Teardown

```bash
helm uninstall voicebot-qa
kind delete cluster --name voicebot-qa
colima stop
```

## What gets deployed

| Pod | Role |
|-----|------|
| `probe-worker-*` | Collect TTFB → write `latency_runs` |
| `eval-worker` | Poll `recordings` queue → transcribe → judge → write |
| `orchestrator` | FastAPI: `/api/runs`, `/api/evaluations`, `/api/jobs` |
| `ui` | nginx + React; proxies `/api` → orchestrator |
| `postgres` | Postgres 16-alpine; init'd from `schema.sql` ConfigMap |

## Troubleshooting

- **Browser "connection failed" on `:30090`** — port not published. Port-forward instead:
  ```bash
  kubectl port-forward svc/voicebot-qa-ui 8080:80
  ```
- **ImagePullBackOff** — run `build-and-load.sh` again; kind needs images loaded locally.
- **Postgres pod not ready** — check logs: `kubectl logs deploy/voicebot-qa-postgres`. Schema errors mean `files/schema.sql` wasn't copied before `helm install` — re-run `build-and-load.sh`.
- **Eval worker CrashLoop** — check `ELEVENLABS_API_KEY` and the judge API key (e.g. `OPENAI_API_KEY`) in the Secret. Judge model is now per-job, not a pod env var.
