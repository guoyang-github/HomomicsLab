# Core Analysis Functions for diffcyt
# =====================================
#
# This module provides wrapper functions for diffcyt differential analysis
# including data preparation, clustering, differential abundance (DA) testing,
# and differential state (DS) testing.
#
# Reference: Weber et al., Communications Biology 2019

#' Check diffcyt dependencies
#'
#' Check if required packages are installed
#'
#' @return Logical indicating if all dependencies are available
#' @export
check_diffcyt_dependencies <- function() {
  required_pkgs <- c("diffcyt", "flowCore", "SummarizedExperiment", "S4Vectors")
  missing_pkgs <- required_pkgs[!sapply(required_pkgs, requireNamespace, quietly = TRUE)]

  if (length(missing_pkgs) > 0) {
    stop(sprintf("Missing required packages: %s. Install with: BiocManager::install(c('%s'))",
                 paste(missing_pkgs, collapse = ", "),
                 paste(missing_pkgs, collapse = "', '")))
  }

  message("All diffcyt dependencies are available")
  return(TRUE)
}

#' Validate input data for diffcyt
#'
#' @param d_input Input data (flowSet, list of flowFrames, or SingleCellExperiment)
#' @param experiment_info Experiment information data frame
#' @param marker_info Marker information data frame
#' @return List with validation results
#' @export
validate_diffcyt_input <- function(d_input, experiment_info = NULL, marker_info = NULL) {
  # Check input type
  is_catalyst <- inherits(d_input, "SingleCellExperiment")

  if (!is_catalyst) {
    # For non-CATALYST input
    if (is.null(experiment_info)) {
      stop("'experiment_info' must be provided (unless using SingleCellExperiment from CATALYST)")
    }
    if (is.null(marker_info)) {
      stop("'marker_info' must be provided (unless using SingleCellExperiment from CATALYST)")
    }

    # Check experiment_info
    if (!("sample_id" %in% colnames(experiment_info))) {
      stop("'experiment_info' must contain a column named 'sample_id'")
    }

    # Check marker_info
    if (!("marker_name" %in% colnames(marker_info)) || !("marker_class" %in% colnames(marker_info))) {
      stop("'marker_info' must contain columns 'marker_name' and 'marker_class'")
    }

    # Check marker_class levels
    valid_classes <- c("type", "state", "none")
    if (!all(marker_info$marker_class %in% valid_classes)) {
      stop(sprintf("'marker_class' must be one of: %s", paste(valid_classes, collapse = ", ")))
    }

    message("Data validation passed (non-CATALYST input)")
    message(sprintf("  Samples: %d", nrow(experiment_info)))
    message(sprintf("  Markers: %d (%d type, %d state, %d none)",
                    nrow(marker_info),
                    sum(marker_info$marker_class == "type"),
                    sum(marker_info$marker_class == "state"),
                    sum(marker_info$marker_class == "none")))
  } else {
    message("Data validation passed (CATALYST SingleCellExperiment input)")
    message(sprintf("  Samples: %d", length(unique(d_input$sample_id))))
  }

  list(is_catalyst = is_catalyst, valid = TRUE)
}

#' Prepare data for diffcyt analysis
#'
#' Wrapper around diffcyt::prepareData with additional validation
#'
#' @param d_input Input data (flowSet, list of flowFrames/data.frames/matrices)
#' @param experiment_info Experiment information data frame
#' @param marker_info Marker information data frame
#' @param cols_to_include Logical vector indicating which columns to include
#' @param subsampling Whether to subsample equal number of cells from each sample
#' @param n_sub Number of cells to subsample (default: min sample size)
#' @param seed_sub Random seed for subsampling
#' @return SummarizedExperiment object
#' @export
prepare_diffcyt_data <- function(d_input,
                                  experiment_info,
                                  marker_info,
                                  cols_to_include = NULL,
                                  subsampling = FALSE,
                                  n_sub = NULL,
                                  seed_sub = NULL) {
  if (!requireNamespace("diffcyt", quietly = TRUE)) {
    stop("diffcyt package required")
  }

  message("Preparing data for diffcyt...")
  message(sprintf("  Subsampling: %s", ifelse(subsampling, "enabled", "disabled")))

  d_se <- diffcyt::prepareData(
    d_input = d_input,
    experiment_info = experiment_info,
    marker_info = marker_info,
    cols_to_include = cols_to_include,
    subsampling = subsampling,
    n_sub = n_sub,
    seed_sub = seed_sub
  )

  n_cells <- S4Vectors::metadata(d_se)$n_cells
  message(sprintf("  Total cells: %d", sum(n_cells)))
  message(sprintf("  Cells per sample: min=%d, max=%d, mean=%.1f",
                  min(n_cells), max(n_cells), mean(n_cells)))

  return(d_se)
}

#' Generate clusters using FlowSOM
#'
#' @param d_se SummarizedExperiment object
#' @param cols_clustering Columns to use for clustering (NULL = type markers)
#' @param xdim Horizontal grid size (default: 10)
#' @param ydim Vertical grid size (default: 10)
#' @param meta_clustering Whether to perform meta-clustering
#' @param meta_k Number of meta-clusters
#' @param seed_clustering Random seed
#' @return SummarizedExperiment with cluster assignments
#' @export
generate_diffcyt_clusters <- function(d_se,
                                       cols_clustering = NULL,
                                       xdim = 10,
                                       ydim = 10,
                                       meta_clustering = FALSE,
                                       meta_k = 40,
                                       seed_clustering = NULL) {
  if (!requireNamespace("diffcyt", quietly = TRUE)) {
    stop("diffcyt package required")
  }

  n_clusters <- xdim * ydim
  message(sprintf("Generating clusters with FlowSOM..."))
  message(sprintf("  Grid: %d x %d = %d clusters", xdim, ydim, n_clusters))
  message(sprintf("  Meta-clustering: %s", ifelse(meta_clustering, sprintf("enabled (k=%d)", meta_k), "disabled")))

  d_se <- diffcyt::generateClusters(
    d_se = d_se,
    cols_clustering = cols_clustering,
    xdim = xdim,
    ydim = ydim,
    meta_clustering = meta_clustering,
    meta_k = meta_k,
    seed_clustering = seed_clustering
  )

  # Get cluster counts
  cluster_ids <- SummarizedExperiment::rowData(d_se)$cluster_id
  n_detected <- length(unique(cluster_ids))
  message(sprintf("  Detected %d non-empty clusters", n_detected))

  return(d_se)
}

#' Test for differential abundance (DA) using edgeR
#'
#' @param d_counts Cluster counts from calcCounts
#' @param design Design matrix
#' @param contrast Contrast matrix
#' @param min_cells Minimum cells per cluster
#' @param min_samples Minimum samples with min_cells
#' @param normalize Whether to include normalization factors
#' @param norm_factors Normalization factors (default: "TMM")
#' @return DA test results
#' @export
test_da_edger <- function(d_counts,
                          design,
                          contrast,
                          min_cells = 3,
                          min_samples = NULL,
                          normalize = FALSE,
                          norm_factors = "TMM") {
  if (!requireNamespace("diffcyt", quietly = TRUE)) {
    stop("diffcyt package required")
  }

  if (is.null(min_samples)) {
    min_samples <- floor(ncol(d_counts) / 2)
  }

  message("Testing for differential abundance (DA) using edgeR...")
  message(sprintf("  Filtering: min_cells=%d, min_samples=%d", min_cells, min_samples))

  res <- diffcyt::testDA_edgeR(
    d_counts = d_counts,
    design = design,
    contrast = contrast,
    min_cells = min_cells,
    min_samples = min_samples,
    normalize = normalize,
    norm_factors = norm_factors
  )

  # Get number of significant clusters
  res_table <- SummarizedExperiment::rowData(res)
  n_sig <- sum(res_table$p_adj < 0.05, na.rm = TRUE)
  message(sprintf("  Found %d significant DA clusters (FDR < 0.05)", n_sig))

  return(res)
}

#' Run complete diffcyt pipeline
#'
#' @param d_input Input data
#' @param experiment_info Experiment information
#' @param marker_info Marker information
#' @param analysis_type "DA" or "DS"
#' @param method_DA DA method ("edgeR", "voom", "GLMM")
#' @param method_DS DS method ("limma", "LMM")
#' @param design Design matrix (optional)
#' @param formula Formula object (optional)
#' @param contrast Contrast matrix
#' @param transform Whether to apply arcsinh transform
#' @param cofactor Cofactor for transform
#' @param xdim FlowSOM x dimension
#' @param ydim FlowSOM y dimension
#' @param meta_clustering Whether to do meta-clustering
#' @param seed_clustering Random seed
#' @param min_cells Minimum cells per cluster
#' @param min_samples Minimum samples
#' @param verbose Whether to print messages
#' @return List with results and data objects
#' @export
run_diffcyt_pipeline <- function(d_input,
                                  experiment_info = NULL,
                                  marker_info = NULL,
                                  analysis_type = c("DA", "DS"),
                                  method_DA = c("edgeR", "voom", "GLMM"),
                                  method_DS = c("limma", "LMM"),
                                  design = NULL,
                                  formula = NULL,
                                  contrast = NULL,
                                  transform = TRUE,
                                  cofactor = 5,
                                  xdim = 10,
                                  ydim = 10,
                                  meta_clustering = FALSE,
                                  seed_clustering = NULL,
                                  min_cells = 3,
                                  min_samples = NULL,
                                  verbose = TRUE) {
  if (!requireNamespace("diffcyt", quietly = TRUE)) {
    stop("diffcyt package required")
  }

  analysis_type <- match.arg(analysis_type)
  method_DA <- match.arg(method_DA)
  method_DS <- match.arg(method_DS)

  # Validate inputs
  validation <- validate_diffcyt_input(d_input, experiment_info, marker_info)

  # Step 1: Prepare data (if not CATALYST input)
  if (!validation$is_catalyst) {
    if (verbose) message("\n[Step 1/5] Preparing data...")
    d_se <- prepare_diffcyt_data(d_input, experiment_info, marker_info)

    # Step 2: Transform
    if (transform) {
      if (verbose) message("\n[Step 2/5] Transforming data...")
      d_se <- diffcyt::transformData(d_se, cofactor = cofactor)
    }

    # Step 3: Clustering
    if (verbose) message("\n[Step 3/5] Generating clusters...")
    d_se <- generate_diffcyt_clusters(d_se,
                                       xdim = xdim,
                                       ydim = ydim,
                                       meta_clustering = meta_clustering,
                                       seed_clustering = seed_clustering)
  } else {
    # CATALYST input - use directly
    if (verbose) message("\nUsing CATALYST SingleCellExperiment input")
    d_se <- d_input
  }

  # Step 4: Calculate features
  if (verbose) message("\n[Step 4/5] Calculating features...")
  d_counts <- diffcyt::calcCounts(d_se)

  if (analysis_type == "DS") {
    d_medians <- diffcyt::calcMedians(d_se)
  }

  # Check required args for testing
  if (is.null(contrast)) {
    stop("'contrast' must be provided for differential testing")
  }

  # Step 5: Differential testing
  if (verbose) message(sprintf("\n[Step 5/5] Testing for %s...", analysis_type))

  if (analysis_type == "DA") {
    if (method_DA == "edgeR") {
      if (is.null(design)) stop("'design' required for edgeR method")
      res <- test_da_edger(d_counts, design, contrast, min_cells, min_samples)
    } else if (method_DA == "voom") {
      if (is.null(design)) stop("'design' required for voom method")
      res <- diffcyt::testDA_voom(d_counts, design, contrast, min_cells = min_cells, min_samples = min_samples)
    } else if (method_DA == "GLMM") {
      if (is.null(formula)) stop("'formula' required for GLMM method")
      res <- diffcyt::testDA_GLMM(d_counts, formula, contrast, min_cells = min_cells, min_samples = min_samples)
    } else {
      stop(sprintf("Unsupported DA method: %s", method_DA))
    }
  } else if (analysis_type == "DS") {
    if (method_DS == "limma") {
      if (is.null(design)) stop("'design' required for limma method")
      res <- diffcyt::testDS_limma(d_medians = d_medians, d_counts = d_counts, design = design, contrast = contrast, min_cells = min_cells, min_samples = min_samples)
    } else if (method_DS == "LMM") {
      if (is.null(formula)) stop("'formula' required for LMM method")
      res <- diffcyt::testDS_LMM(d_counts, d_medians, formula, contrast, min_cells = min_cells, min_samples = min_samples)
    } else {
      stop(sprintf("Unsupported DS method: %s", method_DS))
    }
  } else {
    stop(sprintf("Unsupported analysis type: %s", analysis_type))
  }

  # Compile results
  if (analysis_type == "DA") {
    results <- list(res = res, d_se = d_se, d_counts = d_counts)
  } else {
    results <- list(res = res, d_se = d_se, d_counts = d_counts, d_medians = d_medians)
  }

  if (verbose) message("\nPipeline complete!")
  return(results)
}

#' Extract top significant results
#'
#' @param res Test results object
#' @param n_top Number of top results to return
#' @param p_value_col Column name for p-values
#' @param sort_by Column to sort by
#' @return Data frame with top results
#' @export
get_top_results <- function(res, n_top = 10, p_value_col = "p_adj", sort_by = NULL) {
  if (!requireNamespace("diffcyt", quietly = TRUE)) {
    stop("diffcyt package required")
  }

  if (is.null(sort_by)) {
    sort_by <- p_value_col
  }

  top_table <- diffcyt::topTable(res, format_vals = TRUE)

  if (nrow(top_table) > n_top) {
    top_table <- top_table[1:n_top, ]
  }

  return(top_table)
}

#' Get significant clusters
#'
#' @param res Test results object
#' @param p_threshold P-value threshold (default: 0.05)
#' @param p_value_col Column name for p-values
#' @return Vector of significant cluster IDs
#' @export
get_significant_clusters <- function(res, p_threshold = 0.05, p_value_col = "p_adj") {
  res_table <- SummarizedExperiment::rowData(res)

  if (!(p_value_col %in% colnames(res_table))) {
    stop(sprintf("Column '%s' not found in results", p_value_col))
  }

  sig_idx <- res_table[[p_value_col]] < p_threshold
  sig_clusters <- res_table$cluster_id[sig_idx]

  message(sprintf("Found %d significant clusters (p < %g)", length(sig_clusters), p_threshold))
  return(sig_clusters)
}
