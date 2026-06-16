# Monocle3 Usage Guide

## Overview

Monocle3 uses reversed graph embedding to learn a principal graph representing cell developmental trajectories. It orders cells by pseudotime, identifies branching points, analyzes gene expression dynamics, and supports batch correction, gene module detection, and cell type classification.

## Key Features

- **Reversed Graph Embedding**: Learn a principal graph representing cell trajectories
- **Pseudotime Ordering**: Assign pseudotime values based on progression
- **Branch Point Detection**: Identify where cells diverge
- **Gene Dynamics**: Analyze gene expression changes (Moran's I test)
- **Gene Modules**: Find co-expressed gene modules
- **Batch Correction**: Align datasets using `align_cds()`
- **3D Visualization**: Interactive 3D trajectory plots
- **Model Evaluation**: AIC, BIC, deviance, likelihood ratio tests
- **Cell Classification**: Garnett integration for automated annotation
- **BPCells Support**: On-disk matrices for large datasets

## When to Use

- Developmental trajectory analysis
- Stem cell differentiation studies
- Reprogramming time-course data
- Disease progression analysis
- Any data with expected temporal or hierarchical structure

## Requirements

- R >= 4.2.0
- monocle3 >= 1.4.25
- Bioconductor >= 3.17

## Installation

```r
# Install Bioconductor manager
if (!require("BiocManager", quietly = TRUE))
    install.packages("BiocManager")

# Install Monocle3
BiocManager::install("monocle3")

# Install additional dependencies
install.packages(c("ggplot2", "dplyr", "igraph"))
```

## Quick Start

### Basic Usage

```r
library(monocle3)

# Create cell_data_set
cds <- new_cell_data_set(
  expression_data = counts_matrix,
  cell_metadata = cell_metadata,
  gene_metadata = gene_metadata
)

# QC
cds <- detect_genes(cds, min_expr = 0.1)
cds <- estimate_size_factors(cds)

# Preprocess
cds <- preprocess_cds(cds, num_dim = 50)
cds <- reduce_dimension(cds, reduction_method = "UMAP")
cds <- cluster_cells(cds)

# Learn trajectory graph
cds <- learn_graph(cds)

# Order cells (specify root or use interactive selection)
cds <- order_cells(cds, root_cells = root_cell_ids)

# Plot pseudotime
plot_cells(cds, color_cells_by = "pseudotime")
```

## Step-by-Step

### 1. Load Data

#### From Count Matrix

```r
library(monocle3)

# From count matrix
cds <- new_cell_data_set(
  expression_data = counts_matrix,
  cell_metadata = cell_metadata,
  gene_metadata = gene_metadata
)
```

#### From 10x Cell Ranger

```r
cds <- monocle3::load_cellranger_data(dir_path = "./filtered_gene_bc_matrices")
```

#### From MTX

```r
cds <- monocle3::load_mtx_data(
  mtx_file = "matrix.mtx",
  feature_file = "features.tsv",
  barcode_file = "barcodes.tsv"
)
```

#### From Seurat Object

```r
# Seurat v5 compatible
counts <- Seurat::GetAssayData(seurat_obj, layer = "counts")
cell_metadata <- seurat_obj@meta.data
gene_metadata <- data.frame(
  gene_short_name = rownames(counts),
  row.names = rownames(counts)
)

cds <- new_cell_data_set(
  expression_data = counts,
  cell_metadata = cell_metadata,
  gene_metadata = gene_metadata
)
```

### 2. Quality Control

```r
# Detect expressed genes
cds <- detect_genes(cds, min_expr = 0.1)

# Estimate size factors for normalization
cds <- estimate_size_factors(cds)

# Check size factors
head(size_factors(cds))

# Get normalized counts
norm_counts <- normalized_counts(cds)
```

**Parameters:**
- `min_expr`: Minimum expression threshold (default: 0.1)
- Size factors are used internally by `preprocess_cds`

### 3. Preprocess

```r
# Basic preprocessing
cds <- preprocess_cds(cds, num_dim = 50)

# With batch correction
cds <- preprocess_cds(cds,
                      num_dim = 50,
                      residual_model_formula_str = "~ batch")

# Plot PCA variance
plot_pc_variance_explained(cds)
```

**Parameters:**
- `num_dim`: Number of principal components (default: 50)
- `norm_method`: Normalization method ("log" or "size_only")
- `residual_model_formula_str`: Model for batch correction

### 4. Reduce Dimensions

```r
# UMAP (recommended for trajectory)
cds <- reduce_dimension(cds,
                        reduction_method = "UMAP",
                        max_components = 2,
                        umap.metric = "cosine",
                        umap.min_dist = 0.1,
                        umap.n_neighbors = 15)

# Plot
plot_cells(cds)
plot_cells(cds, color_cells_by = "cluster")
```

**Parameters:**
- `reduction_method`: "UMAP", "tSNE", or "PCA"
- `max_components`: Number of dimensions (2 or 3)
- `umap.n_neighbors`: Controls local vs global structure
- `umap.min_dist`: Controls cluster tightness

### 5. Cluster Cells

```r
# Basic clustering
cds <- cluster_cells(cds, resolution = 1e-5)

# With custom parameters
cds <- cluster_cells(cds,
                     resolution = c(10^seq(-6, -1)),
                     k = 20,
                     cluster_method = "leiden")

# Plot clusters
plot_cells(cds, color_cells_by = "cluster")
plot_cells(cds, color_cells_by = "partition")
```

**Parameters:**
- `resolution`: Controls cluster granularity (higher = more clusters)
- `k`: Number of nearest neighbors
- `cluster_method`: "leiden" or "louvain"

### 6. Learn Trajectory Graph

```r
# Learn principal graph
cds <- learn_graph(cds, use_partition = TRUE, close_loop = FALSE)

# Plot with trajectory
plot_cells(cds,
           color_cells_by = "cluster",
           label_groups_by_cluster = FALSE,
           label_leaves = TRUE,
           label_branch_points = TRUE,
           graph_label_size = 1.5)
```

**Parameters:**
- `use_partition`: Whether to use partitions to constrain graph
- `close_loop`: Whether to close loops in the graph

### 7. Order Cells

```r
# Method 1: Specify root cells
cds <- order_cells(cds, root_cells = root_cell_ids)

# Method 2: Specify root principal nodes
cds <- order_cells(cds, root_pr_nodes = "Y_21")

# Method 3: Interactive selection (opens Shiny app)
cds <- order_cells(cds)

# Plot pseudotime
plot_cells(cds,
           color_cells_by = "pseudotime",
           label_cell_groups = FALSE,
           label_leaves = FALSE,
           label_branch_points = FALSE)
```

**Helper function to find root:**
```r
get_earliest_principal_node <- function(cds, time_bin_col, time_bin_value) {
  if (!time_bin_col %in% colnames(colData(cds))) {
    stop("Column '", time_bin_col, "' not found in colData(cds). ",
         "Available columns: ", paste(colnames(colData(cds)), collapse = ", "))
  }

  cell_ids <- which(colData(cds)[[time_bin_col]] == time_bin_value)
  if (length(cell_ids) == 0) {
    stop("No cells match ", time_bin_col, " = '", time_bin_value, "'")
  }

  closest_vertex <- cds@principal_graph_aux[["UMAP"]]$pr_graph_cell_proj_closest_vertex
  closest_vertex <- as.matrix(closest_vertex[colnames(cds), ])

  cell_vertex_counts <- table(closest_vertex[cell_ids, ])
  if (length(cell_vertex_counts) == 0) {
    stop("Could not map cells to principal graph vertices")
  }

  root_pr_nodes <- igraph::V(principal_graph(cds)[["UMAP"]])$name[
    as.numeric(names(which.max(cell_vertex_counts)))
  ]

  return(root_pr_nodes)
}

# Use helper
cds <- order_cells(cds,
                   root_pr_nodes = get_earliest_principal_node(
                     cds, "embryo.time.bin", "130-170"
                   ))
```

### 8. Differential Expression Analysis

```r
# Test genes along trajectory
pr_graph_test_res <- graph_test(cds,
                                neighbor_graph = "principal_graph",
                                cores = 4)

# Get significant genes
pr_deg_ids <- row.names(subset(pr_graph_test_res, q_value < 0.05))

# Visualize top genes
top_genes <- pr_deg_ids[1:6]
cds_subset <- cds[top_genes, ]
plot_genes_in_pseudotime(cds_subset, color_cells_by = "cluster")
```

**Parameters:**
- `neighbor_graph`: "principal_graph" or "knn"
- `method`: "Moran_I" (spatial autocorrelation test)
- `cores`: Number of cores for parallel processing

### 9. Gene Expression Modeling

```r
# Fit models for specific genes
genes_of_interest <- c("gene1", "gene2", "gene3")
cds_subset <- cds[genes_of_interest, ]

# Fit with pseudotime
gene_fits <- fit_models(cds_subset,
                        model_formula_str = "~pseudotime",
                        expression_family = "quasipoisson")

# Evaluate model quality
eval_res <- evaluate_fits(gene_fits)
head(eval_res)

# Get coefficients
fit_coefs <- coefficient_table(gene_fits)
sig_terms <- subset(fit_coefs, q_value < 0.05)

# Compare models
full_models <- fit_models(cds_subset,
                          model_formula_str = "~pseudotime + batch")
reduced_models <- fit_models(cds_subset,
                             model_formula_str = "~pseudotime")
comparison <- compare_models(full_models, reduced_models)

# Predict expression
preds <- model_predictions(gene_fits)
```

**Expression family options:**
- `"quasipoisson"` (default): fast, good for most cases
- `"negbinomial"`: more accurate, slower
- `"poisson"`: simple Poisson
- `"binomial"`: for ATAC-seq data

### 10. Gene Module Analysis

```r
# Find gene modules
gene_module_df <- find_gene_modules(cds[pr_deg_ids, ],
                                    resolution = 1e-3,
                                    max_components = 2,
                                    k = 20)

# Aggregate expression by module
cell_group_df <- tibble::tibble(
  cell = row.names(colData(cds)),
  cell_group = clusters(cds)[colnames(cds)]
)

agg_mat <- aggregate_gene_expression(cds,
                                     gene_module_df,
                                     cell_group_df)

# Visualize
plot_cells(cds,
           genes = gene_module_df %>% filter(module %in% c(1, 2, 3)),
           label_cell_groups = FALSE,
           show_trajectory_graph = FALSE)
```

### 11. Batch Correction with align_cds

```r
# Align CDS BEFORE preprocessing
cds <- align_cds(cds,
                 alignment_group = "batch",
                 residual_model_formula_str = "~ batch")

# Continue with standard workflow
cds <- preprocess_cds(cds, num_dim = 50)
cds <- reduce_dimension(cds)
# ... etc
```

### 12. 3D Trajectory Visualization

```r
# Compute 3D UMAP
cds_3d <- reduce_dimension(cds, max_components = 3)
cds_3d <- cluster_cells(cds_3d)
cds_3d <- learn_graph(cds_3d)
cds_3d <- order_cells(cds_3d, root_pr_nodes = root_nodes)

# Plot 3D
plot_cells_3d(cds_3d, color_cells_by = "partition")
```

### 13. Combine Multiple Datasets

```r
# Combine multiple CDS objects
cds_combined <- combine_cds(list(cds1, cds2, cds3), keep_all_genes = TRUE)

# Run standard workflow
cds_combined <- preprocess_cds(cds_combined, num_dim = 50)
cds_combined <- reduce_dimension(cds_combined)
cds_combined <- cluster_cells(cds_combined)
```

### 14. Save and Load Objects

```r
# Enable BPCells for large datasets
cds <- set_matrix_control(cds, list(matrix_class = "BPCells"))

# Save complete analysis
save_monocle_objects(cds, output_dir = "./monocle_output")

# Load back
cds <- load_monocle_objects("./monocle_output")
```

### 15. Interactive Subsetting

```r
# Interactively select cells (opens Shiny app)
cds_subset <- choose_cells(cds)

# Interactively select graph segments
cds_branch <- choose_graph_segments(cds)
```

### 16. Cell Classification with Garnett

```r
# Generate marker file
generate_garnett_marker_file(marker_data, "marker_file.txt")

# Train classifier
classifier <- train_cell_classifier(cds, marker_file = "marker_file.txt")

# Classify cells
cds <- classify_cells(cds, classifier = classifier)
```

## Hyperparameter Selection

### Number of Dimensions (num_dim)

```r
# Plot variance explained to choose num_dim
cds <- preprocess_cds(cds, num_dim = 100)
plot_pc_variance_explained(cds)

# Choose where variance starts to plateau
```

### UMAP n_neighbors

| Value | Effect | Use Case |
|-------|--------|----------|
| 5-10 | Local structure only | Small datasets, fine structure |
| 15-30 | Balanced | General use (default: 15) |
| 50-100 | Global structure | Large datasets, broad trajectories |

### Clustering Resolution

```r
# Test multiple resolutions
cds <- cluster_cells(cds, resolution = c(10^seq(-6, -1)))

# Evaluate using plots
plot_cells(cds, color_cells_by = "cluster")
```

| Resolution | Clusters | Use Case |
|------------|----------|----------|
| 1e-6 | Very few | Broad types |
| 1e-4 | Few | Major trajectories |
| 1e-2 | Moderate | Subtypes |
| 0.1 | Many | Fine-grained |

## AI Agent Test Cases

### Basic Usage
> "Run Monocle3 trajectory analysis on my Seurat object"

```r
cds <- cds_from_seurat(seurat_obj)
cds <- run_trajectory_analysis(cds, num_dim = 50, root_cells = root_ids)
plot_cells(cds, color_cells_by = "pseudotime", show_trajectory_graph = TRUE)
```

### Batch Correction
> "Run Monocle3 with batch correction"

```r
cds <- align_cds(cds, alignment_group = "batch")
cds <- run_trajectory_analysis(cds, num_dim = 50)
```

### Find Branch Points
> "Identify branching points in my trajectory"

```r
cds <- learn_graph(cds)
branch_nodes <- get_branch_nodes(cds)
leaf_nodes <- get_leaf_nodes(cds)
plot_cells(cds, label_cell_groups = FALSE,
           label_leaves = TRUE, label_branch_points = TRUE,
           show_trajectory_graph = TRUE, cell_size = 0.5)
```

### Gene Dynamics
> "Find genes that change over pseudotime"

```r
sig_genes <- find_trajectory_variable_genes(cds,
                                            q_value_threshold = 0.05)
plot_genes_in_pseudotime(cds[rownames(sig_genes)[1:6], ])
```

### Gene Modules
> "Find gene modules along the trajectory"

```r
sig_genes <- find_trajectory_variable_genes(cds)
gene_module_df <- find_gene_modules(cds[rownames(sig_genes), ])
plot_cells(cds, genes = gene_module_df %>% dplyr::filter(module %in% c(1, 2)))
```

### 3D Visualization
> "Create 3D trajectory plot"

```r
cds_3d <- reduce_dimension(cds, max_components = 3)
cds_3d <- learn_graph(cds_3d)
cds_3d <- order_cells(cds_3d, root_pr_nodes = roots)
plot_cells_3d(cds_3d, color_cells_by = "pseudotime")
```

### Model Evaluation
> "Evaluate the quality of my gene expression models"

```r
gene_fits <- fit_models(cds_subset, model_formula_str = "~pseudotime")
eval_res <- evaluate_fits(gene_fits)
print(eval_res)
```

### Load 10x Data
> "Load Cell Ranger data and run trajectory analysis"

```r
cds <- monocle3::load_cellranger_data(dir_path = "./filtered_gene_bc_matrices")
cds <- run_trajectory_analysis(cds, num_dim = 50, root_cells = root_ids)
```

### Save/Load Analysis
> "Save my Monocle3 analysis for later"

```r
save_monocle_objects(cds, output_dir = "./my_analysis")
cds <- load_monocle_objects("./my_analysis")
```

## Best Practices

1. **QC First**: Filter low-quality cells before trajectory analysis; use `detect_genes()` and `estimate_size_factors()`
2. **Choose Root Carefully**: Biological prior knowledge helps identify root
3. **Check Partitions**: Use partitions to identify disconnected trajectories
4. **Validate Trajectory**: Check that pseudotime correlates with known markers
5. **Gene Selection**: Use trajectory-variable genes for module analysis
6. **Multiple Roots**: Can specify multiple root nodes for complex trajectories
7. **BPCells for Large Data**: Use `set_matrix_control()` for datasets > 100k cells
8. **align_cds BEFORE preprocess**: Batch correction must happen before dimensionality reduction

## Troubleshooting

### No Clear Trajectory

```r
# Try different UMAP parameters
cds <- reduce_dimension(cds, umap.n_neighbors = 50, umap.min_dist = 0.3)

# Or use tSNE instead
cds <- reduce_dimension(cds, reduction_method = "tSNE")
```

### Too Many/Few Branches

```r
# Adjust clustering resolution
cds <- cluster_cells(cds, resolution = 1e-3)  # More clusters
# OR
cds <- cluster_cells(cds, resolution = 1e-6)  # Fewer clusters

# Re-learn graph
cds <- learn_graph(cds)
```

### Batch Effects

```r
# Use align_cds BEFORE preprocessing
cds <- align_cds(cds, alignment_group = "batch")
cds <- preprocess_cds(cds, num_dim = 50)
```

### Out of Memory

```r
# Enable BPCells for on-disk storage
cds <- set_matrix_control(cds, list(matrix_class = "BPCells"))

# Use fewer dimensions
cds <- preprocess_cds(cds, num_dim = 30)
cds <- reduce_dimension(cds, max_components = 2)

# Use principal_graph instead of knn for graph_test
graph_test(cds, neighbor_graph = "principal_graph", cores = 1)
```

## References

1. Trapnell et al. (2014). The dynamics and regulators of cell fate decisions are revealed by pseudotemporal ordering of single cells. *Nature Biotechnology*, 32(4), 381-386.
2. Cao et al. (2019). The single-cell transcriptional landscape of mammalian organogenesis. *Nature*, 566(7745), 496-502.
3. Monocle3 documentation: https://cole-trapnell-lab.github.io/monocle3/
