# Visualization Functions for diffcyt
# ====================================
#
# This module provides visualization functions for diffcyt differential analysis results

#' Plot volcano plot for differential abundance
#'
#' @param res Test results object
#' @param p_threshold P-value threshold for significance
#' @param logfc_threshold Log fold change threshold
#' @param title Plot title
#' @return ggplot object
#' @export
plot_volcano <- function(res, p_threshold = 0.05, logfc_threshold = 1,
                         title = "Volcano Plot") {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  res_table <- SummarizedExperiment::rowData(res)

  # Handle different column names for DA vs DS
  if ("logFC" %in% colnames(res_table)) {
    x_col <- "logFC"
    y_col <- "p_adj"
  } else if ("logFC_cluster" %in% colnames(res_table)) {
    x_col <- "logFC_cluster"
    y_col <- "p_adj_cluster"
  } else {
    stop("Could not identify logFC column in results")
  }

  # Create significance column
  res_table$significant <- ifelse(
    res_table[[y_col]] < p_threshold & abs(res_table[[x_col]]) > logfc_threshold,
    "Significant",
    "Not Significant"
  )

  # Handle -log10(0)
  y_vals <- res_table[[y_col]]
  y_min_pos <- min(y_vals[y_vals > 0], na.rm = TRUE)
  y_vals[y_vals == 0] <- y_min_pos / 10
  res_table$neg_log10_p <- -log10(y_vals)

  p <- ggplot2::ggplot(res_table, ggplot2::aes(x = .data[[x_col]],
                                               y = .data[["neg_log10_p"]],
                                               color = .data[["significant"]])) +
    ggplot2::geom_point(alpha = 0.6, size = 2) +
    ggplot2::scale_color_manual(values = c("Not Significant" = "gray50",
                                            "Significant" = "red")) +
    ggplot2::geom_vline(xintercept = c(-logfc_threshold, logfc_threshold),
                        linetype = "dashed", color = "gray70") +
    ggplot2::geom_hline(yintercept = -log10(p_threshold),
                        linetype = "dashed", color = "gray70") +
    ggplot2::labs(x = "Log Fold Change",
                  y = "-log10(Adjusted P-value)",
                  title = title,
                  color = "Significance") +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "bottom")

  return(p)
}

#' Plot cluster abundance by sample
#'
#' @param d_counts Cluster counts from calcCounts
#' @param clusters Clusters to plot (NULL = all)
#' @param title Plot title
#' @return ggplot object
#' @export
plot_cluster_abundance <- function(d_counts, clusters = NULL,
                                   title = "Cluster Abundance") {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("reshape2", quietly = TRUE)) {
    stop("reshape2 package required")
  }

  counts <- SummarizedExperiment::assay(d_counts)

  if (!is.null(clusters)) {
    counts <- counts[clusters, , drop = FALSE]
  }

  # Melt for ggplot
  counts_df <- reshape2::melt(counts)
  colnames(counts_df) <- c("cluster_id", "sample_id", "count")

  p <- ggplot2::ggplot(counts_df, ggplot2::aes(x = sample_id, y = count, fill = cluster_id)) +
    ggplot2::geom_bar(stat = "identity", position = "fill") +
    ggplot2::labs(x = "Sample", y = "Proportion", title = title) +
    ggplot2::theme_minimal() +
    ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1))

  return(p)
}

#' Plot marker expression heatmap
#'
#' @param d_medians Cluster medians from calcMedians
#' @param markers Markers to include (NULL = all state markers)
#' @param scale Scale rows
#' @return ComplexHeatmap object
#' @export
plot_marker_heatmap <- function(d_medians, markers = NULL, scale = TRUE) {
  if (!requireNamespace("ComplexHeatmap", quietly = TRUE)) {
    stop("ComplexHeatmap package required")
  }

  # Get median expression
  medians <- SummarizedExperiment::assay(d_medians)

  # Select markers if specified
  if (!is.null(markers)) {
    medians <- medians[, markers, drop = FALSE]
  }

  # Scale if requested
  if (scale) {
    medians <- t(scale(t(medians)))
  }

  hm <- ComplexHeatmap::Heatmap(medians,
                                 name = "Expression",
                                 cluster_rows = TRUE,
                                 cluster_columns = TRUE,
                                 show_row_names = TRUE,
                                 show_column_names = TRUE)

  return(hm)
}

#' Plot pairwise comparisons between groups
#'
#' @param d_counts Cluster counts
#' @param group_factor Factor defining groups
#' @param clusters Clusters to plot
#' @return ggplot object
#' @export
plot_pairwise_comparison <- function(d_counts, group_factor, clusters = NULL) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  counts <- SummarizedExperiment::assay(d_counts)

  if (!is.null(clusters)) {
    counts <- counts[clusters, , drop = FALSE]
  }

  # Normalize to proportions
  props <- apply(counts, 2, function(x) x / sum(x))

  # Create data frame
  plot_df <- data.frame(
    cluster_id = rep(rownames(props), ncol(props)),
    sample_id = rep(colnames(props), each = nrow(props)),
    proportion = as.vector(props),
    group = rep(group_factor, each = nrow(props))
  )

  p <- ggplot2::ggplot(plot_df, ggplot2::aes(x = group, y = proportion, fill = group)) +
    ggplot2::geom_boxplot() +
    ggplot2::geom_jitter(width = 0.2, alpha = 0.5) +
    ggplot2::facet_wrap(~cluster_id, scales = "free_y") +
    ggplot2::labs(x = "Group", y = "Proportion") +
    ggplot2::theme_minimal() +
    ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
                   legend.position = "none")

  return(p)
}

#' Plot MA plot for differential abundance
#'
#' @param res Test results
#' @param p_threshold P-value threshold
#' @param title Plot title
#' @return ggplot object
#' @export
plot_ma <- function(res, p_threshold = 0.05, title = "MA Plot") {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  res_table <- SummarizedExperiment::rowData(res)

  # Get columns
  if ("logFC" %in% colnames(res_table) && "logCPM" %in% colnames(res_table)) {
    x_col <- "logCPM"
    y_col <- "logFC"
    p_col <- "p_adj"
  } else {
    stop("Could not identify required columns in results")
  }

  res_table$significant <- res_table[[p_col]] < p_threshold

  p <- ggplot2::ggplot(res_table, ggplot2::aes(x = .data[[x_col]], y = .data[[y_col]],
                                               color = .data[["significant"]])) +
    ggplot2::geom_point(alpha = 0.6) +
    ggplot2::scale_color_manual(values = c("TRUE" = "red", "FALSE" = "gray50")) +
    ggplot2::geom_hline(yintercept = 0, linetype = "dashed", color = "gray70") +
    ggplot2::labs(x = "Log Counts Per Million",
                  y = "Log Fold Change",
                  title = title,
                  color = "Significant") +
    ggplot2::theme_minimal()

  return(p)
}

#' Plot QC metrics
#'
#' @param d_se SummarizedExperiment object
#' @return List of ggplot objects
#' @export
plot_qc_metrics <- function(d_se) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  n_cells <- S4Vectors::metadata(d_se)$n_cells

  # Cells per sample
  p1 <- ggplot2::ggplot(data.frame(sample = names(n_cells), n_cells = n_cells),
                        ggplot2::aes(x = sample, y = n_cells)) +
    ggplot2::geom_bar(stat = "identity", fill = "steelblue") +
    ggplot2::labs(x = "Sample", y = "Number of Cells", title = "Cells per Sample") +
    ggplot2::theme_minimal() +
    ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1))

  # Return list of plots
  list(cells_per_sample = p1)
}

#' Create comprehensive diffcyt report plots
#'
#' @param d_se SummarizedExperiment object
#' @param res DA or DS results
#' @param analysis_type "DA" or "DS"
#' @param output_dir Directory to save plots
#' @export
save_diffcyt_plots <- function(d_se, res, analysis_type = "DA",
                               output_dir = "./diffcyt_plots") {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  message(sprintf("Saving plots to %s", output_dir))

  # Main heatmap (ComplexHeatmap object, use pdf device)
  p1 <- diffcyt::plotHeatmap(d_se, res, analysis_type = analysis_type)
  pdf(file.path(output_dir, "heatmap.pdf"), width = 10, height = 8)
  ComplexHeatmap::draw(p1)
  dev.off()

  # Volcano plot
  p2 <- plot_volcano(res)
  ggplot2::ggsave(file.path(output_dir, "volcano.pdf"), p2, width = 8, height = 6)

  if (analysis_type == "DA") {
    # MA plot
    p3 <- plot_ma(res)
    ggplot2::ggsave(file.path(output_dir, "ma_plot.pdf"), p3, width = 8, height = 6)
  }

  message("Plots saved successfully")
}
