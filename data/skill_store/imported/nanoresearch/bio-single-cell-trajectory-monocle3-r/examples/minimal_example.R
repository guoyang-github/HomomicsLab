#!/usr/bin/env Rscript
#' Monocle3 Minimal Example
#'
#' Demonstrates the basic trajectory inference workflow using official monocle3
#' functions plus high-value skill helpers for logging and export.
#'
#' Requirements:
#'   BiocManager::install("monocle3")
#'
#' Usage:
#'   Rscript minimal_example.R

# Load required libraries
suppressPackageStartupMessages({
  library(monocle3)
  library(ggplot2)
  library(dplyr)
})

# Source custom scripts (only high-value helpers)
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("Monocle3 Minimal Example - Trajectory Inference\n")
cat(rep("=", 70), "\n", sep = "")

# ==============================================================================
# Step 1: Create Simulated Data
# ==============================================================================
cat("\nStep 1: Creating simulated data...\n")

set.seed(42)

n_cells <- 500
n_genes <- 1000

expression_matrix <- matrix(rpois(n_cells * n_genes, lambda = 2),
                            nrow = n_genes, ncol = n_cells)

# Simulate trajectory with branching
branch_assignment <- sample(c("progenitor", "branch_A", "branch_B"),
                            n_cells, replace = TRUE, prob = c(0.2, 0.4, 0.4))

pseudotime_values <- runif(n_cells, 0, 1)

# Make genes change along pseudotime
for (i in 1:n_cells) {
  if (branch_assignment[i] == "progenitor") {
    progenitor_genes <- 1:100
    expression_matrix[progenitor_genes, i] <- expression_matrix[progenitor_genes, i] +
      rpois(100, lambda = 5 * (1 - pseudotime_values[i]))
  } else if (branch_assignment[i] == "branch_A") {
    branch_a_genes <- 101:200
    expression_matrix[branch_a_genes, i] <- expression_matrix[branch_a_genes, i] +
      rpois(100, lambda = 5 * pseudotime_values[i])
  } else {
    branch_b_genes <- 201:300
    expression_matrix[branch_b_genes, i] <- expression_matrix[branch_b_genes, i] +
      rpois(100, lambda = 5 * pseudotime_values[i])
  }
}

# Add metadata
gene_metadata <- data.frame(
  gene_short_name = paste0("gene_", 1:n_genes),
  row.names = paste0("gene_", 1:n_genes)
)
rownames(expression_matrix) <- rownames(gene_metadata)

cell_metadata <- data.frame(
  cell_id = paste0("cell_", 1:n_cells),
  true_branch = branch_assignment,
  true_pseudotime = pseudotime_values,
  row.names = paste0("cell_", 1:n_cells)
)
colnames(expression_matrix) <- rownames(cell_metadata)

cat(sprintf("  Created data: %d genes x %d cells\n", n_genes, n_cells))

# ==============================================================================
# Step 2: Create Cell Data Set
# ==============================================================================
cat("\nStep 2: Creating Cell Data Set...\n")

cds <- create_cds(expression_matrix, cell_metadata, gene_metadata)
cat(sprintf("  CDS dimensions: %d genes x %d cells\n", nrow(cds), ncol(cds)))

# ==============================================================================
# Step 3: Preprocess
# ==============================================================================
cat("\nStep 3: Preprocessing data...\n")

cds <- preprocess_cds(cds, num_dim = 30)
cat("  Preprocessing complete\n")

p <- plot_pc_variance_explained(cds)
ggsave("pca_variance.png", p, width = 6, height = 4, dpi = 150)
cat("  PCA variance plot saved to pca_variance.png\n")

# ==============================================================================
# Step 4: Reduce Dimensions
# ==============================================================================
cat("\nStep 4: Reducing dimensions...\n")

cds <- reduce_dimension(cds, reduction_method = "UMAP",
                        umap.min_dist = 0.1, umap.n_neighbors = 15)
cat("  UMAP reduction complete\n")

p <- plot_cells(cds, label_cell_groups = FALSE)
ggsave("umap_cells.png", p, width = 6, height = 6, dpi = 150)
cat("  UMAP plot saved to umap_cells.png\n")

# ==============================================================================
# Step 5: Cluster Cells
# ==============================================================================
cat("\nStep 5: Clustering cells...\n")

cds <- cluster_cells(cds, resolution = 1e-5)
cat(sprintf("  Found %d clusters\n", length(unique(clusters(cds)))))

p <- plot_cells(cds, color_cells_by = "cluster")
ggsave("clusters.png", p, width = 6, height = 6, dpi = 150)
cat("  Cluster plot saved to clusters.png\n")

# ==============================================================================
# Step 6: Learn Trajectory Graph
# ==============================================================================
cat("\nStep 6: Learning trajectory graph...\n")

cds <- learn_graph(cds, use_partition = TRUE, close_loop = FALSE)
cat("  Graph learning complete\n")

p <- plot_cells(cds, label_cell_groups = FALSE,
                label_leaves = TRUE, label_branch_points = TRUE,
                show_trajectory_graph = TRUE, cell_size = 0.5)
ggsave("trajectory_graph.png", p, width = 6, height = 6, dpi = 150)
cat("  Trajectory graph saved to trajectory_graph.png\n")

# ==============================================================================
# Step 7: Order Cells by Pseudotime
# ==============================================================================
cat("\nStep 7: Ordering cells by pseudotime...\n")

# For non-interactive use, identify root cells programmatically
root_cells <- names(which(pseudotime_values < 0.1))
cat(sprintf("  Using %d cells as roots\n", length(root_cells)))

cds <- order_cells(cds, root_cells = root_cells)
cat("  Pseudotime ordering complete\n")

p <- plot_cells(cds, color_cells_by = "pseudotime",
                label_cell_groups = FALSE, label_leaves = FALSE,
                label_branch_points = FALSE, cell_size = 1,
                show_trajectory_graph = TRUE)
ggsave("pseudotime.png", p, width = 7, height = 6, dpi = 150)
cat("  Pseudotime plot saved to pseudotime.png\n")

# ==============================================================================
# Step 8: Find Trajectory-Variable Genes
# ==============================================================================
cat("\nStep 8: Finding trajectory-variable genes...\n")

# Use the skill helper that combines graph_test + filtering
test_res <- graph_test(cds, neighbor_graph = "principal_graph", cores = 1)
sig_genes <- subset(test_res, q_value < 0.05 & morans_I > 0.05)
cat(sprintf("  Found %d trajectory-variable genes\n", nrow(sig_genes)))

# Plot top genes
top_genes <- rownames(sig_genes)[1:min(6, nrow(sig_genes))]
cds_subset <- cds[top_genes, ]

p <- plot_genes_in_pseudotime(cds_subset, color_cells_by = "cluster")
ggsave("genes_in_pseudotime.png", p, width = 10, height = 8, dpi = 150)
cat("  Gene expression in pseudotime saved to genes_in_pseudotime.png\n")

# ==============================================================================
# Step 9: Find Gene Modules
# ==============================================================================
cat("\nStep 9: Finding gene modules...\n")

pr_deg_ids <- rownames(sig_genes)[1:min(200, nrow(sig_genes))]
gene_module_df <- find_gene_modules(cds[pr_deg_ids, ], resolution = 1e-2, cores = 1)

cat(sprintf("  Found %d gene modules\n", length(unique(gene_module_df$module))))

# Plot gene modules
top_modules <- unique(gene_module_df$module)[1:min(4, length(unique(gene_module_df$module)))]
p <- plot_cells(cds, genes = gene_module_df %>% dplyr::filter(module %in% top_modules),
                label_cell_groups = FALSE, show_trajectory_graph = FALSE)
ggsave("gene_modules.png", p, width = 8, height = 6, dpi = 150)
cat("  Gene module plot saved to gene_modules.png\n")

# ==============================================================================
# Step 10: Export Results
# ==============================================================================
cat("\nStep 10: Exporting results...\n")

export_pseudotime_data(cds, "pseudotime_data.csv")
sig_genes <- subset(test_res, q_value < 0.05)
write.csv(sig_genes, "trajectory_de_genes.csv", row.names = FALSE)

# ==============================================================================
# Summary
# ==============================================================================
cat("\n", rep("=", 70), "\n", sep = "")
cat("Analysis Complete!\n")
cat(rep("=", 70), "\n", sep = "")

cat("\nKey steps demonstrated:\n")
cat("  1. Cell Data Set creation (create_cds)\n")
cat("  2. Preprocessing (preprocess_cds)\n")
cat("  3. Dimensionality reduction (reduce_dimension)\n")
cat("  4. Cell clustering (cluster_cells)\n")
cat("  5. Trajectory graph learning (learn_graph)\n")
cat("  6. Pseudotime ordering (order_cells)\n")
cat("  7. Trajectory-variable gene detection (graph_test)\n")
cat("  8. Gene module identification (find_gene_modules)\n")

cat("\nOutput files:\n")
cat("  - pca_variance.png\n")
cat("  - umap_cells.png\n")
cat("  - clusters.png\n")
cat("  - trajectory_graph.png\n")
cat("  - pseudotime.png\n")
cat("  - genes_in_pseudotime.png\n")
cat("  - gene_modules.png\n")
cat("  - pseudotime_data.csv\n")
cat("  - trajectory_de_genes.csv\n")
