#!/usr/bin/env Rscript
#' Advanced Example: CARD Comprehensive Spatial Deconvolution
#'
#' This example demonstrates advanced CARD features including:
#' - Reference-based and reference-free deconvolution
#' - High-resolution imputation
#' - Single-cell mapping
#' - Multiple visualization types
#' - Multi-sample analysis
#'
#' Requirements:
#'   - CARD (>= 1.0)
#'   - SingleCellExperiment
#'   - SpatialExperiment
#'   - Matrix
#'   - ggplot2
#'   - scatterpie
#'   - ggcorrplot
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

# Source custom scripts
source("../scripts/r/utils.R")
source("../scripts/r/visualization.R")

# Set seed for reproducibility
set.seed(42)

cat("================================================================================\n")
cat("                  CARD Advanced Example\n")
cat("================================================================================\n\n")

# ================================================================================
# PART 1: Data Preparation
# ================================================================================

cat("PART 1: Data Preparation\n")
cat("--------------------------------------------------------------------------------\n")

# Create synthetic data with realistic structure
n_genes <- 500
n_cells <- 1000
cell_types <- c("T_cell", "B_cell", "Myeloid", "Fibroblast", "Endothelial", "Epithelial")

# Define marker genes for each cell type
marker_list <- list(
  T_cell = c("CD3D", "CD3E", "CD4", "CD8A", "TRAC"),
  B_cell = c("CD79A", "CD79B", "MS4A1", "CD19", "IGHM"),
  Myeloid = c("LYZ", "CD14", "CD68", "CSF1R", "MARCO"),
  Fibroblast = c("COL1A1", "COL1A2", "ACTA2", "PDGFRA", "DCN"),
  Endothelial = c("PECAM1", "VWF", "CDH5", "ENG", "KDR"),
  Epithelial = c("EPCAM", "KRT18", "KRT19", "CDH1", "MUC1")
)

all_markers <- unlist(marker_list)
random_genes <- paste0("GENE_", seq_len(n_genes - length(all_markers)))
gene_names <- c(all_markers, random_genes)

# Create single-cell reference with structure
counts_sc <- matrix(
  rpois(n_genes * n_cells, lambda = 2),
  nrow = n_genes,
  ncol = n_cells
)

# Assign cells to types with varying proportions
cell_type_vec <- sample(cell_types, n_cells, replace = TRUE, prob = c(0.2, 0.15, 0.2, 0.25, 0.1, 0.1))

# Add marker gene expression
for (ct in cell_types) {
  markers <- marker_list[[ct]]
  target_cells <- which(cell_type_vec == ct)
  for (marker in markers) {
    marker_idx <- which(gene_names == marker)
    if (length(marker_idx) > 0) {
      counts_sc[marker_idx, target_cells] <- counts_sc[marker_idx, target_cells] +
        rpois(length(target_cells), lambda = 20)
    }
  }
}

rownames(counts_sc) <- gene_names[seq_len(nrow(counts_sc))]
colnames(counts_sc) <- paste0("Cell_", seq_len(n_cells))

# Create metadata
sc_meta <- data.frame(
  cell_type = cell_type_vec,
  sample = rep("Sample1", n_cells),
  row.names = colnames(counts_sc)
)

# Create spatial data with spatial patterns
n_spots <- 300
n_cols <- 20
n_rows <- 15

counts_sp <- matrix(
  rpois(n_genes * n_spots, lambda = 2),
  nrow = n_genes,
  ncol = n_spots
)

# Create spatial coordinates
x_coords <- rep(1:n_cols, length.out = n_spots)
y_coords <- rep(1:n_rows, each = ceiling(n_spots/n_rows))[1:n_spots]

# Add spatial patterns
region1_spots <- which(x_coords <= 7 & y_coords <= 7)
region2_spots <- which(x_coords > 7 & x_coords <= 14 & y_coords > 7)
region3_spots <- which(x_coords > 14)

for (spot_idx in region1_spots) {
  t_markers <- marker_list$T_cell
  my_markers <- marker_list$Myeloid
  marker_idx <- which(gene_names %in% c(t_markers, my_markers))
  counts_sp[marker_idx, spot_idx] <- counts_sp[marker_idx, spot_idx] + rpois(length(marker_idx), lambda = 12)
}

for (spot_idx in region2_spots) {
  fib_markers <- marker_list$Fibroblast
  end_markers <- marker_list$Endothelial
  marker_idx <- which(gene_names %in% c(fib_markers, end_markers))
  counts_sp[marker_idx, spot_idx] <- counts_sp[marker_idx, spot_idx] + rpois(length(marker_idx), lambda = 12)
}

for (spot_idx in region3_spots) {
  epi_markers <- marker_list$Epithelial
  marker_idx <- which(gene_names %in% epi_markers)
  counts_sp[marker_idx, spot_idx] <- counts_sp[marker_idx, spot_idx] + rpois(length(marker_idx), lambda = 15)
}

rownames(counts_sp) <- gene_names[seq_len(nrow(counts_sp))]
colnames(counts_sp) <- paste0("Spot_", seq_len(n_spots))

# Create spatial location data frame
spatial_location <- data.frame(
  x = x_coords,
  y = y_coords,
  row.names = colnames(counts_sp)
)

cat(sprintf("Created scRNA-seq: %d genes x %d cells\n", nrow(counts_sc), ncol(counts_sc)))
cat(sprintf("Created spatial: %d genes x %d spots\n", nrow(counts_sp), ncol(counts_sp)))
cat(sprintf("Spatial grid: %d x %d\n", n_cols, n_rows))
cat("\n")

# Validate data
validation <- validate_card_data(
  sc_count = counts_sc,
  spatial_count = counts_sp,
  spatial_location = spatial_location,
  sc_meta = sc_meta,
  min_cells = 20,
  min_genes = 200
)

print_validation_results(validation)

if (!validation$valid) {
  stop("Data validation failed.")
}
cat("\n")

# ================================================================================
# PART 2: Reference-Based Deconvolution
# ================================================================================

cat("PART 2: Reference-Based Deconvolution\n")
cat("--------------------------------------------------------------------------------\n")

# Create CARD object
CARD_obj <- createCARDObject(
  sc_count = counts_sc,
  sc_meta = sc_meta,
  spatial_count = counts_sp,
  spatial_location = spatial_location,
  ct.varname = "cell_type",
  ct.select = NULL,
  sample.varname = NULL,
  minCountGene = 100,
  minCountSpot = 5
)

# Run deconvolution
CARD_obj <- CARD_deconvolution(CARD_obj)

proportions <- CARD_obj@Proportion_CARD

cat("\nDeconvolution complete!\n")
cat(sprintf("Optimal phi: %.2f\n", CARD_obj@info_parameters$phi))
cat(sprintf("Proportion matrix: %s\n", paste(dim(proportions), collapse = " x ")))
cat("\n")

# ================================================================================
# PART 3: Result Analysis
# ================================================================================

cat("PART 3: Result Analysis\n")
cat("--------------------------------------------------------------------------------\n")

# Summary statistics
summary <- summarize_card_results(CARD_obj)
cat("Summary:\n")
cat(sprintf("  Spots: %d\n", summary$n_spots))
cat(sprintf("  Cell types: %d\n", summary$n_cell_types))
cat(sprintf("  Optimal phi: %.3f\n", summary$optimal_phi))
cat("\nMean proportions:\n")
print(round(summary$mean_proportions, 3))

# Dominant cell types
dominant <- get_dominant_cell_type(proportions)
cat("\nDominant cell type distribution:\n")
print(table(dominant))
cat("\n")

# ================================================================================
# PART 4: Visualization
# ================================================================================

cat("PART 4: Visualization\n")
cat("--------------------------------------------------------------------------------\n")

output_dir <- "output_advanced"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# 1. Spatial proportion maps
cat("Creating spatial proportion maps...\n")
if (requireNamespace("ggplot2", quietly = TRUE)) {
  tryCatch({
    p <- CARD.visualize.prop(
      proportion = proportions,
      spatial_location = spatial_location,
      ct.visualize = cell_types[1:4],
      colors = c("lightblue", "lightyellow", "red"),
      NumCols = 2,
      pointSize = 3.0
    )
    ggplot2::ggsave(file.path(output_dir, "spatial_proportions.png"), p, width = 12, height = 10)
    cat("  Saved: spatial_proportions.png\n")
  }, error = function(e) {
    cat("  Error creating spatial plot:", conditionMessage(e), "\n")
  })
}

# 2. Scatterpie plot
cat("\nCreating scatterpie plot...\n")
if (requireNamespace("scatterpie", quietly = TRUE)) {
  tryCatch({
    p <- CARD.visualize.pie(
      proportion = proportions,
      spatial_location = spatial_location,
      colors = NULL,
      radius = NULL,
      seed = 12345
    )
    ggplot2::ggsave(file.path(output_dir, "scatterpie.png"), p, width = 10, height = 8)
    cat("  Saved: scatterpie.png\n")
  }, error = function(e) {
    cat("  Error creating scatterpie:", conditionMessage(e), "\n")
  })
}

# 3. Correlation matrix
cat("\nCreating correlation matrix...\n")
if (requireNamespace("ggcorrplot", quietly = TRUE)) {
  tryCatch({
    p <- CARD.visualize.Cor(
      proportion = proportions,
      colors = c("#91a28c", "white", "#8f2c37")
    )
    ggplot2::ggsave(file.path(output_dir, "correlation_matrix.png"), p, width = 8, height = 8)
    cat("  Saved: correlation_matrix.png\n")
  }, error = function(e) {
    cat("  Error creating correlation matrix:", conditionMessage(e), "\n")
  })
}

# 4. Two cell type comparison
cat("\nCreating two cell type comparison...\n")
tryCatch({
  p <- CARD.visualize.prop.2CT(
    proportion = proportions,
    spatial_location = spatial_location,
    ct2.visualize = cell_types[1:2],
    colors = list(c("lightblue", "lightyellow", "red"),
                  c("lightblue", "lightyellow", "black"))
  )
  ggplot2::ggsave(file.path(output_dir, "two_celltype_comparison.png"), p, width = 8, height = 8)
  cat("  Saved: two_celltype_comparison.png\n")
}, error = function(e) {
  cat("  Error creating comparison plot:", conditionMessage(e), "\n")
})
cat("\n")

# ================================================================================
# PART 5: High-Resolution Imputation
# ================================================================================

cat("PART 5: High-Resolution Imputation\n")
cat("--------------------------------------------------------------------------------\n")

if (requireNamespace("concaveman", quietly = TRUE)) {
  cat("Running high-resolution imputation...\n")
  tryCatch({
    CARD_obj <- CARD.imputation(
      CARD_obj,
      NumGrids = 1000,
      ineibor = 10,
      exclude = NULL
    )

    cat(sprintf("\nImputation complete!\n"))
    cat(sprintf("  Refined spots: %d\n", nrow(CARD_obj@refined_prop)))
    cat(sprintf("  Refined genes: %d\n", nrow(CARD_obj@refined_expression)))

    # Visualize refined proportions
    if (requireNamespace("ggplot2", quietly = TRUE)) {
      refined_coords <- data.frame(
        x = as.numeric(sapply(strsplit(rownames(CARD_obj@refined_prop), "x"), "[", 1)),
        y = as.numeric(sapply(strsplit(rownames(CARD_obj@refined_prop), "x"), "[", 2)),
        row.names = rownames(CARD_obj@refined_prop)
      )

      p <- CARD.visualize.prop(
        proportion = CARD_obj@refined_prop,
        spatial_location = refined_coords,
        ct.visualize = cell_types[1:3],
        colors = c("lightblue", "lightyellow", "red"),
        NumCols = 3,
        pointSize = 2.0
      )
      ggplot2::ggsave(file.path(output_dir, "refined_proportions.png"), p, width = 15, height = 5)
      cat("  Saved: refined_proportions.png\n")
    }
  }, error = function(e) {
    cat("  Error in imputation:", conditionMessage(e), "\n")
  })
} else {
  cat("Skipping imputation (concaveman not available)\n")
}
cat("\n")

# ================================================================================
# PART 6: Reference-Free Deconvolution (CARDfree)
# ================================================================================

cat("PART 6: Reference-Free Deconvolution\n")
cat("--------------------------------------------------------------------------------\n")

# Create marker list for CARDfree
markerList <- list(
  CT1 = c("CD3D", "CD3E", "CD8A"),
  CT2 = c("CD79A", "CD79B", "MS4A1"),
  CT3 = c("LYZ", "CD14", "CD68"),
  CT4 = c("COL1A1", "COL1A2", "ACTA2"),
  CT5 = c("PECAM1", "VWF", "CDH5"),
  CT6 = c("EPCAM", "KRT18", "KRT19")
)

tryCatch({
  CARDfree_obj <- createCARDfreeObject(
    markerList = markerList,
    spatial_count = counts_sp,
    spatial_location = spatial_location,
    minCountGene = 100,
    minCountSpot = 5
  )

  CARDfree_obj <- CARD_refFree(CARDfree_obj)

  cat("Reference-free deconvolution complete!\n")
  cat(sprintf("Optimal phi: %.2f\n", CARDfree_obj@info_parameters$phi))
  cat(sprintf("Estimated reference matrix: %s\n", paste(dim(CARDfree_obj@estimated_refMatrix), collapse = " x ")))

  # Export CARDfree results
  write.csv(CARDfree_obj@Proportion_CARD, file.path(output_dir, "cardfree_proportions.csv"))
  cat("  Saved: cardfree_proportions.csv\n")
}, error = function(e) {
  cat("  Error in CARDfree:", conditionMessage(e), "\n")
})
cat("\n")

# ================================================================================
# PART 7: Export Results
# ================================================================================

cat("PART 7: Exporting Results\n")
cat("--------------------------------------------------------------------------------\n")

# Export all results
export_card_results(
  CARD_obj,
  output_dir = output_dir,
  prefix = "advanced_example",
  export_proportions = TRUE,
  export_refined = TRUE,
  export_object = TRUE
)

cat(sprintf("Results exported to: %s/\n", output_dir))
cat("\n")

# ================================================================================
# Summary
# ================================================================================

cat("================================================================================\n")
cat("                           Analysis Complete!\n")
cat("================================================================================\n")
cat("\nOutput files:\n")

output_files <- c(
  "spatial_proportions.png",
  "scatterpie.png",
  "correlation_matrix.png",
  "two_celltype_comparison.png",
  "refined_proportions.png",
  "cardfree_proportions.csv",
  "advanced_example_proportions.csv",
  "advanced_example_refined_proportions.csv",
  "advanced_example_object.rds"
)

for (f in output_files) {
  fpath <- file.path(output_dir, f)
  if (file.exists(fpath)) {
    cat(sprintf("  ✓ %s\n", f))
  }
}

cat("\nNext steps:\n")
cat("  1. Review plots in output_advanced/\n")
cat("  2. Load results: CARD_obj <- readRDS('output_advanced/advanced_example_object.rds')\n")
cat("  3. For real data, use actual Visium spatial data and scRNA-seq reference\n")
cat("\n")
