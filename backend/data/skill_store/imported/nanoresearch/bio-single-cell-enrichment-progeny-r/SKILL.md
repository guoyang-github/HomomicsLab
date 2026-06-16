---
name: bio-single-cell-enrichment-progeny-r
description: |
  PROGENy estimates signaling pathway activity from gene expression using footprint-based analysis.
  Uses pathway-responsive genes derived from perturbation experiments to infer 14 pathway activities
  (MAPK, PI3K, TGFb, TNFa, NFkB, etc.). Supports Human and Mouse. Input requires normalized
  gene expression with HGNC/MGI symbols. Output is pathway activity scores per cell.
tool_type: r
primary_tool: progeny
languages: [r]
keywords: ["single-cell", "pathway", "enrichment", "progeny", "signaling", "footprint",
           "MAPK", "PI3K", "TGFb", "R"]
---

## Version Compatibility

| Package | Required Version | Notes |
|---------|-----------------|-------|
| R | >= 4.2.0 | |
| progeny | >= 1.20.0 | Bioconductor; tested on 1.32.0 |
| Seurat | >= 4.0.0 | v4 and v5 both supported |
| Bioconductor | >= 3.16 | |
| ggplot2 | >= 3.3.0 | Visualization |
| pheatmap | >= 1.0.0 | Heatmaps |
| patchwork | >= 1.1.0 | Multi-panel plots |
| ggridges | >= 0.5.0 | Optional; ridge plots |

## Installation

```r
if (!requireNamespace("BiocManager", quietly = TRUE))
  install.packages("BiocManager")
BiocManager::install("progeny")

# Additional dependencies
install.packages(c("Seurat", "ggplot2", "pheatmap", "patchwork"))
install.packages(c("ggridges", "dplyr"))  # optional, for advanced plots
```

## Skill Overview

PROGENy (Pathway RespOnsive GENes) estimates signaling pathway activity from gene expression using footprint-based analysis. It uses pathway-responsive genes derived from large-scale perturbation experiments to infer activities of 14 key pathways.

**Core workflow**: Validate input -> Run PROGENy scoring -> Add to metadata -> Visualize -> Differential analysis

**When to use:**
- Pathway activity inference from scRNA-seq or bulk RNA-seq
- Single-cell pathway analysis: map activities onto cell types and states
- Condition comparison: compare pathway activities between treatments, time points, or disease states
- Cell type characterization: identify which pathways drive specific cell populations
- Cross-talk analysis: study correlations between different signaling pathways

**When NOT to use:**
- No single-cell or bulk expression reference available (PROGENy requires gene expression input)
- Gene symbols are not HGNC (Human) or MGI (Mouse) -> re-annotate gene symbols first
- Very small gene overlap (<50 shared genes with PROGENy model) -> results unreliable
- Need probabilistic uncertainty estimates -> use decoupleR or VIPER instead

**Input requirements:**
- Seurat object (recommended) with normalized expression, or matrix/data.frame (genes in rows)
- Gene symbols: HGNC for Human, MGI for Mouse
- Expression values: normalized counts (log-transformed recommended)
- Minimum gene overlap: >50% of PROGENy model genes should be present

```r
source("scripts/r/utils.R")
overlap <- validate_gene_overlap(rownames(seurat_obj), organism = "Human")
# Check overlap$overlap_fraction > 0.5 for reliable results
```

## Core Workflow

### Step 1 -- Validate Input & Gene Overlap

**Input**: Seurat object or expression matrix
**Output**: Validation result + gene overlap statistics

```r
source("scripts/r/utils.R")
check_progeny_input(seurat_obj)
overlap <- validate_gene_overlap(rownames(seurat_obj), organism = "Human")
```

**How it works:**
1. Checks input type (Seurat / matrix / data.frame / SingleCellExperiment)
2. Computes overlap between input genes and PROGENy model genes
3. Reports overlap fraction and matched gene count

**State after Step 1:** Input validated. `overlap$overlap_fraction` should be > 0.5.

| Parameter | Default | What It Does | When to Change |
|-----------|---------|--------------|----------------|
| `organism` | `"Human"` | Gene symbol convention | `"Mouse"` for murine data |
| `top` | `100` | Top responsive genes per pathway | `200-500` for noisy/small data; `50` for clean data |

---

### Step 2 -- Run PROGENy Pathway Scoring

**Input**: Validated Seurat object or expression matrix
**Output**: Seurat with `progeny` assay, or raw score matrix (samples x 14 pathways)

```r
source("scripts/r/core_analysis.R")
seurat_obj <- run_progeny(
  seurat_obj,
  organism = "Human",
  top = 100,
  scale = FALSE,
  assay_name = "RNA",
  return_assay = TRUE,
  verbose = TRUE
)
```

**How it works:**
1. Extracts expression matrix manually (Seurat v4 `slot="data"` / v5 `layer="data"`)
2. Converts sparse matrix to dense (`as.matrix()`)
3. Calls `progeny::progeny()` with footprint-based scoring
4. Creates new `"progeny"` assay in Seurat object

**Key decisions:**
- **`scale`**: Use `FALSE` for single-cell (preserves cell-to-cell variation), `TRUE` for bulk/pseudobulk
- **`top`**: 100 is standard. Use 200-500 for noisy/small datasets (<100 cells). Use 50 for very clean data.
- **`return_assay`**: `TRUE` for Seurat workflow (adds assay). `FALSE` to get raw matrix.

**State after Step 2:** `seurat_obj` has new `"progeny"` assay with 14 pathway scores per cell.

---

### Step 3 -- Add Scores to Metadata

**Input**: Seurat object with `progeny` assay
**Output**: Seurat object with `PROGENy_*` metadata columns

```r
seurat_obj <- add_progeny_to_metadata(seurat_obj, prefix = "PROGENy_")
# Access: seurat_obj$PROGENy_MAPK, seurat_obj$PROGENy_PI3K, etc.
```

**State after Step 3:** Pathway scores accessible as metadata columns for Seurat plotting functions.

---

### Step 4 -- Visualize Pathway Activity

**Input**: Seurat object with progeny assay or metadata
**Output**: ggplot / pheatmap objects

```r
source("scripts/r/visualization.R")

# Embedding plots
plot_pathway_embedding(seurat_obj, pathways = c("MAPK", "PI3K"), reduction = "umap")

# Heatmap by group
plot_pathway_heatmap(seurat_obj, group.by = "seurat_clusters", scale = "row")

# Violin plots
plot_pathway_violin(seurat_obj, pathways = c("MAPK", "TGFb"), group.by = "cell_type")

# Correlation matrix
plot_pathway_correlation(seurat_obj, method = "pearson")
```

**State after Step 4:** Publication-ready figures generated.

---

### Step 5 -- Differential Pathway Analysis

**Input**: Seurat object with progeny assay + grouping metadata
**Output**: Data frame with differential pathway markers or condition comparisons

```r
# Differential markers between clusters
pathway_markers <- find_pathway_markers(
  seurat_obj, group.by = "seurat_clusters",
  assay = "progeny", min.pct = 0, logfc.threshold = 0
)

# Average activity by group
avg_activity <- average_pathway_activity(
  seurat_obj, group.by = "condition", use_metadata = TRUE, prefix = "PROGENy_"
)

# Cross-condition comparison
scores <- t(as.matrix(seurat_obj[["progeny"]]@data))
comparison <- compare_pathway_conditions(
  scores, metadata = seurat_obj@meta.data,
  condition_col = "treatment", condition1 = "control", condition2 = "treated",
  method = "wilcox"
)
```

**State after Step 5:** Differential pathway results ready for interpretation and export.

## Complete Pipeline

```r
library(Seurat)
library(ggplot2)
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# 1. Load & validate
seurat_obj <- readRDS("data.rds")
overlap <- validate_gene_overlap(rownames(seurat_obj), organism = "Human")

# 2. Run PROGENy
seurat_obj <- run_progeny(seurat_obj, organism = "Human", top = 100, scale = FALSE)

# 3. Add metadata
seurat_obj <- add_progeny_to_metadata(seurat_obj, prefix = "PROGENy_")

# 4. Visualize
plot_pathway_embedding(seurat_obj, pathways = c("MAPK", "PI3K"))
plot_pathway_heatmap(seurat_obj, group.by = "seurat_clusters")

# 5. Differential analysis
pathway_markers <- find_pathway_markers(seurat_obj, group.by = "seurat_clusters")

# 6. Export
export_progeny_results(seurat_obj, output_dir = "progeny_results")
```

Shortcut: `run_progeny()` wraps input validation, expression extraction, and assay creation in one call.

## Skill-Provided Functions

### Core Analysis
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `run_progeny()` | Run PROGENy scoring | Cross-version Seurat support (v4/v5); sparse->dense conversion; `scale=FALSE` default for scRNA-seq |
| `run_progeny_permutation()` | Permutation-based significance | Wraps `progeny()` with permutations; handles data.frame->matrix conversion |
| `get_progeny_model_info()` | Model statistics per pathway | Reports n_genes, mean_weight, sd per pathway |
| `add_progeny_to_metadata()` | Add scores as metadata columns | Enables Seurat-native plotting functions |
| `find_pathway_markers()` | Differential pathway markers | Wraps `Seurat::FindAllMarkers` on pathway assay |
| `average_pathway_activity()` | Average activity per group | Aggregates by group with optional metadata columns |
| `compare_pathway_conditions()` | Statistical comparison between conditions | Supports t.test and wilcox; returns p-values and effect sizes |
| `export_progeny_results()` | Export scores and metadata CSVs | Batch export with configurable prefix |

### Visualization
| Function | Purpose | Key Value Over Native |
|----------|---------|----------------------|
| `plot_pathway_embedding()` | FeaturePlot on UMAP/t-SNE | Multi-panel via patchwork; auto-filters missing pathways |
| `plot_pathway_heatmap()` | Average-per-group heatmap | Wraps pheatmap with defaults for pathway data |
| `plot_pathway_violin()` | Violin plots by group | Wraps `Seurat::VlnPlot` for pathway assay |
| `plot_pathway_correlation()` | Pathway correlation heatmap | Pearson/Spearman/Kendall support |
| `plot_pathway_summary()` | Combined summary (embedding + violin) | Single-call publication panel |

### Utilities
| Function | Purpose |
|----------|---------|
| `validate_gene_overlap()` | Check gene overlap with PROGENy model |
| `get_extreme_pathway_cells()` | Find cells with extreme pathway activity |
| `recommend_top_parameter()` | Recommend `top` value based on dataset size |
| `create_progeny_report()` | Generate text summary report |

## Official API -- Agents Often Miss These

```r
# Core scoring
progeny::progeny(
  expr,                    # Expression matrix: genes (rows) x samples (cols)
  scale = TRUE,            # Default TRUE (use FALSE for single-cell)
  organism = "Human",      # "Human" or "Mouse"
  top = 100,               # Top responsive genes per pathway
  perm = 1,                # Permutations (1 = no permutation)
  verbose = FALSE,
  z_scores = FALSE,        # Return z-scores (only when perm > 1)
  get_nulldist = FALSE,    # Return null distributions (only when perm > 1)
  ...
)

# Retrieve model matrix
progeny::getModel(organism = "Human", top = 100, decoupleR = FALSE)

# Gene contribution scatter plots
progeny::progenyScatter(expr, weight_matrix, statName = "Expression")
```

### Result structure

**`progeny::progeny()` return types:**

| Scenario | Return type | Structure |
|----------|------------|-----------|
| `perm = 1` | Matrix | Samples (rows) x Pathways (cols); 14 pathways |
| `perm > 1`, `get_nulldist = FALSE` | Matrix | Same as above, but values are significance-adjusted |
| `perm > 1`, `get_nulldist = TRUE` | **List** | `[[1]]` scores (data.frame), `[[2]]` null distributions |

**Skill wrapper `run_progeny()` with Seurat:**
- Returns modified Seurat object with new `"progeny"` assay
- `seurat_obj[["progeny"]]` assay: `data` slot contains pathway scores (pathways x cells)
- Metadata columns added by `add_progeny_to_metadata()`: `PROGENy_MAPK`, `PROGENy_PI3K`, etc.

**14 PROGENy pathways:**

| Pathway | Biological Process |
|---------|-------------------|
| Androgen | Hormone response |
| EGFR | Growth, proliferation |
| Estrogen | Hormone response |
| Hypoxia | Oxygen sensing |
| JAK-STAT | Immune response, cytokine |
| MAPK | Growth, differentiation |
| NFkB | Inflammation, immunity |
| PI3K | Survival, metabolism |
| TGFb | Differentiation, EMT |
| TNFa | Inflammation, apoptosis |
| Trail | Apoptosis |
| VEGF | Angiogenesis |
| WNT | Development, stemness |
| p53 | DNA damage, apoptosis |

## Common Pitfalls

1. **Warning Native `scale = TRUE` is wrong for single-cell**
   The native `progeny::progeny()` defaults to `scale = TRUE`, which z-scores per pathway across all cells. For single-cell, this destroys cell-to-cell variation. The skill wrapper sets `scale = FALSE` by default. Always use `scale = FALSE` for scRNA-seq.

2. **Warning Seurat v5 incompatibility in native progeny**
   Native `progeny::progeny()` calls `GetAssayData(..., slot = "data")` internally, which is **defunct** in Seurat v5. Use the skill's `run_progeny()` wrapper, which detects Seurat version and uses `layer = "data"` (v5) or `slot = "data"` (v4) manually.

3. **Warning Sparse matrix incompatibility**
   Native `progeny::progeny()` does NOT accept `dgCMatrix` sparse matrices. The wrapper converts sparse to dense with `as.matrix()` automatically.

4. **Warning `perm > 1` changes return type unexpectedly**
   When `perm > 1` and `get_nulldist = TRUE`, the return is a **list** `[[1]]` scores, `[[2]]` null distributions. Do NOT pass this directly to `CreateAssayObject(data = t(perm_results))`.

5. **Warning Gene naming must be HGNC (Human) or MGI (Mouse)**
   PROGENy models use standard gene symbols. If your data uses Ensembl IDs or other conventions, map to symbols first. Use `validate_gene_overlap()` to check before running.

6. **Warning Low gene overlap (<50%) produces unreliable scores**
   If `overlap_fraction < 0.5`, re-check gene naming, organism parameter, and data quality. Some dropout in scRNA-seq is normal, but very low overlap means most model genes are missing.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Error: The slot argument of GetAssayData() was deprecated...` | Using native `progeny::progeny()` on Seurat v5 | Use skill's `run_progeny()` wrapper |
| `Error: Do not know how to access the data matrix from class dgCMatrix` | Passing sparse matrix to native progeny | Use `run_progeny()` which calls `as.matrix()` |
| `Error: object 'high_mapk' not found` | Running `advanced_example.R` as-is | Example is commented skeleton; uncomment and define variables |
| `Error: could not find function "wrap_plots"` | patchwork not loaded | `library(patchwork)` |
| `Warning: Layer counts isn't present in the assay object` | Seurat v5 warning when adding assay without counts layer | Harmless; progeny assay only needs data layer |
| `pathway not found in default search locations, found in 'progeny' assay instead` | Seurat v5 searches default assay first | Harmless; Seurat finds pathway in progeny assay |
| All scores look similar across cells | `scale = TRUE` or wrong `top` value | Set `scale = FALSE`; try `top = 200` or `top = 50` |

## Related Skills

- [bio-single-cell-enrichment-decoupler-r](../bio-single-cell-enrichment-decoupler-r/SKILL.md) -- Alternative pathway enrichment using decoupleR
- [bio-single-cell-enrichment-clusterprofiler-r](../bio-single-cell-enrichment-clusterprofiler-r/SKILL.md) -- ORA/GSEA enrichment analysis
- [bio-single-cell-trajectory-monocle3-r](../bio-single-cell-trajectory-monocle3-r/SKILL.md) -- Trajectory analysis with pathway dynamics

## References

1. Schubert et al. (2018). Perturbation-response genes reveal signaling footprints in cancer gene expression. *Nature Communications*, 9:20. https://doi.org/10.1038/s41467-017-02391-6
2. Holland et al. (2020). Robustness of gene expression signatures towards low-input RNA-seq and active ingredient determination in colorectal cancer. *Genome Medicine*, 12:76. https://doi.org/10.1186/s13059-020-1949-z
3. PROGENy Bioconductor: https://bioconductor.org/packages/progeny/
4. PROGENy GitHub: https://github.com/saezlab/progeny
