#!/usr/bin/env Rscript
#' fastCNV Single-Cell Basic Analysis Example
#'
#' Demonstrates complete CNV inference workflow on single-cell data.

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
source(file.path(script_dir, "..", "scripts", "r", "run_fastcnv.R"))

# Check if fastCNV is installed
if (!requireNamespace("fastCNV", quietly = TRUE)) {
  message("Installing fastCNV...")
  remotes::install_github("must-bioinfo/fastCNV")
}

library(fastCNV)

message("=== fastCNV Single-Cell Analysis Example ===\n")

# =============================================================================
# Step 1: Create Simulated Tumor Data
# =============================================================================

message("Step 1: Creating simulated single-cell tumor dataset...")

set.seed(42)
n_cells <- 300
n_genes <- 1000

# Create expression matrix
counts <- matrix(
  rpois(n_cells * n_genes, lambda = 5),
  nrow = n_genes,
  ncol = n_cells
)

# Gene and cell names
rownames(counts) <- paste0("GENE_", 1:n_genes)
colnames(counts) <- paste0("cell_", 1:n_cells)

# Create cell type annotations
# 40% Tumor, 20% T cells, 15% B cells, 15% Macrophages, 10% Endothelial
cell_types <- c(
  rep("Tumor", 120),
  rep("T_cell", 60),
  rep("B_cell", 45),
  rep("Macrophage", 45),
  rep("Endothelial", 30)
)

# Shuffle
cell_types <- sample(cell_types)

# Create Seurat object
seurat_obj <- CreateSeuratObject(counts = counts)
seurat_obj$cell_type <- cell_types
seurat_obj$annot <- cell_types

# Add sample metadata
seurat_obj$sample <- "Tumor1"

message(sprintf("  Created dataset: %d cells, %d genes", n_cells, n_genes))
message(sprintf("  Cell types: %s", paste(table(cell_types), collapse = ", ")))
message(sprintf("  Reference cells (T_cell, B_cell, Macrophage): %d\n",
                sum(cell_types %in% c("T_cell", "B_cell", "Macrophage"))))

# =============================================================================
# Step 2: Run fastCNV with Reference
# =============================================================================

message("Step 2: Running fastCNV with immune reference...")

result <- run_fastcnv_sc(
  seurat_obj = seurat_obj,
  sample_name = "Simulated_Tumor",
  reference_var = "annot",
  reference_label = c("T_cell", "B_cell", "Macrophage"),
  reCluster = FALSE,
  getCNVPerChromosomeArm = TRUE,
  printPlot = FALSE,
  verbose = TRUE
)

message("  fastCNV complete!\n")

# =============================================================================
# Step 3: Explore CNV Results
# =============================================================================

message("Step 3: Exploring CNV results...")

# Check CNV columns added
cnv_cols <- grep("cnv|_CNV$", colnames(result@meta.data), value = TRUE)
message(sprintf("  CNV columns added (%d):", length(cnv_cols)))
message(sprintf("    %s", paste(head(cnv_cols, 5), collapse = ", ")))
if (length(cnv_cols) > 5) {
  message(sprintf("    ... and %d more", length(cnv_cols) - 5))
}

# CNV fraction summary
if ("cnv_fraction" %in% colnames(result@meta.data)) {
  message("\n  CNV fraction summary:")
  print(summary(result@meta.data$cnv_fraction))
}

# CNV clusters
if ("cnv_clusters" %in% colnames(result@meta.data)) {
  message("\n  CNV cluster distribution:")
  cluster_table <- table(result@meta.data$cnv_clusters)
  print(cluster_table)

  # Compare with original annotations
  message("\n  Comparison: Cell Type vs CNV Clusters")
  comparison <- table(
    Cell_Type = result@meta.data$cell_type,
    CNV_Cluster = result@meta.data$cnv_clusters
  )
  print(comparison)
}

# =============================================================================
# Step 4: CNV Clustering and Classification
# =============================================================================

message("\nStep 4: Running CNV clustering and classification...")

result <- cnv_cluster(result, reference_var = "annot")
message("  CNV clustering complete.")

result <- merge_cnv_clusters(result, mergeThreshold = 0.95)
message("  Merged correlated clusters.")

result <- cnv_classification(result, cnv_thresh = 0.09)
classification_cols <- grep("_CNV_classification$", colnames(result@meta.data), value = TRUE)
message(sprintf("  Classification columns added: %s", paste(head(classification_cols, 3), collapse = ", ")))

# =============================================================================
# Step 5: Summarize by Groups
# =============================================================================

message("\nStep 5: Summarizing CNV by groups...")

# By cell type
message("\n  CNV by Cell Type:")
cell_type_summary <- summarize_cnv_by_cluster(
  result,
  group_by = "cell_type",
  metric = "cnv_fraction"
)
print(cell_type_summary)

# By CNV cluster
message("\n  CNV by CNV Cluster:")
cluster_summary <- summarize_cnv_by_cluster(
  result,
  group_by = "cnv_clusters",
  metric = "cnv_fraction"
)
print(cluster_summary)

# =============================================================================
# Step 6: Extract and Export
# =============================================================================

message("\nStep 6: Extracting and exporting results...")

# Extract CNV metadata
cnv_data <- extract_cnv_metadata(result, include_chromosomes = TRUE)
message(sprintf("  Extracted %d columns of CNV data for %d cells",
                ncol(cnv_data) - 1, nrow(cnv_data)))

# Show sample
message("\n  Sample of CNV data:")
print(head(cnv_data[, 1:min(5, ncol(cnv_data))]))

# Export
output_dir <- file.path(script_dir, "fastcnv_output")
export_cnv_results(
  result,
  output_dir = output_dir,
  prefix = "example_sc",
  export_matrix = FALSE  # Skip matrix for demo
)

message(sprintf("\n  Results exported to: %s", output_dir))

# =============================================================================
# Step 7: Visualization Examples
# =============================================================================

message("\nStep 7: Visualization examples...")

if (requireNamespace("ggplot2", quietly = TRUE)) {
  message("  Available visualizations:")
  message("    - FeaturePlot(result, features = 'cnv_fraction')")
  message("    - DimPlot(result, group.by = 'cnv_clusters')")
  message("    - VlnPlot(result, features = 'cnv_fraction')")
  message("    - plot_chr_arm_umap(result, feature = '20.p_CNV')")
} else {
  message("  Install ggplot2 for visualization: install.packages('ggplot2')")
}

message("\n  For CNV heatmap:")
message("    plot_cnv_heatmap(result, output_file = 'cnv_heatmap.pdf')")

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
message("  2. Run standard Seurat clustering and compare with CNV clusters")
message("  3. Identify tumor subclones using CNV profiles")
message("  4. Compare with known cancer CNV alterations")

message("\nFor multi-sample analysis:")
message("  results <- run_fastcnv_multi_sc(")
message("    seurat_list = list(sample1, sample2, sample3),")
message("    sample_names = c('S1', 'S2', 'S3'),")
message("    reference_var = 'annot',")
message("    reference_label = c('T_cell', 'B_cell')")
message("  )")
