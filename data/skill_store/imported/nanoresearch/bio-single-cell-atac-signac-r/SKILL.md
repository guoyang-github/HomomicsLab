---
name: bio-single-cell-atac-signac-r
description: Single-cell ATAC-seq analysis using Signac. Quality control, normalization, dimensionality reduction, peak calling, and integration with scRNA-seq within the Seurat framework.
tool_type: r
primary_tool: Signac
supported_tools: [Seurat, MACS2, AnnotationHub, GenomeInfoDb]
languages: [r]
keywords: ["single-cell", "ATAC", "Signac", "Seurat", "chromatin", "accessibility", "peaks", "LSI", "R"]
---

## Version Compatibility

- **R**: >= 4.2.0
- **Signac**: >= 1.10.0
- **Seurat**: >= 4.3.0
- **Bioconductor**: >= 3.17

## Installation

```r
# Install Bioconductor dependencies
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("Signac")

# Optional: Install annotation packages
BiocManager::install(c("EnsDb.Hsapiens.v86", "BSgenome.Hsapiens.UCSC.hg38"))

# Optional: Install MACS2 for peak calling
# pip install MACS2
```

## Import Wrapper Functions

Source the wrapper scripts before using:

```r
# Core analysis functions
source("scripts/r/core_analysis.R")

# Visualization functions
source("scripts/r/visualization.R")

# Utility functions
source("scripts/r/utils.R")
```

## Core Analysis Workflow

Signac extends Seurat to handle single-cell ATAC-seq data, providing tools for quality control, normalization, dimensionality reduction, and integration with scRNA-seq.

### Step 1: Create Seurat Object

Create a Seurat object with ChromatinAssay from 10x Genomics output.

```r
# From 10x HDF5 and fragments
seurat_obj <- create_signac_object(
  counts_file = "filtered_peak_bc_matrix.h5",
  fragments_file = "fragments.tsv.gz",
  metadata_file = "singlecell.csv",  # Optional
  sep = c(":", "-"),
  genome = "hg38",
  min_cells = 10,
  min_features = 200
)
```

**Input Files:**
- `counts_file`: HDF5 file from Cell Ranger or MatrixMarket format
- `fragments_file`: Tabix-indexed fragments.tsv.gz file
- `metadata_file`: CSV with cell metadata (optional)

### Step 2: Compute QC Metrics

Compute nucleosome signal and TSS enrichment.

```r
# Compute QC metrics
seurat_obj <- compute_qc_metrics(
  seurat_obj,
  assay = "peaks",
  compute_nucleosome = TRUE,
  compute_tss = TRUE,
  tss_fast = TRUE
)

# Add blacklist ratio
seurat_obj <- add_blacklist_ratio(
  seurat_obj,
  blacklist = "hg38-blacklist.v2.bed"
)

# View QC summary
qc_summary <- get_qc_summary(seurat_obj)
print(qc_summary)
```

**QC Metrics:**
- `nucleosome_signal`: Ratio of mononucleosomal to nucleosome-free fragments
- `TSS.enrichment`: Transcription start site enrichment score
- `pct_reads_in_peaks`: Percentage of reads in peaks
- `blacklist_ratio`: Fraction of reads in blacklist regions

### Step 3: Filter Cells

Filter cells based on QC thresholds.

```r
# Filter cells
seurat_obj <- filter_cells_signac(
  seurat_obj,
  min_counts = 1000,
  max_counts = NULL,
  min_tss = 2,
  max_ns = 4,
  min_rip = 15,
  max_bl = 0.05
)
```

**Recommended Thresholds:**
- `min_counts`: 1000-3000
- `max_counts`: 20000-50000 (removes doublets)
- `min_tss`: 2-4
- `max_ns`: 2-4
- `min_rip`: 15-40%
- `max_bl`: 0.05

### Step 4: TF-IDF Normalization

Run term frequency-inverse document frequency normalization.

```r
# TF-IDF normalization
seurat_obj <- run_tfidf(
  seurat_obj,
  assay = "peaks",
  method = 1,              # 1, 2, or 3
  scale_factor = 10000
)
```

**TF-IDF Methods:**
- Method 1: Standard TF-IDF (default)
- Method 2: Log-TF with IDF
- Method 3: Term frequency only

### Step 5: Feature Selection

Identify most accessible features.

```r
# Find top features
seurat_obj <- find_top_features(
  seurat_obj,
  assay = "peaks",
  min_cutoff = "q0",       # "qX" for quantile or numeric
  n_features = NULL        # Optional limit
)
```

### Step 6: Dimensionality Reduction (LSI)

Run SVD-based dimensionality reduction (Latent Semantic Indexing).

```r
# Run LSI
seurat_obj <- run_lsi(
  seurat_obj,
  assay = "peaks",
  reduction_name = "lsi",
  dims = 50,
  features = NULL          # Use VariableFeatures if NULL
)
```

**Key Points:**
- Skip the first LSI component (often captures sequencing depth)
- Use components 2:30 or 2:50 for downstream analysis

### Step 7: Clustering and UMAP

Cluster cells and visualize with UMAP.

```r
# Find neighbors
seurat_obj <- FindNeighbors(
  object = seurat_obj,
  reduction = "lsi",
  dims = 2:30
)

# Find clusters
seurat_obj <- FindClusters(
  object = seurat_obj,
  resolution = 0.8,
  verbose = FALSE
)

# Run UMAP
seurat_obj <- RunUMAP(
  object = seurat_obj,
  reduction = "lsi",
  dims = 2:30
)
```

### Step 8: Complete Workflow

Run the entire standard Signac pipeline.

```r
# Complete workflow
seurat_obj <- run_signac_workflow(
  seurat_obj = seurat_obj,
  dims = 2:30,
  resolution = 0.8,
  run_umap = TRUE,
  run_clustering = TRUE,
  tfidf_method = 1,
  min_cutoff = "q0"
)
```

## Gene Activity Analysis

### Create Gene Activity Matrix

Create gene activity scores from peak accessibility.

```r
# Create gene activity matrix
seurat_obj <- create_gene_activity(
  seurat_obj,
  assay = "peaks",
  annotation = NULL,          # Auto-detect if NULL
  extend_upstream = 2000,
  extend_downstream = 0,
  biotypes = "protein_coding"
)
```

**Key Points:**
- Gene activity approximates gene expression
- Useful for integration with scRNA-seq
- Activity scores are computed from promoter and gene body accessibility

## Peak Calling

### Call Peaks with MACS2

Call peaks using MACS2.

```r
# Call peaks
seurat_obj <- call_peaks_signac(
  seurat_obj,
  group_by = "seurat_clusters",
  macs2_path = "macs2",
  effective_genome_size = 2.7e9,
  shift = -100,
  extsize = 200,
  pvalue = 0.01
)
```

**Requirements:**
- MACS2 installation: `pip install MACS2`
- Provide path to MACS2 executable

## Visualization

### Plot QC Metrics

```r
# QC violin plots
plot_qc_metrics(
  seurat_obj,
  features = NULL,           # Auto-detect
  group_by = NULL,
  log_scale = TRUE
)
```

### Plot UMAP

```r
# UMAP by clusters
Seurat::DimPlot(seurat_obj, reduction = "umap", label = TRUE)

# Gene activity on UMAP
plot_gene_activity_umap(
  seurat_obj,
  genes = c("CD3D", "CD79A", "LYZ"),
  reduction = "umap"
)
```

### Coverage Tracks

```r
# Plot coverage track
plot_coverage_track(
  seurat_obj,
  region = "chr14:106,772,282-106,827,066",  # IGH locus
  group_by = "seurat_clusters",
  assay = "peaks"
)

# Plot by gene name
plot_coverage_track(
  seurat_obj,
  region = "MS4A1",
  group_by = "seurat_clusters"
)
```

## Integration with scRNA-seq

### Transfer Labels from scRNA-seq

```r
# Load scRNA data
seRNA <- readRDS("scRNA_data.rds")

# Find transfer anchors
transfer_anchors <- Seurat::FindTransferAnchors(
  reference = seRNA,
  query = seurat_obj,
  reference.assay = "RNA",
  query.assay = "RNA",       # Gene activity assay
  reduction = "cca"
)

# Transfer labels
predicted_labels <- Seurat::TransferData(
  anchorset = transfer_anchors,
  refdata = seRNA$cell_type
)

seurat_obj$predicted.id <- predicted_labels$predicted.id
```

## Export Results

### Export Data

```r
# Export results
export_signac_results(
  seurat_obj,
  output_dir = "./signac_output",
  prefix = "sample"
)
```

**Exports:**
- `{prefix}_metadata.tsv`: Cell metadata
- `{prefix}_{reduction}.tsv`: Dimensionality reductions
- `{prefix}_qc_summary.tsv`: QC statistics

## Input Requirements

### Fragment File Format

```
chr1    1000    1050    ACGTACGT-1    1
chr1    2000    2050    ACGTACGT-1    1
```

Columns:
1. Chromosome
2. Start (0-based)
3. End (1-based)
4. Cell barcode
5. Count (usually 1)

Files must be:
- Tab-delimited
- Gzipped (.tsv.gz)
- Tabix-indexed (.tbi)

### Count Matrix Format

10x Genomics output:
- `filtered_peak_bc_matrix.h5`: HDF5 format
- `filtered_peak_bc_matrix/`: MatrixMarket directory

## Output Specifications

### Cell Metadata

| Column | Description |
|--------|-------------|
| `nCount_peaks` | Total fragment count |
| `nFeature_peaks` | Number of detected peaks |
| `TSS.enrichment` | TSS enrichment score |
| `nucleosome_signal` | Nucleosome signal ratio |
| `pct_reads_in_peaks` | % reads in peaks |
| `blacklist_ratio` | % reads in blacklist |
| `seurat_clusters` | Cluster assignment |

### LSI Reduction

| Component | Interpretation |
|-----------|----------------|
| LSI_1 | Often correlates with sequencing depth |
| LSI_2-50 | Biological variation |

## Key Parameters

### Quality Control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_counts` | 1000 | Minimum fragments per cell |
| `max_counts` | NULL | Maximum fragments per cell |
| `min_tss` | 2 | Minimum TSS enrichment |
| `max_ns` | 4 | Maximum nucleosome signal |

### Dimensionality Reduction

| Parameter | Default | Description |
|-----------|---------|-------------|
| `dims` | 2:30 | LSI components to use |
| `resolution` | 0.8 | Clustering resolution |
| `min_cutoff` | "q0" | Feature selection cutoff |

### Peak Calling

| Parameter | Default | Description |
|-----------|---------|-------------|
| `shift` | -100 | MACS2 shift parameter |
| `extsize` | 200 | MACS2 extension size |
| `pvalue` | 0.01 | MACS2 p-value threshold |

## Expected Runtime

| Dataset Size | Runtime (single core) |
|--------------|----------------------|
| 5K cells | 5-10 min |
| 20K cells | 20-30 min |
| 100K cells | 2-4 hours |

*Runtime estimates for complete workflow.*

## Best Practices

1. **QC first**: Always review QC metrics before filtering
2. **Skip LSI_1**: First component often captures technical variation
3. **Gene activity**: Useful for annotation but not quantitative
4. **Peak calling**: Call peaks per cluster for better sensitivity
5. **Integration**: Use gene activity matrix for scRNA integration

## Error Handling

### Common Errors and Solutions

**Fragments file not found**
```
Error: Fragments file not found
```
→ Check path to fragments.tsv.gz
→ Ensure tabix index exists (.tbi file)

**MACS2 not found**
```
Error: MACS2 not found
```
→ Install: `pip install MACS2`
→ Provide full path to executable

**Out of memory**
```
Error: cannot allocate vector of size X Gb
```
→ Process in chunks
→ Use `subset()` to sample cells
→ Reduce dimensions parameter

## Related Skills

- [bio-single-cell-atac-archr-r](../bio-single-cell-atac-archr-r/SKILL.md) - ArchR for scATAC-seq
- [bio-single-cell-atac-chromvar-r](../bio-single-cell-atac-chromvar-r/SKILL.md) - chromVAR for TF analysis
- [bio-single-cell-rna-seurat-r](../bio-single-cell-rna-seurat-r/SKILL.md) - Seurat for scRNA-seq

## References

1. Stuart et al. (2021). Single-cell chromatin state analysis with Signac. *Nature Methods*, 18, 1333-1341.
2. Signac documentation: https://stuartlab.org/signac/
3. Signac GitHub: https://github.com/timoast/signac
