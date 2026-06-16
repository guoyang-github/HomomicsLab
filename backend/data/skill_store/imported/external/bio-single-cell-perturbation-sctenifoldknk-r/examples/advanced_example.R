#!/usr/bin/env Rscript
#' Advanced Example: scTenifoldKnk Comprehensive Analysis
#'
#' This example demonstrates advanced features of scTenifoldKnk including:
#' - Multiple gene knockdowns
#' - Comparison across knockdowns
#' - Pathway enrichment analysis
#' - Network visualization
#' - Comparison with experimental data
#'
#' Requirements:
#'   - scTenifoldKnk
#'   - scTenifoldNet
#'   - Seurat
#'   - Matrix
#'   - enrichR (for enrichment)
#'   - fgsea (for GSEA)
#'   - ggplot2 (for visualization)
#'   - pheatmap (for heatmaps)
#'   - igraph (for network plots)
#'
#' Reference:
#'   Osorio et al. (2020). Systematic characterization of gene knockdown perturbations
#'   in single-cell data. bioRxiv.

# Load required libraries
if (!requireNamespace("scTenifoldKnk", quietly = TRUE)) {
  stop("Package 'scTenifoldKnk' is required.")
}

library(scTenifoldKnk)
library(Matrix)

# Source custom scripts
source("../scripts/r/core_analysis.R")
source("../scripts/r/enrichment.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# Set seed for reproducibility
set.seed(42)

cat("================================================================================\n")
cat("                  scTenifoldKnk Advanced Example\n")
cat("================================================================================\n\n")

# ================================================================================
# PART 1: Data Preparation
# ================================================================================

cat("PART 1: Data Preparation\n")
cat("--------------------------------------------------------------------------------\n")

# Option 1: Load from Seurat object (recommended)
# seurat_obj <- readRDS("your_data.rds")
# counts <- GetAssayData(seurat_obj, slot = "counts")

# Option 2: Load from MatrixMarket files
# counts <- readMM("matrix.mtx")
# rownames(counts) <- readLines("genes.txt")
# colnames(counts) <- readLines("barcodes.txt")

# Option 3: Create synthetic data for this example
cat("Creating synthetic single-cell data for demonstration...\n")

n_genes <- 1000
n_cells <- 1000

# Define transcription factors of interest
tf_genes <- c("POU5F1", "SOX2", "NANOG", "KLF4", "MYC")
random_genes <- paste0("GENE_", seq_len(n_genes - length(tf_genes)))
gene_names <- c(tf_genes, random_genes)

# Create structured count matrix
counts <- matrix(
  rpois(n_genes * n_cells, lambda = 3),
  nrow = n_genes,
  ncol = n_cells
)

# Add cell-type specific expression patterns
for (i in seq_along(tf_genes)) {
  cell_group <- ((i - 1) %% 3) + 1
  cell_idx <- ((cell_group - 1) * 333 + 1):min(cell_group * 333, n_cells)
  counts[i, cell_idx] <- counts[i, cell_idx] + rpois(length(cell_idx), lambda = 15)
}

# Add correlated gene expression (regulatory network effects)
for (i in seq_along(tf_genes)) {
  # Add correlated genes for each TF
  correlated_idx <- (length(tf_genes) + (i - 1) * 50 + 1):(length(tf_genes) + i * 50)
  correlated_idx <- correlated_idx[correlated_idx <= n_genes]

  for (j in correlated_idx) {
    counts[j, ] <- counts[j, ] + round(counts[i, ] * 0.3)
  }
}

# Clean up
rownames(counts) <- gene_names[seq_len(nrow(counts))]
colnames(counts) <- paste0("Cell_", seq_len(ncol(counts)))
counts <- counts[rowSums(counts) > 10, colSums(counts) > 200]

cat(sprintf("Created matrix: %d genes x %d cells\n", nrow(counts), ncol(counts)))
cat(sprintf("Genes for knockdown analysis: %s\n", paste(tf_genes, collapse = ", ")))
cat("\n")

# Validate data
validation <- validate_knk_data(counts, min_cells = 500, min_genes = 800)
print_validation_results(validation)

if (!validation$valid) {
  stop("Data validation failed.")
}
cat("\n")

# ================================================================================
# PART 2: Single Gene Knockdown with Full Pipeline
# ================================================================================

cat("PART 2: Single Gene Knockdown (POU5F1)\n")
cat("--------------------------------------------------------------------------------\n")

target_gene <- "POU5F1"

if (target_gene %in% rownames(counts)) {
  cat(sprintf("Running complete analysis for %s...\n\n", target_gene))

  result_single <- run_complete_knockdown_analysis(
    countMatrix = counts,
    gKO = target_gene,
    output_dir = "output_advanced",
    run_enrichment = requireNamespace("enrichR", quietly = TRUE),
    create_plots = requireNamespace("ggplot2", quietly = TRUE),
    qc = TRUE,
    qc_minLSize = 200,
    nc_nNet = 5,        # Reduced for speed
    nc_nCells = 200,    # Reduced for speed
    nc_q = 0.9,
    verbose = TRUE
  )

  cat("\n")
} else {
  cat(sprintf("Gene %s not found in data, skipping single analysis\n\n", target_gene))
}

# ================================================================================
# PART 3: Multiple Gene Knockdowns
# ================================================================================

cat("PART 3: Multiple Gene Knockdown Analysis\n")
cat("--------------------------------------------------------------------------------\n")

# Define genes to knock down (use available ones)
genes_to_knock <- tf_genes[tf_genes %in% rownames(counts)]

if (length(genes_to_knock) >= 2) {
  cat(sprintf("Running knockdowns for: %s\n\n", paste(genes_to_knock, collapse = ", ")))

  results_multi <- run_multiple_knockdowns(
    countMatrix = counts,
    gene_list = genes_to_knock,
    qc = TRUE,
    qc_minLSize = 200,
    nc_nNet = 5,
    nc_nCells = 200,
    verbose = TRUE
  )

  # Compare knockdowns
  cat("\nComparing knockdown results...\n")
  comparison <- compare_knockdowns(results_multi, method = "correlation")

  cat("\nCorrelation matrix of Z-scores:\n")
  print(round(comparison, 3))

  # Visualize comparison
  if (requireNamespace("pheatmap", quietly = TRUE)) {
    cat("\nGenerating comparison heatmap...\n")

    plot_comparison_heatmap(
      results_multi,
      n_genes = 50,
      save_path = "output_advanced/comparison_heatmap.png"
    )
  }

  cat("\n")
} else {
  cat("Insufficient genes available for multiple knockdown analysis\n\n")
}

# ================================================================================
# PART 4: Enrichment Analysis
# ================================================================================

cat("PART 4: Pathway Enrichment Analysis\n")
cat("--------------------------------------------------------------------------------\n")

if (exists("result_single") && requireNamespace("enrichR", quietly = TRUE)) {
  cat("Running enrichment analysis on POU5F1 knockdown...\n")

  enrichment <- run_enrichment_analysis(
    result_single,
    databases = c("KEGG_2019_Human", "GO_Biological_Process_2018"),
    p_cutoff = 0.05,
    fdr_threshold = 0.05,
    organism = "human"
  )

  # Print summary
  cat(sprintf("\nEnrichment Summary:\n"))
  cat(sprintf("  Significant genes: %d\n", enrichment$summary$n_sig_genes))
  cat(sprintf("  Enriched terms: %d\n", enrichment$summary$n_enriched_terms))

  # Print top KEGG pathways
  if (!is.null(enrichment$enrichr$KEGG_2019_Human) &&
      nrow(enrichment$enrichr$KEGG_2019_Human) > 0) {
    cat("\nTop KEGG Pathways:\n")
    top_kegg <- head(enrichment$enrichr$KEGG_2019_Human, 5)
    for (i in seq_len(nrow(top_kegg))) {
      cat(sprintf("  %d. %s (FDR = %.2e)\n",
                  i, top_kegg$Term[i], top_kegg$Adjusted.P.value[i]))
    }
  }

  # Plot enrichment
  if (requireNamespace("ggplot2", quietly = TRUE) &&
      !is.null(enrichment$enrichr$KEGG_2019_Human) &&
      nrow(enrichment$enrichr$KEGG_2019_Human) > 0) {
    cat("\nGenerating enrichment plot...\n")

    p <- plot_enrichment(
      enrichment,
      database = "KEGG_2019_Human",
      n_terms = 15,
      save_path = "output_advanced/enrichment_plot.png"
    )
  }

  cat("\n")
} else {
  cat("Skipping enrichment analysis (enrichR not available or no results)\n\n")
}

# ================================================================================
# PART 5: Visualization
# ================================================================================

cat("PART 5: Result Visualization\n")
cat("--------------------------------------------------------------------------------\n")

if (exists("result_single") && requireNamespace("ggplot2", quietly = TRUE)) {
  cat("Creating visualizations...\n")

  # Volcano plot
  cat("  - Volcano plot\n")
  plot_volcano(
    result_single,
    gKO = target_gene,
    p_cutoff = 0.05,
    label_top_n = 15,
    save_path = "output_advanced/volcano_plot.png"
  )

  # Top genes barplot
  cat("  - Top affected genes plot\n")
  plot_top_genes(
    result_single,
    n = 20,
    direction = "both",
    save_path = "output_advanced/top_genes.png"
  )

  cat("\n")
}

# ================================================================================
# PART 6: Generate Comprehensive Report
# ================================================================================

cat("PART 6: Generate Analysis Report\n")
cat("--------------------------------------------------------------------------------\n")

if (exists("result_single")) {
  report <- create_knockdown_report(
    result_single,
    gKO = target_gene,
    output_file = "output_advanced/comprehensive_report.txt",
    p_cutoff = 0.05
  )

  cat("\nReport preview (first 50 lines):\n")
  report_lines <- strsplit(report, "\n")[[1]]
  cat(paste(head(report_lines, 50), collapse = "\n"))
  cat("\n...\n\n")
}

# ================================================================================
# Summary
# ================================================================================

cat("================================================================================\n")
cat("                           Analysis Complete!\n")
cat("================================================================================\n")
cat("\nOutput files generated in output_advanced/:\n")

output_files <- c(
  "POU5F1_knockdown.rds",
  "POU5F1_diffRegulation.csv",
  "volcano_plot.png",
  "top_genes.png",
  "comparison_heatmap.png",
  "enrichment_plot.png",
  "comprehensive_report.txt"
)

for (f in output_files) {
  fpath <- file.path("output_advanced", f)
  if (file.exists(fpath)) {
    cat(sprintf("  ✓ %s\n", f))
  }
}

cat("\n")
cat("Next steps:\n")
cat("  1. Review the comprehensive report: output_advanced/comprehensive_report.txt\n")
cat("  2. Examine plots in output_advanced/\n")
cat("  3. Load full results: result <- readRDS('output_advanced/POU5F1_knockdown.rds')\n")
cat("  4. For real data, use ~1000+ cells and adjust nc_nNet/nc_nCells accordingly\n")
cat("\n")
