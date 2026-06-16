---
name: plot_umap
description: Generate a UMAP visualization of single-cell data.
tool_type: python
primary_tool: scanpy
supported_tools: [scanpy, anndata, matplotlib]
keywords: ["single-cell", "visualization", "umap", "plot"]
category: single-cell
version: 1.0.0
author: HomomicsLab
license: MIT
inputs:
  adata_path:
    type: string
    description: Path to .h5ad file with embeddings and clusters.
    required: true
  color:
    type: string
    description: Metadata column to color cells by.
    default: leiden
outputs:
  output_path:
    type: string
    description: Path to generated UMAP plot.
---

# Plot UMAP

Generate a UMAP visualization of single-cell data.

## Parameters

- `adata_path` (required) - Path to .h5ad file.
- `color` - Metadata column to color by (default: leiden).

## Outputs

- `output_path` - Path to generated plot.
