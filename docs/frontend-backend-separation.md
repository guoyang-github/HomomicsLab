# Frontend / Backend Separation Deployment

HomomicsLab is built as a decoupled React frontend and FastAPI backend. This guide covers the minimal steps to deploy them on different hosts — for example, the backend on a Linux server and the frontend on a PC or static-file host.

## Quick overview

- The frontend is a static SPA. It only needs to know the backend URL.
- The backend needs to allow the frontend origin via CORS.
- WebSocket is used only for the optional presence/collaboration feature.

## 1. Choose how the frontend learns the backend URL

### Option A: Runtime `config.json` (recommended)

At startup the frontend requests `/config.json` and uses the values there. This lets the same build run in multiple environments.

Example `frontend/public/config.json`:

```json
{
  "apiBaseUrl": "http://your-server:8080/api",
  "wsUrl": "ws://your-server:8080"
}
```

- `apiBaseUrl` — prefix for all REST API calls.
- `wsUrl` — WebSocket base URL. If omitted, the frontend derives it from `apiBaseUrl` or falls back to the current host.

For the Docker frontend image, set environment variables instead of editing the file:

```bash
HOMOMICS_API_BASE_URL=http://your-server:8080/api
HOMOMICS_WS_URL=ws://your-server:8080
```

The container startup script writes these into `/usr/share/nginx/html/config.json` automatically.

### Option B: Build-time `VITE_API_BASE_URL`

Use this for non-Docker builds where the backend address is known when you build:

```bash
cd frontend
VITE_API_BASE_URL=http://your-server:8080/api npm run build
```

The build-time value is used as the fallback when `/config.json` is missing or the field is empty.

## 2. Configure the backend

Edit `.env` on the backend server:

```bash
HOMOMICS_HOST=0.0.0.0
HOMOMICS_PORT=8080
HOMOMICS_CORS_ORIGINS=["http://your-pc:5173"]
HOMOMICS_TRUSTED_HOSTS=your-server
```

- `HOMOMICS_CORS_ORIGINS` must include the exact origin where the frontend is served (including port).
- `HOMOMICS_TRUSTED_HOSTS` is optional but recommended for production.

If `HOMOMICS_CORS_ORIGINS` is empty and debug mode is off, the backend logs a warning at startup:

```
Cross-origin frontend requests will be blocked.
```

## 3. Start the services

### Backend

```bash
cd backend
python -m uvicorn homomics_lab.main:app --host 0.0.0.0 --port 8080
```

Or use Gunicorn for production:

```bash
gunicorn homomics_lab.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --workers 2
```

### Frontend

#### Local dev on PC

```bash
cd frontend
npm run dev
```

Create `frontend/public/config.json` pointing to the server, or rely on the Vite dev proxy (which forwards `/api` to `localhost:8080` by default).

#### Static build on PC

```bash
cd frontend
npm run build
```

Serve the `frontend/dist/` folder with any static server. Ensure `config.json` is present in `dist/`.

#### Docker on PC / server

```bash
cd frontend
docker build -t homomics-frontend .
docker run -e HOMOMICS_API_BASE_URL=http://your-server:8080/api \
           -e HOMOMICS_WS_URL=ws://your-server:8080 \
           -p 5173:8080 homomics-frontend
```

## 4. Verify

From the PC where the frontend runs:

```bash
curl http://your-server:8080/health
```

Then open the frontend in a browser and check the browser console for CORS errors. If you see:

```
CORS policy: No 'Access-Control-Allow-Origin' header
```

Add the frontend origin to `HOMOMICS_CORS_ORIGINS` on the backend and restart.

## 5. Authentication

When `HOMOMICS_AUTH_ENABLED=true`, the frontend reads the token from its auth store and sends it as a `Bearer` header. No extra CORS configuration is needed beyond the origin, but ensure the token is obtained before the first API call.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Network Error` from frontend | Backend unreachable or CORS blocked | Check `config.json` and `HOMOMICS_CORS_ORIGINS` |
| WebSocket connection fails | `wsUrl` wrong or backend not accepting WS | Verify `HOMOMICS_WS_URL` and that the backend host/port are reachable |
| Uploads fail | Reverse proxy body size too small | Increase `NGINX_CLIENT_MAX_BODY_SIZE` or equivalent |
| `config.json` not loaded | File missing from `dist/` or wrong path | Ensure `public/config.json` is copied to the build output |
