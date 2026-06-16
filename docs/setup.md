# HomomicsLab Development Setup

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd HomomicsLab
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
HOMOMICS_DATABASE_URL="sqlite+aiosqlite:///./homomics_lab.db" homomics start
```

## Running Tests

```bash
make test-backend
make test-frontend
```

## CLI Usage

```bash
# Check version
homomics --version

# Start server
homomics start
homomics start --port 9000 --reload
```
