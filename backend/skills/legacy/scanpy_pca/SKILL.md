---
name: scanpy_pca
description: Run PCA dimensionality reduction on single-cell data.
tool_type: python
primary_tool: scanpy
supported_tools: [scanpy, anndata]
keywords: ["single-cell", "pca", "dimensionality-reduction", "scanpy"]
category: single-cell
version: 1.0.0
author: HomomicsLab
license: MIT
inputs:
  adata_path:
    type: string
    description: Path to input .h5ad file.
    required: true
  n_comps:
    type: number
    description: Number of principal components.
    default: 50
outputs:
  output_path:
    type: string
    description: Path to .h5ad with PCA embeddings.
---

# Scanpy PCA

Run PCA dimensionality reduction on single-cell data.

## Parameters

- `adata_path` (required) - Path to input .h5ad file.
- `n_comps` - Number of PCs (default: 50).

## Outputs

- `output_path` - Path to .h5ad with PCA embeddings.
