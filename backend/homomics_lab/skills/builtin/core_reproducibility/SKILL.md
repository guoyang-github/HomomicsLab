---
name: core_reproducibility
description: Capture provenance and generate reproducibility records for executed skills.
tool_type: agent
primary_tool: agent_core
supported_tools: []
keywords: ["agent", "reproducibility", "provenance", "meta"]
category: agent_core
version: 0.1.0
author: HomomicsLab
license: MIT
inputs:
  execution_log:
    type: object
    description: Log of skill executions (skill_id, inputs, outputs, runtime).
    required: true
  artifacts:
    type: array
    description: List of output artifact paths.
  workspace_dir:
    type: string
    description: Project workspace used to locate finalized reproducibility bundles (.metadata/reproducibility_bundle*.json). Defaults to the current directory.
outputs:
  provenance:
    type: object
    description: Structured provenance record (steps, artifact checksums, environment snapshot, known reproducibility bundles).
---

# Core Reproducibility

Capture provenance and generate reproducibility records for executed skills.

## When to Use

- After a pipeline completes and a reproducibility report is needed.
- Before sharing results with collaborators.
- When registering an execution in the SkillDAG.

## Parameters

- `execution_log` (required) - Execution log.
- `artifacts` - Output artifact paths.
- `workspace_dir` - Project workspace to scan for finalized reproducibility bundles (default: current directory).

## Outputs

- `provenance` - Provenance record with:
  - `steps` - skill executions from the execution log.
  - `artifacts` - each artifact with SHA-256 checksum, size, and MIME type (same shape as `provenance.recorder.FileRecord`).
  - `environment` - runtime snapshot (Python version, platform, installed packages, content hash) captured via `provenance.env_snapshot`.
  - `reproducibility_bundles` - summaries of the bundle manifests the job runner has already finalized under `.metadata/reproducibility_bundle*.json` (project, skills, phases, code snippets, HITL decisions).

## Notes

- The authoritative `ReproducibilityBundle` for the current job is created and finalized by the job runner (`jobs/runner.py` + `reproducibility/engine.py`) after the job ends. This skill does not replace it: it captures step-level provenance on demand and reports the bundles that already exist in the workspace.
- `scripts/python/run.py` is the reference implementation: it calls the real `homomics_lab.provenance` helpers when the package is importable and falls back to identical stdlib logic inside a sandbox. It never writes to the workspace.
