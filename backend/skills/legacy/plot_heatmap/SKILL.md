---
name: plot_heatmap
description: Generate a heatmap of marker gene expression.
tool_type: python
primary_tool: scanpy
supported_tools: [scanpy, anndata, matplotlib]
keywords: ["single-cell", "visualization", "heatmap", "plot"]
category: single-cell
version: 1.0.0
author: HomomicsLab
license: MIT
inputs:
  adata_path:
    type: string
    description: Path to .h5ad file.
    required: true
  markers:
    type: array
    description: List of marker genes to plot.
outputs:
  output_path:
    type: string
    description: Path to generated heatmap.
---

# Plot Heatmap

Generate a heatmap of marker gene expression.

## Parameters

- `adata_path` (required) - Path to .h5ad file.
- `markers` - List of marker genes to plot.

## Outputs

- `output_path` - Path to generated heatmap.
