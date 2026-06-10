#!/usr/bin/env bash
# Deploy Victros to Azure — no CI/CD needed.
# Run from the repo root:  ./deploy.sh
#
# Prerequisites:
#   az login  (you're already logged in if this was just provisioned)
#   npm       (for the frontend build)
#
# NOTE: These resource names match the Bicep output (infra/main.bicep).
# If you changed the 'environment' parameter or resource group name,
# update these values to match your deployment outputs.
#
set -euo pipefail

RG="rg-victros-prod"
ACR="acrvictrosprod"
CONTAINER_APP="ca-victros-prod-backend"
SWA="swa-victros-prod"
IMAGE="victros-backend"
TAG="sha-$(git rev-parse --short HEAD)"

deploy_backend() {
  echo "=== Backend: build + push image to ACR ==="
  az acr build \
    --registry "$ACR" \
    --image "${IMAGE}:${TAG}" \
    --image "${IMAGE}:latest" \
    --file victros-poc/backend/Dockerfile \
    --build-arg BUILD_SHA="$TAG" \
    victros-poc

  echo "=== Backend: update Container App ==="
  az containerapp update \
    --name "$CONTAINER_APP" \
    --resource-group "$RG" \
    --image "${ACR}.azurecr.io/${IMAGE}:${TAG}"

  echo "Backend deployed: ${TAG}"
}

deploy_frontend() {
  echo "=== Frontend: deployed via GitHub Actions ==="
  echo "Frontend deploys are handled by the GitHub Actions workflow"
  echo "(frontend.yml) which triggers on push to main."
  echo ""
  echo "SWA Easy Auth requires deployment via Azure/static-web-apps-deploy@v1"
  echo "(the GitHub Actions action), NOT the SWA CLI. The SWA CLI overwrites"
  echo "portal-managed auth config and breaks the OIDC redirect flow."
  echo ""
  echo "To deploy frontend: push to main and the workflow will run."
  echo ""
  echo "Checking latest workflow run..."
  gh run list --workflow=frontend.yml --limit=3 2>/dev/null || echo "(install gh CLI to check workflow status)"
  echo ""
  echo "Frontend deployed via GitHub Actions"
}

# Parse args: default = deploy both; pass "backend" or "frontend" to deploy one
case "${1:-both}" in
  backend)  deploy_backend ;;
  frontend) deploy_frontend ;;
  both)     deploy_backend && deploy_frontend ;;
  *)
    echo "Usage: ./deploy.sh [backend|frontend|both]"
    exit 1
    ;;
esac

echo ""
echo "Done. Check your SWA URL from the Bicep deployment output."
