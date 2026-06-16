# ArchR Usage Guide

## Overview

ArchR is a comprehensive R package for analyzing single-cell ATAC-seq (Assay for Transposase-Accessible Chromatin using sequencing) data. It provides scalable workflows for quality control, dimensionality reduction, clustering, peak calling, motif enrichment, and integration with scRNA-seq data.

## When to Use

- **Large-scale scATAC-seq**: Analyzing 10,000+ cells efficiently
- **Peak calling**: Identifying accessible chromatin regions
- **Motif enrichment**: Finding enriched TF binding motifs
- **Cell type annotation**: Using gene activity scores and marker genes
- **Multi-modal integration**: Integrating scATAC-seq with scRNA-seq
- **Trajectory inference**: Analyzing differentiation trajectories

## Quick Start

### Minimal Example

```r
library(ArchR)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Setup
setup_archr(threads = 16, genome = "hg38")

# Create Arrow files
arrow_files <- create_arrow_files(
  input_files = "fragments.tsv.gz",
  sample_names = "Sample1",
  filter_tss = 4,
  filter_frags = 1000
)

# Create project
proj <- create_archr_project(arrow_files)

# Run complete analysis
proj <- add_doublet_scores(proj)
proj <- filter_doublets(proj)
proj <- add_iterative_lsi(proj)
proj <- add_clusters(proj)
proj <- add_umap(proj)

# Visualize
plot_embedding(proj, color_by = "cellColData", name = "Clusters")
```

## Step-by-Step Workflow

### 1. Environment Setup

```r
library(ArchR)

# Set threads
setup_archr(threads = 16, genome = "hg38")

# Check MACS2 for peak calling
check_macs2()

# Get recommendations
recommend_archr_params(
  n_cells = 20000,
  n_samples = 2
)
```

### 2. Prepare Fragment Files

```r
# Validate fragment files
input_files <- c(
  "sample1_fragments.tsv.gz",
  "sample2_fragments.tsv.gz"
)

validation <- validate_fragment_files(input_files)
print(validation)

# Create sample metadata
metadata <- create_sample_metadata(
  input_files,
  pattern = "^([^_]+)"
)
```

### 3. Create Arrow Files

Arrow files are the foundation of ArchR analysis - create them once, use them multiple times.

```r
# Create Arrow files
arrow_files <- create_arrow_files(
  input_files = input_files,
  sample_names = c("Sample1", "Sample2"),
  filter_tss = 4,
  filter_frags = 1000,
  add_tile_mat = TRUE,
  add_gene_score_mat = TRUE
)

# Arrow files are saved in the working directory
print(arrow_files)
```

**Quality Control Considerations:**
- `filter_tss`: TSS enrichment score (4-6 for good quality)
- `filter_frags`: Minimum fragments per cell (1000-5000)
- Stricter filters = fewer but higher quality cells

### 4. Create ArchR Project

```r
# Create project
proj <- create_archr_project(
  arrow_files = arrow_files,
  output_directory = "Save-ArchR",
  copy_arrows = TRUE
)

# Get summary
summary <- get_archr_summary(proj)
print(summary)

# View cell data
cell_data <- getCellColData(proj)
head(cell_data)
```

### 5. Filter Doublets

```r
# Add doublet scores
proj <- add_doublet_scores(
  proj,
  k = 10,
  n_trials = 5
)

# Plot doublet scores (optional)
# plot_embedding(proj, color_by = "cellColData", name = "DoubletScore")

# Filter doublets
proj <- filter_doublets(proj)

# Check remaining cells
print(length(getCellNames(proj)))
```

### 6. Dimensionality Reduction with LSI

```r
# Add iterative LSI
proj <- add_iterative_lsi(
  proj,
  name = "IterativeLSI",
  iterations = 2,
  cluster_params = list(
    resolution = 2,
    sampleCells = 10000
  ),
  var_features = 25000,
  dims_to_use = 1:30
)

# Access LSI dimensions
lsi_dims <- getReducedDims(proj, reducedDims = "IterativeLSI")
```

### 7. Clustering

```r
# Add clusters
proj <- add_clusters(
  proj,
  reduced_dims = "IterativeLSI",
  name = "Clusters",
  resolution = 0.8,
  method = "Seurat"
)

# View cluster distribution
table(proj$Clusters)
```

**Resolution Guidelines:**
- 0.4-0.6: Major cell types
- 0.8-1.2: Cell subtypes (default)
- 1.5+: Fine subpopulations

### 8. UMAP Visualization

```r
# Add UMAP
proj <- add_umap(
  proj,
  reduced_dims = "IterativeLSI",
  n_neighbors = 40,
  min_dist = 0.4
)

# Visualize clusters
plot_embedding(
  proj,
  embedding = "UMAP",
  color_by = "cellColData",
  name = "Clusters",
  size = 0.5
)

# Visualize by sample
plot_embedding(
  proj,
  color_by = "cellColData",
  name = "Sample"
)
```

### 9. Gene Score Visualization

```r
# Get marker gene list
markers <- create_marker_list(
  cell_types = c("T_cell", "B_cell", "Monocyte"),
  tissue = "pbmc"
)

# Plot gene scores
gene_plots <- plot_gene_scores(
  proj,
  genes = unlist(markers),
  embedding = "UMAP",
  impute = TRUE
)

# Arrange plots
cowplot::plot_grid(plotlist = gene_plots[1:6], ncol = 3)
```

### 10. Peak Calling

```r
# Check MACS2
if (check_macs2()) {
  # Add reproducible peak set
  proj <- add_reproducible_peak_set(
    proj,
    group_by = "Clusters",
    reproducibility = "2",
    path_to_macs2 = "macs2"
  )

  # Add peak matrix
  proj <- add_peak_matrix(proj)

  # View peaks
  peaks <- getPeakSet(proj)
  print(length(peaks))
}
```

### 11. Motif and Deviation Analysis

```r
# Add motif annotations
proj <- add_motif_annotations(
  proj,
  motif_set = "cisbp",
  anno_name = "Motif"
)

# Add deviations matrix
proj <- add_deviations_matrix(
  proj,
  peak_annotation = "Motif"
)

# Visualize motif deviations
plot_embedding(
  proj,
  color_by = "MotifMatrix",
  name = "GATA1",
  embedding = "UMAP"
)
```

### 12. Integration with scRNA-seq

```r
# Load scRNA data
seRNA <- readRDS("scRNA_data.rds")

# Add integration matrix
proj <- addGeneIntegrationMatrix(
  ArchRProj = proj,
  seRNA = seRNA,
  groupATAC = "Clusters",
  groupRNA = "seurat_clusters"
)

# Transfer labels
proj$predictedCellType <- proj$predictedGroup_Un

# Plot predictions
plot_embedding(
  proj,
  color_by = "cellColData",
  name = "predictedCellType"
)
```

### 13. Save and Export

```r
# Save project
proj <- save_archr_project(proj)

# Export metadata
export_cell_metadata(proj, "cell_metadata.tsv")

# Create report
report <- create_archr_report(proj)
cat(report)
```

## AI Agent Test Cases

### Basic Usage

> "Run ArchR analysis on scATAC-seq data"

```r
proj <- run_archr_workflow(
  input_files = "fragments.tsv.gz",
  output_directory = "ArchR-Output",
  genome = "hg38"
)
```

> "Create ArchR project from fragment files"

```r
arrow_files <- create_arrow_files(input_files)
proj <- create_archr_project(arrow_files)
```

### Analysis

> "Cluster scATAC-seq cells with ArchR"

```r
proj <- add_iterative_lsi(proj)
proj <- add_clusters(proj, resolution = 0.8)
```

> "Call peaks using ArchR"

```r
proj <- add_reproducible_peak_set(proj, group_by = "Clusters")
proj <- add_peak_matrix(proj)
```

### Visualization

> "Plot UMAP from ArchR project"

```r
plot_embedding(proj, embedding = "UMAP", color_by = "cellColData", name = "Clusters")
```

> "Visualize gene activity scores"

```r
plot_gene_scores(proj, genes = c("CD34", "GATA1"))
```

### Advanced

> "Integrate scATAC with scRNA using ArchR"

```r
proj <- addGeneIntegrationMatrix(proj, seRNA = seurat_obj)
```

> "Run motif enrichment in ArchR"

```r
proj <- add_motif_annotations(proj, motif_set = "cisbp")
proj <- add_deviations_matrix(proj)
```

## Interpretation

### Quality Metrics

| Metric | Good | Poor |
|--------|------|------|
| TSS Enrichment | > 6 | < 4 |
| nFrags | > 1000 | < 500 |
| Blacklist Ratio | < 0.05 | > 0.1 |

### Cluster Resolution

| Resolution | Use Case |
|------------|----------|
| 0.4-0.6 | Broad cell lineages |
| 0.8-1.2 | Cell types (default) |
| 1.5+ | Fine subtypes |

### Gene Scores

- High score: Accessible promoter/regulatory regions
- Low score: Closed chromatin
- Compare across clusters for marker identification

## Best Practices

### Before Analysis

1. **Check fragment files**: Ensure proper format and compression
2. **Set appropriate threads**: Balance speed and memory
3. **Install MACS2**: Required for peak calling
4. **Prepare gene annotations**: Match genome version

### During Analysis

1. **QC first**: Review TSS enrichment and fragment counts
2. **Iterative LSI**: Use 2-3 iterations for best results
3. **Doublet removal**: Always filter before clustering
4. **Save frequently**: Use `saveArchRProject()` after major steps

### After Analysis

1. **Validate clusters**: Check marker gene expression
2. **Peak QC**: Check reproducibility across samples
3. **Document parameters**: Save analysis parameters
4. **Export results**: Save metadata and matrices

## Troubleshooting

### Arrow Creation Fails

```
Error: Fragment file is not properly formatted
```

**Solution:**
- Check file is gzipped: `file.tsv.gz`
- Verify tab-delimited format
- Ensure 5 columns: chr, start, end, barcode, count
- Check files are sorted by position

### Memory Issues

```
Error: Cannot allocate vector of size X Gb
```

**Solution:**
- Reduce threads: `addArchRThreads(4)`
- Process samples individually, then merge
- Use `subsetArchRProject()` for large projects

### MACS2 Not Found

```
Error: MACS2 not found in PATH
```

**Solution:**
```bash
pip install MACS2
# Or provide full path
path_to_macs2 = "/usr/local/bin/macs2"
```

### Slow Performance

**Solution:**
- Increase thread count
- Use SSD for temporary files
- Filter to high-quality cells first
- Sample cells for initial exploration

## References

1. Granja et al. (2021). ArchR is a scalable software package for integrative single-cell chromatin accessibility analysis. *Nature Genetics*.
2. ArchR documentation: https://www.archrproject.com/
