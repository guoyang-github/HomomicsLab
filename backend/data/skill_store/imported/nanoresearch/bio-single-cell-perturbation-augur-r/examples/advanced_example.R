#!/usr/bin/env Rscript
#' Augur Advanced Example
#'
#' Advanced Augur workflow including:
#' - Multi-condition comparison
#' - Permutation test
#' - Differential prioritization
#' - Feature importance analysis
#'
#' @date 2026-04-22

source("scripts/r/augur_analysis.R")

# ------------------------------------------------------------------------------
# Example 1: Compare Classifiers (RF vs LR)
# ------------------------------------------------------------------------------

# Run with random forest
# augur_rf <- run_augur(
#   seurat_obj,
#   label_col = "condition",
#   cell_type_col = "cell_type",
#   classifier = "rf",
#   n_subsamples = 50,
#   n_threads = 4
# )

# Run with logistic regression
# augur_lr <- run_augur(
#   seurat_obj,
#   label_col = "condition",
#   cell_type_col = "cell_type",
#   classifier = "lr",
#   n_subsamples = 50,
#   n_threads = 4
# )

# Compare scatterplot
# p <- plot_augur_scatterplot(augur_rf, augur_lr, top_n = 5)
# print(p)
# ggsave("augur_rf_vs_lr.pdf", p, width = 5, height = 5)

# ------------------------------------------------------------------------------
# Example 2: Permutation Test (Null Distribution)
# ------------------------------------------------------------------------------

# Run observed Augur
# augur_obs <- run_augur(
#   seurat_obj,
#   label_col = "condition",
#   cell_type_col = "cell_type",
#   classifier = "rf",
#   n_subsamples = 50
# )

# Run permuted Augur for null distribution (uses 500 subsamples)
# augur_null <- run_augur(
#   seurat_obj,
#   label_col = "condition",
#   cell_type_col = "cell_type",
#   classifier = "rf",
#   augur_mode = "permute"
# )

# Compare observed vs null AUCs
# obs_auc <- augur_obs$AUC
# null_auc <- augur_null$AUC
# comparison <- merge(obs_auc, null_auc, by = "cell_type", suffixes = c("_obs", "_null"))
# print(comparison)

# ------------------------------------------------------------------------------
# Example 3: Differential Prioritization Between Conditions
# ------------------------------------------------------------------------------

# Assume seurat_obj has a 'batch' column with Batch1 and Batch2

# Split and run Augur for each batch
# batch1 <- subset(seurat_obj, batch == "Batch1")
# batch2 <- subset(seurat_obj, batch == "Batch2")
#
# augur1 <- run_augur(batch1, label_col = "condition", n_threads = 4)
# augur2 <- run_augur(batch2, label_col = "condition", n_threads = 4)
#
# # Run permuted versions
# perm1 <- run_augur(batch1, label_col = "condition", augur_mode = "permute")
# perm2 <- run_augur(batch2, label_col = "condition", augur_mode = "permute")
#
# # Differential prioritization
# diff <- run_differential_prioritization(
#   augur1, augur2, perm1, perm2,
#   n_permutations = 1000
# )
#
# # View significant cell types
# sig <- diff[diff$padj < 0.05, ]
# print(sig[, c("cell_type", "auc.x", "auc.y", "delta_auc", "padj")])
#
# # Plot
# p <- plot_augur_differential(diff, top_n = 5)
# print(p)
# ggsave("augur_differential.pdf", p, width = 5, height = 5)

# ------------------------------------------------------------------------------
# Example 4: Multi-Condition Comparison (No Common Control)
# ------------------------------------------------------------------------------

# Compare across multiple independent conditions
# conditions <- c("DrugA", "DrugB", "DrugC")
# condition_results <- list()
#
# for (cond in conditions) {
#   sub <- subset(seurat_obj, drug == cond)
#   augur <- run_augur(sub, label_col = "condition", n_threads = 4)
#   condition_results[[cond]] <- augur$AUC
# }
#
# # Combine for comparison
# combined <- Reduce(function(x, y) merge(x, y, by = "cell_type"), condition_results)
# colnames(combined) <- c("cell_type", paste0("auc_", conditions))
# print(combined)

# ------------------------------------------------------------------------------
# Example 5: Custom RF Parameters
# ------------------------------------------------------------------------------

# augur_custom <- run_augur(
#   seurat_obj,
#   label_col = "condition",
#   cell_type_col = "cell_type",
#   classifier = "rf",
#   rf_params = list(
#     trees = 500,
#     mtry = 5,
#     importance = "gini"
#   ),
#   n_subsamples = 100,
#   subsample_size = 30,
#   n_threads = 8
# )

# ------------------------------------------------------------------------------
# Example 6: Regression Mode (Continuous Labels)
# ------------------------------------------------------------------------------

# For continuous labels (e.g., time points, dosages)
# The label_col should contain numeric values
# Augur automatically detects numeric labels and uses regression mode
#
# augur_reg <- run_augur(
#   seurat_obj,
#   label_col = "time_point",  # numeric column
#   cell_type_col = "cell_type",
#   classifier = "rf",
#   n_subsamples = 50
# )
#
# # Results will have CCC instead of AUC
# print(augur_reg$CCC)

# ------------------------------------------------------------------------------
# Example 7: Export Complete Results
# ------------------------------------------------------------------------------

# export_augur_results(
#   augur_obs,
#   output_dir = "augur_output",
#   prefix = "experiment1",
#   export_summary = TRUE,
#   export_importances = TRUE,
#   export_detailed = TRUE
# )

cat("\nAdvanced example completed. Uncomment sections to run with real data.\n")
