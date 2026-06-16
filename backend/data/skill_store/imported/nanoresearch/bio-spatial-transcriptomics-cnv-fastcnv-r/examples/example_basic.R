#!/usr/bin/env Rscript
#' fastCNV Basic Analysis Example
#'
#' Demonstrates complete CNV inference workflow with simulated data.

# =============================================================================
# Setup
# =============================================================================

# Load required packages
if (!requireNamespace("Seurat", quietly = TRUE)) {
  install.packages("Seurat")
}

library(Seurat)

# Source the fastCNV analysis module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "fastcnv_analysis.R"))

# Check if fastCNV is installed
if (!requireNamespace("fastCNV", quietly = TRUE)) {
  message("Installing fastCNV...")
  remotes::install_github("must-bioinfo/fastCNV")
}

library(fastCNV)

message("=== fastCNV Analysis Example ===\n")

# =============================================================================
# Step 1: Create Simulated Tumor Data
# =============================================================================

message("Step 1: Creating simulated tumor dataset...")

set.seed(42)
n_cells <- 200
n_genes <- 500

# Create expression matrix
counts <- matrix(
  rpois(n_cells * n_genes, lambda = 5),
  nrow = n_genes,
  ncol = n_cells
)

# Add gene names (simulating real gene symbols)
gene_names <- paste0("GENE_", 1:n_genes)
rownames(counts) <- gene_names
colnames(counts) <- paste0("cell_", 1:n_cells)

# Create cell type annotations
# 40% Healthy, 20% Immune (reference), 40% Tumor
cell_types <- c(
  rep("Healthy", 80),
  rep("Immune", 40),
  rep("Tumor", 80)
)

# Create Seurat object
seurat_obj <- CreateSeuratObject(counts = counts)
seurat_obj$cell_type <- cell_types
seurat_obj$annotations <- ifelse(cell_types %in% c("Healthy", "Immune"), "Normal", "Tumor")

message(sprintf("  Created dataset: %d cells, %d genes", n_cells, n_genes))
message(sprintf("  Cell types: %s\n", paste(table(cell_types), collapse = ", ")))

# =============================================================================
# Step 2: Run fastCNV with Reference
# =============================================================================

message("Step 2: Running fastCNV with normal reference...")

result <- run_fastcnv(
  seuratObj = seurat_obj,
  sampleName = "Simulated_Tumor",
  referenceVar = "annotations",
  referenceLabel = "Normal",
  getCNVPerChromosomeArm = TRUE,
  printPlot = FALSE,
  verbose = TRUE
)

message("  fastCNV complete!\n")

# =============================================================================
# Step 3: Access CNV Results
# =============================================================================

message("Step 3: Accessing CNV results...")

# Check what CNV results were added
cnv_cols <- grep("cnv|_CNV", colnames(result@meta.data), value = TRUE)
message(sprintf("  CNV columns added: %s", paste(cnv_cols, collapse = ", ")))

# CNV fraction summary
if ("cnv_fraction" %in% colnames(result@meta.data)) {
  message("\n  CNV fraction summary:")
  print(summary(result@meta.data$cnv_fraction))
}

# CNV clusters
if ("cnv_clusters" %in% colnames(result@meta.data)) {
  message("\n  CNV clusters:")
  print(table(result@meta.data$cnv_clusters))

  # Compare with original annotations
  message("\n  Comparison with original annotations:")
  comparison <- table(
    Original = result@meta.data$cell_type,
    CNV_Cluster = result@meta.data$cnv_clusters
  )
  print(comparison)
}

# =============================================================================
# Step 4: CNV Clustering and Classification
# =============================================================================

message("\nStep 4: Running CNV clustering and classification...")

result <- cnv_cluster(result, referenceVar = "annotations")
message("  CNV clustering complete.")

result <- merge_cnv_clusters(result, mergeThreshold = 0.95)
message("  Merged correlated clusters.")

result <- cnv_classification(result, cnv_thresh = 0.09)
classification_cols <- grep("_CNV_classification$", colnames(result@meta.data), value = TRUE)
message(sprintf("  Classification columns added: %s", paste(head(classification_cols, 3), collapse = ", ")))

# =============================================================================
# Step 5: Extract and Summarize Results
# =============================================================================

message("\nStep 5: Extracting CNV results...")

cnv_results <- extract_cnv_results(result, include_chromosomes = TRUE)
message(sprintf("  Extracted %d columns of CNV data", ncol(cnv_results)))

# Summarize by cell type
message("\n  CNV fraction by cell type:")
summary_df <- summarize_cnv_by_group(
  result,
  group.by = "cell_type",
  metric = "cnv_fraction"
)
print(summary_df)

# =============================================================================
# Step 6: Export Results
# =============================================================================

message("\nStep 6: Exporting results...")

output_dir <- file.path(script_dir, "fastcnv_output")
export_cnv_results(
  result,
  output_dir = output_dir,
  prefix = "example",
  export_matrix = FALSE  # Skip matrix export for demo
)

message(sprintf("\n  Results exported to: %s", output_dir))

# =============================================================================
# Step 7: Visualization (if spatial data available)
# =============================================================================

message("\nStep 7: Visualization...")

# Standard Seurat plots
message("  Creating standard Seurat visualizations...")

# DimPlot by CNV clusters (if dimensionality reduction exists)
if ("pca" %in% names(result@reductions)) {
  message("  - PCA plot by CNV clusters available")
}

# Feature plot of CNV fraction
if ("cnv_fraction" %in% colnames(result@meta.data)) {
  message("  - CNV fraction feature plot available")
}

# Note: For spatial plots, you would need spatial coordinates
# plot_cnv_fraction_spatial(result, features = "cnv_fraction")

# =============================================================================
# Summary
# =============================================================================

message("\n=== Analysis Complete ===")
message("\nKey results:")
message(sprintf("  - Total cells analyzed: %d", ncol(result)))
message(sprintf("  - CNV clusters identified: %d", length(unique(result$cnv_clusters))))
message(sprintf("  - Mean CNV fraction: %.3f", mean(result$cnv_fraction, na.rm = TRUE)))

message("\nNext steps:")
message("  1. Check exported results in:", output_dir)
message("  2. For real data: use SpatialFeaturePlot() for spatial visualization")
message("  3. For real data: use plot_fastcnv_heatmap() for CNV heatmaps")
message("  4. Compare CNV profiles with known cancer alterations")
