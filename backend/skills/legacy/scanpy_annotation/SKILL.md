---
name: scanpy_annotation
description: Annotate single-cell clusters using marker genes or reference data.
tool_type: python
primary_tool: scanpy
supported_tools: [scanpy, anndata]
keywords: ["single-cell", "annotation", "cell-types", "scanpy"]
category: single-cell
version: 1.0.0
author: HomomicsLab
license: MIT
inputs:
  adata_path:
    type: string
    description: Path to clustered .h5ad file.
    required: true
  method:
    type: string
    description: Annotation method.
    default: markers
outputs:
  output_path:
    type: string
    description: Path to annotated .h5ad file.
---

# Scanpy Annotation

Annotate single-cell clusters using marker genes or reference data.

## Parameters

- `adata_path` (required) - Path to clustered .h5ad file.
- `method` - Annotation method (default: markers).

## Outputs

- `output_path` - Path to annotated .h5ad file.
