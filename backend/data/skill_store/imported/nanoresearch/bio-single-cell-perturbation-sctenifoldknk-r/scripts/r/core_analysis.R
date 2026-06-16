#' Core scTenifoldKnk Analysis Functions
#'
#' This module provides high-level functions to run in-silico gene knockdown
#' analysis using scTenifoldKnk, including single and multiple gene knockdowns
#' and complete analysis pipelines.
#'
#' @author Daniel Osorio <dcosorioh@tamu.edu>
#' @references Osorio et al. (2020). Systematic characterization of gene knockdown
#'   perturbations in single-cell data. bioRxiv.

#' Run In-silico Knockdown Analysis
#'
#' Performs virtual knockout experiment on single-cell gene regulatory networks.
#' Constructs WT network, simulates KO by zeroing target gene edges, aligns
#' networks via manifold learning, and identifies differentially regulated genes.
#'
#' @param countMatrix Gene expression matrix with genes as rows and cells as columns.
#'   Can be a matrix, Matrix, or Seurat object.
#' @param gKO Character string. Gene symbol to knock out. Must exist in rownames
#'   of countMatrix.
#' @param qc Logical. Whether to apply quality control (default: TRUE).
#' @param qc_mtThreshold Numeric. Maximum mitochondrial ratio (0-1, default: 0.1).
#' @param qc_minLSize Integer. Minimum library size per cell (default: 1000).
#' @param qc_minCells Integer. Minimum cells per gene to retain (default: 25).
#' @param nc_nNet Integer. Number of networks in ensemble (default: 10).
#' @param nc_nCells Integer. Cells to subsample per network (default: 500).
#' @param nc_nComp Integer. PCA components for network construction (default: 3).
#' @param nc_symmetric Logical. Whether to return symmetric networks (default: FALSE).
#' @param nc_scaleScores Logical. Whether to normalize edge weights (default: TRUE).
#' @param nc_lambda Numeric. Directionality strength (0-1, default: 0).
#' @param nc_q Numeric. Quantile threshold for edges (0-1, default: 0.9).
#' @param td_K Integer. CP tensor decomposition rank (default: 3).
#' @param td_maxIter Integer. Maximum tensor decomposition iterations (default: 1000).
#' @param td_maxError Numeric. Relative Frobenius error tolerance (default: 1e-5).
#' @param td_nDecimal Integer. Decimal places for tensor values (default: 3).
#' @param ma_nDim Integer. Manifold alignment dimensions (default: 2).
#' @param nCores Integer. Number of parallel cores (default: detectCores()).
#' @param verbose Logical. Whether to print progress messages (default: TRUE).
#'
#' @return List containing:
#'   \item{tensorNetworks}{List with WT and KO networks}
#'   \item{manifoldAlignment}{Data frame with aligned coordinates}
#'   \item{diffRegulation}{Data frame with differential regulation results}
#'
#' @examples
#' \dontrun{
#' # Basic usage
#' result <- run_knockdown_analysis(counts, gKO = "POU5F1")
#'
#' # Custom parameters
#' result <- run_knockdown_analysis(
#'   counts,
#'   gKO = "SOX2",
#'   nc_nNet = 20,
#'   nc_nCells = 1000,
#'   qc = FALSE
#' )
#' }
#'
#' @export
run_knockdown_analysis <- function(
    countMatrix,
    gKO,
    qc = TRUE,
    qc_mtThreshold = 0.1,
    qc_minLSize = 1000,
    qc_minCells = 25,
    nc_nNet = 10,
    nc_nCells = 500,
    nc_nComp = 3,
    nc_symmetric = FALSE,
    nc_scaleScores = TRUE,
    nc_lambda = 0,
    nc_q = 0.9,
    td_K = 3,
    td_maxIter = 1000,
    td_maxError = 1e-5,
    td_nDecimal = 3,
    ma_nDim = 2,
    nCores = parallel::detectCores(),
    verbose = TRUE
) {
  # Load required packages
  if (!requireNamespace("scTenifoldKnk", quietly = TRUE)) {
    stop("Package 'scTenifoldKnk' is required. Install with:\n",
         "  remotes::install_github('cailab-tamu/scTenifoldKnk')")
  }

  # Validate inputs
  if (is.null(gKO) || !is.character(gKO) || length(gKO) != 1) {
    stop("gKO must be a single gene symbol (character string)")
  }

  # Check if countMatrix is Seurat object
  if (inherits(countMatrix, "Seurat")) {
    if (verbose) message("Extracting count matrix from Seurat object...")
    if (packageVersion("SeuratObject") >= "5.0.0") {
      countMatrix <- Seurat::GetAssayData(countMatrix, layer = "counts")
    } else {
      countMatrix <- Seurat::GetAssayData(countMatrix, slot = "counts")
    }
  }

  # Validate gene presence
  if (!gKO %in% rownames(countMatrix)) {
    stop(sprintf("Gene '%s' is not present in the count matrix row names", gKO))
  }

  if (verbose) {
    message(sprintf("Running scTenifoldKnk for gene: %s", gKO))
    message(sprintf("Input matrix: %d genes x %d cells", nrow(countMatrix), ncol(countMatrix)))
  }

  # Run scTenifoldKnk
  result <- scTenifoldKnk::scTenifoldKnk(
    countMatrix = countMatrix,
    gKO = gKO,
    qc = qc,
    qc_mtThreshold = qc_mtThreshold,
    qc_minLSize = qc_minLSize,
    qc_minCells = qc_minCells,
    nc_nNet = nc_nNet,
    nc_nCells = nc_nCells,
    nc_nComp = nc_nComp,
    nc_symmetric = nc_symmetric,
    nc_scaleScores = nc_scaleScores,
    nc_lambda = nc_lambda,
    nc_q = nc_q,
    td_K = td_K,
    td_maxIter = td_maxIter,
    td_maxError = td_maxError,
    td_nDecimal = td_nDecimal,
    ma_nDim = ma_nDim,
    nCores = nCores
  )

  if (verbose) {
    n_sig <- sum(result$diffRegulation$p.adj < 0.05, na.rm = TRUE)
    message(sprintf("Analysis complete. %d significantly affected genes identified.", n_sig))
  }

  return(result)
}

#' Run Multiple Gene Knockdowns
#'
#' Performs in-silico knockdown analysis for multiple genes in batch.
#'
#' @param countMatrix Gene expression matrix (genes x cells).
#' @param gene_list Character vector of gene symbols to knock out.
#' @param ... Additional parameters passed to run_knockdown_analysis().
#'
#' @return Named list of knockdown results, with gene symbols as names.
#'
#' @examples
#' \dontrun{
#' genes <- c("POU5F1", "SOX2", "NANOG")
#' results <- run_multiple_knockdowns(counts, genes)
#'
#' # Access individual results
#' head(results[["POU5F1"]]$diffRegulation)
#' }
#'
#' @export
run_multiple_knockdowns <- function(countMatrix, gene_list, ...) {
  # Validate input
  if (!is.character(gene_list) || length(gene_list) == 0) {
    stop("gene_list must be a non-empty character vector")
  }

  # Check which genes are available
  available_genes <- gene_list[gene_list %in% rownames(countMatrix)]
  missing_genes <- setdiff(gene_list, rownames(countMatrix))

  if (length(missing_genes) > 0) {
    warning(sprintf("Genes not found in matrix and will be skipped: %s",
                    paste(missing_genes, collapse = ", ")))
  }

  if (length(available_genes) == 0) {
    stop("No genes from gene_list found in count matrix")
  }

  # Run knockdowns
  results <- list()

  for (i in seq_along(available_genes)) {
    gene <- available_genes[i]
    message(sprintf("\n[%d/%d] Running knockdown for: %s", i, length(available_genes), gene))

    tryCatch({
      results[[gene]] <- run_knockdown_analysis(
        countMatrix = countMatrix,
        gKO = gene,
        ...
      )
    }, error = function(e) {
      warning(sprintf("Error running knockdown for %s: %s", gene, conditionMessage(e)))
      results[[gene]] <- NULL
    })
  }

  # Remove NULL results
  results <- results[!sapply(results, is.null)]

  message(sprintf("\nCompleted %d/%d knockdown analyses", length(results), length(available_genes)))

  return(results)
}

#' Run Complete Knockdown Analysis Pipeline
#'
#' Runs the complete scTenifoldKnk analysis pipeline including optional
#' enrichment analysis and visualization.
#'
#' @param countMatrix Gene expression matrix (genes x cells).
#' @param gKO Gene symbol to knock out.
#' @param output_dir Directory to save results (default: NULL).
#' @param run_enrichment Logical. Whether to run enrichment analysis (default: FALSE).
#' @param create_plots Logical. Whether to create plots (default: TRUE).
#' @param ... Additional parameters passed to run_knockdown_analysis().
#'
#' @return Knockdown result list with additional summary information.
#'
#' @examples
#' \dontrun{
#' result <- run_complete_knockdown_analysis(
#'   counts,
#'   gKO = "POU5F1",
#'   output_dir = "results",
#'   run_enrichment = TRUE
#' )
#' }
#'
#' @export
run_complete_knockdown_analysis <- function(
    countMatrix,
    gKO,
    output_dir = NULL,
    run_enrichment = FALSE,
    create_plots = TRUE,
    ...
) {
  # Run main analysis
  result <- run_knockdown_analysis(countMatrix, gKO, ...)

  # Add summary statistics
  dr <- result$diffRegulation
  result$summary <- list(
    target_gene = gKO,
    n_genes_analyzed = nrow(dr),
    n_significant = sum(dr$p.adj < 0.05, na.rm = TRUE),
    n_upregulated = sum(dr$p.adj < 0.05 & dr$Z > 0, na.rm = TRUE),
    n_downregulated = sum(dr$p.adj < 0.05 & dr$Z < 0, na.rm = TRUE),
    top_affected = head(dr$gene[order(dr$p.adj)], 10)
  )

  # Save results if output directory provided
  if (!is.null(output_dir)) {
    if (!dir.exists(output_dir)) {
      dir.create(output_dir, recursive = TRUE)
    }

    # Save main result
    saveRDS(result, file.path(output_dir, sprintf("%s_knockdown.rds", gKO)))

    # Export differential regulation table
    write.csv(
      result$diffRegulation,
      file.path(output_dir, sprintf("%s_diffRegulation.csv", gKO)),
      row.names = FALSE
    )

    message(sprintf("Results saved to: %s", output_dir))
  }

  # Run enrichment if requested
  if (run_enrichment) {
    if (requireNamespace("enrichR", quietly = TRUE)) {
      message("Running enrichment analysis...")
      result$enrichment <- run_enrichment_analysis(result)
    } else {
      warning("Package 'enrichR' not available. Skipping enrichment analysis.")
    }
  }

  # Create plots if requested
  if (create_plots && !is.null(output_dir)) {
    if (requireNamespace("ggplot2", quietly = TRUE)) {
      message("Creating plots...")

      # Volcano plot
      p <- plot_volcano(result, gKO = gKO)
      ggplot2::ggsave(
        file.path(output_dir, sprintf("%s_volcano.png", gKO)),
        p, width = 10, height = 8
      )
    }
  }

  return(result)
}

#' Compare Knockdown Results
#'
#' Compares the effects of different gene knockdowns on the same dataset.
#'
#' @param results_list Named list of knockdown results from run_multiple_knockdowns().
#' @param method Comparison method: "correlation" or "overlap" (default: "correlation").
#'
#' @return Comparison matrix or overlap statistics.
#'
#' @examples
#' \dontrun{
#' results <- run_multiple_knockdowns(counts, c("POU5F1", "SOX2", "NANOG"))
#' comparison <- compare_knockdowns(results)
#' }
#'
#' @export
compare_knockdowns <- function(results_list, method = "correlation") {
  if (!all(sapply(results_list, function(x) !is.null(x$diffRegulation)))) {
    stop("All results must contain diffRegulation data frame")
  }

  genes <- results_list[[1]]$diffRegulation$gene

  if (method == "correlation") {
    # Extract Z-scores for comparison
    z_scores <- sapply(results_list, function(res) {
      dr <- res$diffRegulation
      z <- dr$Z
      names(z) <- dr$gene
      return(z[genes])
    })

    # Compute correlation matrix
    cor_matrix <- cor(z_scores, use = "pairwise.complete.obs", method = "spearman")
    return(cor_matrix)

  } else if (method == "overlap") {
    # Compute overlap of significant genes
    sig_genes <- lapply(results_list, function(res) {
      dr <- res$diffRegulation
      dr$gene[dr$p.adj < 0.05]
    })

    n <- length(sig_genes)
    overlap_matrix <- matrix(0, n, n)
    rownames(overlap_matrix) <- colnames(overlap_matrix) <- names(results_list)

    for (i in seq_len(n)) {
      for (j in seq_len(n)) {
        if (i == j) {
          overlap_matrix[i, j] <- 1
        } else {
          intersect_size <- length(intersect(sig_genes[[i]], sig_genes[[j]]))
          union_size <- length(union(sig_genes[[i]], sig_genes[[j]]))
          overlap_matrix[i, j] <- intersect_size / union_size
        }
      }
    }

    return(overlap_matrix)
  } else {
    stop("method must be 'correlation' or 'overlap'")
  }
}
