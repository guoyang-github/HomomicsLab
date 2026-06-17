# decoupleR Usage Guide

## Overview

decoupleR infers pathway and transcription factor (TF) activities from gene expression data using multiple statistical methods and prior knowledge networks.

## When to Use

- **Pathway Activity Analysis**: Understand which signaling pathways are active in different cell types or conditions
- **TF Activity Estimation**: Infer transcription factor activities from target gene expression
- **Functional Interpretation**: Add biological context beyond differential gene expression
- **Multi-method Validation**: Use multiple statistical approaches for robust results
- **Footprint-based Enrichment**: Leverage prior knowledge networks for activity inference

## When NOT to Use

- **Direct TF Expression**: decoupleR infers *activity*, not expression levels
- **De Novo Discovery**: Requires prior knowledge networks
- **Single Gene Analysis**: Designed for pathway/TF target gene sets
- **Cross-dataset Comparison**: Scores are relative within a dataset

## Quick Start

```r
# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

library(decoupleR)
library(Seurat)

# Load Seurat object
seurat_obj <- readRDS("processed_data.rds")

# Get pathway network
net <- get_progeny_network(organism = "human", top = 500)

# Run ULM analysis
acts <- run_decoupler_seurat(
  seurat_obj,
  net = net,
  method = "ulm",
  minsize = 5
)

# Add results to Seurat
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts)

# Visualize
plot_activity_heatmap(acts, n_top = 10)
```

## Step-by-Step Guide

### 1. Data Preparation

```r
library(Seurat)
library(decoupleR)

# Source wrapper functions
source("scripts/r/core_analysis.R")
source("scripts/r/utils.R")

# Load Seurat object
seurat_obj <- readRDS("data.rds")

# Check data quality
print(paste("Cells:", ncol(seurat_obj)))
print(paste("Genes:", nrow(seurat_obj)))

# Validate input
mat <- GetAssayData(seurat_obj, slot = "data")
validation <- validate_decoupler_input(mat, data.frame(source = "test", target = rownames(mat)[1:10]))
print(paste("Valid:", validation$valid))
```

### 2. Network Selection

**PROGENy Pathway Network:**
```r
# Get PROGENy network (14 pathways)
progeny_net <- get_progeny_network(organism = "human", top = 500)

# View available pathways
print(unique(progeny_net$source))
```

**DoRothEA TF Network:**
```r
# Get DoRothEA network (high confidence)
dorothea_net <- get_dorothea_network(
  organism = "human",
  levels = c("A", "B", "C")  # A=high, D=low confidence
)

# Check TF coverage
print(paste("TFs:", length(unique(dorothea_net$source))))
```

**CollecTRI TF Network:**
```r
# Get CollecTRI network (expanded coverage)
collectri_net <- get_collectri_network(organism = "human")

print(paste("TFs:", length(unique(collectri_net$source))))
```

**Custom Network:**
```r
# Create custom network
custom_net <- data.frame(
  source = c("MyPathway", "MyPathway", "MyPathway"),
  target = c("GENE1", "GENE2", "GENE3"),
  weight = c(1, -1, 1),
  stringsAsFactors = FALSE
)

# Convert to decoupleR format
custom_net_std <- get_custom_network(custom_net)
```

### 3. Running Analysis Methods

**Univariate Linear Model (ULM) - Recommended:**
```r
# Run ULM - fast and robust
acts_ulm <- run_ulm_analysis(
  mat = mat,
  net = progeny_net,
  minsize = 5,
  center = FALSE
)

head(acts_ulm)
```

**Multivariate Linear Model (MLM):**
```r
# Run MLM - accounts for TF interactions
acts_mlm <- run_mlm_analysis(
  mat = mat,
  net = progeny_net,
  minsize = 5
)
```

**Weighted Sum (WSum):**
```r
# Run WSum - simple and interpretable
acts_wsum <- run_wsum_analysis(
  mat = mat,
  net = progeny_net,
  minsize = 5
)
```

**Multi-method Analysis:**
```r
# Run multiple methods at once
acts_multi <- run_decoupler_multi(
  mat = mat,
  net = progeny_net,
  methods = c("ulm", "mlm", "wsum"),
  minsize = 5
)

# Create consensus score
acts_consensus <- create_consensus_score(acts_multi)
```

### 4. TF Activity Inference

```r
# Get TF network
tf_net <- get_dorothea_network(organism = "human", levels = c("A", "B"))

# Run TF activity inference
tf_acts <- run_ulm_analysis(
  mat = mat,
  net = tf_net,
  minsize = 5
)

# Get top TFs
top_tfs <- get_top_activities(tf_acts, n_top = 20)
print(top_tfs)
```

### 5. Seurat Integration

**Run Directly with Seurat:**
```r
# Run analysis from Seurat object
acts <- run_decoupler_seurat(
  seurat_obj,
  net = progeny_net,
  assay = "RNA",
  slot = "data",
  method = "ulm",
  minsize = 5
)
```

**Add Results to Seurat:**
```r
# Add as metadata
seurat_obj <- add_decoupler_to_seurat(
  seurat_obj,
  acts,
  score_col = "score",
  as_assay = FALSE
)

# Or add as new assay
seurat_obj <- add_decoupler_to_seurat(
  seurat_obj,
  acts,
  as_assay = TRUE
)
```

### 6. Visualization

**Activity Heatmap:**
```r
# Plot top pathway activities
plot_activity_heatmap(
  acts,
  n_top = 15,
  scale = TRUE,
  title = "Pathway Activities"
)
```

**Top Activities Bar Plot:**
```r
# Plot top activities for a condition
p <- plot_top_activities(
  acts,
  condition = "Sample_1",
  n_top = 20,
  color_by_sign = TRUE
)
print(p)
```

**Activity on UMAP:**
```r
# Plot pathway activity on UMAP
p <- plot_activity_reduced(
  seurat_obj,
  source = "TNFa",
  dimred = "umap"
)
print(p)
```

**Method Comparison:**
```r
# Compare ULM vs MLM results
p <- plot_method_comparison(acts_multi, source_specific = "TNFa")
print(p)
```

**Comprehensive Summary:**
```r
# Generate all summary plots
plot_decoupler_summary(
  acts,
  output_dir = "./decoupler_plots",
  prefix = "pathway"
)
```

### 7. Differential Analysis

```r
# Compare activities between conditions
diff_acts <- get_differential_activities(
  acts,
  cond1 = "Control",
  cond2 = "Treatment"
)

# View most differentially active pathways
head(diff_acts)

# Plot scatter comparison
p <- plot_activity_scatter(
  acts,
  x_condition = "Control",
  y_condition = "Treatment"
)
print(p)
```

### 8. Export Results

```r
# Export all results
export_decoupler_results(
  acts,
  output_dir = "./decoupler_output",
  prefix = "sample"
)

# Generate report
report <- create_decoupler_report(
  acts,
  net = progeny_net,
  output_file = "./decoupler_report.txt"
)
cat(report)
```

## Parameters and Options

### minsize Parameter

Controls the minimum number of target genes required for a source:

```r
# Relaxed filtering (more sources, potentially noisier)
acts <- run_ulm_analysis(mat, net, minsize = 3)

# Stringent filtering (fewer sources, more robust)
acts <- run_ulm_analysis(mat, net, minsize = 10)

# Default recommended
acts <- run_ulm_analysis(mat, net, minsize = 5)
```

### Method Selection

| Method | Speed | Use Case |
|--------|-------|----------|
| ULM | Fast | General purpose, recommended |
| MLM | Medium | When regulators may interact |
| WSum | Fast | Simple interpretation |
| AUCell | Medium | Small gene sets |
| ORA | Fast | Binary input data |
| GSVA | Slow | Bulk-like behavior |

### Network Confidence Levels (DoRothEA)

```r
# High confidence only (most reliable)
net_A <- get_dorothea_network(organism = "human", levels = "A")

# Medium confidence (recommended balance)
net_ABC <- get_dorothea_network(organism = "human", levels = c("A", "B", "C"))

# All confidence levels (most comprehensive)
net_all <- get_dorothea_network(organism = "human", levels = c("A", "B", "C", "D"))
```

## Common Workflows

### Basic Pathway Analysis

```r
# Load data and network
seurat_obj <- readRDS("data.rds")
net <- get_progeny_network(organism = "human")

# Run analysis
acts <- run_decoupler_seurat(seurat_obj, net, method = "ulm")

# Add to Seurat
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts)

# Visualize top pathways
plot_activity_heatmap(acts, n_top = 10)
```

### Multi-sample Comparison

```r
# Run multi-method analysis
acts_multi <- run_decoupler_multi(
  mat,
  net,
  methods = c("ulm", "mlm", "wsum")
)

# Create consensus
acts_consensus <- create_consensus_score(acts_multi)

# Compare conditions
diff <- get_differential_activities(acts_consensus, "Ctrl", "Treat")
```

### Per-cluster Analysis

```r
# Get cluster-specific activities
seurat_obj$cell_type <- Idents(seurat_obj)

# Average expression by cluster
avg_expr <- AverageExpression(seurat_obj, group.by = "cell_type")$RNA

# Run decoupleR on cluster averages
acts_cluster <- run_ulm_analysis(avg_expr, progeny_net)

# Visualize
plot_activity_heatmap(acts_cluster, n_top = 15)
```

## AI Agent Test Cases

### Basic Usage

> "Run decoupleR ULM to infer pathway activities from my scRNA-seq data"

```r
net <- get_progeny_network(organism = "human")
acts <- run_decoupler_seurat(seurat_obj, net, method = "ulm")
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts)
```

> "Estimate TF activities using DoRothEA network"

```r
tf_net <- get_dorothea_network(organism = "human", levels = c("A", "B", "C"))
tf_acts <- run_ulm_analysis(GetAssayData(seurat_obj), tf_net)
```

### Multi-method Analysis

> "Run decoupleR with multiple methods and get consensus scores"

```r
acts_multi <- run_decoupler_multi(
  mat,
  net,
  methods = c("ulm", "mlm", "wsum")
)
acts_consensus <- create_consensus_score(acts_multi)
```

> "Compare ULM vs WSum pathway activity results"

```r
acts_ulm <- run_ulm_analysis(mat, net)
acts_wsum <- run_wsum_analysis(mat, net)
acts_multi <- dplyr::bind_rows(acts_ulm, acts_wsum)
plot_method_comparison(acts_multi)
```

### Visualization

> "Plot pathway activity heatmap for top 15 pathways"

```r
plot_activity_heatmap(acts, n_top = 15, scale = TRUE)
```

> "Show TNFa pathway activity on UMAP"

```r
plot_activity_reduced(seurat_obj, source = "TNFa", dimred = "umap")
```

> "Compare pathway activities between two conditions"

```r
plot_activity_scatter(acts, x_condition = "Ctrl", y_condition = "Treat")
```

### Advanced Queries

> "Filter network to only include sources with at least 10 targets"

```r
net_filtered <- filter_network_by_size(net, minsize = 10)
```

> "Get top 20 differentially active TFs between clusters"

```r
diff <- get_differential_activities(tf_acts, "Cluster1", "Cluster2")
head(diff, 20)
```

> "Create comprehensive summary plots for all results"

```r
plot_decoupler_summary(acts, output_dir = "./plots", prefix = "analysis")
```

## Troubleshooting

### Low Gene Overlap

**Problem**: "No common genes between mat and net targets"

**Solution**:
```r
# Check gene naming
head(rownames(mat))
head(unique(net$target))

# Convert gene symbols if needed
library(org.Hs.eg.db)
# Convert between IDs

# Check overlap
overlap <- intersect(rownames(mat), net$target)
print(paste("Overlap:", length(overlap)))
```

### All Scores Near Zero

**Problem**: Activity scores have very small magnitude

**Solution**:
```r
# Check data scaling
summary(as.vector(mat))

# Ensure log-normalized data
# Raw counts will give poor results

# Try different minsize
acts <- run_ulm_analysis(mat, net, minsize = 3)
```

### Memory Issues with Large Datasets

**Problem**: Analysis fails with >50,000 cells

**Solution**:
```r
# Use ULM only (most memory efficient)
acts <- run_ulm_analysis(mat, net)

# Or downsample
set.seed(42)
cells <- sample(colnames(seurat_obj), 10000)
seurat_sub <- subset(seurat_obj, cells = cells)
```

## Best Practices

1. **Data Quality**: Use normalized, log-transformed expression data
2. **Method Selection**: Start with ULM for general analysis
3. **Multi-method**: Run 2-3 methods for robustness
4. **Network Coverage**: Check gene overlap before running
5. **Interpretation**: Focus on relative differences, not absolute scores
6. **Validation**: Compare with known biology

## References

1. Badia-i-Mompel P, et al. (2022). decoupleR: Ensemble of computational methods to infer biological activities from omics data. *Bioinformatics Advances*, 2(1), vbac016.

2. Schubert M, et al. (2018). Perturbation-response genes reveal signaling footprints in cancer gene expression. *Nature Communications*, 9(1), 20.

3. Garcia-Alonso L, et al. (2019). Benchmark and integration of resources for the estimation of human transcription factor activities. *Genome Research*, 29(8), 1363-1375.

4. decoupleR documentation: https://saezlab.github.io/decoupleR/
