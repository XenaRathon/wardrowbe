# Wardrobe Kubernetes Deployment

This directory contains Kubernetes manifests for deploying Wardrobe to a Kubernetes cluster.

## Prerequisites

1. **Kubernetes Cluster** - k3s, k8s, or similar
2. **Ingress Controller** - Traefik (included in k3s) or nginx-ingress
3. **cert-manager** - For automatic TLS certificates
4. **Container Registry** - Or direct image import to nodes

## Architecture

```
                    ┌─────────────────┐
                    │     Ingress     │
                    │  (TLS/HTTPS)    │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    │
   ┌─────────┐          ┌─────────┐               │
   │Frontend │          │ Backend │               │
   │  :3000  │          │  :8000  │               │
   └─────────┘          └────┬────┘               │
                             │                    │
                   ┌─────────┼─────────┐          │
                   │         │         │          │
                   ▼         ▼         ▼          │
              ┌────────┐ ┌────────┐ ┌────────┐   │
              │Postgres│ │ Redis  │ │ Worker │◄──┘
              │ :5432  │ │ :6379  │ │  (arq) │
              └────────┘ └────────┘ └────────┘
```

## Quick Start

### 1. Create Namespace

```bash
kubectl apply -f namespace.yaml
```

### 2. Configure Secrets

Copy the template and fill in your values:

```bash
cp secrets.yaml.template secrets.yaml
# Edit secrets.yaml with your values
```

Generate secure secrets:

```bash
# PostgreSQL password
openssl rand -hex 16

# NextAuth/Backend secrets
openssl rand -hex 32
```

Apply secrets:

```bash
kubectl apply -f secrets.yaml
```

### 3. Configure Settings

Edit `configmap.yaml` with your domain and AI settings:

```yaml
data:
  APP_URL: "https://wardrobe.example.com"
  NEXTAUTH_URL: "https://wardrobe.example.com"
  AI_BASE_URL: "https://api.openai.com/v1" # Or your Ollama/LocalAI URL
```

Apply config:

```bash
kubectl apply -f configmap.yaml
```

### 4. Deploy Infrastructure

```bash
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml

# Wait for pods to be ready
kubectl -n wardrobe get pods -w
```

### 5. Deploy Application

`backend.yaml`, `worker.yaml`, and `frontend.yaml` reference placeholder images
(`wardrobe/backend:latest`, `wardrobe/frontend:latest`) that don't exist in any public registry —
point them at real images first, either the project's published multi-arch (amd64/arm64) builds
or your own. See [Container Images](#container-images) below.

```bash
kubectl apply -f backend.yaml
kubectl apply -f worker.yaml
kubectl apply -f frontend.yaml
```

### 6. Configure Ingress

Edit `ingress.yaml` with your domain:

```yaml
spec:
  tls:
    - hosts:
        - wardrobe.example.com
  rules:
    - host: wardrobe.example.com
```

Apply:

```bash
kubectl apply -f ingress.yaml
```

### 7. Run Migrations

```bash
kubectl -n wardrobe exec deployment/backend -- alembic upgrade head
```

### 8. Apply Network Policies (Optional)

```bash
kubectl apply -f network-policy.yaml
```

## Files

| File                    | Description                                                                     |
| ----------------------- | ------------------------------------------------------------------------------- |
| `namespace.yaml`        | Namespace definition                                                            |
| `configmap.yaml`        | Non-sensitive configuration                                                     |
| `secrets.yaml.template` | Template for the `wardrobe-secrets` and `wardrobe-notifications` Secret objects |
| `secrets.yaml`          | Your secrets (DO NOT commit!)                                                   |
| `postgres.yaml`         | PostgreSQL database + PVC                                                       |
| `redis.yaml`            | Redis for job queue + PVC                                                       |
| `backend.yaml`          | FastAPI backend + PVC                                                           |
| `worker.yaml`           | arq background worker                                                           |
| `frontend.yaml`         | Next.js frontend                                                                |
| `ingress.yaml`          | Ingress configuration                                                           |
| `network-policy.yaml`   | Network isolation rules                                                         |
| `kustomization.yaml`    | Kustomize configuration                                                         |

## Configuration

### Container Images

`backend.yaml`, `worker.yaml`, and `frontend.yaml` ship with placeholder image references
(`wardrobe/backend:latest`, `wardrobe/frontend:latest`) — replace them before deploying:

- **Use the published images** (same ones the Docker Compose deployment pulls): set the image to
  `ghcr.io/anyesh/wardrowbe:backend-latest` / `ghcr.io/anyesh/wardrowbe:frontend-latest`, or pin to
  a release, e.g. `ghcr.io/anyesh/wardrowbe:backend-1.3.0`. Both are published multi-arch
  (`linux/amd64` and `linux/arm64`).
- **Build your own**: build `./backend` and `./frontend` (see the root
  [README's build pipeline notes](../README.md)), push to a registry your cluster can pull from,
  and point the manifests at that image instead.

`worker.yaml` reuses the backend image (it runs the same codebase as an arq worker process).

### AI Service

Configure your AI endpoint in `configmap.yaml`:

```yaml
# OpenAI
AI_BASE_URL: "https://api.openai.com/v1"
# Add AI_API_KEY in secrets.yaml

# Ollama (local)
AI_BASE_URL: "http://ollama:11434/v1"

# LocalAI
AI_BASE_URL: "http://localai:8080/v1"
```

`AI_TIMEOUT` (seconds the backend waits for one LLM response) and `AI_MAX_RETRIES` are also set
in `configmap.yaml`; slow local models often need `AI_TIMEOUT=300` or more.

Internal AI is optional. `AI_INTERNAL_ENABLED: "false"` runs the backend with no internal AI
provider at all, deferring tagging/suggestions/pairings to an external agent. With internal AI on,
`AI_VISION_ENABLED` and `AI_TEXT_ENABLED` can each be disabled individually; unset values inherit
the master switch. Check the effective state at `GET /api/v1/capabilities`.

### Notifications (Optional)

- **ntfy.sh**: set `NTFY_SERVER` / `NTFY_TOPIC` in `configmap.yaml`, and `ntfy-token` in the
  `wardrobe-notifications` secret if your topic requires auth.
- **Email**: set `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_NAME`, `SMTP_FROM_EMAIL` in
  `configmap.yaml`, and `smtp-user` / `smtp-password` in the `wardrobe-notifications` secret.

See `configmap.yaml` for the full, current set of keys — `LOG_LEVEL`, `AUTH_TRUST_HEADER`, and
`OIDC_MOBILE_CLIENT_ID` (for a separate mobile-app OIDC client) are also configured there.

### Authentication

Wardrobe supports multiple auth providers via NextAuth:

1. **Development Mode** (default): Simple email/name login
2. **OIDC Provider**: Authentik, Keycloak, Auth0, etc.

Configure OIDC in `configmap.yaml` and `secrets.yaml`:

```yaml
# configmap.yaml
OIDC_ISSUER_URL: "https://auth.example.com"

# secrets.yaml
oidc-client-id: "your-client-id"
oidc-client-secret: "your-client-secret"
```

### Storage

Each stateful service gets its own PVC, sized conservatively by default — resize any of them by
editing the `storage` request in the matching manifest before applying it:

| PVC                             | Manifest        | Default size |
| ------------------------------- | --------------- | ------------ |
| `uploads-pvc` (clothing photos) | `backend.yaml`  | 1Gi          |
| `postgres-pvc`                  | `postgres.yaml` | 5Gi          |
| `redis-pvc`                     | `redis.yaml`    | 1Gi          |

```yaml
spec:
  resources:
    requests:
      storage: 50Gi # Increase as needed
```

## Troubleshooting

### Check pod status

```bash
kubectl -n wardrobe get pods
kubectl -n wardrobe describe pod <pod-name>
```

### View logs

```bash
kubectl -n wardrobe logs deployment/backend
kubectl -n wardrobe logs deployment/frontend
kubectl -n wardrobe logs deployment/worker
```

### Database connection issues

```bash
# Check if DATABASE_URL is correct
kubectl -n wardrobe exec deployment/backend -- env | grep DATABASE

# Test postgres connection
kubectl -n wardrobe exec deployment/postgres -- psql -U wardrobe -c '\l'
```

### Certificate not issuing

```bash
kubectl -n wardrobe get certificates
kubectl -n wardrobe describe certificate <cert-name>
kubectl get challenges -A
```

## Useful Commands

```bash
# Restart deployments
kubectl -n wardrobe rollout restart deployment/backend
kubectl -n wardrobe rollout restart deployment/frontend

# Scale deployments
kubectl -n wardrobe scale deployment/backend --replicas=2

# Exec into pod
kubectl -n wardrobe exec -it deployment/backend -- bash

# Port forward for local access
kubectl -n wardrobe port-forward svc/backend 8000:8000
kubectl -n wardrobe port-forward svc/frontend 3000:3000
```
