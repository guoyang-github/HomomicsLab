# Utility Functions for diffcyt
# =============================
#
# Helper functions for data manipulation, result processing, and analysis utilities

#' Create sample experiment info
#'
#' @param sample_ids Vector of sample IDs
#' @param group_ids Vector of group IDs
#' @param ... Additional columns
#' @return Data frame with experiment info
#' @export
create_experiment_info <- function(sample_ids, group_ids, ...) {
  experiment_info <- data.frame(
    sample_id = factor(sample_ids),
    group_id = factor(group_ids),
    stringsAsFactors = FALSE,
    ...
  )
  return(experiment_info)
}

#' Create sample marker info
#'
#' @param marker_names Vector of marker names
#' @param marker_classes Vector of marker classes ("type", "state", "none")
#' @param channel_names Optional vector of channel names
#' @return Data frame with marker info
#' @export
create_marker_info <- function(marker_names, marker_classes,
                               channel_names = NULL) {
  if (!all(marker_classes %in% c("type", "state", "none"))) {
    stop("marker_classes must be one of: 'type', 'state', 'none'")
  }

  if (is.null(channel_names)) {
    channel_names <- sprintf("channel%03d", seq_along(marker_names))
  }

  marker_info <- data.frame(
    channel_name = channel_names,
    marker_name = marker_names,
    marker_class = factor(marker_classes, levels = c("type", "state", "none")),
    stringsAsFactors = FALSE
  )

  return(marker_info)
}

#' Summarize diffcyt results
#'
#' @param res Test results object
#' @param p_threshold P-value threshold for significance
#' @return List with summary statistics
#' @export
summarize_results <- function(res, p_threshold = 0.05) {
  res_table <- SummarizedExperiment::rowData(res)

  # Identify p-value column
  p_cols <- grep("^p_adj", colnames(res_table), value = TRUE)
  if (length(p_cols) == 0) {
    stop("No adjusted p-value column found")
  }
  p_col <- p_cols[1]

  # Calculate summary stats
  n_total <- nrow(res_table)
  n_sig <- sum(res_table[[p_col]] < p_threshold, na.rm = TRUE)
  n_up <- sum(res_table[[p_col]] < p_threshold & res_table$logFC > 0, na.rm = TRUE)
  n_down <- sum(res_table[[p_col]] < p_threshold & res_table$logFC < 0, na.rm = TRUE)

  summary <- list(
    n_total = n_total,
    n_significant = n_sig,
    n_upregulated = n_up,
    n_downregulated = n_down,
    prop_significant = n_sig / n_total,
    p_threshold = p_threshold
  )

  return(summary)
}

#' Print summary of diffcyt results
#'
#' @param res Test results object
#' @param p_threshold P-value threshold
#' @export
print_results_summary <- function(res, p_threshold = 0.05) {
  summary <- summarize_results(res, p_threshold)

  message("diffcyt Results Summary")
  message("=======================")
  message(sprintf("Total clusters tested: %d", summary$n_total))
  message(sprintf("Significant clusters: %d (%.1f%%)",
                  summary$n_significant,
                  summary$prop_significant * 100))
  message(sprintf("  Up-regulated: %d", summary$n_upregulated))
  message(sprintf("  Down-regulated: %d", summary$n_downregulated))
}

#' Export results to CSV
#'
#' @param res Test results object
#' @param output_file Output file path
#' @param p_threshold P-value threshold for filtering
#' @param significant_only Whether to export only significant results
#' @export
export_results <- function(res, output_file = "diffcyt_results.csv",
                           p_threshold = NULL, significant_only = FALSE) {
  res_table <- SummarizedExperiment::rowData(res)
  res_df <- as.data.frame(res_table)

  if (significant_only) {
    if (is.null(p_threshold)) {
      p_threshold <- 0.05
    }
    p_col <- grep("^p_adj", colnames(res_df), value = TRUE)[1]
    res_df <- res_df[res_df[[p_col]] < p_threshold, ]
    message(sprintf("Exported %d significant results to %s", nrow(res_df), output_file))
  } else {
    message(sprintf("Exported %d results to %s", nrow(res_df), output_file))
  }

  write.csv(res_df, output_file, row.names = FALSE)
}

#' Merge DA and DS results
#'
#' @param da_res DA results
#' @param ds_res DS results
#' @return Merged data frame
#' @export
merge_da_ds_results <- function(da_res, ds_res) {
  da_table <- as.data.frame(SummarizedExperiment::rowData(da_res))
  ds_table <- as.data.frame(SummarizedExperiment::rowData(ds_res))

  # Identify common cluster column
  if ("cluster_id" %in% colnames(da_table) && "cluster_id" %in% colnames(ds_table)) {
    merged <- merge(da_table, ds_table, by = "cluster_id", suffixes = c("_DA", "_DS"))
  } else {
    stop("Could not find common cluster_id column")
  }

  return(merged)
}

#' Filter clusters by abundance
#'
#' @param d_counts Cluster counts
#' @param min_cells Minimum cells per cluster
#' @param min_samples Minimum samples with min_cells
#' @return Filtered counts object
#' @export
filter_clusters_by_abundance <- function(d_counts, min_cells = 3,
                                         min_samples = NULL) {
  counts <- SummarizedExperiment::assay(d_counts)

  if (is.null(min_samples)) {
    min_samples <- ncol(counts) / 2
  }

  # Identify clusters to keep
  keep <- rowSums(counts >= min_cells) >= min_samples

  message(sprintf("Keeping %d / %d clusters (min_cells=%d, min_samples=%d)",
                  sum(keep), nrow(counts), min_cells, min_samples))

  d_counts_filtered <- d_counts[keep, ]
  return(d_counts_filtered)
}

#' Normalize cluster counts
#'
#' @param d_counts Cluster counts
#' @param method Normalization method ("TMM", "RLE", "upperquartile")
#' @return Normalized counts
#' @export
normalize_counts <- function(d_counts, method = "TMM") {
  if (!requireNamespace("edgeR", quietly = TRUE)) {
    stop("edgeR package required for normalization")
  }

  counts <- SummarizedExperiment::assay(d_counts)

  # Create DGEList
  dge <- edgeR::DGEList(counts)

  # Calculate normalization factors
  dge <- edgeR::calcNormFactors(dge, method = method)

  # Return normalized counts (CPM)
  norm_counts <- edgeR::cpm(dge, log = FALSE)

  return(norm_counts)
}

#' Convert SingleCellExperiment to diffcyt format
#'
#' @param sce SingleCellExperiment object
#' @param marker_info Marker information (optional)
#' @return SummarizedExperiment in diffcyt format
#' @export
convert_sce_to_diffcyt <- function(sce, marker_info = NULL) {
  if (!requireNamespace("SingleCellExperiment", quietly = TRUE)) {
    stop("SingleCellExperiment package required")
  }

  # Extract expression data
  exprs <- SummarizedExperiment::assay(sce)

  # Create experiment info from colData
  if ("sample_id" %in% colnames(SummarizedExperiment::colData(sce))) {
    sample_ids <- sce$sample_id
    experiment_info <- data.frame(
      sample_id = factor(sample_ids),
      stringsAsFactors = FALSE
    )
  } else {
    stop("SingleCellExperiment must contain 'sample_id' in colData")
  }

  # Create marker info if not provided
  if (is.null(marker_info)) {
    marker_names <- rownames(sce)
    marker_classes <- rep("state", length(marker_names))  # Default to state
    marker_info <- create_marker_info(marker_names, marker_classes)
  }

  # Split expression matrix by sample_id (cells as rows, markers as columns)
  sample_ids_unique <- unique(sample_ids)
  d_input_list <- lapply(sample_ids_unique, function(sid) {
    cell_idx <- which(sample_ids == sid)
    t(exprs[, cell_idx, drop = FALSE])
  })
  names(d_input_list) <- as.character(sample_ids_unique)

  # Prepare data
  d_se <- prepare_diffcyt_data(
    d_input = d_input_list,
    experiment_info = experiment_info,
    marker_info = marker_info
  )

  return(d_se)
}

#' Subsample cells for testing
#'
#' @param d_input Input data (list)
#' @param n_sub Number of cells per sample
#' @param seed Random seed
#' @return Subsampled data
#' @export
subsample_cells <- function(d_input, n_sub = 1000, seed = NULL) {
  if (!is.null(seed)) {
    set.seed(seed)
  }

  subsampled <- lapply(d_input, function(d) {
    n <- nrow(d)
    if (n > n_sub) {
      idx <- sample(seq_len(n), n_sub)
      d[idx, , drop = FALSE]
    } else {
      d
    }
  })

  return(subsampled)
}

#' Compare two groups
#'
#' @param d_counts Cluster counts
#' @param group1 Sample IDs for group 1
#' @param group2 Sample IDs for group 2
#' @return Comparison results
#' @export
compare_two_groups <- function(d_counts, group1, group2) {
  counts <- SummarizedExperiment::assay(d_counts)

  # Subset to groups
  counts1 <- counts[, group1, drop = FALSE]
  counts2 <- counts[, group2, drop = FALSE]

  # Calculate mean abundance per group
  mean1 <- rowMeans(counts1)
  mean2 <- rowMeans(counts2)

  # Calculate fold change
  logFC <- log2((mean2 + 1) / (mean1 + 1))

  # Create result
  result <- data.frame(
    cluster_id = rownames(counts),
    mean_group1 = mean1,
    mean_group2 = mean2,
    logFC = logFC
  )

  return(result)
}

#' Create random test data
#'
#' @param n_samples Number of samples
#' @param n_cells_per_sample Number of cells per sample
#' @param n_markers Number of markers
#' @param n_groups Number of groups
#' @param seed Random seed
#' @return List with d_input, experiment_info, marker_info
#' @export
create_test_data <- function(n_samples = 4,
                             n_cells_per_sample = 1000,
                             n_markers = 20,
                             n_groups = 2,
                             seed = NULL) {
  if (!is.null(seed)) {
    set.seed(seed)
  }

  # Create random expression data
  d_random <- function(n, ncol) {
    matrix(rnorm(n * ncol, mean = 0, sd = 1), nrow = n, ncol = ncol)
  }

  d_input <- lapply(seq_len(n_samples), function(i) {
    d_random(n_cells_per_sample, n_markers)
  })

  names(d_input) <- paste0("sample", seq_len(n_samples))

  # Create experiment info
  group_ids <- rep(paste0("group", seq_len(n_groups)), length.out = n_samples)
  experiment_info <- data.frame(
    sample_id = factor(paste0("sample", seq_len(n_samples))),
    group_id = factor(group_ids),
    stringsAsFactors = FALSE
  )

  # Create marker info
  n_type <- floor(n_markers / 2)
  n_state <- n_markers - n_type

  marker_info <- data.frame(
    channel_name = paste0("channel", sprintf("%03d", seq_len(n_markers))),
    marker_name = paste0("marker", sprintf("%02d", seq_len(n_markers))),
    marker_class = factor(c(rep("type", n_type), rep("state", n_state)),
                          levels = c("type", "state", "none")),
    stringsAsFactors = FALSE
  )

  list(
    d_input = d_input,
    experiment_info = experiment_info,
    marker_info = marker_info
  )
}

#' Add differential signal to test data
#'
#' @param d_input Input data list
#' @param da_clusters Clusters with DA signal
#' @param ds_clusters Clusters with DS signal
#' @param da_samples Samples with DA signal
#' @param ds_samples Samples with DS signal
#' @param effect_size Effect size (default: 2)
#' @return Modified d_input
#' @export
add_differential_signal <- function(d_input,
                                    da_clusters = NULL,
                                    ds_clusters = NULL,
                                    da_samples = NULL,
                                    ds_samples = NULL,
                                    effect_size = 2) {
  # This is a simplified version - in practice, you'd integrate with clustering
  message("Adding differential signal to test data")

  # Add DA signal (sample-level abundance shift)
  if (!is.null(da_samples)) {
    for (s in da_samples) {
      if (s %in% names(d_input)) {
        d_input[[s]] <- d_input[[s]] + effect_size
      } else {
        warning(sprintf("DA sample '%s' not found in d_input, skipping", s))
      }
    }
  }

  # Add DS signal (marker-level shift for specific clusters)
  if (!is.null(ds_samples) || !is.null(ds_clusters)) {
    warning("DS signal injection is not yet implemented in this simplified wrapper")
  }

  return(d_input)
}

#' Create comprehensive analysis report
#'
#' @param d_se SummarizedExperiment object
#' @param da_res DA results (optional)
#' @param ds_res DS results (optional)
#' @param output_file Output file path
#' @export
create_analysis_report <- function(d_se, da_res = NULL, ds_res = NULL,
                                   output_file = "diffcyt_report.txt") {
  sink(output_file)
  on.exit(sink(), add = TRUE)

  cat("diffcyt Analysis Report\n")
  cat("=======================\n\n")
  cat(sprintf("Date: %s\n", Sys.time()))
  cat(sprintf("Total cells: %d\n", sum(S4Vectors::metadata(d_se)$n_cells)))
  cat(sprintf("Samples: %d\n", length(S4Vectors::metadata(d_se)$n_cells)))

  if (!is.null(da_res)) {
    cat("\n--- Differential Abundance (DA) Results ---\n")
    print_results_summary(da_res)
  }

  if (!is.null(ds_res)) {
    cat("\n--- Differential State (DS) Results ---\n")
    print_results_summary(ds_res)
  }

  message(sprintf("Report saved to %s", output_file))
}
