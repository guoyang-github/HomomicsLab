# HomomicsLab

A general-purpose agent platform for computational biology that bridges the gap between **rigid bioinformatics pipelines** and **unstructured notebook collections**. HomomicsLab turns natural language research questions into reproducible, auditable, and extensible analysis workflows—combining the adaptability of AI agents with the rigor of production-grade data engineering.

> **v0.5.0** — End-to-end analysis automation with single-file domain declarations, CLI scaffolding, LLM-assisted domain generation, runtime hot-reloading, dynamic agent roles, multi-agent swarm, self-evolving skill knowledge graphs, dynamic replanning, CBKB auto-curation, multi-layer stability guards, complete reproducibility capture, DataStore offloading for large results, skill result memoization, **CodeAct code caching**, **cross-process tool invocation sandbox**, and a **domain template marketplace**.

---

## The Problem

Computational biology sits at a painful intersection:

| Approach | Strength | Fatal Weakness |
|---|---|---|
| **Turnkey Pipelines** (Galaxy, nf-core) | Reproducible, validated | Rigid—one parameter mismatch and the pipeline breaks; users must speak "workflow-ese" |
| **Notebook Collections** (Scanpy tutorials, Seurat vignettes) | Flexible, educational | Fragmented, manual, impossible to reproduce at scale |
| **General LLM Agents** (ChatGPT, Claude Code) | Conversational, generalist | No domain knowledge of bioinformatics; hallucinates packages, misses batch effects, produces irreproducible one-offs |
| **Workflow Engines** (Snakemake, Nextflow DSL) | Scalable, declarative | Require expert orchestration; no semantic understanding of data state |

**HomomicsLab is the fourth option**: a **domain-native agent platform** that understands both the biology *and* the engineering—planning analysis strategies from natural language, executing them with sandboxed precision, interpreting results with domain-aware anomaly detection, and capturing every decision for reproducibility.

---

## Current Status & Maturity

HomomicsLab is best understood as a **production-ready agent framework** with a growing library of built-in capabilities. The core architecture, execution engine, stability guards, and extensibility mechanisms are implemented and tested. However, like any general-purpose agent platform, its practical power grows with the number and quality of skills/domains installed.

| Capability | Status | Notes |
|---|---|---|
| Agent orchestration (intent → plan → execute) | ✅ Implemented | `TurnRunner`, `PlanEngine`, `Orchestrator`, `AgentCore` |
| Dynamic agent roles | ✅ Implemented | YAML-configurable `RoleDefinition` + `DynamicAgent` |
| Multi-agent swarm & consensus | ✅ Implemented | `AgentSwarm` with semaphore-controlled parallelism |
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
| CBKB & auto-curation | 🟡 Framework ready | Interfaces implemented; self-evolution loop requires sufficient execution history |
| SkillDAG self-evolution | 🟡 Framework ready | Graph exists and records executions; edge promotion requires repeated successful runs |
| Dense semantic search | 🟡 Optional | Requires `HOMOMICS_SEMANTIC_SEARCH_MODEL` |
| Agent self-evolution | 🟡 Framework ready | Scheduled jobs disabled by default for individual users |

> **For individual users**: HomomicsLab is designed to be self-hosted, privacy-first, and locally runnable. No data leaves your machine unless you explicitly configure external LLM APIs or cloud storage.

---

## What's New in v0.5.0

### Cross-Process Tool Invocation Sandbox
- `backend/homomics_lab/tools/invoke_tool.py` provides a uniform protocol for invoking atomic tools across process boundaries.
- Supports `local`, `bubblewrap`, and `container` backends so high-risk tool calls run in isolated sandboxes.

### CodeAct Code Cache
- `backend/homomics_lab/execution/code_cache.py` caches CodeAct-generated code keyed by task-description embeddings.
- Similar tasks hit the cache instead of calling the LLM again, reducing cost and latency.

### Auto-Recorded Regression Baselines
- After a successful CodeAct execution, the system automatically records a regression baseline.
- Future runs of the same skill/code can be compared against the baseline to detect silent drift.

### "Save as Skill" in the Frontend
- The Skill Manager UI now includes a **Save as Skill** button that promotes a successful CodeAct run into a curated `SKILL.md + scripts/` package.

### Domain Template Marketplace
- New `frontend/src/components/domains/DomainMarketplace.tsx` UI tab for browsing, importing, and exporting domain templates.
- Backend endpoints: `GET /api/domains/`, `POST /api/domains/import`, `POST /api/domains/{id}/export`, `POST /api/domains/import-zip`.

### Modern Frontend UI/UX Overhaul
- New component library in `frontend/src/components/ui/` (Button, Input, Card, Modal, Tabs, Toast, CommandPalette, etc.).
- Light/dark theme system with system-aware auto-switching and persistent user preference.
- Sidebar + top-bar navigation layout with keyboard shortcuts and command palette (`Ctrl+K` / `Cmd+K`).
- Settings panel for LLM provider/model, execution backend, search, budget, and general preferences.
- Chat: Markdown + LaTeX + syntax-highlighted code rendering, drag-and-drop file uploads, session switching, and HITL inline forms.
- Workflow canvas with real-time execution log panel, node status badges, zoom-to-fit, and detail sidebars.
- Consistent empty states, skeleton loaders, and toast notifications across all views.

### Task Orchestration & Resource Scheduling
- New `backend/homomics_lab/hpc/` module with pluggable execution backends: `LocalScheduler`, `SlurmScheduler`, and `NextflowRunner`.
- Nextflow DSL2 template registry maps analysis intents (`rnaseq_analysis`, `single_cell_analysis`, etc.) to curated workflow templates.
- nf-core integration (`backend/homomics_lab/nfcore_integration.py`) supports pipeline discovery, download, schema-driven parameter loading, profile selection, and execution.
- SLURM support via `sbatch`/`squeue`/`sacct` integration for submitting long-running analyses to HPC clusters.
- Execution backend is selectable per request so the same agent plan can run locally, on a cluster, or as a Nextflow workflow.

---

## What Makes HomomicsLab Different

### 1. End-to-End Analysis Closure

From a sentence like *"Analyze my PBMC dataset and find marker genes for each cluster"* to a **self-contained HTML report with UMAPs, DE tables, and method sections**—in one conversation.

HomomicsLab handles the entire lifecycle:
- **Intent Analysis** — Parses natural language research goals into structured `UserIntent` objects loaded from `domain.yaml`.
- **Adaptive Planning** — Selects from extensible domain strategy templates and generates plans that adapt to real-time data state.
- **Execution** — Sandboxed skill runtime with schema validation and resource monitoring. Skills are source-agnostic.
- **Interpretation** — Phase-level result analysis and anomaly detection.
- **Reporting** — Auto-generated HTML/Markdown reports with figures and provenance.
- **Reproducibility** — Every analysis exports a `ReproducibilityBundle`: exact code, plan, HITL decisions, environment lock.

### 2. Domain-Native Intelligence

- **Strategy Templates**: The PlanEngine carries built-in domain strategies (`single_cell_standard`, `spatial_transcriptomics`, `qc_only`) that encode the *correct order of operations* as adaptable templates.
- **Data-State Adaptation**: The plan changes based on data characteristics—batch effect detected → inject integration; low quality → tighten QC.
- **SkillDAG**: A self-evolving knowledge graph that tracks how skills relate in practice, learned from execution history and `domain.yaml` seeds.

### 3. Self-Evolving Skill Ecosystem

- **Self-Evolving Relationships**: SkillDAG discovers `followed_by`, `conflicts_with`, and `alternative_to` relationships. Edges graduate from `CANDIDATE` → `CONFIRMED` after repeated success.
- **Semantic Discovery**: Dual-engine skill search—TF-IDF fallback + optional sentence-transformers dense embeddings.
- **Auto-Generation**: Generate new skills from natural language requirements.
- **Unified Format**: Built-in and external skills use the identical `SKILL.md + scripts/` format.
- **Promotion from CodeAct**: Successful CodeAct runs can be promoted to reusable skills via UI or API.

### 4. Multi-Layer Stability Guard

| Layer | Defense | Prevents |
|---|---|---|
| **L1 — Schema Validation** | Every skill input/output validated against declared JSON Schema | Type mismatches, missing required fields, silent data corruption |
| **L2 — Version Locking** | Project-level lock: skill versions, script SHA-256, pip freeze, Python version | "It worked yesterday" drift, dependency hell |
| **L2 — Regression Testing** | Record baselines from known-good executions; detect output signature drift | Skill updates that silently change results |
| **L2 — Code Safety** | Static audit of LLM-generated CodeAct code before execution | Dangerous imports, path traversal, shell injection |

### 5. Complete Reproducibility

The `ReproducibilityEngine` captures:
- Exact agent-generated code
- The full execution plan with data-state adaptations
- Every HITL decision
- Environment lock (`pip freeze`, Python version)
- Skill version lock (exact versions and script checksums)

### 6. Interpretable, Not a Black Box

After every major phase, the **InterpretationEngine** produces:
- A human-readable summary
- Anomaly flags when thresholds are exceeded
- Actionable recommendations ranked by confidence

### 7. Data Provenance as a First-Class Feature

```
workspaces/{project_id}/
├── data/               # Original data — read-only protected
├── intermediate/       # Step artifacts with SHA-256 checksums
├── outputs/            # Final deliverables
├── logs/               # Execution logs
└── .metadata/          # Artifact registry, lineage graph, snapshots, version.lock
```

### 8. Dynamic Agent Roles

Instead of hardcoded agent classes, HomomicsLab uses YAML-configurable roles:

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

### 9. Big Results & Skill Memoization

- **DataStore** automatically offloads pandas `DataFrame` → Parquet, `AnnData` → H5AD, and large objects to files, returning a small `ResultReference`.
- **SkillCache** memoizes deterministic skill executions keyed by stable SHA-256 of `skill_id + inputs + fingerprint`.
- **CodeActCache** caches generated code by task-description embedding similarity.

### 10. Security & Trust Model

- Imported skills are marked `trusted=false` by default.
- `POST /api/skills/{id}/trust` toggles trust.
- High-risk tools (`shell_exec`, `file_write`, `file_edit`) carry `risk_level=high`.
- `HOMOMICS_INTERACTIVE_MODE=true` requires explicit approval before high-risk tool invocation.
- `HOMOMICS_FORCE_SANDBOX=true` routes shell/code execution through bubblewrap/container sandboxes.

---

## Quick Start

### Docker (Recommended)

```bash
docker-compose up --build
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

For local/embedded model use, configure a compatible local inference endpoint and set:

```env
HOMOMICS_LLM_PROVIDER=openai-compatible
HOMOMICS_LLM_BASE_URL=http://localhost:11434/v1
HOMOMICS_LLM_MODEL=qwen2.5:14b
```

> Note: Local models work best for intent analysis and simple skill selection. Complex CodeAct generation still benefits from frontier models.

---

## Task Orchestration & Resource Scheduling

HomomicsLab is not limited to single-process skill execution. The same agent plan can be dispatched to multiple execution backends depending on scale, environment, and reproducibility requirements.

| Backend | Use Case | How It Works |
|---|---|---|
| **Local** | Fast iteration, small data, laptop/WSL | Python/R/Bash skills run in the API process or a local subprocess sandbox |
| **SLURM** | HPC clusters, long-running jobs, many cores | `SlurmScheduler` translates skill code into `sbatch` scripts, monitors via `squeue`/`sacct`, and streams results back |
| **Nextflow** | Reproducible pipelines, nf-core workflows, cloud/HPC | `NextflowRunner` renders DSL2 templates or invokes nf-core pipelines with schema-driven parameters and profiles |

### Nextflow & nf-core Integration

- **Template Registry** (`hpc/template_registry.py`): maps high-level intents like `rnaseq_analysis` or `single_cell_analysis` to curated Nextflow DSL2 templates.
- **NFCoreManager** (`nfcore_integration.py`): discovers available nf-core pipelines, caches them locally, loads their JSON parameter schemas, detects executor profiles (`docker`, `singularity`, `conda`, `slurm`), and runs them.
- **API Endpoints** (`api/nfcore.py`): `GET /api/nfcore/pipelines`, `POST /api/nfcore/run`, and execution-status endpoints expose nf-core directly to the frontend.
- **Parameter Safety**: nf-core pipeline parameters are validated against their published schemas before submission, reducing the "rigid pipeline breaks on one parameter" problem.

### Why This Matters

- **One agent, many executors**: A natural-language request can become a local sandbox test, a SLURM batch job, or a containerized Nextflow pipeline without rewriting the plan.
- **Production scale**: Long-running bioinformatics workloads (alignment, quantification, variant calling) can be offloaded to cluster or cloud executors while the agent continues to monitor, interpret, and report.
- **Reproducibility by default**: Nextflow and nf-core bring containerized, version-locked execution; HomomicsLab layers its own reproducibility bundle on top.

---

## Project Structure

```
HomomicsLab/
├── backend/
│   ├── homomics_lab/
│   │   ├── agent/              # Agent orchestration layer
│   │   │   ├── core/           # AgentCore, DynamicAgent, RoleRegistry, roles/*.yaml
│   │   │   ├── plan/           # PlanEngine — adaptive strategy generation
│   │   │   ├── replanning.py   # DynamicReplanningEngine
│   │   │   ├── interpretation.py
│   │   │   ├── swarm.py        # AgentSwarm — parallel multi-agent execution + consensus
│   │   │   ├── orchestrator.py # Task scheduler with retry & HITL
│   │   │   ├── evolution.py    # AgentEvolutionEngine
│   │   │   └── turn_runner.py  # Unified conversational turn loop
│   │   ├── domain/             # Domain declaration system (v0.5.0)
│   │   │   ├── models.py
│   │   │   ├── loader.py       # DomainLoader — reads domain.yaml
│   │   │   ├── registry.py     # DomainRegistry
│   │   │   ├── hot_reload.py   # Runtime hot-reload
│   │   │   ├── marketplace.py  # Domain template marketplace
│   │   │   └── domains/        # Built-in domain declarations
│   │   │       ├── single_cell/domain.yaml
│   │   │       ├── spatial/domain.yaml
│   │   │       └── metagenomics/domain.yaml
│   │   ├── cli/                # Command-line tools
│   │   │   └── commands/       # init, validate, install, generate, list, trace
│   │   ├── execution/          # CodeAct execution base layer
│   │   │   ├── code_act.py     # CodeAct execution engine
│   │   │   ├── code_cache.py   # CodeAct similarity cache
│   │   │   └── code_safety.py  # Static safety audit for generated code
│   │   ├── hpc/                # Task orchestration & resource scheduling
│   │   │   ├── scheduler.py    # Local / SLURM / Nextflow runners
│   │   │   └── template_registry.py  # Intent → Nextflow DSL2 templates
│   │   ├── nfcore_integration.py  # nf-core pipeline discovery & execution
│   │   ├── skills/             # Skill ecosystem
│   │   │   ├── skill_dag.py    # Self-evolving typed knowledge graph
│   │   │   ├── loader.py       # Unified SKILL.md + scripts/ loader
│   │   │   ├── runtime.py      # Sandbox execution with schema validation
│   │   │   ├── registry.py     # Skill discovery & registration
│   │   │   ├── promotion.py    # Promote CodeAct runs to skills
│   │   │   └── models.py       # Pydantic skill definitions
│   │   ├── stability/          # Quality assurance
│   │   │   ├── schema_validator.py
│   │   │   ├── version_locker.py
│   │   │   └── regression_tester.py
│   │   ├── tools/              # Atomic tool registry + cross-process invocation
│   │   │   ├── registry.py
│   │   │   ├── approval.py
│   │   │   └── invoke_tool.py
│   │   ├── workspace/          # Data provenance & persistence
│   │   ├── reproducibility/    # Audit trail
│   │   ├── context/            # Working memory, semantic memory, compression
│   │   ├── knowledge/          # CBKB: 5-layer domain-specific knowledge base
│   │   ├── jobs/               # Background job queue + worker
│   │   └── api/                # FastAPI REST + WebSocket endpoints
│   └── tests/                  # 901 tests
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ui/             # Reusable UI component library + theme system
│       │   ├── layout/         # Sidebar, top bar, app shell
│       │   ├── settings/       # Settings panel (LLM, execution, search, budget)
│       │   ├── chat/           # Chat panel, HITL forms, plot rendering, sessions
│       │   ├── workspace/      # Workflow canvas, execution log panel, detail sidebars
│       │   ├── reports/        # Report list + viewer
│       │   ├── skills/         # Skill search + manager + generator
│       │   └── domains/        # Domain marketplace
│       ├── hooks/              # Theme, keyboard shortcuts, command palette
│       └── stores/             # Zustand state management
├── Dockerfile
├── docker-compose.yml
└── docs/
    ├── architecture.md
    ├── design.md
    ├── operations.md
    ├── domain-extension-guide.md
    ├── roadmap-v0.5.md
    └── homomics-lab-improvement-plan-v1.0.md
```

---

## API Endpoints

### Chat & Execution
| Endpoint | Description |
|---|---|
| `POST /api/chat/send` | Send message to agent |
| `POST /api/chat/hitl/respond` | Respond to HITL checkpoint |
| `POST /api/chat/debate/respond` | Respond to a debate choice |
| `WS /api/chat/ws/{session_id}` | Real-time chat WebSocket |
| `POST /api/chat/sla` | Assess confidence/execution mode before running |

### Skills
| Endpoint | Description |
|---|---|
| `GET /api/skills/` | List all skills |
| `GET /api/skills/search?q=` | Keyword search skills |
| `GET /api/skills/{id}` | Get skill details |
| `POST /api/skills/import` | Import skill from path/git/zip |
| `POST /api/skills/{id}/update` | Re-import/update a skill |
| `DELETE /api/skills/{id}` | Remove a skill |
| `POST /api/skills/{id}/enable` | Enable a skill |
| `POST /api/skills/{id}/disable` | Disable a skill |
| `POST /api/skills/{id}/validate` | Validate skill directory structure |
| `POST /api/skills/{id}/test` | Run skill's built-in tests |
| `POST /api/skills/{id}/trust` | Mark skill trusted/untrusted |
| `POST /api/skills/promote` | Promote CodeAct run to curated skill |
| `POST /api/skills/lock` | Create project version lock |
| `GET /api/skills/tools/pending` | List pending high-risk tool approvals |
| `POST /api/skills/approve-tool/{call_id}` | Approve a high-risk tool call |
| `POST /api/skills/reject-tool/{call_id}` | Reject a high-risk tool call |

### Plans & Jobs
| Endpoint | Description |
|---|---|
| `GET /api/plan/{plan_id}` | Get plan details |
| `POST /api/plan/{plan_id}/approve` | Approve a plan |
| `POST /api/plan/{plan_id}/reject` | Reject a plan |
| `POST /api/plan/{plan_id}/modify` | Modify and approve/reject a plan |
| `GET /api/execution/{job_id}/status` | Get job execution status |

### Domains & Marketplace
| Endpoint | Description |
|---|---|
| `GET /api/domains/` | List available domain templates |
| `POST /api/domains/import` | Import domain from path/git/zip |
| `POST /api/domains/import-zip` | Upload and import domain zip |
| `POST /api/domains/{id}/export` | Export domain template as zip |
| `POST /api/domains/import-templates` | Import code templates into a domain |

### Projects, Reports & Viz
| Endpoint | Description |
|---|---|
| `GET /api/projects` | List projects |
| `POST /api/projects` | Create project |
| `GET /api/projects/{id}` | Get project details |
| `POST /api/projects/{id}/lock-versions` | Lock environment versions |
| `POST /api/viz/plot` | Generate plot |
| `POST /api/reports/create` | Create analysis report |
| `GET /api/reports/{id}/html` | Export self-contained HTML report |

---

## CLI

```bash
# Initialize a new domain
homomics init metagenomics --phases "qc,denoising,taxonomy,diversity"

# Validate a domain.yaml
homomics validate domain.yaml

# Install a domain
homomics install ./metagenomics --domains-dir ./backend/homomics_lab/domains

# Generate a domain from a description (requires OPENAI_API_KEY)
homics generate "16S amplicon analysis with DADA2 and QIIME2"

# List installed domains
homomics list --domains-dir ./backend/homomics_lab/domains
```

---

## Testing

```bash
pytest backend/tests/ -q
# 901 passed
```

Coverage spans:
- **Agent layer**: Dynamic roles, adaptive planning, interpretation, orchestration, task state machine
- **Skill layer**: DAG evolution, unified loader, sandbox execution, semantic search, CodeAct cache
- **Stability layer**: Schema validation, version locking, regression testing
- **Workspace layer**: Path resolution, artifact registry, lineage graph, snapshots
- **Reproducibility layer**: Bundle capture, JSON roundtrip, environment lock
- **Integration layer**: AgentCore + Orchestrator, PlanEngine + AgentCore, Workspace + VersionLocker
- **Domain layer**: Domain declaration models, loader, registry, validation, hot-reload
- **Tool layer**: Cross-process invocation, approval flow, risk levels

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

- **Backend**: Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy, scikit-learn, sentence-transformers, sqlite-vec, pyarrow, weasyprint
- **Frontend**: React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Plotly.js
- **Workflows**: Nextflow (DSL2), SLURM (sbatch/sacct)
- **Deployment**: Docker, Docker Compose, nginx

---

## Roadmap

See [`docs/roadmap-v0.5.md`](docs/roadmap-v0.5.md) and [`docs/homomics-lab-improvement-plan-v1.0.md`](docs/homomics-lab-improvement-plan-v1.0.md) for detailed plans.

High-level next steps:
- Expand built-in and community skill coverage across single-cell, spatial, genomics, and metagenomics.
- Strengthen the self-evolution loop as execution history accumulates.
- Improve out-of-the-box experience for individual users (local model defaults, example datasets, guided onboarding).
- Harden long-running job reliability and resource monitoring for personal devices.

---

## License

MIT
