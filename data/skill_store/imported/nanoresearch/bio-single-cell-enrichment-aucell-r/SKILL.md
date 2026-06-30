---
name: bio-single-cell-enrichment-aucell-r
description: Per-cell gene set activity scoring using AUCell (AUC-based, robust for sparse scRNA-seq data). Calculate normalized enrichment scores for pathways, signatures, or marker sets and add them to a Seurat object for downstream analysis.
version: "1.1"
tool_type: r
primary_tool: AUCell
supported_tools: [Seurat, Matrix, ggplot2, ggridges]
language: r
dependencies:
  - AUCell >= 1.24.0
  - Seurat >= 4.3.0
  - Matrix
  - ggplot2
  - ggridges (optional, for ridge plots)
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "enrichment", "AUCell", "AUC", "pathway-activity", "sparse-data", "R"]
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| AUCell | >= 1.24.0 | Install from Bioconductor |
| Seurat | >= 4.3.0 | For Seurat integration helpers |
| Matrix | | For sparse matrix support |
| ggplot2 | | For distribution plots |
| ggridges | optional | For ridge plots |

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install("AUCell")
install.packages(c("Seurat", "Matrix", "ggplot2", "ggridges"))
```

## Skill Overview

AUCell calculates Area Under the recovery Curve (AUC) scores for gene set enrichment in single-cell RNA-seq data. It ranks genes per cell and computes the fraction of the gene set recovered in the top-ranked genes, producing a normalized 0-1 score per cell and gene set.

**When to use:**
- You need per-cell pathway or signature activity scores.
- Your data is sparse (high dropout) and you want a ranking-based method robust to zeros.
- You want normalized scores comparable across cells and samples.
- You want to binarize cells into signature-positive vs. negative populations.

**When NOT to use:**
- You need raw, unbounded scores for downstream differential analysis - consider [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) or [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md).
- Your gene sets are very large (>500 genes) - AUCell works best with small to medium sets (20-200 genes).
- You need competitive over-representation testing per cluster - use [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md).
- You need transcription factor activity inference - use [bio-single-cell-enrichment-progeny-r](../bio-single-cell-enrichment-progeny-r/SKILL.md).

## Quick Selector

| Feature | AUCell | vs ssGSEA | vs UCell |
|---------|--------|-----------|----------|
| **Best for** | Sparse scRNA-seq | Dense bulk-like data | Fast per-cell ranking |
| **Speed** | Medium | Fast | Fast |
| **Scores** | Normalized 0-1 | Raw/unnormalized | Normalized 0-1 |
| **Dropout robustness** | High | Medium | High |

## Core Workflow

### Step 1: Prepare Data

**Input:** Expression matrix (genes x cells) or `Seurat` object.  
**Requirements:**
- Gene symbols as row names (e.g., `CD3D`, `VEGFA`).
- Raw counts are acceptable; AUCell ranks genes internally.
- Named list of gene sets.

```r
library(Seurat)
seurat_obj <- readRDS("your_data.rds")
```

### Step 2: Define Gene Sets

```r
gene_sets <- list(
  T_cells = c("CD3D", "CD3E", "CD4", "CD8A", "CD8B"),
  B_cells = c("CD19", "CD79A", "CD79B", "MS4A1"),
  Hypoxia = c("VEGFA", "EGLN1", "CA9", "PGK1", "LDHA")
)
```

### Step 3: Run AUCell

```r
source("scripts/r/run_aucell.R")

auc_results <- run_aucell(
  expr_matrix = seurat_obj,
  gene_sets = gene_sets,
  auc_threshold = 0.05,
  nCores = 4,
  verbose = TRUE
)

auc_matrix <- getAUC(auc_results)
```

### Step 4: Add to Seurat and Visualize

```r
seurat_obj <- add_aucell_to_seurat(seurat_obj, auc_results, key_prefix = "AUC.")

FeaturePlot(seurat_obj, features = "AUC.Hypoxia")
VlnPlot(seurat_obj, features = "AUC.T_cells")
```

### Step 5: Export

```r
export_aucell_results(auc_results, output_file = "aucell_scores.csv", format = "csv")
```

## Complete Pipeline (Copy-Pasteable)

```r
library(Seurat)
library(AUCell)

# 1. Load data
seurat_obj <- readRDS("your_data.rds")

# 2. Define gene sets
gene_sets <- list(
  Hypoxia = c("VEGFA", "EGLN1", "CA9", "PGK1", "LDHA"),
  Glycolysis = c("HK2", "PFKFB3", "GAPDH", "ENO1", "PKM"),
  OXPHOS = c("NDUFS1", "SDHA", "UQCRC1", "COX4I1", "ATP5F1A")
)

# 3. Source skill wrapper
source("scripts/r/run_aucell.R")

# 4. Run AUCell
auc_results <- run_aucell(
  expr_matrix = seurat_obj,
  gene_sets = gene_sets,
  auc_threshold = 0.05,
  nCores = 4,
  norm_auc = TRUE
)

# 5. Add to Seurat
seurat_obj <- add_aucell_to_seurat(seurat_obj, auc_results, key_prefix = "AUC.")

# 6. Visualize
FeaturePlot(seurat_obj, features = "AUC.Hypoxia", reduction = "umap")
VlnPlot(seurat_obj, features = "AUC.Glycolysis", group.by = "cell_type")

# 7. Export
export_aucell_results(auc_results, output_file = "aucell_scores.csv", format = "csv")
```

## Skill-Provided Functions

**Pipeline orchestration**
- `run_aucell(expr_matrix, gene_sets, auc_threshold, nCores, keep_zeroes_as_na, norm_auc, verbose)` - build rankings and compute AUC scores.
- `create_gene_sets_from_markers(markers, min_genes, max_genes)` - convert marker lists to AUCell-compatible gene sets.

**Integration & export**
- `add_aucell_to_seurat(seurat_obj, auc_results, key_prefix)` - add AUC scores to `seurat_obj@meta.data`.
- `export_aucell_results(auc_results, output_file, format)` - save scores as CSV/TSV/RDS.

**Analysis & visualization**
- `plot_aucell_distribution(auc_results, group_vector, gene_set, plot_type)` - violin/box/ridge plot of AUC scores across groups.
- `filter_cells_by_auc(auc_results, gene_set, threshold_method, return_names)` - identify signature-positive cells.

## Official API - Agents Often Miss These

**1. `run_aucell()` accepts either a matrix or a Seurat object**
When a Seurat object is passed, the wrapper extracts `counts` automatically (using `layer = "counts"` for Seurat v5, `slot = "counts"` for v4).

```r
# Correct - pass Seurat object directly
auc_results <- run_aucell(seurat_obj, gene_sets)

# Also correct - pass matrix explicitly
expr_matrix <- GetAssayData(seurat_obj, layer = "counts")
auc_results <- run_aucell(expr_matrix, gene_sets)
```

**2. `auc_threshold` is a fraction, not a count**
`auc_threshold = 0.05` means the top 5% of ranked genes are used. The wrapper converts it to `aucMaxRank = nrow(rankings) * auc_threshold`.

**3. Gene sets must be a named list**
```r
# Correct
gene_sets <- list(Hypoxia = c("VEGFA", "CA9"))

# Wrong - unnamed list will error
gene_sets <- list(c("VEGFA", "CA9"))
```

**4. `getAUC()` returns gene sets as rows and cells as columns**
The skill wrapper transposes this when adding to Seurat metadata.

**5. `filter_cells_by_auc()` uses mean + 1 SD in "auto" mode**
This is a simple heuristic, not the official AUCell threshold exploration. For data-driven thresholds, call `AUCell_exploreThresholds()` directly.

**6. AUCell native binarization requires `AUCell_exploreThresholds()`**
```r
set.seed(123)
cells_assignment <- AUCell_exploreThresholds(cells_auc, plotHist = TRUE, nCores = 1, assign = TRUE)
active_cells <- cells_assignment$Hypoxia$assignment
```

## Common Pitfalls

1. **Using ENSEMBL IDs instead of gene symbols**  
   Gene set names must match `rownames(expr_matrix)`. Convert IDs beforehand.

2. **Gene sets that are too large or too small**  
   AUCell is most reliable with 20-200 genes per set. Sets with fewer than 3 genes are ignored by the wrapper.

3. **Passing log-normalized data expecting different behavior**  
   AUCell ranks genes, so raw counts usually work fine. Do not expect the same absolute ranks if you switch between raw and normalized data.

4. **Forgetting to name gene sets**  
   `run_aucell()` stops with an error if `names(gene_sets)` is NULL.

5. **Assuming "auto" threshold is the official AUCell threshold**  
   The wrapper's `filter_cells_by_auc()` uses mean + SD. Use `AUCell_exploreThresholds()` for the official bimodal threshold method.

6. **Ridge plots fail without `ggridges`**  
   Install `ggridges` before using `plot_type = "ridge"`.

## Scenarios

### Scenario 1: Basic Single-Sample Scoring

```r
source("scripts/r/run_aucell.R")

auc_results <- run_aucell(
  expr_matrix = seurat_obj,
  gene_sets = gene_sets,
  auc_threshold = 0.05,
  nCores = 4
)

auc_matrix <- getAUC(auc_results)
```

### Scenario 2: Add Scores to Seurat and Visualize

```r
seurat_obj <- add_aucell_to_seurat(seurat_obj, auc_results, key_prefix = "AUC.")

FeaturePlot(seurat_obj, features = "AUC.Hypoxia", reduction = "umap")
VlnPlot(seurat_obj, features = "AUC.T_cells", group.by = "cell_type")
```

### Scenario 3: Build Gene Sets from Marker Lists

```r
markers <- list(
  Naive_T = c("IL7R", "TCF7", "LEF1", "CCR7"),
  Effector_T = c("GZMB", "PRF1", "IFNG", "TNF"),
  Exhausted_T = c("PDCD1", "CTLA4", "HAVCR2", "LAG3")
)

gene_sets <- create_gene_sets_from_markers(markers, min_genes = 3, max_genes = 50)
```

### Scenario 4: Distribution and Threshold Analysis

```r
# Violin plot across clusters
plot_aucell_distribution(
  auc_results = auc_results,
  group_vector = seurat_obj$cell_type,
  gene_set = "Hypoxia",
  plot_type = "violin"
)

# Identify signature-positive cells
positive_cells <- filter_cells_by_auc(
  auc_results,
  gene_set = "Hypoxia",
  threshold_method = "auto"
)
```

### Scenario 5: Export Results

```r
# CSV of cell x gene set scores
export_aucell_results(auc_results, output_file = "aucell_scores.csv", format = "csv")

# TSV
export_aucell_results(auc_results, output_file = "aucell_scores.tsv", format = "tsv")

# RDS for R reuse
export_aucell_results(auc_results, output_file = "aucell_results.rds", format = "rds")
```

## Output Interpretation

| Value | Interpretation |
|-------|----------------|
| AUC = 0 | No genes in set expressed |
| AUC = 1 | All genes in set are top expressed |
| 0.5-0.7 | Moderate enrichment |
| > 0.8 | Strong enrichment |

## Parameters

### `run_aucell()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expr_matrix` | matrix / Seurat | required | Expression matrix (genes x cells) or Seurat object |
| `gene_sets` | named list | required | Named list of gene sets |
| `auc_threshold` | numeric | 0.05 | Top fraction of genes for AUC calculation (0.01-0.1 typical) |
| `nCores` | integer | 1 | Number of cores for parallel processing |
| `keep_zeroes_as_na` | logical | FALSE | Convert zeroes to NA in rankings instead of random end placement |
| `norm_auc` | logical | TRUE | Normalize maximum possible AUC to 1 |
| `verbose` | logical | TRUE | Print progress |

### `add_aucell_to_seurat()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object |
| `auc_results` | AUCellResults | required | AUCell result object |
| `key_prefix` | char | "AUC." | Prefix for new metadata columns |

### `plot_aucell_distribution()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `auc_results` | AUCellResults | required | AUCell result object |
| `group_vector` | vector | required | Group labels per cell |
| `gene_set` | char | required | Gene set name to plot |
| `plot_type` | char | "violin" | "violin", "box", or "ridge" |

### `filter_cells_by_auc()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `auc_results` | AUCellResults | required | AUCell result object |
| `gene_set` | char | required | Gene set name |
| `threshold_method` | char/numeric | "auto" | "auto" (mean + 1 SD) or numeric threshold |
| `return_names` | logical | TRUE | Return cell names (TRUE) or logical vector (FALSE) |

### `export_aucell_results()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `auc_results` | AUCellResults | required | AUCell result object |
| `output_file` | char | required | Output file path |
| `format` | char | "csv" | "csv", "tsv", or "rds" |

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `gene_sets must be named` | Unnamed list passed | Add names to every gene set |
| `No valid gene sets provided` | All sets empty or filtered out | Check gene set contents and `min_genes` |
| Low AUC scores for expected pathway | Gene IDs mismatch or too few genes | Verify gene symbols; increase set size to 20+ |
| `ggridges package required` | Ridge plot without ggridges | `install.packages("ggridges")` |
| Seurat v5 slot error | `slot = "counts"` not supported | The wrapper auto-detects v5 and uses `layer = "counts"` |
| Memory issues with large datasets | Building rankings on dense full matrix | Use sparse matrix; reduce `nCores` or chunk cells |

## Related Skills

- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) - ssGSEA / GSEApy methods (Python)
- [bio-single-cell-enrichment-ucell-r](../bio-single-cell-enrichment-ucell-r/SKILL.md) - UCell (R, faster alternative)
- [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md) - decoupleR (R, multi-method enrichment)
- [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md) - Over-representation and GSEA (R)
- [bio-single-cell-enrichment-progeny-r](../bio-single-cell-enrichment-progeny-r/SKILL.md) - TF activity inference (R)

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*.
2. AUCell documentation: https://www.bioconductor.org/packages/release/bioc/html/AUCell.html
