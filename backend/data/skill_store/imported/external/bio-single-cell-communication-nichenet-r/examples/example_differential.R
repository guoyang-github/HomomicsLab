#!/usr/bin/env Rscript
#' Differential NicheNet Analysis Example
#'
#' Demonstrates comparing ligand activities between two conditions
#' to identify condition-specific communication.
#'
#' @author Yang Guo
#' @date 2026-04-01

library(Seurat)
library(dplyr)
library(ggplot2)

# Source NicheNet scripts
source("../scripts/r/nichenet_database.R")
source("scripts/r/nichenet_analysis.R")
source("../scripts/r/nichenet_seurat.R")
source("../scripts/r/nichenet_visualization.R")

message("=== Differential NicheNet Analysis Example ===")

# ============================================================================
# Step 1: Prepare Data
# ============================================================================

message("\n1. Preparing data...")

# In practice, load your own Seurat object
# For this example, we create synthetic data with known differences

set.seed(42)

n_cells_per_group <- 200
conditions <- c(rep("control", n_cells_per_group), rep("stimulated", n_cells_per_group))

# Create synthetic data with condition-specific expression
n_genes <- 3000
counts <- matrix(
  rpois(n_cells_per_group * 2 * n_genes, lambda = 0.5),
  nrow = n_genes,
  ncol = n_cells_per_group * 2
)

# Add meaningful gene names
common_genes <- c(
  # Macrophage markers
  "CD14", "CD68", "CSF1R", "MARCO", "FCGR1A",
  # T cell markers
  "CD3D", "CD3E", "CD4", "CD8A", "TRAC",
  # Ligands (higher in stimulated)
  "IL1B", "TNF", "IL6", "CCL2", "CXCL10",
  # Response genes (DE in stimulated)
  "IL2RA", "IFNG", "TNF", "GZMB", "PRF1",
  "ICOS", "CTLA4", "PDCD1", "HAVCR2",
  # Housekeeping
  "ACTB", "GAPDH", "B2M", "RPLP0"
)

rownames(counts) <- c(
  common_genes,
  paste0("GENE", (length(common_genes) + 1):n_genes)
)

colnames(counts) <- paste0("CELL", 1:(n_cells_per_group * 2))

# Simulate condition-specific expression
stim_cells <- (n_cells_per_group + 1):(n_cells_per_group * 2)

# Upregulate ligands in stimulated macrophages
ligands <- c("IL1B", "TNF", "IL6", "CCL2", "CXCL10")
for (lig in ligands) {
  if (lig %in% rownames(counts)) {
    counts[lig, stim_cells[1:100]] <- counts[lig, stim_cells[1:100]] + rpois(100, 10)
  }
}

# Upregulate response genes in stimulated T cells
response_genes <- c("IL2RA", "IFNG", "GZMB", "PRF1", "ICOS")
for (gene in response_genes) {
  if (gene %in% rownames(counts)) {
    counts[gene, stim_cells[101:200]] <- counts[gene, stim_cells[101:200]] + rpois(100, 8)
  }
}

# Create Seurat object
seurat_obj <- CreateSeuratObject(counts = counts)

# Add metadata
seurat_obj$condition <- conditions
seurat_obj$cell_type <- c(
  rep("Macrophage", 100), rep("T_cell", 100),   # control
  rep("Macrophage", 100), rep("T_cell", 100)    # stimulated
)

seurat_obj <- NormalizeData(seurat_obj)

message(sprintf("Created Seurat object: %d cells", ncol(seurat_obj)))
message("Cell type distribution:")
print(table(seurat_obj$cell_type, seurat_obj$condition))

# ============================================================================
# Step 2: Check Database
# ============================================================================

message("\n2. Checking NicheNet database...")
check_nichenet_database("human")

# ============================================================================
# Step 3: Run Differential NicheNet Analysis
# ============================================================================

message("\n3. Running differential NicheNet analysis...")

results_stim <- run_nichenet_aggregate(
  seurat_obj = seurat_obj,
  sender = "Macrophage",
  receiver = "T_cell",
  condition_colname = "condition",
  condition_oi = "stimulated",
  condition_reference = "control",
  organism = "human"
)

# ============================================================================
# Step 4: Explore Stimulated Condition Results
# ============================================================================

message("\n4. Top ligands in stimulated condition:")
print(head(results_stim$ligand_activities[, c("test_ligand", "pearson")], 10))

# Get targets for top ligands
message("\nTop ligand targets:")
for (ligand in head(results_stim$top_ligands, 3)) {
  targets <- head(results_stim$ligand_targets[[ligand]], 5)
  message(sprintf("  %s: %s", ligand, paste(targets, collapse = ", ")))
}

# ============================================================================
# Step 5: Compare with Control (Reverse Analysis)
# ============================================================================

message("\n5. Running control condition analysis for comparison...")

results_ctrl <- run_nichenet_aggregate(
  seurat_obj = seurat_obj,
  sender = "Macrophage",
  receiver = "T_cell",
  condition_colname = "condition",
  condition_oi = "control",        # Now control is "oi"
  condition_reference = "stimulated", # And stimulated is reference
  organism = "human"
)

message("\nTop ligands in control condition:")
print(head(results_ctrl$ligand_activities[, c("test_ligand", "pearson")], 10))

# ============================================================================
# Step 6: Identify Condition-Specific Ligands
# ============================================================================

message("\n6. Identifying condition-specific ligands...")

# Compare rankings
stim_ranking <- results_stim$ligand_activities$test_ligand
ctrl_ranking <- results_ctrl$ligand_activities$test_ligand

# Find ligands highly ranked only in stimulated
stim_specific <- setdiff(head(stim_ranking, 20), head(ctrl_ranking, 30))
ctrl_specific <- setdiff(head(ctrl_ranking, 20), head(stim_ranking, 30))

message("\nStimulated-specific ligands:")
print(stim_specific)

message("\nControl-specific ligands:")
print(ctrl_specific)

# ============================================================================
# Step 7: Create Comparison Visualization
# ============================================================================

message("\n7. Creating comparison plots...")

dir.create("output", showWarnings = FALSE)

# Combine results for comparison
compare_df <- data.frame(
  ligand = unique(c(stim_ranking[1:30], ctrl_ranking[1:30]))
)

compare_df$stim_rank <- match(compare_df$ligand, stim_ranking)
compare_df$ctrl_rank <- match(compare_df$ligand, ctrl_ranking)
compare_df$stim_rank[is.na(compare_df$stim_rank)] <- 999
compare_df$ctrl_rank[is.na(compare_df$ctrl_rank)] <- 999

# Calculate rank difference
compare_df$rank_diff <- compare_df$ctrl_rank - compare_df$stim_rank

# Sort by differential ranking
compare_df <- compare_df[order(-compare_df$rank_diff), ]

# Plot 1: Rank comparison scatter plot
p1 <- ggplot2::ggplot(compare_df, ggplot2::aes(x = stim_rank, y = ctrl_rank)) +
  ggplot2::geom_point(ggplot2::aes(color = rank_diff), size = 3, alpha = 0.7) +
  ggplot2::scale_color_gradient2(low = "blue", mid = "gray", high = "red", midpoint = 0) +
  ggplot2::geom_abline(intercept = 0, slope = 1, linetype = "dashed") +
  ggplot2::labs(
    title = "Ligand Ranking: Stimulated vs Control",
    x = "Rank in Stimulated",
    y = "Rank in Control",
    color = "Rank Difference\n(Control - Stim)"
  ) +
  ggplot2::theme_minimal() +
  ggplot2::theme(plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"))

ggsave("output/diff_rank_comparison.png", p1, width = 8, height = 6, dpi = 150)
message("Saved: output/diff_rank_comparison.png")

# Plot 2: Stimulated condition dot plot
p2 <- plot_ligand_activity_dotplot(
  results_stim$ligand_activities,
  top_n = 15,
  title = "Ligand Activities (Stimulated)"
)
ggsave("output/diff_stim_dotplot.png", p2, width = 8, height = 6, dpi = 150)
message("Saved: output/diff_stim_dotplot.png")

# Plot 3: Control condition dot plot
p3 <- plot_ligand_activity_dotplot(
  results_ctrl$ligand_activities,
  top_n = 15,
  title = "Ligand Activities (Control)"
)
ggsave("output/diff_ctrl_dotplot.png", p3, width = 8, height = 6, dpi = 150)
message("Saved: output/diff_ctrl_dotplot.png")

# ============================================================================
# Step 8: Export Results
# ============================================================================

message("\n8. Exporting results...")

export_nichenet_results(results_stim, "output", prefix = "differential_stim")
export_nichenet_results(results_ctrl, "output", prefix = "differential_ctrl")

# Export comparison
write.csv(compare_df, "output/differential_comparison.csv", row.names = FALSE)

# ============================================================================
# Summary
# ============================================================================

message("\n=== Differential Analysis Complete ===")

message("\nKey Findings:")
message(sprintf("- Stimulated-specific ligands: %s", paste(stim_specific[1:min(3, length(stim_specific))], collapse = ", ")))
message(sprintf("- Control-specific ligands: %s", paste(ctrl_specific[1:min(3, length(ctrl_specific))], collapse = ", ")))

message("\nExpected results based on synthetic data:")
message("- Stimulated: IL1B, TNF, IL6 should be top-ranked")
message("- Control: Should show baseline communication")

message("\nOutput files:")
message("  - differential_stim_ligand_activities.csv")
message("  - differential_ctrl_ligand_activities.csv")
message("  - differential_comparison.csv")
message("  - diff_*.png visualizations")
