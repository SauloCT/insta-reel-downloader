#!/usr/bin/env bash
# Redeploy the insta-reel-downloader stack on Portainer
# Usage: ./scripts/redeploy.sh [--wait-ci]
# Requires: .env with PORTAINER_URL, PORTAINER_TOKEN, PORTAINER_STACK_NAME

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env not found at $ENV_FILE"
  exit 1
fi

set -a && source "$ENV_FILE" && set +a

PORTAINER_URL="${PORTAINER_URL%/}"
STACK_ID=17
ENDPOINT_ID=2

COMPOSE=$(cat "$SCRIPT_DIR/../docker-compose.yml")

echo "→ Redeploying stack '$PORTAINER_STACK_NAME' (id=$STACK_ID) on Portainer..."

RESPONSE=$(curl -sk -X PUT \
  -H "X-API-Key: $PORTAINER_TOKEN" \
  -H "Content-Type: application/json" \
  "$PORTAINER_URL/api/stacks/$STACK_ID?endpointId=$ENDPOINT_ID" \
  -d "{
    \"stackFileContent\": $(echo "$COMPOSE" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'),
    \"pullImage\": true,
    \"env\": []
  }")

if echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if 'Id' in d else 'FAIL')" 2>/dev/null | grep -q "OK"; then
  echo "✓ Stack redeployed successfully"
else
  echo "✗ Redeploy failed:"
  echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
  exit 1
fi
