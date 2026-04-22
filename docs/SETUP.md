# TWC AI Bios - Setup & Deployment Guide

This document provides instructions for setting up and deploying the AI Bios service.

---

## Overview

The AI Bios service generates AI-powered customer biographies for retail staff. It aggregates customer data from ClickHouse, sends it to Claude AI for bio generation, and caches results in DynamoDB.

**Architecture:**
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  AI Bios    │────▶│ ClickHouse  │
│  (Staff UI) │     │   Service   │     │  (read)     │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              ┌──────────┐  ┌──────────┐
              │ DynamoDB │  │  Claude  │
              │ (cache)  │  │   API    │
              └──────────┘  └──────────┘
```

---

## Prerequisites

### 1. Infrastructure Requirements

| Component | Purpose | Notes |
|-----------|---------|-------|
| **ClickHouse** | Customer data source | Read-only access needed |
| **DynamoDB** | Bio cache + settings | 2 tables required |
| **Anthropic API** | Claude AI for generation | API key required |
| **AWS IAM** | DynamoDB access | Service role or credentials |

### 2. DynamoDB Tables

Create two DynamoDB tables:

**Table 1: `twc-customer-bios`**
```
Partition Key: tenant_id (String)
Sort Key: customer_ref (String)
```

**Table 2: `twc-retailer-settings`**
```
Partition Key: tenant_id (String)
```

AWS CLI commands:
```bash
# Bio cache table
aws dynamodb create-table \
  --table-name twc-customer-bios \
  --attribute-definitions \
    AttributeName=tenant_id,AttributeType=S \
    AttributeName=customer_ref,AttributeType=S \
  --key-schema \
    AttributeName=tenant_id,KeyType=HASH \
    AttributeName=customer_ref,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-2

# Retailer settings table
aws dynamodb create-table \
  --table-name twc-retailer-settings \
  --attribute-definitions \
    AttributeName=tenant_id,AttributeType=S \
  --key-schema \
    AttributeName=tenant_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-southeast-2
```

### 3. ClickHouse Access

The service requires read access to these ClickHouse tables:
- `TWCCUSTOMER` - Customer profiles
- `TWCPREFERENCES` - Customer preferences (likes/dislikes/sizes)
- `TWCALLORDERS` - Order history
- `ORDERLINE` - Order line items
- `TWCVARIANT` - Product variants
- `TWCWISHLIST` / `WISHLISTITEM` - Wishlist data
- `TWCCLICKSTREAM` - Browsing behavior
- `TWCCUSTOMER_MESSAGE` - Customer messages

### 4. Anthropic API Key

Obtain an API key from [Anthropic Console](https://console.anthropic.com/).

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key |
| `CLICKHOUSE_HOST` | Yes | localhost | ClickHouse hostname |
| `CLICKHOUSE_PORT` | No | 8443 | ClickHouse port |
| `CLICKHOUSE_USER` | No | default | ClickHouse username |
| `CLICKHOUSE_PASSWORD` | Yes | - | ClickHouse password |
| `CLICKHOUSE_DATABASE` | No | default | ClickHouse database |
| `AWS_REGION` | No | ap-southeast-2 | AWS region |
| `BIO_CACHE_TABLE` | No | twc-customer-bios | DynamoDB cache table |
| `RETAILER_SETTINGS_TABLE` | No | twc-retailer-settings | DynamoDB settings table |

---

## Local Development

### 1. Clone Repository

```bash
git clone git@github.com:mjhampshire/ai-bios.git
cd ai-bios
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 4. Run Locally

```bash
uvicorn src.main:app --reload --port 8000
```

### 5. Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# View API docs
open http://localhost:8000/docs

# Get bio (requires headers)
curl -H "X-Tenant-ID: viktoria-woods" \
     -H "X-User-ID: staff123" \
     http://localhost:8000/api/v1/customers/CUST001/bio

# Generate bio
curl -X POST \
     -H "X-Tenant-ID: viktoria-woods" \
     -H "X-User-ID: staff123" \
     -H "Content-Type: application/json" \
     -d '{}' \
     http://localhost:8000/api/v1/customers/CUST001/bio/generate
```

---

## Docker Deployment

### 1. Build Image

```bash
docker build -t twc-ai-bios:latest .
```

### 2. Run Container

```bash
docker run -d \
  --name twc-ai-bios \
  -p 8000:8000 \
  --env-file .env \
  twc-ai-bios:latest
```

### 3. Push to ECR

```bash
# Authenticate with ECR
aws ecr get-login-password --region ap-southeast-2 | \
  docker login --username AWS --password-stdin 354582224285.dkr.ecr.ap-southeast-2.amazonaws.com

# Tag and push
docker tag twc-ai-bios:latest 354582224285.dkr.ecr.ap-southeast-2.amazonaws.com/twc-ai-bios:latest
docker push 354582224285.dkr.ecr.ap-southeast-2.amazonaws.com/twc-ai-bios:latest
```

---

## Kubernetes Deployment

### 1. Create Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### 2. Create Secrets

```bash
# Copy and edit secret template
cp k8s/secret.yaml.example k8s/secret.yaml
# Edit k8s/secret.yaml with actual values

kubectl apply -f k8s/secret.yaml
```

**Important:** Never commit `k8s/secret.yaml` to version control.

### 3. Update ConfigMap

Edit `k8s/configmap.yaml` with your ClickHouse host and other settings:

```yaml
data:
  CLICKHOUSE_HOST: "your-actual-clickhouse-host"
```

```bash
kubectl apply -f k8s/configmap.yaml
```

### 4. Update Deployment Image

Edit `k8s/deployment.yaml` to use your ECR repository:

```yaml
image: 354582224285.dkr.ecr.ap-southeast-2.amazonaws.com/twc-ai-bios:latest
```

### 5. Deploy

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### 6. Verify Deployment

```bash
# Check pods
kubectl -n ai-bios get pods

# Check logs
kubectl -n ai-bios logs -f deployment/twc-ai-bios

# Port forward for testing
kubectl -n ai-bios port-forward svc/twc-ai-bios 8000:80

# Test health endpoint
curl http://localhost:8000/health
```

---

## API Reference

### Authentication

All endpoints require two headers:
- `X-Tenant-ID`: Retailer identifier (e.g., `viktoria-woods`)
- `X-User-ID`: Staff user identifier

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/docs` | OpenAPI documentation |
| `GET` | `/api/v1/customers/{customer_ref}/bio` | Get cached bio |
| `POST` | `/api/v1/customers/{customer_ref}/bio/generate` | Generate new bio |
| `PUT` | `/api/v1/customers/{customer_ref}/bio` | Staff edit bio |
| `POST` | `/api/v1/customers/{customer_ref}/bio/reset` | Reset to AI-generated |
| `GET` | `/api/v1/customers/{customer_ref}/bio/staleness` | Check if bio is stale |

### Example: Generate Bio

```bash
curl -X POST \
  -H "X-Tenant-ID: viktoria-woods" \
  -H "X-User-ID: staff123" \
  -H "Content-Type: application/json" \
  -d '{"regenerate": false}' \
  https://api.example.com/api/v1/customers/CUST001/bio/generate
```

**Response:**
```json
{
  "exists": true,
  "bio": "**Sarah Mitchell** has been a valued VIP customer since March 2022...",
  "conversation_starters": [
    "Ask about the Zimmermann dress she wishlisted last week",
    "She recently purchased blazers - show the new autumn collection"
  ],
  "generated_at": "2024-01-15T10:30:00Z",
  "generated_by": "staff123",
  "is_staff_edited": false,
  "is_stale": false
}
```

---

## Retailer Settings

Each retailer can customize bio generation via the `twc-retailer-settings` DynamoDB table.

**Example settings record:**
```json
{
  "tenant_id": "viktoria-woods",
  "bio_settings": {
    "tone": "luxury",
    "include_spend_data": true,
    "include_conversation_starters": true,
    "max_notes_to_include": 10,
    "language": "en-AU"
  }
}
```

**Tone options:**
- `professional` - Business-appropriate, formal
- `friendly` - Warm, casual, personable
- `luxury` - Elegant, refined, premium feel

To insert settings:
```bash
aws dynamodb put-item \
  --table-name twc-retailer-settings \
  --item '{
    "tenant_id": {"S": "viktoria-woods"},
    "bio_settings": {"M": {
      "tone": {"S": "luxury"},
      "include_spend_data": {"BOOL": true},
      "include_conversation_starters": {"BOOL": true}
    }}
  }' \
  --region ap-southeast-2
```

---

## Monitoring

### Health Check

The `/health` endpoint returns:
```json
{"status": "healthy", "service": "twc-ai-bios"}
```

Configure your monitoring to poll this endpoint.

### Logs

The service logs to stdout. In Kubernetes, use:
```bash
kubectl -n ai-bios logs -f deployment/twc-ai-bios
```

### Key Metrics to Monitor

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Pod restarts | Kubernetes | > 3 in 10 min |
| Health check failures | Load balancer | > 2 consecutive |
| Response latency | Application | p95 > 10s |
| Error rate | Application logs | > 5% |

---

## Troubleshooting

### Pod won't start

1. Check secrets are created:
   ```bash
   kubectl -n ai-bios get secrets
   ```

2. Check configmap:
   ```bash
   kubectl -n ai-bios get configmap twc-ai-bios-config -o yaml
   ```

3. Check pod events:
   ```bash
   kubectl -n ai-bios describe pod <pod-name>
   ```

### ClickHouse connection failed

1. Verify host is reachable from cluster
2. Check credentials in secret
3. Verify ClickHouse port (usually 8443 for HTTPS)

### DynamoDB access denied

1. Check IAM role/credentials have DynamoDB permissions
2. Verify table names match config
3. Check AWS region

### Claude API errors

1. Verify `ANTHROPIC_API_KEY` is set correctly
2. Check API key has sufficient quota
3. Review Claude API status page

---

## Security Considerations

1. **Never commit secrets** - Use Kubernetes secrets or external secret management
2. **Use HTTPS** - Configure ingress with TLS
3. **Restrict network access** - Use network policies to limit pod communication
4. **Audit API access** - Log all bio generation/edit requests
5. **PII handling** - Bios may contain customer PII; ensure compliance with privacy policies

---

## Support

For issues or questions:
- Repository: https://github.com/mjhampshire/ai-bios
- Design doc: `docs/DESIGN.md`
