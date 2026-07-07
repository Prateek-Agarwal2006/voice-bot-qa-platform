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
  echo "  GEMINI_API_KEY        (optional — required if judge model is Google)" >&2
  exit 1
fi

kubectl create secret generic "${SECRET_NAME}" \
  --namespace "${NAMESPACE}" \
  --from-literal=POSTGRES_DSN="${POSTGRES_DSN}" \
  --from-literal=POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-voicebot}" \
  --from-literal=ELEVENLABS_API_KEY="${ELEVENLABS_API_KEY:-}" \
  --from-literal=OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
  --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
  --from-literal=GEMINI_API_KEY="${GEMINI_API_KEY:-}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret '${SECRET_NAME}' applied in namespace '${NAMESPACE}'."
