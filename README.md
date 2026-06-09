# HomomicsLab

A general-purpose agent platform for bioinformatics analysis. Supports single-cell RNA-seq, spatial transcriptomics, genomics, and proteomics workflows through an extensible skill ecosystem.

## Features

- **Agent Orchestration** — Task decomposition, multi-agent collaboration, TODO tracking
- **Skill Ecosystem** — 74 built-in bioinformatics skills (Python + R), auto-generation, self-evolution via A/B testing
- **HPC Integration** — Local / SLURM / Nextflow execution backends
- **Semantic Search** — TF-IDF + sentence-transformers dual-engine skill discovery
- **Visualization** — 6 chart types (UMAP, heatmap, violin, bar, scatter, histogram) with frontend rendering
- **Report Generation** — Self-contained HTML and Markdown analysis reports
- **Context Compression** — Intelligent relevance filtering and summarization
- **Human-in-the-Loop** — Interactive checkpoints with parameter forms
- **Docker Deployment** — One-command containerized setup

## Quick Start

### Docker (Recommended)

```bash
docker-compose up --build
# Backend: http://localhost:8080
# Frontend: http://localhost:3000
```

### Local Development

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn homomics_lab.main:app --reload --port 8080

# Frontend (new terminal)
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

## Project Structure

```
HomomicsLab/
├── backend/
│   ├── homomics_lab/
│   │   ├── agent/          # Agent orchestrator, task decomposer
│   │   ├── skills/         # Skill registry, sandbox, external loader
│   │   │   ├── generator/  # Auto-generate skills from requirements
│   │   │   ├── semantic_search.py      # TF-IDF search
│   │   │   ├── semantic_search_v2.py   # Dense embedding search
│   │   │   └── ...
│   │   ├── hpc/            # SLURM, Nextflow, local schedulers
│   │   ├── context/        # Working memory, relevance filter, compressor
│   │   ├── viz/            # Matplotlib plot generator
│   │   ├── reports/        # HTML/Markdown report engine
│   │   └── api/            # FastAPI endpoints
│   └── tests/              # 214 tests
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── chat/       # Chat panel, HITL, plot rendering
│       │   ├── workspace/  # Workflow canvas, tabs
│       │   ├── reports/    # Report list + viewer
│       │   └── skills/     # Skill search + generator
│       └── stores/         # Zustand state management
├── Dockerfile              # Backend container
├── docker-compose.yml      # Full stack deployment
└── docs/                   # Architecture + setup docs
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/chat/send` | Send message to agent |
| `GET /api/skills/` | List all skills |
| `GET /api/skills/search?q=` | Search skills |
| `POST /api/viz/plot` | Generate plot |
| `POST /api/reports/create` | Create report |
| `GET /api/reports/{id}/html` | Export HTML report |
| `POST /api/skill-generator/generate` | Auto-generate skill |

## Testing

```bash
cd backend
pytest tests/ -q
# 214 tests passing
```

## Configuration

Environment variables (prefix `HOMOMICS_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HOMOMICS_PORT` | 8080 | API server port |
| `HOMOMICS_EXTERNAL_SKILLS_DIR` | — | Path to external skill collection |
| `HOMOMICS_SEMANTIC_SEARCH_MODEL` | — | Set to `all-MiniLM-L6-v2` for dense embeddings |

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic, SQLAlchemy, scikit-learn, sentence-transformers
- **Frontend**: React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query
- **Workflows**: Nextflow (DSL2), SLURM (sbatch/sacct)
- **Deployment**: Docker, Docker Compose, nginx

## License

MIT
