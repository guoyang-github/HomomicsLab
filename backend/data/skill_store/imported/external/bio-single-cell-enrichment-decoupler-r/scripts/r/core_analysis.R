# decoupleR Core Analysis Functions
# ==================================
#
# Main analysis functions for pathway and TF activity inference using decoupleR
# Reference: Badia-i-Mompel et al., Bioinformatics Advances 2022

#' Check decoupleR dependencies
#'
#' Check if required packages are installed
#'
#' @return Logical indicating if all dependencies are available
#' @export
check_decoupler_dependencies <- function() {
  required <- c("decoupleR", "Seurat", "dplyr", "tidyr", "ggplot2", "tibble", "ggrepel")
  missing <- required[!sapply(required, requireNamespace, quietly = TRUE)]

  if (length(missing) > 0) {
    warning(paste("Missing packages:", paste(missing, collapse = ", ")))
    return(FALSE)
  }
  return(TRUE)
}

#' Validate decoupleR input
#'
#' Validate input data before running decoupleR analysis
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @return List with validation results
#' @export
validate_decoupler_input <- function(mat, net) {
  errors <- character()
  warnings <- character()
  stats <- list()

  # Check matrix
  if (!is.matrix(mat) && !inherits(mat, "dgCMatrix") && !inherits(mat, "Matrix")) {
    errors <- c(errors, "mat must be a matrix or sparse Matrix")
  } else {
    stats$n_genes <- nrow(mat)
    stats$n_samples <- ncol(mat)

    if (is.null(rownames(mat))) {
      errors <- c(errors, "mat must have gene names as rownames")
    }

    if (any(is.na(mat))) {
      warnings <- c(warnings, "mat contains NA values")
    }

    if (any(is.infinite(mat))) {
      warnings <- c(warnings, "mat contains infinite values")
    }
  }

  # Check network
  if (!is.data.frame(net)) {
    errors <- c(errors, "net must be a data frame")
  } else {
    required_cols <- c("source", "target")
    missing_cols <- required_cols[!required_cols %in% colnames(net)]

    if (length(missing_cols) > 0) {
      errors <- c(errors, paste("net missing required columns:", paste(missing_cols, collapse = ", ")))
    }

    stats$n_sources <- length(unique(net$source))
    stats$n_interactions <- nrow(net)
  }

  # Check overlap
  if ((is.matrix(mat) || inherits(mat, "Matrix")) && is.data.frame(net)) {
    common_genes <- intersect(rownames(mat), net$target)
    stats$n_common_genes <- length(common_genes)
    stats$overlap_fraction <- length(common_genes) / length(unique(net$target))

    if (length(common_genes) == 0) {
      errors <- c(errors, "No common genes between mat and net targets")
    } else if (length(common_genes) < 10) {
      warnings <- c(warnings, paste("Low gene overlap:", length(common_genes), "genes"))
    } else if (stats$overlap_fraction < 0.5) {
      warnings <- c(warnings, sprintf("Gene overlap is only %.1f%%", stats$overlap_fraction * 100))
    }
  }

  list(
    valid = length(errors) == 0,
    errors = errors,
    warnings = warnings,
    stats = stats
  )
}

#' Get PROGENy pathway network
#'
#' Wrapper to get PROGENy pathway network from OmniPath/DecoupleR
#'
#' @param organism Organism: "human" or "mouse"
#' @param top Number of top genes per pathway (default: 500)
#' @return Network data frame with columns: source, target, weight, p_value
#' @export
get_progeny_network <- function(organism = "human", top = 500) {
  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required. Install with: BiocManager::install('decoupleR')")
  }

  net <- decoupleR::get_progeny(organism = organism, top = top)

  # Ensure weight column exists
  if (!"weight" %in% colnames(net)) {
    if ("logfc" %in% colnames(net)) {
      net$weight <- net$logfc
    } else {
      net$weight <- 1
    }
  }

  message(sprintf("Loaded PROGENy network: %d pathways, %d interactions",
                  length(unique(net$source)), nrow(net)))

  return(net)
}

#' Get DoRothEA TF network
#'
#' Wrapper to get DoRothEA transcription factor network
#'
#' @param organism Organism: "human", "mouse", or "rat"
#' @param levels Confidence levels (A=high, B=medium, C=low, D=very low)
#' @return Network data frame
#' @export
get_dorothea_network <- function(organism = "human", levels = c("A", "B", "C")) {
  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  net <- decoupleR::get_dorothea(organism = organism, levels = levels)

  message(sprintf("Loaded DoRothEA network (levels %s): %d TFs, %d interactions",
                  paste(levels, collapse = ""),
                  length(unique(net$source)), nrow(net)))

  return(net)
}

#' Get CollecTRI TF network
#'
#' Wrapper to get CollecTRI transcription factor network (expanded coverage)
#'
#' @param organism Organism: "human" or "mouse"
#' @return Network data frame
#' @export
get_collectri_network <- function(organism = "human") {
  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  net <- decoupleR::get_collectri(organism = organism)

  message(sprintf("Loaded CollecTRI network: %d TFs, %d interactions",
                  length(unique(net$source)), nrow(net)))

  return(net)
}

#' Get custom network from data frame
#'
#' Convert a user-provided data frame to decoupleR network format
#'
#' @param df Data frame with network information
#' @param source_col Column name for source (e.g., pathway/TF name)
#' @param target_col Column name for target (gene symbol)
#' @param weight_col Column name for weight (optional)
#' @param ... Additional columns to include
#' @return Standardized network data frame
#' @export
get_custom_network <- function(df, source_col = "source", target_col = "target",
                               weight_col = NULL, ...) {

  if (!source_col %in% colnames(df)) {
    stop(sprintf("Source column '%s' not found in data frame", source_col))
  }

  if (!target_col %in% colnames(df)) {
    stop(sprintf("Target column '%s' not found in data frame", target_col))
  }

  # Create standardized network
  net <- data.frame(
    source = df[[source_col]],
    target = df[[target_col]],
    stringsAsFactors = FALSE
  )

  # Add weight if provided
  if (!is.null(weight_col)) {
    if (weight_col %in% colnames(df)) {
      net$weight <- df[[weight_col]]
    } else {
      warning(sprintf("Weight column '%s' not found, using 1", weight_col))
      net$weight <- 1
    }
  } else {
    net$weight <- 1
  }

  # Add additional columns
  extra_cols <- list(...)
  for (col_name in names(extra_cols)) {
    if (extra_cols[[col_name]] %in% colnames(df)) {
      net[[col_name]] <- df[[extra_cols[[col_name]]]]
    }
  }

  message(sprintf("Created custom network: %d sources, %d interactions",
                  length(unique(net$source)), nrow(net)))

  return(net)
}

#' Run decouple with multiple methods
#'
#' Main decoupleR function that runs multiple statistical methods and computes consensus
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param statistics Vector of method names to run (default: c("mlm", "ulm", "wsum"))
#' @param consensus_score Whether to compute consensus score across methods
#' @param minsize Minimum number of targets per source
#' @param args List of additional arguments for each method
#' @return Results tibble with activities from all methods
#' @export
run_decouple <- function(mat, net,
                         statistics = c("mlm", "ulm", "wsum"),
                         consensus_score = TRUE,
                         minsize = 5,
                         args = list()) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  # Validate input
  validation <- validate_decoupler_input(mat, net)
  if (!validation$valid) {
    stop(paste("Validation failed:", paste(validation$errors, collapse = "; ")))
  }

  if (length(validation$warnings) > 0) {
    warning(paste("Validation warnings:", paste(validation$warnings, collapse = "; ")))
  }

  message(sprintf("Running decoupleR with %d methods...", length(statistics)))

  # Run decouple
  # Note: decouple() dispatches to individual run_* methods.
  # Network column mappings (source, target, weight/mor) are handled
  # automatically when columns are named conventionally.
  results <- decoupleR::decouple(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    statistics = statistics,
    args = args,
    minsize = minsize
  )

  message(sprintf("Completed: %d sources x %d conditions x %d methods",
                  length(unique(results$source)),
                  length(unique(results$condition)),
                  length(unique(results$statistic))))

  # Compute consensus score if requested and multiple methods were run
  if (consensus_score && length(unique(results$statistic)) >= 2) {
    message("Computing consensus scores...")
    results <- create_consensus_score(results)
  }

  return(results)
}

#' Run ULM (Univariate Linear Model)
#'
#' Fast and robust method for activity inference. Recommended for general use.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @param center Center the matrix by row means
#' @param na.rm Remove NA values when centering
#' @return Results tibble
#' @export
run_ulm_analysis <- function(mat, net, minsize = 5, center = FALSE, na.rm = FALSE) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_ulm(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    .mor = weight,
    minsize = minsize,
    center = center,
    na.rm = na.rm
  )

  return(results)
}

#' Run MLM (Multivariate Linear Model)
#'
#' Accounts for interactions between regulators. Slower but more comprehensive.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @return Results tibble
#' @export
run_mlm_analysis <- function(mat, net, minsize = 5) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_mlm(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    .mor = weight,
    minsize = minsize
  )

  return(results)
}

#' Run WSum (Weighted Sum)
#'
#' Simple weighted sum of target gene expression. Fast and interpretable.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @return Results tibble
#' @export
run_wsum_analysis <- function(mat, net, minsize = 5) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_wsum(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    .mor = weight,
    minsize = minsize
  )

  return(results)
}

#' Run WMean (Weighted Mean)
#'
#' Weighted mean of target gene expression, similar to WSum but normalized.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @return Results tibble
#' @export
run_wmean_analysis <- function(mat, net, minsize = 5) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_wmean(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    .mor = weight,
    minsize = minsize
  )

  return(results)
}

#' Run AUCell
#'
#' Area Under the Curve-based enrichment. Good for small gene sets.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @param nproc Number of processors for parallel processing
#' @param aucMaxRank Maximum rank for AUC calculation
#' @return Results tibble
#' @export
run_aucell_analysis <- function(mat, net, minsize = 5, nproc = 1, aucMaxRank = NULL) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  args <- list(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    minsize = minsize,
    nproc = nproc
  )

  if (!is.null(aucMaxRank)) {
    args$aucMaxRank <- aucMaxRank
  }

  results <- do.call(decoupleR::run_aucell, args)

  return(results)
}

#' Run ORA (Over-Representation Analysis)
#'
#' Fisher's exact test for binary or ranked data.
#'
#' @param mat Expression matrix (genes x samples) - binary or DEGs
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @param n_up Number of top genes to consider as "upregulated"
#' @return Results tibble
#' @export
run_ora_analysis <- function(mat, net, minsize = 5, n_up = NULL) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  # Validate binary input — ORA expects 0/1 matrix
  if (is.matrix(mat) || inherits(mat, "Matrix")) {
    unique_vals <- unique(as.vector(mat))
    if (!all(unique_vals %in% c(0, 1, NA))) {
      warning(sprintf(
        "ORA expects a binary matrix (0/1), but found values: %s. Results may be unreliable. Consider thresholding your matrix before ORA.",
        paste(head(setdiff(unique_vals, c(0, 1, NA)), 5), collapse = ", ")
      ))
    }
  }

  args <- list(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    minsize = minsize
  )

  if (!is.null(n_up)) {
    args$n_up <- n_up
  }

  results <- do.call(decoupleR::run_ora, args)

  return(results)
}

#' Run GSVA
#'
#' Gene Set Variation Analysis. Good for detecting subtle pathway activity changes.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @param method GSVA method ("gsva", "ssgsea", "zscore", "plage")
#' @param kcdf Kernel for CDF estimation ("Gaussian", "Poisson")
#' @param verbose Print progress messages
#' @return Results tibble
#' @export
run_gsva_analysis <- function(mat, net, minsize = 5,
                              method = "gsva", kcdf = "Gaussian",
                              verbose = FALSE) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_gsva(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    minsize = minsize,
    method = method,
    kcdf = kcdf,
    verbose = verbose
  )

  return(results)
}

#' Run FGSEA
#'
#' Fast Gene Set Enrichment Analysis. Good for ranked gene lists.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @param nperm Number of permutations for p-value estimation
#' @return Results tibble
#' @export
run_fgsea_analysis <- function(mat, net, minsize = 5, nperm = 1000) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_fgsea(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    minsize = minsize,
    nperm = nperm
  )

  return(results)
}

#' Run UDT (Univariate Decision Tree)
#'
#' Decision tree-based method for activity inference.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @return Results tibble
#' @export
run_udt_analysis <- function(mat, net, minsize = 5) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_udt(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    .mor = weight,
    minsize = minsize
  )

  return(results)
}

#' Run MDT (Multivariate Decision Tree)
#'
#' Multivariate decision tree-based method.
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param minsize Minimum number of targets per source
#' @return Results tibble
#' @export
run_mdt_analysis <- function(mat, net, minsize = 5) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  results <- decoupleR::run_mdt(
    mat = mat,
    network = net,
    .source = "source",
    .target = "target",
    .mor = weight,
    minsize = minsize
  )

  return(results)
}

#' Run multi-method analysis with individual methods
#'
#' Run multiple decoupleR methods individually and return combined results
#'
#' @param mat Expression matrix (genes x samples)
#' @param net Network data frame
#' @param methods Vector of method names to run
#' @param minsize Minimum number of targets per source
#' @param ... Additional arguments passed to individual methods
#' @return Combined results tibble
#' @export
run_decoupler_multi <- function(mat, net,
                                methods = c("ulm", "mlm", "wsum"),
                                minsize = 5, ...) {

  all_results <- list()

  for (method in methods) {
    message(sprintf("Running %s...", method))

    result <- tryCatch({
      switch(tolower(method),
             "ulm" = run_ulm_analysis(mat, net, minsize = minsize, ...),
             "mlm" = run_mlm_analysis(mat, net, minsize = minsize, ...),
             "wsum" = run_wsum_analysis(mat, net, minsize = minsize, ...),
             "wmean" = run_wmean_analysis(mat, net, minsize = minsize, ...),
             "aucell" = run_aucell_analysis(mat, net, minsize = minsize, ...),
             "ora" = run_ora_analysis(mat, net, minsize = minsize, ...),
             "gsva" = run_gsva_analysis(mat, net, minsize = minsize, ...),
             "fgsea" = run_fgsea_analysis(mat, net, minsize = minsize, ...),
             "udt" = run_udt_analysis(mat, net, minsize = minsize, ...),
             "mdt" = run_mdt_analysis(mat, net, minsize = minsize, ...),
             stop(paste("Unknown method:", method))
      )
    }, error = function(e) {
      warning(paste("Method", method, "failed:", conditionMessage(e)))
      NULL
    })

    if (!is.null(result)) {
      all_results[[method]] <- result
    }
  }

  # Combine results
  if (length(all_results) == 0) {
    stop("All methods failed")
  }

  combined <- dplyr::bind_rows(all_results)

  message(sprintf("Completed %d methods successfully", length(all_results)))

  return(combined)
}

#' Compute consensus score across methods
#'
#' Generate a consensus activity score by combining results from multiple methods
#'
#' @param acts Results tibble from multiple methods
#' @return Results tibble with consensus scores added
#' @export
create_consensus_score <- function(acts) {

  if (!requireNamespace("decoupleR", quietly = TRUE)) {
    stop("decoupleR package required")
  }

  # Check if there are multiple methods
  n_methods <- length(unique(acts$statistic))
  if (n_methods < 2) {
    warning("Need at least 2 methods for consensus. Returning original results.")
    return(acts)
  }

  # decoupleR does not provide a standalone run_consensus function.
  # Compute a simple consensus as the median score across methods per source and condition.
  consensus <- acts %>%
    dplyr::group_by(source, condition) %>%
    dplyr::summarise(
      score = median(score, na.rm = TRUE),
      statistic = "consensus",
      .groups = "drop"
    )

  return(dplyr::bind_rows(acts, consensus))
}

#' Run decoupleR with Seurat object
#'
#' Convenience function to run decoupleR directly from Seurat object
#'
#' @param seurat_obj Seurat object
#' @param net Network data frame
#' @param assay Assay to use (default: "RNA")
#' @param slot Slot to extract (default: "data")
#' @param method Method to run (default: "ulm")
#' @param minsize Minimum number of targets per source
#' @param ... Additional arguments passed to the method
#' @return Results tibble
#' @export
run_decoupler_seurat <- function(seurat_obj, net,
                                 assay = "RNA", slot = "data",
                                 method = "ulm", minsize = 5, ...) {

  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Validate assay exists
  if (!assay %in% names(seurat_obj@assays)) {
    available <- paste(names(seurat_obj@assays), collapse = ", ")
    stop(sprintf("Assay '%s' not found in Seurat object. Available: %s", assay, available))
  }

  # Extract matrix
  if (packageVersion("SeuratObject") >= "5.0.0") {
    mat <- Seurat::GetAssayData(seurat_obj, assay = assay, layer = slot)
  } else {
    mat <- Seurat::GetAssayData(seurat_obj, assay = assay, slot = slot)
  }

  # Run analysis
  results <- switch(tolower(method),
                    "ulm" = run_ulm_analysis(mat, net, minsize = minsize, ...),
                    "mlm" = run_mlm_analysis(mat, net, minsize = minsize),
                    "wsum" = run_wsum_analysis(mat, net, minsize = minsize),
                    "wmean" = run_wmean_analysis(mat, net, minsize = minsize),
                    "aucell" = run_aucell_analysis(mat, net, minsize = minsize, ...),
                    "ora" = run_ora_analysis(mat, net, minsize = minsize, ...),
                    "gsva" = run_gsva_analysis(mat, net, minsize = minsize, ...),
                    "fgsea" = run_fgsea_analysis(mat, net, minsize = minsize, ...),
                    "udt" = run_udt_analysis(mat, net, minsize = minsize),
                    "mdt" = run_mdt_analysis(mat, net, minsize = minsize),
                    stop(paste("Unknown method:", method))
  )

  return(results)
}

#' Add decoupleR results to Seurat object
#'
#' Add pathway/TF activities as metadata or assay
#'
#' @param seurat_obj Seurat object
#' @param acts Activity results from decoupleR
#' @param score_col Column containing scores (default: "score")
#' @param as_assay Store as assay instead of metadata
#' @param assay_name Name for the new assay (if as_assay = TRUE)
#' @return Seurat object with added data
#' @export
add_decoupler_to_seurat <- function(seurat_obj, acts,
                                    score_col = "score",
                                    as_assay = FALSE,
                                    assay_name = "decoupleR") {

  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Check for multiple statistics — pivot_wider cannot handle duplicates
  if ("statistic" %in% colnames(acts) && length(unique(acts$statistic)) > 1) {
    stats <- unique(acts$statistic)
    warning(sprintf(
      "acts contains multiple statistics (%s). Filtering to '%s'. Re-run with a single statistic or filter before calling this function.",
      paste(stats, collapse = ", "), stats[1]
    ))
    acts <- acts[acts$statistic == stats[1], ]
  }

  # Check if p_value column exists for filtering
  if ("p_value" %in% colnames(acts)) {
    # Warn about significant results
    n_sig <- sum(acts$p_value < 0.05, na.rm = TRUE)
    message(sprintf("Note: %d significant activities (p < 0.05) out of %d total",
                    n_sig, nrow(acts)))
  }

  # Reshape to wide format
  acts_wide <- acts %>%
    dplyr::select(source, condition, !!rlang::sym(score_col)) %>%
    tidyr::pivot_wider(
      names_from = source,
      values_from = !!rlang::sym(score_col)
    ) %>%
    as.data.frame()

  rownames(acts_wide) <- acts_wide$condition
  acts_wide$condition <- NULL

  if (as_assay) {
    # Add as new assay
    acts_mat <- as.matrix(t(acts_wide))
    seurat_obj[[assay_name]] <- Seurat::CreateAssayObject(data = acts_mat)
    message(sprintf("Added decoupleR results as '%s' assay with %d features",
                    assay_name, nrow(acts_mat)))
  } else {
    # Add as metadata
    # Match cells
    cells <- colnames(seurat_obj)
    acts_matched <- acts_wide[match(cells, rownames(acts_wide)), , drop = FALSE]
    rownames(acts_matched) <- cells

    # Add each source as metadata
    n_added <- 0
    for (col in colnames(acts_matched)) {
      safe_name <- make.names(paste0(assay_name, "_", col))
      seurat_obj[[safe_name]] <- acts_matched[[col]]
      n_added <- n_added + 1
    }

    message(sprintf("Added %d decoupleR scores to metadata", n_added))
  }

  return(seurat_obj)
}

#' Summarize decoupleR results
#'
#' Generate summary statistics from decoupleR results
#'
#' @param acts Activity results from decoupleR
#' @param p_threshold P-value threshold for significance (if p_value column exists)
#' @return List with summary statistics
#' @export
summarize_decoupler_results <- function(acts, p_threshold = 0.05) {

  summary <- list(
    n_sources = length(unique(acts$source)),
    n_conditions = length(unique(acts$condition)),
    n_scores = nrow(acts),
    methods = unique(acts$statistic)
  )

  # Score statistics
  summary$score_range <- range(acts$score, na.rm = TRUE)
  summary$score_mean <- mean(acts$score, na.rm = TRUE)
  summary$score_sd <- sd(acts$score, na.rm = TRUE)
  summary$score_median <- median(acts$score, na.rm = TRUE)

  # Significant results if p_value exists
  if ("p_value" %in% colnames(acts)) {
    summary$n_significant <- sum(acts$p_value < p_threshold, na.rm = TRUE)
    summary$significant_fraction <- summary$n_significant / nrow(acts)
  }

  # Top activities per source
  top_acts <- acts %>%
    dplyr::group_by(source) %>%
    dplyr::summarise(
      mean_score = mean(score, na.rm = TRUE),
      sd_score = sd(score, na.rm = TRUE),
      max_score = max(score, na.rm = TRUE),
      min_score = min(score, na.rm = TRUE),
      .groups = 'drop'
    ) %>%
    dplyr::arrange(dplyr::desc(abs(mean_score)))

  summary$top_sources <- head(top_acts, 10)

  # Method comparison
  if (length(summary$methods) > 1) {
    method_cor <- acts %>%
      dplyr::select(source, condition, statistic, score) %>%
      tidyr::pivot_wider(names_from = statistic, values_from = score) %>%
      dplyr::select(-source, -condition) %>%
      cor(use = "pairwise.complete.obs")

    summary$method_correlations <- method_cor
  }

  return(summary)
}

#' Export decoupleR results
#'
#' Export results to CSV files
#'
#' @param acts Activity results from decoupleR
#' @param output_dir Output directory
#' @param prefix File prefix
#' @return Invisible list of exported file paths
#' @export
export_decoupler_results <- function(acts,
                                     output_dir = "./decoupler_output",
                                     prefix = "decoupler") {

  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  files <- list()

  # Export long format
  long_file <- file.path(output_dir, paste0(prefix, "_activities_long.csv"))
  write.csv(acts, long_file, row.names = FALSE)
  files$long <- long_file
  message(sprintf("Exported: %s", long_file))

  # Export wide format
  acts_wide <- acts %>%
    dplyr::select(source, condition, score) %>%
    tidyr::pivot_wider(names_from = source, values_from = score) %>%
    as.data.frame()

  wide_file <- file.path(output_dir, paste0(prefix, "_activities_wide.csv"))
  write.csv(acts_wide, wide_file, row.names = FALSE)
  files$wide <- wide_file
  message(sprintf("Exported: %s", wide_file))

  # Export summary
  summary <- summarize_decoupler_results(acts)
  summary_file <- file.path(output_dir, paste0(prefix, "_summary.txt"))

  con <- file(summary_file, open = "wt")
  on.exit(close(con), add = TRUE)

  writeLines("decoupleR Analysis Summary", con)
  writeLines("==========================\n", con)
  writeLines(sprintf("Sources: %d", summary$n_sources), con)
  writeLines(sprintf("Conditions: %d", summary$n_conditions), con)
  writeLines(sprintf("Total scores: %d", summary$n_scores), con)
  writeLines(sprintf("Methods: %s", paste(summary$methods, collapse = ", ")), con)
  writeLines(sprintf("\nScore range: %.3f to %.3f",
                     summary$score_range[1], summary$score_range[2]), con)
  writeLines(sprintf("Mean score: %.3f (SD: %.3f)",
                     summary$score_mean, summary$score_sd), con)
  writeLines("\nTop 10 sources by mean absolute score:", con)
  capture.output(print(summary$top_sources), file = con)

  files$summary <- summary_file
  message(sprintf("Exported: %s", summary_file))

  invisible(files)
}
