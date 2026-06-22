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
outputs:
  provenance:
    type: object
    description: Structured provenance record.
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

## Outputs

- `provenance` - Provenance record.
