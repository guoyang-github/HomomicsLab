---
name: bio-single-cell-enrichment-aucell-r
description: Per-cell gene set activity scoring using AUCell (AUC-based, robust for sparse scRNA-seq data)
tool_type: r
primary_tool: AUCell
language: r
dependencies:
  - AUCell >= 1.24.0
  - Seurat >= 4.3.0
  - Matrix
  - ggplot2
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "enrichment", "AUCell", "AUC", "pathway-activity", "sparse-data", "R"]
---

## Version Compatibility

Reference examples tested with:
- **R**: 4.2.0+
- **AUCell**: 1.24+
- **Seurat**: 4.3+

## Installation

```r
# Install Bioconductor if needed
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

# Install AUCell
BiocManager::install("AUCell")

# Optional: for visualization
install.packages(c("ggplot2", "ggridges"))
```

# Single-Cell Enrichment with AUCell

Calculate AUC-based gene set activity scores per cell. Particularly suitable for sparse scRNA-seq data.

## Quick Selector

| Feature | AUCell | vs ssGSEA (Python) |
|---------|--------|-------------------|
| **Best for** | Sparse data | Dense data |
| **Speed** | Medium | Fast |
| **Robustness** | High (handles dropouts) | Medium |
| **Output** | 0-1 normalized scores | Raw scores |

### When to Use AUCell

- Your data has high dropout rates (>50% zeros)
- You need normalized scores for comparison across datasets
- You want binary (on/off) pathway activity calls

---

## Quick Start

### Basic Usage

```r
source("scripts/r/run_aucell.R")

# Run AUCell
auc_results <- run_aucell(
  expr_matrix = counts_matrix,
  gene_sets = my_gene_sets,
  auc_threshold = 0.05
)

# Access AUC scores
auc_matrix <- getAUC(auc_results)
```

**Full implementation:** [scripts/r/run_aucell.R](scripts/r/run_aucell.R)

---

## Detailed Usage

### 1. Run AUCell with Seurat

```r
library(Seurat)
source("scripts/r/run_aucell.R")

# Load data
seurat_obj <- readRDS("your_data.rds")

# Define gene sets
gene_sets <- list(
  T_cells = c("CD3D", "CD3E", "CD4", "CD8A", "CD8B"),
  B_cells = c("CD19", "CD79A", "CD79B", "MS4A1"),
  Myeloid = c("CD14", "LYZ", "CST3", "FCER1G")
)

# Run AUCell
auc_results <- run_aucell(
  expr_matrix = seurat_obj,
  gene_sets = gene_sets,
  auc_threshold = 0.05,
  nCores = 4,
  verbose = TRUE
)

# Add to Seurat
seurat_obj <- add_aucell_to_seurat(seurat_obj, auc_results, key_prefix = "AUC.")

# Visualize
FeaturePlot(seurat_obj, features = "AUC.T_cells")
```

### 2. Create Gene Sets from Markers

```r
# Load markers from file or analysis
markers <- list(
  Naive_T = c("IL7R", "TCF7", "LEF1", "CCR7"),
  Effector_T = c("GZMB", "PRF1", "IFNG", "TNF"),
  Exhausted_T = c("PDCD1", "CTLA4", "HAVCR2", "LAG3")
)

# Filter and format
gene_sets <- create_gene_sets_from_markers(
  markers,
  min_genes = 3,
  max_genes = 50
)
```

### 3. Visualize AUC Distribution

```r
# Plot distribution across clusters
plot_aucell_distribution(
  auc_results = auc_results,
  group_vector = seurat_obj$seurat_clusters,
  gene_set = "T_cells",
  plot_type = "violin"
)
```

### 4. Filter Cells by Activity

```r
# Get cells with high T cell signature
positive_cells <- filter_cells_by_auc(
  auc_results,
  gene_set = "T_cells",
  threshold_method = "auto"
)

message(sprintf("Found %d T cell signature positive cells", length(positive_cells)))
```

### 5. Export Results

```r
# Export as CSV
export_aucell_results(
  auc_results,
  output_file = "aucell_scores.csv",
  format = "csv"
)

# Or save as RDS for R reuse
export_aucell_results(
  auc_results,
  output_file = "aucell_results.rds",
  format = "rds"
)
```

---

## Parameters

### run_aucell()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expr_matrix` | matrix/Seurat | - | Expression matrix (genes x cells) or Seurat object |
| `gene_sets` | list | - | Named list of gene sets |
| `auc_threshold` | numeric | 0.05 | Top fraction of genes for AUC calculation |
| `nCores` | integer | 1 | Number of cores for parallel processing |
| `verbose` | logical | TRUE | Print progress |

**AUC Threshold:** Lower values = more stringent (top 5% genes). Typical range: 0.01-0.1.

---

## API Reference

### Functions

| Function | Location | Description |
|----------|----------|-------------|
| `run_aucell()` | [run_aucell.R:26](scripts/r/run_aucell.R#L26) | Main AUCell analysis |
| `create_gene_sets_from_markers()` | [run_aucell.R:92](scripts/r/run_aucell.R#L92) | Create gene sets from markers |
| `add_aucell_to_seurat()` | [run_aucell.R:120](scripts/r/run_aucell.R#L120) | Add AUC to Seurat metadata |
| `plot_aucell_distribution()` | [run_aucell.R:152](scripts/r/run_aucell.R#L152) | Plot AUC distributions |
| `filter_cells_by_auc()` | [run_aucell.R:198](scripts/r/run_aucell.R#L198) | Filter cells by threshold |
| `export_aucell_results()` | [run_aucell.R:235](scripts/r/run_aucell.R#L235) | Export results |

### AUCell Native Functions

| Function | Description |
|----------|-------------|
| `getAUC()` | Extract AUC matrix from results |
| `getRanking()` | Extract gene rankings |
| `AUCell_plot()` | Plot AUC distributions |
| `cbind()` | Combine AUCell results |

---

## Examples

| Example | Description |
|---------|-------------|
| [minimal_example.R](examples/minimal_example.R) | Basic AUCell workflow |
| [seurat_integration.R](examples/seurat_integration.R) | Integrate with Seurat |

---

## Related Skills

- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) - gseapy methods (Python)
- [bio-single-cell-enrichment-ucell-r](../bio-single-cell-enrichment-ucell-r/SKILL.md) - UCell (R)
- [bio-single-cell-enrichment-decoupler](../bio-single-cell-enrichment-decoupler/SKILL.md) - decoupleR (R)

---

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. Nature Methods.
2. AUCell documentation: https://www.bioconductor.org/packages/release/bioc/html/AUCell.html
