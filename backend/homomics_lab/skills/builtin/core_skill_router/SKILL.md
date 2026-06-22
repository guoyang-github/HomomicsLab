---
name: core_skill_router
description: Select the most appropriate skill(s) for a given task and data state.
tool_type: agent
primary_tool: agent_core
supported_tools: []
keywords: ["agent", "routing", "skill-selection", "meta"]
category: agent_core
version: 0.1.0
author: HomomicsLab
license: MIT
inputs:
  task:
    type: string
    description: Task description.
    required: true
  candidates:
    type: array
    description: List of candidate skill IDs or skill metadata objects.
  data_state:
    type: object
    description: Current data state (artifacts, schema, observations).
outputs:
  selected_skills:
    type: array
    description: Ordered list of recommended skill IDs.
  rationale:
    type: string
    description: Why these skills were selected.
---

# Core Skill Router

Select the most appropriate skill(s) for a given task and data state.

## When to Use

- Multiple skills could solve a task.
- The planner needs skill recommendations based on data compatibility.
- A skill failed and an alternative is needed.

## Parameters

- `task` (required) - Task description.
- `candidates` - Candidate skills.
- `data_state` - Current data state.

## Outputs

- `selected_skills` - Recommended skill IDs.
- `rationale` - Selection rationale.
