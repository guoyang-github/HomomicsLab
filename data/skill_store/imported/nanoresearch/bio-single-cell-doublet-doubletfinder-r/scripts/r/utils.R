# Utility Functions for DoubletFinder
# =====================================
#
# Helper functions for parameter estimation, validation, and result processing.

#' Calculate standard 10x Genomics doublet rate
#'
#' Based on 10x documentation: ~0.8% doublets per 1000 cells loaded
#'
#' @param n_loaded Number of cells loaded into device
#' @return Expected doublet rate (proportion)
#' @export
get_10x_doublet_rate <- function(n_loaded) {
  # 10x Genomics doublet rate: approximately 0.8% per 1000 cells
  rate <- (n_loaded / 1000) * 0.008
  return(rate)
}

#' Calculate expected doublets for various platforms
#'
#' @param n_cells Number of cells recovered
#' @param platform Platform name: "10x_v2", "10x_v3", "10x_v3_1", "10x_ht", "parse", "dropseq"
#' @return Expected number of doublets
#' @export
estimate_expected_doublets <- function(n_cells, platform = "10x_v3") {
  # Doublet rates based on manufacturer documentation and literature
  rates <- list(
    "10x_v2" = 0.008,      # ~0.8% per 1000 cells for 10x v2
    "10x_v3" = 0.008,      # ~0.8% per 1000 cells for 10x v3
    "10x_v3_1" = 0.004,    # ~0.4% per 1000 cells for 10x v3.1 (lower doublet rate)
    "10x_ht" = 0.016,      # ~1.6% per 1000 cells for high-throughput
    "parse" = 0.006,       # Parse Biosciences ~0.6% per 1000
    "dropseq" = 0.005,     # Drop-seq ~0.5% per 1000
    "smartseq" = 0.001     # Smart-seq2 very low doublet rate
  )

  if (!platform %in% names(rates)) {
    warning("Unknown platform '", platform, "'. Using 10x_v3 rate.")
    platform <- "10x_v3"
  }

  rate_per_1k <- rates[[platform]]
  n_doublets <- round(n_cells * (n_cells / 1000) * rate_per_1k)

  message("Platform: ", platform)
  message("Estimated doublet rate: ~", round(rate_per_1k * (n_cells/1000) * 100, 2), "%")
  message("Expected doublets: ", n_doublets)

  return(n_doublets)
}

#' Check if expected doublet rate is reasonable
#'
#' @param n_cells Number of cells
#' @param n_exp Expected doublets
#' @return Logical indicating if rate seems reasonable
#' @export
validate_expected_doublets <- function(n_cells, n_exp) {
  rate <- n_exp / n_cells

  if (rate < 0.005) {
    warning("Very low doublet rate (", round(rate*100, 2),
            "%). May miss real doublets.")
    return(FALSE)
  } else if (rate > 0.15) {
    warning("Very high doublet rate (", round(rate*100, 2),
            "%). May over-filter.")
    return(FALSE)
  }

  message("Expected doublet rate (", round(rate*100, 2), "%) seems reasonable")
  return(TRUE)
}

#' Get cell loading recommendation for 10x Genomics
#'
#' @param target_cells Target number of cells to recover
#' @return Recommended loading number
#' @export
get_loading_recommendation <- function(target_cells) {
  # 10x Genomics recovery rate is approximately 50-70%
  # Recommend loading 1.5-2x target
  recommended_loading <- round(target_cells * 1.6)

  message("Target cells: ", target_cells)
  message("Recommended loading: ", recommended_loading,
          " cells (assuming ~60% recovery)")

  return(recommended_loading)
}

#' Extract pANN column name from Seurat object
#'
#' @param seu Seurat object
#' @return Character vector of pANN column names
#' @export
get_pann_columns <- function(seu) {
  cols <- grep("^pANN_", colnames(seu@meta.data), value = TRUE)
  return(cols)
}

#' Extract DF classification column name
#'
#' @param seu Seurat object
#' @return Character vector of classification column names
#' @export
get_df_classification_columns <- function(seu) {
  cols <- grep("^DF.classifications", colnames(seu@meta.data), value = TRUE)
  return(cols)
}

#' Get parameters from DF classification column name
#'
#' @param col_name Column name (e.g., "DF.classifications_0.25_0.09_500")
#' @return List with pN, pK, nExp values
#' @export
parse_df_column_name <- function(col_name) {
  # Remove prefix
  params_str <- sub("DF.classifications_", "", col_name)
  params <- strsplit(params_str, "_")[[1]]

  if (length(params) != 3) {
    stop("Unexpected column name format: ", col_name)
  }

  pN <- suppressWarnings(as.numeric(params[1]))
  pK <- suppressWarnings(as.numeric(params[2]))
  nExp <- suppressWarnings(as.numeric(params[3]))

  if (any(is.na(c(pN, pK, nExp)))) {
    stop("Unexpected column name format: ", col_name)
  }

  return(list(
    pN = pN,
    pK = pK,
    nExp = nExp
  ))
}

#' Create summary table of doublet predictions by sample
#'
#' @param seu Seurat object
#' @param sample_col Sample identifier column
#' @return Data frame with summary statistics
#' @export
summarize_by_sample <- function(seu, sample_col = "sample") {
  if (!sample_col %in% colnames(seu@meta.data)) {
    stop("Sample column '", sample_col, "' not found")
  }

  if (!"doublet" %in% colnames(seu@meta.data)) {
    stop("No doublet predictions found")
  }

  samples <- unique(seu@meta.data[[sample_col]])

  summary <- lapply(samples, function(s) {
    cells <- seu@meta.data[[sample_col]] == s
    data.frame(
      sample = s,
      total_cells = sum(cells),
      n_doublets = sum(seu$doublet[cells] == "Doublet"),
      n_singlets = sum(seu$doublet[cells] == "Singlet"),
      doublet_rate = round(sum(seu$doublet[cells] == "Doublet") / sum(cells) * 100, 2)
    )
  })

  summary <- do.call(rbind, summary)
  return(summary)
}

#' Identify high-confidence doublets based on pANN threshold
#'
#' @param seu Seurat object
#' @param pann_threshold pANN threshold (default: 0.5)
#' @return Vector of cell IDs
#' @export
get_high_confidence_doublets <- function(seu, pann_threshold = 0.5) {
  pann_cols <- get_pann_columns(seu)
  if (length(pann_cols) == 0) {
    stop("No pANN scores found")
  }

  pann <- seu@meta.data[[pann_cols[1]]]
  high_conf <- colnames(seu)[pann >= pann_threshold & !is.na(pann)]

  message("High-confidence doublets (pANN >= ", pann_threshold, "): ",
          length(high_conf))

  return(high_conf)
}

#' Compare two DoubletFinder runs
#'
#' @param seu Seurat object with multiple DF runs
#' @return Data frame with comparison statistics
#' @export
compare_df_runs <- function(seu) {
  df_cols <- get_df_classification_columns(seu)

  if (length(df_cols) < 2) {
    stop("Need at least 2 DF classification columns for comparison")
  }

  # Create comparison matrix
  comparison <- data.frame(
    run1 = seu@meta.data[[df_cols[1]]],
    run2 = seu@meta.data[[df_cols[2]]]
  )

  # Agreement statistics
  agreement <- table(comparison$run1, comparison$run2)

  message("Agreement between runs:")
  print(agreement)

  percent_agree <- sum(diag(agreement)) / sum(agreement) * 100
  message("Percent agreement: ", round(percent_agree, 1), "%")

  return(as.data.frame(agreement))
}

#' Generate DoubletFinder report
#'
#' @param seu Seurat object
#' @param output_file Output file path (optional)
#' @return Report text
#' @export
generate_df_report <- function(seu, output_file = NULL) {
  lines <- c(
    "DoubletFinder Analysis Report",
    "============================",
    "",
    paste("Analysis Date:", Sys.time()),
    paste("Total Cells:", ncol(seu)),
    paste("Genes:", nrow(seu)),
    ""
  )

  # Doublet summary
  if ("doublet" %in% colnames(seu@meta.data)) {
    n_doublets <- sum(seu$doublet == "Doublet")
    n_singlets <- sum(seu$doublet == "Singlet")
    rate <- n_doublets / ncol(seu) * 100

    lines <- c(lines,
      "Doublet Detection Results:",
      paste("  Predicted Doublets:", n_doublets, "(", round(rate, 2), "%)"),
      paste("  Predicted Singlets:", n_singlets),
      ""
    )
  }

  # DF parameters
  df_cols <- get_df_classification_columns(seu)
  if (length(df_cols) > 0) {
    params <- parse_df_column_name(df_cols[1])
    lines <- c(lines,
      "Parameters Used:",
      paste("  pN:", params$pN),
      paste("  pK:", params$pK),
      paste("  nExp:", params$nExp),
      ""
    )
  }

  report_text <- paste(lines, collapse = "\n")

  if (!is.null(output_file)) {
    writeLines(report_text, output_file)
    message("Report saved to ", output_file)
  }

  cat(report_text)
  return(invisible(report_text))
}

#' Recommend PC range based on elbow plot
#'
#' @param seu Seurat object with PCA
#' @param variance_threshold Minimum cumulative variance (default: 0.9)
#' @return Recommended number of PCs
#' @export
recommend_pcs <- function(seu, variance_threshold = 0.9) {
  if (!"pca" %in% names(seu@reductions)) {
    stop("PCA not found in Seurat object")
  }

  # Get standard deviations
  stdev <- seu@reductions$pca@stdev
  variance <- stdev^2 / sum(stdev^2)
  cumvar <- cumsum(variance)

  # Find number of PCs for threshold
  n_pcs <- min(which(cumvar >= variance_threshold))

  message("Variance explained by first ", n_pcs, " PCs: ",
          round(cumvar[n_pcs] * 100, 1), "%")
  message("Recommended PCs: 1:", n_pcs)

  return(n_pcs)
}
