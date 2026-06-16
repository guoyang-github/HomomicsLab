# HomomicsLab Architecture (v0.4.1)

## Overview

HomomicsLab uses a layered hybrid architecture:
- **Core**: Python/FastAPI modular monolith
- **Frontend**: React + TypeScript + Zustand + ReactFlow
- **Skills**: Local subprocess sandbox execution (Python / R), with optional container/Firejail backends
- **Storage**: SQLite + filesystem + Parquet/H5AD/pickle offloading for large results

## Data Flow

1. User sends message via React frontend
2. FastAPI receives message, stores in working memory
3. **Intent analyzer** determines query type
4. **PlanEngine** generates strategy-aware execution plan (NOT SkillDAG traversal)
5. **AgentCore** resolves the best **DynamicAgent** for each task (1 Analyst + N on-demand Specialists)
6. **Orchestrator** dispatches tasks via state machine; long-running workflows are submitted as background **Job**s
7. **BackgroundJobRunner** executes jobs and streams progress via **ExecutionPubSub**; Agents execute skills in **SkillRuntimeExecutor** sandbox
8. **DataStore** offloads large skill results (DataFrame → Parquet, AnnData → H5AD, etc.) and returns a small `ResultReference`
9. **SkillCache** memoizes deterministic skill executions keyed by stable SHA-256 of inputs + skill fingerprint
10. **InterpretationEngine** interprets phase results and recommends next steps
11. **StabilityGuard** validates schemas (L1) and locks versions (L2)
12. **ReproducibilityEngine** captures code, plans, HITL decisions, environment lock, and finalizes a per-job bundle
13. **TraceStore** records per-job, per-task, per-phase execution nodes for observability
14. Results are returned via WebSocket/REST
15. Frontend updates chat panel and workspace

## Key Components

### Agent Layer (`agent/`)
- `agent/core/` — **AgentCore**: dynamic role injection system
  - `RoleDefinition`: YAML-configurable agent capabilities (skills, tools, prompts, permissions)
  - `DynamicAgent`: runtime agent driven by RoleDefinition (replaces hardcoded BioinfoAgent/VizAgent)
  - `AgentCore`: 1 permanent Analyst + on-demand Specialist spawning/dismissal
  - `RoleRegistry`: loads roles from `agent/core/roles/*.yaml`
- `agent/plan/engine.py` — **PlanEngine**: state-driven plan generation using domain strategy templates
- `agent/interpretation.py` — **InterpretationEngine**: phase-level result interpretation with anomaly detection
- `agent/orchestrator.py` — **Orchestrator**: task scheduler with retry, HITL, progress tracking, and trace-node recording
- `agent/turn_runner.py` — **TurnRunner**: unified conversational turn execution loop
- `jobs/` — **JobService + BackgroundJobRunner**: persistent SQLite-backed job queue and background execution worker

### Skills Layer (`skills/`)
- `skills/registry.py` — **SkillRegistry**: discovers and registers skills
- `skills/loader.py` — **SkillLoader**: unified loader for `SKILL.md + scripts/` format (built-in and external are identical)
- `skills/runtime.py` — **SkillRuntimeExecutor**: sandboxed execution with schema validation, caching, and data offloading
- `skills/skill_dag.py` — **SkillDAG**: self-evolving typed graph for skill discovery and relationship tracking (used for selection assistance, NOT plan generation)
- `skills/cache.py` — **SkillCache**: disk-based memoization of deterministic skill results
- `skills/models.py` — Pydantic models for skill definitions (input/output schema, runtime, metadata)
- `skills/semantic_search_v2.py` — optional dense semantic skill retrieval (sentence-transformers) with TF-IDF fallback

### Data Layer (`data/`)
- `data/data_store.py` — **DataStore**: automatic offloading of pandas/AnnData/pickle/large-JSON results to files

### Stability Layer (`stability/`)
- `stability/schema_validator.py` — **SchemaValidator** (L1): strict JSON Schema validation for skill inputs/outputs
- `stability/version_locker.py` — **VersionLocker** (L2): project-level version locking (skills, environment, Python version)
- `stability/regression_tester.py` — **RegressionTester** (L2): lightweight regression baselines for skill output drift detection

### Workspace Layer (`workspace/`)
- `workspace/manager.py` — **WorkspaceManager**: persistent project directories with artifact registry, SHA-256 checksums, data lineage graph, snapshots, and version locking integration
- `workspace/lineage.py` — **LineageGraph**: directed provenance graph of artifacts

### Reproducibility Layer (`reproducibility/`)
- `reproducibility/engine.py` — **ReproducibilityEngine**: captures agent code, plans, HITL decisions, environment lock, and skill versions into a replayable Bundle; started/finalized per job by `BackgroundJobRunner`

### Tools Layer (`tools/`)
- `tools/registry.py` — **ToolRegistry**: atomic tool capability registry (file_read/write/list, shell_exec, web_search, memory_search) with role-based access control and `risk_level` metadata
- `tools/approval.py` — **ToolApprovalStore**: interactive approval flow for high-risk tool calls when `HOMOMICS_INTERACTIVE_MODE=true`

### Observability Layer (`observability/`)
- `observability/trace_store.py` — **TraceStore**: persistent execution traces with correlation IDs, structured per job / task / phase

### Context Layer (`context/`)
- `context/working_memory.py` — **WorkingMemory**: session-level message and state storage
- `context/semantic_memory.py` — **SemanticMemory**: persistent vector-based memory for skill and result storage/retrieval

## Architecture Principles (v0.4.1)

1. **SkillDAG is NOT the plan driver**: Plan skeleton comes from domain strategy templates (`single_cell_standard`, `spatial_transcriptomics`, etc.). SkillDAG is only used for skill selection candidates, conflict detection, and alternative recommendations.

2. **GapFill removed**: AnalystAgent writes complete Python code that directly imports and calls skill functions. No opaque LLM-generated glue code.

3. **Dynamic roles replace hardcoded agents**: Instead of BioinfoAgent/VizAgent/ExperimentAgent classes, all agents are `DynamicAgent` instances configured by `RoleDefinition` YAML files.

4. **Unified skill format**: Built-in and external skills use the identical `SKILL.md + scripts/` format. Only `metadata["source"]` differs; external skills default to `trusted=false`.

5. **Progressive disclosure (L1/L2/L3)**:
   - L1: Skill list with name, description, category
   - L2: + input/output schemas, runtime requirements
   - L3: + full scripts, DAG edge info from SkillDAG query

6. **Phase-level interpretation**: InterpretationEngine triggers at phase boundaries, not every step, providing actionable recommendations based on rules + SkillDAG + data state.

7. **Result offloading by default**: Large objects never travel as inline JSON; `DataStore` serializes them to the workspace and returns a `ResultReference`.

8. **Deterministic caching**: Identical skill inputs + fingerprint skip execution entirely via `SkillCache`.

9. **Defense in depth for tools**: High-risk tools (`shell_exec`, `file_write`, `file_edit`) carry `risk_level=high`; interactive mode requires explicit approval before invocation.

10. **Reproducibility per job**: Every background job produces a finalized `ReproducibilityBundle`, and outcomes are ingested into CBKB for self-evolution.
