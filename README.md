# HomomicsLab

A general-purpose agent platform for computational biology that bridges the gap between **rigid bioinformatics pipelines** and **unstructured notebook collections**. HomomicsLab turns natural language research questions into reproducible, auditable, and self-evolving analysis workflows—combining the adaptability of AI agents with the rigor of production-grade data engineering.

> **v0.4.1** — End-to-end analysis automation with **single-file domain declarations**, CLI scaffolding, LLM-assisted domain generation, runtime hot-reloading, dynamic agent roles, multi-agent swarm, self-evolving skill knowledge graphs, dynamic replanning, agent self-evolution, CBKB auto-curation, multi-layer stability guards, and complete reproducibility capture.

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

## What Makes HomomicsLab Different

HomomicsLab is not built in a vacuum. It synthesizes the best ideas from **general-purpose AI agents**, **bioinformatics workflow systems**, **interactive notebooks**, **MLOps tooling**, and **code-generation assistants**—then adds the missing pieces that none of them provide alone.

### Intellectual Lineage

HomomicsLab is part of a rapidly emerging class of **domain-specific agent systems** for science. We directly acknowledge the shoulders we stand on:

| System | What We Adopted | What Was Missing (That HomomicsLab Adds) |
|---|---|---|
| **Biomni** (Stanford/Genentech) | CodeAct-style code generation; unified biomedical tool space; retrieval-augmented planning | Single-agent architecture with no stability guards; no version locking; no data lineage; reproducibility is an afterthought |
| **DeerFlow 2** (ByteDance) | Sub-agent orchestration; sandboxed execution; progressive skill loading; persistent memory | Generalist research harness with no bioinformatics domain strategy; no schema validation; no regression testing; loop detection kills legitimate bioinformatics workflows |
| **Hermes** (NousResearch) | `SKILL.md` skill specification format; modular skill libraries | No execution-time schema validation; no skill relationship evolution; no workspace provenance |
| **OmicVerse** | Single-cell/bulk RNA-seq analysis methods; visualization best practices | A Python library, not an agent—requires manual orchestration; no natural language interface; no reproducibility capture |
| **CowAgent** (zhayujie) | Sub-agent orchestration; sandboxed execution; progressive skill loading; persistent memory; Markdown wiki PKB | Generalist IM assistant with no bioinformatics domain strategy; no schema validation; no regression testing; PKB is a black-box wiki with no experiment provenance or parameter lore |
| **AutoGPT / BabyAGI** | Autonomous planning loops; task decomposition; memory layers | No domain knowledge of biology; no stability guards; no reproducibility framework |
| **LangChain / LlamaIndex** | Tool registry abstraction; context compression; retrieval patterns | No strict schema validation for tool I/O; no version locking; no regression testing |
| **Galaxy / nf-core** | Community-validated workflows; reproducible environments | Rigid parameter schemas; users must speak "workflow-ese"; no adaptive planning based on data state |
| **Snakemake / Nextflow** | Declarative execution; HPC scalability | Require expert orchestration; no semantic understanding of data state |
| **Aider / Cursor / Devin** | Code generation as first-class artifact; agent-driven editing | No domain strategy templates; no explanation of *why* code was generated; no cross-run learning |
| **W&B / MLflow** | Experiment tracking; environment logging | Track model training, not end-to-end bioinformatics analysis; miss HITL decisions and agent reasoning |
| **DVC** | Data versioning; pipeline lineage concepts | Require manual DAG definition; no automated provenance from agent execution |

**What none of the above provide together**: a **bioinformatics-native agent platform** with dynamic roles, self-evolving skill relationships, three-layer stability guards, complete reproducibility bundles, and automated data lineage—running inside a sandboxed workspace with human-in-the-loop checkpoints.

### 0. Single-File Domain Declaration — Extend to Any Omics in 20 Minutes

HomomicsLab is not limited to single-cell or spatial transcriptomics. Any bioinformatics domain—genomics, proteomics, metabolomics, epigenomics, metagenomics—can be added via a **single `domain.yaml` file**.

```bash
# Initialize a new domain scaffold
homomics domain init metagenomics --phases "qc,denoising,taxonomy,diversity"

# Or let LLM generate it from natural language
homomics domain generate "16S amplicon analysis with DADA2 and QIIME2"

# Validate and install
homomics validate domain.yaml && homomics install .
```

No Python code changes. No service restart. The `DomainLoader` automatically registers skills, strategies, intents, DAG seeds, roles, and SOPs. See [`docs/domain-extension-guide.md`](docs/domain-extension-guide.md) for the full guide.

### 1. End-to-End Analysis Closure

From a sentence like *"Analyze my PBMC dataset and find marker genes for each cluster"* to a **self-contained HTML report with UMAPs, DE tables, and method sections**—in one conversation.

HomomicsLab handles the entire lifecycle:
- **Intent Analysis** — Parses natural language research goals into structured `UserIntent` objects. Dynamically loaded from `domain.yaml` intent declarations—not hardcoded keyword lists. Supports any bioinformatics workflow.
- **Adaptive Planning** — Selects from extensible domain strategy templates declared in `domain.yaml` and generates plans that adapt to real-time data state. Batch detected → inject integration; low quality → tighten QC; skill fails → auto-swap alternative via SkillDAG.
- **Execution** — Sandboxed skill runtime with schema validation and resource monitoring. Skills are **source-agnostic**—builtin, external, community, or user-uploaded are treated identically.
- **Interpretation** — Phase-level result analysis: "QC filtered 12% of cells—within normal range. Next: normalization."
- **Reporting** — Auto-generated publication-ready HTML/Markdown reports with figures and provenance
- **Reproducibility** — Every analysis exports a `ReproducibilityBundle`: exact code, plan, HITL decisions, environment lock

### 2. Domain-Native Intelligence

HomomicsLab is not a thin wrapper around GPT-4. It embeds **bioinformatics workflow knowledge** at the architecture level:

- **Strategy Templates**: The PlanEngine carries built-in domain strategies (`single_cell_standard`, `spatial_transcriptomics`, `qc_only`) that encode the *correct order of operations*—not as hardcoded scripts, but as adaptable templates that respond to data characteristics.
- **Data-State Adaptation**: The plan changes based on what the data tells us. Batch effect detected? The plan automatically inserts integration. Low cell quality? QC thresholds tighten. Already have clusters? Skip redundancy.
- **SkillDAG**: A self-evolving knowledge graph that tracks how skills relate in practice—`scanpy_qc` → `scanpy_pca` → `scanpy_cluster`—learned from execution history, not hand-coded.

### 3. Self-Evolving Skill Ecosystem

Skills in HomomicsLab are not plugins you manually install and forget. They are **first-class citizens in a living system**:

- **Self-Evolving Relationships**: The SkillDAG automatically discovers `followed_by`, `conflicts_with`, and `alternative_to` relationships from execution history and `domain.yaml` seed declarations. Edges graduate from `CANDIDATE` → `CONFIRMED` after repeated success.
- **Semantic Discovery**: Dual-engine skill search—TF-IDF for exact matching + sentence-transformers for conceptual similarity. A query for "reduce dimensions" finds PCA, UMAP, and t-SNE even if none mention "reduce" in their titles.
- **Auto-Generation**: Generate new skills from natural language requirements via templated scaffolding.
- **Unified Format**: Built-in and external skills use the identical `SKILL.md + scripts/` format. No "second-class citizen" external skills.

### 4. Multi-Layer Stability Guard

Bioinformatics analysis is too critical to fail silently. HomomicsLab deploys **defense in depth**:

| Layer | Defense | Prevents |
|---|---|---|
| **L1 — Schema Validation** | Every skill input/output validated against declared JSON Schema | Type mismatches, missing required fields, silent data corruption |
| **L2 — Version Locking** | Project-level lock: skill versions, script SHA-256, pip freeze, Python version | "It worked yesterday" drift, dependency hell |
| **L2 — Regression Testing** | Record baselines from known-good executions; detect output signature drift | Skill updates that silently change results |
| *(planned) L3* | Cross-phase semantic consistency checks | Logical contradictions between analysis steps |

### 5. Complete Reproducibility, Not Just Version Control

A Git commit is not enough for computational biology. HomomicsLab's `ReproducibilityEngine` captures:

- **Exact code** — The agent-generated Python that called the skills, not just skill names
- **The plan** — Full execution strategy with data-state adaptations
- **Every HITL decision** — When the human chose resolution=0.8 over the default
- **Environment lock** — `pip freeze`, `conda env export`, Python version
- **Skill version lock** — Exact versions and script checksums of every skill used

The result is a **JSON-serializable Bundle** that can be reloaded, inspected, and replayed.

### 6. Interpretable, Not a Black Box

After every major phase (QC, clustering, annotation, DE, visualization), the **InterpretationEngine** produces:

- A **human-readable summary**: *"QC filtered 12% of cells (2,531 remaining), within normal range."*
- **Anomaly flags**: *"High cell filtering rate: 80% — check data quality"* when filter rate exceeds 50%
- **Actionable recommendations**: *"Next: dimensionality reduction with PCA"* — ranked by confidence, informed by workflow rules + SkillDAG + current data state

Users always know what happened, why it happened, and what should come next.

### 7. Computational Biology Knowledge Base (CBKB)

Unlike generic personal knowledge bases (e.g., CowAgent's Markdown wiki), HomomicsLab's CBKB is **structured around the ontology of bioinformatics analysis**:

| Layer | Stores | Value |
|---|---|---|
| **Experiment Graph** | Every `ReproducibilityBundle` as a node; typed edges (`shares_skill`, `shares_parameter`, `derived_from`) | "Which past analyses used the same QC strategy?" |
| **Parameter Lore** | "Skill parameter → outcome quality" mappings extracted from execution history | "For PBMC datasets, `resolution=0.6` historically yields the best cluster separation" |
| **Anomaly Archive** | Every phase-level anomaly detected by InterpretationEngine | "Last time batch effect exceeded 30%, Harmony outperformed scVI" |
| **Lab SOP** | Best-practice templates auto-distilled from repeated successful analyses | Versioned, lockable standard operating procedures per lab |
| **Skill Evolution Log** | History of SkillDAG edge state transitions (`CANDIDATE` → `CONFIRMED`) | "Our lab's data has independently confirmed the QC→PCA→Cluster workflow 47 times" |

CBKB is **not a black-box vector database**. Every entry is traceable to a `ReproducibilityBundle`, a `Workspace` artifact, or a `SkillDAG` edge. It is a **collective memory for the lab**, not just the assistant.

### 8. Data Provenance as a First-Class Feature

Every artifact in HomomicsLab carries its history:

```
workspaces/{project_id}/
├── data/               # Original data — read-only protected (chmod 444)
├── intermediate/       # Step artifacts with SHA-256 checksums
├── outputs/            # Final deliverables
├── logs/               # Execution logs
└── .metadata/          # Artifact registry, lineage graph, snapshots, version.lock
```

- **Lineage Graph**: Directed provenance from raw data → QC → clustering → DE → figures
- **Snapshots**: Point-in-time workspace state capture
- **Checksum Integrity**: Every artifact registered with SHA-256; tampering is detectable

### 9. Dynamic Agent Roles — Capability as Configuration

Instead of hardcoding `BioinfoAgent`, `VizAgent`, and `ExperimentAgent` classes, HomomicsLab uses **YAML-configurable roles** that determine what skills, tools, and permissions an agent has:

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

- One permanent **Analyst** coordinates; **Specialists** spawn on demand
- **Wildcard matching**: `scanpy_*` routes all Scanpy skills automatically
- **Blocked skills**: Explicit denylist for security-sensitive environments
- **Tool-level access control**: Each role sees only its permitted atomic tools

### 10. Long-Horizon Dynamic Replanning

Plans are not carved in stone. The **DynamicReplanningEngine** monitors execution and replans in real time when reality diverges from expectation:

- **Critical anomaly detected in QC** → automatically insert a re-QC phase with tightened thresholds
- **Batch effect discovered post-clustering** → dynamically insert integration before differential expression
- **Skill failure** → swap to an alternative skill via SkillDAG and resume
- **User intervention changes parameters** → propagate the change downstream through all dependent phases

Unlike static workflow engines (Snakemake, Galaxy), HomomicsLab adapts the plan *while executing* based on data state and intermediate results.

### 11. Multi-Agent Swarm — Parallel Execution + Consensus

HomomicsLab is not limited to a single agent per task. The **AgentSwarm** orchestrates multiple specialists in parallel:

- **Parallel task groups**: Independent tasks fan out to sub-agents with semaphore-controlled concurrency
- **Consensus voting**: The same task can be assigned to multiple agents; disagreeing opinions are surfaced with confidence scores
- **Broadcast messaging**: The lead analyst can broadcast context to all matching specialists
- **SwarmOrchestrator**: Automatically identifies independent task groups in a task tree and executes them in parallel

This is not just "multi-agent" theater—it's disciplined parallelism with conflict detection.

### 12. Agent Self-Evolution

Agents get smarter with every analysis. The **AgentEvolutionEngine** continuously learns from CBKB history:

- **Role evolution**: If `resolution=0.6` consistently yields better clusters across 10+ projects, the system proposes updating the role's default prompt or metadata
- **Plan pattern mining**: Recurring successful phase sequences are extracted as reusable plan patterns with success-rate statistics
- **Parameter preference learning**: Per-project and per-lab parameter preferences are automatically distilled from ParameterLore
- **SOP auto-evolution**: When a successful analysis pattern repeats >3 times, the system proposes a new Lab SOP or a version bump to an existing one

Roles and plans are **living configurations**, not static YAML files.

### 13. CBKB Auto-Curation — The Knowledge Base That Curates Itself

The Computational Biology Knowledge Base does not wait for manual maintenance. The **CBKBCurator** runs automatic curation passes:

- **Nightly distillation**: New experiment bundles are scanned for skill sequences, parameter combinations, and project similarities
- **Topic clustering**: Experiments are grouped by Jaccard similarity on skills + parameters; each cluster gets a topic name and centroid summary
- **Narrative reports**: "This month your lab analyzed 12 single-cell datasets. The most common anomaly was batch effect (6 occurrences). The most reliable parameter was `resolution=0.6`."
- **Auto-linking**: Similar experiments automatically get typed edges (`shares_skill`, `shares_parameter`) in the Experiment Graph
- **SOP divergence detection**: When existing SOPs no longer match the lab's actual best practices, the system flags them for review

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

---

## Project Structure

```
HomomicsLab/
├── backend/
│   ├── homomics_lab/
│   │   ├── domain/             # Domain declaration system (v0.4.1)
│   │   │   ├── models.py       # DomainDefinition, Phase, StateCheck Pydantic models
│   │   │   ├── loader.py       # DomainLoader — reads domain.yaml, auto-registers all
│   │   │   ├── registry.py     # DomainRegistry — manages loaded domains
│   │   │   ├── hot_reload.py   # Runtime hot-reload for domains & skills
│   │   │   └── domains/        # Built-in domain declarations
│   │   │       ├── single_cell/domain.yaml
│   │   │       ├── spatial/domain.yaml
│   │   │       └── metagenomics/domain.yaml
│   │   ├── cli/                # Command-line tools (v0.4.1)
│   │   │   ├── main.py         # homomics CLI entry point
│   │   │   └── commands/       # init, validate, install, generate, list
│   │   ├── agent/              # Agent orchestration layer
│   │   │   ├── core/           # AgentCore, DynamicAgent, RoleRegistry, roles/*.yaml
│   │   │   ├── plan/           # PlanEngine — adaptive strategy generation
│   │   │   ├── replanning.py     # DynamicReplanningEngine — execution-time plan adaptation
│   │   │   ├── interpretation.py   # InterpretationEngine
│   │   │   ├── swarm.py            # AgentSwarm — parallel multi-agent execution + consensus
│   │   │   ├── orchestrator.py     # Task scheduler with retry & HITL
│   │   │   ├── evolution.py        # AgentEvolutionEngine — role/plan/SOP self-evolution
│   │   │   └── turn_runner.py    # Unified conversational turn loop
│   │   ├── skills/             # Skill ecosystem
│   │   │   ├── skill_dag.py    # Self-evolving typed knowledge graph
│   │   │   ├── loader.py       # Unified SKILL.md + scripts/ loader (builtin/external/user)
│   │   │   ├── runtime.py      # Sandbox execution with schema validation
│   │   │   ├── registry.py     # Skill discovery & registration
│   │   │   └── models.py       # Pydantic skill definitions
│   │   ├── stability/          # Quality assurance
│   │   │   ├── schema_validator.py   # L1: JSON Schema validation
│   │   │   ├── version_locker.py     # L2: version locking
│   │   │   └── regression_tester.py  # L2: regression baselines
│   │   ├── workspace/          # Data provenance & persistence
│   │   │   ├── manager.py      # Persistent workspace + artifact registry
│   │   │   └── lineage.py      # Data provenance graph
│   │   ├── reproducibility/    # Audit trail
│   │   │   └── engine.py       # Bundle capture (code, plan, HITL, env)
│   │   ├── tools/              # Atomic tool registry with role filtering
│   │   ├── context/            # Working memory, semantic memory, compression
│   │   ├── knowledge/          # CBKB: 5-layer domain-specific knowledge base
│   │   │   ├── cbkb.py             # ExperimentGraph, ParameterLore, AnomalyArchive, LabSOP, SkillEvolutionLog
│   │   │   └── curator.py        # CBKBCurator — auto-distillation, clustering, narrative reports
│   │   ├── hpc/                # SLURM, Nextflow, local schedulers
│   │   ├── viz/                # Plotly-based visualization engine
│   │   ├── reports/            # HTML/Markdown report generation
│   │   └── api/                # FastAPI REST + WebSocket endpoints
│   └── tests/                  # 504 tests
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── chat/           # Chat panel, HITL forms, plot rendering
│       │   ├── workspace/      # Workflow canvas, tabs
│       │   ├── reports/        # Report list + viewer
│       │   └── skills/         # Skill search + generator
│       └── stores/             # Zustand state management
├── Dockerfile
├── docker-compose.yml
└── docs/
    ├── architecture.md         # v0.4.0 architecture principles
    └── setup.md
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `POST /api/chat/send` | Send message to agent |
| `POST /api/chat/hitl/respond` | Respond to HITL checkpoint |
| `GET /api/skills/` | List all skills |
| `GET /api/skills/search?q=` | Semantic + graph-boosted skill search |
| `POST /api/viz/plot` | Generate plot |
| `POST /api/reports/create` | Create analysis report |
| `GET /api/reports/{id}/html` | Export self-contained HTML report |
| `POST /api/skill-generator/generate` | Auto-generate skill from requirements |
| `POST /api/domains/install` | Install domain from upload |
| `GET /api/domains/` | List installed domains |
| `POST /api/domains/reload` | Hot-reload a domain |

---

## Testing

```bash
cd backend
pytest tests/ -q
# 538+ tests passing
```

Coverage spans:
- **Agent layer**: Dynamic roles, adaptive planning, interpretation, orchestration, task state machine
- **Skill layer**: DAG evolution, unified loader, sandbox execution, semantic search
- **Stability layer**: Schema validation, version locking, regression testing
- **Workspace layer**: Path resolution, artifact registry, lineage graph, snapshots
- **Reproducibility layer**: Bundle capture, JSON roundtrip, environment lock
- **Integration layer**: AgentCore + Orchestrator, PlanEngine + AgentCore, Workspace + VersionLocker
- **Domain layer**: Domain declaration models, loader, registry, validation, hot-reload

---

## Configuration

Environment variables (prefix `HOMOMICS_`):

| Variable | Default | Description |
|---|---|---|
| `HOMOMICS_PORT` | `8080` | API server port |
| `HOMOMICS_EXTERNAL_SKILLS_DIR` | — | Path to external skill collection |
| `HOMOMICS_SEMANTIC_SEARCH_MODEL` | — | Set to `all-MiniLM-L6-v2` for dense embeddings |

---

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy, scikit-learn, sentence-transformers, sqlite-vec
- **Frontend**: React 18, TypeScript, Tailwind CSS, Zustand, TanStack Query, Plotly.js
- **Workflows**: Nextflow (DSL2), SLURM (sbatch/sacct)
- **Deployment**: Docker, Docker Compose, nginx

---

## License

MIT
