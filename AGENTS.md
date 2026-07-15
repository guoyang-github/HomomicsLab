# AGENTS.md — HomomicsLab

> This file is written for AI coding agents that need to work on the HomomicsLab codebase. It is based on the actual files in the repository. At the time it was created, no root `AGENTS.md` existed, so this is a fresh summary of the project's architecture, conventions, build/test commands, and security model.

## Project overview

HomomicsLab is a domain-native AI agent platform for computational biology. It turns natural-language research questions into reproducible, auditable analysis workflows, combining agentic planning with production-grade data engineering.

The repository contains:

- A Python **backend** (`backend/homomics_lab/`) built with FastAPI, Pydantic v2, and SQLAlchemy.
- A React 18 + TypeScript **frontend** (`frontend/`).
- Declarative **domains** (`backend/homomics_lab/domains/*/domain.yaml`) that define analysis strategies, intents, roles, SOPs, and SkillDAG seeds.
- A **skill ecosystem** using the unified `SKILL.md + scripts/` format.
- HPC/workflow orchestration backends (local, SLURM, Nextflow, nf-core).
- Docker Compose and Helm deployment artifacts.

The package version in `pyproject.toml` is `0.5.0`. The project documentation refers to the running feature set as **v0.5.0** (see `README.md` and `CHANGELOG.md`).

## Repository layout

```text
HomomicsLab/
├── backend/
│   ├── homomics_lab/            # Main Python package
│   │   ├── agent/               # Agent orchestration (core, plan, intent, swarm, etc.)
│   │   ├── api/                 # FastAPI routers
│   │   ├── cli/                 # `homomics` command-line tool
│   │   ├── config.py            # Pydantic-Settings configuration (HOMOMICS_* env vars)
│   │   ├── context/             # Memory, context engine, session/semantic stores
│   │   ├── data/                # DataStore for large result offloading
│   │   ├── database/            # SQLAlchemy models / connection helpers
│   │   ├── domain/              # Domain loader, registry, marketplace, hot-reload
│   │   ├── domains/             # Built-in domain declarations
│   │   ├── embeddings/          # Embedding-provider factory
│   │   ├── evaluation/          # Lightweight evaluation harness
│   │   ├── execution/           # CodeAct executor, code cache, code safety audit
│   │   ├── hpc/                 # Local/SLURM/Nextflow schedulers
│   │   ├── jobs/                # Background job queue and runner
│   │   ├── knowledge/           # CBKB knowledge base and curator
│   │   ├── llm/                 # LLM client, cache, runtime config
│   │   ├── mcp/                 # MCP tool integration
│   │   ├── models/              # Shared Pydantic / SQLAlchemy models
│   │   ├── observability/       # Trace store
│   │   ├── plan/                # PlanEngine and strategy library
│   │   ├── preferences/         # User preferences
│   │   ├── projects/            # Project management
│   │   ├── provenance/          # Provenance recorder
│   │   ├── reports/             # Report generation
│   │   ├── reproducibility/     # Reproducibility bundle engine
│   │   ├── skills/              # Skill loader, runtime, cache, DAG, store
│   │   ├── stability/           # Schema validation, version locking, regression testing
│   │   ├── tasks/               # Task state machine helpers
│   │   ├── templates/           # Analysis templates
│   │   ├── tools/               # Tool registry, approval flow, cross-process invocation
│   │   ├── viz/                 # Visualization helpers
│   │   ├── workspace/           # Workspace / artifact / lineage management
│   │   ├── worker.py            # Standalone worker entry point
│   │   ├── bootstrap.py         # Shared runtime bootstrap for API and worker
│   │   └── main.py              # FastAPI application factory + lifespan
│   ├── alembic/                 # Database migrations
│   ├── alembic.ini              # Alembic config (uses HOMOMICS_DATABASE_URL)
│   └── tests/                   # pytest suite (223 test files, ~900 tests)
├── frontend/
│   ├── src/                     # React/TypeScript source (~90 .ts/.tsx files)
│   │   ├── components/          # UI component library + feature views
│   │   ├── hooks/               # Theme, keyboard shortcuts, command palette
│   │   ├── services/            # API/WebSocket clients
│   │   ├── stores/              # Zustand state management
│   │   ├── types/               # Shared TypeScript types
│   │   └── utils/               # Pure helpers (e.g. subagent log grouping)
│   ├── e2e/                     # Playwright end-to-end tests
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── playwright.config.ts
│   ├── tailwind.config.js
│   └── Dockerfile
├── deploy/helm/homomicslab/     # Helm chart
├── docs/                        # Architecture/design/operations guides
├── skills/                      # Empty top-level skill directory (canonical store lives under data/)
├── data/                        # Runtime data, caches, skill store
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── docker-compose.prod.yml
├── gunicorn.conf.py
├── Makefile
└── .env.example
```

## Technology stack

- **Backend**: Python 3.10–3.13 (project metadata says `>=3.10,<3.14`), FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, Uvicorn, Gunicorn.
- **Databases**: SQLite + aiosqlite for local dev/tests; PostgreSQL + asyncpg for production. Redis for queues. Qdrant/pgvector/sqlite-vec for vectors. NetworkX or Neo4j for graph backend.
- **Storage**: Local filesystem or S3-compatible object storage (MinIO configuration included).
- **LLMs**: OpenAI-compatible, OpenAI, Anthropic, Ollama, DeepSeek, Qwen, Zhipu, Moonshot, etc. Configured via `HOMOMICS_LLM_PROVIDER` / `HOMOMICS_LLM_MODEL`.
- **Frontend**: React 18, TypeScript 5, Vite 6, Tailwind CSS 3, Zustand, TanStack Query, React Flow, Plotly.js, Socket.IO client, KaTeX.
- **Workflows**: Nextflow DSL2, nf-core, SLURM `sbatch`/`squeue`/`sacct`.
- **Deployment**: Docker, Docker Compose, Helm, nginx.
- **Package/lock**: `pyproject.toml` uses `hatchling`; `uv.lock` is present.

## Configuration

All backend settings are defined in `backend/homomics_lab/config.py` and read from environment variables with the prefix `HOMOMICS_`. Copy `.env.example` to `.env` and edit.

Key variables:

| Variable | Typical value / default | Purpose |
|---|---|---|
| `HOMOMICS_DEBUG` | `false` | Verbose logging / dev behavior |
| `HOMOMICS_PORT` | `8080` | API port |
| `HOMOMICS_DATABASE_URL` | `sqlite+aiosqlite:///./homomics_lab.db` | Primary database |
| `HOMOMICS_SESSION_STORE_URL` | `sqlite+aiosqlite:///./data/sessions.db` | Session store |
| `HOMOMICS_QUEUE_BACKEND` | `memory` / `redis` | Job queue backend |
| `HOMOMICS_REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `HOMOMICS_STORAGE_BACKEND` | `local` / `s3` | Object storage |
| `HOMOMICS_LLM_PROVIDER` | `openai`, `openai-compatible`, `ollama`, ... | LLM provider |
| `HOMOMICS_LLM_MODEL` | `gpt-4o-mini` | Default model |
| `HOMOMICS_AUTH_ENABLED` | `false` | API-key / JWT auth (opt-in) |
| `HOMOMICS_FORCE_SANDBOX` | `true` | Force sandbox for shell/code execution |
| `HOMOMICS_SKILL_SANDBOX_BACKEND` | `auto` | `local`, `bubblewrap`, `container`, `auto` |
| `HOMOMICS_CODEACT_CACHE_ENABLED` | `true` | Cache CodeAct-generated code |
| `HOMOMICS_SKILL_CACHE_ENABLED` | `true` | Memoize deterministic skill results |
| `HOMOMICS_AGENT_TOOL_OUTPUT_MAX_CHARS` | `4000` | Per-tool output budget before `_compact_tool_output` truncation (errors keep the tail, get 1.5x budget) |
| `HOMOMICS_WORKER_MODE` | `true` | Run a local worker inside the API process |
| `HOMOMICS_CURATION_ENABLED` | `false` | Nightly CBKB curation (disabled by default) |
| `HOMOMICS_EVOLUTION_ENABLED` | `false` | Nightly agent evolution (disabled by default) |

The frontend uses `VITE_API_BASE_URL` and `VITE_WS_URL` for build-time/dev proxy configuration (see `frontend/vite.config.ts`).

Note: relative SQLite URLs in `HOMOMICS_DATABASE_URL` / `HOMOMICS_SESSION_STORE_URL` are anchored to the `backend/` directory at load time (`_abs_sqlite_url` in `config.py`), so `Settings()` resolves them to absolute paths rather than CWD-dependent relative ones.

## Build and run commands

### Local development

```bash
# Install both backend and frontend dependencies
make install

# Terminal 1 — backend (run from repo root)
make dev-backend
# Equivalent to: cd backend && uvicorn homomics_lab.main:app --reload --port 8080

# Terminal 2 — frontend
make dev-frontend
# Equivalent to: cd frontend && npm run dev
# Open http://localhost:5173
```

### Docker (recommended for full-stack)

```bash
# Development stack: postgres, redis, minio, backend, worker, frontend
docker compose up --build
# Backend:  http://localhost:8080
# Frontend: http://localhost:3000
# MinIO console: http://localhost:9001

# Production stack
cp .env.example .env
# edit .env with real secrets
docker compose -f docker-compose.prod.yml up -d
```

### Manual Python install

```bash
pip install -e ".[dev,test]"
cd backend
uvicorn homomics_lab.main:app --reload --port 8080
```

### CLI

After installation the `homomics` command is available:

```bash
homomics --help
homomics init metagenomics --phases "qc,denoising,taxonomy"
honomics validate domain.yaml
homomics install ./metagenomics --domains-dir ./backend/homomics_lab/domains
homomics list --domains-dir ./backend/homomics_lab/domains
homomics generate "16S amplicon analysis with DADA2 and QIIME2"
homomics seed [--force] [--data-dir PATH]   # broadcast cold-start CBKB/SkillDAG baseline seeds
```

## Testing instructions

### Backend

```bash
# From repo root
make test-backend
# Equivalent to: cd backend && pytest -v

# CI-style with coverage
cd backend
pytest -q --tb=short --cov=backend/homomics_lab --cov-report=term-missing --cov-fail-under=70
```

- Test root: `backend/tests/` (configured in `pyproject.toml`).
- `pytest-asyncio` and `fakeredis` are used for async/queue tests.
- The full backend suite is documented as passing ~901 tests.

### Frontend

```bash
cd frontend
npm test -- --run      # Vitest unit tests
npm run test:e2e       # Playwright end-to-end tests
npm run build          # Type-check + Vite production build
```

### CI

GitHub Actions (`.github/workflows/ci.yml`) runs:

- Backend tests with coverage on Python 3.12.
- Backend lint with `ruff` and `mypy`.
- Backend Docker build + `/health` smoke test.
- Frontend `npm ci`, `npm test -- --run`, and `npm run build` on Node 20.

## Code style guidelines

### Python

- Formatter: **Black**.
- Linter: **Ruff**.
- Type checker: **mypy** (`mypy backend/homomics_lab`).
- Run from repo root via `Makefile`:
  - `make lint-backend`
  - `make format`
  - `make clean`

### TypeScript / Frontend

- Type-check: `npx tsc --noEmit`.
- Formatter: **Prettier** for `src/**/*.{ts,tsx}`.
- Run from `Makefile`:
  - `make lint-frontend`
  - `make format-frontend`
- UI components: shadcn/ui (Tailwind v3 registry via `shadcn@2.1.8` CLI — the v4 CLI emits incompatible code) lives in `src/components/ui/shadcn/`; the legacy exports in `src/components/ui/` are adaptation wrappers keeping the old props API — import from the legacy paths, not from `shadcn/` directly. Design tokens (spacing/elevation/motion) are extended incrementally in `src/index.css`; never change existing `:root`/`.dark` semantic variable names or values.
- Navigation is hash-routed (`App.tsx` syncs `activeItem` with `window.location.hash`); no react-router. Sidebar shows only Chat / Files / Skills / Domains / MCP / Settings, plus a Project selector and session history (`components/layout/SidebarSessions.tsx`) below the main nav. The sidebar collapse toggle keeps icons centered and the Project selector remains accessible. Reports / Workflow / Figures are not top-level entries; they surface as inline cards in the message stream and open full-screen overlays via `src/components/overlay/OverlayManager.tsx`.
- Message types: `frontend/src/types/chat.ts` defines the chat message contract. The backend now emits `type: 'artifact'` messages after successful runs (`models/common.py` `MessageType.ARTIFACT`, `jobs/runner.py`), rendered inline by `components/chat/ArtifactMessage.tsx`; tables inside artifacts are collapsed by default and expandable per-table. The backend also recognizes `analysis_type: 'visualization_edit'` (`agent/intent/classifiers.py`) for natural-language figure edits; `turn_viz_handler.py` + `viz/edit_engine.py` apply rule-based Plotly transforms and return a new `PLOT_DATA` message.
- Execution progress is shown by `components/chat/TodoChecklist.tsx` as a compact checklist above the chat input, not as a top progress bar or large inline card. The send button in `components/chat/ChatInput.tsx` switches to an abort/stop state while a run is in progress. The top bar (`components/layout/TopBar.tsx`) is compact (`h-10`) and keeps the visual focus on the conversation.
- The MCP marketplace (`components/mcp/MCPMarketplace.tsx`) silently degrades when the registry is unreachable (no repeated "Not Found" toasts). New user-facing labels go through `src/i18n/index.ts` so both English and Chinese keys stay in sync.

### General

- Follow the existing module organization. New feature code should live in the appropriate layer (`agent/`, `skills/`, `execution/`, `api/`, etc.).
- Keep domain-specific configuration out of Python when possible — put it in `domain.yaml`.
- Use Pydantic models for API contracts and config; use SQLAlchemy for persistence.
- All environment-driven config belongs in `backend/homomics_lab/config.py`.
- Self-improvement data:
  - `agent/plan/mode_selection_lore.py` stores `(intent_features → execution_mode)` statistics learned from `evaluation/mode_benchmark.py`; `ModeSelector` uses them as a prior when confidence and sample thresholds are met.
  - `knowledge/seed.py` / `skills/skill_dag.py` distinguish `source="seed"` (hand-curated YAML) from `source="observed"` (auto-promoted from consecutive successful skill transitions via `_record_execution_feedback`). Observed edges are promoted to `CONFIRMED` only after `seed_observed_promotion_threshold` consecutive successes and zero failures.

## Project conventions

### Domain declarations

Domains are the primary extension mechanism. A domain is a directory containing a single `domain.yaml` plus an optional `skills/` subdirectory.

Example locations:

- `backend/homomics_lab/domains/single_cell/domain.yaml`
- `backend/homomics_lab/domains/spatial/domain.yaml`
- `backend/homomics_lab/domains/genomics/domain.yaml`
- `backend/homomics_lab/domains/mrnaseq/domain.yaml`
- `backend/homomics_lab/domains/metagenomics/` (generated/installed)

A `domain.yaml` defines:

- `phases` — analysis strategy skeleton used by `PlanEngine`.
- `state_checks` — data-state-driven plan adaptations.
- `intents` — keywords/patterns for `IntentAnalyzer`.
- `roles` — YAML-configurable agent roles.
- `dag_seeds` — initial SkillDAG edges.
- `sops` — standard operating procedures for CBKB.
- `data_state_schema` — domain-specific `DataState` fields.

Key invariant from the architecture docs: **SkillDAG is not the plan driver**. Plans come from domain strategy templates; SkillDAG assists with skill selection, conflict detection, and alternatives.

Plan-level execution mode: `PlanResult.execution_mode` (`auto` / `fixed_pipeline` / `codeact`) is filled by `agent/plan/mode_selector.py` from skill coverage, gaps, and risk signals. `auto` defers to the phase-level `agent/execution_router.py`. Quantitative comparison: `python -m homomics_lab.evaluation.mode_benchmark`.

### Skill format

Skills use the unified `SKILL.md + scripts/` layout:

```text
skills/{skill_id}/
├── SKILL.md              # YAML frontmatter + agent-facing documentation
├── scripts/              # Reference implementations the agent reads and adapts
│   ├── python/           # Named by purpose (core_analysis.py, utils.py, ...);
│   │                     # there is NO fixed run.py entrypoint contract
│   └── r/
├── assets/               # Optional reference data (model registries, marker lists, ...)
├── requirements.txt      # Optional Python dependencies
├── environment.yml       # Optional conda environment
└── tests/                # Optional skill-level tests
```

The agent treats `SKILL.md` and `scripts/` as **reference material**: it reads them and generates task-specific analysis code step by step, rather than invoking a pre-defined entrypoint.

`SKILL.md` frontmatter declares the skill type via `tool_type`:

- `tool_type: python` / `r` / `mixed` — reference-script skills (the common case in `skills/`).
- `tool_type: cli` — wraps an external command-line tool.
- `tool_type: agent` / `knowledge` — LLM-driven declarative skill / read-only reference (rare).

External/imported skills default to the `experimental` trust tier and will not execute in non-interactive mode until trusted (see the four-tier trust model under Security). High-risk tools (`shell_exec`, `file_write`, `file_edit`) carry `risk_level=high` and require approval in interactive mode.

### Skill retrieval

Skill candidates from hybrid retrieval are reranked by `agent/retrieval_rerank.py` (pure-Python BM25 over skill docs, blended 0.4 semantic / 0.5 BM25 / 0.1 graph boost) before reaching the planner. Generic phase-text queries (e.g. `"{phase_type} analysis step"`) score ~0.16-0.19 cosine against arbitrary skills, so both the retrieval path (`rerank_min_score=0.1`) and the PlanEngine fallback matcher (`fallback_min_similarity=0.15`) apply explicit thresholds — never lower them to force a match; an unmatched step should fall through to CodeAct instead of binding a wrong skill.

### Hot reload

`domain.yaml` files and external skill directories can be watched at runtime. This is enabled by `HOMOMICS_SKILL_HOT_RELOAD_ENABLED` (default `true`) and started in `main.py` lifespan.

### API structure

Routers live in `backend/homomics_lab/api/` and are mounted under `/api` in `api/router.py`.

Major route prefixes:

- `/api/chat` — chat, WebSocket, HITL responses, SLA.
- `/api/skills` — skill CRUD, import/export, trust, validation, testing.
- `/api/plan` — plan approval/modification.
- `/api/execution` — job status and execution endpoints.
- `/api/projects` — project management, version locking, RO-Crate export, audit log.
- `/api/domains` — domain marketplace (list, import, import-zip, export).
- `/api/nfcore` — nf-core pipeline discovery and execution.
- `/api/reports`, `/api/viz`, `/api/knowledge`, `/api/scheduler`, `/api/settings`, `/api/secrets`, `/api/costs`, `/api/collab`.
- `/api/waiting` — Waiting Orchestrator: list/get wait conditions, resume (webhook token validated), cancel. Backed by `jobs/waiting.py` (`WaitingService`, SQLite at `data/waiting.db`); jobs suspend via `JobService.suspend_for_event` (`JobStatus.AWAITING_EVENT`) and re-queue on event via the `RESUME_HITL` resume path. Timer conditions use the APScheduler instance from `scheduler.py` with a periodic `tick()` fallback.

Health/metrics endpoints are public:

- `GET /health`
- `GET /health/memory`
- `GET /health/usage`
- `GET /metrics`

### Workspace and provenance

Each project gets a workspace:

```text
workspaces/{project_id}/
├── data/               # Read-only input data
├── intermediate/       # Step artifacts with SHA-256 checksums
├── outputs/            # Final deliverables
├── logs/               # Execution logs
└── .metadata/          # Artifact registry, lineage graph, snapshots, version.lock
```

Large objects are offloaded via `DataStore` (`DataFrame` → Parquet, `AnnData` → H5AD, pickle for non-JSON objects) and returned as `ResultReference`. Every background job produces a `ReproducibilityBundle`.

## Deployment

### Docker Compose development

`docker-compose.yml` brings up:

- `postgres:16-alpine`
- `redis:7-alpine`
- `minio/minio`
- `backend` (Gunicorn + Uvicorn workers)
- `worker` (`homomics-worker` standalone)
- `frontend` (nginx)

The backend container mounts the host Docker socket so it can launch sibling sandbox containers. This uses `user: "0:0"` for local convenience; production should use tighter permissions.

### Docker Compose production

`docker-compose.prod.yml` uses:

- PostgreSQL + Redis (Redis not exposed to host).
- Backend and worker services with `.env` secrets.
- `HOMOMICS_AUTH_ENABLED=true`, `HOMOMICS_FORCE_SANDBOX=true`, `HOMOMICS_RATE_LIMIT_ENABLED=true`.
- Capabilities `SETUID`, `SETGID`, `SYS_ADMIN` for bubblewrap/container sandboxing.
- Frontend nginx with `NGINX_BACKEND_HOST` / `NGINX_BACKEND_PORT`.

### Helm

A Helm chart is available at `deploy/helm/homomicslab/` with:

- `Chart.yaml`, `values.yaml`
- Deployment, Service, HPA, Ingress, and PVC templates.

See `deploy/helm/homomicslab/README.md` for chart-specific instructions.

### Gunicorn

Production Gunicorn config is in `gunicorn.conf.py`:

- Uvicorn worker class.
- `workers = max(2, min(cpu_count(), 4))`.
- `timeout = 120`, `preload_app = True`.

## Security considerations

- **Authentication is opt-in locally**. Set `HOMOMICS_AUTH_ENABLED=true` in production and provide `HOMOMICS_API_KEY` / JWT secret / OIDC config.
- **Sandbox all code execution**. `HOMOMICS_FORCE_SANDBOX=true` routes `shell_exec` and CodeAct through `local`, `bubblewrap`, or `container` sandboxes. The production compose file enables this and requires a capable container runtime.
- **Skill trust model**. Four tiers (`skills/trust.py`): `official` (builtin) / `verified` (trusted) / `community` / `experimental` (untrusted). They differentiate sandbox backend (community/experimental never use the local sandbox), CodeAct cache (excluded for experimental), and HITL. Experimental skills do not execute in non-interactive mode; in interactive mode they now raise a real skill-level HITL checkpoint via `PersistentApprovalStore` (`skills/runtime.py`) instead of only logging a warning. Trust toggles via `POST /api/skills/{id}/trust`.
- **High-risk tool approval**. When `HOMOMICS_INTERACTIVE_MODE=true`, `shell_exec`, `file_write`, and `file_edit` calls pause for explicit approval.
- **Secrets**. API keys, DB passwords, S3 credentials, and JWT secrets live in `.env` only. `config.py` provides `masked_dump()` for logs/health output. Never commit `.env`.
- **CORS / trusted hosts**. Production should set `HOMOMICS_CORS_ORIGINS` and `HOMOMICS_TRUSTED_HOSTS` explicitly. Debug mode allows `localhost:5173` and `localhost:3000`.
- **Rate limiting**. Enable with `HOMOMICS_RATE_LIMIT_ENABLED=true` (memory or Redis backend).
- **Pickle serialization** is disabled by default (`HOMOMICS_ALLOW_PICKLE_SERIALIZATION=false`). Only enable in fully trusted single-user environments.
- **Audit logging**. Optional rotating audit log for project-scoped requests via `HOMOMICS_AUDIT_LOG_ENABLED`.
- **Scheduled background jobs** (`curation`, `evolution`, `narrative reports`, `SOP proposals`) are disabled by default for individual users because they can consume tokens/CPU/GPU.

## Useful references

- `README.md` — high-level introduction, quick start, feature status.
- `README.zh.md` — Chinese version of the README.
- `docs/architecture.md` — component-level architecture and data flow.
- `docs/design.md` — design principles, module contracts, state machines.
- `docs/operations.md` — operations guide: installation, config, HPC, nf-core, troubleshooting.
- `docs/setup.md` — local development setup.
- `docs/skill-authoring-guide.md` — Chinese guide for writing skills.
- `docs/domain-extension-guide.md` — Chinese guide for extending domains.
- `docs/roadmap-v0.5.md` and `docs/homomics-lab-improvement-plan-v1.0.md` — roadmaps.
- `CHANGELOG.md` — release notes.
- `.env.example` — annotated configuration template.

## Notes for agents

- Prefer editing `domain.yaml` over Python code when adding or modifying analysis strategies, intents, roles, or SOPs.
- When adding a new skill, follow the `SKILL.md + scripts/` convention and place it in the correct domain `skills/` directory or use the skill import API.
- Subagent progress events follow the contract in `agent/progress_events.py`: sub-execution states carry top-level `actor: "subagent:<skill_id>"` and `parent_id`; top-level executions omit both keys. The frontend (`utils/subagentLogs.ts`, `ExecutionLogPanel`) relies on this to group nested logs — keep both ends in sync when changing the event shape.
- `agent/turn_runner.py` is no longer a god class; it delegates to `turn_result_assembler`, `turn_context_formatter`, `turn_file_resolver`, `turn_risk_assessor`, `turn_clarification`, `turn_intent_router`, `turn_response_generator`, `turn_self_correction`, and `turn_workflow_handler`. Do not add new large methods directly to `turn_runner.py` — place them in the appropriate collaborator module and add a thin delegating method only when necessary.
- Run `make lint-backend` / `make test-backend` after backend changes and `npm test -- --run` / `npm run build` after frontend changes.
- Do not run `git commit`, `git push`, or destructive production actions unless explicitly asked.
