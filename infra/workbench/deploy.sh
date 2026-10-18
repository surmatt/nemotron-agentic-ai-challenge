#!/usr/bin/env bash
# Push the workbench image to Nebius Container Registry and start a public CPU endpoint.
# Run from the repository root after `nebius profile create` and `nebius registry configure-helper`.
# The endpoint has no password. Anyone with the URL can run the live steps with the team's keys.
set -euo pipefail

: "${REGION_ID:?Set REGION_ID, for example uk-south2}"
: "${REGISTRY_PATH:?Set REGISTRY_PATH: the registry ID without the registry- prefix}"
NAME="${NAME:-nemotron-workbench}"
SECRET="${SECRET:-workbench-keys}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
PLATFORM="${PLATFORM:-cpu-d3}"
PRESET="${PRESET:-4vcpu-16gb}"
IMAGE="cr.${REGION_ID}.nebius.cloud/${REGISTRY_PATH}/${NAME}:${TAG}"
PROJECT="$(nebius config get parent-id)"

docker buildx build --platform linux/amd64 --push -f infra/workbench/Dockerfile -t "$IMAGE" .

# Split .env: URLs and model names go in as plain variables, API keys go to a MysteryBox secret.
env_args=()
keys=()
while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" == \#* || -z "$value" ]] && continue
  case "$key" in
    *_API_KEY) keys+=("$key") ;;
    WIKIPEDIA_API_URL|PARSE_*|RETRIEVAL_BASE_URL|SUPER_*) env_args+=(--env "$key=$value") ;;
  esac
done < .env

if ((${#keys[@]})); then
  if ! nebius mysterybox secret get-by-name --name "$SECRET" --parent-id "$PROJECT" >/dev/null 2>&1; then
    payload="$(uv run --quiet python -c 'import json, sys; from dotenv import dotenv_values
env = dotenv_values(".env")
print(json.dumps([{"key": k, "string_value": env[k]} for k in sys.argv[1:]]))' "${keys[@]}")"
    nebius mysterybox secret create --name "$SECRET" --parent-id "$PROJECT" \
      --secret-version-payload "$payload" >/dev/null
    echo "Created MysteryBox secret $SECRET with: ${keys[*]}"
  fi
  for key in "${keys[@]}"; do env_args+=(--env-secret "$key=$SECRET"); done
fi

nebius ai endpoint create --name "$NAME" --image "$IMAGE" \
  --platform "$PLATFORM" --preset "$PRESET" --disk-size 50Gi \
  --container-port 8790/http --auth none "${env_args[@]}"

echo "Read the public URL from status.public_endpoints:"
echo "  nebius ai endpoint get-by-name --name $NAME --format json | jq -r '.status.public_endpoints'"
echo "Stop it with: nebius ai endpoint stop <id>"
