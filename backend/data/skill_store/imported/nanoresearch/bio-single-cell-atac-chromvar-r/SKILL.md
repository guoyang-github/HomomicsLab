---
name: bio-single-cell-atac-chromvar-r
description: Single-cell ATAC-seq TF motif deviation analysis using chromVAR. Identifies variability in transcription factor binding activity across cells.
tool_type: r
primary_tool: chromVAR
supported_tools: [SummarizedExperiment, motifmatchr, JASPAR, BSgenome]
languages: [r]
keywords: ["single-cell", "ATAC", "chromVAR", "TF", "motifs", "chromatin", "accessibility", "deviations", "R"]
---

## Version Compatibility

- **R**: >= 4.2.0
- **chromVAR**: >= 1.20.0
- **Bioconductor**: >= 3.17

## Installation

```r
# Install chromVAR from Bioconductor
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

BiocManager::install("chromVAR")

# Install additional dependencies
BiocManager::install(c("motifmatchr", "JASPAR2020", "BSgenome.Hsapiens.UCSC.hg38"))
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

chromVAR analyzes chromatin accessibility variation at transcription factor binding motifs to infer cell-specific TF activity from scATAC-seq data.

### Step 1: Create Input Object

Create a `RangedSummarizedExperiment` from peak counts and metadata.

```r
# From count matrix and peaks
rse <- create_chromvar_object(
  counts = count_matrix,      # peaks x cells sparse matrix
  peaks = peaks_granges,      # GRanges with peak coordinates
  cell_metadata = metadata    # Data frame with cell info (optional)
)

# Or from BED file and MTX file
counts <- load_count_matrix("peak_counts.mtx")
peaks <- load_peaks_from_bed("peaks.bed")
rse <- create_chromvar_object(counts, peaks)
```

**Input Requirements:**
- `counts`: Sparse matrix (peaks x cells) with fragment counts
- `peaks`: GRanges object with genomic coordinates
- Peaks should be non-overlapping for best results

### Step 2: Validate Input

Validate input data before running analysis.

```r
validation <- validate_chromvar_input(rse)

if (!validation$valid) {
  stop(paste("Validation errors:", paste(validation$errors, collapse = "\n")))
}

if (length(validation$warnings) > 0) {
  for (warning in validation$warnings) {
    warning(warning)
  }
}

# View stats
cat(sprintf("Peaks: %d, Cells: %d\n",
            validation$stats$n_peaks,
            validation$stats$n_cells))
```

### Step 3: Filter Peaks

Filter peaks to remove low-accessibility regions and overlaps.

```r
# Filter peaks
rse_filtered <- filter_peaks_chromvar(
  rse,
  min_fragments_per_peak = 1,  # Minimum total fragments per peak
  non_overlapping = TRUE        # Remove overlapping peaks
)
```

**Filtering Guidelines:**
- `min_fragments_per_peak`: Higher values (e.g., 5-10) for large datasets
- `non_overlapping`: Always TRUE for standard chromVAR analysis

### Step 4: Add GC Bias

Compute GC content for each peak for bias correction.

```r
# Add GC bias
rse_filtered <- add_gc_bias(
  rse_filtered,
  genome = "BSgenome.Hsapiens.UCSC.hg38"  # or BSgenome object
)
```

**Supported Genomes:**
- Human: `BSgenome.Hsapiens.UCSC.hg19`, `BSgenome.Hsapiens.UCSC.hg38`
- Mouse: `BSgenome.Mmusculus.UCSC.mm9`, `BSgenome.Mmusculus.UCSC.mm10`

### Step 5: Match Motifs

Find TF motif occurrences in peak sequences.

```r
# Option 1: Use JASPAR database
motif_ix <- match_motifs_chromvar(
  rse_filtered,
  motifs = "jaspar2020",                    # or "jaspar2018"
  genome = "BSgenome.Hsapiens.UCSC.hg38"
)

# Option 2: Load custom motifs
jaspar_motifs <- load_jaspar_motifs(species = 9606)  # 9606 = human
motif_ix <- match_motifs_chromvar(
  rse_filtered,
  motifs = jaspar_motifs,
  genome = "BSgenome.Hsapiens.UCSC.hg38"
)
```

### Step 6: Compute Deviations

Compute accessibility deviations for each motif.

```r
# Compute background peaks (optional - computed automatically if NULL)
bg_peaks <- get_background_peaks(rse_filtered, niterations = 50)

# Compute deviations
dev <- compute_deviations_chromvar(
  rse = rse_filtered,
  annotations = motif_ix,
  background_peaks = bg_peaks
)
```

**Output:**
- `deviations`: Raw deviation scores (observed vs expected)
- `z`: Bias-corrected z-scores (use these for analysis)

### Step 7: Compute Variability

Compute per-motif variability across cells.

```r
# Compute variability
var <- compute_variability_chromvar(
  dev,
  bootstrap_error = TRUE,    # Compute confidence intervals
  bootstrap_samples = 1000
)

# View top variable motifs
head(var[order(var$variability, decreasing = TRUE), ])
```

### Step 8: Run Complete Workflow

Run the entire chromVAR pipeline in one command.

```r
# Complete workflow
results <- run_chromvar(
  rse = rse,
  motifs = "jaspar2020",
  genome = "BSgenome.Hsapiens.UCSC.hg38",
  filter_peaks = TRUE,
  min_fragments_per_peak = 1,
  n_bg_iterations = 50,
  n_cores = 4
)

# Access results
results$rse           # Filtered RSE with GC bias
results$motif_matches # Motif match object
results$deviations    # chromVARDeviations object
results$variability   # Variability data frame
```

## Visualization

### Plot Variability

```r
# Variability plot
plot_variability_chromvar(
  results$variability,
  n_label = 5,
  use_plotly = FALSE
)
```

### Deviation Heatmap

```r
# Heatmap of top variable motifs
plot_deviation_heatmap(
  results$deviations,
  var = results$variability,
  n_motifs = 20
)
```

### Motif Activity by Group

```r
# Compare motif activity across groups
plot_motif_deviations(
  results$deviations,
  motif_names = c("GATA1", "CEBPA", "PAX5"),
  group_by = cell_metadata$cell_type,
  plot_type = "violin"
)
```

### Motif Activity on Dimensionality Reduction

```r
# Plot on UMAP/tSNE
plot_deviations_dimred(
  results$deviations,
  dimred = data.frame(x = umap_coords[, 1], y = umap_coords[, 2]),
  motif_names = var$name[1:4]
)
```

### Comprehensive Visualization Report

```r
# Create all plots
create_chromvar_plots(
  results,
  dimred = umap_coords,
  group_by = cell_metadata$cell_type,
  output_dir = "./chromvar_plots"
)
```

## Advanced Analysis

### Extract and Analyze Specific Motifs

```r
# Get top variable motifs
top_motifs <- get_top_variable_motifs(results$variability, n = 10)

# Extract deviation scores
z_scores <- get_motif_deviation_scores(
  results$deviations,
  motif_names = top_motifs$name
)
```

### Correlate with Gene Expression

```r
# Correlate TF activity with gene expression
correlations <- correlate_deviations_with_expression(
  dev = results$deviations,
  gene_expression = gene_expression_matrix
)
```

### Differential Accessibility Analysis

```r
# Test for differential deviations between groups
diff_dev <- chromVAR::differentialDeviations(
  results$deviations,
  groups = cell_metadata$condition
)

# Test for differential variability
diff_var <- chromVAR::differentialVariability(
  results$deviations,
  groups = cell_metadata$condition
)
```

## Export and Reporting

### Export Results

```r
# Export all results
export_chromvar_results(
  results,
  output_dir = "./chromvar_output",
  prefix = "sample1"
)
```

**Exported Files:**
- `{prefix}_variability.txt`: Motif variability statistics
- `{prefix}_deviation_scores.txt`: Cell x motif z-scores
- `{prefix}_summary.txt`: Summary statistics

### Generate Report

```r
# Create text report
report <- create_chromvar_report(results, "chromvar_report.txt")
cat(report)
```

## Input Requirements

### Count Matrix Format

```r
# Required: peaks x cells sparse matrix
library(Matrix)
counts <- Matrix::Matrix(0, nrow = 50000, ncol = 1000, sparse = TRUE)
rownames(counts) <- paste0("peak_", 1:50000)
colnames(counts) <- paste0("cell_", 1:1000)

# From 10x Genomics output
counts <- load_count_matrix("peak_counts.mtx")
```

### Peak Format

```r
# GRanges object
peaks <- GenomicRanges::GRanges(
  seqnames = c("chr1", "chr1", "chr2"),
  ranges = IRanges::IRanges(start = c(1000, 5000, 2000), width = 500)
)

# Or from BED file
peaks <- load_peaks_from_bed("peaks.bed")
```

## Output Specifications

### Variability Data Frame

| Column | Description |
|--------|-------------|
| `name` | Motif name |
| `variability` | Standard deviation of z-scores |
| `bootstrap_lower_bound` | Lower CI (if bootstrap=TRUE) |
| `bootstrap_upper_bound` | Upper CI (if bootstrap=TRUE) |
| `p_value` | Significance p-value |
| `p_value_adj` | FDR-adjusted p-value |

### Deviation Scores

| Metric | Interpretation |
|--------|----------------|
| `z > 0` | Higher accessibility than expected |
| `z < 0` | Lower accessibility than expected |
| `|z| > 2` | Significant deviation |

## Key Parameters

### Background Peaks

| Parameter | Default | Description |
|-----------|---------|-------------|
| `niterations` | 50 | Background samples per peak |
| `w` | 0.1 | Similarity threshold (smaller = more similar) |
| `bs` | 50 | Bin size for GC-accessibility space |

### Filtering

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_fragments_per_peak` | 1 | Minimum fragments across all cells |
| `non_overlapping` | TRUE | Remove overlapping peaks |

### Computation

| Parameter | Default | Description |
|-----------|---------|-------------|
| `n_cores` | 1 | Parallel cores |
| `bootstrap_error` | TRUE | Compute confidence intervals |

## Expected Runtime

| Dataset Size | Runtime (4 cores) |
|--------------|-------------------|
| 1K cells, 20K peaks | 5-10 min |
| 5K cells, 50K peaks | 20-40 min |
| 10K cells, 100K peaks | 1-2 hours |

*Runtime estimates include motif matching and deviation computation.*

## Best Practices

1. **Peak quality**: Filter low-quality peaks before analysis
2. **GC bias**: Always correct for GC bias
3. **Motif database**: Use JASPAR2020 for best coverage
4. **Cell numbers**: chromVAR works best with >100 cells
5. **Peak numbers**: 10K-100K peaks is typical; filter very low-accessibility peaks
6. **Interpretation**: High variability = cell-type-specific TF activity
7. **Batch effects**: Run on harmonized data if batch effects present

## Error Handling

### Common Errors and Solutions

**Peaks have overlaps**
```
Warning: Peaks have overlaps!
```
→ Run `filter_peaks_chromvar()` with `non_overlapping = TRUE`

**GC bias not found**
```
Error: GC bias not found. Run add_gc_bias() first.
```
→ Ensure `add_gc_bias()` is called before `get_background_peaks()`

**No matching motifs**
```
Error: No matching motifs found
```
→ Check motif names match those in the deviation object

## Related Skills

- [bio-single-cell-atac-signac-r](../bio-single-cell-atac-signac-r/SKILL.md) - scATAC-seq analysis with Signac
- [bio-single-cell-atac-archr-r](../bio-single-cell-atac-archr-r/SKILL.md) - scATAC-seq analysis with ArchR
- [bio-single-cell-enrichment-chromvar-r](../bio-single-cell-enrichment-chromvar-r/SKILL.md) - chromVAR enrichment analysis

## References

1. Schep et al. (2017). chromVAR: inferring transcription-factor-associated accessibility from single-cell epigenomic data. *Nature Methods*, 14, 975-978.
2. chromVAR documentation: https://greenleaflab.github.io/chromVAR/
3. JASPAR database: https://jaspar.genereg.net/
