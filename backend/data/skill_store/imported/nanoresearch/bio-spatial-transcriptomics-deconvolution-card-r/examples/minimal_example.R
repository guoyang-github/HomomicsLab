#!/usr/bin/env Rscript
#' Minimal Example: CARD Spatial Deconvolution
#'
#' This example demonstrates basic CARD usage for spatial transcriptomics
#' deconvolution using synthetic data.
#'
#' Requirements:
#'   - CARD (>= 1.0)
#'   - SingleCellExperiment
#'   - Matrix
#'
#' Reference:
#'   Ma et al. (2022). CARD: Computational deconvolution of spatial
#'   transcriptomics with conditional autoregressive model. Nature Communications.

# Load required libraries
if (!requireNamespace("CARD", quietly = TRUE)) {
  stop("Package 'CARD' is required. Install with:\n",
       "  devtools::install_github('YingMa0107/CARD')")
}

library(CARD)
library(Matrix)

# Source utility functions
source("../scripts/r/utils.R")

# Set seed for reproducibility
set.seed(42)

cat("========================================\n")
cat("CARD Minimal Example\n")
cat("========================================\n\n")

# ================================================================================
# Step 1: Create Synthetic Data
# ================================================================================

cat("Step 1: Creating synthetic data...\n")

# Create synthetic single-cell reference
n_genes <- 200
n_cells <- 300
cell_types <- c("T_cell", "B_cell", "Myeloid")

# Generate gene names
marker_genes <- c("CD3D", "CD3E", "CD79A", "CD79B", "LYZ", "CD14")
random_genes <- paste0("GENE_", seq_len(n_genes - length(marker_genes)))
gene_names <- c(marker_genes, random_genes)

# Create count matrix with cell-type structure
counts_sc <- matrix(
  rpois(n_genes * n_cells, lambda = 2),
  nrow = n_genes,
  ncol = n_cells
)

# Assign cells to types
cell_type_vec <- rep(cell_types, length.out = n_cells)

# Add marker gene expression
for (i in seq_along(marker_genes)) {
  ct_idx <- ((i - 1) %% length(cell_types)) + 1
  target_cells <- which(cell_type_vec == cell_types[ct_idx])
  counts_sc[i, target_cells] <- counts_sc[i, target_cells] + rpois(length(target_cells), lambda = 15)
}

rownames(counts_sc) <- gene_names[seq_len(nrow(counts_sc))]
colnames(counts_sc) <- paste0("Cell_", seq_len(n_cells))

# Create metadata
sc_meta <- data.frame(
  cell_type = cell_type_vec,
  sample = rep("Sample1", n_cells),
  row.names = colnames(counts_sc)
)

# Create spatial data
n_spots <- 100
n_cols <- 10
n_rows <- 10

counts_sp <- matrix(
  rpois(n_genes * n_spots, lambda = 2),
  nrow = n_genes,
  ncol = n_spots
)

# Create spatial coordinates
x_coords <- rep(1:n_cols, each = n_rows)[1:n_spots]
y_coords <- rep(1:n_rows, n_cols)[1:n_spots]

# Add spatial patterns
for (i in seq_along(cell_types)) {
  spot_idx <- ((i - 1) * 33 + 1):min(i * 33, n_spots)
  marker_idx <- ((i - 1) * 2 + 1):(i * 2)
  counts_sp[marker_idx, spot_idx] <- counts_sp[marker_idx, spot_idx] + rpois(length(marker_idx) * length(spot_idx), lambda = 8)
}

rownames(counts_sp) <- gene_names[seq_len(nrow(counts_sp))]
colnames(counts_sp) <- paste0("Spot_", seq_len(n_spots))

# Create spatial location data frame
spatial_location <- data.frame(
  x = x_coords,
  y = y_coords,
  row.names = colnames(counts_sp)
)

cat(sprintf("  Created scRNA-seq: %d genes x %d cells\n", nrow(counts_sc), ncol(counts_sc)))
cat(sprintf("  Created spatial: %d genes x %d spots\n", nrow(counts_sp), ncol(counts_sp)))
cat(sprintf("  Cell types: %s\n", paste(cell_types, collapse = ", ")))
cat("\n")

# ================================================================================
# Step 2: Validate Data
# ================================================================================

cat("Step 2: Validating input data...\n")

validation <- validate_card_data(
  sc_count = counts_sc,
  spatial_count = counts_sp,
  spatial_location = spatial_location,
  sc_meta = sc_meta,
  min_cells = 20,
  min_genes = 50
)

print_validation_results(validation)

if (!validation$valid) {
  stop("Data validation failed. Please check errors above.")
}
cat("\n")

# ================================================================================
# Step 3: Create CARD Object
# ================================================================================

cat("Step 3: Creating CARD object...\n")

CARD_obj <- createCARDObject(
  sc_count = counts_sc,
  sc_meta = sc_meta,
  spatial_count = counts_sp,
  spatial_location = spatial_location,
  ct.varname = "cell_type",
  ct.select = NULL,              # Use all cell types
  sample.varname = NULL,         # Single sample
  minCountGene = 50,
  minCountSpot = 3
)

cat(sprintf("  CARD object created successfully!\n"))
cat(sprintf("  Cell types: %s\n", paste(CARD_obj@info_parameters$ct.select, collapse = ", ")))
cat("\n")

# ================================================================================
# Step 4: Run CARD Deconvolution
# ================================================================================

cat("Step 4: Running CARD deconvolution...\n")
cat("  (This may take 1-2 minutes)\n\n")

tryCatch({
  CARD_obj <- CARD_deconvolution(CARD_obj)

  cat("\n  Deconvolution complete!\n\n")

  # ================================================================================
  # Step 5: View Results
  # ================================================================================

  cat("Step 5: Results Summary\n")
  cat("------------------------\n")

  # Extract proportions
  proportions <- CARD_obj@Proportion_CARD

  cat(sprintf("Proportion matrix: %d spots x %d cell types\n", nrow(proportions), ncol(proportions)))
  cat(sprintf("Optimal phi: %.2f\n", CARD_obj@info_parameters$phi))
  cat("\nFirst 6 spots:\n")
  print(round(head(proportions), 3))

  cat("\nCell type distribution (mean proportion):\n")
  print(round(colMeans(proportions), 3))

  # Get dominant cell type per spot
  dominant <- get_dominant_cell_type(proportions)
  cat("\nDominant cell type counts:\n")
  print(table(dominant))

  # ================================================================================
  # Step 6: Export Results
  # ================================================================================

  cat("\nStep 6: Exporting results...\n")

  output_dir <- "output"
  if (!dir.exists(output_dir)) {
    dir.create(output_dir)
  }

  # Export proportions
  write.csv(proportions, file.path(output_dir, "card_proportions.csv"))

  # Export summary
  summary <- summarize_card_results(CARD_obj)
  writeLines(
    c(
      "CARD Analysis Summary",
      "=====================",
      "",
      sprintf("Spots analyzed: %d", summary$n_spots),
      sprintf("Cell types: %d", summary$n_cell_types),
      sprintf("Optimal phi: %.3f", summary$optimal_phi),
      "",
      "Cell type proportions (mean):",
      paste(names(summary$mean_proportions),
            round(summary$mean_proportions, 3),
            sep = ": ",
            collapse = "\n")
    ),
    file.path(output_dir, "card_summary.txt")
  )

  # Save full object
  saveRDS(CARD_obj, file.path(output_dir, "card_object.rds"))

  cat("\n")
  cat("========================================\n")
  cat("Analysis complete!\n")
  cat(sprintf("Results saved to: %s/\n", output_dir))
  cat("  - card_proportions.csv\n")
  cat("  - card_summary.txt\n")
  cat("  - card_object.rds\n")
  cat("========================================\n")

}, error = function(e) {
  cat("\n")
  cat("========================================\n")
  cat("Error during analysis:\n")
  cat(conditionMessage(e), "\n")
  cat("========================================\n")
  cat("\nNote: This example uses synthetic data which may not be\n")
  cat("      suitable for actual CARD analysis. For real data,\n")
  cat("      use actual scRNA-seq reference and Visium spatial data.\n")
})
