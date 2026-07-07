#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER_NAME="${KIND_CLUSTER_NAME:-latency-dashboard}"
NAMESPACE="${NAMESPACE:-default}"
SECRET_NAME="${SNOWFLAKE_SECRET_NAME:-latency-dashboard-snowflake}"

if [[ -z "${SNOWFLAKE_TOKEN:-}" ]]; then
  echo "Set SNOWFLAKE_TOKEN (and other SNOWFLAKE_* vars) before running." >&2
  echo "Example:" >&2
  echo "  export SNOWFLAKE_TOKEN='your_pat'" >&2
  echo "  export SNOWFLAKE_SQL_API_URL='https://myorg-myacct.snowflakecomputing.com/api/v2/statements'" >&2
  echo "  export SNOWFLAKE_WAREHOUSE='COMPUTE_WH'" >&2
  echo "  export SNOWFLAKE_DATABASE='LATENCY'" >&2
  exit 1
fi

kubectl create secret generic "${SECRET_NAME}" \
  --namespace "${NAMESPACE}" \
  --from-literal=SNOWFLAKE_TOKEN="${SNOWFLAKE_TOKEN}" \
  --from-literal=SNOWFLAKE_WAREHOUSE="${SNOWFLAKE_WAREHOUSE}" \
  --from-literal=SNOWFLAKE_DATABASE="${SNOWFLAKE_DATABASE}" \
  ${SNOWFLAKE_SQL_API_URL:+--from-literal=SNOWFLAKE_SQL_API_URL="${SNOWFLAKE_SQL_API_URL}"} \
  ${SNOWFLAKE_ACCOUNT:+--from-literal=SNOWFLAKE_ACCOUNT="${SNOWFLAKE_ACCOUNT}"} \
  ${SNOWFLAKE_SCHEMA:+--from-literal=SNOWFLAKE_SCHEMA="${SNOWFLAKE_SCHEMA}"} \
  ${SNOWFLAKE_ROLE:+--from-literal=SNOWFLAKE_ROLE="${SNOWFLAKE_ROLE}"} \
  ${SNOWFLAKE_RUNS_TABLE:+--from-literal=SNOWFLAKE_RUNS_TABLE="${SNOWFLAKE_RUNS_TABLE}"} \
  --dry-run=client -o yaml | kubectl apply -f -

echo "Secret '${SECRET_NAME}' applied in namespace '${NAMESPACE}'."
