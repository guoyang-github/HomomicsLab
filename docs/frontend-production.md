# Frontend Production Deployment Notes

## Overview

The HomomicsLab frontend is a static React SPA served by nginx. In production it
should sit behind a TLS-terminating reverse proxy or load balancer.

## Nginx Template Variables

The production `nginx.conf` is processed with `envsubst` at container startup.
Available variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NGINX_SERVER_NAME` | `localhost` | Server name / production domain |
| `NGINX_BACKEND_HOST` | `backend` | Backend service hostname |
| `NGINX_BACKEND_PORT` | `8080` | Backend service port |
| `NGINX_CLIENT_MAX_BODY_SIZE` | `1G` | Max upload size |

## Example Production Configuration

```bash
# .env
NGINX_SERVER_NAME=app.homomics.lab
NGINX_BACKEND_HOST=backend
NGINX_BACKEND_PORT=8080
NGINX_CLIENT_MAX_BODY_SIZE=2G
```

```yaml
# docker-compose.prod.yml snippet
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  environment:
    NGINX_SERVER_NAME: ${NGINX_SERVER_NAME}
    NGINX_BACKEND_HOST: ${NGINX_BACKEND_HOST:-backend}
    NGINX_BACKEND_PORT: ${NGINX_BACKEND_PORT:-8080}
    NGINX_CLIENT_MAX_BODY_SIZE: ${NGINX_CLIENT_MAX_BODY_SIZE:-1G}
  ports:
    - "80:80"
```

## TLS Termination

Do **not** expose the nginx container directly on the public internet without
TLS. Recommended options:

1. **External reverse proxy** (recommended)
   - Traefik, Caddy, or nginx on the host handles HTTPS.
   - Forwards to the frontend container on port 80.

2. **Cloud load balancer**
   - AWS ALB, GCP Load Balancer, or Cloudflare Tunnel terminates TLS.

3. **Let's Encrypt sidecar**
   - Use `nginxproxy/acme-companion` or similar if you want TLS inside the
     compose stack.

## CORS

Set `HOMOMICS_CORS_ORIGINS` on the backend to your production frontend URL:

```env
HOMOMICS_CORS_ORIGINS=["https://app.homomics.lab"]
```

## API Key

When `HOMOMICS_AUTH_ENABLED=true`, the frontend must send the API key in every
request. Configure it in the frontend build-time or runtime environment and
attach it as `X-API-Key` header.
