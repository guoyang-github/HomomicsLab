#!/usr/bin/env Rscript
#' Minimal working example for bio-single-cell-enrichment-aucell-r
#'
#' Demonstrates basic AUCell workflow with test data

# Load required libraries
if (!requireNamespace("AUCell", quietly = TRUE)) {
  install.packages("BiocManager")
  BiocManager::install("AUCell")
}
if (!requireNamespace("Seurat", quietly = TRUE)) {
  install.packages("Seurat")
}

library(AUCell)
library(Seurat)

# Source skill functions
source("../scripts/r/run_aucell.R")

# ============================================
# 1. Load test data (using Seurat's pbmc3k dataset)
# ============================================
message("Loading test data...")

# Download pbmc3k data if not available
data_dir <- "./test_data"
dir.create(data_dir, showWarnings = FALSE, recursive = TRUE)

# For this example, we'll create synthetic data
# In practice, use: seurat_obj <- readRDS("your_data.rds")
set.seed(42)
n_cells <- 500
n_genes <- 2000

# Create synthetic count matrix
counts <- matrix(
  rpois(n_cells * n_genes, lambda = 0.5),
  nrow = n_genes,
  ncol = n_cells
)
rownames(counts) <- paste0("Gene", 1:n_genes)
colnames(counts) <- paste0("Cell", 1:n_cells)

# Add some marker genes with higher expression
marker_genes <- list(
  T_cells = c("Gene1", "Gene2", "Gene3", "Gene4"),
  B_cells = c("Gene5", "Gene6", "Gene7", "Gene8"),
  Myeloid = c("Gene9", "Gene10", "Gene11", "Gene12")
)

# Add expression to marker genes
counts[marker_genes$T_cells, 1:100] <- counts[marker_genes$T_cells, 1:100] + 5
counts[marker_genes$B_cells, 101:200] <- counts[marker_genes$B_cells, 101:200] + 5
counts[marker_genes$Myeloid, 201:300] <- counts[marker_genes$Myeloid, 201:300] + 5

# Rename genes to real marker names
rownames(counts)[1:12] <- c(
  "CD3D", "CD3E", "CD4", "CD8A",           # T cells
  "CD19", "CD79A", "CD79B", "MS4A1",       # B cells
  "CD14", "LYZ", "CST3", "FCGR3A"          # Myeloid
)

marker_genes <- list(
  T_cells = c("CD3D", "CD3E", "CD4", "CD8A"),
  B_cells = c("CD19", "CD79A", "CD79B", "MS4A1"),
  Myeloid = c("CD14", "LYZ", "CST3", "FCGR3A")
)

message(sprintf("Created %d cells x %d genes matrix", ncol(counts), nrow(counts)))

# ============================================
# 2. Run AUCell Analysis
# ============================================
message("\nRunning AUCell analysis...")

auc_results <- run_aucell(
  expr_matrix = counts,
  gene_sets = marker_genes,
  auc_threshold = 0.05,
  nCores = 1,
  verbose = TRUE
)

# ============================================
# 3. Access Results
# ============================================
message("\nAccessing results...")

auc_matrix <- getAUC(auc_results)
message(sprintf("AUC matrix dimensions: %d gene sets x %d cells",
                nrow(auc_matrix), ncol(auc_matrix)))

# Print summary statistics
message("\nAUC Score Summary:")
for (gs in rownames(auc_matrix)) {
  scores <- as.numeric(auc_matrix[gs, ])
  message(sprintf("  %s: mean=%.3f, max=%.3f",
                  gs, mean(scores), max(scores)))
}

# ============================================
# 4. Identify Positive Cells
# ============================================
message("\nIdentifying signature-positive cells...")

for (gs in rownames(auc_matrix)) {
  positive_cells <- filter_cells_by_auc(
    auc_results,
    gene_set = gs,
    threshold_method = "auto",
    return_names = TRUE
  )
  message(sprintf("  %s: %d positive cells (%.1f%%)",
                  gs, length(positive_cells),
                  100 * length(positive_cells) / ncol(auc_matrix)))
}

# ============================================
# 5. Export Results
# ============================================
message("\nExporting results...")

output_dir <- "./output"
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

export_aucell_results(
  auc_results,
  output_file = file.path(output_dir, "aucell_scores.csv"),
  format = "csv"
)

export_aucell_results(
  auc_results,
  output_file = file.path(output_dir, "aucell_results.rds"),
  format = "rds"
)

# ============================================
# Complete
# ============================================
message("\n========================================")
message("Example complete!")
message(sprintf("Results saved to %s/", output_dir))
message("========================================")
