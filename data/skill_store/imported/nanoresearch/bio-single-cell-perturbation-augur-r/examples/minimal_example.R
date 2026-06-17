#!/usr/bin/env Rscript
#' Augur Minimal Example
#'
#' Basic Augur workflow for cell type prioritization.
#'
#' @date 2026-04-22

# Load wrapper functions
source("scripts/r/augur_analysis.R")

# ------------------------------------------------------------------------------
# Step 1: Prepare Data
# ------------------------------------------------------------------------------

# This example assumes you have a Seurat object with:
# - 'condition' column: control vs treatment labels
# - 'cell_type' column: cell type annotations
#
# Replace with your actual data loading:
# seurat_obj <- readRDS("your_data.rds")

# For demonstration, we show the expected structure:
cat("Expected Seurat object metadata:\n")
cat("  - condition: control, treatment\n")
cat("  - cell_type: T_cell, B_cell, Monocyte, etc.\n")

# ------------------------------------------------------------------------------
# Step 2: Validate Data
# ------------------------------------------------------------------------------

# validation <- validate_augur_data(
#   seurat_obj,
#   label_col = "condition",
#   cell_type_col = "cell_type",
#   min_cells = 20
# )
# print_validation_results(validation)

# ------------------------------------------------------------------------------
# Step 3: Run Augur Analysis
# ------------------------------------------------------------------------------

# Run Augur with default random forest classifier
# augur <- run_augur(
#   seurat_obj,
#   label_col = "condition",
#   cell_type_col = "cell_type",
#   classifier = "rf",
#   n_subsamples = 50,
#   subsample_size = 20,
#   folds = 3,
#   n_threads = 4
# )

# ------------------------------------------------------------------------------
# Step 4: View Results
# ------------------------------------------------------------------------------

# Print AUC summary
# print(augur$AUC)

# Get summary statistics
# stats <- summarize_augur_results(augur)
# print(stats)

# ------------------------------------------------------------------------------
# Step 5: Visualize
# ------------------------------------------------------------------------------

# Lollipop plot
# p <- plot_augur_lollipop(augur)
# print(p)
# ggsave("augur_lollipop.pdf", p, width = 6, height = 4)

# UMAP overlay
# p <- plot_augur_umap(augur, seurat_obj, reduction = "umap")
# print(p)

# ------------------------------------------------------------------------------
# Step 6: Feature Importance
# ------------------------------------------------------------------------------

# Get top genes per cell type
# top_genes <- get_top_features(augur, top_n = 10)
# print(top_genes)

# ------------------------------------------------------------------------------
# Step 7: Export
# ------------------------------------------------------------------------------

# export_augur_results(
#   augur,
#   output_dir = "augur_results",
#   prefix = "sample1",
#   export_summary = TRUE,
#   export_importances = TRUE
# )

cat("\nMinimal example completed. Uncomment lines to run with real data.\n")
