#!/usr/bin/env Rscript
#' Minimal Example: scTenifoldKnk In-silico Knockdown Analysis
#'
#' This example demonstrates a basic single gene knockdown analysis using scTenifoldKnk.
#' It creates synthetic data, runs the knockdown simulation, and visualizes results.
#'
#' Requirements:
#'   - scTenifoldKnk
#'   - scTenifoldNet
#'   - Seurat
#'   - Matrix
#'   - ggplot2 (for visualization)
#'
#' Reference:
#'   Osorio et al. (2020). Systematic characterization of gene knockdown perturbations
#'   in single-cell data. bioRxiv.

# Load required libraries
if (!requireNamespace("scTenifoldKnk", quietly = TRUE)) {
  stop("Package 'scTenifoldKnk' is required. Install with:\n",
       "  remotes::install_github('cailab-tamu/scTenifoldKnk')")
}

library(scTenifoldKnk)
library(Matrix)

# Set seed for reproducibility
set.seed(42)

cat("========================================\n")
cat("scTenifoldKnk Minimal Example\n")
cat("========================================\n\n")

# Step 1: Create synthetic single-cell data
cat("Step 1: Creating synthetic single-cell data...\n")

# Define parameters
n_genes <- 500
n_cells <- 600
cell_types <- c("TypeA", "TypeB", "TypeC")

# Generate gene names (mix of marker genes and random genes)
marker_genes <- c("POU5F1", "SOX2", "NANOG", "KLF4", "MYC", "STAT3")
random_genes <- paste0("GENE_", seq_len(n_genes - length(marker_genes)))
gene_names <- c(marker_genes, random_genes)

# Create count matrix with some structure
# Marker genes have higher expression in specific cell type groups
counts <- matrix(
  rpois(n_genes * n_cells, lambda = 2),
  nrow = n_genes,
  ncol = n_cells
)

# Add higher expression for marker genes
for (i in seq_along(marker_genes)) {
  cell_group <- ((i - 1) %% length(cell_types)) + 1
  cell_idx <- ((cell_group - 1) * 200 + 1):(cell_group * 200)
  counts[i, cell_idx] <- counts[i, cell_idx] + rpois(length(cell_idx), lambda = 10)
}

# Ensure no zero rows/columns
counts <- counts[rowSums(counts) > 0, colSums(counts) > 100]

# Set dimensions
rownames(counts) <- gene_names[seq_len(nrow(counts))]
colnames(counts) <- paste0("Cell_", seq_len(ncol(counts)))

cat(sprintf("  Created matrix: %d genes x %d cells\n", nrow(counts), ncol(counts)))
cat(sprintf("  Target gene for knockdown: %s\n", marker_genes[1]))
cat("\n")

# Step 2: Validate data
cat("Step 2: Validating input data...\n")
source("../scripts/r/utils.R")

validation <- validate_knk_data(
  counts,
  target_gene = marker_genes[1],
  min_cells = 300,
  min_genes = 400
)

print_validation_results(validation)

if (!validation$valid) {
  stop("Data validation failed. Please check errors above.")
}
cat("\n")

# Step 3: Run scTenifoldKnk
cat("Step 3: Running scTenifoldKnk analysis...\n")
cat("  (This may take a few minutes)\n\n")

tryCatch({
  # Run knockdown with reduced parameters for faster execution in example
  result <- scTenifoldKnk(
    countMatrix = counts,
    gKO = marker_genes[1],
    qc = TRUE,
    qc_minLSize = 100,
    qc_minCells = 5,
    nc_nNet = 5,           # Reduced from default 10 for speed
    nc_nCells = 100,       # Reduced from default 500 for speed
    nc_nComp = 3,
    nc_q = 0.9,
    td_K = 3,
    ma_nDim = 2,
    nCores = 1             # Single core for reproducibility
  )

  cat("\n  Analysis complete!\n\n")

  # Step 4: View results
  cat("Step 4: Results Summary\n")
  cat("------------------------\n")

  summary <- summarize_knockdown_results(result, p_cutoff = 0.05)
  stats <- summary$statistics

  cat(sprintf("Total genes analyzed: %d\n", stats$n_genes_analyzed))
  cat(sprintf("Significant genes (FDR < 0.05): %d\n", stats$n_significant))
  cat(sprintf("  - Upregulated: %d\n", stats$n_upregulated))
  cat(sprintf("  - Downregulated: %d\n", stats$n_downregulated))
  cat("\n")

  # Step 5: Top affected genes
  cat("Step 5: Top 10 Most Affected Genes\n")
  cat("-----------------------------------\n")

  top_genes <- head(result$diffRegulation[order(result$diffRegulation$p.adj), ], 10)

  for (i in seq_len(nrow(top_genes))) {
    gene <- top_genes$gene[i]
    z <- top_genes$Z[i]
    p <- top_genes$p.adj[i]
    direction <- ifelse(z > 0, "UP", "DOWN")
    cat(sprintf("%2d. %-15s Z = %6.3f  FDR = %.2e  [%s]\n", i, gene, z, p, direction))
  }
  cat("\n")

  # Step 6: Export results
  cat("Step 6: Exporting results...\n")

  output_dir <- "output"
  if (!dir.exists(output_dir)) {
    dir.create(output_dir)
  }

  export_knockdown_results(
    result,
    output_dir = output_dir,
    prefix = "minimal_example",
    gKO = marker_genes[1],
    export_networks = FALSE,  # Skip large network files for example
    export_genelist = TRUE,
    export_tables = TRUE
  )

  # Generate report
  report <- create_knockdown_report(
    result,
    gKO = marker_genes[1],
    output_file = file.path(output_dir, "minimal_example_report.txt")
  )

  cat("\n")
  cat("========================================\n")
  cat("Analysis complete!\n")
  cat(sprintf("Results saved to: %s/\n", output_dir))
  cat("========================================\n")

}, error = function(e) {
  cat("\n")
  cat("========================================\n")
  cat("Error during analysis:\n")
  cat(conditionMessage(e), "\n")
  cat("========================================\n")
  cat("\nNote: This example uses synthetic data which may not be\n")
  cat("      suitable for actual scTenifoldKnk analysis. For\n")
  cat("      real data, use ~1000+ cells and 1000+ genes.\n")
})
