#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER_NAME="${KIND_CLUSTER_NAME:-voicebot-qa}"
TAG="${IMAGE_TAG:-local}"
HELM_CHART="$ROOT/deploy/helm/latency-dashboard"

echo "Syncing probe configs into Helm chart..."
mkdir -p "$HELM_CHART/config"
cp "$ROOT/config/config.json" "$HELM_CHART/config/"
cp "$ROOT/config/config-westeurope.json" "$HELM_CHART/config/" 2>/dev/null || true

echo "Syncing schema.sql into Helm chart files/..."
mkdir -p "$HELM_CHART/files"
cp "$ROOT/backend/schema.sql" "$HELM_CHART/files/schema.sql"

echo "Building images..."
docker build -f "$ROOT/deploy/docker/Dockerfile.probe-worker"  -t "voicebot-qa-probe-worker:${TAG}"  "$ROOT"
docker build -f "$ROOT/deploy/docker/Dockerfile.eval-worker"   -t "voicebot-qa-eval-worker:${TAG}"   "$ROOT"
docker build -f "$ROOT/deploy/docker/Dockerfile.orchestrator"  -t "voicebot-qa-orchestrator:${TAG}"  "$ROOT"
docker build -f "$ROOT/deploy/docker/Dockerfile.ui"            -t "voicebot-qa-ui:${TAG}"            "$ROOT"

echo "Loading images into kind cluster '${CLUSTER_NAME}'..."
kind load docker-image "voicebot-qa-probe-worker:${TAG}"  --name "${CLUSTER_NAME}"
kind load docker-image "voicebot-qa-eval-worker:${TAG}"   --name "${CLUSTER_NAME}"
kind load docker-image "voicebot-qa-orchestrator:${TAG}"  --name "${CLUSTER_NAME}"
kind load docker-image "voicebot-qa-ui:${TAG}"            --name "${CLUSTER_NAME}"
# postgres:16-alpine is pulled directly by the pod (IfNotPresent) — not loaded via kind
# to avoid multi-platform manifest failures with `ctr import --all-platforms`

echo ""
echo "Done. Next steps:"
echo "  1. Create secrets:  ./deploy/kind/create-secrets.sh"
echo "  2. Helm install:    helm upgrade --install voicebot-qa $HELM_CHART -f $HELM_CHART/values-kind.yaml"
