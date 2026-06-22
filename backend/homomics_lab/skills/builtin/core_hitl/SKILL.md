---
name: core_hitl
description: Manage human-in-the-loop checkpoints and clarifications.
tool_type: agent
primary_tool: agent_core
supported_tools: []
keywords: ["agent", "hitl", "human-in-the-loop", "clarification", "meta"]
category: agent_core
version: 0.1.0
author: HomomicsLab
license: MIT
inputs:
  checkpoint_type:
    type: string
    description: Type of checkpoint (clarification, approval, choice, warning).
    required: true
  message:
    type: string
    description: Message presented to the human.
    required: true
  options:
    type: array
    description: Options for choice checkpoints.
  payload:
    type: object
    description: Optional data associated with the checkpoint.
outputs:
  resolution:
    type: object
    description: Human resolution (choice, text, approved flag).
---

# Core HITL

Manage human-in-the-loop checkpoints and clarifications.

## When to Use

- The agent needs user approval before an irreversible action.
- A parameter is ambiguous and needs clarification.
- A warning or conflict requires human decision.

## Parameters

- `checkpoint_type` (required) - Type of checkpoint.
- `message` (required) - Human-readable message.
- `options` - Options for choice checkpoints.
- `payload` - Associated data.

## Outputs

- `resolution` - Human resolution.
