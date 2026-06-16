#!/usr/bin/env Rscript
#' SCEVAN Minimal Example
#'
#' Demonstrates the SCEVAN helper workflow using simulated data.
#' Note: Actual SCEVAN::pipelineCNA() requires real tumor data and the SCEVAN
#' package installed from GitHub. This example focuses on helper functions.
#'
#' Requirements:
#'   devtools::install_github("AntonioDeFalco/SCEVAN")
#'
#' Usage:
#'   Rscript minimal_example.R

# Source skill helpers
source("../scripts/r/run_scevan.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("SCEVAN Minimal Example - CNV Analysis Workflow\n")
cat(rep("=", 70), "\n", sep = "")

# ==============================================================================
# Step 1: Create Simulated Data
# ==============================================================================
cat("\nStep 1: Creating simulated count matrix...\n")

set.seed(42)

n_cells <- 100
n_genes <- 500

counts_matrix <- matrix(rpois(n_cells * n_genes, lambda = 3),
                        nrow = n_genes, ncol = n_cells)

# Gene symbols as rownames (SCEVAN requirement)
gene_names <- paste0("GENE", 1:n_genes)
rownames(counts_matrix) <- gene_names

# Cell barcodes as colnames
cell_barcodes <- paste0("CELL", 1:n_cells)
colnames(counts_matrix) <- cell_barcodes

cat(sprintf("  Created data: %d genes x %d cells\n", n_genes, n_cells))
cat(sprintf("  First gene: %s, First cell: %s\n", rownames(counts_matrix)[1],
            colnames(counts_matrix)[1]))

# ==============================================================================
# Step 2: Run SCEVAN (would require real tumor data)
# ==============================================================================
cat("\nStep 2: SCEVAN pipeline...\n")
cat("  (Skipped in this example - requires real tumor data)\n")
cat("  Example call:\n")
cat("    results <- run_scevan(\n")
cat("      count_mtx = counts_matrix,\n")
cat("      sample_name = \"Tumor1\",\n")
cat("      par_cores = 4,\n")
cat("      SUBCLONES = TRUE,\n")
cat("      beta_vega = 0.5,\n")
cat("      organism = \"human\"\n")
cat("    )\n")

# ==============================================================================
# Step 3: Simulate SCEVAN Results for Helper Demonstration
# ==============================================================================
cat("\nStep 3: Simulating SCEVAN output for helper demonstration...\n")

# Mock results (what pipelineCNA would return)
mock_results <- data.frame(
  class = sample(c("malignant", "non-malignant"), n_cells, replace = TRUE, prob = c(0.6, 0.4)),
  subclone = NA_character_,
  row.names = cell_barcodes
)
# Assign subclones only to malignant cells
malig_cells <- rownames(mock_results)[mock_results$class == "malignant"]
mock_results[malig_cells, "subclone"] <- sample(c("subclone_1", "subclone_2"),
                                                 length(malig_cells), replace = TRUE)

cat(sprintf("  Simulated %d malignant, %d non-malignant cells\n",
            sum(mock_results$class == "malignant"),
            sum(mock_results$class == "non-malignant")))

# ==============================================================================
# Step 4: Summarize Results
# ==============================================================================
cat("\nStep 4: Summarizing results...\n")
summarize_scevan(mock_results)

# ==============================================================================
# Step 5: Create Mock Seurat Object and Add Results
# ==============================================================================
cat("\nStep 5: Adding results to Seurat object...\n")

if (requireNamespace("Seurat", quietly = TRUE)) {
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts_matrix)

  # Add SCEVAN results
  seurat_obj <- add_scevan_to_seurat(seurat_obj, mock_results)

  cat("  Added columns:\n")
  cat("    - scevan_class\n")
  cat("    - scevan_subclone\n")
  cat("\n  Classification table:\n")
  print(table(seurat_obj$scevan_class, useNA = "ifany"))

  # ==============================================================================
  # Step 6: Plot Classification
  # ==============================================================================
  cat("\nStep 6: Running PCA + UMAP for visualization...\n")
  seurat_obj <- Seurat::NormalizeData(seurat_obj, verbose = FALSE)
  seurat_obj <- Seurat::FindVariableFeatures(seurat_obj, verbose = FALSE)
  seurat_obj <- Seurat::ScaleData(seurat_obj, verbose = FALSE)
  seurat_obj <- Seurat::RunPCA(seurat_obj, verbose = FALSE)
  seurat_obj <- Seurat::RunUMAP(seurat_obj, dims = 1:10, verbose = FALSE)

  cat("  Plotting classification on UMAP...\n")
  p <- plot_scevan_classification(seurat_obj, reduction = "umap")
  ggplot2::ggsave("scevan_classification.png", p, width = 8, height = 6, dpi = 150)
  cat("  Saved: scevan_classification.png\n")

} else {
  cat("  (Seurat not installed - skipping Seurat integration demo)\n")
}

# ==============================================================================
# Summary
# ==============================================================================
cat("\n", rep("=", 70), "\n", sep = "")
cat("Example Complete!\n")
cat(rep("=", 70), "\n", sep = "")

cat("\nKey steps demonstrated:\n")
cat("  1. Count matrix preparation (gene symbols as rownames)\n")
cat("  2. SCEVAN workflow structure\n")
cat("  3. summarize_scevan() - result summary\n")
cat("  4. add_scevan_to_seurat() - merge results into Seurat\n")
cat("  5. plot_scevan_classification() - visualize on UMAP\n")
