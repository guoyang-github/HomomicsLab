#!/usr/bin/env Rscript
#' Minimal Example: SPOTlight Spatial Deconvolution
#'
#' This example demonstrates basic SPOTlight usage for spatial transcriptomics
#' deconvolution using synthetic data.
#'
#' Requirements:
#'   - SPOTlight (>= 1.0)
#'   - Seurat (>= 4.3.0)
#'   - SingleCellExperiment
#'   - Matrix
#'
#' Reference:
#'   Elosua-Bayes et al. (2021). SPOTlight: seeded NMF regression to deconvolute
#'   spatial transcriptomics spots. Nucleic Acids Research, 49(19): e95.

# Load required libraries
if (!requireNamespace("SPOTlight", quietly = TRUE)) {
  stop("Package 'SPOTlight' is required. Install with:\n",
       "  devtools::install_github('Marcello-Sergio/SPOTlight')")
}

library(SPOTlight)
library(Matrix)

# Source utility functions
source("../scripts/r/utils.R")

# Set seed for reproducibility
set.seed(42)

cat("========================================\n")
cat("SPOTlight Minimal Example\n")
cat("========================================\n\n")

# ================================================================================
# Step 1: Create Synthetic Data
# ================================================================================

cat("Step 1: Creating synthetic data...\n")

# Create synthetic single-cell reference
n_genes <- 300
n_cells <- 500
cell_types <- c("T_cell", "B_cell", "Myeloid", "Fibroblast")

# Generate gene names
marker_genes <- c("CD3D", "CD3E", "CD79A", "CD79B", "LYZ", "CD14", "COL1A1", "ACTA2")
random_genes <- paste0("GENE_", seq_len(n_genes - length(marker_genes)))
gene_names <- c(marker_genes, random_genes)

# Create count matrix
counts_sc <- matrix(
  rpois(n_genes * n_cells, lambda = 2),
  nrow = n_genes,
  ncol = n_cells
)

# Add cell-type specific expression patterns
# Assign cells to types
cell_type_vec <- rep(cell_types, length.out = n_cells)

# Add marker gene expression
for (i in seq_along(marker_genes)) {
  cell_type_idx <- ((i - 1) %% length(cell_types)) + 1
  target_cells <- which(cell_type_vec == cell_types[cell_type_idx])
  counts_sc[i, target_cells] <- counts_sc[i, target_cells] + rpois(length(target_cells), lambda = 15)
}

rownames(counts_sc) <- gene_names[seq_len(nrow(counts_sc))]
colnames(counts_sc) <- paste0("Cell_", seq_len(n_cells))

# Create spatial data
n_spots <- 200
counts_sp <- matrix(
  rpois(n_genes * n_spots, lambda = 2),
  nrow = n_genes,
  ncol = n_spots
)

# Add spatial patterns (some spots enriched for specific cell types)
for (i in seq_along(cell_types)) {
  spot_idx <- ((i - 1) * 50 + 1):(i * 50)
  marker_idx <- ((i - 1) * 2 + 1):(i * 2)  # Use 2 markers per type
  counts_sp[marker_idx, spot_idx] <- counts_sp[marker_idx, spot_idx] + rpois(length(marker_idx) * length(spot_idx), lambda = 10)
}

rownames(counts_sp) <- gene_names[seq_len(nrow(counts_sp))]
colnames(counts_sp) <- paste0("Spot_", seq_len(n_spots))

# Create marker gene data frame
markers <- data.frame(
  gene = marker_genes,
  cluster = rep(cell_types, each = 2),
  avg_log2FC = runif(length(marker_genes), 1.5, 3.0),
  p_val_adj = runif(length(marker_genes), 1e-10, 1e-5)
)

cat(sprintf("  Created scRNA-seq: %d genes x %d cells\n", nrow(counts_sc), ncol(counts_sc)))
cat(sprintf("  Created spatial: %d genes x %d spots\n", nrow(counts_sp), ncol(counts_sp)))
cat(sprintf("  Marker genes: %d\n", nrow(markers)))
cat("\n")

# ================================================================================
# Step 2: Validate Data
# ================================================================================

cat("Step 2: Validating input data...\n")

validation <- validate_spotlight_data(
  sc_counts = counts_sc,
  sp_counts = counts_sp,
  cell_types = cell_type_vec,
  min_cells_per_type = 50,
  min_genes = 100,
  min_spots = 50
)

print_validation_results(validation)

if (!validation$valid) {
  stop("Data validation failed. Please check errors above.")
}
cat("\n")

# ================================================================================
# Step 3: Run SPOTlight
# ================================================================================

cat("Step 3: Running SPOTlight deconvolution...\n")
cat("  (This may take a few minutes)\n\n")

tryCatch({
  # Run SPOTlight with reduced parameters for speed
  spotlight_ls <- SPOTlight(
    x = counts_sc,
    y = counts_sp,
    groups = cell_type_vec,
    mgs = markers,
    gene_id = "gene",
    group_id = "cluster",
    weight_id = "avg_log2FC",
    n_top = NULL,        # Use all markers
    scale = TRUE,
    min_prop = 0.01,
    verbose = TRUE
  )

  cat("\n  Deconvolution complete!\n\n")

  # ================================================================================
  # Step 4: View Results
  # ================================================================================

  cat("Step 4: Results Summary\n")
  cat("------------------------\n")

  # Extract proportions
  proportions <- spotlight_ls$mat

  cat(sprintf("Proportion matrix: %d spots x %d cell types\n", nrow(proportions), ncol(proportions)))
  cat("\nFirst 6 spots:\n")
  print(round(head(proportions), 3))

  cat("\nCell type distribution (mean proportion):\n")
  print(round(colMeans(proportions), 3))

  # Get dominant cell type per spot
  dominant <- get_dominant_cell_type(proportions)
  cat("\nDominant cell type counts:\n")
  print(table(dominant))

  # ================================================================================
  # Step 5: Export Results
  # ================================================================================

  cat("\nStep 5: Exporting results...\n")

  output_dir <- "output"
  if (!dir.exists(output_dir)) {
    dir.create(output_dir)
  }

  # Export proportions
  write.csv(proportions, file.path(output_dir, "spotlight_proportions.csv"))

  # Export summary
  summary <- summarize_spotlight_results(spotlight_ls)
  writeLines(
    c(
      "SPOTlight Analysis Summary",
      "==========================",
      "",
      sprintf("Spots analyzed: %d", summary$n_spots),
      sprintf("Cell types: %d", summary$n_cell_types),
      sprintf("Mean residuals: %.4f", summary$mean_residuals),
      "",
      "Cell type proportions (mean):",
      paste(names(summary$mean_proportions),
            round(summary$mean_proportions, 3),
            sep = ": ",
            collapse = "\n")
    ),
    file.path(output_dir, "spotlight_summary.txt")
  )

  # Save full results
  saveRDS(spotlight_ls, file.path(output_dir, "spotlight_results.rds"))

  cat("\n")
  cat("========================================\n")
  cat("Analysis complete!\n")
  cat(sprintf("Results saved to: %s/\n", output_dir))
  cat("  - spotlight_proportions.csv\n")
  cat("  - spotlight_summary.txt\n")
  cat("  - spotlight_results.rds\n")
  cat("========================================\n")

}, error = function(e) {
  cat("\n")
  cat("========================================\n")
  cat("Error during analysis:\n")
  cat(conditionMessage(e), "\n")
  cat("========================================\n")
  cat("\nNote: This example uses synthetic data. For real analysis,\n")
  cat("      use actual scRNA-seq reference and Visium spatial data.\n")
})
