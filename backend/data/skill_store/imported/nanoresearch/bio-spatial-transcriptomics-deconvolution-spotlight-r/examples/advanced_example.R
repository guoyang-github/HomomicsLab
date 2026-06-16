#!/usr/bin/env Rscript
#' Advanced Example: SPOTlight Comprehensive Spatial Deconvolution
#'
#' This example demonstrates advanced SPOTlight features including:
#' - Two-step deconvolution (trainNMF + runDeconvolution)
#' - Spatial visualization with scatterpie plots
#' - Topic profile analysis
#' - Cell-cell interaction analysis
#' - Multi-sample analysis
#' - Quality control and diagnostics
#'
#' Requirements:
#'   - SPOTlight (>= 1.0)
#'   - Seurat (>= 4.3.0)
#'   - SingleCellExperiment
#'   - SpatialExperiment
#'   - Matrix
#'   - ggplot2
#'   - scatterpie
#'   - ggcorrplot
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

# Source custom scripts
source("../scripts/r/utils.R")
source("../scripts/r/visualization.R")

# Set seed for reproducibility
set.seed(42)

cat("================================================================================\n")
cat("                  SPOTlight Advanced Example\n")
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

# Create spatial data with spatial patterns
n_spots <- 300
n_cols <- 20  # Simulate a 20x15 grid
n_rows <- 15

counts_sp <- matrix(
  rpois(n_genes * n_spots, lambda = 2),
  nrow = n_genes,
  ncol = n_spots
)

# Create spatial coordinates (simulate tissue structure)
x_coords <- rep(1:n_cols, length.out = n_spots)
y_coords <- rep(1:n_rows, each = ceiling(n_spots/n_rows))[1:n_spots]

# Add spatial patterns (different regions have different cell type enrichment)
# Region 1: T-cells and Myeloid (immune infiltration)
region1_spots <- which(x_coords <= 7 & y_coords <= 7)
# Region 2: Fibroblasts and Endothelial (stroma)
region2_spots <- which(x_coords > 7 & x_coords <= 14 & y_coords > 7)
# Region 3: Epithelial (tumor/core region)
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

# Create spatial coordinates data frame
spatial_coords <- data.frame(
  spot = colnames(counts_sp),
  x = x_coords,
  y = y_coords,
  row.names = colnames(counts_sp)
)

# Create marker gene data frame
markers_df <- data.frame(
  gene = all_markers,
  cluster = rep(cell_types, sapply(marker_list, length)),
  avg_log2FC = runif(length(all_markers), 1.5, 4.0),
  p_val_adj = runif(length(all_markers), 1e-15, 1e-8)
)

cat(sprintf("Created scRNA-seq: %d genes x %d cells\n", nrow(counts_sc), ncol(counts_sc)))
cat(sprintf("Created spatial: %d genes x %d spots\n", nrow(counts_sp), ncol(counts_sp)))
cat(sprintf("Spatial grid: %d x %d\n", n_cols, n_rows))
cat(sprintf("Marker genes: %d\n", nrow(markers_df)))
cat("\n")

# Validate data
validation <- validate_spotlight_data(
  sc_counts = counts_sc,
  sp_counts = counts_sp,
  cell_types = cell_type_vec,
  min_cells_per_type = 50,
  min_genes = 200,
  min_spots = 100
)

print_validation_results(validation)

if (!validation$valid) {
  stop("Data validation failed.")
}
cat("\n")

# ================================================================================
# PART 2: Two-Step Deconvolution
# ================================================================================

cat("PART 2: Two-Step Deconvolution (trainNMF + runDeconvolution)\n")
cat("--------------------------------------------------------------------------------\n")

# Step 1: Train NMF model
cat("Step 1: Training NMF model on single-cell data...\n")

nmf_model <- trainNMF(
  x = counts_sc,
  y = rownames(counts_sp),
  groups = cell_type_vec,
  mgs = markers_df,
  gene_id = "gene",
  group_id = "cluster",
  weight_id = "avg_log2FC",
  n_top = NULL,
  scale = TRUE,
  verbose = TRUE
)

cat("\nNMF model trained successfully!\n")
cat(sprintf("  Basis matrix (w): %s\n", paste(dim(nmf_model$w), collapse = " x ")))
cat(sprintf("  Coefficient matrix (h): %s\n", paste(dim(nmf_model$h), collapse = " x ")))
cat("\n")

# Step 2: Deconvolute spatial spots
cat("Step 2: Deconvoluting spatial spots...\n")

decon_results <- runDeconvolution(
  x = counts_sp,
  mod = nmf_model$mod,
  ref = nmf_model$topic,
  scale = TRUE,
  min_prop = 0.01
)

proportions <- decon_results$mat

cat("\nDeconvolution complete!\n")
cat(sprintf("  Proportion matrix: %s\n", paste(dim(proportions), collapse = " x ")))
cat("\n")

# ================================================================================
# PART 3: Result Analysis
# ================================================================================

cat("PART 3: Result Analysis\n")
cat("--------------------------------------------------------------------------------\n")

# Summary statistics
summary <- summarize_spotlight_results(list(mat = proportions, res_ss = decon_results$res_ss))
cat("Summary:\n")
cat(sprintf("  Spots: %d\n", summary$n_spots))
cat(sprintf("  Cell types: %d\n", summary$n_cell_types))
cat(sprintf("  Mean residuals: %.4f\n", summary$mean_residuals))
cat("\nMean proportions:\n")
print(round(summary$mean_proportions, 3))

# Dominant cell types
dominant <- get_dominant_cell_type(proportions)
cat("\nDominant cell type distribution:\n")
print(table(dominant))

# Filter low-confidence predictions
filtered_props <- filter_proportions(
  proportions,
  min_confidence = 0.5,
  min_proportion = 0.05
)
cat(sprintf("\nFiltered proportions (min_conf=0.5, min_prop=0.05): %d non-zero entries\n", sum(filtered_props > 0)))
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

# 1. Spatial scatterpie plot
cat("Creating spatial scatterpie plot...\n")
if (requireNamespace("scatterpie", quietly = TRUE) && requireNamespace("ggplot2", quietly = TRUE)) {
  tryCatch({
    plot_spatial_scatterpie(
      x = spatial_coords,
      y = proportions,
      cell_types = colnames(proportions),
      pie_scale = 0.4,
      save_path = file.path(output_dir, "spatial_scatterpie.png")
    )
    cat("  Saved: spatial_scatterpie.png\n")
  }, error = function(e) {
    cat("  Error creating scatterpie:", conditionMessage(e), "\n")
  })
} else {
  cat("  Skipping (scatterpie/ggplot2 not available)\n")
}

# 2. Topic profiles from NMF
cat("\nCreating topic profile plot...\n")
if (requireNamespace("ggplot2", quietly = TRUE)) {
  tryCatch({
    plot_topic_profiles(
      x = nmf_model,
      y = cell_type_vec,
      facet = TRUE,
      save_path = file.path(output_dir, "topic_profiles.png")
    )
    cat("  Saved: topic_profiles.png\n")
  }, error = function(e) {
    cat("  Error creating topic profiles:", conditionMessage(e), "\n")
  })
} else {
  cat("  Skipping (ggplot2 not available)\n")
}

# 3. Cell type correlation matrix
cat("\nCreating correlation matrix...\n")
if (requireNamespace("ggcorrplot", quietly = TRUE)) {
  tryCatch({
    plot_correlation_matrix(
      x = proportions,
      cor.method = "pearson",
      save_path = file.path(output_dir, "correlation_matrix.png")
    )
    cat("  Saved: correlation_matrix.png\n")
  }, error = function(e) {
    cat("  Error creating correlation matrix:", conditionMessage(e), "\n")
  })
} else {
  cat("  Skipping (ggcorrplot not available)\n")
}

# 4. Cell-cell interactions
cat("\nCreating interaction plot...\n")
tryCatch({
  plot_interactions(
    x = proportions,
    which = "heatmap",
    min_prop = 0.1,
    save_path = file.path(output_dir, "interactions_heatmap.png")
  )
  cat("  Saved: interactions_heatmap.png\n")
}, error = function(e) {
  cat("  Error creating interaction plot:", conditionMessage(e), "\n")
})

# 5. Individual cell type spatial plots
cat("\nCreating individual cell type plots...\n")
if (requireNamespace("ggplot2", quietly = TRUE)) {
  for (ct in head(colnames(proportions), 3)) {
    tryCatch({
      plot_spotlight_cell_type(
        proportions = proportions,
        spatial_coords = spatial_coords,
        cell_type = ct,
        save_path = file.path(output_dir, sprintf("spatial_%s.png", ct))
      )
      cat(sprintf("  Saved: spatial_%s.png\n", ct))
    }, error = function(e) {
      cat(sprintf("  Error creating %s plot: %s\n", ct, conditionMessage(e)))
    })
  }
}
cat("\n")

# ================================================================================
# PART 5: Quality Control
# ================================================================================

cat("PART 5: Quality Control\n")
cat("--------------------------------------------------------------------------------\n")

# QC metrics
qc_metrics <- calculate_qc_metrics(list(mat = proportions, res_ss = decon_results$res_ss))
cat("QC Metrics:\n")
cat(sprintf("  Mean residual SS: %.4f\n", qc_metrics$mean_residual_ss))
cat(sprintf("  Median residual SS: %.4f\n", qc_metrics$median_residual_ss))
cat(sprintf("  Spots with residuals < 0.5: %d (%.1f%%)\n",
            qc_metrics$n_low_residual, qc_metrics$pct_low_residual))
cat(sprintf("  Mean entropy: %.4f\n", qc_metrics$mean_entropy))

# Plot residuals
cat("\nCreating residual plot...\n")
if (requireNamespace("ggplot2", quietly = TRUE)) {
  tryCatch({
    plot_residuals(
      decon_results$res_ss,
      save_path = file.path(output_dir, "residuals.png")
    )
    cat("  Saved: residuals.png\n")
  }, error = function(e) {
    cat("  Error creating residual plot:", conditionMessage(e), "\n")
  })
}
cat("\n")

# ================================================================================
# PART 6: Export Results
# ================================================================================

cat("PART 6: Exporting Results\n")
cat("--------------------------------------------------------------------------------\n")

# Export all results
export_spotlight_results(
  spotlight_ls = list(
    mat = proportions,
    res_ss = decon_results$res_ss,
    NMF = nmf_model
  ),
  output_dir = output_dir,
  prefix = "advanced_example",
  export_proportions = TRUE,
  export_nmf = TRUE,
  export_qc = TRUE
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
  "spatial_scatterpie.png",
  "topic_profiles.png",
  "correlation_matrix.png",
  "interactions_heatmap.png",
  "residuals.png",
  "advanced_example_proportions.csv",
  "advanced_example_qc_metrics.txt",
  "spatial_T_cell.png",
  "spatial_B_cell.png",
  "spatial_Myeloid.png"
)

for (f in output_files) {
  fpath <- file.path(output_dir, f)
  if (file.exists(fpath)) {
    cat(sprintf("  ✓ %s\n", f))
  }
}

cat("\nNext steps:\n")
cat("  1. Review plots in output_advanced/\n")
cat("  2. Load results: results <- readRDS('output_advanced/advanced_example_complete.rds')\n")
cat("  3. For real data, use actual Visium spatial data and scRNA-seq reference\n")
cat("\n")
