#!/usr/bin/env Rscript
#' Monocle3 Advanced Example
#'
#' Demonstrates advanced features using official monocle3 functions plus
#' high-value skill helpers.
#'
#' Requirements:
#'   BiocManager::install("monocle3")
#'   install.packages("plotly")
#'
#' Usage:
#'   Rscript advanced_example.R

suppressPackageStartupMessages({
  library(monocle3)
  library(ggplot2)
  library(dplyr)
})

source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("Monocle3 Advanced Example\n")
cat(rep("=", 70), "\n", sep = "")

# ==============================================================================
# Part 1: Batch Correction with align_cds
# ==============================================================================
cat("\n--- Part 1: Batch Correction ---\n")

set.seed(42)

# Simulate data with batch effect
n_cells_batch1 <- 300
n_cells_batch2 <- 300
n_genes <- 800

expr_batch1 <- matrix(rpois(n_cells_batch1 * n_genes, lambda = 2),
                      nrow = n_genes, ncol = n_cells_batch1)
expr_batch2 <- matrix(rpois(n_cells_batch2 * n_genes, lambda = 3),
                      nrow = n_genes, ncol = n_cells_batch2)

expression_matrix <- cbind(expr_batch1, expr_batch2)

cell_metadata <- data.frame(
  cell_id = paste0("cell_", 1:ncol(expression_matrix)),
  batch = c(rep("batch1", n_cells_batch1), rep("batch2", n_cells_batch2)),
  row.names = paste0("cell_", 1:ncol(expression_matrix))
)

gene_metadata <- data.frame(
  gene_short_name = paste0("gene_", 1:n_genes),
  row.names = paste0("gene_", 1:n_genes)
)

rownames(expression_matrix) <- rownames(gene_metadata)
colnames(expression_matrix) <- rownames(cell_metadata)

cat("Creating CDS with batch effect...\n")
cds <- create_cds(expression_matrix, cell_metadata, gene_metadata)

# Preprocess without alignment
cat("Preprocessing without alignment...\n")
cds_no_align <- preprocess_cds(cds, num_dim = 30)
cds_no_align <- reduce_dimension(cds_no_align)
cds_no_align <- cluster_cells(cds_no_align)

p1 <- plot_cells(cds_no_align, color_cells_by = "batch",
                 label_cell_groups = FALSE) +
  ggtitle("Without Batch Correction")
ggsave("batch_effect_no_correction.png", p1, width = 6, height = 6, dpi = 150)
cat("  Saved: batch_effect_no_correction.png\n")

# Preprocess WITH alignment (must be BEFORE preprocess_cds)
cat("Preprocessing with alignment...\n")
cds_aligned <- align_cds(cds,
                         alignment_group = "batch",
                         residual_model_formula_str = "~ batch")
cds_aligned <- preprocess_cds(cds_aligned, num_dim = 30)
cds_aligned <- reduce_dimension(cds_aligned)
cds_aligned <- cluster_cells(cds_aligned)

p2 <- plot_cells(cds_aligned, color_cells_by = "batch",
                 label_cell_groups = FALSE) +
  ggtitle("With Batch Correction")
ggsave("batch_effect_corrected.png", p2, width = 6, height = 6, dpi = 150)
cat("  Saved: batch_effect_corrected.png\n")

# ==============================================================================
# Part 2: 3D Trajectory Analysis
# ==============================================================================
cat("\n--- Part 2: 3D Trajectory Analysis ---\n")

cat("Computing 3D UMAP...\n")
cds_3d <- reduce_dimension(cds_aligned, max_components = 3)
cds_3d <- cluster_cells(cds_3d)
cds_3d <- learn_graph(cds_3d)

root_cells <- colnames(cds_3d)[1:5]
cds_3d <- order_cells(cds_3d, root_cells = root_cells)

cat("3D trajectory analysis complete\n")
cat("  Use plot_cells_3d(cds_3d) or plot_trajectory_3d(cds_3d) for 3D visualization\n")

# ==============================================================================
# Part 3: Multi-Branch Trajectory Analysis
# ==============================================================================
cat("\n--- Part 3: Multi-Branch Analysis ---\n")

set.seed(123)
n_cells <- 600
n_genes <- 500

# Simulate trajectory with two branches
branch_labels <- sample(c("root", "fate_A", "fate_B"),
                        n_cells, replace = TRUE, prob = c(0.2, 0.4, 0.4))

pt_root <- runif(sum(branch_labels == "root"), 0, 0.3)
pt_a <- runif(sum(branch_labels == "fate_A"), 0.3, 1)
pt_b <- runif(sum(branch_labels == "fate_B"), 0.3, 1)

pseudotime_all <- c(pt_root, pt_a, pt_b)
branch_all <- c(rep("root", length(pt_root)),
                rep("fate_A", length(pt_a)),
                rep("fate_B", length(pt_b)))

expr_matrix <- matrix(rpois(n_cells * n_genes, 2), nrow = n_genes, ncol = n_cells)

root_cells_idx <- which(branch_all == "root")
fate_a_cells_idx <- which(branch_all == "fate_A")
fate_b_cells_idx <- which(branch_all == "fate_B")

root_genes <- 1:50
expr_matrix[root_genes, root_cells_idx] <- expr_matrix[root_genes, root_cells_idx] +
  matrix(rpois(length(root_genes) * length(root_cells_idx), 8),
         nrow = length(root_genes))

fate_a_genes <- 51:100
expr_matrix[fate_a_genes, fate_a_cells_idx] <- expr_matrix[fate_a_genes, fate_a_cells_idx] +
  matrix(rpois(length(fate_a_genes) * length(fate_a_cells_idx), 8),
         nrow = length(fate_a_genes))

fate_b_genes <- 101:150
expr_matrix[fate_b_genes, fate_b_cells_idx] <- expr_matrix[fate_b_genes, fate_b_cells_idx] +
  matrix(rpois(length(fate_b_genes) * length(fate_b_cells_idx), 8),
         nrow = length(fate_b_genes))

cell_meta <- data.frame(
  cell_id = paste0("cell_", 1:n_cells),
  true_branch = branch_all,
  true_pseudotime = pseudotime_all,
  row.names = paste0("cell_", 1:n_cells)
)
gene_meta <- data.frame(
  gene_short_name = paste0("gene_", 1:n_genes),
  row.names = paste0("gene_", 1:n_genes)
)
rownames(expr_matrix) <- rownames(gene_meta)
colnames(expr_matrix) <- rownames(cell_meta)

cds_branch <- create_cds(expr_matrix, cell_meta, gene_meta)

# Preprocess and learn trajectory
cds_branch <- preprocess_cds(cds_branch, num_dim = 30)
cds_branch <- reduce_dimension(cds_branch, umap.min_dist = 0.3)
cds_branch <- cluster_cells(cds_branch, resolution = 1e-4)
cds_branch <- learn_graph(cds_branch, close_loop = FALSE)

# Find branch points
branch_nodes <- get_branch_nodes(cds_branch)
cat(sprintf("  Found %d branch point(s)\n", length(branch_nodes)))

# Order cells
root_cells <- names(which(branch_all == "root"))[1:10]
cds_branch <- order_cells(cds_branch, root_cells = root_cells)

# Plot trajectory with branches
p <- plot_cells(cds_branch,
                color_cells_by = "true_branch",
                label_branch_points = TRUE,
                label_leaves = TRUE,
                cell_size = 1)
ggsave("multi_branch_trajectory.png", p, width = 7, height = 6, dpi = 150)
cat("  Saved: multi_branch_trajectory.png\n")

# ==============================================================================
# Part 4: Complex Gene Module Analysis
# ==============================================================================
cat("\n--- Part 4: Gene Module Analysis ---\n")

# Find trajectory-variable genes
sig_genes <- find_trajectory_variable_genes(cds_branch,
                                            q_value_threshold = 0.01,
                                            morans_I_threshold = 0.1)
cat(sprintf("  Found %d trajectory-variable genes\n", nrow(sig_genes)))

# Find gene modules
pr_deg_ids <- rownames(sig_genes)[1:min(150, nrow(sig_genes))]
gene_module_df <- find_gene_modules(cds_branch[pr_deg_ids, ],
                                    resolution = c(0, 10^seq(-6, -1)),
                                    cores = 1)

cat(sprintf("  Identified %d gene modules\n", length(unique(gene_module_df$module))))

# Aggregate expression by module
cell_group_df <- data.frame(
  cell = colnames(cds_branch),
  cell_group = colData(cds_branch)$true_branch
)

agg_mat <- aggregate_gene_expression(cds_branch, gene_module_df,
                                     cell_group_df = cell_group_df,
                                     scale_agg_values = TRUE)

cat("  Module expression aggregated by branch\n")

# Plot top modules
top_modules <- unique(gene_module_df$module)[1:min(6, length(unique(gene_module_df$module)))]
p <- plot_cells(cds_branch,
                genes = gene_module_df %>% dplyr::filter(module %in% top_modules),
                label_cell_groups = FALSE, show_trajectory_graph = FALSE)
ggsave("complex_gene_modules.png", p, width = 10, height = 8, dpi = 150)
cat("  Saved: complex_gene_modules.png\n")

# ==============================================================================
# Part 5: Gene Expression Modeling
# ==============================================================================
cat("\n--- Part 5: Gene Expression Modeling ---\n")

model_genes <- rownames(sig_genes)[1:4]
cds_model <- cds_branch[model_genes, ]

# Fit models with pseudotime
gene_fits <- fit_models(cds_model,
                        model_formula_str = "~ splines::ns(pseudotime, df=3)",
                        expression_family = "quasipoisson",
                        cores = 1)

# Evaluate model quality
eval_res <- evaluate_fits(gene_fits)
cat(sprintf("  Modeled %d genes\n", length(model_genes)))
cat(sprintf("  Mean AIC: %.1f\n", mean(eval_res$AIC, na.rm = TRUE)))

# Get coefficients
coefs <- coefficient_table(gene_fits)
sig_coefs <- coefs %>% dplyr::filter(q_value < 0.05)
cat(sprintf("  Found %d significant coefficients\n", nrow(sig_coefs)))

# Plot gene expression in pseudotime
p <- plot_genes_in_pseudotime(cds_model,
                              color_cells_by = "true_branch",
                              min_expr = 0.1)
ggsave("modeled_genes_pseudotime.png", p, width = 10, height = 8, dpi = 150)
cat("  Saved: modeled_genes_pseudotime.png\n")

# ==============================================================================
# Part 6: Pipeline Summary with check_cds_completeness
# ==============================================================================
cat("\n--- Part 6: Pipeline Validation ---\n")

print_cds_summary(cds_branch)

# ==============================================================================
# Summary
# ==============================================================================
cat("\n", rep("=", 70), "\n", sep = "")
cat("Advanced Analysis Complete!\n")
cat(rep("=", 70), "\n", sep = "")

cat("\nAdvanced features demonstrated:\n")
cat("  1. Batch correction with align_cds() (BEFORE preprocess_cds)\n")
cat("  2. 3D trajectory visualization setup\n")
cat("  3. Multi-branch trajectory analysis\n")
cat("  4. Branch point identification (get_branch_nodes)\n")
cat("  5. Complex gene module analysis (find_gene_modules)\n")
cat("  6. Gene expression modeling with splines\n")
cat("  7. Model evaluation (evaluate_fits)\n")
cat("  8. Pipeline validation (check_cds_completeness)\n")

cat("\nOutput files:\n")
cat("  - batch_effect_no_correction.png\n")
cat("  - batch_effect_corrected.png\n")
cat("  - multi_branch_trajectory.png\n")
cat("  - complex_gene_modules.png\n")
cat("  - modeled_genes_pseudotime.png\n")
