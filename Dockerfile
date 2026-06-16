# HomomicsLab Backend
# Multi-stage build for reproducible, production-ready deployment.

FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools, R runtime for R-based skills, and uv.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    r-base \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# Copy dependency manifests and source for the editable install.
COPY pyproject.toml uv.lock README.md ./
COPY backend/ ./backend/

# Export a locked requirements file from uv.lock (production deps only).
RUN uv export --locked --no-dev -o requirements.txt

# --- Production stage ---
FROM python:3.12-slim AS production

WORKDIR /app

# Install runtime-only system dependencies (R + basic tools for skill execution).
RUN apt-get update && apt-get install -y --no-install-recommends \
    r-base \
    bubblewrap \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security.
RUN groupadd -r homomics && useradd -r -g homomics -d /app homomics

# Copy locked requirements, install dependencies, then install the package.
COPY --chown=homomics:homomics pyproject.toml README.md ./
COPY --chown=homomics:homomics backend/ ./backend/
COPY --chown=homomics:homomics --from=builder /app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir hatchling \
    && pip install --no-cache-dir -r requirements.txt -e .

# Ensure the editable install metadata is present so console scripts work.
RUN python -c "import homomics_lab; print(homics_lab.__file__)"

# Create writable directories for data and results.
RUN mkdir -p /app/data /app/results /app/workspace && chown -R homomics:homomics /app

USER homomics

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["uvicorn", "homomics_lab.main:app", "--host", "0.0.0.0", "--port", "8080"]
