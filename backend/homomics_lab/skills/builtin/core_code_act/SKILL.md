---
name: core_code_act
description: Generate and execute code actions to fulfill a concrete sub-task.
tool_type: python
primary_tool: agent_core
supported_tools: []
keywords: ["agent", "code", "execution", "codeact", "meta"]
category: agent_core
version: 0.1.0
author: HomomicsLab
license: MIT
code_act: true
inputs:
  task:
    type: string
    description: Concrete sub-task to solve with code.
    required: true
  language:
    type: string
    description: Target language (python, r, bash).
    default: python
  context:
    type: object
    description: Available variables, data paths, and prior outputs.
outputs:
  code:
    type: string
    description: Generated code snippet or script.
  result:
    type: object
    description: Execution result summary.
---

# Core CodeAct

Generate and execute code actions to fulfill a concrete sub-task.

When an LLM is configured, CodeAct retrieves relevant skills from the registry
and uses the LLM to generate production-quality code. In offline or test
environments it falls back to a small set of rule-based templates.

## When to Use

- A plan step requires custom code not covered by an existing skill.
- The agent needs to read, transform, or visualize data on the fly.
- A skill failed and a fallback code patch is required.

## Parameters

- `task` (required) - Concrete sub-task.
- `language` - Target language (python, r, bash).
- `context` - Available variables and paths.

## Outputs

- `code` - Generated code.
- `result` - Execution summary.
