# Signac Usage Guide

## Overview

Signac is a comprehensive toolkit for single-cell ATAC-seq data analysis that extends Seurat to handle chromatin accessibility data. It provides tools for quality control, normalization, dimensionality reduction, visualization, and integration with single-cell RNA-seq.

## When to Use

- **scATAC-seq analysis**: Standard analysis of chromatin accessibility
- **Integration with scRNA-seq**: When you have matching RNA data
- **Gene activity prediction**: Infer gene expression from chromatin
- **Peak calling**: Call cell-type-specific peaks
- **Visualization**: Coverage tracks and browser-style plots

## Quick Start

### Minimal Example

```r
library(Signac)
library(Seurat)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Create object
seurat_obj <- create_signac_object(
  counts_file = "filtered_peak_bc_matrix.h5",
  fragments_file = "fragments.tsv.gz",
  genome = "hg38"
)

# QC
seurat_obj <- compute_qc_metrics(seurat_obj)
seurat_obj <- filter_cells_signac(seurat_obj)

# Run workflow
seurat_obj <- run_signac_workflow(seurat_obj)

# Visualize
DimPlot(seurat_obj, reduction = "umap", label = TRUE)
```

## Step-by-Step Workflow

### 1. Load Data

```r
library(Signac)
library(Seurat)

# Load from 10x output
seurat_obj <- create_signac_object(
  counts_file = "filtered_peak_bc_matrix.h5",
  fragments_file = "fragments.tsv.gz",
  metadata_file = "singlecell.csv",  # Optional
  genome = "hg38",
  min_cells = 10,
  min_features = 200
)

# View object
seurat_obj
```

**Input Formats:**
- Counts: HDF5 (from Cell Ranger) or MatrixMarket
- Fragments: Tabix-indexed .tsv.gz file
- Metadata: CSV with cell barcodes as rownames

### 2. Quality Control

```r
# Compute QC metrics
seurat_obj <- compute_qc_metrics(
  seurat_obj,
  compute_nucleosome = TRUE,
  compute_tss = TRUE
)

# Add blacklist ratio
seurat_obj <- add_blacklist_ratio(seurat_obj)

# Visualize QC
plot_qc_metrics(seurat_obj)

# View QC summary
get_qc_summary(seurat_obj)
```

**Understanding QC Metrics:**

| Metric | Good | Poor | Interpretation |
|--------|------|------|----------------|
| nCount_peaks | 1000-20000 | <500 or >50000 | Library size |
| TSS.enrichment | >4 | <2 | Signal-to-noise |
| nucleosome_signal | <4 | >10 | Fragment distribution |
| pct_reads_in_peaks | >40% | <15% | Enrichment efficiency |
| blacklist_ratio | <0.05 | >0.1 | Artifact contamination |

### 3. Filter Cells

```r
# Filter by QC
seurat_obj <- filter_cells_signac(
  seurat_obj,
  min_counts = 1000,
  max_counts = 20000,
  min_tss = 2,
  max_ns = 4,
  min_rip = 15,
  max_bl = 0.05
)
```

**Filtering Strategy:**
1. Start with lenient thresholds
2. Visualize distributions
3. Adjust based on data quality
4. Check cell type representation after filtering

### 4. Normalization and Dimensionality Reduction

```r
# TF-IDF normalization
seurat_obj <- run_tfidf(seurat_obj, method = 1)

# Find variable features
seurat_obj <- find_top_features(seurat_obj, min_cutoff = "q0")

# LSI dimensionality reduction
seurat_obj <- run_lsi(seurat_obj, dims = 50)
```

**TF-IDF Methods:**
- Method 1: Standard (recommended)
- Method 2: Log-TF
- Method 3: Term frequency only

### 5. Clustering and UMAP

```r
# Clustering
seurat_obj <- FindNeighbors(seurat_obj, reduction = "lsi", dims = 2:30)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.8)

# UMAP
seurat_obj <- RunUMAP(seurat_obj, reduction = "lsi", dims = 2:30)

# Plot
DimPlot(seurat_obj, reduction = "umap", label = TRUE)
```

**LSI Components:**
- Always skip the first component (LSI_1) - captures sequencing depth
- Use 2:30 for standard datasets
- Use 2:50 for large/complex datasets

### 6. Gene Activity Scores

```r
# Create gene activity matrix
seurat_obj <- create_gene_activity(
  seurat_obj,
  extend_upstream = 2000,
  extend_downstream = 0
)

# Visualize marker genes
markers <- create_marker_list(tissue = "pbmc")
plot_gene_activity_umap(seurat_obj, genes = unlist(markers)[1:6])
```

### 7. Peak Calling

```r
# Requires MACS2
if (check_macs2()) {
  seurat_obj <- call_peaks_signac(
    seurat_obj,
    group_by = "seurat_clusters",
    macs2_path = "macs2"
  )
}
```

### 8. Visualization

```r
# Coverage tracks
plot_coverage_track(
  seurat_obj,
  region = "chr14:106772282-106827066",  # IGH locus
  group_by = "seurat_clusters"
)

# TSS profile
plot_tss_profile(seurat_obj)

# Fragment distribution
plot_fragment_distribution(seurat_obj)
```

## AI Agent Test Cases

### Basic Usage

> "Run Signac QC on my scATAC-seq data"

```r
seurat_obj <- compute_qc_metrics(seurat_obj)
plot_qc_metrics(seurat_obj)
```

> "Analyze scATAC-seq data using Signac"

```r
seurat_obj <- run_signac_workflow(seurat_obj)
```

### Analysis

> "Cluster scATAC-seq cells with Signac"

```r
seurat_obj <- run_lsi(seurat_obj)
seurat_obj <- FindNeighbors(seurat_obj, reduction = "lsi", dims = 2:30)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.8)
```

> "Create gene activity matrix in Signac"

```r
seurat_obj <- create_gene_activity(seurat_obj)
```

### Advanced

> "Integrate scATAC with scRNA using Signac"

```r
# Create gene activity first
seurat_obj <- create_gene_activity(seurat_obj)

# Find anchors
anchors <- FindTransferAnchors(
  reference = seRNA,
  query = seurat_obj,
  reference.assay = "RNA",
  query.assay = "RNA"
)
```

> "Plot coverage track in Signac"

```r
plot_coverage_track(seurat_obj, region = "MS4A1", group_by = "seurat_clusters")
```

## Interpretation

### QC Metrics

**Nucleosome Signal:**
- < 1.5: Nucleosome-free (good)
- 1.5-4: Mixed (acceptable)
- > 4: Nucleosomal (poor)

**TSS Enrichment:**
- > 6: High quality
- 4-6: Good
- 2-4: Acceptable
- < 2: Poor

**Fragment Length Distribution:**
- Peak at ~50-100 bp: Nucleosome-free
- Peak at ~200 bp: Mononucleosome
- Peaks at ~400, 600 bp: Di-, tri-nucleosomes

### Clustering Resolution

| Resolution | Result |
|------------|--------|
| 0.4-0.6 | Major lineages |
| 0.8-1.2 | Cell types |
| 1.5-2.0 | Subtypes |

## Best Practices

### Before Analysis

1. **Check fragment file**: Ensure tabix index exists
2. **Set genome**: Match genome to your reference
3. **Prepare metadata**: Sample info for batch correction

### During Analysis

1. **QC first**: Review metrics before filtering
2. **Skip LSI_1**: Always exclude first component
3. **Visualize**: Check intermediate results
4. **Iterate**: Adjust thresholds based on results

### After Analysis

1. **Annotate**: Use gene activity for cell type ID
2. **Validate**: Check marker genes
3. **Export**: Save results and metadata
4. **Document**: Record parameters used

## Troubleshooting

### Common Issues

**"Fragments file not found"**
→ Check file path
→ Ensure .tbi index exists
→ Verify file is tabix-compressed

**"Out of memory"**
→ Reduce dataset size: `seurat_obj[, sample_cells]`
→ Process in chunks
→ Use `gc()` to free memory

**"MACS2 not found"**
→ Install: `pip install MACS2`
→ Check path: `which macs2`

**"No TSS enrichment computed"**
→ Requires gene annotation
→ Install: `BiocManager::install("EnsDb.Hsapiens.v86")`

## References

1. Stuart et al. (2021). Single-cell chromatin state analysis with Signac. *Nature Methods*.
2. Signac documentation: https://stuartlab.org/signac/
