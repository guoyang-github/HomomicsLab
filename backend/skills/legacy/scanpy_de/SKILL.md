---
name: scanpy_de
description: Perform differential expression analysis on single-cell clusters.
tool_type: python
primary_tool: scanpy
supported_tools: [scanpy, anndata]
keywords: ["single-cell", "differential-expression", "de", "scanpy"]
category: single-cell
version: 1.0.0
author: HomomicsLab
license: MIT
inputs:
  adata_path:
    type: string
    description: Path to annotated .h5ad file.
    required: true
  groupby:
    type: string
    description: Column to group cells by.
    default: leiden
outputs:
  output_path:
    type: string
    description: Path to DE results CSV.
---

# Scanpy Differential Expression

Perform differential expression analysis on single-cell clusters.

## Parameters

- `adata_path` (required) - Path to annotated .h5ad file.
- `groupby` - Column to group cells by (default: leiden).

## Outputs

- `output_path` - Path to DE results CSV.
