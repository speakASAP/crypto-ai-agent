# Deployment: Kubernetes (Primary)

Namespace: `statex-apps`
Secrets: all secrets in Vault → synced via ExternalSecret (`k8s/external-secret.yaml`)
See `k8s/` for all manifests.

## Deploy

```bash
./scripts/deploy.sh
```

Or manually:

```bash
kubectl apply -f k8s/ -n statex-apps
```

## Verify

```bash
kubectl get pods -n statex-apps -l app=crypto-ai-agent
kubectl logs -n statex-apps deploy/crypto-ai-agent
curl https://crypto-ai-agent.alfares.cz/api/health
```

## Rollback

```bash
kubectl rollout undo deployment/crypto-ai-agent -n statex-apps
```

## Manifests

| File | Purpose |
|------|---------|
| `deployment.yaml` | App deployment (1 replica, RollingUpdate) |
| `service.yaml` | ClusterIP service |
| `ingress.yaml` | Nginx ingress + TLS |
| `configmap.yaml` | Non-secret env vars |
| `external-secret.yaml` | Vault → K8s Secret sync |

## Secrets

All secrets stored in Vault: `secret/prod/crypto-ai-agent`
Synced automatically via ExternalSecret. Never put secrets in manifests.

## Database

Connects to shared `database-server` via K8s service name `db-server-postgres`.
See `../shared/docs/VAULT.md` for credential paths.

## Ports

| Service | Container Port | External |
|---------|---------------|----------|
| Backend (FastAPI) | 3000 | via ingress |
| Frontend (Next.js) | 3000 | via ingress |
