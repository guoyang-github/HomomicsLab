# Changelog

All notable changes to HomomicsLab are documented in this file.

## [0.5.0] — Full Roadmap Implementation

### Added

- **Memory & retrieval**
  - Metadata-aware semantic memory with project/session filtering.
  - Hybrid dense + FTS5 search with RRF fusion.
  - Cross-encoder and bi-encoder rerankers.
  - Memory consolidation into `concept` memories.

- **HITL & preference learning**
  - `UserPreferenceStore` records choices from HITL checkpoints.
  - Natural-language HITL response parsing.
  - Adaptive HITL defaults and "Remember my choice" UI toggle.

- **Intelligent planning**
  - Probabilistic strategy scoring and beam search in `PlanEngine`.
  - `InformationGatheringEngine` probes missing project metadata.
  - SkillDAG schema-similarity edges and plan validation.

- **Execution layer**
  - Per-skill conda/mamba environments via `environment.yml`.
  - Provenance recorder wired into schedulers.
  - RO-Crate export API (`/api/projects/{id}/export/rocrate`) and CLI (`homomics export`).
  - R skills default to `settings.r_container_image` in container sandboxes.
  - **Cross-process tool invocation sandbox** (`backend/homomics_lab/tools/invoke_tool.py`): uniform protocol for invoking atomic tools across process boundaries, with `local`, `bubblewrap`, and `container` backends so high-risk tool calls run in isolated sandboxes.
  - **CodeAct code cache** (`backend/homomics_lab/execution/code_cache.py`): caches CodeAct-generated code keyed by task-description embeddings so similar tasks hit the cache instead of calling the LLM again.
  - **Auto-recorded regression baselines**: after a successful CodeAct execution, the system automatically records a regression baseline for drift detection.
  - **"Save as Skill" frontend button**: promotes a successful CodeAct run into a curated `SKILL.md + scripts/` package.

- **Frontend & collaboration**
  - PWA manifest, service worker, and offline fallback.
  - Real-time presence WebSocket with remote cursor overlay.
  - RO-Crate export button in the top bar.
  - **Modern UI/UX overhaul**: new component library (`Button`, `Input`, `Card`, `Modal`, `Tabs`, `Toast`, `CommandPalette`), light/dark theme system, sidebar + top-bar navigation, keyboard shortcuts and command palette (`Ctrl+K` / `Cmd+K`), settings panel for LLM provider/model, execution backend, search, budget, and general preferences.
  - **Chat**: Markdown + LaTeX + syntax-highlighted code rendering, drag-and-drop file uploads, session switching, and HITL inline forms.
  - **Workflow canvas**: real-time execution log panel, node status badges, zoom-to-fit, and detail sidebars.

- **Task orchestration & resource scheduling**
  - New `backend/homomics_lab/hpc/` module with pluggable execution backends: `LocalScheduler`, `SlurmScheduler`, and `NextflowRunner`.
  - Nextflow DSL2 template registry maps analysis intents to curated workflow templates.
  - nf-core integration supports pipeline discovery, download, schema-driven parameter loading, profile selection, and execution.
  - SLURM support via `sbatch`/`squeue`/`sacct` integration.
  - Execution backend is selectable per request.

- **Domain template marketplace**
  - `backend/homomics_lab/domain/marketplace.py` + `backend/homomics_lab/api/domains.py`.
  - Endpoints: `GET /api/domains/`, `POST /api/domains/import`, `POST /api/domains/import-zip`, `POST /api/domains/{id}/export`, `POST /api/domains/import-templates`.
  - Frontend: `frontend/src/components/domains/DomainMarketplace.tsx`.

- **Reproducibility & governance**
  - Project audit log endpoint (`/api/projects/{id}/audit`).
  - Skill semantic versioning with breaking-change detection.

- **Evaluation & CI/CD**
  - Lightweight evaluation harness (`homomics_lab.evaluation.harness`).
  - CI workflow now runs backend lint (ruff/mypy) and frontend tests.

### Changed

- Updated `docs/operations.md` with new API endpoints, PWA/collaboration, audit/versioning, and evaluation sections.
- Updated `docs/architecture.md` to v0.5.0 and corrected sandbox backend names (bubblewrap/container, no Firejail).
- Updated `AGENTS.md` and `backend/homomics_lab/version.py` fallback to `0.5.0`.

## [0.4.2] — Agent Execution Hardening & Domain Marketplace

### Added

- **Cross-process tool invocation sandbox** (`backend/homomics_lab/tools/invoke_tool.py`)
  - Uniform protocol for invoking atomic tools across process boundaries.
  - Supports `local`, `bubblewrap`, and `container` backends.
  - High-risk tools (`shell_exec`, `file_write`, `file_edit`) can be forced to run inside an isolated sandbox via `HOMOMICS_FORCE_SANDBOX=true`.

- **CodeAct code cache** (`backend/homomics_lab/execution/code_cache.py`)
  - Caches CodeAct-generated code keyed by task-description embeddings.
  - Similar tasks hit the cache instead of calling the LLM again.
  - Configurable via `HOMOMICS_CODEACT_CACHE_ENABLED` and `HOMOMICS_CODEACT_CACHE_DIR`.

- **Auto-recorded regression baselines** (`backend/homomics_lab/stability/regression_tester.py`)
  - Successful CodeAct executions automatically record a regression baseline.
  - Future runs can be compared against the baseline to detect silent drift.

- **"Save as Skill" frontend button**
  - `frontend/src/components/skills/SkillManager.tsx` now includes a **Save as Skill** button.
  - Calls `POST /api/skills/promote` to turn a successful CodeAct run into a curated `SKILL.md + scripts/` package.

- **Domain template marketplace**
  - `backend/homomics_lab/domain/marketplace.py` + `backend/homomics_lab/api/domains.py`
  - Endpoints: `GET /api/domains/`, `POST /api/domains/import`, `POST /api/domains/import-zip`, `POST /api/domains/{id}/export`, `POST /api/domains/import-templates`.
  - Frontend: `frontend/src/components/domains/DomainMarketplace.tsx` with a new **Domains** tab in the workspace.

- **Tests**
  - Added regression and integration tests covering tool sandbox invocation, CodeAct cache hit/miss, and domain marketplace import/export.
  - Full backend suite: **901 passed**.

### Changed

- Updated `README.md` and `README.zh.md` to reflect the latest architecture, current maturity, and new v0.4.2 capabilities.

## [0.4.1] — P3 Big Data, Caching & Security Hardening

### Added

- **Big-result DataStore** (`backend/homomics_lab/data/data_store.py`)
  - Automatically offloads large results to files: `DataFrame` → Parquet, `AnnData` → H5AD, non-JSON objects → pickle, large JSON → file.
  - Returns a serializable `ResultReference` so small results stay inline while big results stay out of API JSON payloads.
  - Integrated into `SkillRuntimeExecutor.execute()` so every skill result is stored optimally.

- **Skill Result Cache / Memoization** (`backend/homomics_lab/skills/cache.py`)
  - Disk-based cache keyed by stable SHA-256 of `skill_id + inputs + fingerprint`.
  - Checked before execution and populated after successful deterministic skill runs.
  - Supports invalidation, clearing, and corrupted-cache recovery.

- **Optional Dense Semantic Search**
  - `backend/homomics_lab/skills/semantic_search_v2.py` adds sentence-transformers embeddings.
  - Activated by setting `HOMOMICS_SEMANTIC_SEARCH_MODEL` (e.g. `all-MiniLM-L6-v2`); falls back to TF-IDF when unset.

- **Tool Risk Levels & Approval Flow**
  - `ToolDefinition` now carries `risk_level: low | medium | high`.
  - Builtin tools marked: `shell_exec`, `file_write`, `file_edit` → high; `file_read`, `file_list` → medium.
  - New `HOMOMICS_INTERACTIVE_MODE=true` requires explicit approval before high-risk tool calls.
  - New endpoints: `GET /api/skills/tools/pending`, `POST /api/skills/approve-tool/{call_id}`, `POST /api/skills/reject-tool/{call_id}`.

- **ReproducibilityEngine Integration**
  - `BackgroundJobRunner` now starts a reproducibility analysis, records the task tree plan, and finalizes the bundle on job completion/failure.
  - Bundles are saved to the workspace and indexed into CBKB when available.

- **Finer-Grained Execution Traces**
  - `BackgroundJobRunner` passes `trace_id` through `TurnRunner` to `Orchestrator`.
  - `Orchestrator` writes per-task phase nodes into `TraceStore`, capturing inputs, outputs, and error state.

- **Tests**
  - `backend/tests/test_data_store.py` — 9 tests covering inline, Parquet, H5AD, pickle fallback, and large-object offloading.
  - `backend/tests/test_skills/test_cache.py` — 10 tests covering cache hit/miss, key stability, fingerprint isolation, and corrupted entries.
  - `backend/tests/test_tools/test_approval.py` — 3 tests covering interactive-mode approval for high-risk tools.

### Fixed

- **Docker build** (`Dockerfile`)
  - Corrected broken `COPY backend/pyproject.toml` path; now uses root `pyproject.toml` + `uv.lock`.
  - Switched to multi-stage build with locked dependency export and non-root user.
  - Added healthcheck and production-ready defaults.

- **CI workflow** (`.github/workflows/ci.yml`)
  - Fixed install path (repo root instead of `cd backend`).
  - Added ruff lint, mypy type-check, pytest-cov coverage, and Docker smoke-test jobs.

- **Skill trust bypass**
  - `SkillStore.import_skill()` now normalizes non-builtin sources to `imported` in `metadata["source"]` so runtime trust checks reliably reject untrusted external skills.

- **Runtime `UnboundLocalError`**
  - Initialized `result`, `success`, and `error_msg` before the try/except in `SkillRuntimeExecutor.execute()`.

- **Category inference from SKILL.md frontmatter**
  - `SkillLoader` now honors an explicit `category` field in SKILL.md frontmatter instead of always falling back to keyword/name inference.

- **Test baseline**
  - Replaced stale builtin-skill tests with meta-capability skill tests.
  - Added global test fixture to force sandbox backend to `local`, preventing Docker/WSL misconfiguration failures.
  - Increased API integration test polling timeouts (`tests/test_api/*.py`) from 5 s to 30 s so real skill execution has time to reach HITL/completed/failed states.

- **CBKB ingestion timezone bug**
  - `BackgroundJobRunner._ingest_to_cbkb()` now normalizes naive/aware datetimes before computing job duration, preventing `TypeError: can't subtract offset-naive and offset-aware datetimes`.

- **Python 3.11 / 3.10 compatibility**
  - Replaced `Path.walk()` with `os.walk()` in `WorkspaceManager.snapshot()` and `restore()`; `Path.walk()` is only available in Python 3.12+.

- **VersionLocker without pip**
  - `_capture_pip_freeze()` now uses `importlib.metadata.distributions()` so environment locks work in uv-managed venvs that do not ship `pip`.

### Changed

- Bumped `__version__` from `0.1.0-mvp` to `0.4.1` to align with documented release.
- `pyproject.toml` test optional-dependencies now include `fakeredis` and `pytest-cov`.
- Added core runtime dependencies: `pyarrow` (DataStore Parquet offload), `sentence-transformers` (dense semantic search / memory), `weasyprint` (PDF report export), and `sqlite-vec` (vector memory).
