# scDblFinder Core Analysis Functions
# ====================================
#
# Main analysis functions for single-cell doublet detection using scDblFinder

#' Check scDblFinder dependencies
#'
#' Check if required packages are installed
#'
#' @return Logical indicating if all dependencies are available
#' @export
check_scdblfinder_dependencies <- function() {
  required <- c("scDblFinder", "SingleCellExperiment", "SummarizedExperiment",
                "ggplot2", "BiocParallel")
  missing <- required[!sapply(required, requireNamespace, quietly = TRUE)]

  if (length(missing) > 0) {
    warning(paste("Missing packages:", paste(missing, collapse = ", ")))
    return(FALSE)
  }
  return(TRUE)
}

#' Validate scDblFinder input
#'
#' Validate input data before running scDblFinder
#'
#' @param sce SingleCellExperiment object or count matrix
#' @return List with validation results
#' @export
validate_scdblfinder_input <- function(sce) {
  errors <- character()
  warnings <- character()
  stats <- list()

  # Check if SingleCellExperiment
  if (!inherits(sce, "SingleCellExperiment") && !inherits(sce, "SummarizedExperiment")) {
    if (!is.matrix(sce) && !inherits(sce, "dgCMatrix")) {
      errors <- c(errors, "Input must be SingleCellExperiment, SummarizedExperiment, or count matrix")
    } else {
      # It's a matrix
      stats$n_cells <- ncol(sce)
      stats$n_genes <- nrow(sce)

      if (is.null(rownames(sce))) {
        warnings <- c(warnings, "Count matrix has no gene names (rownames)")
      }
      if (is.null(colnames(sce))) {
        warnings <- c(warnings, "Count matrix has no cell names (colnames)")
      }
    }
  } else {
    # It's an SCE/SE object
    if (!"counts" %in% names(SummarizedExperiment::assays(sce))) {
      errors <- c(errors, "No 'counts' assay found in object")
    } else {
      counts <- SummarizedExperiment::assay(sce, "counts")
      stats$n_cells <- ncol(counts)
      stats$n_genes <- nrow(counts)
    }
  }

  # Check cell number
  if (!is.null(stats$n_cells)) {
    if (stats$n_cells < 50) {
      errors <- c(errors, paste("Too few cells:", stats$n_cells, "- need at least 50"))
    } else if (stats$n_cells < 200) {
      warnings <- c(warnings, "Low cell count may affect accuracy - recommend at least 200 cells")
    }

    if (stats$n_cells > 50000) {
      warnings <- c(warnings, "Large dataset - consider using BPPARAM for parallel processing")
    }
  }

  list(
    valid = length(errors) == 0,
    errors = errors,
    warnings = warnings,
    stats = stats
  )
}

#' Run scDblFinder analysis
#'
#' Run scDblFinder for doublet detection
#'
#' @param sce SingleCellExperiment object or count matrix
#' @param samples Vector of sample IDs or colData column name
#' @param clusters Cluster assignments (TRUE for auto, vector for manual, FALSE/NULL for random)
#' @param artificialDoublets Number of artificial doublets to create
#' @param nfeatures Number of top features to use (or character vector of feature names)
#' @param dims Number of PCA dimensions to use
#' @param k Number of nearest neighbors for KNN graph
#' @param dbr Expected doublet rate (NULL for auto)
#' @param dbr.sd Standard deviation of doublet rate uncertainty
#' @param dbr.per1k Doublet rate per 1000 cells (default 0.008 for 10X)
#' @param knownDoublets Logical vector of known doublets (or column name)
#' @param knownUse How to use known doublets: 'discard' or 'positive'
#' @param multiSampleMode Multi-sample handling: "split", "singleModel", "singleModelSplitThres", or "asOne"
#' @param removeUnidentifiable Remove unidentifiable artificial doublets
#' @param includePCs Principal components to include as predictors
#' @param propRandom Proportion of random artificial doublets (when clusters used)
#' @param propMarkers Proportion of features selected as markers
#' @param iter Number of scoring iterations
#' @param threshold Whether to threshold scores into binary calls
#' @param returnType Output type: "sce", "scores", "table", or "full"
#' @param verbose Print progress messages
#' @param BPPARAM BiocParallelParam for multithreading
#' @param validate Validate input before running
#' @return SingleCellExperiment with scDblFinder results (or other format based on returnType)
#' @export
run_scdblfinder <- function(
    sce,
    samples = NULL,
    clusters = NULL,
    artificialDoublets = NULL,
    nfeatures = 1000,
    dims = 20,
    k = NULL,
    dbr = NULL,
    dbr.sd = 0.015,
    dbr.per1k = 0.008,
    knownDoublets = NULL,
    knownUse = c("discard", "positive"),
    multiSampleMode = c("split", "singleModel", "singleModelSplitThres", "asOne"),
    removeUnidentifiable = TRUE,
    includePCs = 1:5,
    propRandom = 0.1,
    propMarkers = 0,
    iter = 1,
    threshold = TRUE,
    returnType = "sce",
    verbose = TRUE,
    BPPARAM = BiocParallel::SerialParam(),
    validate = TRUE
) {
  # Validate input
  if (validate) {
    validation <- validate_scdblfinder_input(sce)
    if (!validation$valid) {
      stop(paste("Validation errors:", paste(validation$errors, collapse = "\n")))
    }
    if (length(validation$warnings) > 0) {
      for (w in validation$warnings) {
        warning(w)
      }
    }
    if (verbose) {
      cat("Input validation passed.\n")
      if (!is.null(validation$stats$n_cells)) {
        cat(sprintf("Cells: %d, Genes: %d\n", validation$stats$n_cells, validation$stats$n_genes))
      }
    }
  }

  # Check dependencies
  if (!requireNamespace("scDblFinder", quietly = TRUE)) {
    stop("scDblFinder package required. Install with: BiocManager::install('scDblFinder')")
  }

  # Convert matrix to SingleCellExperiment if needed
  if (is.matrix(sce) || inherits(sce, "dgCMatrix")) {
    if (verbose) cat("Converting count matrix to SingleCellExperiment...\n")
    sce <- SingleCellExperiment::SingleCellExperiment(
      assays = list(counts = sce)
    )
  }

  # Match arguments
  knownUse <- match.arg(knownUse)
  multiSampleMode <- match.arg(multiSampleMode)

  # Run scDblFinder
  if (verbose) {
    cat("Running scDblFinder...\n")
    if (!is.null(samples)) {
      cat(sprintf("Multi-sample mode: %s\n", multiSampleMode))
    }
    cat(sprintf("Clusters: %s\n", ifelse(isTRUE(clusters), "auto", ifelse(isFALSE(clusters) || is.null(clusters), "random", "provided"))))
  }

  sce <- scDblFinder::scDblFinder(
    sce,
    samples = samples,
    clusters = clusters,
    artificialDoublets = artificialDoublets,
    nfeatures = nfeatures,
    dims = dims,
    k = k,
    dbr = dbr,
    dbr.sd = dbr.sd,
    dbr.per1k = dbr.per1k,
    knownDoublets = knownDoublets,
    knownUse = knownUse,
    multiSampleMode = multiSampleMode,
    removeUnidentifiable = removeUnidentifiable,
    includePCs = includePCs,
    propRandom = propRandom,
    propMarkers = propMarkers,
    iter = iter,
    threshold = threshold,
    returnType = returnType,
    verbose = verbose,
    BPPARAM = BPPARAM
  )

  if (verbose) cat("scDblFinder analysis complete.\n")
  return(sce)
}

#' Run scDblFinder with Seurat object
#'
#' Convenience function to run scDblFinder directly from Seurat object
#'
#' @param seurat_obj Seurat object
#' @param assay Assay to use (default: "RNA")
#' @param slot Slot to extract (default: "counts")
#' @param samples Sample information (column name or vector)
#' @param clusters Cluster assignments
#' @param dbr Expected doublet rate
#' @param dbr.sd Doublet rate uncertainty
#' @param nfeatures Number of features
#' @param dims Number of dimensions
#' @param k Number of neighbors
#' @param return_seurat Return Seurat object instead of SCE
#' @param ... Additional arguments passed to run_scdblfinder
#' @return Seurat object with scDblFinder results (if return_seurat=TRUE) or SCE
#' @export
run_scdblfinder_seurat <- function(
    seurat_obj,
    assay = "RNA",
    slot = "counts",
    samples = NULL,
    clusters = FALSE,
    dbr = NULL,
    dbr.sd = NULL,
    nfeatures = 1500,
    dims = 20,
    k = NULL,
    return_seurat = TRUE,
    verbose = TRUE,
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Convert to SingleCellExperiment
  # Note: Seurat v5's as.SingleCellExperiment does not accept 'assay' argument.
  # If the assay is v5 format, convert to v3 first to avoid errors.
  if (verbose) cat("Converting Seurat to SingleCellExperiment...\n")
  target_assay <- seurat_obj[[assay]]
  if (inherits(target_assay, "Assay5")) {
    if (verbose) cat("  Converting v5 assay to v3 format first...\n")
    target_assay <- as(target_assay, Class = "Assay")
    seurat_obj[[assay]] <- target_assay
  }
  sce <- Seurat::as.SingleCellExperiment(seurat_obj)

  # Handle samples parameter if it's a column name
  if (is.character(samples) && length(samples) == 1 && samples %in% colnames(seurat_obj[[]])) {
    samples <- seurat_obj[[samples]][, 1]
  }

  # Handle clusters parameter if it's a column name
  if (is.character(clusters) && length(clusters) == 1 && clusters %in% colnames(seurat_obj[[]])) {
    clusters <- seurat_obj[[clusters]][, 1]
  }

  # Run scDblFinder
  sce <- run_scdblfinder(
    sce = sce,
    samples = samples,
    clusters = clusters,
    dbr = dbr,
    dbr.sd = dbr.sd,
    nfeatures = nfeatures,
    dims = dims,
    k = k,
    returnType = "sce",
    ...
  )

  if (return_seurat) {
    # Add results back to Seurat
    seurat_obj <- add_scdblfinder_to_seurat(seurat_obj, sce)
    return(seurat_obj)
  } else {
    return(sce)
  }
}

#' Extract doublet scores from scDblFinder results
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @return Data frame with doublet scores and classifications
#' @export
extract_doublet_scores <- function(sce) {
  if (!inherits(sce, "SingleCellExperiment")) {
    stop("Input must be SingleCellExperiment")
  }

  cd <- SummarizedExperiment::colData(sce)

  # Check for scDblFinder columns
  scdbl_cols <- grep("^scDblFinder", colnames(cd), value = TRUE)

  if (length(scdbl_cols) == 0) {
    stop("No scDblFinder results found in object. Run scDblFinder first.")
  }

  # Extract relevant columns
  result <- as.data.frame(cd[, scdbl_cols, drop = FALSE])
  result$cell <- rownames(result)

  return(result)
}

#' Get doublet cells from scDblFinder results
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @return Vector of cell names classified as doublets
#' @export
get_doublet_cells <- function(sce) {
  if (!"scDblFinder.class" %in% colnames(SummarizedExperiment::colData(sce))) {
    stop("No scDblFinder classification found. Run scDblFinder first.")
  }

  cd <- SummarizedExperiment::colData(sce)
  doublet_cells <- rownames(cd)[cd$scDblFinder.class == "doublet"]

  return(doublet_cells)
}

#' Get singlet cells from scDblFinder results
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @return Vector of cell names classified as singlets
#' @export
get_singlet_cells <- function(sce) {
  if (!"scDblFinder.class" %in% colnames(SummarizedExperiment::colData(sce))) {
    stop("No scDblFinder classification found. Run scDblFinder first.")
  }

  cd <- SummarizedExperiment::colData(sce)
  singlet_cells <- rownames(cd)[cd$scDblFinder.class == "singlet"]

  return(singlet_cells)
}

#' Summarize scDblFinder results
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @return List with summary statistics
#' @export
summarize_scdblfinder_results <- function(sce) {
  cd <- SummarizedExperiment::colData(sce)

  if (!"scDblFinder.class" %in% colnames(cd)) {
    stop("No scDblFinder results found in object")
  }

  class_table <- table(cd$scDblFinder.class)
  n_doublets <- sum(cd$scDblFinder.class == "doublet")
  n_singlets <- sum(cd$scDblFinder.class == "singlet")

  summary <- list(
    n_cells = nrow(cd),
    n_doublets = n_doublets,
    n_singlets = n_singlets,
    doublet_rate = n_doublets / nrow(cd),
    class_table = class_table
  )

  # Include score statistics if available
  if ("scDblFinder.score" %in% colnames(cd)) {
    summary$mean_score <- mean(cd$scDblFinder.score, na.rm = TRUE)
    summary$median_score <- median(cd$scDblFinder.score, na.rm = TRUE)
    summary$score_range <- range(cd$scDblFinder.score, na.rm = TRUE)
  }

  # Include most likely origin if available
  if ("scDblFinder.mostLikelyOrigin" %in% colnames(cd)) {
    summary$origin_table <- table(cd$scDblFinder.mostLikelyOrigin)
  }

  # Include sample info if multi-sample
  if ("scDblFinder.sample" %in% colnames(cd)) {
    summary$doublets_by_sample <- table(cd$scDblFinder.sample, cd$scDblFinder.class)
  }

  return(summary)
}

#' Filter doublets from SingleCellExperiment
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param remove_doublets Whether to remove doublets (default: TRUE)
#' @param remove_unclassified Whether to remove unclassified cells (default: FALSE)
#' @return Filtered SingleCellExperiment
#' @export
filter_scdblfinder <- function(
    sce,
    remove_doublets = TRUE,
    remove_unclassified = FALSE
) {
  cd <- SummarizedExperiment::colData(sce)

  if (!"scDblFinder.class" %in% colnames(cd)) {
    stop("No scDblFinder classification found")
  }

  # Determine cells to keep
  keep <- rep(TRUE, nrow(cd))

  if (remove_doublets) {
    keep <- keep & cd$scDblFinder.class != "doublet"
  }

  if (remove_unclassified) {
    keep <- keep & !is.na(cd$scDblFinder.class)
  }

  cat(sprintf("Keeping %d of %d cells (%.1f%%)\n",
              sum(keep), length(keep), 100 * sum(keep) / length(keep)))

  sce_filtered <- sce[, keep]
  return(sce_filtered)
}

#' Export scDblFinder results
#'
#' Export doublet classifications and scores to files
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param output_dir Output directory
#' @param prefix File prefix
#' @export
export_scdblfinder_results <- function(
    sce,
    output_dir = "./scdblfinder_output",
    prefix = "sample"
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Extract results
  results <- extract_doublet_scores(sce)

  # Export classifications
  class_file <- file.path(output_dir, paste0(prefix, "_classifications.csv"))
  write.csv(results, class_file, row.names = FALSE)
  cat(sprintf("Exported: %s\n", class_file))

  # Export summary
  summary <- summarize_scdblfinder_results(sce)
  summary_file <- file.path(output_dir, paste0(prefix, "_summary.txt"))

  sink(summary_file)
  on.exit(sink(), add = TRUE)
  cat("scDblFinder Analysis Summary\n")
  cat("============================\n\n")
  cat(sprintf("Total cells: %d\n", summary$n_cells))
  cat(sprintf("Doublets: %d (%.1f%%)\n", summary$n_doublets, 100 * summary$doublet_rate))
  cat(sprintf("Singlets: %d (%.1f%%)\n", summary$n_singlets, 100 * summary$n_singlets / summary$n_cells))
  if (!is.null(summary$mean_score)) {
    cat(sprintf("\nMean doublet score: %.3f\n", summary$mean_score))
  }
  cat("\nClassification table:\n")
  print(summary$class_table)

  cat(sprintf("Exported: %s\n", summary_file))
}

#' Create scDblFinder report
#'
#' Generate a text summary report
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param output_file Output file path (optional)
#' @return Report text
#' @export
create_scdblfinder_report <- function(sce, output_file = NULL) {
  summary <- summarize_scdblfinder_results(sce)

  report <- sprintf("
scDblFinder Analysis Report
===========================
Date: %s

Cell Summary
------------
Total cells analyzed: %d
Doublets: %d (%.1f%%)
Singlets: %d (%.1f%%)

Score Statistics
----------------
Mean doublet score: %.3f
Median doublet score: %.3f
Score range: %.3f - %.3f

Classification
--------------
%s

Notes
-----
- Doublets are cells predicted to be formed by two or more cells
- scDblFinder uses gradient-boosted classification on artificial doublets
- Consider visualizing results on UMAP/t-SNE to assess spatial distribution
",
                    format(Sys.time(), "%Y-%m-%d %H:%M"),
                    summary$n_cells,
                    summary$n_doublets, 100 * summary$doublet_rate,
                    summary$n_singlets, 100 * summary$n_singlets / summary$n_cells,
                    ifelse(is.null(summary$mean_score), NA, summary$mean_score),
                    ifelse(is.null(summary$median_score), NA, summary$median_score),
                    ifelse(is.null(summary$score_range[1]), NA, summary$score_range[1]),
                    ifelse(is.null(summary$score_range[2]), NA, summary$score_range[2]),
                    paste(capture.output(print(summary$class_table)), collapse = "\n")
  )

  if (!is.null(output_file)) {
    writeLines(report, output_file)
  }

  return(report)
}

#' Add scDblFinder results to Seurat object
#'
#' @param seurat_obj Seurat object
#' @param sce SingleCellExperiment with scDblFinder results (or NULL to use colData)
#' @param prefix Prefix for metadata columns (default: "scDblFinder_")
#' @return Seurat object with added metadata
#' @export
add_scdblfinder_to_seurat <- function(seurat_obj, sce, prefix = "scDblFinder_") {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract colData
  cd <- SummarizedExperiment::colData(sce)

  # Find scDblFinder columns
  scdbl_cols <- grep("^scDblFinder", colnames(cd), value = TRUE)

  if (length(scdbl_cols) == 0) {
    warning("No scDblFinder columns found in object")
    return(seurat_obj)
  }

  # Add to Seurat metadata
  cell_names <- colnames(seurat_obj)

  for (col in scdbl_cols) {
    new_col_name <- paste0(prefix, sub("^scDblFinder\\.?", "", col))

    # Match cells
    matches <- match(cell_names, rownames(cd))

    if (is.numeric(cd[[col]])) {
      seurat_obj[[new_col_name]] <- cd[[col]][matches]
    } else {
      seurat_obj[[new_col_name]] <- as.character(cd[[col]][matches])
    }
  }

  cat(sprintf("Added %d scDblFinder columns to Seurat object\n", length(scdbl_cols)))

  return(seurat_obj)
}
