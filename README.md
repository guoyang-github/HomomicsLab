# HomicsLab

A general-purpose agent for bioinformatics analysis.

## Quick Start

```bash
make install
make dev-backend   # terminal 1
make dev-frontend  # terminal 2
# open http://localhost:5173
```

See [docs/setup.md](docs/setup.md) for detailed setup instructions and [docs/architecture.md](docs/architecture.md) for architecture overview.

## Setup

Requires Python 3.10 or newer.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e "."
```

## Development install

```bash
pip install -e ".[dev]"
```

## Verify installation

```bash
python -c "import homics_lab; print(homics_lab.__version__)"
```
