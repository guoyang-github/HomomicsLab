# Utility Functions for miloR
# ===========================
#
# Helper functions for data preparation and result processing

library(SingleCellExperiment)
library(miloR)

#' Create test data for miloR analysis
#'
#' @param n_cells Number of cells per sample (default: 500)
#' @param n_samples Number of samples (default: 6)
#' @param n_genes Number of genes (default: 1000)
#' @param n_groups Number of condition groups (default: 2)
#' @param da_effect Simulate DA effect (default: TRUE)
#' @param seed Random seed (default: 123)
#' @return SingleCellExperiment object
#' @export
create_milo_test_data <- function(n_cells = 500, n_samples = 6, n_genes = 1000,
                                  n_groups = 2, da_effect = TRUE, seed = 123) {
  set.seed(seed)

  # Create sample structure
  samples_per_group <- n_samples / n_groups
  sample_ids <- rep(paste0("Sample", 1:n_samples), each = n_cells)
  conditions <- rep(paste0("Group", 1:n_groups), each = n_cells * samples_per_group)
  replicates <- rep(rep(paste0("R", 1:samples_per_group)), each = n_cells, n_groups)

  # Generate expression matrix
  expr_matrix <- matrix(rpois(n_genes * n_cells * n_samples, lambda = 5),
                        nrow = n_genes)
  rownames(expr_matrix) <- paste0("Gene", 1:n_genes)
  colnames(expr_matrix) <- paste0("Cell", 1:(n_cells * n_samples))

  # Log normalize
  logcounts <- log2(expr_matrix + 1)

  # Add DA effect if requested (some cells more abundant in Group1 vs Group2)
  if (da_effect) {
    da_cells <- 1:floor(n_cells * 0.3)
    for (s in 1:(n_samples/2)) {
      cell_idx <- ((s-1) * n_cells + 1):(s * n_cells)
      expr_matrix[, cell_idx[da_cells]] <- expr_matrix[, cell_idx[da_cells]] * 2
    }
    logcounts <- log2(expr_matrix + 1)
  }

  # Compute PCA
  pca <- prcomp(t(logcounts), center = TRUE, scale. = TRUE)
  pca_dims <- pca$x[, 1:min(30, ncol(pca$x))]

  # Create cell metadata
  cell_metadata <- data.frame(
    sample_id = factor(sample_ids),
    condition = factor(conditions),
    replicate = factor(replicates),
    row.names = colnames(expr_matrix)
  )

  # Create SCE
  sce <- SingleCellExperiment(
    assays = list(counts = expr_matrix, logcounts = logcounts),
    colData = cell_metadata,
    reducedDims = SimpleList(PCA = pca_dims)
  )

  message("Created test data:")
  message("  Cells: ", ncol(sce))
  message("  Genes: ", nrow(sce))
  message("  Samples: ", n_samples)
  message("  Conditions: ", paste(levels(sce$condition), collapse = ", "))

  return(sce)
}

#' Prepare SingleCellExperiment for miloR from Seurat
#'
#' @param seurat_obj Seurat object
#' @param assay Assay to extract (default: "RNA")
#' @param slot Slot to extract (default: "data")
#' @param dimreducs Reduced dimensions to transfer (default: c("pca", "umap"))
#' @return SingleCellExperiment object
#' @export
seurat_to_sce <- function(seurat_obj, assay = "RNA", slot = "data",
                          dimreducs = c("pca", "umap")) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat is required for conversion")
  }

  # Extract counts and logcounts
  # Handle Seurat v4 (slot) vs v5 (layer) API difference
  if (utils::packageVersion("SeuratObject") >= package_version("5.0.0")) {
    counts <- Seurat::GetAssayData(seurat_obj, assay = assay, layer = "counts")
    logcounts <- Seurat::GetAssayData(seurat_obj, assay = assay, layer = slot)
  } else {
    counts <- Seurat::GetAssayData(seurat_obj, assay = assay, slot = "counts")
    logcounts <- Seurat::GetAssayData(seurat_obj, assay = assay, slot = slot)
  }

  # Extract metadata
  cell_metadata <- seurat_obj@meta.data

  # Create SCE
  sce <- SingleCellExperiment(
    assays = list(counts = counts, logcounts = logcounts),
    colData = cell_metadata
  )

  # Transfer reduced dimensions
  for (dr in dimreducs) {
    if (dr %in% names(seurat_obj@reductions)) {
      embedding <- Seurat::Embeddings(seurat_obj, reduction = dr)
      reducedDim(sce, toupper(dr)) <- embedding
    }
  }

  message("Converted Seurat to SCE:")
  message("  Cells: ", ncol(sce))
  message("  Genes: ", nrow(sce))
  message("  Reduced dims: ", paste(reducedDimNames(sce), collapse = ", "))

  return(sce)
}

#' Create design data frame for miloR
#'
#' @param sample_col Sample IDs
#' @param condition_col Condition values
#' @param covariates Additional covariates (data frame)
#' @return Design data frame with sample_id as rownames
#' @export
create_milo_design <- function(sample_col, condition_col, covariates = NULL) {
  design_df <- data.frame(
    sample_id = factor(sample_col),
    condition = factor(condition_col)
  )

  if (!is.null(covariates)) {
    design_df <- cbind(design_df, covariates)
  }

  rownames(design_df) <- design_df$sample_id

  return(design_df)
}

#' Get top DA neighborhoods
#'
#' @param da.res DA results from testNhoods
#' @param n_top Number of top neighborhoods (default: 10)
#' @param sort.by Column to sort by (default: "SpatialFDR")
#' @return Data frame with top DA neighborhoods
#' @export
get_top_da_nhoods <- function(da.res, n_top = 10, sort.by = "SpatialFDR") {
  if (!sort.by %in% colnames(da.res)) {
    stop(sprintf("Column '%s' not found in DA results", sort.by))
  }

  top_nhoods <- head(da.res[order(da.res[[sort.by]]), ], n_top)
  return(top_nhoods)
}

#' Get significant DA neighborhoods
#'
#' @param da.res DA results from testNhoods
#' @param alpha FDR threshold (default: 0.1)
#' @param min.logFC Minimum absolute logFC (default: 0)
#' @return Vector of significant neighborhood indices
#' @export
get_significant_nhoods <- function(da.res, alpha = 0.1, min.logFC = 0) {
  sig_idx <- which(da.res$SpatialFDR < alpha & abs(da.res$logFC) >= min.logFC)
  message(sprintf("Found %d significant DA neighborhoods (FDR < %.2f, |logFC| >= %.2f)",
                  length(sig_idx), alpha, min.logFC))
  return(sig_idx)
}

#' Summarize DA results
#'
#' @param da.res DA results from testNhoods
#' @param alpha FDR threshold (default: 0.1)
#' @return List with summary statistics
#' @export
summarize_milo_results <- function(da.res, alpha = 0.1) {
  n_total <- nrow(da.res)
  n_sig <- sum(da.res$SpatialFDR < alpha, na.rm = TRUE)
  n_up <- sum(da.res$SpatialFDR < alpha & da.res$logFC > 0, na.rm = TRUE)
  n_down <- sum(da.res$SpatialFDR < alpha & da.res$logFC < 0, na.rm = TRUE)

  summary <- list(
    n_total = n_total,
    n_significant = n_sig,
    n_upregulated = n_up,
    n_downregulated = n_down,
    prop_significant = n_sig / n_total,
    alpha_threshold = alpha
  )

  message("=== DA Results Summary ===")
  message(sprintf("Total neighborhoods: %d", n_total))
  message(sprintf("Significant (FDR < %.2f): %d (%.1f%%)",
                  alpha, n_sig, 100 * n_sig / n_total))
  message(sprintf("  Up-regulated: %d", n_up))
  message(sprintf("  Down-regulated: %d", n_down))

  return(summary)
}

#' Export DA results to CSV
#'
#' @param da.res DA results from testNhoods
#' @param file Output file path
#' @param significant_only Export only significant results (default: FALSE)
#' @param alpha FDR threshold for significance (default: 0.1)
#' @export
export_milo_results <- function(da.res, file, significant_only = FALSE,
                                alpha = 0.1) {
  if (significant_only) {
    output <- da.res[da.res$SpatialFDR < alpha, ]
    message(sprintf("Exporting %d significant results to %s", nrow(output), file))
  } else {
    output <- da.res
    message(sprintf("Exporting all %d results to %s", nrow(output), file))
  }

  write.csv(output, file, row.names = FALSE)
}

#' Filter neighborhoods by abundance
#'
#' @param x Milo object
#' @param min_cells Minimum cells per neighborhood (default: 10)
#' @param min_samples Minimum samples with cells (default: 2)
#' @return Milo object with filtered neighborhoods
#' @export
filter_milo_by_abundance <- function(x, min_cells = 10, min_samples = 2) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  counts <- nhoodCounts(x)
  cells_per_nhood <- rowSums(counts)
  samples_per_nhood <- rowSums(counts > 0)

  keep <- cells_per_nhood >= min_cells & samples_per_nhood >= min_samples
  n_keep <- sum(keep)

  message(sprintf("Keeping %d / %d neighborhoods (min %d cells, %d samples)",
                  n_keep, length(keep), min_cells, min_samples))

  # Subset neighborhoods
  nhoods(x) <- nhoods(x)[, keep]
  nhoodCounts(x) <- nhoodCounts(x)[keep, ]

  return(x)
}

#' Get neighborhood cell membership
#'
#' @param x Milo object
#' @param nhood_idx Neighborhood index
#' @return Vector of cell IDs in the neighborhood
#' @export
get_nhood_cells <- function(x, nhood_idx) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  nhoods_mat <- nhoods(x)
  cells <- rownames(nhoods_mat)[nhoods_mat[, nhood_idx] > 0]
  return(cells)
}

#' Get neighborhood expression summary
#'
#' @param x Milo object
#' @param nhood_idx Neighborhood index
#' @param assay Assay to use (default: "logcounts")
#' @return Vector of mean expression per gene
#' @export
get_nhood_expression <- function(x, nhood_idx, assay = "logcounts") {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  cells <- get_nhood_cells(x, nhood_idx)
  expr <- assay(x, assay)[, cells, drop = FALSE]
  mean_expr <- rowMeans(expr)

  return(mean_expr)
}

#' Compare two groups of samples
#'
#' @param da.res DA results
#' @param group1_samples Vector of sample IDs in group 1
#' @param group2_samples Vector of sample IDs in group 2
#' @param x Milo object (optional, for extracting counts)
#' @return Data frame with comparison statistics
#' @export
compare_milo_groups <- function(da.res, group1_samples, group2_samples, x = NULL) {
  message("Comparing groups:")
  message("  Group 1: ", paste(group1_samples, collapse = ", "))
  message("  Group 2: ", paste(group2_samples, collapse = ", "))

  # The logFC in DA results already represents this comparison
  # This function provides additional context
  comparison <- data.frame(
    Nhood = seq_len(nrow(da.res)),
    logFC = da.res$logFC,
    PValue = da.res$PValue,
    FDR = da.res$SpatialFDR,
    Significant = da.res$SpatialFDR < 0.1
  )

  return(comparison)
}

#' Check batch effects in DA results
#'
#' @param da.res DA results
#' @param batch_col Batch column from design.df
#' @return Diagnostic plot or statistics
#' @export
check_milo_batch_effects <- function(da.res, batch_col) {
  message("Checking for batch effects...")
  message("Batch column: ", batch_col)

  # This is a placeholder for batch effect diagnostics
  # In practice, you'd check for correlations between batch and DA signal

  return(TRUE)
}

#' Recommend k parameter based on dataset size
#'
#' @param n_cells Total number of cells
#' @return Recommended k value
#' @export
recommend_milo_k <- function(n_cells) {
  if (n_cells < 1000) {
    k <- 10
  } else if (n_cells < 10000) {
    k <- 30
  } else if (n_cells < 100000) {
    k <- 50
  } else {
    k <- 100
  }

  message(sprintf("Recommended k for %d cells: %d", n_cells, k))
  return(k)
}

#' Recommend prop parameter based on dataset size
#'
#' @param n_cells Total number of cells
#' @return Recommended prop value
#' @export
recommend_milo_prop <- function(n_cells) {
  if (n_cells < 1000) {
    prop <- 0.2
  } else if (n_cells < 10000) {
    prop <- 0.1
  } else if (n_cells < 100000) {
    prop <- 0.05
  } else {
    prop <- 0.01
  }

  message(sprintf("Recommended prop for %d cells: %.2f", n_cells, prop))
  return(prop)
}

#' Create miloR analysis report
#'
#' @param results Results list from run_milo_pipeline
#' @param output_file Output file path (default: "milo_report.txt")
#' @export
create_milo_report <- function(results, output_file = "milo_report.txt") {
  sink(output_file)

  cat("=== miloR Differential Abundance Analysis Report ===\n\n")

  cat("Date: ", format(Sys.time()), "\n\n")

  cat("Parameters:\n")
  cat(sprintf("  k: %d\n", results$params$k))
  cat(sprintf("  d: %d\n", results$params$d))
  cat(sprintf("  prop: %.2f\n", results$params$prop))
  cat(sprintf("  refined: %s\n\n", results$params$refined))

  cat("Design:\n")
  cat(sprintf("  Formula: %s\n", deparse(results$design)), "\n")

  cat("\nResults Summary:\n")
  summary <- summarize_milo_results(results$da_results)

  cat("\nTop 10 Significant Neighborhoods:\n")
  top <- get_top_da_nhoods(results$da_results, n_top = 10)
  print(top[, c("logFC", "PValue", "SpatialFDR")])

  sink()
  message("Report saved to ", output_file)
}
