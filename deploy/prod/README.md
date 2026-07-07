# Production Kubernetes deployment

Deploy Latency Dashboard to a cloud Kubernetes cluster (EKS, GKE, AKS, or on-prem).

**Prerequisites:** cluster access, container registry, Snowflake account (see [`../DEPLOYMENT.md`](../DEPLOYMENT.md) Part 0).

---

## 1. Container images

Build from repo root and push to your registry:

```bash
export REGISTRY=123456789.dkr.ecr.us-east-1.amazonaws.com/latency-dashboard
export TAG=1.0.0

docker build -f deploy/docker/Dockerfile.worker -t $REGISTRY/worker:$TAG .
docker build -f deploy/docker/Dockerfile.orchestrator -t $REGISTRY/orchestrator:$TAG .
docker build -f deploy/docker/Dockerfile.ui -t $REGISTRY/ui:$TAG .

docker push $REGISTRY/worker:$TAG
docker push $REGISTRY/orchestrator:$TAG
docker push $REGISTRY/ui:$TAG
```

CI should tag images with git SHA and promote through staging → prod.

---

## 2. Snowflake secret

Create in the target namespace (never commit PAT to git):

```bash
kubectl create namespace latency-dashboard

kubectl create secret generic latency-dashboard-snowflake \
  --namespace latency-dashboard \
  --from-literal=SNOWFLAKE_TOKEN="$SNOWFLAKE_TOKEN" \
  --from-literal=SNOWFLAKE_WAREHOUSE="$SNOWFLAKE_WAREHOUSE" \
  --from-literal=SNOWFLAKE_DATABASE="$SNOWFLAKE_DATABASE" \
  --from-literal=SNOWFLAKE_SCHEMA="${SNOWFLAKE_SCHEMA:-PUBLIC}" \
  --from-literal=SNOWFLAKE_ROLE="$SNOWFLAKE_ROLE" \
  --from-literal=SNOWFLAKE_SQL_API_URL="$SNOWFLAKE_SQL_API_URL" \
  --from-literal=SNOWFLAKE_ACCOUNT="$SNOWFLAKE_ACCOUNT" \
  --from-literal=SNOWFLAKE_RUNS_TABLE="${SNOWFLAKE_RUNS_TABLE:-LATENCY_RUNS}"
```

For production, prefer External Secrets Operator, Sealed Secrets, or your cloud secret manager.

---

## 3. Probe configuration

Edit `config/config.prod.json`:

- Set `provider: gen-ai-router`
- Fill Sprinklr fields (`routerUrl`, `deployment`, `llm_config_id`, etc.)
- Set `source_region` per worker deployment

Sync configs into the Helm chart before install:

```bash
mkdir -p deploy/helm/latency-dashboard/config
cp config/config.prod.json deploy/helm/latency-dashboard/config/config-eastus.json
# repeat per region
```

Update `workers:` in your prod values file to list each region and config file.

---

## 4. Helm values

Copy the example and customize:

```bash
cp deploy/helm/latency-dashboard/values-prod.example.yaml \
   deploy/helm/latency-dashboard/values-prod.yaml
# Edit values-prod.yaml — do not commit secrets
```

Key settings:

```yaml
image:
  pullPolicy: IfNotPresent
  worker:
    repository: your-registry/worker
    tag: "1.0.0"
  orchestrator:
    repository: your-registry/orchestrator
    tag: "1.0.0"
  ui:
    repository: your-registry/ui
    tag: "1.0.0"

global:
  resultSink: snowflake
  collectIntervalSeconds: 300

workers:
  - name: eastus
    configFile: config-eastus.json
  # add one entry per source region

orchestrator:
  runsStore: snowflake

snowflake:
  secretName: latency-dashboard-snowflake

service:
  ui:
    type: ClusterIP   # put Ingress in front
    nodePort: 30080   # ignored when type=ClusterIP
```

Add an Ingress resource (not included in chart yet) or use your platform's load balancer.

---

## 5. Install

```bash
helm upgrade --install latency-dashboard ./deploy/helm/latency-dashboard \
  --namespace latency-dashboard \
  -f ./deploy/helm/latency-dashboard/values.yaml \
  -f ./deploy/helm/latency-dashboard/values-prod.yaml
```

---

## 6. Post-deploy checks

```bash
kubectl -n latency-dashboard get pods
kubectl -n latency-dashboard logs -l app.kubernetes.io/component=worker --tail=50
kubectl -n latency-dashboard logs deploy/latency-dashboard-orchestrator --tail=20

# Port-forward for smoke test before Ingress is ready
kubectl -n latency-dashboard port-forward svc/latency-dashboard-ui 8080:8080
curl -s http://127.0.0.1:8080/api/health
curl -s http://127.0.0.1:8080/api/runs | head
```

In Snowsight:

```sql
SELECT COUNT(*), MAX(collected_at) FROM LATENCY.PUBLIC.LATENCY_RUNS;
```

---

## 7. Multi-region layout

Deploy **one worker pod per source region** (each in or near that region's cluster). All workers write to the **same** Snowflake table. One orchestrator + UI deployment (any region) serves the dashboard.

```
Region A cluster → worker (source=A) ──┐
Region B cluster → worker (source=B) ──┼──► Snowflake
Central cluster  → orchestrator + UI ──┘
```

Workers have **no inbound endpoints** — only outbound probes and Snowflake writes.

---

## 8. Upgrade

```bash
# New images
export TAG=1.0.1
# build, push...

helm upgrade latency-dashboard ./deploy/helm/latency-dashboard \
  -n latency-dashboard \
  -f values.yaml -f values-prod.yaml \
  --set image.worker.tag=$TAG \
  --set image.orchestrator.tag=$TAG \
  --set image.ui.tag=$TAG
```
