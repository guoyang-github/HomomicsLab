# chromVAR Usage Guide

## Overview

chromVAR is an R package for analyzing chromatin accessibility variation across single cells at transcription factor binding motifs. It identifies motifs associated with variability in accessibility and computes per-cell motif deviation scores that can be used to infer cell-specific TF activity.

## When to Use

- **TF activity inference**: Identify which transcription factors show cell-type-specific activity patterns
- **Motif enrichment**: Find variable TF binding motifs in scATAC-seq data
- **Cell heterogeneity**: Understand chromatin accessibility differences between cell populations
- **Integration**: Correlate chromatin accessibility with gene expression or other modalities

## Quick Start

### Minimal Example

```r
library(chromVAR)
library(SummarizedExperiment)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# Create input from counts and peaks
counts <- Matrix::Matrix(rpois(100000, 5), nrow = 1000, sparse = TRUE)
peaks <- GenomicRanges::GRanges(
  seqnames = rep("chr1", 1000),
  ranges = IRanges::IRanges(start = seq(1, 1000000, by = 1000), width = 500)
)

# Create RangedSummarizedExperiment
rse <- create_chromvar_object(counts, peaks)

# Run complete analysis
results <- run_chromvar(
  rse,
  motifs = "jaspar2020",
  genome = "BSgenome.Hsapiens.UCSC.hg38"
)

# View top variable motifs
head(results$variability[order(results$variability$variability, decreasing = TRUE), ])
```

## Step-by-Step Workflow

### 1. Data Preparation

#### From 10x Genomics Output

```r
# Load from 10x output
counts <- Seurat::Read10X("filtered_peak_bc_matrix/")
peaks <- load_peaks_from_bed("peaks.bed")

# Create chromVAR object
rse <- create_chromvar_object(
  counts = counts,
  peaks = peaks,
  cell_metadata = data.frame(
    cell_id = colnames(counts),
    sample = extract_sample(colnames(counts))
  )
)
```

#### From Signac Object

```r
library(Signac)

# Extract from Signac
counts <- GetAssayData(seurat_obj, assay = "peaks", slot = "counts")
peaks <- granges(seurat_obj[["peaks"]])

rse <- create_chromvar_object(counts, peaks)
```

### 2. Quality Control

```r
# Validate input
validation <- validate_chromvar_input(rse)
print(validation$stats)

# Check peak accessibility
plot_peak_accessibility(rse)

# Check cell depth
plot_sample_depth(rse)

# Filter peaks
rse_filtered <- filter_peaks_chromvar(
  rse,
  min_fragments_per_peak = 5,
  non_overlapping = TRUE
)
```

### 3. GC Bias Correction

```r
# Add GC bias
rse_filtered <- add_gc_bias(
  rse_filtered,
  genome = BSgenome.Hsapiens.UCSC.hg38::BSgenome.Hsapiens.UCSC.hg38
)

# Visualize GC distribution
plot_gc_bias(rse_filtered)
```

### 4. Motif Analysis

```r
# Load JASPAR motifs
motifs <- load_jaspar_motifs(species = 9606)  # Human

# Match motifs
motif_ix <- match_motifs_chromvar(
  rse_filtered,
  motifs = motifs,
  genome = "BSgenome.Hsapiens.UCSC.hg38"
)

# Get background peaks
bg_peaks <- get_background_peaks(rse_filtered, niterations = 50)
```

### 5. Compute Deviations

```r
# Compute deviations
dev <- compute_deviations_chromvar(
  rse = rse_filtered,
  annotations = motif_ix,
  background_peaks = bg_peaks
)

# Extract z-scores
z_scores <- chromVAR::deviationScores(dev)
```

### 6. Variability Analysis

```r
# Compute variability
var <- compute_variability_chromvar(dev)

# Top variable motifs
top_10 <- get_top_variable_motifs(var, n = 10)
print(top_10[, c("name", "variability", "p_value_adj")])
```

### 7. Visualization

```r
# Variability plot
plot_variability_chromvar(var, n_label = 5)

# Deviation heatmap
plot_deviation_heatmap(dev, var, n_motifs = 20)

# Motif activity by group
plot_motif_deviations(
  dev,
  motif_names = top_10$name[1:6],
  group_by = metadata$cell_type
)
```

## Advanced Topics

### Parallel Processing

```r
library(BiocParallel)

# Register parallel backend
register(MulticoreParam(4))

# Run with parallelization
results <- run_chromvar(rse, motifs = "jaspar2020",
                       genome = "BSgenome.Hsapiens.UCSC.hg38",
                       n_cores = 4)
```

### Custom Motif Sets

```r
# Load specific TF families
tfs_of_interest <- c("GATA1", "GATA2", "SPI1", "CEBPA")

# Get all JASPAR motifs
all_motifs <- load_jaspar_motifs()

# Subset to TFs of interest
custom_motifs <- all_motifs[names(all_motifs) %in% tfs_of_interest]

# Run analysis
motif_ix <- match_motifs_chromvar(rse, custom_motifs, genome)
```

### Integration with Seurat

```r
# Add motif deviations to Seurat object
z_scores <- chromVAR::deviationScores(results$deviations)

# Add as a new assay
seurat_obj[["chromvar"]] <- CreateAssayObject(data = z_scores)

# Find variable motifs
seurat_obj <- FindVariableFeatures(seurat_obj, assay = "chromvar")
```

### Batch Correction

```r
# chromVAR should be run on batch-corrected data
# Use Harmony or other integration methods first

# Example: Run per batch and merge
results_list <- lapply(unique(batch_ids), function(batch) {
  rse_batch <- rse[, batch_ids == batch]
  run_chromvar(rse_batch, motifs = "jaspar2020", genome = genome)
})

merged <- merge_chromvar_results(results_list, unique(batch_ids))
```

## AI Agent Test Cases

### Basic Usage

> "Run chromVAR on scATAC-seq data"

```r
results <- run_chromvar(rse, motifs = "jaspar2020",
                       genome = "BSgenome.Hsapiens.UCSC.hg38")
```

> "Identify variable TF motifs"

```r
var <- compute_variability_chromvar(results$deviations)
top_motifs <- get_top_variable_motifs(var, n = 10)
```

### Motif Analysis

> "Find GATA1 activity in my scATAC data"

```r
z_scores <- get_motif_deviation_scores(results$deviations, "GATA1")
gata1_activity <- z_scores["GATA1", ]
```

> "Compare TF activity between cell types"

```r
plot_motif_deviations(
  results$deviations,
  motif_names = c("GATA1", "CEBPA"),
  group_by = metadata$cell_type
)
```

### Advanced

> "Export chromVAR results"

```r
export_chromvar_results(results, output_dir = "./output")
```

> "Create visualization report"

```r
create_chromvar_plots(results, dimred = umap_coords,
                     group_by = metadata$cell_type)
```

## Interpretation

### Understanding Deviations

| Z-score | Interpretation |
|---------|----------------|
| `z > 2` | Significantly higher accessibility than expected |
| `0 < z < 2` | Moderately higher accessibility |
| `z ≈ 0` | Accessibility matches expectation |
| `-2 < z < 0` | Moderately lower accessibility |
| `z < -2` | Significantly lower accessibility |

### Understanding Variability

- **High variability**: TF shows cell-type-specific activity
- **Low variability**: TF activity is uniform across cells
- **Statistical significance**: Check `p_value_adj` column

### Common Patterns

1. **Cell-type markers**: TFs with high variability often define cell types
2. **Activity correlation**: Motifs with similar patterns may regulate same genes
3. **Batch effects**: Check if high-variability TFs are technical artifacts

## Best Practices

### Before Analysis

1. **Filter low-quality cells** (minimum 500-1000 fragments)
2. **Remove batch effects** if analyzing multiple samples
3. **Filter peaks** to remove very low-accessibility regions
4. **Ensure non-overlapping peaks** for accurate analysis

### During Analysis

1. **Use appropriate genome** for GC bias correction
2. **Match motif database** to your species
3. **Compute background peaks** with sufficient iterations (50-100)
4. **Use parallel processing** for large datasets

### After Analysis

1. **Validate top motifs** against known biology
2. **Check correlation** with gene expression when available
3. **Visualize on dimensionality reduction** to confirm patterns
4. **Test for differential deviations** between conditions

## Troubleshooting

### Low variability for all motifs

- Check GC bias was added correctly
- Verify peak quality and number
- Ensure sufficient cell heterogeneity

### Unexpected top motifs

- Check for batch effects
- Verify genome matches your data
- Look at raw deviations, not just z-scores

### Memory issues

- Process in chunks for very large datasets
- Use `filterPeaks` aggressively before analysis
- Run with fewer cores if RAM is limited

### Slow computation

- Increase parallel cores with `n_cores`
- Reduce `niterations` for background peaks (trade accuracy for speed)
- Filter to top variable peaks first

## References

1. Schep et al. (2017). chromVAR: inferring transcription-factor-associated accessibility from single-cell epigenomic data. *Nature Methods*.
2. chromVAR documentation: https://greenleaflab.github.io/chromVAR/
