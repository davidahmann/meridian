---
title: "Deploy ML Features Without Kubernetes"
description: "How to deploy ML features to production without Kubernetes. One-command deploys to Fly.io, Cloud Run, Railway, and more."
keywords: deploy ml features, feature store deployment, mlops without kubernetes, fly.io ml, railway ml deployment, simple ml deployment
date: 2025-01-06
---

# Deploy ML Features Without Kubernetes

Every ML deployment tutorial starts with:

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
# Debug why pods aren't starting for 3 hours
```

What if you could just run:

```bash
fabra deploy fly --name my-features
```

## The Kubernetes Tax

Kubernetes is powerful. It's also:

- **Complex:** 47 concepts to learn before "hello world"
- **Expensive:** Managed K8s costs $70-150/month minimum
- **Overkill:** Most ML features need one container, not an orchestration platform

For a feature store serving 1-10k requests per second, Kubernetes adds complexity without proportional benefit.

## The Alternative: Platform-as-a-Service

Modern PaaS platforms handle:

- Container orchestration
- Auto-scaling
- Load balancing
- SSL termination
- Health checks

For $5-50/month. With zero YAML.

## Fabra's Deploy Command

```bash
# Fly.io
fabra deploy fly --name my-app

# Google Cloud Run
fabra deploy cloudrun --name my-app --project my-gcp-project

# AWS ECS (via Copilot)
fabra deploy ecs --name my-app

# Railway
fabra deploy railway --name my-app

# Render
fabra deploy render --name my-app
```

Each command generates the right configuration files and deploys.

## What Gets Generated

### Fly.io

```bash
fabra deploy fly --name my-features
```

Creates:

**fly.toml:**
```toml
app = "my-features"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[env]
  FABRA_ENV = "production"

[http_service]
  internal_port = 8000
  force_https = true
  auto_start_machines = true
  auto_stop_machines = true
  min_machines_running = 1

[[services]]
  protocol = "tcp"
  internal_port = 8000

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
```

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["fabra", "serve", "features.py", "--host", "0.0.0.0"]
```

### Google Cloud Run

```bash
fabra deploy cloudrun --name my-features --project my-gcp-project
```

Creates:

**cloudbuild.yaml:**
```yaml
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/my-features', '.']
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/my-features']
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'run'
      - 'deploy'
      - 'my-features'
      - '--image=gcr.io/$PROJECT_ID/my-features'
      - '--platform=managed'
      - '--region=us-central1'
      - '--allow-unauthenticated'
```

## Setting Up Secrets

Production needs database and cache connections:

### Fly.io

```bash
fly secrets set FABRA_POSTGRES_URL="postgresql+asyncpg://..."
fly secrets set FABRA_REDIS_URL="redis://..."
```

### Cloud Run

```bash
gcloud secrets create fabra-postgres --data-file=-
gcloud secrets create fabra-redis --data-file=-

gcloud run services update my-features \
  --set-secrets=FABRA_POSTGRES_URL=fabra-postgres:latest \
  --set-secrets=FABRA_REDIS_URL=fabra-redis:latest
```

### Railway

```bash
railway variables set FABRA_POSTGRES_URL="postgresql+asyncpg://..."
railway variables set FABRA_REDIS_URL="redis://..."
```

## Production Stack Options

### Option 1: All-in-One (Simplest)

Use a platform that provides Postgres and Redis:

**Railway:**
- Deploy Fabra container
- Add Postgres plugin
- Add Redis plugin
- Connect via environment variables

Total: ~$10-30/month

**Render:**
- Deploy Fabra web service
- Add managed Postgres
- Add managed Redis
- Connect via environment variables

Total: ~$20-50/month

### Option 2: Managed Databases (More Control)

**Neon (Postgres) + Upstash (Redis):**
- Neon: Serverless Postgres with pgvector, generous free tier
- Upstash: Serverless Redis, pay-per-request
- Deploy Fabra to Fly.io/Cloud Run

Total: ~$5-20/month

### Option 3: Self-Hosted (Maximum Control)

**Single VM:**
- DigitalOcean/Linode $20/month droplet
- Docker Compose with Postgres, Redis, Fabra
- Nginx for SSL termination

Good for: teams who want full control.

## Docker Compose for Local Production Testing

Before deploying, test your production config locally:

```bash
fabra setup
# Generates docker-compose.yml
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  fabra:
    build: .
    ports:
      - "8000:8000"
    environment:
      FABRA_ENV: production
      FABRA_POSTGRES_URL: postgresql+asyncpg://postgres:yourpassword@postgres:5432/fabra  # pragma: allowlist secret
      FABRA_REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_PASSWORD: password
      POSTGRES_DB: fabra
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

```bash
docker-compose up
curl http://localhost:8000/health
```

## Health Checks

Fabra exposes health endpoints:

```bash
curl http://localhost:8000/health
# {"status": "healthy", "postgres": "connected", "redis": "connected"}

curl http://localhost:8000/ready
# {"status": "ready"}
```

Configure your platform to use these:

**Fly.io:**
```toml
[[services.http_checks]]
  interval = "10s"
  timeout = "2s"
  path = "/health"
```

**Cloud Run:**
```yaml
livenessProbe:
  httpGet:
    path: /health
readinessProbe:
  httpGet:
    path: /ready
```

## Scaling

### Horizontal Scaling

Most platforms auto-scale:

**Fly.io:**
```toml
[http_service]
  min_machines_running = 1
  max_machines_running = 10
```

**Cloud Run:**
```yaml
spec:
  containerConcurrency: 80
  autoscaling:
    minScale: 1
    maxScale: 10
```

### When to Scale

Fabra handles ~1000 requests/second per instance with async I/O. Scale when:

- P99 latency exceeds 100ms
- CPU utilization > 70%
- Memory usage > 80%

Most startups never need more than 2-3 instances.

## Cost Comparison

| Platform | Minimum Viable | With Traffic |
|----------|----------------|--------------|
| Fly.io | $5/month | $15-50/month |
| Cloud Run | $0 (scale to zero) | $10-50/month |
| Railway | $5/month | $15-40/month |
| Render | $7/month | $20-60/month |
| Kubernetes (GKE) | $70/month | $100-300/month |

Kubernetes is 10-20x more expensive for the same workload.

## Monitoring

Export Prometheus metrics:

```python
# Fabra exposes metrics at /metrics
curl http://localhost:8000/metrics
```

Key metrics:
- `fabra_feature_requests_total`
- `fabra_feature_latency_seconds`
- `fabra_cache_hit_ratio`

Connect to:
- **Grafana Cloud** (free tier)
- **Datadog** (paid)
- **Platform-native** (Fly.io Metrics, Cloud Run Monitoring)

## Try It

```bash
pip install "fabra[ui]"

# Create features
cat > features.py << 'EOF'
from fabra.core import FeatureStore, entity, feature

store = FeatureStore()

@entity(store)
class User:
    user_id: str

@feature(entity=User, refresh="5m")
def login_count(user_id: str) -> int:
    return abs(hash(user_id)) % 100
EOF

# Deploy to Fly.io
fabra deploy fly --name my-features
fly deploy

# Test
curl https://my-features.fly.dev/features/login_count?user_id=test123
```

No Kubernetes. No YAML. Just features.

[Full deployment guide →](../local-to-production.md)
