---
name: bio-single-cell-trajectory-monocle3-r
description: Single-cell trajectory inference and pseudotime analysis using Monocle3 (v1.4.25+). Reversed graph embedding for ordering cells along developmental trajectories, branch detection, gene dynamics (Moran's I), gene module detection, batch correction (align_cds), and BPCells support for large datasets.
tool_type: r
primary_tool: monocle3
supported_tools: [Bioconductor, Seurat, ggplot2, plotly]
languages: [r]
keywords: ["single-cell", "trajectory", "pseudotime", "monocle3", "R", "development", "lineage", "branching", "gene-dynamics", "batch-correction", "gene-modules"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.2.0"
  monocle3: ">=1.4.25"
  bioconductor: ">=3.17"
---

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| monocle3 | >= 1.4.25 | Core package; install via BiocManager |
| Bioconductor | >= 3.17 | Package repository |
| Seurat | >= 4.3.0 | Optional: **v4 and v5 both supported** via `layer=` vs `slot=` detection |
| plotly | >= 4.9.0 | Optional: 3D visualization |

**Seurat v5 compatibility**: `cds_from_seurat()` automatically detects SeuratObject >= 5.0.0 and uses `layer = "counts"` instead of `slot = "counts"`.

## Installation

```r
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install("monocle3")
```

## Skill Overview

Monocle3 uses reversed graph embedding to learn a principal graph representing cell developmental trajectories, orders cells by pseudotime, identifies branching points, analyzes gene expression dynamics, and supports batch correction and gene module detection.

**Core workflow**: `new_cell_data_set()` → `preprocess_cds()` → `reduce_dimension()` → `cluster_cells()` → `learn_graph()` → `order_cells()` → `graph_test()` / `find_gene_modules()`

**When to use**: developmental trajectories, differentiation studies, reprogramming time-course, disease progression, any data with temporal/hierarchical structure.

## Quick Reference: Method Selection

| Goal | Primary Function | Notes |
|------|-----------------|-------|
| Basic trajectory | `run_trajectory_analysis()` | End-to-end pipeline wrapper |
| Batch correction | `align_cds()` | **MUST run BEFORE `preprocess_cds()`** |
| Find variable genes | `graph_test()` + `find_trajectory_variable_genes()` | Moran's I spatial autocorrelation |
| Gene modules | `find_gene_modules()` | UMAP + Louvain on genes |
| Model expression | `fit_models()` + `evaluate_fits()` | GLM with pseudotime |
| 3D visualization | `reduce_dimension(max_components = 3)` | Then `plot_cells_3d()` |
| Large datasets | `set_matrix_control(matrix_class = "BPCells")` | On-disk storage |

## Core Workflow (Step-by-Step)

Load skill helpers before using convenience functions:

```r
source("scripts/r/core_analysis.R")
source("scripts/r/utils.R")
source("scripts/r/visualization.R")
```

### Step 1: Create Cell Data Set (CDS)

**Goal**: Convert raw data into a monocle3 `cell_data_set` object.

**Input**: Expression matrix (genes × cells), cell metadata, gene metadata
**Output**: `cell_data_set` object

#### Option A: From count matrix

```r
cds <- new_cell_data_set(
  expression_data = counts_matrix,
  cell_metadata = cell_metadata,
  gene_metadata = gene_metadata
)
```

#### Option B: From Seurat (v4/v5 auto-detected)

```r
cds <- cds_from_seurat(seurat_obj, assay = "RNA")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `seurat_obj` | Seurat | required | Seurat v4 or v5 object |
| `assay` | string | "RNA" | Assay to extract |

#### Option C: From SingleCellExperiment

```r
cds <- cds_from_sce(sce)
```

#### Option D: From 10x Cell Ranger

```r
cds <- monocle3::load_cellranger_data(dir_path = "./filtered_gene_bc_matrices")
```

#### Option E: From MTX

```r
cds <- monocle3::load_mtx_data(
  mtx_file = "matrix.mtx",
  feature_file = "features.tsv",
  barcode_file = "barcodes.tsv"
)
```

#### Option F: Using skill helper with NULL-safe defaults

```r
cds <- create_cds(expression_matrix, cell_metadata, gene_metadata)
# NULL metadata auto-creates cell_id / gene_short_name columns
```

---

### Step 2: Quality Control

**Goal**: Filter low-quality cells and estimate size factors.

```r
cds <- detect_genes(cds, min_expr = 0.1)
cds <- estimate_size_factors(cds)

# Access normalized counts
norm_counts <- normalized_counts(cds)
head(size_factors(cds))
```

---

### Step 3: Batch Correction (Optional)

**Goal**: Remove batch effects before dimensionality reduction.

**⚠️ CRITICAL: `align_cds()` MUST run BEFORE `preprocess_cds()`**

```r
cds <- align_cds(cds, alignment_group = "batch")
cds <- preprocess_cds(cds, num_dim = 50)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `alignment_group` | string | required | Metadata column defining batches |
| `residual_model_formula_str` | string | NULL | Additional covariates (e.g. `~ batch + condition`) |

---

### Step 4: Preprocess

**Goal**: Normalize, select genes, and run PCA.

```r
cds <- preprocess_cds(cds, num_dim = 50)
plot_pc_variance_explained(cds)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `num_dim` | int | 50 | Number of PCs. Small data: 30-50; large: 100-200 |
| `norm_method` | string | "log" | "log" or "size_only" |
| `residual_model_formula_str` | string | NULL | Regress out covariates |

---

### Step 5: Reduce Dimensions

**Goal**: Compute UMAP (or tSNE/PCA) embedding.

```r
cds <- reduce_dimension(cds,
                        reduction_method = "UMAP",
                        max_components = 2,
                        umap.n_neighbors = 15,
                        umap.min_dist = 0.1)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reduction_method` | string | "UMAP" | "UMAP", "tSNE", or "PCA" |
| `max_components` | int | 2 | 2 or 3 (for 3D) |
| `umap.n_neighbors` | int | 15 | Local vs global balance |
| `umap.min_dist` | float | 0.1 | Cluster tightness |

---

### Step 6: Cluster Cells

**Goal**: Identify cell groups.

```r
cds <- cluster_cells(cds, resolution = 1e-5)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `resolution` | float | 1e-5 | Higher = more clusters. Try `c(10^seq(-6, -1))` |
| `k` | int | 20 | Nearest neighbors |
| `cluster_method` | string | "leiden" | "leiden" or "louvain" |

---

### Step 7: Learn Trajectory Graph

**Goal**: Learn principal graph representing cell trajectories.

```r
cds <- learn_graph(cds, use_partition = TRUE, close_loop = FALSE)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_partition` | bool | TRUE | Constrain graph within partitions |
| `close_loop` | bool | FALSE | Allow closed loops |

---

### Step 8: Order Cells by Pseudotime

**Goal**: Assign pseudotime values along trajectories.

**⚠️ CRITICAL: In non-interactive sessions, you MUST specify `root_cells` or `root_pr_nodes`. Without roots, `order_cells()` opens an interactive Shiny app that will hang.**

```r
# Method 1: Specify root cells
cds <- order_cells(cds, root_cells = root_cell_ids)

# Method 2: Specify root principal nodes
cds <- order_cells(cds, root_pr_nodes = "Y_21")

# Method 3: Programmatic root selection from metadata
cds <- order_cells(cds,
                   root_pr_nodes = get_earliest_principal_node(
                     cds, time_bin_col = "embryo.time.bin",
                     time_bin_value = "130-170"
                   ))
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `root_cells` | character vector | NULL | Cell IDs of root cells |
| `root_pr_nodes` | character vector | NULL | Principal graph node names |

---

### Step 9: Find Trajectory-Variable Genes

**Goal**: Identify genes whose expression varies along pseudotime.

```r
# Official function
test_res <- graph_test(cds, neighbor_graph = "principal_graph", cores = 4)
sig_genes <- subset(test_res, q_value < 0.05)

# Skill helper: graph_test + q-value + Moran's I filter
sig_genes <- find_trajectory_variable_genes(cds,
                                            q_value_threshold = 0.05,
                                            morans_I_threshold = 0,
                                            cores = 4)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `neighbor_graph` | string | "principal_graph" | "principal_graph" (faster, less memory) or "knn" |
| `cores` | int | 1 | Parallel cores |

**Memory tip**: Large datasets may OOM with `neighbor_graph = "knn"`; use `"principal_graph"` instead.

---

### Step 10: Gene Expression Modeling

**Goal**: Fit GLMs to gene expression along pseudotime.

```r
cds_subset <- cds[rownames(sig_genes)[1:10], ]

# Fit models
gene_fits <- fit_models(cds_subset,
                        model_formula_str = "~pseudotime",
                        expression_family = "quasipoisson",
                        cores = 1)

# Evaluate quality
eval_res <- evaluate_fits(gene_fits)  # AIC, BIC, deviance, logLik

# Get coefficients
coefs <- coefficient_table(gene_fits)
sig_coefs <- coefs %>% dplyr::filter(q_value < 0.05)
# Optional: filter by specific term
# sig_coefs <- sig_coefs %>% dplyr::filter(term == "pseudotime")

# Compare nested models
full <- fit_models(cds_subset, model_formula_str = "~pseudotime + batch")
reduced <- fit_models(cds_subset, model_formula_str = "~pseudotime")
comparison <- compare_models(full, reduced)

# Predict expression
preds <- model_predictions(gene_fits)
```

**Expression families**: `"quasipoisson"` (default, fast), `"negbinomial"` (accurate, slower), `"poisson"`, `"binomial"` (for ATAC-seq).

---

### Step 11: Gene Module Analysis

**Goal**: Find co-expressed gene modules across trajectories.

```r
gene_module_df <- find_gene_modules(cds[rownames(sig_genes), ],
                                    resolution = 1e-3,
                                    max_components = 2,
                                    k = 20)

# Aggregate module expression per cell group
cell_group_df <- data.frame(
  cell = colnames(cds),
  cell_group = clusters(cds)
)
agg_mat <- aggregate_gene_expression(cds, gene_module_df, cell_group_df)

# Plot modules
plot_cells(cds,
           genes = gene_module_df %>% dplyr::filter(module %in% c(1, 2)),
           label_cell_groups = FALSE,
           show_trajectory_graph = FALSE)
```

---

### Step 12: Visualization

```r
# Basic pseudotime plot
plot_cells(cds, color_cells_by = "pseudotime", show_trajectory_graph = TRUE)

# Clean trajectory view
plot_cells(cds, label_cell_groups = FALSE,
           label_leaves = TRUE, label_branch_points = TRUE,
           show_trajectory_graph = TRUE, cell_size = 0.5)

# Multi-panel features
plot_trajectory_features(cds, c("cluster", "batch"))

# Custom histogram
plot_pseudotime_distribution(cds, group_by = "cluster")

# 3D (requires max_components = 3)
cds_3d <- reduce_dimension(cds, max_components = 3)
cds_3d <- learn_graph(cds_3d)
cds_3d <- order_cells(cds_3d, root_pr_nodes = roots)
plot_trajectory_3d(cds_3d, color_cells_by = "pseudotime")
```

---

### Step 13: Export Results

```r
# Export pseudotime + metadata
export_pseudotime_data(cds, "pseudotime_data.csv")

# Export significant DE genes
sig_genes <- subset(test_res, q_value < 0.05)
write.csv(sig_genes, "trajectory_de_genes.csv", row.names = FALSE)
```

---

## Complete Pipeline via Skill Wrapper

```r
source("scripts/r/core_analysis.R")
source("scripts/r/visualization.R")
source("scripts/r/utils.R")

# From Seurat
cds <- cds_from_seurat(seurat_obj)

# Or from matrix
cds <- create_cds(counts_matrix, cell_metadata, gene_metadata)

# End-to-end analysis
cds <- run_trajectory_analysis(cds,
                               num_dim = 50,
                               reduction_method = "UMAP",
                               root_cells = root_ids)

# Visualize
plot_cells(cds, color_cells_by = "pseudotime", show_trajectory_graph = TRUE)
plot_cells(cds, label_cell_groups = FALSE,
           label_leaves = TRUE, label_branch_points = TRUE,
           show_trajectory_graph = TRUE, cell_size = 0.5)

# Find variable genes
sig_genes <- find_trajectory_variable_genes(cds, cores = 4)

# Export
export_pseudotime_data(cds, "pseudotime.csv")
```

---

## Skill-Provided Helper Functions

Source: `scripts/r/core_analysis.R`, `scripts/r/utils.R`, `scripts/r/visualization.R`

### Data Creation & Conversion (`core_analysis.R`)

| Function | Parameters | What it adds |
|----------|-----------|-------------|
| `create_cds(expr, cell_meta, gene_meta)` | `cell_meta`, `gene_meta` optional | NULL-metadata defaults |
| `cds_from_seurat(seurat_obj, assay = "RNA")` | Auto-detects v4 (`slot=`) vs v5 (`layer=`) | Seurat conversion |
| `cds_from_sce(sce)` | — | SCE conversion with `gene_short_name` fix |

### Pipeline & Analysis (`core_analysis.R`)

| Function | Parameters | What it adds |
|----------|-----------|-------------|
| `run_trajectory_analysis(cds, num_dim = 50, reduction_method = "UMAP", cluster_resolution = 1e-5, root_cells = NULL, root_pr_nodes = NULL)` | All optional except `cds` | End-to-end: preprocess → reduce → cluster → graph → order |
| `get_earliest_principal_node(cds, time_bin_col, time_bin_value)` | — | Programmatic root selection from metadata time-bin |
| `find_trajectory_variable_genes(cds, q_value_threshold = 0.05, morans_I_threshold = 0, cores = 1)` | — | `graph_test()` + filter by q-value + Moran's I |

### Graph Utilities (`utils.R`)

| Function | Returns | Description |
|----------|---------|-------------|
| `get_root_nodes(cds, reduction_method = "UMAP")` | Integer indices | Root node indices in principal graph |
| `get_branch_nodes(cds, reduction_method = "UMAP")` | Integer indices | Branch nodes (degree > 2, non-root) |
| `get_leaf_nodes(cds, reduction_method = "UMAP")` | Integer indices | Leaf nodes (degree == 1, non-root) |
| `get_clusters(cds)` | Named vector | Extract cluster assignments from internal S4 structure |
| `get_partitions(cds)` | Named vector | Extract partition assignments from internal S4 structure |

### Marker & Model Utilities (`utils.R`)

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_top_markers(cds, group_cells_by = "cluster", n_markers = 3, reference_cells = 100, cores = 1)` | — | `top_markers()` + fraction_expressing + pseudo_R2 filter |
| `annotate_clusters(cds, cluster_annotations, annotation_col = "cell_type")` | Named vector mapping IDs → names | Map cluster IDs to annotations |

### Metadata & Export (`utils.R`)

| Function | Parameters | Description |
|----------|-----------|-------------|
| `export_pseudotime_data(cds, output_file)` | — | Export pseudotime + metadata to CSV |
| `check_cds_completeness(cds)` | — | Returns list: preprocessed, reduced_dims, clustered, graph_learned, pseudotime_ordered |
| `print_cds_summary(cds)` | — | Print dimensions and analysis status |

### Visualization (`visualization.R`)

| Function | Parameters | Description |
|----------|-----------|-------------|
| `plot_trajectory_3d(cds, color_cells_by = "partition", ...)` | — | Validates 3D reduction exists before plotting |
| `plot_trajectory_features(cds, features, ncol = 2)` | — | Named list of ggplot objects, one per feature |
| `plot_pseudotime_distribution(cds, group_by = NULL, bins = 30)` | — | Custom ggplot histogram of pseudotime |

---

## Official API — Agents Often Miss These

These are real monocle3 functions that agents frequently forget or misuse:

| Function | Key Point |
|----------|-----------|
| `align_cds(cds, alignment_group = "batch")` | **MUST run BEFORE `preprocess_cds()`** — MNN batch correction |
| `evaluate_fits(gene_fits)` | Model quality: AIC, BIC, deviance, logLik |
| `compare_models(full, reduced)` | Likelihood ratio test for nested models |
| `model_predictions(models)` | Predict expression from fitted models |
| `set_matrix_control(cds, list(matrix_class = "BPCells"))` | Enable on-disk storage for large datasets |
| `save_monocle_objects(cds, output_dir)` | Save CDS + BPCells matrices (NOT `saveRDS()`) |
| `load_monocle_objects(output_dir)` | Load saved objects with BPCells |
| `load_cellranger_data(dir_path)` | Load 10x Cell Ranger output directly |
| `load_mtx_data(mtx_file, feature_file, barcode_file)` | Load MTX + features + barcodes |
| `find_gene_modules(cds, resolution = 1e-3)` | UMAP + Louvain on genes for co-expression modules |
| `aggregate_gene_expression(cds, gene_module_df, cell_group_df)` | Aggregate module expression per cell group |
| `choose_cells(cds)` / `choose_graph_segments(cds)` | Interactive Shiny selection |
| `plot_genes_in_pseudotime(cds_subset, color_cells_by = "cluster")` | Plot gene expression dynamics along pseudotime |
| `normalized_counts(cds)` | Access normalized expression matrix |

**Accessors**: `pseudotime(cds)`, `principal_graph(cds)`, `clusters(cds)`, `partitions(cds)`.

---

## Hyperparameter Guide

| Parameter | Default | Small data (<1k) | Medium (1k-10k) | Large (>10k) |
|-----------|---------|-------------------|-----------------|---------------|
| `num_dim` | 50 | 30-50 | 50-100 | 100-200 |
| `umap.n_neighbors` | 15 | 5-15 | 15-30 | 30-100 |
| `umap.min_dist` | 0.1 | 0.01-0.1 | 0.1-0.5 | 0.5-1.0 |
| `cluster_cells` resolution | 1e-5 | 1e-6-1e-4 (few) | 1e-4-1e-2 (moderate) | 1e-2-0.1 (many) |

---

## Common Pitfalls

1. **`align_cds` before `preprocess_cds`**: Batch correction must happen before dimensionality reduction.
2. **Root selection**: Without `root_cells` or `root_pr_nodes`, `order_cells()` opens an interactive Shiny app — non-interactive sessions will hang.
3. **BPCells save/load**: Use `save_monocle_objects()` / `load_monocle_objects()`, not base `saveRDS()`/`readRDS()`.
4. **graph_test memory**: Large datasets may OOM with `neighbor_graph = "knn"`; use `"principal_graph"` instead.
5. **Seurat v5**: Always use `cds_from_seurat()` rather than manual extraction to handle `layer` vs `slot` correctly.
6. **Partitions**: Partitions represent disconnected trajectory components. Cells in different partitions cannot be connected by pseudotime.

---

## Related Skills

- [bio-single-cell-trajectory-scvelo](../bio-single-cell-trajectory-scvelo/SKILL.md) - RNA velocity-based trajectory
- [bio-single-cell-clustering-seurat](../bio-single-cell-clustering-seurat/SKILL.md) - Seurat clustering
- [bio-single-cell-differential-expression](../bio-single-cell-differential-expression/SKILL.md) - Differential expression analysis

## References

1. Trapnell et al. (2014). The dynamics and regulators of cell fate decisions are revealed by pseudotemporal ordering of single cells. *Nature Biotechnology*, 32(4), 381-386.
2. Cao et al. (2019). The single-cell transcriptional landscape of mammalian organogenesis. *Nature*, 566(7745), 496-502.
3. Monocle3 documentation: https://cole-trapnell-lab.github.io/monocle3/
4. Monocle3 GitHub: https://github.com/cole-trapnell-lab/monocle3
