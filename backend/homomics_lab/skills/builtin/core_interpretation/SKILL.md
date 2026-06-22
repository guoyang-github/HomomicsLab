---
name: core_interpretation
description: Interpret analysis outputs and generate human-readable explanations.
tool_type: agent
primary_tool: agent_core
supported_tools: []
keywords: ["agent", "interpretation", "explanation", "meta"]
category: agent_core
version: 0.1.0
author: HomomicsLab
license: MIT
inputs:
  outputs:
    type: object
    description: Structured outputs from one or more skills.
    required: true
  question:
    type: string
    description: Specific question the user wants answered.
  audience:
    type: string
    description: Target audience (expert, biologist, clinician).
    default: biologist
outputs:
  summary:
    type: string
    description: Interpretation summary.
  key_findings:
    type: array
    description: List of key findings.
---

# Core Interpretation

Interpret analysis outputs and generate human-readable explanations.

## When to Use

- A skill produced results that need explanation.
- The user asks "what does this mean?" or "what should I do next?".
- The agent needs to translate technical outputs for a non-expert audience.

## Parameters

- `outputs` (required) - Skill outputs.
- `question` - Specific question.
- `audience` - Target audience.

## Outputs

- `summary` - Human-readable summary.
- `key_findings` - Key findings.
