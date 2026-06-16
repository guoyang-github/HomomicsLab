# chromVAR Visualization Functions
# =================================
#
# Plotting and visualization functions for chromVAR analysis results

#' Plot motif variability
#'
#' Create a variability plot showing the most variable motifs
#'
#' @param var Variability data frame from compute_variability_chromvar
#' @param n_label Number of top motifs to label (default: 5)
#' @param use_plotly Use interactive plotly (default: FALSE)
#' @param title Plot title (optional)
#' @return ggplot or plotly object
#' @export
plot_variability_chromvar <- function(var,
                                      n_label = 5,
                                      use_plotly = FALSE,
                                      title = "Motif Variability") {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  # Create the plot
  p <- chromVAR::plotVariability(var, use_plotly = use_plotly, n = n_label)

  # Add title if not using plotly
  if (!use_plotly && !is.null(title)) {
    p <- p + ggplot2::ggtitle(title)
  }

  return(p)
}

#' Plot deviations heatmap
#'
#' Create a heatmap of deviation scores for top variable motifs
#'
#' @param dev chromVARDeviations object
#' @param var Variability data frame (optional, computed if NULL)
#' @param n_motifs Number of motifs to include (default: 20)
#' @param annotation_col Data frame for column annotation (optional)
#' @param show_cell_names Whether to show cell names (default: FALSE)
#' @param output_file Output file path (optional)
#' @return Heatmap object (invisible)
#' @export
plot_deviation_heatmap <- function(dev,
                                   var = NULL,
                                   n_motifs = 20,
                                   annotation_col = NULL,
                                   show_cell_names = FALSE,
                                   output_file = NULL) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }
  if (!requireNamespace("pheatmap", quietly = TRUE)) {
    stop("pheatmap package required. Install with: install.packages('pheatmap')")
  }

  # Compute variability if not provided
  if (is.null(var)) {
    var <- chromVAR::computeVariability(dev)
  }

  # Get top variable motifs
  top_motifs <- var$name[order(var$variability, decreasing = TRUE)][seq_len(min(n_motifs, nrow(var)))]

  # Get z-scores
  z_scores <- chromVAR::deviationScores(dev)

  # Match motif names
  motif_names <- if (!is.null(SummarizedExperiment::rowData(dev)$name)) {
    SummarizedExperiment::rowData(dev)$name
  } else {
    rownames(dev)
  }

  motif_idx <- match(top_motifs, motif_names)
  motif_idx <- motif_idx[!is.na(motif_idx)]

  if (length(motif_idx) == 0) {
    stop("No matching motifs found")
  }

  # Subset matrix
  plot_mat <- z_scores[motif_idx, ]
  rownames(plot_mat) <- motif_names[motif_idx]

  # Limit cells for visualization
  if (ncol(plot_mat) > 100 && !show_cell_names) {
    message(sprintf("Subsampling to 100 cells for visualization (from %d)", ncol(plot_mat)))
    set.seed(42)
    sample_idx <- sample(ncol(plot_mat), 100)
    plot_mat <- plot_mat[, sample_idx]
    if (!is.null(annotation_col)) {
      annotation_col <- annotation_col[sample_idx, , drop = FALSE]
    }
  }

  # Create heatmap
  hm <- pheatmap::pheatmap(
    plot_mat,
    scale = "none",
    cluster_rows = TRUE,
    cluster_cols = TRUE,
    annotation_col = annotation_col,
    show_colnames = show_cell_names,
    main = paste("Top", length(motif_idx), "Variable Motifs"),
    color = colorRampPalette(c("blue", "white", "red"))(100),
    breaks = seq(-3, 3, length.out = 101),
    filename = output_file
  )

  return(invisible(hm))
}

#' Plot deviation scores for specific motifs
#'
#' Create violin/box plots of deviation scores grouped by cell metadata
#'
#' @param dev chromVARDeviations object
#' @param motif_names Character vector of motif names to plot
#' @param group_by Vector of group labels for cells
#' @param plot_type Type of plot: "violin" or "box" (default: "violin")
#' @param ncol Number of columns for faceting (default: 3)
#' @return ggplot object
#' @export
plot_motif_deviations <- function(dev,
                                  motif_names,
                                  group_by,
                                  plot_type = "violin",
                                  ncol = 3) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }
  if (!requireNamespace("reshape2", quietly = TRUE)) {
    stop("reshape2 package required. Install with: install.packages('reshape2')")
  }

  # Get z-scores
  z_scores <- chromVAR::deviationScores(dev)

  # Match motif names
  available_names <- if (!is.null(SummarizedExperiment::rowData(dev)$name)) {
    SummarizedExperiment::rowData(dev)$name
  } else {
    rownames(dev)
  }

  motif_idx <- match(motif_names, available_names)
  names(motif_idx) <- motif_names
  motif_idx <- motif_idx[!is.na(motif_idx)]

  if (length(motif_idx) == 0) {
    stop("No matching motifs found")
  }

  # Prepare data
  plot_data <- as.data.frame(t(z_scores[motif_idx, , drop = FALSE]))
  colnames(plot_data) <- names(motif_idx)
  plot_data$group <- group_by

  # Melt for ggplot
  plot_data_melt <- reshape2::melt(plot_data, id.vars = "group",
                                    variable.name = "motif",
                                    value.name = "z_score")

  # Create plot
  if (plot_type == "violin") {
    p <- ggplot2::ggplot(plot_data_melt, ggplot2::aes(x = group, y = z_score, fill = group)) +
      ggplot2::geom_violin(trim = FALSE, alpha = 0.7) +
      ggplot2::geom_boxplot(width = 0.1, outlier.shape = NA) +
      ggplot2::facet_wrap(~motif, ncol = ncol, scales = "free_y")
  } else {
    p <- ggplot2::ggplot(plot_data_melt, ggplot2::aes(x = group, y = z_score, fill = group)) +
      ggplot2::geom_boxplot(outlier.shape = NA) +
      ggplot2::facet_wrap(~motif, ncol = ncol, scales = "free_y")
  }

  p <- p +
    ggplot2::theme_minimal() +
    ggplot2::labs(x = "Group", y = "Deviation Z-score") +
    ggplot2::theme(
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
      legend.position = "none"
    )

  return(p)
}

#' Plot motif deviations on dimensionality reduction
#'
#' Visualize motif activity on UMAP/tSNE coordinates
#'
#' @param dev chromVARDeviations object
#' @param dimred Data frame with dimensionality reduction coordinates (x, y columns)
#' @param motif_names Character vector of motif names to plot
#' @param point_size Point size (default: 1)
#' @param alpha Point alpha (default: 0.6)
#' @return List of ggplot objects
#' @export
plot_deviations_dimred <- function(dev,
                                   dimred,
                                   motif_names,
                                   point_size = 1,
                                   alpha = 0.6) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }
  if (!requireNamespace("cowplot", quietly = TRUE)) {
    stop("cowplot package required. Install with: install.packages('cowplot')")
  }

  # Get z-scores
  z_scores <- chromVAR::deviationScores(dev)

  # Match motif names
  available_names <- if (!is.null(SummarizedExperiment::rowData(dev)$name)) {
    SummarizedExperiment::rowData(dev)$name
  } else {
    rownames(dev)
  }

  motif_idx <- match(motif_names, available_names)
  names(motif_idx) <- motif_names
  motif_idx <- motif_idx[!is.na(motif_idx)]

  if (length(motif_idx) == 0) {
    stop("No matching motifs found")
  }

  # Check dimred
  if (!all(c("x", "y") %in% colnames(dimred))) {
    stop("dimred must have 'x' and 'y' columns")
  }

  # Create plots
  plots <- list()
  for (motif in names(motif_idx)) {
    idx <- motif_idx[motif]
    plot_data <- data.frame(
      x = dimred$x,
      y = dimred$y,
      score = z_scores[idx, ]
    )

    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = score)) +
      ggplot2::geom_point(size = point_size, alpha = alpha) +
      ggplot2::scale_color_gradient2(
        low = "blue",
        mid = "lightgray",
        high = "red",
        midpoint = 0,
        name = "Z-score"
      ) +
      ggplot2::theme_minimal() +
      ggplot2::labs(title = motif, x = "Dimension 1", y = "Dimension 2") +
      ggplot2::theme(
        plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"),
        axis.text = ggplot2::element_blank(),
        axis.ticks = ggplot2::element_blank()
      )

    plots[[motif]] <- p
  }

  # Combine plots if multiple
  if (length(plots) > 1) {
    combined <- cowplot::plot_grid(plotlist = plots, ncol = ceiling(sqrt(length(plots))))
    return(combined)
  }

  return(plots[[1]])
}

#' Plot GC bias distribution
#'
#' Visualize the GC content distribution across peaks
#'
#' @param rse RangedSummarizedExperiment with GC bias added
#' @param bins Number of histogram bins (default: 50)
#' @return ggplot object
#' @export
plot_gc_bias <- function(rse, bins = 50) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  gc <- SummarizedExperiment::rowData(rse)$bias
  if (is.null(gc)) {
    stop("GC bias not found. Run add_gc_bias() first.")
  }

  plot_data <- data.frame(gc_content = gc)

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = gc_content)) +
    ggplot2::geom_histogram(bins = bins, fill = "steelblue", color = "white", alpha = 0.7) +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      title = "GC Content Distribution",
      x = "GC Content",
      y = "Number of Peaks"
    ) +
    ggplot2::geom_vline(
      xintercept = mean(gc, na.rm = TRUE),
      color = "red",
      linetype = "dashed",
      size = 1
    )

  return(p)
}

#' Plot peak accessibility distribution
#'
#' Visualize the distribution of fragments per peak
#'
#' @param rse RangedSummarizedExperiment
#' @param log_scale Use log scale for y-axis (default: TRUE)
#' @return ggplot object
#' @export
plot_peak_accessibility <- function(rse, log_scale = TRUE) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("Matrix", quietly = TRUE)) {
    stop("Matrix package required")
  }

  counts <- SummarizedExperiment::assay(rse, "counts")
  fragments_per_peak <- Matrix::rowSums(counts)

  plot_data <- data.frame(
    peak_id = seq_along(fragments_per_peak),
    fragments = fragments_per_peak
  )

  # Sort by fragment count
  plot_data <- plot_data[order(plot_data$fragments, decreasing = TRUE), ]
  plot_data$rank <- seq_len(nrow(plot_data))

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = rank, y = fragments)) +
    ggplot2::geom_line(color = "steelblue", size = 0.5) +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      title = "Peak Accessibility Distribution",
      x = "Peak Rank",
      y = "Total Fragments"
    )

  if (log_scale) {
    p <- p + ggplot2::scale_y_log10()
  }

  return(p)
}

#' Plot sample depth distribution
#'
#' Visualize the distribution of reads per cell
#'
#' @param rse RangedSummarizedExperiment
#' @param bins Number of histogram bins (default: 50)
#' @return ggplot object
#' @export
plot_sample_depth <- function(rse, bins = 50) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("Matrix", quietly = TRUE)) {
    stop("Matrix package required")
  }

  counts <- SummarizedExperiment::assay(rse, "counts")
  depth <- Matrix::colSums(counts)

  plot_data <- data.frame(depth = depth)

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = depth)) +
    ggplot2::geom_histogram(bins = bins, fill = "steelblue", color = "white", alpha = 0.7) +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      title = "Read Depth Distribution",
      x = "Fragments per Cell",
      y = "Number of Cells"
    ) +
    ggplot2::scale_x_log10() +
    ggplot2::geom_vline(
      xintercept = median(depth),
      color = "red",
      linetype = "dashed",
      size = 1
    )

  return(p)
}

#' Create comprehensive chromVAR visualization report
#'
#' Generate multiple plots for chromVAR results
#'
#' @param results Results list from run_chromvar
#' @param dimred Data frame with dimensionality reduction coordinates (optional)
#' @param group_by Vector of group labels for cells (optional)
#' @param output_dir Output directory for plots
#' @param prefix File prefix
#' @return Invisible NULL
#' @export
create_chromvar_plots <- function(results,
                                  dimred = NULL,
                                  group_by = NULL,
                                  output_dir = "./chromvar_plots",
                                  prefix = "sample") {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Plot 1: Variability plot
  message("Creating variability plot...")
  p1 <- plot_variability_chromvar(results$variability, n_label = 10)
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_variability.pdf")),
    p1,
    width = 10,
    height = 6
  )

  # Plot 2: Heatmap
  message("Creating deviation heatmap...")
  pdf(file.path(output_dir, paste0(prefix, "_heatmap.pdf")), width = 10, height = 8)
  plot_deviation_heatmap(
    results$deviations,
    var = results$variability,
    n_motifs = 20
  )
  dev.off()

  # Plot 3: Top motifs by group (if group_by provided)
  if (!is.null(group_by)) {
    message("Creating group comparison plots...")
    top_motifs <- results$variability$name[
      order(results$variability$variability, decreasing = TRUE)
    ][1:min(6, nrow(results$variability))]

    p3 <- plot_motif_deviations(
      results$deviations,
      motif_names = top_motifs,
      group_by = group_by,
      plot_type = "violin"
    )
    ggplot2::ggsave(
      file.path(output_dir, paste0(prefix, "_group_comparison.pdf")),
      p3,
      width = 12,
      height = 8
    )
  }

  # Plot 4: Dimred plots (if provided)
  if (!is.null(dimred)) {
    message("Creating dimensionality reduction plots...")
    top_motifs <- results$variability$name[
      order(results$variability$variability, decreasing = TRUE)
    ][1:min(4, nrow(results$variability))]

    p4 <- plot_deviations_dimred(
      results$deviations,
      dimred = dimred,
      motif_names = top_motifs
    )
    ggplot2::ggsave(
      file.path(output_dir, paste0(prefix, "_dimred.pdf")),
      p4,
      width = 10,
      height = 10
    )
  }

  message(sprintf("Plots saved to %s", output_dir))
  return(invisible(NULL))
}
