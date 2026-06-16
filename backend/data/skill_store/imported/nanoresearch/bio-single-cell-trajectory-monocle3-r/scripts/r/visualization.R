#' Visualization Functions for Monocle3 Trajectory Analysis
#'
#' Plots that add validation logic or combine multiple plot_cells() calls.
#' For basic plotting, use monocle3::plot_cells() directly.
#'
#' Author: Yang Guo
#' Date: 2026-05-21

#==============================================================================
# 3D and Multi-Panel Plots
#==============================================================================

#' Plot 3D Trajectory
#'
#' Validates that 3D reduction exists before calling plot_cells_3d().
#'
#' @param cds A cell_data_set object with 3D reduction
#' @param color_cells_by Column to color cells by (default: "partition")
#' @param ... Additional arguments to plot_cells_3d()
#' @return plotly object
#' @export
plot_trajectory_3d <- function(cds,
                               color_cells_by = "partition",
                               ...) {
  if (is.null(SingleCellExperiment::reducedDims(cds)[['UMAP']]) || ncol(SingleCellExperiment::reducedDims(cds)[['UMAP']]) < 3) {
    stop("3D reduction not found. Run reduce_dimension(cds, max_components = 3) first.")
  }

  plot_cells_3d(
    cds,
    color_cells_by = color_cells_by,
    ...
  )
}

#' Plot Multiple Trajectory Features
#'
#' Creates a list of ggplot objects, one per feature, each showing cells
#' colored by the feature with the trajectory graph overlaid.
#'
#' @param cds A cell_data_set object
#' @param features Vector of colData column names to plot
#' @param ncol Number of columns (affects layout if combined with patchwork/cowplot)
#' @return Named list of ggplot objects
#' @export
plot_trajectory_features <- function(cds, features, ncol = 2) {
  plots <- list()

  for (feature in features) {
    p <- plot_cells(
      cds,
      color_cells_by = feature,
      label_cell_groups = FALSE,
      show_trajectory_graph = TRUE,
      cell_size = 0.5
    ) +
      ggplot2::ggtitle(feature)

    plots[[feature]] <- p
  }

  return(plots)
}

#==============================================================================
# Custom ggplot Visualizations
#==============================================================================

#' Plot Pseudotime Histogram
#'
#' Custom ggplot histogram of pseudotime values, optionally grouped by metadata.
#'
#' @param cds A cell_data_set object with pseudotime
#' @param group_by colData column to group by (optional)
#' @param bins Number of bins (default: 30)
#' @return ggplot object
#' @export
plot_pseudotime_distribution <- function(cds,
                                         group_by = NULL,
                                         bins = 30) {
  if (is.null(pseudotime(cds))) {
    stop("No pseudotime found. Run order_cells() first.")
  }

  df <- data.frame(
    pseudotime = pseudotime(cds)
  )

  if (!is.null(group_by)) {
    df$group <- colData(cds)[[group_by]]

    p <- ggplot2::ggplot(df, ggplot2::aes(x = pseudotime, fill = group)) +
      ggplot2::geom_histogram(bins = bins, alpha = 0.7, position = "identity")
  } else {
    p <- ggplot2::ggplot(df, ggplot2::aes(x = pseudotime)) +
      ggplot2::geom_histogram(bins = bins, fill = "steelblue", alpha = 0.7)
  }

  p +
    ggplot2::theme_minimal() +
    ggplot2::labs(x = "Pseudotime", y = "Count")
}
