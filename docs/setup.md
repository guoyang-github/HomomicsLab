# HomicsLab Development Setup

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd homics-lab
make install

# 2. Start backend (terminal 1)
make dev-backend

# 3. Start frontend (terminal 2)
make dev-frontend

# 4. Open browser
# http://localhost:5173
```

## Production-like Local Setup

```bash
# SQLite is used by default
HOMICS_DATABASE_URL="sqlite+aiosqlite:///./homics_lab.db" homics-lab start
```

## Running Tests

```bash
make test-backend
make test-frontend
```

## CLI Usage

```bash
# Check version
homics-lab version

# Start server
homics-lab start
homics-lab start --port 9000 --reload
```
