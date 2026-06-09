---
name: scanpy-qc
description: Perform QC filtering on single-cell data using scanpy best practices
tool_type: python
primary_tool: scanpy
supported_tools: ["scanpy", "anndata"]
keywords: ["qc", "quality control", "filter", "single-cell"]
category: single-cell
multi_sample: false
---

# Scanpy Quality Control

Filter low-quality cells and genes following scanpy best practices.

## When to Use

- User wants QC before downstream analysis
- Need to filter by n_genes, n_counts, or MT%

## Parameters

- `adata_path` (required) - Path to input .h5ad file
- `min_genes` - Minimum genes per cell (default: 200)
- `min_cells` - Minimum cells per gene (default: 3)
- `mt_threshold` - Mitochondrial % threshold (default: 0.05)

## Outputs

- `input_cells` - Cell count before filtering
- `output_cells` - Cell count after filtering
- `output_path` - Path to filtered .h5ad
