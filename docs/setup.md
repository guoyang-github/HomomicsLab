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

# Domain management
homomics init metagenomics --phases "qc,denoising,taxonomy"
homomics validate domain.yaml
homomics install ./metagenomics --domains-dir ./backend/homomics_lab/domains
homomics list --domains-dir ./backend/homomics_lab/domains
```

## Useful Configuration

```bash
# Run with a local/embedded model instead of OpenAI
export HOMOMICS_LLM_PROVIDER=openai-compatible
export HOMOMICS_LLM_BASE_URL=http://localhost:11434/v1
export HOMOMICS_LLM_MODEL=qwen2.5:14b

# Enable bubblewrap/container sandbox for high-risk tools
export HOMOMICS_FORCE_SANDBOX=true
export HOMOMICS_SKILL_SANDBOX_BACKEND=bubblewrap

# Disable CodeAct cache for debugging
export HOMOMICS_CODEACT_CACHE_ENABLED=false
```
