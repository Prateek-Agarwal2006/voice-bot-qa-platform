#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-default}"
SECRET_NAME="${SECRET_NAME:-voicebot-qa-secrets}"

if [[ -z "${POSTGRES_DSN:-}" ]]; then
  echo "Required env vars:" >&2
  echo "  POSTGRES_DSN          postgresql://user:pass@postgres-svc:5432/voicebot" >&2
  echo "  ELEVENLABS_API_KEY    your ElevenLabs key" >&2
  echo "  OPENAI_API_KEY        (optional — required if judge model is OpenAI)" >&2
  echo "  ANTHROPIC_API_KEY     (optional — required if judge model is Anthropic)" >&2
  echo "  GEMINI_API_KEY        (optional — required if judge model is Google AI Studio)" >&2
  echo "  VERTEXAI_PROJECT      (optional — required if judge model is Vertex)" >&2
  echo "  VERTEXAI_LOCATION     (optional — e.g. us-central1)" >&2
  echo "  VERTEX_SA_JSON_FILE   (optional — path to GCP service-account JSON)" >&2
  exit 1
fi

ARGS=(
  --namespace "${NAMESPACE}"
  --from-literal=POSTGRES_DSN="${POSTGRES_DSN}"
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-voicebot}"
  --from-literal=ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-}"
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY:-}"
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
  --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY:-}"
  --from-literal=VERTEXAI_PROJECT="${VERTEXAI_PROJECT:-}"
  --from-literal=VERTEXAI_LOCATION="${VERTEXAI_LOCATION:-}"
)

if [[ -n "${VERTEX_SA_JSON_FILE:-}" ]]; then
  if [[ ! -f "${VERTEX_SA_JSON_FILE}" ]]; then
    echo "VERTEX_SA_JSON_FILE not found: ${VERTEX_SA_JSON_FILE}" >&2
    exit 1
  fi
  ARGS+=(--from-file=GCP_SA_JSON="${VERTEX_SA_JSON_FILE}")
else
  ARGS+=(--from-literal=GCP_SA_JSON="")
fi

kubectl create secret generic "${SECRET_NAME}" \
  "${ARGS[@]}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret '${SECRET_NAME}' applied in namespace '${NAMESPACE}'."
if [[ -n "${VERTEX_SA_JSON_FILE:-}" ]]; then
  echo "Vertex SA JSON loaded. Set vertex.enabled=true in values-kind.yaml (or --set vertex.enabled=true) and helm upgrade."
fi
