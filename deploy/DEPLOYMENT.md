# Deployment guide

Complete instructions for running Latency Dashboard on Kubernetes. There are two targets:

| Target | Where | Purpose |
|--------|-------|---------|
| **Kind sim** | Your Mac (Colima + kind) | Test full pod layout + real Snowflake before prod |
| **Production** | Cloud Kubernetes (EKS/GKE/AKS) | Real probes + dashboard for your team |

Both use the **same Helm chart** (`deploy/helm/latency-dashboard/`) and **Snowflake** as storage. Workers write; orchestrator reads; UI proxies `/api`.

---

## Architecture (both environments)

```
  worker-eastus ──┐
                  ├── MERGE rows ──► Snowflake LATENCY_RUNS ◄── SELECT ── orchestrator ◄── /api ── UI ◄── browser
  worker-westeu ──┘
```

Detailed diagrams: [`docs/architecture.md`](../docs/architecture.md).

---

## Part 0 — One-time Snowflake setup

Do this once per Snowflake account (trial or prod).

### 0.1 Create account and database

1. Sign up at [https://signup.snowflake.com/](https://signup.snowflake.com/)
2. In Snowsight → **Worksheets**, run:

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;

CREATE DATABASE IF NOT EXISTS LATENCY;
CREATE SCHEMA IF NOT EXISTS LATENCY.PUBLIC;
```

### 0.2 Network policy (required for PAT + SQL API)

```sql
USE ROLE SECURITYADMIN;

CREATE NETWORK POLICY LATENCY_DASHBOARD_POLICY
  ALLOWED_IP_LIST = ('0.0.0.0/0');   -- tighten for prod

ALTER ACCOUNT SET NETWORK_POLICY = LATENCY_DASHBOARD_POLICY;
ALTER USER YOUR_USERNAME SET NETWORK_POLICY = LATENCY_DASHBOARD_POLICY;
```

Replace `YOUR_USERNAME` with your Snowflake user (e.g. `PrateekAgarwal`).

### 0.3 Programmatic Access Token (PAT)

In Snowsight: **Governance & security → Users & roles → your user → Programmatic access tokens → Generate**.

Or SQL:

```sql
ALTER USER YOUR_USERNAME ADD PROGRAMMATIC ACCESS TOKEN latency_dashboard;
```

Copy the **token secret** immediately (shown once).

### 0.4 Local env file (never commit)

Create `.env` in the repo root (gitignored):

```bash
export SNOWFLAKE_ACCOUNT='myorg-myacct'
export SNOWFLAKE_SQL_API_URL="https://${SNOWFLAKE_ACCOUNT}.snowflakecomputing.com/api/v2/statements"
export SNOWFLAKE_TOKEN='your_pat_secret'
export SNOWFLAKE_TOKEN_TYPE='PROGRAMMATIC_ACCESS_TOKEN'
export SNOWFLAKE_WAREHOUSE='COMPUTE_WH'
export SNOWFLAKE_DATABASE='LATENCY'
export SNOWFLAKE_SCHEMA='PUBLIC'
export SNOWFLAKE_ROLE='ACCOUNTADMIN'
export SNOWFLAKE_RUNS_TABLE='LATENCY_RUNS'
```

Verify:

```bash
source .env
curl -s -X POST "$SNOWFLAKE_SQL_API_URL" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $SNOWFLAKE_TOKEN" \
  -d '{"statement":"SELECT CURRENT_USER()","warehouse":"COMPUTE_WH","database":"LATENCY","schema":"PUBLIC","role":"ACCOUNTADMIN"}'
```

Expect JSON with your username, not error `390432`.

The worker auto-creates table `LATENCY_RUNS` on first write.

---

## Part A — Local Kubernetes simulation (kind on Mac)

Full detail: [`deploy/kind/README.md`](kind/README.md).

### A.1 Prerequisites

```bash
brew install colima docker kubectl helm kind
colima start --cpu 4 --memory 4
```

### A.2 Create kind cluster (with UI port mapping)

**Important:** use `kind-config.yaml` so `http://127.0.0.1:30080` works.

```bash
kind create cluster \
  --name latency-dashboard \
  --config deploy/kind/kind-config.yaml

kubectl cluster-info --context kind-latency-dashboard
```

### A.3 Inject Snowflake secret into cluster

```bash
cd /path/to/Latency_Dashboard
source .env
chmod +x deploy/kind/create-snowflake-secret.sh
./deploy/kind/create-snowflake-secret.sh
```

### A.4 Build Docker images and load into kind

```bash
chmod +x deploy/kind/build-and-load.sh
./deploy/kind/build-and-load.sh
```

Builds three images tagged `:local` and copies probe configs into the Helm chart.

### A.5 Helm install

```bash
helm upgrade --install latency-dashboard ./deploy/helm/latency-dashboard \
  -f ./deploy/helm/latency-dashboard/values-kind.yaml
```

### A.6 Verify and open

```bash
kubectl get pods
# All four pods should be Running

kubectl logs deploy/latency-dashboard-worker-eastus --tail=20
kubectl logs deploy/latency-dashboard-orchestrator --tail=20

open http://127.0.0.1:30080
```

Wait one collect cycle (`collect_interval_seconds` in config, default **300s**), then refresh the dashboard.

### A.7 After code changes

```bash
./deploy/kind/build-and-load.sh
helm upgrade --install latency-dashboard ./deploy/helm/latency-dashboard \
  -f ./deploy/helm/latency-dashboard/values-kind.yaml
```

### A.8 Teardown

```bash
helm uninstall latency-dashboard
kind delete cluster --name latency-dashboard
colima stop   # optional
```

---

## Part B — Production Kubernetes

Full detail: [`deploy/prod/README.md`](prod/README.md).

### B.1 Differences from kind sim

| | Kind sim | Production |
|---|----------|------------|
| Cluster | kind on Mac | EKS / GKE / AKS |
| Images | `kind load` locally | Push to **container registry** |
| Helm values | `values-kind.yaml` | `values.yaml` + `values-prod.yaml` |
| `image.pullPolicy` | `Never` | `IfNotPresent` or `Always` |
| UI access | NodePort `:30080` | **Ingress** or Load Balancer |
| Probe config | `config.json` (fake) | `config.prod.json` (Gen AI Router) |
| Snowflake secret | `create-snowflake-secret.sh` | CI/CD or cloud secret manager |
| Workers | 2 sim regions on one node | **One worker per source region** |

### B.2 Build and push images

```bash
export REGISTRY=your-registry.example.com/your-org
export TAG=$(git rev-parse --short HEAD)

docker build -f deploy/docker/Dockerfile.worker \
  -t $REGISTRY/latency-dashboard-worker:$TAG .
docker build -f deploy/docker/Dockerfile.orchestrator \
  -t $REGISTRY/latency-dashboard-orchestrator:$TAG .
docker build -f deploy/docker/Dockerfile.ui \
  -t $REGISTRY/latency-dashboard-ui:$TAG .

docker push $REGISTRY/latency-dashboard-worker:$TAG
docker push $REGISTRY/latency-dashboard-orchestrator:$TAG
docker push $REGISTRY/latency-dashboard-ui:$TAG
```

### B.3 Create namespace and Snowflake secret

```bash
kubectl create namespace latency-dashboard

# Option 1: same script, different namespace
export NAMESPACE=latency-dashboard
source .env
./deploy/kind/create-snowflake-secret.sh

# Option 2: kubectl directly (see scripts/env.example for all keys)
```

### B.4 Configure prod probe configs

1. Edit `config/config.prod.json` — replace `??????` with real Sprinklr router fields
2. Set `provider: gen-ai-router` at the top level
3. Copy/sync configs into Helm chart `deploy/helm/latency-dashboard/config/` before deploy, or mount via your own ConfigMap pipeline

One **worker Deployment per source region**, each with its own config ConfigMap.

### B.5 Helm install (production)

Copy and edit `deploy/helm/latency-dashboard/values-prod.example.yaml`, then:

```bash
helm upgrade --install latency-dashboard ./deploy/helm/latency-dashboard \
  --namespace latency-dashboard \
  -f ./deploy/helm/latency-dashboard/values.yaml \
  -f ./deploy/helm/latency-dashboard/values-prod.example.yaml
```

Set image repository/tag, Ingress host, and worker list for your regions.

### B.6 Verify

```bash
kubectl -n latency-dashboard get pods
kubectl -n latency-dashboard logs deploy/latency-dashboard-orchestrator
curl -s https://your-ingress-host/api/health
```

### B.7 Upgrade / rollback

```bash
helm upgrade latency-dashboard ./deploy/helm/latency-dashboard \
  -n latency-dashboard -f values.yaml -f values-prod.yaml

helm rollback latency-dashboard -n latency-dashboard
```

---

## Environment variables reference

See [`scripts/env.example`](../scripts/env.example).

| Variable | Pod | Purpose |
|----------|-----|---------|
| `RESULT_SINK` | worker | Must be `snowflake` |
| `RUNS_STORE` | orchestrator | Must be `snowflake` |
| `CONFIG_PATH` | worker, orchestrator | Path to probe JSON in pod |
| `SNOWFLAKE_TOKEN` | worker, orchestrator | PAT (from k8s Secret) |
| `SNOWFLAKE_SQL_API_URL` | worker, orchestrator | SQL REST endpoint |
| `SNOWFLAKE_WAREHOUSE` | worker, orchestrator | e.g. `COMPUTE_WH` |
| `SNOWFLAKE_DATABASE` | worker, orchestrator | e.g. `LATENCY` |
| `COLLECT_ONCE` | worker | Optional: one cycle then exit |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Connection refused on `:30080` | Recreate kind cluster **with** `kind-config.yaml`; or `kubectl port-forward svc/latency-dashboard-ui 8080:8080` |
| `ImagePullBackOff` (kind) | Re-run `./deploy/kind/build-and-load.sh` |
| Snowflake `390432` network policy | Complete Part 0.2 |
| Empty dashboard | Wait for collect interval; check worker logs |
| `401` from Snowflake | Rotate PAT; re-run secret script |

---

## Related files

| Path | Purpose |
|------|---------|
| `deploy/kind/` | kind cluster + build/load scripts |
| `deploy/helm/latency-dashboard/` | Helm chart |
| `deploy/docker/` | Dockerfiles |
| `scripts/env.example` | Env var template |
| `docs/architecture.md` | System diagrams |
