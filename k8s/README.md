# Kubernetes Deployment

## Prerequisites

1. Create the namespace:
   ```bash
   kubectl apply -f namespace.yaml
   ```

2. Create secrets (copy from example and fill in values):
   ```bash
   cp secret.yaml.example secret.yaml
   # Edit secret.yaml with actual values
   kubectl apply -f secret.yaml
   ```

3. Update configmap with your ClickHouse host:
   ```bash
   kubectl apply -f configmap.yaml
   ```

## Deploy

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## Verify

```bash
kubectl -n ai-bios get pods
kubectl -n ai-bios logs -f deployment/twc-ai-bios
```

## Internal Access

This service is internal-only (no public ingress). Other services in the cluster
access it via Kubernetes DNS:

```
http://twc-ai-bios.ai-bios.svc.cluster.local/api/v1/customers/{customer_ref}/bio
```

**Example endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `.../api/v1/customers/{customer_ref}/bio` | Get cached bio |
| `POST` | `.../api/v1/customers/{customer_ref}/bio/generate` | Generate new bio |
| `PUT` | `.../api/v1/customers/{customer_ref}/bio` | Staff edit bio |
| `POST` | `.../api/v1/customers/{customer_ref}/bio/reset` | Reset to AI-generated |
| `GET` | `.../api/v1/settings/bio` | Get retailer settings |
| `PUT` | `.../api/v1/settings/bio` | Update retailer settings |
| `GET` | `.../health` | Health check |

**Required headers** (injected by FE proxy from authenticated user context):
- `X-Tenant-ID`: Retailer identifier
- `X-User-ID`: Staff user identifier

## Local Testing

Run locally with Docker:
```bash
docker build -t twc-ai-bios .
docker run -p 8000:8000 --env-file .env twc-ai-bios
```

Then access:
- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs
