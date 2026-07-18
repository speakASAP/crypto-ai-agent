#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'

SERVICE_NAME="crypto-ai-agent"
NAMESPACE="${NAMESPACE:-statex-apps}"
REGISTRY="${REGISTRY:-localhost:5000}"
# Tag describes the WORKING TREE that is actually built, not just git HEAD:
# a tag derived from HEAD alone repeats itself when files changed without a
# commit, which makes `kubectl set image` a no-op and silently keeps the old
# image running.
compute_default_tag() {
  local head dirty root
  root="${PROJECT_ROOT:-$(pwd)}"
  head="$(git -C "$root" rev-parse --short HEAD 2>/dev/null || true)"
  if [ -z "$head" ]; then
    echo "build-$(date -u +%Y%m%d%H%M%S)"
    return
  fi
  dirty="$(git -C "$root" status --porcelain 2>/dev/null || true)"
  if [ -n "$dirty" ]; then
    echo "${head}-wt$(date -u +%Y%m%d%H%M%S)"
  else
    echo "$head"
  fi
}

IMAGE_TAG="${1:-$(compute_default_tag)-$(date -u +%Y%m%d%H%M%S)}"
IMAGE="${REGISTRY}/${SERVICE_NAME}:${IMAGE_TAG}"
IMAGE_LATEST="${REGISTRY}/${SERVICE_NAME}:latest"
K8S_DIR="$PROJECT_ROOT/k8s"
EXTERNAL_SECRET_NAME="${SERVICE_NAME}-secret"
HEALTH_PATH="/api/ready"

# shellcheck disable=SC1091
source "$(dirname "$PROJECT_ROOT")/shared/scripts/load-deploy-phase-timing.sh" "$PROJECT_ROOT" 2>/dev/null \
  || source "$HOME/Documents/Github/shared/scripts/load-deploy-phase-timing.sh" "$PROJECT_ROOT" \
  || { echo "Error: deploy timing library not found" >&2; exit 1; }
deploy_timing_init "crypto-ai-agent"

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { local level="$1"; shift; printf "[%s] [%s] %s\n" "$(ts)" "$level" "$*"; }
phase() { echo -e "${BLUE}[$(ts)] $*${NC}"; }

diagnose() {
  log ERROR "Collecting deployment diagnostics"
  kubectl get deploy "$SERVICE_NAME" -n "$NAMESPACE" -o wide || true
  kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" -o wide || true
  kubectl describe deployment "$SERVICE_NAME" -n "$NAMESPACE" || true
  kubectl describe externalsecret "$EXTERNAL_SECRET_NAME" -n "$NAMESPACE" || true
  kubectl get events -n "$NAMESPACE" --sort-by=.metadata.creationTimestamp | tail -n 40 || true

  local pod
  for pod in $(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null || true); do
    echo -e "${YELLOW}[$(ts)] --- describe pod/${pod} ---${NC}"
    kubectl describe pod -n "$NAMESPACE" "$pod" || true
    echo -e "${YELLOW}[$(ts)] --- logs pod/${pod} (tail 160) ---${NC}"
    kubectl logs -n "$NAMESPACE" "$pod" --tail=160 || true
    echo -e "${YELLOW}[$(ts)] --- health pod/${pod} ---${NC}"
    kubectl exec -n "$NAMESPACE" "$pod" -- curl -sS -i "http://127.0.0.1:3000${HEALTH_PATH}" || true
  done
}

on_error() {
  local exit_code="$?"
  echo -e "${RED}[$(ts)] Deployment failed with exit code ${exit_code}${NC}" >&2
  diagnose
  exit "$exit_code"
}
trap on_error ERR

preflight_service_health() {
  log INFO "Preflight: checking Kubernetes, Docker, registry, and current service state"

  if ! kubectl get namespace "$NAMESPACE" >/dev/null 2>&1; then
    log ERROR "Namespace not found: $NAMESPACE"
    exit 1
  fi

  if ! kubectl get nodes >/dev/null 2>&1; then
    log ERROR "kubectl cannot reach cluster"
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    log ERROR "Docker is not available"
    exit 1
  fi

  if ! curl -fsS "http://${REGISTRY}/v2/" >/dev/null 2>&1; then
    log ERROR "Local registry is not reachable: ${REGISTRY}"
    exit 1
  fi

  BAD_PODS=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" --no-headers 2>/dev/null | awk '$3 ~ /Error|CrashLoopBackOff|ImagePullBackOff|CreateContainerConfigError|CreateContainerError|ErrImagePull/ {print $1}')
  if [ -n "$BAD_PODS" ]; then
    log ERROR "Service has pod errors before deploy: $BAD_PODS"
    diagnose
    exit 1
  fi

  echo -e "${GREEN}[$(ts)] Preflight passed${NC}"
}

wait_for_external_secret_ready() {
  phase "Waiting for ExternalSecret ${EXTERNAL_SECRET_NAME}"
  kubectl wait \
    --for=condition=Ready \
    "externalsecret/${EXTERNAL_SECRET_NAME}" \
    -n "$NAMESPACE" \
    --timeout=60s
}

echo -e "${BLUE}[$(ts)] ==========================================================${NC}"
echo -e "${BLUE}[$(ts)]   Crypto AI Agent - Kubernetes Deployment${NC}"
echo -e "${BLUE}[$(ts)] ==========================================================${NC}"

if [ ! -d "$K8S_DIR" ]; then
  log ERROR "Missing k8s directory: $K8S_DIR"
  exit 1
fi

cd "$PROJECT_ROOT"
deploy_timing_run_phase "Preflight" preflight_service_health

deploy_timing_phase_start "Build image"
phase "[1/7] Building Docker image ${IMAGE}"
docker build -t "$IMAGE" -t "$IMAGE_LATEST" "$PROJECT_ROOT"
deploy_timing_phase_end "Build image"

deploy_timing_phase_start "Push image"
docker push "$IMAGE"
docker push "$IMAGE_LATEST"
deploy_timing_phase_end "Push image"

deploy_timing_phase_start "Apply Kubernetes manifests"
for manifest in configmap.yaml external-secret.yaml service.yaml ingress.yaml deployment.yaml; do
  if [ -f "$K8S_DIR/$manifest" ]; then
    kubectl apply -f "$K8S_DIR/$manifest" -n "$NAMESPACE"
  fi
done
deploy_timing_phase_end "Apply Kubernetes manifests"

deploy_timing_phase_start "Verify ExternalSecret"
wait_for_external_secret_ready
deploy_timing_phase_end "Verify ExternalSecret"

deploy_timing_phase_start "Apply deployment image"
kubectl set env deployment/"$SERVICE_NAME" DATABASE_URL- -n "$NAMESPACE" || true
kubectl set image deployment/"$SERVICE_NAME" app="$IMAGE" -n "$NAMESPACE"
deploy_timing_phase_end "Apply deployment image"

deploy_timing_phase_start "Wait for rollout"
deploy_timing_k8s_rollout_wait kubectl "$SERVICE_NAME" "$NAMESPACE" "900s"
deploy_timing_phase_end "Wait for rollout"

deploy_timing_phase_start "Health check"
POD="$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" --no-headers | awk '$2=="1/1" && $3=="Running" {print $1; exit}')"
if [ -z "$POD" ]; then
  log ERROR "No ready pod found for ${SERVICE_NAME}"
  exit 1
fi
kubectl exec -n "$NAMESPACE" "$POD" -- curl -fsS "http://127.0.0.1:3000${HEALTH_PATH}" >/dev/null
log INFO "Health endpoint passed on pod/${POD}"

kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME"
deploy_timing_phase_end "Health check"

deploy_timing_finish_success "Crypto AI Agent"
DEPLOY_TIMING_FINISHED=1
exit 0
