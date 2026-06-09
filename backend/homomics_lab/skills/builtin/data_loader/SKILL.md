---
name: data-loader
description: Load omics data from various formats (10x, h5ad, csv)
tool_type: python
primary_tool: scanpy
supported_tools: ["scanpy", "anndata"]
keywords: ["load", "data", "io", "10x", "h5ad"]
category: data_io
multi_sample: false
---

# Data Loader

Load single-cell or bulk omics data from common formats.

## When to Use

- User wants to load data before analysis
- Input files are in 10x, h5ad, or CSV format

## Parameters

- `path` (required) - Path to input data file
- `format` - Format hint: "auto", "10x", "h5ad", "csv"

## Outputs

- `format` - Detected format
- `shape` - Data dimensions [cells, genes]
- `status` - Load status
