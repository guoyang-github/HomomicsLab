# HomomicsLab Operations Guide (v0.4.0)

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Domain Extension via CLI](#domain-extension-via-cli)
5. [Project Management](#project-management)
5. [Running Analyses](#running-analyses)
6. [Agent Swarm Usage](#agent-swarm-usage)
7. [HITL Interactions](#hitl-interactions)
8. [HPC & Nextflow Execution](#hpc--nextflow-execution)
9. [Skill Development](#skill-development)
10. [CBKB Curation](#cbkb-curation)
11. [Monitoring & Observability](#monitoring--observability)
12. [Troubleshooting](#troubleshooting)
13. [Production Deployment](#production-deployment)
14. [API Quick Reference](#api-quick-reference)

---

## Quick Start

```bash
# 1. Start backend (with WebSocket support)
conda activate nanobot
cd backend
uvicorn homomics_lab.main:app --host 0.0.0.0 --port 8000

# 2. Start frontend
cd frontend
npm run dev

# 3. Open browser
open http://localhost:5173

# 4. Create a project and upload data
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "first_analysis", "description": "My first analysis"}'

# 5. Send a message
curl -X POST http://localhost:8000/chat/send \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "message": "Perform differential expression on my data"}'
```

---

## Installation

### Requirements

| Component | Version |
|-----------|---------|
| Python | 3.12+ |
| Node.js | 20+ |
| SQLite | 3.35+ (with JSON1) |
| OS | Linux / macOS / WSL2 |

### Python Backend

```bash
conda create -n nanobot python=3.12
conda activate nanobot
pip install -r backend/requirements.txt
```

Key dependencies: FastAPI, pydantic, sentence-transformers, sqlite-vec, psutil, pynvml, plotly, weasyprint

### Frontend

```bash
cd frontend
npm install
```

### Optional: sentence-transformers Model

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Docker (One-command Deploy)

```bash
docker compose up --build
# Access at http://localhost:80
```

---

## Configuration

### Backend Config (`backend/.env`)

```env
# Core
APP_ENV=development
DATABASE_URL=sqlite:///./homomics_lab.db

# LLM (required for chat)
OPENAI_API_KEY=sk-...
# or ANTHROPIC_API_KEY=sk-ant-...

# Semantic Memory
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Reproducibility
WORKSPACE_ROOT=./workspaces
RANDOM_SEED=42

# Swarm
MAX_PARALLELISM=3

# Scheduled Tasks (APScheduler)
HOMOMICS_CURATION_ENABLED=true
HOMOMICS_CURATION_SCHEDULE=0 2 * * *
HOMOMICS_NARRATIVE_REPORT_ENABLED=true
HOMOMICS_NARRATIVE_REPORT_SCHEDULE=0 6 * * *
HOMOMICS_SOP_PROPOSAL_ENABLED=true
HOMOMICS_SOP_PROPOSAL_SCHEDULE=0 3 * * 0
HOMOMICS_SCHEDULER_TIMEZONE=UTC
# For development: run enabled jobs once shortly after startup
HOMOMICS_SCHEDULER_RUN_AT_STARTUP=false
```

Scheduled tasks run inside the API process. You can also trigger them manually:

```bash
curl -X POST http://localhost:8080/api/scheduler/jobs/cbkb_full_curation/run
```

And inspect recent runs:

```bash
curl http://localhost:8080/api/scheduler/runs?limit=10
```

### Job Queue & Workers (P3)

HomomicsLab can run background jobs either in-process with an `asyncio.Queue` or out-of-process using Redis for multi-replica deployments.

```env
# In-process queue (default, single-process development)
HOMOMICS_QUEUE_BACKEND=memory
HOMOMICS_WORKER_MODE=true

# Redis-backed queue + pub/sub (production / multiple workers)
HOMOMICS_QUEUE_BACKEND=redis
HOMOMICS_REDIS_URL=redis://redis:6379/0
HOMOMICS_WORKER_MODE=true
HOMOMICS_WORKER_CONCURRENCY=1
HOMOMICS_WORKER_HEARTBEAT_TTL=30
HOMOMICS_WORKER_LOCK_TTL=600
```

When `HOMOMICS_WORKER_MODE=true`, the API process starts a local worker that consumes the queue. For horizontal scaling, set `HOMOMICS_WORKER_MODE=false` on API replicas and run dedicated worker processes that share the same Redis URL.

Jobs transition through the same statuses as synchronous analyses (`QUEUED` → `RUNNING` → `COMPLETED`/`FAILED`/`AWAITING_HUMAN`). Progress is published to an in-memory or Redis pub/sub bus and is observable via `/api/jobs/{job_id}/state`.

### MCP Tools

HomomicsLab ships with embedded MCP tools for public bioinformatics databases:

- `pubmed_search` / `pubmed_fetch`
- `uniprot_search`
- `geo_search`

Configuration:

```env
HOMOMICS_MCP_ENABLED=true
HOMOMICS_MCP_MODE=embedded  # "embedded" is built-in; "stdio"/"sse" are planned
```

When enabled, agents will automatically invoke these tools for requests like:

- "搜索 PubMed 单细胞 RNA-seq"
- "查一下 UniProt p53"
- "找 GEO 里的肿瘤表达数据集"

MCP tools are also registered as lightweight skills, so the planner can include
them in multi-step workflows.

### Frontend Config

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

### Role Configuration (`agent/core/roles/`)

YAML files define agent roles. Example:

```yaml
# agent/core/roles/bioinformatician.yaml
name: "Bioinformatician"
description: "Expert in computational biology analysis"
allowed_skills:
  - deseq2
  - fastqc
  - kallisto
  - salmon
allowed_tools:
  - file_read
  - file_write
  - shell_exec
permissions:
  - execute_code
  - modify_workspace
priority: 2
```

---

## Domain Extension via CLI

HomomicsLab ships with a `homomics` command-line tool for managing domain extensions.

### Installation

After installing the package, the CLI is available as:

```bash
homomics --help
```

The console script is registered as `homomics` (not `homomics-lab`).

### Commands

#### `homomics init <name>`

Scaffold a new domain directory.

```bash
homomics init metagenomics --phases qc,denoising,taxonomy --output ./domains
```

This creates:

```
domains/metagenomics/
├── domain.yaml
├── skills/
│   └── .gitkeep
└── README.md
```

#### `homomics validate <domain.yaml>`

Validate a domain declaration before loading it.

```bash
homomics validate domains/metagenomics/domain.yaml --strict
```

#### `homomics install <source>`

Install a domain from a local directory or a git repository.

```bash
# Local directory
homomics install ./domains/metagenomics --domains-dir ./domains

# Git repository
homomics install https://github.com/example/homomics-metagenomics.git --domains-dir ./domains
```

#### `homomics generate --description "..."`

Generate a domain scaffold from a natural-language description (LLM-assisted).

```bash
homomics generate \
  "A spatial transcriptomics domain with QC, clustering, and deconvolution phases" \
  --output ./domains \
  --model gpt-4o
```

Requires `OPENAI_API_KEY` to be set.

#### `homomics list`

List all installed domains.

```bash
homomics list --domains-dir ./domains --verbose
```

### Domain Hot-Reload

Domains declared in `backend/homomics_lab/domains/` are automatically loaded when the FastAPI server starts. Changes to `domain.yaml` files are detected and reloaded without restarting the server.

External domains placed in `HOMOMICS_EXTERNAL_SKILLS_DIR` are also watched when that directory is configured.

---

## Project Management

### Creating a Project

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rna_seq_de_analysis",
    "description": "Differential expression of mouse liver RNA-seq"
  }'
```

Response:
```json
{
  "id": 1,
  "name": "rna_seq_de_analysis",
  "workspace_path": "./workspaces/rna_seq_de_analysis",
  "version_lock": {...}
}
```

### Project Workspace Structure

```
workspaces/{project_name}/
├── data/                    # Read-only input data
├── intermediate/            # Temporary outputs
├── outputs/                 # Final analysis outputs
├── logs/                    # Execution logs
└── .metadata/
    ├── reproducibility_bundle.json
    ├── version_lock.json
    └── checkpoints/
```

### Version Locking

```bash
# Lock current environment
curl -X POST http://localhost:8000/projects/1/lock-versions

# Verify environment hasn't drifted
curl http://localhost:8000/projects/1/verify-versions
```

### Provenance & RO-Crate Export

HomomicsLab records every skill execution in a provenance database. You can export a project together with its execution provenance as an RO-Crate zip archive for publication, audit, or long-term reproducibility.

```bash
# Via CLI
homomics export <project_id> --format rocrate -o ./exports

# Via API
curl -X POST http://localhost:8000/api/projects/<project_id>/export/rocrate \
  --output project_rocrate.zip
```

The exported archive contains `ro-crate-metadata.json` describing the dataset, each recorded execution as a `CreateAction`, and the input/output files referenced by the provenance records.

### Project Audit Log

HTTP requests that include a `project_id` are written to a rotating audit log when `HOMOMICS_AUDIT_LOG_ENABLED=true`. Project members can query recent entries:

```bash
curl http://localhost:8000/api/projects/<project_id>/audit?limit=50
```

### Skill Versioning

Skills use semantic versioning (`major.minor.patch`). You can compare two skill definitions programmatically:

```python
from homomics_lab.skills.versioning import detect_breaking_changes, bump_version
from homomics_lab.skills.models import SkillDefinition

changes = detect_breaking_changes(old_skill, new_skill)
new_version = bump_version(old_skill.version, changes)
```

Breaking changes include removing required inputs, adding new required inputs, removing guaranteed outputs, or changing the runtime language.

---

## Running Analyses

### Single-Message Analysis

```bash
curl -X POST http://localhost:8000/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "message": "Run QC on all samples, then differential expression comparing treatment vs control",
    "data_state": {
      "has_reads": true,
      "n_samples": 6,
      "has_counts": false
    }
  }'
```

### Multi-turn Conversation (WebSocket)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onopen = () => {
  ws.send(JSON.stringify({
    project_id: 1,
    message: "Show me the volcano plot"
  }));
};
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: "thought" | "tool_call" | "tool_result" | "final"
  console.log(msg.type, msg.content);
};
```

### Analysis States

| State | Description |
|-------|-------------|
| `PENDING` | Message received, awaiting execution |
| `RUNNING` | Agent is executing skills |
| `AWAITING_HUMAN` | HITL checkpoint reached |
| `COMPLETED` | Analysis finished successfully |
| `FAILED` | Error occurred (check logs) |
| `ABORTED` | User cancelled or system shutdown |

### Result Storage & Loading (P3)

Large or non-JSON skill outputs are persisted by `DataStore` and returned as `ResultReference` objects. Supported formats include JSON, Parquet, HDF5 (`.h5ad`), Zarr, and (opt-in) Pickle.

```python
from homomics_lab.data import DataStore

store = DataStore("./data")
ref = store.store("task_1", large_anndata_object)  # may return a path reference
```

Zarr arrays and groups are detected automatically and stored as on-disk `.zarr` directories. You can reload any reference through the API:

```bash
curl -X POST http://localhost:8080/api/results/load \
  -H "Content-Type: application/json" \
  -d '{
    "inline": false,
    "path": "./data/results/task_1_a1b2c3d4.zarr",
    "format": "zarr",
    "size": 0
  }'
```

For `zarr`, `parquet`, `h5ad`, and `pickle` references the endpoint returns a streaming `FileResponse`. For JSON-compatible references it returns the deserialized payload.

---

## Agent Swarm Usage

### When to Use Swarm

- **Parallel QC**: Run FastQC on multiple samples simultaneously
- **Consensus mode**: Have 3 agents independently call peaks, then vote
- **Multi-dataset analysis**: Process treatment and control groups in parallel

### Consensus Vote Example

```python
from homomics_lab.agent.swarm import AgentSwarm
from homomics_lab.agent.core.agent_core import AgentCore

swarm = AgentSwarm(agent_core)

# 3 agents independently call peaks
agents = [agent_core.spawn_specialist("bioinformatician", f"caller_{i}") for i in range(3)]
result = await swarm.consensus_vote(
    task={"type": "call_peaks", "data_path": "/path/to/bam"},
    agents=agents,
    context={"genome": "mm10", "format": "macs2"}
)

print(f"Consensus: {result.consensus_value}")
print(f"Dissent: {result.dissent_records}")
```

### Parallel Task Group

```python
from homomics_lab.agent.swarm import ParallelTaskGroup

tasks = ParallelTaskGroup(max_parallelism=4)
tasks.add({"type": "fastqc", "sample": "sample1.fastq"})
tasks.add({"type": "fastqc", "sample": "sample2.fastq"})
tasks.add({"type": "fastqc", "sample": "sample3.fastq"})
tasks.add({"type": "fastqc", "sample": "sample4.fastq"})

results = await swarm.execute_parallel(tasks)
# results = {"sample1.fastq": {...}, "sample2.fastq": {...}, ...}
```

---

## HITL Interactions

### Checkpoint Triggers

HITL checkpoints are auto-inserted for:
- Destructive operations (deleting intermediate files)
- Low-confidence decisions (model uncertainty > threshold)
- Complex operations (operations with >5 tool calls)
- Budget-critical operations (HPC job submission with >$10 estimate)

### Responding to HITL

```bash
# Get pending checkpoints
curl http://localhost:8000/hitl/pending?project_id=1

# Respond to a checkpoint
curl -X POST http://localhost:8000/hitl/respond \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_id": 42,
    "choice": "approve",
    "parameters": {"threshold": 0.05}
  }'

# Or reject with custom parameters
curl -X POST http://localhost:8000/hitl/respond \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_id": 42,
    "choice": "reject",
    "custom_parameters": {"threshold": 0.01}
  }'
```

---

## Domain Marketplace

HomomicsLab includes a domain template marketplace for sharing and importing bioinformatics domain declarations.

## List available domains

```bash
curl http://localhost:8000/api/domains/
```

## Import a domain

```bash
# From a local directory
curl -X POST http://localhost:8000/api/domains/import \
  -H "Content-Type: application/json" \
  -d '{"source": "./domains/metagenomics"}'

# From a git repository
curl -X POST http://localhost:8000/api/domains/import \
  -H "Content-Type: application/json" \
  -d '{"source": "https://github.com/example/homomics-metagenomics.git"}'
```

## Export a domain

```bash
curl -X POST http://localhost:8000/api/domains/metagenomics/export
```

## Import code templates

```bash
curl -X POST http://localhost:8000/api/domains/import-templates \
  -H "Content-Type: application/json" \
  -d '{
    "domain_id": "metagenomics",
    "templates": {"qc_template": "...code..."}
  }'
```

The marketplace UI is available in the frontend under the **Domains** workspace tab.

---

# CodeAct Cache & Tool Sandbox

## CodeAct Cache

CodeAct-generated code is cached by task-description embedding similarity. To disable:

```env
HOMOMICS_CODEACT_CACHE_ENABLED=false
```

Cache directory defaults to `./data/codeact_cache`.

## Tool Invocation Sandbox

High-risk tools can be forced to run in an isolated sandbox:

```env
HOMOMICS_FORCE_SANDBOX=true
HOMOMICS_SKILL_SANDBOX_BACKEND=auto   # auto | local | bubblewrap | container
```

- `local`: subprocess inside the worker process (fastest, least isolation)
- `bubblewrap`: Linux user-namespace sandbox (recommended for local dev)
- `container`: Docker/container runtime (recommended for production)

---

# Skill Development

### Canonical Skill Directory

The runtime canonical skill directory is the **project-root `skills/` folder** (`HomomicsLab/skills/`). On startup the backend:

1. Registers any skill placed directly under `skills/` as a user drop-in skill.
2. Copies skills imported from git/zip/external directories into `skills/`.

This path is independent of the backend's working directory because `HOMOMICS_SKILLS_DIR` defaults to the project root. Override it only if you want a non-standard layout:

```env
HOMOMICS_SKILLS_DIR=/path/to/skills
```

External skill repositories are **not** auto-discovered. To load skills from outside `skills/`, set `HOMOMICS_EXTERNAL_SKILLS_DIRS` explicitly:

```env
HOMOMICS_EXTERNAL_SKILLS_DIRS=./external_skills,/path/to/other-skills
HOMOMICS_SKILL_SIBLING_DISCOVERY_ENABLED=false
```

`backend/skills/` is not used as the canonical directory; any previous content there was a runtime artifact of launching the backend from `backend/` with the old relative default.

### Directory Structure

```
skills/{skill_id}/
├── SKILL.md              # Manifest (YAML frontmatter)
├── README.md             # Human documentation
├── scripts/
│   ├── python/           # Python implementations
│   │   └── main.py
│   └── r/                # R implementations (optional)
│       └── main.R
├── tests/
│   └── test_main.py
└── resources/            # Static data files
    └── reference_genome.fa
```

### SKILL.md Template

```markdown
---
id: "my_skill"
name: "My Analysis Skill"
description: "Brief description"
category: "rnaseq"
runtime: "python"
input_schema:
  type: object
  required: [input_file, output_dir]
  properties:
    input_file:
      type: string
      format: "*.fastq.gz"
    output_dir:
      type: string
output_schema:
  type: object
  required: [output_file]
  properties:
    output_file:
      type: string
---

## Usage

```python
from homomics_lab.skill_runtime import execute_skill

result = execute_skill("my_skill", {
    "input_file": "sample.fastq.gz",
    "output_dir": "./results"
})
```
```

### Per-Skill Conda Environments

If a skill requires packages that are easier to manage with conda, place an `environment.yml` next to `requirements.txt` in `scripts/`:

```yaml
# skills/{skill_id}/scripts/environment.yml
name: my_skill_env
channels:
  - conda-forge
  - bioconda
dependencies:
  - python=3.11
  - numpy
  - scanpy
```

When `conda` or `mamba` is available on `PATH`, `EnvironmentManager` will create or reuse a cached conda prefix from the `environment.yml`. If neither is available, the manager falls back to `requirements.txt` and logs a warning.

### R Container Image

When the sandbox backend is set to `container`, R skills automatically use the image configured in `settings.r_container_image` (default: `r-base:4.3.0`). Python skills continue to use `settings.skill_container_image` (default: `python:3.10-slim`). Set `R_CONTAINER_IMAGE` in your environment or `homomics_lab.toml` to override it.

### Testing Skills

```bash
# Run skill tests from the project root
pytest skills/my_skill/tests/ -v

# Run with coverage
pytest skills/my_skill/tests/ --cov=homomics_lab --cov-report=html
```

### Registering New Skills

Skills are auto-discovered on startup. To hot-reload:

```python
from homomics_lab.skills.registry import SkillRegistry
registry = SkillRegistry()
registry.load_all()  # Re-scan skills/ directory
```

---

## CBKB Curation

### Manual Trigger

```python
from homomics_lab.knowledge.cbkb import CBKB
from homomics_lab.knowledge.curator import CBKBCurator

cbkb = CBKB()
curator = CBKBCurator(cbkb)

# Full curation run
report = curator.run_full_curation()
print(f"Distilled {report['insights']} insights")
print(f"Found {report['topics']} topic clusters")
print(f"Generated narrative: {report['narrative']}")
```

### Nightly Auto-Curation

Enable in config:
```env
CURATION_SCHEDULE=0 2 * * *   # Every day at 2 AM
```

Or run manually:
```bash
python -c "
from homomics_lab.knowledge.curator import run_curation_job
run_curation_job()
"
```

## Evaluation

### Lightweight Evaluation Harness

`homomics_lab.evaluation.harness` provides a no-framework way to benchmark skills or plans against a JSONL dataset:

```python
from homomics_lab.evaluation.harness import load_cases, run_evaluation, save_report

cases = load_cases("benchmarks/rnaseq_skill.jsonl")
report = run_evaluation(cases, evaluator=my_skill_executor)
save_report(report, "results/rnaseq_report.json")
```

Each JSONL line must contain ``input`` and ``expected`` keys. For list-valued expectations the harness reports precision, recall, and F1 in addition to pass rate.

### Accessing Curated Knowledge

```python
# Query parameter lore
lore = cbkb.suggest_parameters("deseq2", metric="padj_rate")

# Get narrative report
report = curator.generate_narrative(period_days=30)
print(report.summary)

# Check SOP divergence
proposals = curator.propose_sop_updates()
for p in proposals:
    print(f"SOP '{p.sop_id}' divergence: {p.divergence_score}")
```

---

## Monitoring & Observability

### Logs

Backend logs are structured JSON:

```bash
# Tail logs
tail -f workspaces/*/logs/execution.log | jq .

# Search for errors
grep '"level":"ERROR"' workspaces/*/logs/execution.log | jq '.timestamp, .message'
```

Log format:
```json
{
  "timestamp": "2026-06-10T10:00:00Z",
  "level": "INFO",
  "agent": "analyst",
  "phase": "deseq2_run",
  "skill": "deseq2",
  "message": "Skill executed successfully",
  "duration_ms": 2450
}
```

### Metrics

```bash
# System health
curl http://localhost:8000/health

# Prometheus metrics (if enabled)
curl http://localhost:8000/metrics
```

### Workspace Monitoring

```python
from homomics_lab.workspace import WorkspaceManager

wm = WorkspaceManager("./workspaces")
status = wm.monitor_all()

for project, info in status.items():
    print(f"{project}: {info['disk_usage']} used, {info['artifact_count']} artifacts")
```

---

## HPC & Nextflow Execution

HomomicsLab can dispatch analyses to three execution backends. The default is local sandbox execution; for cluster or pipeline workloads, configure SLURM or Nextflow.

| Backend | Environment | Best For |
|---|---|---|
| **LocalScheduler** | Default | Development, small data, quick iteration |
| **SlurmScheduler** | `SLURM_*` env vars or scheduler config | HPC clusters, long-running jobs, many cores |
| **NextflowRunner** | Nextflow installed (`nextflow` on PATH) | Reproducible DSL2 pipelines, nf-core workflows |

### Configuration

```env
# General execution backend selection
HOMOMICS_EXECUTION_BACKEND=local   # local | slurm | nextflow

# SLURM (optional)
HOMOMICS_SLURM_PARTITION=cpu
HOMOMICS_SLURM_ACCOUNT=lab
HOMOMICS_SLURM_TIME=04:00:00
HOMOMICS_SLURM_MEM=16G
HOMOMICS_SLURM_CPUS_PER_TASK=4

# Nextflow / nf-core (optional)
HOMOMICS_NFCORE_PROFILES=docker,slurm   # comma-separated Nextflow profiles
HOMOMICS_NFCORE_WORKDIR=./work/nfcore
```

### Running a Nextflow Template from the Agent

When the plan resolves to an intent with a registered Nextflow template (e.g., `rnaseq_analysis`), the `NextflowRunner` renders the template and submits it:

```bash
curl -X POST http://localhost:8080/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "message": "Run an nf-core rnaseq pipeline on my FASTQ files",
    "execution_backend": "nextflow"
  }'
```

### Listing and Running nf-core Pipelines

```bash
# List available nf-core pipelines
curl http://localhost:8080/api/nfcore/pipelines?refresh=false

# Run a pipeline with schema-validated parameters
curl -X POST http://localhost:8080/api/nfcore/run \
  -H "Content-Type: application/json" \
  -d '{
    "name": "nf-core/rnaseq",
    "version": "3.14.0",
    "params": {
      "input": "samplesheet.csv",
      "outdir": "./results",
      "genome": "GRCh38"
    },
    "profiles": ["docker"]
  }'
```

### SLURM Submission

With `HOMOMICS_EXECUTION_BACKEND=slurm`, skill code is wrapped in an `sbatch` script. The backend:

1. Renders a job script using configured partition/account/resources.
2. Submits via `sbatch` and captures the job ID.
3. Polls `squeue` / `sacct` until completion.
4. Streams `stdout`/`stderr` back through the execution log panel.

You can also submit directly via API:

```bash
curl -X POST http://localhost:8080/api/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": 1,
    "message": "Differential expression on the counts matrix",
    "execution_backend": "slurm",
    "slurm_options": {"partition": "cpu", "time": "02:00:00"}
  }'
```

### Execution Logs

The frontend **Execution Log Panel** streams real-time logs for all backends. Logs include:

- `info` — scheduler-level events (submit, start, complete)
- `stdout` — tool/pipeline standard output
- `stderr` — warnings and errors
- `error` — fatal failures
- `success` — completion events

Logs are persisted in `workspaces/{project_id}/logs/` alongside the reproducibility bundle.

### Troubleshooting HPC/Nextflow

| Symptom | Cause | Fix |
|---|---|---|
| `NextflowNotFoundError` | `nextflow` not on PATH | Install Nextflow or set `NEXTFLOW_HOME` |
| `SlurmCommandNotFound` | `sbatch`/`squeue` not available | Verify SLURM client tools, or use local backend |
| `NFCoreSchemaValidationError` | Pipeline params mismatch schema | Check the pipeline's `nextflow_schema.json` |
| `ProfileNotDetected` | Missing container/engine profile | Add `docker`, `singularity`, or `conda` to profiles |
| Pipeline hangs | Executor queue full | Check `squeue`; increase `time` or choose another partition |

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `SkillNotFoundError` | Skill not in `skills/` directory | Run `SkillRegistry.load_all()` |
| `SchemaValidationError` | Input/output doesn't match schema | Check `SKILL.md` schemas |
| `VersionLockMismatch` | Dependencies changed | Run `project.lock_versions()` |
| `RegressionFailure` | Skill output changed | Review `test_regression.py` |
| `HITLTimeout` | Human didn't respond in time | Adjust `HITL_TIMEOUT` env var |
| `EmbeddingModelError` | sentence-transformers not loaded | Run model download script |
| `SwarmOversubscribed` | Too many parallel tasks | Reduce `MAX_PARALLELISM` |
| `CBKBLockError` | Concurrent access | Use context manager: `with cbkb.lock():` |

### Debug Mode

```bash
# Enable verbose logging
export HOMOMICS_LOG_LEVEL=DEBUG
export HOMOMICS_LOG_FORMAT=detailed

# Run with debugger
python -m pdb -m pytest tests/test_specific.py -v
```

### Checking Test Status

```bash
cd backend
pytest -v --tb=short

# Run specific module
pytest tests/test_agent/test_core.py -v

# Run with warnings
pytest -v -W error::DeprecationWarning
```

---

## Production Deployment

### Checklist

- [ ] `APP_ENV=production`
- [ ] `DATABASE_URL` points to persistent SQLite or PostgreSQL
- [ ] `WORKSPACE_ROOT` on durable storage (not ephemeral)
- [ ] `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` set
- [ ] Version lock created for each project
- [ ] Nightly curation scheduled
- [ ] Log rotation configured
- [ ] Backup strategy for `workspaces/` and `homomics_lab.db`

### Docker Compose (Production)

```yaml
version: '3.8'
services:
  backend:
    build: .
    environment:
      - APP_ENV=production
      - DATABASE_URL=sqlite:///data/homomics_lab.db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - workspaces:/app/workspaces
      - data:/app/data
    deploy:
      resources:
        limits:
          memory: 16G
        reservations:
          memory: 4G

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  workspaces:
  data:
```

### Backup

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/homomics_lab/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Database
cp homomics_lab.db $BACKUP_DIR/

# Workspaces (exclude large intermediate files)
rsync -av --exclude='intermediate/' workspaces/ $BACKUP_DIR/workspaces/

# CBKB
sqlite3 homomics_lab.db ".backup '$BACKUP_DIR/cbkb_backup.db'"
```

---

## Progressive Web App & Real-time Collaboration

### PWA / Offline Support

The frontend ships as a Progressive Web App:

- `frontend/public/manifest.json` defines the app metadata and icons.
- `frontend/public/sw.js` precaches the shell (`index.html`) and serves it as a fallback when the network is unavailable.
- The service worker is registered from `frontend/src/main.tsx`.

When deployed over HTTPS, users can install HomomicsLab to their home screen and continue viewing previously loaded pages while offline.

### Real-time Collaboration

HomomicsLab includes a lightweight presence channel for shared project workspaces:

- **WebSocket**: `/api/collab/{project_id}/ws?user_id={user_id}` broadcasts cursor positions and editing state to other users in the same project.
- **REST**: `GET /api/collab/{project_id}/presence` returns the list of active users.
- The frontend renders remote cursors (`CollabLayer` / `PresenceCursors`) and an active-user indicator in the bottom-right corner.

Presence data is ephemeral and scoped to the running backend process; no persistent session store is required.

---

## API Quick Reference

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/send` | Send message, get response |
| POST | `/chat/hitl/respond` | Respond to HITL checkpoint |
| WS | `/ws` | WebSocket for real-time chat |

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects` | List all projects |
| POST | `/projects` | Create new project |
| GET | `/projects/{id}` | Get project details |
| POST | `/projects/{id}/lock-versions` | Lock environment versions |
| GET | `/projects/{id}/verify-versions` | Verify environment |
| POST | `/projects/{id}/export/rocrate` | Export project + provenance as RO-Crate zip |
| GET | `/projects/{id}/audit` | Project audit log |

### Skills

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/skills` | List available skills (L1) |
| GET | `/skills/{id}` | Get skill details (L2/L3) |
| POST | `/skills/execute/{id}` | Execute skill directly |

### Visualization

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/viz/plot` | Generate plot |
| POST | `/reports/generate` | Generate report (HTML/PDF) |

### nf-core / Nextflow

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/nfcore/pipelines` | List available nf-core pipelines |
| POST | `/api/nfcore/run` | Run an nf-core pipeline |
| GET | `/api/nfcore/status/{run_id}` | Get pipeline run status |

### Collaboration

| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/api/collab/{project_id}/ws` | Presence / cursor broadcast channel |
| GET | `/api/collab/{project_id}/presence` | List active users in a project |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| GET | `/metrics` | Prometheus metrics |

---

## Development & CI

The repository uses GitHub Actions (`.github/workflows/ci.yml`) to run:

- Backend unit tests with coverage (`pytest backend/tests/`).
- `ruff` linting across `backend/homomics_lab` and `backend/tests`.
- `mypy` type checking (informational).
- Frontend tests (`npm test -- --run`) and production build (`npm run build`).
- Backend Docker image build and smoke test.

Local quick checks:

```bash
# Backend
cd backend
../.venv/bin/python -m pytest tests/ -q

# Frontend
cd frontend
npm test -- --run
npm run build
```

---

## Support

- GitHub Issues: Report bugs and feature requests
- Discussions: Architecture questions and community help
- Email: For security concerns

For internal developers, see `docs/architecture.md` for detailed design documents.
