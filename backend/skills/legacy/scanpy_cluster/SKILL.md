---
name: scanpy-cluster
description: Cluster single-cell data with UMAP and Louvain using scanpy
tool_type: python
primary_tool: scanpy
supported_tools: ["scanpy", "anndata", "umap-learn", "louvain"]
keywords: ["cluster", "umap", "louvain", "single-cell"]
category: single-cell
multi_sample: false
---

# Scanpy Clustering

Run UMAP dimensionality reduction and Louvain clustering on single-cell data.

## When to Use

- User wants to cluster cells
- Need UMAP visualization or community detection

## Parameters

- `adata_path` (required) - Path to input .h5ad file
- `n_neighbors` - KNN neighbors (default: 15)
- `resolution` - Louvain resolution (default: 0.8)
- `n_pcs` - Number of PCs to use (default: 30)

## Outputs

- `n_clusters` - Number of clusters found
- `output_path` - Path to clustered .h5ad
