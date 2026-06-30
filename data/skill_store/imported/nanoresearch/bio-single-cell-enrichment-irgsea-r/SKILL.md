---
name: bio-single-cell-enrichment-irgsea-r
description: Integrated multi-method gene set enrichment for single-cell data with RRA consensus scoring. Combines AUCell, UCell, singscore, ssgsea, and ssGSEA2, and provides Seurat integration, differential enrichment, heatmaps, and EMT scoring.
version: "2.1"
tool_type: r
primary_tool: irGSEA
supported_tools: [Seurat, ComplexHeatmap, RobustRankAggreg]
language: r
dependencies:
  - irGSEA (GitHub: GitHUBZJY/irGSEA)
  - Seurat >= 4.3.0, < 5.0.0
  - ComplexHeatmap
  - ggplot2
  - ggridges (optional)
system_requirements:
  - R >= 4.2.0
keywords: ["single-cell", "enrichment", "irGSEA", "multi-method", "RRA", "consensus", "EMT", "R"]
---

## Version Compatibility & Installation

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| irGSEA | Latest GitHub | `devtools::install_github("GitHUBZJY/irGSEA")` |
| Seurat | >= 4.3.0, < 5.0.0 | **Required v4.x**; irGSEA uses `slot` internally, incompatible with Seurat v5 layers |
| ComplexHeatmap | | For heatmap visualization |
| ggplot2 | | For custom plots |
| ggridges | optional | For ridge plots |

```r
if (!require("devtools", quietly = TRUE))
    install.packages("devtools")
devtools::install_github("GitHUBZJY/irGSEA")
install.packages(c("Seurat", "ComplexHeatmap", "ggplot2", "ggridges"))
```

> **Agent warning:** This skill requires **Seurat v4** (`SeuratObject < 5.0.0`). Passing a Seurat v5 object raises an explicit error. To use with v5 data, extract the count matrix manually and pass it to `run_irgsea()`.

## Skill Overview

irGSEA runs multiple single-cell gene set enrichment methods (AUCell, UCell, singscore, ssgsea, ssGSEA2) and integrates them with Robust Rank Aggregation (RRA) to produce consensus scores. It is suitable when you want method-robust signatures or need to compare scoring approaches.

**When to use:**
- You want consensus enrichment scores across multiple methods.
- You need to compare or validate different scoring methods on the same data.
- You want integrated differential enrichment between two groups.
- You are performing EMT scoring (M/E ratio) with the provided helper.

**When NOT to use:**
- You have **Seurat v5** objects and cannot downgrade or extract a matrix — use [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/SKILL.md), [bio-single-cell-enrichment-ucell-r](../bio-single-cell-enrichment-ucell-r/SKILL.md), or [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md) instead.
- You need a single fast method — use UCell or AUCell directly.
- You need over-representation analysis per cluster — use [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md).
- You need only pathway visualization without consensus — native irGSEA functions may be enough.

## Quick Selector

| Feature | irGSEA |
|---------|--------|
| **Methods** | AUCell, UCell, singscore, ssgsea, ssGSEA2 |
| **Integration** | RRA consensus |
| **Best for** | Consensus scoring, method comparison, EMT scoring |
| **Differential** | Built-in two-group differential enrichment |
| **Seurat support** | v4 only |

## Core Workflow

### Step 1: Prepare Data

**Input:** Expression matrix (genes x cells) or Seurat v4 object.  
**Requirements:**
- Gene symbols as row names.
- Named list of gene sets.
- Seurat v4 object if using `run_irgsea_seurat()`.

```r
library(Seurat)
seurat_obj <- readRDS("your_data_v4.rds")

# Or load a matrix
expr_matrix <- readRDS("expression_matrix.rds")  # genes x cells
```

### Step 2: Define Gene Sets

```r
gene_sets <- list(
  Hypoxia = c("VEGFA", "GLUT1", "CA9", "PGK1", "LDHA"),
  Glycolysis = c("HK2", "PFKFB3", "GAPDH", "ENO1", "PKM"),
  T_cells = c("CD3D", "CD3E", "CD4", "CD8A", "CD8B")
)
```

### Step 3: Run irGSEA

```r
source("scripts/r/run_irgsea.R")

results <- run_irgsea(
  expr_matrix = expr_matrix,
  gene_sets = gene_sets,
  methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
  minGSSize = 10,
  maxGSSize = 500,
  ncores = 4,
  rra_integration = TRUE
)

# Access scores
auc_scores <- results$AUCell
rra_scores <- results$RRA
```

### Step 4: Integrate with Seurat

```r
seurat_obj <- run_irgsea_seurat(
  seurat_obj,
  gene_sets = gene_sets,
  slot = "counts",
  method = c("AUCell", "UCell")
)

FeaturePlot(seurat_obj, features = "irGSEA.RRA.Hypoxia")
```

### Step 5: Differential Enrichment

```r
diff_results <- differential_enrichment(
  irgsea_results = results,
  group_vector = seurat_obj$condition,
  method = "RRA",
  test = "wilcoxon"
)

head(diff_results[diff_results$padj < 0.05, ])
```

## Complete Pipeline (Copy-Pasteable)

```r
library(Seurat)
library(irGSEA)

# 1. Load Seurat v4 object with annotations
seurat_obj <- readRDS("your_data_v4.rds")

# 2. Define gene sets
gene_sets <- list(
  Hypoxia = c("VEGFA", "EGLN1", "CA9", "PGK1", "LDHA"),
  Glycolysis = c("HK2", "PFKFB3", "GAPDH", "ENO1", "PKM"),
  OXPHOS = c("NDUFS1", "SDHA", "UQCRC1", "COX4I1", "ATP5F1A")
)

# 3. Source skill wrapper
source("scripts/r/run_irgsea.R")

# 4. Run irGSEA (returns list of score matrices, including RRA)
results <- run_irgsea(
  expr_matrix = seurat_obj,
  gene_sets = gene_sets,
  methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
  rra_integration = TRUE
)

# 5. Add scores to Seurat for visualization
seurat_obj <- run_irgsea_seurat(
  seurat_obj,
  gene_sets = gene_sets,
  slot = "counts",
  method = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
  rra_integration = TRUE
)

# 6. Visualize
FeaturePlot(seurat_obj, features = "irGSEA.RRA.Hypoxia", reduction = "umap")
VlnPlot(seurat_obj, features = "irGSEA.UCell.Glycolysis", group.by = "cell_type")

# 7. Differential enrichment between two conditions
diff_results <- differential_enrichment(
  irgsea_results = results,
  group_vector = seurat_obj$condition,
  method = "RRA",
  test = "wilcoxon"
)

# 8. Export
export_irgsea_results(results, output_dir = "./irgsea_results", prefix = "sample1")
```

## Skill-Provided Functions

**Pipeline orchestration**
- `run_irgsea(expr_matrix, gene_sets, methods, minGSSize, maxGSSize, ncores, rra_integration)` — run multiple scoring methods with optional RRA integration on a matrix.
- `run_irgsea_seurat(seurat_obj, gene_sets, slot, ...)` — run irGSEA on a Seurat v4 object and extract scores to metadata.

**Extraction & integration**
- `extract_irgsea_scores(seurat_obj, method, prefix)` — extract scores from an irGSEA assay to metadata columns.
- `extract_scores_internal(seurat_obj, method)` — internal helper used by `run_irgsea_seurat()`.

**Analysis**
- `differential_enrichment(irgsea_results, group_vector, method, test)` — two-group differential enrichment (wilcoxon or t.test).
- `calculate_emt_score(seurat_obj, mesenchymal_col, epithelial_col, method, new_col_name)` — compute EMT score as M/E ratio or M-E difference.

**Visualization & export**
- `plot_irgsea_heatmap(irgsea_results, method, group_vector, top_n)` — ComplexHeatmap of top variable gene sets.
- `export_irgsea_results(irgsea_results, output_dir, prefix)` — export each method's scores to CSV.

## Official API - Agents Often Miss These

**1. This skill requires Seurat v4**
`run_irgsea_seurat()` checks `SeuratObject` version and errors on v5. To use with v5:
```r
expr_matrix <- Seurat::GetAssayData(seurat_obj, layer = "counts")
results <- run_irgsea(expr_matrix, gene_sets = gene_sets)
```

**2. `run_irgsea()` returns a named list, not a Seurat object**
```r
results <- run_irgsea(expr_matrix, gene_sets)
results$AUCell   # cells x gene_sets
results$RRA      # cells x gene_sets (if rra_integration = TRUE)
```

**3. `run_irgsea_seurat()` adds metadata columns with prefix `irGSEA.<method>.<geneset>`**
```r
# Example column names
seurat_obj$irGSEA.UCell.Hypoxia
seurat_obj$irGSEA.RRA.Hypoxia
```

**4. RRA integration only runs when `length(methods) > 1`**
If you request only one method, `results$RRA` will not be created even if `rra_integration = TRUE`.

**5. `run_irgsea_seurat()` with custom gene sets uses `custom = TRUE`**
The wrapper passes `custom = TRUE` to `irGSEA::irGSEA.score()` when `gene_sets` is provided.

**6. `differential_enrichment()` requires exactly two groups**
`group_vector` must have exactly two unique values. Use ANOVA or other tests for more groups.

**7. `extract_irgsea_scores()` does not run irGSEA**
It only extracts already-computed assay scores to metadata. Call `run_irgsea_seurat()` first.

## Common Pitfalls

1. **Seurat v5 incompatibility**  
   The most common failure. Either downgrade to Seurat v4 or extract the matrix and use `run_irgsea()`.

2. **Gene set size filtering removes all sets**  
   Default `minGSSize = 10` and `maxGSSize = 500`. Small marker sets (< 10 genes) are silently removed.

3. **Forgetting that RRA needs at least two methods**  
   Request only AUCell and you will not get `results$RRA`.

4. **Mismatch between `run_irgsea()` and `run_irgsea_seurat()` outputs**  
   `run_irgsea()` returns a list of score matrices. `run_irgsea_seurat()` returns a Seurat object with metadata columns.

5. **Differential enrichment needs matching cell order**  
   `group_vector` length must equal `nrow(scores)`. Ensure no cells were filtered between scoring and testing.

6. **log2FC can be Inf/NaN with near-zero scores**  
   Some methods produce scores close to zero. Filter or winsorize before interpreting fold changes.

## Scenarios

### Scenario 1: Basic Multi-Method Scoring on a Matrix

```r
source("scripts/r/run_irgsea.R")

results <- run_irgsea(
  expr_matrix = expr_matrix,
  gene_sets = gene_sets,
  methods = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2"),
  ncores = 4,
  rra_integration = TRUE
)

# Access consensus
head(results$RRA)
```

### Scenario 2: Seurat v4 Integration

```r
seurat_obj <- run_irgsea_seurat(
  seurat_obj,
  gene_sets = gene_sets,
  slot = "counts",
  method = c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2")
)

FeaturePlot(seurat_obj, features = "irGSEA.RRA.T_cells")
```

### Scenario 3: Extract Specific Method Scores

```r
# If you ran irGSEA via run_irgsea_seurat() and want a different prefix
seurat_obj <- extract_irgsea_scores(seurat_obj, method = "UCell", prefix = "UCell")

# Now access as seurat_obj$UCell.Hypoxia
FeaturePlot(seurat_obj, features = "UCell.Hypoxia")
```

### Scenario 4: Differential Enrichment

Assumes `results` was generated by `run_irgsea()` (see Scenario 1).

```r
diff_results <- differential_enrichment(
  irgsea_results = results,
  group_vector = seurat_obj$condition,
  method = "RRA",
  test = "wilcoxon"
)

sig <- diff_results[diff_results$padj < 0.05, ]
print(sig[order(sig$padj), ])
```

### Scenario 5: Heatmap of Top Variable Gene Sets

```r
library(ComplexHeatmap)

hm <- plot_irgsea_heatmap(
  irgsea_results = results,
  method = "RRA",
  group_vector = seurat_obj$cell_type,
  top_n = 20
)
draw(hm)
```

### Scenario 6: Export All Scores

```r
export_irgsea_results(
  irgsea_results = results,
  output_dir = "./irgsea_results",
  prefix = "sample1"
)
```

Generates one CSV per method: `sample1_AUCell_scores.csv`, `sample1_RRA_scores.csv`, etc.

### Scenario 7: EMT Scoring (M/E Ratio)

For ready-to-use EMT gene sets (Epithelial, Mesenchymal, EMT_TFs, EMT_Hallmark), see [reference/emt_reference.md](reference/emt_reference.md).

```r
# Load the full EMT gene sets from the reference file
source("reference/emt_reference.R")

seurat_obj <- run_irgsea_seurat(
  seurat_obj,
  gene_sets = emt_gene_sets,
  slot = "counts",
  method = c("AUCell", "UCell"),
  rra_integration = TRUE
)

seurat_obj <- calculate_emt_score(
  seurat_obj,
  mesenchymal_col = "irGSEA.UCell.Mesenchymal",
  epithelial_col = "irGSEA.UCell.Epithelial",
  method = "ratio",
  new_col_name = "EMT_Score"
)

FeaturePlot(seurat_obj, features = "EMT_Score")
```

**EMT score interpretation:**

| Method | Formula | Interpretation |
|--------|---------|----------------|
| `ratio` | M / (E + 0.001) | > 1: mesenchymal-dominant; < 1: epithelial-dominant |
| `difference` | M - E | Positive: mesenchymal; negative: epithelial |

**EMT gene set design:**

A complete EMT analysis typically uses three complementary gene sets:

| Gene set | Representative markers | Biological meaning |
|----------|------------------------|--------------------|
| `Epithelial` | `CDH1`, `EPCAM`, `KRT8/18/19`, `OCLN`, `CLDN3/4/7` | Mature epithelial cell state |
| `Mesenchymal` | `CDH2`, `VIM`, `FN1`, `SNAI1/2`, `TWIST1`, `ZEB1/2`, `MMP2/9` | Mesenchymal / invasive state |
| `EMT_TFs` | `SNAI1`, `SNAI2`, `ZEB1`, `ZEB2`, `TWIST1`, `TWIST2` | Active EMT transcriptional drivers |

**Why include `EMT_TFs` as a separate set:**

1. **Early EMT detection** - Transcription factor changes often precede structural protein changes (e.g., Vimentin, N-cadherin), helping identify cells that are *starting* EMT.
2. **Distinguish driver vs. result** - Epithelial/Mesenchymal signatures reflect cell state (outcome), while EMT_TFs reflect active regulatory signaling (driver).
3. **Capture inter-tumor heterogeneity** - Some cells may score high on EMT_TFs without yet showing full mesenchymal morphology.

**Three common EMT states:**

| Mesenchymal (M) | Epithelial (E) | EMT_TFs | Interpretation |
|-----------------|----------------|---------|----------------|
| High | Low | High | Active EMT (mesenchymal transition) |
| Low | High | High | Early EMT (epithelial but responding to EMT signals) |
| High | Low | Low | Stable mesenchymal state (EMT completed) |

**Practical recommendations:**

- **TGF-β association:** TGF-β is a major upstream inducer of EMT_TFs. Co-checking TGF-β signaling can strengthen interpretation.
- **EMT_TFs high but Mesenchymal low** suggests early EMT; do not rely on M/E ratio alone.
- **EMT_TFs are usually analyzed separately**, not mixed into the EMT_score calculation. The M/E ratio is the standard EMT_score metric.
- **EMT_TFs help identify cells gaining invasive potential**, not only those that have already fully mesenchymalized.

**EMT_Hallmark vs. M/E ratio:**

| Metric | Gene set composition | What it measures | Best use case |
|--------|---------------------|------------------|---------------|
| `EMT_Hallmark` | Mixed E + M genes (e.g., `CDH1`, `VIM`, `SNAI1`, `KRT8`, `FN1`, ...) | Overall EMT-associated gene expression | "Does this cell express EMT-related genes?" |
| `EMT_score` (M/E ratio) | Separate M and E sets: `M / (E + 0.001)` | Relative balance between mesenchymal and epithelial programs | "What EMT stage is this cell in?" |


| Research question | Recommended metric |
|-------------------|-------------------|
| Does the cell have EMT characteristics? | `EMT_Hallmark` |
| Which EMT stage is the cell in? | `EMT_score` (M/E ratio) |
| Compare EMT degree between conditions (e.g., high vs. low NI) | `EMT_score` |
| Screen for EMT-positive cells | Combine `EMT_Hallmark` + `EMT_score` + `EMT_TFs` |

## Parameters

### `run_irgsea()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `expr_matrix` | matrix / Seurat | required | Expression matrix (genes x cells) or Seurat v4 object |
| `gene_sets` | named list | required | Named list of gene sets |
| `methods` | char vector | `c("AUCell", "UCell", "singscore", "ssgsea", "ssGSEA2")` | Methods to run |
| `minGSSize` | int | 10 | Minimum genes per set |
| `maxGSSize` | int | 500 | Maximum genes per set |
| `ncores` | int | 1 | Parallel cores |
| `rra_integration` | logical | TRUE | Compute RRA consensus (needs >= 2 methods) |

### `run_irgsea_seurat()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat v4 | required | Seurat v4 object |
| `gene_sets` | named list | NULL | Custom gene sets; if NULL, uses MSigDB built-ins |
| `slot` | char | "counts" | Assay slot to use |
| `...` | | | Additional arguments passed to `irGSEA::irGSEA.score()` |

### `differential_enrichment()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `irgsea_results` | list | required | Output from `run_irgsea()` |
| `group_vector` | vector | required | Two-group labels per cell |
| `method` | char | "RRA" | Which score matrix to test |
| `test` | char | "wilcoxon" | "wilcoxon" or "t.test" |

### `calculate_emt_score()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object with EMT scores in metadata |
| `mesenchymal_col` | char | required | Column name for mesenchymal score |
| `epithelial_col` | char | required | Column name for epithelial score |
| `method` | char | "ratio" | "ratio" (M/E) or "difference" (M-E) |
| `new_col_name` | char | "EMT_Score" | Output column name |

### `extract_irgsea_scores()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat object with irGSEA assays |
| `method` | char | "UCell" | Assay/method to extract |
| `prefix` | char | method name | Prefix for metadata columns |

### `plot_irgsea_heatmap()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `irgsea_results` | list | required | Output from `run_irgsea()` |
| `method` | char | "RRA" | Method to plot |
| `group_vector` | vector | NULL | Cell group annotation |
| `top_n` | int | 20 | Number of top variable gene sets |

### `export_irgsea_results()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `irgsea_results` | list | required | Output from `run_irgsea()` |
| `output_dir` | char | required | Output directory |
| `prefix` | char | "irgsea" | File prefix |

## Output Description

`run_irgsea()` returns a named list where each element is a **cells x gene_sets** score matrix:

| Element | Description |
|---------|-------------|
| `results$AUCell` | AUCell scores |
| `results$UCell` | UCell scores |
| `results$singscore` | singscore scores |
| `results$ssgsea` | ssgsea scores |
| `results$ssGSEA2` | ssGSEA2 scores |
| `results$RRA` | RRA consensus scores (if `rra_integration = TRUE` and >= 2 methods) |

`run_irgsea_seurat()` returns a Seurat object with new metadata columns:

| Column pattern | Example |
|----------------|---------|
| `irGSEA.<method>.<geneset>` | `irGSEA.UCell.Hypoxia` |
| `irGSEA.RRA.<geneset>` | `irGSEA.RRA.Hypoxia` |
| `EMT_Score` | After `calculate_emt_score()` |

`differential_enrichment()` returns a data frame:

| Column | Description |
|--------|-------------|
| `gene_set` | Gene set name |
| `group1`, `group2` | Compared groups |
| `group1_mean`, `group2_mean` | Mean scores |
| `log2FC` | log2 fold change |
| `pvalue`, `padj` | Raw and BH-adjusted p-values |

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `Seurat v5 detected...` | SeuratObject >= 5.0.0 | Use Seurat v4 or extract matrix and use `run_irgsea()` |
| `No valid gene sets after size filtering` | All sets smaller than `minGSSize` or larger than `maxGSSize` | Adjust thresholds or filter gene sets |
| `results$RRA is NULL` | Only one method requested or `rra_integration = FALSE` | Request >= 2 methods with `rra_integration = TRUE` |
| `Length of group_vector must match number of cells` | Group labels do not match score matrix | Ensure same cells and no reordering |
| `Differential enrichment requires exactly 2 groups` | More or fewer than 2 unique labels | Subset to two groups or use another test |
| `Column 'irGSEA.UCell.X' not found` | Wrong method prefix or score not computed | Check available metadata columns with `colnames(seurat_obj@meta.data)` |
| Heatmap fails | ComplexHeatmap not installed | `BiocManager::install("ComplexHeatmap")` |

## Related Skills

- [bio-single-cell-enrichment-aucell-r](../bio-single-cell-enrichment-aucell-r/SKILL.md) - AUCell single-method scoring (R)
- [bio-single-cell-enrichment-ucell-r](../bio-single-cell-enrichment-ucell-r/SKILL.md) - UCell fast scoring (R)
- [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md) - decoupleR multi-method (R)
- [bio-single-cell-enrichment-gseapy](../bio-single-cell-enrichment-gseapy/SKILL.md) - GSEApy methods (Python)
- [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md) - Over-representation and GSEA (R)
- [bio-single-cell-enrichment-progeny-r](../bio-single-cell-enrichment-progeny-r/SKILL.md) - TF activity inference (R)

## References

1. Zhang et al. (2023). irGSEA: a comprehensive package for single-cell gene set enrichment analysis. *Bioinformatics*.
2. Kolde et al. (2012). Robust rank aggregation for gene list integration and meta-analysis. *Bioinformatics*.
3. irGSEA documentation: https://github.com/GitHUBZJY/irGSEA
