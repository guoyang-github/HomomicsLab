# Spatial Transcriptomics Preprocessing - Usage Guide

## Overview

This skill covers quality control, filtering, normalization, clustering, and spatial visualization for 10x Visium spatial transcriptomics data using both Seurat (R) and Scanpy/Squidpy (Python). These are essential steps before cell type mapping, deconvolution, or advanced spatial analysis.

## Prerequisites

**Python (Scanpy + Squidpy):**
```bash
pip install scanpy squidpy matplotlib
```

**R (Seurat):**
```r
install.packages('Seurat')
```

## Quick Start

Ask your AI agent:

> "Preprocess my Visium spatial data: QC, SCTransform normalization, clustering, and spatial visualization"

> "Merge multiple Visium slices and run joint clustering"

> "Detect spatially variable genes in my spatial transcriptomics data"

## Example Prompts

### Quality Control
> "Calculate spatial QC metrics for my Visium data"

> "Show spatial QC plots (UMI distribution on tissue)"

> "What are good filtering thresholds for this spatial dataset?"

### Filtering
> "Filter spots with low UMI counts and high mitochondrial percentage"

> "Remove spots outside tissue boundaries"

### Normalization
> "Normalize my Visium data with SCTransform"

> "Run log normalization on spatial data"

### Clustering and Visualization
> "Cluster spatial spots and visualize clusters on the tissue image"

> "Show UMAP and spatial plot side by side"

> "Visualize gene expression on the tissue"

### Spatially Variable Features
> "Find spatially variable genes using Moran's I"

> "Show the top spatially variable genes on tissue"

### Multi-Slice Analysis
> "Merge two Visium slices and perform joint clustering"

> "Compare spatial patterns across multiple tissue sections"

## What the Agent Will Do

1. Load Visium spatial data (Space Ranger output)
2. Calculate spatial QC metrics (nCount_Spatial, nFeature_Spatial)
3. Visualize QC distributions (violin plots and spatial maps)
4. Filter low-quality spots by UMI/feature counts and tissue boundaries
5. Normalize counts (SCTransform recommended for spatial data)
6. Run dimensionality reduction (PCA) and clustering
7. Visualize clusters and gene expression on tissue images
8. Detect spatially variable features (Moran's I or mark variogram)

## Tips

- **SCTransform is strongly recommended** for spatial data over standard log normalization, as it better handles the biological variance from varying cell density across tissue
- **Set `return.only.var.genes = FALSE`** in SCTransform (Seurat v5+) to retain all genes for downstream deconvolution
- **QC thresholds are more lenient** than single-cell: spots may contain 0-10 cells, so low UMI spots may still be valid
- **UMI variance is often biological**, reflecting different cell densities across tissue regions (e.g., tumor vs stroma)
- **Seurat v5 spatial coordinates** are stored in the image structure, not directly in `meta.data` — use high-level functions rather than direct slot access
- **Clustering resolution** for spatial data is typically lower than single-cell (broader tissue regions vs fine cell types)
- **Always visualize on tissue** — spatial patterns reveal context that UMAP alone cannot show
- **Use Moran's I** for spatially variable feature detection (faster and more interpretable than mark variogram)
- **When merging slices**, always use `add.cell.ids` to prevent cell name conflicts
