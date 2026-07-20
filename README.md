# HomomicsLab

A **domain-native agent platform for computational biology** that bridges rigid bioinformatics pipelines and unstructured notebook collections. HomomicsLab turns natural-language research questions into reproducible, auditable, and extensible analysis workflows—combining the adaptability of AI agents with the rigor of production-grade data engineering.

> **v0.5.0** — Intent-driven analysis automation with single-file domain declarations, CLI scaffolding, LLM-assisted domain generation, runtime hot-reloading, dynamic agent roles, hypothesis-driven exploration, self-evolving SkillDAG, dynamic replanning, CBKB curation, reproducibility bundles, DataStore offloading, skill memoization, CodeAct caching, cross-process sandboxed tool invocation, and a domain template marketplace.

---

## The Problem

Computational biology sits at a painful intersection:

| Approach | Strength | Fatal Weakness |
|---|---|---|
| **Turnkey Pipelines** (Galaxy, nf-core) | Reproducible, validated | Rigid—one parameter mismatch and the pipeline breaks |
| **Notebook Collections** (Scanpy, Seurat) | Flexible, educational | Fragmented, manual, impossible to reproduce at scale |
| **General LLM Agents** (ChatGPT, Claude Code) | Conversational, generalist | No bioinformatics domain knowledge; hallucinates packages, misses batch effects |
| **Workflow Engines** (Snakemake, Nextflow) | Scalable, declarative | Require expert orchestration; no semantic understanding of data state |

**HomomicsLab is the fourth option**: a domain-native agent platform that understands both the biology and the engineering—planning from natural language, executing with sandboxed precision, interpreting with domain-aware checks, and capturing every decision for reproducibility.

---

## Current Status

HomomicsLab is a **production-ready agent framework** with a growing library of built-in capabilities. The core architecture, execution engine, stability guards, and extensibility mechanisms are implemented and tested. Practical power grows with the number and quality of installed skills and domains.

| Capability | Status | Notes |
|---|---|---|
| Agent orchestration (intent → plan → execute) | ✅ Implemented | `Orchestrator`, `PlanEngine`, `TaskDecomposer`, `TurnRunner` |
| Dynamic agent roles | ✅ Implemented | YAML-configurable `RoleDefinition` + `DynamicAgent` |
| Hypothesis-driven exploration | ✅ Implemented | `ExplorationEngine` blueprint → critique → evidence report |
| Skill runtime & sandboxing | ✅ Implemented | Local / bubblewrap / container backends |
| Schema validation (L1) | ✅ Implemented | JSON Schema input/output validation per skill |
| Version locking (L2) | ✅ Implemented | Project-level skill/env/version locks |
| Regression baselines (L2) | ✅ Implemented | Auto-recorded after successful CodeAct runs |
| Reproducibility bundles | ✅ Implemented | Code, plan, HITL, env lock captured per job |
| DataStore offloading | ✅ Implemented | Parquet/H5AD/pickle offload for large results |
| Skill result cache | ✅ Implemented | SHA-256 keyed memoization |
| CodeAct code cache | ✅ Implemented | Embedding-based similarity cache for generated code |
| Cross-process tool invocation | ✅ Implemented | Sandbox-isolated `shell_exec`/`file_*` tools |
| Domain marketplace | ✅ Implemented | Import/export domain templates via UI/API |
| CBKB & auto-curation | 🟡 Framework ready | Interfaces implemented; loop requires execution history |
| SkillDAG self-evolution | 🟡 Framework ready | Graph records executions; edge promotion requires repeated success |
| Dense semantic search | 🟡 Optional | Requires `HOMOMICS_SEMANTIC_SEARCH_MODEL` |
| Agent self-evolution | 🟡 Framework ready | Scheduled jobs disabled by default for individual users |

> **Privacy-first**: HomomicsLab is designed to be self-hosted and locally runnable. No data leaves your machine unless you explicitly configure external LLM APIs or cloud storage.

---

## What's New in v0.5.0

### Intent-Centric Execution
- The default path now centers on **user intent + data state** rather than forcing every request through a fixed domain/phase pipeline.
- `use_skill_reference` lets CodeAct generate compact scripts using curated skills as reference material, instead of running a rigid skill entrypoint.
- Data preflight inspects uploaded files before routing, so simple requests (e.g., descriptive statistics) do not inherit an 8-step pipeline.

### Cross-Process Tool Invocation Sandbox
- `backend/homomics_lab/tools/invoke_tool.py` provides a uniform protocol for invoking atomic tools across process boundaries.
- Supports `local`, `bubblewrap`, and `container` backends so high-risk tool calls run in isolated sandboxes.

### CodeAct Code Cache
- `backend/homomics_lab/execution/code_cache.py` caches CodeAct-generated code keyed by task-description embeddings.
- Similar tasks hit the cache instead of calling the LLM again, reducing cost and latency.

### "Save as Skill" in the Frontend
- The Skill Manager UI includes a **Save as Skill** button that promotes a successful CodeAct run into a curated `SKILL.md + scripts/` package.

### Modern Frontend UI/UX
- Component library with light/dark theme, command palette, settings panel, chat with Markdown/LaTeX/code rendering, drag-and-drop uploads, session switching, and workflow canvas.

### Task Orchestration & Resource Scheduling
- Pluggable execution backends: `LocalScheduler`, `SlurmScheduler`, and `NextflowRunner`.
- Nextflow DSL2 template registry maps analysis intents to curated workflow templates.
- nf-core integration supports pipeline discovery, download, schema-driven parameters, profile selection, and execution.

---

## What Makes HomomicsLab Different

### 1. End-to-End Analysis Closure

From *"Analyze my PBMC dataset and find marker genes for each cluster"* to a **self-contained HTML report with UMAPs, DE tables, and method sections**—in one conversation.

Lifecycle: **Intent Analysis → Adaptive Planning → Execution → Interpretation → Reporting → Reproducibility Bundle**.

### 2. Domain-Native Intelligence

- **Strategy Templates**: `PlanEngine` uses extensible domain strategies that encode the correct order of operations as adaptable templates.
- **Data-State Adaptation**: The plan changes based on data characteristics—batch effect detected → inject integration; low quality → tighten QC.
- **SkillDAG**: A self-evolving knowledge graph that tracks how skills relate in practice, learned from execution history and `domain.yaml` seeds.

### 3. Self-Evolving Skill Ecosystem

- **SkillDAG** discovers `followed_by`, `conflicts_with`, and `alternative_to` relationships.
- **Semantic Discovery**: TF-IDF + optional dense embeddings.
- **Auto-Generation**: Generate new skills from natural language requirements.
- **Unified Format**: Built-in and external skills use the identical `SKILL.md + scripts/` format.
- **Promotion from CodeAct**: Successful CodeAct runs can be promoted to reusable skills.

### 4. Multi-Layer Stability Guard

| Layer | Defense | Prevents |
|---|---|---|
| **L1 — Schema Validation** | Every skill input/output validated against declared JSON Schema | Type mismatches, missing fields, silent corruption |
| **L2 — Version Locking** | Project-level lock: skill versions, script SHA-256, pip freeze, Python version | "It worked yesterday" drift |
| **L2 — Regression Testing** | Record baselines from known-good executions; detect output drift | Skill updates that silently change results |
| **L2 — Code Safety** | Static audit of LLM-generated CodeAct code before execution | Dangerous imports, path traversal, shell injection |

### 5. Complete Reproducibility

The `ReproducibilityEngine` captures exact code, plan, HITL decisions, environment lock, and skill version lock.

### 6. Data Provenance as a First-Class Feature

```
workspaces/{project_id}/
├── data/               # Original data — read-only protected
├── intermediate/       # Step artifacts with SHA-256 checksums
├── outputs/            # Final deliverables
├── logs/               # Execution logs
└── .metadata/          # Artifact registry, lineage graph, snapshots, version.lock
```

### 7. Dynamic Agent Roles

YAML-configurable roles instead of hardcoded agent classes:

```yaml
role_id: visualization
name: Visualization Specialist
allowed_skills: [plot_umap, plot_heatmap, plot_violin]
allowed_tools: [file_read, file_write]
permissions:
  can_execute: true
  can_spawn_specialist: false
  max_concurrent_tasks: 2
```

### 8. Big Results & Skill Memoization

- **DataStore** offloads pandas `DataFrame` → Parquet, `AnnData` → H5AD, and large objects to files.
- **SkillCache** memoizes deterministic skill executions keyed by stable SHA-256.
- **CodeActCache** caches generated code by task-description embedding similarity.

### 9. Security & Trust Model

- Imported skills are marked `trusted=false` by default.
- `POST /api/skills/{id}/trust` toggles trust.
- High-risk tools carry `risk_level=high`.
- `HOMOMICS_INTERACTIVE_MODE=true` requires explicit approval before high-risk tool invocation.
- `HOMOMICS_FORCE_SANDBOX=true` routes shell/code execution through bubblewrap/container sandboxes.

---

## Quick Start

### Docker (Recommended)

```bash
docker compose up --build
# Backend: http://localhost:8080
# Frontend: http://localhost:3000
```

### Local Development

```bash
# Backend (run from repo root so uv.lock / pyproject.toml are found)
pip install -e ".[dev,test]"
cd backend
uvicorn homomics_lab.main:app --reload --port 8080

# Frontend (new terminal)
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

### Running Without an External LLM Key

For local/embedded model use, configure a compatible local inference endpoint:

```env
HOMOMICS_LLM_PROVIDER=openai-compatible
HOMOMICS_LLM_BASE_URL=http://localhost:11434/v1
HOMOMICS_LLM_MODEL=qwen2.5:14b
```

> Local models work well for intent analysis and simple skill selection. Complex CodeAct generation still benefits from frontier models.

---

## Task Orchestration & Resource Scheduling

| Backend | Use Case | How It Works |
|---|---|---|
| **Local** | Fast iteration, small data, laptop/WSL | Python/R/Bash skills run in the API process or a local subprocess sandbox |
| **SLURM** | HPC clusters, long-running jobs | `SlurmScheduler` translates skill code into `sbatch` scripts and monitors via `squeue`/`sacct` |
| **Nextflow** | Reproducible pipelines, nf-core | `NextflowRunner` renders DSL2 templates or invokes nf-core pipelines with schema-driven parameters |

### Nextflow & nf-core Integration

- **Template Registry** maps intents like `rnaseq_analysis` or `single_cell_analysis` to curated Nextflow DSL2 templates.
- **NFCoreManager** discovers nf-core pipelines, caches them locally, loads JSON parameter schemas, detects profiles, and runs them.
- **Parameter Safety**: nf-core parameters are validated against their published schemas before submission.

---

## Project Structure

```
HomomicsLab/
├── backend/
│   ├── homomics_lab/            # Main Python package
│   │   ├── agent/               # Orchestration, planning, intent, exploration
│   │   ├── api/                 # FastAPI routers
│   │   ├── cli/                 # `homomics` command-line tool
│   │   ├── domain/              # Domain loader, registry, marketplace, domains/
│   │   ├── execution/           # CodeAct engine, cache, safety audit
│   │   ├── hpc/                 # Local / SLURM / Nextflow schedulers
│   │   ├── jobs/                # Background job queue and runner
│   │   ├── knowledge/           # CBKB knowledge base
│   │   ├── skills/              # Skill loader, runtime, registry, DAG, store
│   │   ├── stability/           # Schema validation, version locking, regression
│   │   ├── tools/               # Tool registry, approval, cross-process invocation
│   │   ├── workspace/           # Workspace, artifact, lineage management
│   │   └── main.py              # FastAPI application factory
│   └── tests/                   # pytest suite
├── frontend/                    # React 18 + TypeScript + Vite
├── deploy/helm/homomicslab/     # Helm chart
├── skills/                      # Canonical skill store (runtime)
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

Built-in domains live in `backend/homomics_lab/domains/`:
- `single-cell-transcriptomics/`
- `spatial-transcriptomics/`

---

## API Endpoints

### Chat & Execution
| Endpoint | Description |
|---|---|
| `POST /api/chat/send` | Send message to agent |
| `POST /api/chat/hitl/respond` | Respond to HITL checkpoint |
| `WS /api/chat/ws/{session_id}` | Real-time chat WebSocket |
| `POST /api/chat/sla` | Assess confidence/execution mode before running |

### Skills
| Endpoint | Description |
|---|---|
| `GET /api/skills/` | List all skills |
| `GET /api/skills/search?q=` | Keyword search skills |
| `POST /api/skills/import` | Import skill from path/git/zip |
| `POST /api/skills/{id}/trust` | Mark skill trusted/untrusted |
| `POST /api/skills/promote` | Promote CodeAct run to curated skill |

### Plans & Jobs
| Endpoint | Description |
|---|---|
| `GET /api/plan/{plan_id}` | Get plan details |
| `POST /api/plan/{plan_id}/approve` | Approve a plan |
| `GET /api/execution/{job_id}/status` | Get job execution status |

### Domains
| Endpoint | Description |
|---|---|
| `GET /api/domains/` | List available domain templates |
| `POST /api/domains/import` | Import domain from path/git/zip |
| `POST /api/domains/{id}/export` | Export domain template as zip |

---

## CLI

```bash
# Initialize a new domain
homomics init metagenomics --phases "qc,denoising,taxonomy,diversity"

# Validate a domain.yaml
homomics validate domain.yaml

# Install a domain
homomics install ./metagenomics --domains-dir ./backend/homomics_lab/domains

# Generate a domain from a description
homomics generate "16S amplicon analysis with DADA2 and QIIME2"

# List installed domains
homomics list --domains-dir ./backend/homomics_lab/domains
```

---

## Testing

```bash
cd backend
pytest tests/ -q
```

Coverage spans the agent layer, skill layer, stability layer, workspace layer, reproducibility layer, domain layer, and tool layer.

---

## Configuration

Environment variables (prefix `HOMOMICS_`):

| Variable | Default | Description |
|---|---|---|
| `HOMOMICS_PORT` | `8080` | API server port |
| `HOMOMICS_DATABASE_URL` | `sqlite+aiosqlite:///./homomics_lab.db` | Database URL |
| `HOMOMICS_EXTERNAL_SKILLS_DIR` | — | Path to external skill collection |
| `HOMOMICS_SEMANTIC_SEARCH_MODEL` | — | Set to `all-MiniLM-L6-v2` for dense embeddings |
| `HOMOMICS_SKILL_SANDBOX_BACKEND` | `auto` | `local`, `bubblewrap`, `container`, or `auto` |
| `HOMOMICS_FORCE_SANDBOX` | `true` | Route shell/code execution through sandbox |
| `HOMOMICS_INTERACTIVE_MODE` | `false` | Require approval for high-risk tool calls |
| `HOMOMICS_CODEACT_CACHE_ENABLED` | `true` | Enable CodeAct code cache |
| `HOMOMICS_SKILL_CACHE_ENABLED` | `true` | Enable skill result memoization |
| `HOMOMICS_WORKER_MODE` | `true` | Start a local worker inside the API process |
| `HOMOMICS_CURATION_ENABLED` | `false` | Enable nightly CBKB curation |
| `HOMOMICS_EVOLUTION_ENABLED` | `false` | Enable nightly agent evolution |

---

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy, sentence-transformers, sqlite-vec
- **Frontend**: React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Plotly.js
- **Workflows**: Nextflow (DSL2), SLURM (sbatch/sacct)
- **Deployment**: Docker, Docker Compose, Helm, nginx

---

## Roadmap

High-level next steps:
- Expand built-in and community skill coverage across single-cell, spatial, genomics, and metagenomics.
- Strengthen the self-evolution loop as execution history accumulates.
- Improve out-of-the-box experience for individual users (local model defaults, example datasets, guided onboarding).
- Harden long-running job reliability and resource monitoring for personal devices.

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.
See [LICENSE](./LICENSE) for the full license text.
