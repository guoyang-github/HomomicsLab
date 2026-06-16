---
name: general-code-assistant
version: 1.0.0
description: Generate Python/R snippets or shell commands for general data processing, filtering, parsing, and visualization.
tool_type: python
primary_tool: python
supported_tools: ["python", "bash"]
keywords: ["code", "script", "python", "filter", "parse", "csv", "general", "utility", "rename", "process"]
category: utility
multi_sample: false
---

# General Code Assistant

Generate short, safe code snippets or shell commands for general data manipulation tasks that do not fit a registered bioinformatics domain.

## When to Use

- User wants a Python/R/bash snippet for file processing, filtering, or renaming.
- No registered domain skill covers the request.
- The request should still be reviewed before any code is executed.

## Parameters

- `request` (required) - Natural language description of what the code should do.
- `language` - Target language: "python" (default), "r", or "bash".
- `context` - Extra context such as file paths, column names, or expected input format.

## Outputs

- `code` - Generated code snippet.
- `explanation` - Human-readable explanation of what the code does.
- `warnings` - Safety warnings, e.g. files that will be modified.
