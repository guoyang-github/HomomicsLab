# HomicsLab

A general-purpose agent for bioinformatics analysis.

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
