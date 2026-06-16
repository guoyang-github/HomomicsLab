#' Utility Functions for scTenifoldKnk Analysis
#'
#' This module provides helper functions for data validation, result interpretation,
#' and output generation for scTenifoldKnk analyses.
#'
#' @author Based on scTenifoldKnk manuscript analysis
#' @references Osorio et al. (2020). Systematic characterization of gene knockdown
#'   perturbations in single-cell data. bioRxiv.

#' Validate Input Data for Knockdown Analysis
#'
#' Checks if the input data meets requirements for scTenifoldKnk analysis.
#'
#' @param countMatrix Gene expression matrix (genes x cells) or Seurat object.
#' @param target_gene Character. Gene to be knocked out (optional).
#' @param min_cells Integer. Minimum number of cells required (default: 300).
#' @param min_genes Integer. Minimum number of genes required (default: 1000).
#' @param min_nets Integer. Minimum number of networks (default: 3).
#' @param max_cells_per_net Integer. Maximum cells per network (default: 500).
#'
#' @return List containing:
#'   \item{valid}{Logical indicating if data is valid}
#'   \item{warnings}{Vector of warning messages}
#'   \item{errors}{Vector of error messages}
#'   \item{diagnostics}{List of diagnostic information}
#'
#' @examples
#' \dontrun{
#' validation <- validate_knk_data(counts, target_gene = "POU5F1")
#' if (!validation$valid) {
#'   stop(paste(validation$errors, collapse = "\n"))
#' }
#' }
#'
#' @export
validate_knk_data <- function(
    countMatrix,
    target_gene = NULL,
    min_cells = 300,
    min_genes = 1000,
    min_nets = 3,
    max_cells_per_net = 500
) {
  result <- list(
    valid = TRUE,
    warnings = character(),
    errors = character(),
    diagnostics = list()
  )

  # Extract matrix if Seurat object
  is_seurat <- FALSE
  if (inherits(countMatrix, "Seurat")) {
    is_seurat <- TRUE
    if (packageVersion("SeuratObject") >= "5.0.0") {
      countMatrix <- Seurat::GetAssayData(countMatrix, layer = "counts")
    } else {
      countMatrix <- Seurat::GetAssayData(countMatrix, slot = "counts")
    }
  }

  # Check dimensions
  n_genes <- nrow(countMatrix)
  n_cells <- ncol(countMatrix)

  result$diagnostics$n_genes <- n_genes
  result$diagnostics$n_cells <- n_cells
  result$diagnostics$is_seurat <- is_seurat
  result$diagnostics$is_sparse <- inherits(countMatrix, "sparseMatrix")

  # Validate minimum requirements
  if (n_genes < min_genes) {
    result$errors <- c(result$errors,
                       sprintf("Insufficient genes: %d (minimum %d)", n_genes, min_genes))
    result$valid <- FALSE
  }

  if (n_cells < min_cells) {
    result$errors <- c(result$errors,
                       sprintf("Insufficient cells: %d (minimum %d)", n_cells, min_cells))
    result$valid <- FALSE
  }

  # Check for row and column names
  if (is.null(rownames(countMatrix)) || any(rownames(countMatrix) == "")) {
    result$errors <- c(result$errors, "Genes must have row names")
    result$valid <- FALSE
  }

  if (is.null(colnames(countMatrix)) || any(colnames(countMatrix) == "")) {
    result$warnings <- c(result$warnings, "Cells should have column names")
  }

  # Check target gene presence
  if (!is.null(target_gene)) {
    if (!target_gene %in% rownames(countMatrix)) {
      result$errors <- c(result$errors,
                         sprintf("Target gene '%s' not found in count matrix", target_gene))
      result$valid <- FALSE
    } else {
      # Check expression level of target gene
      gene_expr <- countMatrix[target_gene, ]
      n_expr_cells <- sum(gene_expr > 0)
      result$diagnostics$target_gene_cells <- n_expr_cells
      result$diagnostics$target_gene_mean <- mean(gene_expr)

      if (n_expr_cells < 10) {
        result$warnings <- c(result$warnings,
                             sprintf("Target gene expressed in only %d cells", n_expr_cells))
      }
    }
  }

  # Check for duplicate gene names
  if (length(unique(rownames(countMatrix))) != n_genes) {
    dupes <- rownames(countMatrix)[duplicated(rownames(countMatrix))]
    result$warnings <- c(result$warnings,
                         sprintf("Duplicate gene names found: %s",
                                 paste(head(dupes, 5), collapse = ", ")))
  }

  # Check for all-zero genes/cells
  zero_genes <- sum(Matrix::rowSums(countMatrix) == 0)
  zero_cells <- sum(Matrix::colSums(countMatrix) == 0)

  if (zero_genes > 0) {
    result$warnings <- c(result$warnings,
                         sprintf("%d genes have zero expression", zero_genes))
  }

  if (zero_cells > 0) {
    result$warnings <- c(result$warnings,
                         sprintf("%d cells have zero expression", zero_cells))
  }

  # Check network construction feasibility
  max_possible_nets <- floor(n_cells / max_cells_per_net)
  result$diagnostics$max_possible_nets <- max_possible_nets

  if (max_possible_nets < min_nets) {
    result$warnings <- c(result$warnings,
                         sprintf("Can only construct %d networks (recommend >= %d)",
                                 max_possible_nets, min_nets))
  }

  return(result)
}

#' Print Validation Results
#'
#' Prints validation results in a human-readable format.
#'
#' @param validation List. Output from validate_knk_data().
#'
#' @export
print_validation_results <- function(validation) {
  cat("Data Validation Results\n")
  cat("=======================\n\n")

  cat("Diagnostics:\n")
  cat(sprintf("  Genes: %d\n", validation$diagnostics$n_genes))
  cat(sprintf("  Cells: %d\n", validation$diagnostics$n_cells))
  cat(sprintf("  Input type: %s\n",
              if (validation$diagnostics$is_seurat) "Seurat" else "Matrix"))

  if (!is.null(validation$diagnostics$target_gene_cells)) {
    cat(sprintf("  Target gene expressed in: %d cells\n",
                validation$diagnostics$target_gene_cells))
  }

  cat("\n")

  if (validation$valid && length(validation$warnings) == 0) {
    cat("✓ All checks passed!\n")
  } else {
    if (length(validation$errors) > 0) {
      cat("Errors:\n")
      for (err in validation$errors) {
        cat(sprintf("  ✗ %s\n", err))
      }
      cat("\n")
    }

    if (length(validation$warnings) > 0) {
      cat("Warnings:\n")
      for (warn in validation$warnings) {
        cat(sprintf("  ⚠ %s\n", warn))
      }
    }
  }
}

#' Summarize Knockdown Results
#'
#' Generates a comprehensive summary of scTenifoldKnk analysis results.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param p_cutoff Numeric. P-value cutoff for significance (default: 0.05).
#'
#' @return List containing summary statistics and data frames.
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#' summary <- summarize_knockdown_results(result)
#' print(summary$statistics)
#' }
#'
#' @export
summarize_knockdown_results <- function(result, p_cutoff = 0.05) {
  dr <- result$diffRegulation

  # Calculate summary statistics
  stats <- list(
    n_genes_analyzed = nrow(dr),
    n_significant = sum(dr$p.adj < p_cutoff, na.rm = TRUE),
    n_upregulated = sum(dr$p.adj < p_cutoff & dr$Z > 0, na.rm = TRUE),
    n_downregulated = sum(dr$p.adj < p_cutoff & dr$Z < 0, na.rm = TRUE),
    mean_z_score = mean(dr$Z, na.rm = TRUE),
    sd_z_score = sd(dr$Z, na.rm = TRUE),
    max_z_score = max(abs(dr$Z), na.rm = TRUE),
    p_cutoff = p_cutoff
  )

  # Top affected genes
  top_up <- head(dr[dr$Z > 0, ][order(-dr$Z[dr$Z > 0]), ], 10)
  top_down <- head(dr[dr$Z < 0, ][order(dr$Z[dr$Z < 0]), ], 10)

  # Most significant genes
  top_sig <- head(dr[order(dr$p.adj), ], 20)

  return(list(
    statistics = stats,
    top_upregulated = top_up,
    top_downregulated = top_down,
    most_significant = top_sig,
    all_results = dr
  ))
}

#' Get Significant Genes
#'
#' Extracts the list of significantly affected genes from knockdown results.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param p_cutoff Numeric. Adjusted p-value cutoff (default: 0.05).
#' @param direction Character. Filter by direction: "up", "down", or "both" (default: "both").
#'
#' @return Character vector of gene symbols.
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#' sig_genes <- get_significant_genes(result, p_cutoff = 0.01)
#' up_genes <- get_significant_genes(result, direction = "up")
#' }
#'
#' @export
get_significant_genes <- function(
    result,
    p_cutoff = 0.05,
    direction = "both"
) {
  dr <- result$diffRegulation

  # Filter by p-value
  sig_idx <- dr$p.adj < p_cutoff

  # Filter by direction
  if (direction == "up") {
    sig_idx <- sig_idx & dr$Z > 0
  } else if (direction == "down") {
    sig_idx <- sig_idx & dr$Z < 0
  }

  return(dr$gene[sig_idx])
}

#' Get Top Affected Genes
#'
#' Returns the top N most affected genes by significance or magnitude.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param n Integer. Number of genes to return (default: 20).
#' @param by Character. Sort by "significance" or "magnitude" (default: "significance").
#' @param direction Character. "up", "down", or "both" (default: "both").
#'
#' @return Data frame with top genes and their statistics.
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#' top <- get_top_affected_genes(result, n = 10, direction = "up")
#' }
#'
#' @export
get_top_affected_genes <- function(
    result,
    n = 20,
    by = "significance",
    direction = "both"
) {
  dr <- result$diffRegulation

  # Filter by direction
  if (direction == "up") {
    dr <- dr[dr$Z > 0, ]
  } else if (direction == "down") {
    dr <- dr[dr$Z < 0, ]
  }

  # Sort
  if (by == "significance") {
    dr <- dr[order(dr$p.adj), ]
  } else if (by == "magnitude") {
    dr <- dr[order(-abs(dr$Z)), ]
  }

  # Return top n
  if (nrow(dr) > n) {
    dr <- dr[seq_len(n), ]
  }

  return(dr)
}

#' Export Knockdown Results
#'
#' Exports scTenifoldKnk results to files.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param output_dir Character. Directory to save files (created if needed).
#' @param prefix Character. Prefix for output files (default: "knockdown").
#' @param gKO Character. Gene that was knocked out (for naming).
#' @param export_networks Logical. Whether to export network matrices (default: TRUE).
#' @param export_genelist Logical. Whether to export gene lists (default: TRUE).
#' @param export_tables Logical. Whether to export results tables (default: TRUE).
#'
#' @return Invisible NULL.
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#' export_knockdown_results(result, output_dir = "results", gKO = "POU5F1")
#' }
#'
#' @export
export_knockdown_results <- function(
    result,
    output_dir,
    prefix = "knockdown",
    gKO = NULL,
    export_networks = TRUE,
    export_genelist = TRUE,
    export_tables = TRUE
) {
  # Create output directory
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Determine file prefix
  if (!is.null(gKO)) {
    file_prefix <- file.path(output_dir, paste0(gKO, "_", prefix))
  } else {
    file_prefix <- file.path(output_dir, prefix)
  }

  # Export networks
  if (export_networks) {
    # Save as RData
    WT <- result$tensorNetworks$WT
    KO <- result$tensorNetworks$KO
    save(WT, KO, file = paste0(file_prefix, "_networks.RData"))

    # Export as MatrixMarket if possible
    if (requireNamespace("Matrix", quietly = TRUE)) {
      Matrix::writeMM(WT, paste0(file_prefix, "_WT.mtx"))
      Matrix::writeMM(KO, paste0(file_prefix, "_KO.mtx"))
    }

    message("Networks exported")
  }

  # Export results table
  if (export_tables) {
    write.csv(
      result$diffRegulation,
      paste0(file_prefix, "_diffRegulation.csv"),
      row.names = FALSE
    )

    # Export manifold alignment
    write.csv(
      result$manifoldAlignment,
      paste0(file_prefix, "_manifoldAlignment.csv")
    )

    message("Tables exported")
  }

  # Export gene lists
  if (export_genelist) {
    sig_genes <- result$diffRegulation$gene[result$diffRegulation$p.adj < 0.05]

    if (length(sig_genes) > 0) {
      writeLines(sig_genes, paste0(file_prefix, "_significant_genes.txt"))
    }

    # Top 100 genes
    top_100 <- head(result$diffRegulation$gene[order(result$diffRegulation$p.adj)], 100)
    writeLines(top_100, paste0(file_prefix, "_top100_genes.txt"))

    message("Gene lists exported")
  }

  # Save complete result object
  saveRDS(result, paste0(file_prefix, "_complete.rds"))

  message(sprintf("All results exported to: %s", output_dir))
  invisible(NULL)
}

#' Create Knockdown Analysis Report
#'
#' Generates a text report summarizing the knockdown analysis.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param gKO Character. Gene that was knocked out.
#' @param output_file Character. Path to save report (default: NULL).
#' @param p_cutoff Numeric. P-value cutoff for significance (default: 0.05).
#'
#' @return Character string containing the report (invisibly if output_file provided).
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#' report <- create_knockdown_report(result, gKO = "POU5F1", output_file = "report.txt")
#' }
#'
#' @export
create_knockdown_report <- function(
    result,
    gKO,
    output_file = NULL,
    p_cutoff = 0.05
) {
  # Generate summary
  summary <- summarize_knockdown_results(result, p_cutoff)
  stats <- summary$statistics

  # Build report
  lines <- character()

  lines <- c(lines, "================================================================================")
  lines <- c(lines, "                  scTenifoldKnk Knockdown Analysis Report")
  lines <- c(lines, "================================================================================")
  lines <- c(lines, "")
  lines <- c(lines, sprintf("Target Gene: %s", gKO))
  lines <- c(lines, sprintf("Analysis Date: %s", Sys.time()))
  lines <- c(lines, "")

  lines <- c(lines, "--------------------------------------------------------------------------------")
  lines <- c(lines, "SUMMARY STATISTICS")
  lines <- c(lines, "--------------------------------------------------------------------------------")
  lines <- c(lines, sprintf("Total genes analyzed: %d", stats$n_genes_analyzed))
  lines <- c(lines, sprintf("Significantly affected genes (FDR < %.3f): %d", p_cutoff, stats$n_significant))
  lines <- c(lines, sprintf("  - Upregulated: %d", stats$n_upregulated))
  lines <- c(lines, sprintf("  - Downregulated: %d", stats$n_downregulated))
  lines <- c(lines, sprintf("Mean Z-score: %.3f", stats$mean_z_score))
  lines <- c(lines, sprintf("Max |Z-score|: %.3f", stats$max_z_score))
  lines <- c(lines, "")

  lines <- c(lines, "--------------------------------------------------------------------------------")
  lines <- c(lines, "TOP 10 UPREGULATED GENES")
  lines <- c(lines, "--------------------------------------------------------------------------------")
  if (nrow(summary$top_upregulated) > 0) {
    for (i in seq_len(min(10, nrow(summary$top_upregulated)))) {
      gene <- summary$top_upregulated$gene[i]
      z <- summary$top_upregulated$Z[i]
      p <- summary$top_upregulated$p.adj[i]
      lines <- c(lines, sprintf("%2d. %-15s Z = %7.3f  FDR = %.2e", i, gene, z, p))
    }
  } else {
    lines <- c(lines, "No significantly upregulated genes found.")
  }
  lines <- c(lines, "")

  lines <- c(lines, "--------------------------------------------------------------------------------")
  lines <- c(lines, "TOP 10 DOWNREGULATED GENES")
  lines <- c(lines, "--------------------------------------------------------------------------------")
  if (nrow(summary$top_downregulated) > 0) {
    for (i in seq_len(min(10, nrow(summary$top_downregulated)))) {
      gene <- summary$top_downregulated$gene[i]
      z <- summary$top_downregulated$Z[i]
      p <- summary$top_downregulated$p.adj[i]
      lines <- c(lines, sprintf("%2d. %-15s Z = %7.3f  FDR = %.2e", i, gene, z, p))
    }
  } else {
    lines <- c(lines, "No significantly downregulated genes found.")
  }
  lines <- c(lines, "")

  lines <- c(lines, "--------------------------------------------------------------------------------")
  lines <- c(lines, "MOST SIGNIFICANT GENES (by FDR)")
  lines <- c(lines, "--------------------------------------------------------------------------------")
  for (i in seq_len(min(20, nrow(summary$most_significant)))) {
    gene <- summary$most_significant$gene[i]
    z <- summary$most_significant$Z[i]
    p <- summary$most_significant$p.adj[i]
    dir <- ifelse(z > 0, "UP", "DOWN")
    lines <- c(lines, sprintf("%2d. %-15s Z = %7.3f  FDR = %.2e  [%s]", i, gene, z, p, dir))
  }
  lines <- c(lines, "")

  lines <- c(lines, "================================================================================")
  lines <- c(lines, "                              END OF REPORT")
  lines <- c(lines, "================================================================================")

  report <- paste(lines, collapse = "\n")

  # Save or return
  if (!is.null(output_file)) {
    writeLines(report, output_file)
    message(sprintf("Report saved to: %s", output_file))
    invisible(report)
  } else {
    return(report)
  }
}

#' Compare Predicted with Experimental Data
#'
#' Compares scTenifoldKnk predictions with experimental perturbation data.
#'
#' @param predicted List. Output from scTenifoldKnk analysis.
#' @param experimental Data frame with experimental results.
#'   Should have columns: gene, logFC, pvalue (or similar).
#' @param method Character. Comparison method: "correlation" or "overlap" (default: "correlation").
#'
#' @return List containing comparison statistics and merged data.
#'
#' @examples
#' \dontrun{
#' predicted <- scTenifoldKnk(counts, gKO = "TREM2")
#' exp_data <- read.csv("experimental_de.csv")
#' comparison <- compare_with_experiment(predicted, exp_data)
#' }
#'
#' @export
compare_with_experiment <- function(
    predicted,
    experimental,
    method = "correlation"
) {
  # Extract predicted values
  pred_df <- predicted$diffRegulation
  pred_df$gene_upper <- toupper(pred_df$gene)

  # Process experimental data
  exp_df <- experimental
  exp_df$gene_upper <- toupper(exp_df$gene)

  # Merge data
  merged <- merge(
    pred_df[, c("gene", "gene_upper", "Z", "FC", "p.adj")],
    exp_df[, c("gene_upper", "logFC", "pvalue")],
    by = "gene_upper",
    all = FALSE
  )

  if (nrow(merged) == 0) {
    stop("No common genes found between predicted and experimental data")
  }

  # Calculate correlation
  cor_result <- cor.test(
    merged$Z,
    merged$logFC,
    method = "spearman",
    use = "pairwise.complete.obs"
  )

  # Calculate overlap of significant genes
  pred_sig <- toupper(pred_df$gene[pred_df$p.adj < 0.05])
  exp_sig <- toupper(exp_df$gene_upper[exp_df$pvalue < 0.05])

  overlap <- length(intersect(pred_sig, exp_sig))
  jaccard <- overlap / length(union(pred_sig, exp_sig))

  # Hypergeometric test
  phyper_result <- phyper(
    q = overlap - 1,
    m = length(exp_sig),
    n = length(unique(c(pred_df$gene_upper, exp_df$gene_upper))) - length(exp_sig),
    k = length(pred_sig),
    lower.tail = FALSE
  )

  return(list(
    correlation = list(
      rho = cor_result$estimate,
      p.value = cor_result$p.value
    ),
    overlap = list(
      predicted_sig = length(pred_sig),
      experimental_sig = length(exp_sig),
      overlap = overlap,
      jaccard = jaccard,
      phyper_pvalue = phyper_result
    ),
    data = data.frame(
      gene = merged$gene,
      predicted = merged$Z,
      experimental = merged$logFC
    )
  ))
}
