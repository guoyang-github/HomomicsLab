---
name: core_planning
description: Decompose a user request into a structured, executable analysis plan.
tool_type: agent
primary_tool: agent_core
supported_tools: []
keywords: ["agent", "planning", "decomposition", "meta"]
category: agent_core
version: 0.1.0
author: HomomicsLab
license: MIT
inputs:
  request:
    type: string
    description: Natural-language analysis request from the user.
    required: true
  context:
    type: object
    description: Optional conversation context, data state, or prior plan.
  constraints:
    type: array
    description: Optional list of constraints (e.g., runtime, tools, budget).
outputs:
  plan:
    type: object
    description: Structured plan with goals, phases, and selected skills.
  reasoning:
    type: string
    description: Brief explanation of why the plan was chosen.
---

# Core Planning

Decompose a user request into a structured, executable analysis plan.

## When to Use

- The user asks for a multi-step bioinformatics analysis.
- No existing single skill directly solves the request.
- The agent needs to decide which skills to invoke and in what order.

## Parameters

- `request` (required) - Natural-language analysis request.
- `context` - Optional context object.
- `constraints` - Optional list of constraints.

## Outputs

- `plan` - Structured plan.
- `reasoning` - Explanation of planning decisions.
