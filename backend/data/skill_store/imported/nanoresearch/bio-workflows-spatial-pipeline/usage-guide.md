# Spatial Transcriptomics Pipeline - Usage Guide

## Overview

This is a **workflow orchestrator** that defines the standard spatial transcriptomics analysis pipeline from raw Visium/Xenium data to spatial domains and downstream analyses. It provides minimal runnable code for each step and delegates to specialized sub-skills for advanced parameters, method comparisons, and troubleshooting.

**Languages:** Python (Squidpy/Scanpy) or R (Seurat)
**Workflow:** true
**Type:** Orchestrator (delegates implementation to sub-skills)

## When to Use This Skill

Use this skill when the user says:
- "Analyze my Visium spatial transcriptomics data"
- "Run the spatial transcriptomics pipeline"
- "Find spatially variable genes in my tissue"
- "Identify spatial domains in my sample"
- "Process my Space Ranger output"

## When to Switch to Sub-Skills

| User Request | Switch To |
|-------------|-----------|
| "Which domain detection method?" | [bio-spatial-transcriptomics-domains-stagate](../bio-spatial-transcriptomics-domains-stagate/), [bio-spatial-transcriptomics-domains-bayesspace-r](../bio-spatial-transcriptomics-domains-bayesspace-r/) |
| "Deconvolute my spots" | [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/), [bio-spatial-transcriptomics-deconvolution-rctd-r](../bio-spatial-transcriptomics-deconvolution-rctd-r/) |
| "Cell-cell communication" | [bio-spatial-transcriptomics-communication-commot](../bio-spatial-transcriptomics-communication-commot/), [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/) |
| "Multi-sample integration" | [bio-spatial-transcriptomics-batch-integration](../bio-spatial-transcriptomics-batch-integration/) |
| "Microenvironment analysis" | [bio-spatial-transcriptomics-microenvironment-misty-r](../bio-spatial-transcriptomics-microenvironment-misty-r/) |
| "Non-standard data format" | [bio-spatial-transcriptomics-data-io](../bio-spatial-transcriptomics-data-io/) |

## Prerequisites

```bash
# Core Python packages
pip install scanpy squidpy matplotlib

# Optional: downstream modules
pip install cell2location commot

# R packages for BayesSpace / RCTD / CellChat
R -e "BiocManager::install(c('BayesSpace', 'SPOTlight'))"
```

## Pipeline Steps

| Step | Action | Sub-Skill | State In → State Out |
|------|--------|-----------|---------------------|
| 1 | Load spatial data | data-io | → `[Raw]` + spatial coords |
| 2 | QC + filter | preprocessing | `[Raw]` → `[Filtered]` |
| 3 | Normalize + HVG + cluster | preprocessing | `[Filtered]` → `[Clustered]` |
| 4 | Spatial analysis | neighbors + statistics | `[Clustered]` → `[Spatial-Analyzed]` |
| 5 | Domain detection | domains-* | `[Spatial-Analyzed]` → `[Domains]` |
| 6 | Visualization | preprocessing | `[Domains]` → `[Visualized]` |
| 7 | Deconvolution (optional) | deconvolution-* | → `[Deconvoluted]` |
| 8 | Communication (optional) | communication-* | → `[Communication]` |
| 9 | Microenvironment (optional) | misty-r | → `[Microenv]` |

## Example Prompts

### Full pipeline
> "Analyze my Visium data from start to finish"

> "Run the spatial transcriptomics pipeline on my tissue"

### Specific steps
> "Load my Space Ranger output and show QC"

> "Find spatially variable genes in my sample"

> "Detect spatial domains using STAGATE"

> "Deconvolute my spots with cell2location"

### Multi-sample
> "I have 3 Visium slides, integrate and find shared domains"

> "Compare spatial domains across samples"

## Input Requirements

| Input | Format | Notes |
|-------|--------|-------|
| Space Ranger output | Directory | Standard Visium output |
| Xenium output | Directory | 10x Xenium data |
| AnnData h5ad | `.h5ad` | Can start mid-pipeline |
| Seurat RDS | `.rds` | Can start mid-pipeline |

For GEO format (h5 + spatial.tar.gz), see [bio-spatial-transcriptomics-data-io](../bio-spatial-transcriptomics-data-io/).

## Expected Outputs

| File | Description |
|------|-------------|
| `spatial_analyzed.h5ad` / `spatial_seurat.rds` | Full analyzed object |
| `clusters.pdf` | Clusters overlaid on tissue |
| `domains.pdf` | Spatial domains on tissue |
| `nhood_enrichment.pdf` | Neighborhood enrichment heatmap |
| `co_occurrence.pdf` | Cluster co-occurrence patterns |

## Tips

- **Neighbor count**: 6 for standard Visium (hex grid); 10-15 for high-resolution
- **Resolution**: Lower (0.2-0.3) for broad domains; higher (0.5-1.0) for subtypes
- **SVGs**: Check top Moran's I genes for expected tissue markers
- **Artifacts**: Filter edge/fold spots before clustering to avoid artifact-driven clusters
- **Deconvolution**: Ensure reference scRNA-seq matches tissue type
- **Memory**: Xenium datasets can be very large; use subsetting or backed mode
