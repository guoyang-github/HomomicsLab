---
name: bio-single-cell-enrichment-ucell-r
description: |
  Fast per-cell gene set scoring using UCell (Mann-Whitney U statistic).
  Robust for cross-dataset comparison, small gene sets, and Seurat v4/v5 workflows.
version: "1.1"
tool_type: r
primary_tool: UCell
supported_tools: [Seurat, Matrix, ggplot2, ggridges]
languages: [r]
dependencies:
  - UCell >= 2.6.0
  - Seurat >= 4.3.0
  - Matrix
  - ggplot2
  - ggridges (optional, for ridge plots)
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "enrichment", "UCell", "U-statistic", "pathway-activity",
           "cross-dataset", "module-score", "R"]
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| UCell | >= 2.6.0 | Bioconductor |
| Seurat | >= 4.3.0 | Optional; v4 and v5 both supported |
| Matrix | | Sparse matrix support |
| ggplot2 | | Distribution plots |
| ggridges | optional | Ridge plots |

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install("UCell")
install.packages(c("Seurat", "Matrix", "ggplot2", "ggridges"))
```

> **Agent note:** UCell is also available from GitHub (`carmonalab/UCell`), but Bioconductor is the recommended source.

## Skill Overview

UCell calculates per-cell gene signature scores with the Mann-Whitney U statistic. It ranks genes per cell and tests whether the signature genes are enriched at the top of the ranking. Scores are bounded 0–1, making UCell especially useful for comparing signature activity across batches, samples, or studies.

**When to use:**
- You need fast per-cell pathway or signature activity scores.
- You want normalized 0–1 scores for cross-dataset comparison.
- Your gene sets are small to medium (10–200 genes).
- You prefer a Seurat-compatible module-score workflow.

**When NOT to use:**
- You need competitive over-representation or GSEA on DEG lists → use [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md) or [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md).
- You need TF activity inference from target-gene footprints → use [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md) or [bio-single-cell-enrichment-progeny-r](../bio-single-cell-enrichment-progeny-r/SKILL.md).
- You want multi-method consensus scores → use [bio-single-cell-enrichment-irgsea-r](../bio-single-cell-enrichment-irgsea-r/SKILL.md).
- You need built-in binarization of signature-positive cells → AUCell has richer threshold exploration; see [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/SKILL.md).

## Quick Selector

| Feature | UCell | vs AUCell | vs AddModuleScore |
|---------|-------|-----------|-------------------|
| **Algorithm** | Mann-Whitney U | AUC-based | Mean expression |
| **Speed** | Fast | Medium | Fastest |
| **Scores** | 0–1 normalized | 0–1 normalized | Unbounded, centered |
| **Cross-dataset** | Excellent | Good | Poor |
| **Dropout robustness** | High | High | Low |
| **Best for** | Cross-study comparison, small sets | Sparse data, binarization | Quick co-expression modules |

## Core Workflow

### Step 1: Prepare Data

**Input:** Expression matrix (genes x cells) or `Seurat` object.  
**Requirements:**
- Gene symbols as row names (e.g., `CD3D`, `VEGFA`).
- Named list of gene sets.
- UCell ranks genes internally, so raw counts or log-normalized data both work.

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

### Step 3: Run UCell

```r
source("scripts/r/run_ucell.R")

scores <- run_ucell(
  expr_matrix = seurat_obj,
  gene_sets = gene_sets,
  maxRank = 1500,
  ncores = 4
)
```

### Step 4: Add to Seurat and Visualize

```r
seurat_obj <- run_ucell_seurat(
  seurat_obj,
  gene_sets = gene_sets,
  prefix = "UCell.",
  ncores = 4
)

FeaturePlot(seurat_obj, features = "UCell.Hypoxia", reduction = "umap")
VlnPlot(seurat_obj, features = "UCell.T_cells", group.by = "cell_type")
```

## Complete Pipeline (Copy-Pasteable)

```r
library(Seurat)
library(UCell)

# 1. Load data
seurat_obj <- readRDS("your_data.rds")

# 2. Define signatures
gene_sets <- list(
  Hypoxia = c("VEGFA", "EGLN1", "CA9", "PGK1", "LDHA"),
  Glycolysis = c("HK2", "PFKFB3", "GAPDH", "ENO1", "PKM"),
  OXPHOS = c("NDUFS1", "SDHA", "UQCRC1", "COX4I1", "ATP5F1A")
)

# 3. Source skill wrapper
source("scripts/r/run_ucell.R")

# 4. Run UCell and add scores to Seurat
seurat_obj <- run_ucell_seurat(
  seurat_obj,
  gene_sets = gene_sets,
  prefix = "UCell.",
  maxRank = 1500,
  ncores = 4
)

# 5. Visualize
FeaturePlot(seurat_obj, features = "UCell.Hypoxia", reduction = "umap")
VlnPlot(seurat_obj, features = "UCell.Glycolysis", group.by = "cell_type")

# 6. Export scores
scores <- as.data.frame(seurat_obj@meta.data[, paste0("UCell.", names(gene_sets))])
export_ucell_results(scores, output_file = "ucell_scores.csv", format = "csv")
```

## Skill-Provided Functions

**Pipeline orchestration**
- `run_ucell(expr_matrix, gene_sets, maxRank, w_neg, chunk_size, ncores, force.gc, seed)` — run UCell scoring on a matrix or Seurat object.
- `run_ucell_seurat(seurat_obj, gene_sets, slot, prefix, ...)` — run UCell on a Seurat object and store scores in metadata.
- `AddModuleScore_UCell(seurat_obj, features, name, ...)` — convenience wrapper that mimics Seurat's `AddModuleScore` naming.

**Visualization & export**
- `plot_ucell_distribution(scores, group_vector, gene_set, plot_type)` — violin, box, or ridge plot of scores across groups.
- `export_ucell_results(scores, output_file, format)` — save scores as CSV/TSV/RDS.

## Official API — Agents Often Miss These

**1. `run_ucell()` accepts either a matrix or a Seurat object**

When a Seurat object is passed, the wrapper extracts the `data` slot/layer automatically (v4 uses `slot = "data"`, v5 uses `layer = "data"`).

```r
# Correct - pass Seurat object directly
scores <- run_ucell(seurat_obj, gene_sets)

# Also correct - pass matrix explicitly
expr_matrix <- GetAssayData(seurat_obj, layer = "data")
scores <- run_ucell(expr_matrix, gene_sets)
```

**2. `run_ucell()` returns a cells x gene-sets data frame**

```r
scores <- run_ucell(expr_matrix, gene_sets)
dim(scores)  # n_cells x n_gene_sets
head(scores$Hypoxia)
```

**3. `run_ucell_seurat()` adds metadata columns with prefix `UCell.` by default**

```r
seurat_obj <- run_ucell_seurat(seurat_obj, gene_sets, prefix = "UCell.")
seurat_obj$UCell.Hypoxia
```

**4. Native UCell also provides `ScoreSignatures_UCell()` and `AddModuleScore_UCell()`**

The skill defines its own `AddModuleScore_UCell()` that delegates to `run_ucell_seurat()`. If you call the native `UCell::AddModuleScore_UCell()` directly, column names use a `_UCell` suffix by default, which differs from the skill wrapper. Prefer the skill functions for a consistent prefix scheme.

**5. Reuse rankings for many signatures with `StoreRankings_UCell()`**

```r
rankings <- StoreRankings_UCell(seurat_obj, maxRank = 1500)
scores1 <- ScoreSignatures_UCell(rankings, features = gene_sets1)
scores2 <- ScoreSignatures_UCell(rankings, features = gene_sets2)
```

**6. UCell scores are bounded 0–1**

Higher values mean stronger enrichment of the signature genes among the top-ranked genes of a cell. Values near 0 mean no enrichment.

## Common Pitfalls

1. **Using ENSEMBL IDs instead of gene symbols**  
   Gene set names must match `rownames(expr_matrix)`. Convert IDs beforehand.

2. **Gene sets that are too large or too small**  
   UCell works best with 10–200 genes per set. The wrapper removes empty sets but does not enforce an upper size limit; very large sets dilute signal.

3. **Column-name mismatch between the skill wrapper and native UCell**  
   The skill's `AddModuleScore_UCell()` produces columns like `UCell_Hypoxia` (prefix + set name). Native `UCell::AddModuleScore_UCell()` produces `Hypoxia_UCell` by default. Verify names with `colnames(seurat_obj@meta.data)`.

4. **Forgetting to name gene sets**  
   `run_ucell()` stops with an error if `names(gene_sets)` is NULL.

5. **Ridge plots fail without `ggridges`**  
   Install `ggridges` before using `plot_type = "ridge"`.

6. **Scores depend on the ranking distribution of the input dataset**  
   Although UCell is robust, direct comparison across separately normalized datasets should be interpreted with care.

## Scenarios

### Scenario 1: Basic Scoring on a Matrix

```r
source("scripts/r/run_ucell.R")

scores <- run_ucell(
  expr_matrix = expr_matrix,
  gene_sets = gene_sets,
  maxRank = 1500,
  ncores = 4
)

head(scores)
```

### Scenario 2: Add Scores to Seurat and Visualize

```r
seurat_obj <- run_ucell_seurat(
  seurat_obj,
  gene_sets = gene_sets,
  prefix = "UCell.",
  ncores = 4
)

FeaturePlot(seurat_obj, features = "UCell.Hypoxia", reduction = "umap")
VlnPlot(seurat_obj, features = "UCell.T_cells", group.by = "cell_type")
```

### Scenario 3: Module-Score Style Naming

```r
seurat_obj <- AddModuleScore_UCell(
  seurat_obj,
  features = gene_sets,
  name = "UCell",
  ncores = 4
)

# Access as seurat_obj$UCell_Hypoxia
```

### Scenario 4: Distribution Plot Across Groups

```r
scores <- run_ucell(seurat_obj, gene_sets)

plot_ucell_distribution(
  scores = scores,
  group_vector = seurat_obj$cell_type,
  gene_set = "Hypoxia",
  plot_type = "violin"
)
```

### Scenario 5: Export Results

```r
scores <- run_ucell(seurat_obj, gene_sets)

export_ucell_results(scores, output_file = "ucell_scores.csv", format = "csv")
export_ucell_results(scores, output_file = "ucell_scores.tsv", format = "tsv")
export_ucell_results(scores, output_file = "ucell_scores.rds", format = "rds")
```

## Output Interpretation

| Score | Interpretation |
|-------|----------------|
| 0 | Signature genes are not enriched in top-ranked genes |
| 0.3–0.5 | Weak enrichment |
| 0.5–0.7 | Moderate enrichment |
| > 0.8 | Strong enrichment |

## Parameters

### `run_ucell()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expr_matrix` | matrix / Seurat | required | Expression matrix (genes x cells) or Seurat object |
| `gene_sets` | named list | required | Named list of gene sets |
| `maxRank` | integer | 1500 | Maximum gene rank considered; higher = more genes, slower but potentially more accurate |
| `w_neg` | numeric | 1 | Weight on negative genes in signature |
| `chunk_size` | integer | 100 | Cells processed simultaneously |
| `ncores` | integer | 1 | Parallel cores |
| `force.gc` | logical | FALSE | Force garbage collection |
| `seed` | integer | 123 | Random seed for reproducibility |

### `run_ucell_seurat()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object |
| `gene_sets` | named list | required | Named list of gene sets |
| `slot` | character | "data" | Assay slot/layer to use |
| `prefix` | character | "UCell." | Prefix for new metadata columns |
| `...` | | | Additional arguments passed to `run_ucell()` |

### `AddModuleScore_UCell()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object |
| `features` | named list | required | Named list of gene sets |
| `name` | character | "UCell" | Prefix for output columns |
| `...` | | | Additional arguments passed to `run_ucell()` |

### `plot_ucell_distribution()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scores` | data.frame | required | UCell scores (cells x gene sets) |
| `group_vector` | vector | required | Group labels per cell |
| `gene_set` | character | required | Gene set name to plot |
| `plot_type` | character | "violin" | "violin", "box", or "ridge" |

### `export_ucell_results()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `scores` | data.frame | required | UCell scores |
| `output_file` | character | required | Output file path |
| `format` | character | "csv" | "csv", "tsv", or "rds" |

## API Reference

| Function | Location | Description |
|----------|----------|-------------|
| `run_ucell()` | [run_ucell.R:44](scripts/r/run_ucell.R#L44) | Main UCell scoring |
| `run_ucell_seurat()` | [run_ucell.R:121](scripts/r/run_ucell.R#L121) | Seurat wrapper |
| `AddModuleScore_UCell()` | [run_ucell.R:166](scripts/r/run_ucell.R#L166) | Module-score style wrapper |
| `plot_ucell_distribution()` | [run_ucell.R:203](scripts/r/run_ucell.R#L203) | Distribution plots |
| `export_ucell_results()` | [run_ucell.R:256](scripts/r/run_ucell.R#L256) | Export scores |

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `gene_sets must be named` | Unnamed list passed | Add names to every gene set |
| `No valid gene sets provided` | All sets empty | Check gene set contents |
| `UCell package required` | UCell not installed | `BiocManager::install("UCell")` |
| Low scores for expected pathway | Gene IDs mismatch or too few genes | Verify gene symbols; use sets with 10+ genes |
| `ggridges package required` | Ridge plot without ggridges | `install.packages("ggridges")` |
| Seurat v5 slot error | `slot = "data"` not supported | The wrapper auto-detects v5 and uses `layer = "data"` |
| Column `UCell.Hypoxia` not found | Wrong prefix or skill/native mismatch | Check `colnames(seurat_obj@meta.data)` |

## Related Skills

- [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/SKILL.md) — AUCell single-method scoring (R)
- [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md) — decoupleR pathway/TF activity inference (R)
- [bio-single-cell-enrichment-irgsea-r](../bio-single-cell-enrichment-irgsea-r/SKILL.md) — Multi-method consensus scoring (R)
- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) — GSEApy ORA/GSEA/ssGSEA (Python)
- [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md) — Over-representation and GSEA (R)
- [bio-single-cell-enrichment-progeny-r](../bio-single-cell-enrichment-progeny-r/SKILL.md) — PROGENy pathway activity (R)

## References

1. Andreatta & Carmona (2021). UCell: Robust and scalable single-cell gene signature scoring. *Computational and Structural Biotechnology Journal*.
2. UCell Bioconductor: https://bioconductor.org/packages/UCell/
3. UCell GitHub: https://github.com/carmonalab/UCell
