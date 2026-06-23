"""Gunicorn production configuration for HomomicsLab backend."""

import multiprocessing

# Server socket
bind = "0.0.0.0:8080"

# Worker processes: 1 worker per CPU core, minimum 2, capped at 4 for small deployments.
workers = max(2, min(multiprocessing.cpu_count(), 4))

# Uvicorn ASGI worker class
worker_class = "uvicorn.workers.UvicornWorker"

# Timeouts (seconds)
timeout = 120
keepalive = 5
graceful_timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Preload app to reduce memory footprint (safe once DB connections are created lazily).
preload_app = True

# Worker tmp dir for heartbeat files (use /tmp which is writable in most containers)
worker_tmp_dir = "/tmp"
