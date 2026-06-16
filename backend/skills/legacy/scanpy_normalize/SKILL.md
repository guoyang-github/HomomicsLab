---
name: scanpy_normalize
description: Normalize single-cell counts (total count + log1p).
tool_type: python
primary_tool: scanpy
supported_tools: [scanpy, anndata]
keywords: ["single-cell", "normalization", "scanpy"]
category: single-cell
version: 1.0.0
author: HomomicsLab
license: MIT
inputs:
  adata_path:
    type: string
    description: Path to input .h5ad file.
    required: true
  target_sum:
    type: number
    description: Target total counts per cell.
    default: 10000
outputs:
  output_path:
    type: string
    description: Path to normalized .h5ad file.
---

# Scanpy Normalize

Normalize single-cell counts following scanpy best practices.

## Parameters

- `adata_path` (required) - Path to input .h5ad file.
- `target_sum` - Target total counts per cell (default: 10000).

## Outputs

- `output_path` - Path to normalized .h5ad file.
