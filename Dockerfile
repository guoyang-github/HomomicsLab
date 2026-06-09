# HomomicsLab Backend
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    r-base \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/pyproject.toml backend/README.md ./
RUN pip install --no-cache-dir -e ".[dev]" || true

# Copy backend code
COPY backend/ ./

# Install runtime dependencies explicitly
RUN pip install --no-cache-dir fastapi uvicorn pydantic sqlalchemy scikit-learn sentence-transformers

EXPOSE 8080

CMD ["uvicorn", "homomics_lab.main:app", "--host", "0.0.0.0", "--port", "8080"]
