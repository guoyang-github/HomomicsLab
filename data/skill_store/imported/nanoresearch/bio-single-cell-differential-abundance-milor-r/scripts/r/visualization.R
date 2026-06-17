# Visualization Functions for miloR
# =================================
#
# Plotting functions for differential abundance analysis results

library(ggplot2)
library(miloR)

#' Plot DA results as beeswarm plot
#'
#' @param da.res DA results from testNhoods
#' @param group.by Column to group by (default: NULL)
#' @param alpha FDR threshold for significance (default: 0.1)
#' @param show.signif Show significance threshold line (default: TRUE)
#' @return ggplot object
#' @export
plot_milo_beeswarm <- function(da.res, group.by = NULL, alpha = 0.1,
                               show.signif = TRUE) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 is required for plotting")
  }

  p <- plotDAbeeswarm(da.res, group.by = group.by, alpha = alpha)

  if (show.signif) {
    p <- p + geom_hline(yintercept = c(-log10(alpha)), linetype = "dashed",
                        color = "red", alpha = 0.5)
  }

  return(p)
}

#' Plot neighborhood graph with DA coloring
#'
#' @param x Milo object
#' @param da.res DA results from testNhoods
#' @param alpha FDR threshold (default: 0.1)
#' @param layout Layout matrix (optional, uses UMAP if available)
#' @param size Point size (default: 1)
#' @return ggplot object
#' @export
plot_milo_graph_da <- function(x, da.res, alpha = 0.1, layout = NULL,
                               size = 1) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  p <- plotNhoodGraphDA(x, da.res = da.res, alpha = alpha, layout = layout,
                        size = size)
  return(p)
}

#' Plot neighborhood graph (structure only)
#'
#' @param x Milo object
#' @param layout Layout matrix (optional)
#' @param colour_by Column to color by (optional)
#' @param size Point size (default: 1)
#' @return ggplot object
#' @export
plot_milo_graph <- function(x, layout = NULL, colour_by = NULL, size = 1) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  p <- plotNhoodGraph(x, layout = layout, colour_by = colour_by, size = size)
  return(p)
}

#' Plot DA results on reduced dimension embedding
#'
#' @param x Milo object
#' @param da.res DA results from testNhoods
#' @param dimred Name of reduced dimension (default: "UMAP")
#' @param alpha FDR threshold (default: 0.1)
#' @param point.size Point size (default: 0.5)
#' @return ggplot object
#' @export
plot_milo_umap_da <- function(x, da.res, dimred = "UMAP", alpha = 0.1,
                              point.size = 0.5) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  # Merge DA results with cell-level data
  nhood_summary <- data.frame(
    Nhood = seq_len(nrow(da.res)),
    logFC = da.res$logFC,
    FDR = da.res$SpatialFDR,
    Significant = da.res$SpatialFDR < alpha
  )

  # Get cell coordinates
  if (!dimred %in% reducedDimNames(x)) {
    stop(sprintf("Reduced dimension '%s' not found", dimred))
  }

  coords <- as.data.frame(reducedDim(x, dimred))
  colnames(coords) <- c("Dim1", "Dim2")

  # Assign cells to neighborhoods
  nhoods_mat <- nhoods(x)
  cell_da <- data.frame(
    cell_id = colnames(x),
    logFC = NA,
    FDR = NA,
    Significant = FALSE
  )

  for (i in seq_len(ncol(nhoods_mat))) {
    cells_in_nhood <- which(nhoods_mat[, i] > 0)
    if (length(cells_in_nhood) > 0) {
      cell_da$logFC[cells_in_nhood] <- nhood_summary$logFC[i]
      cell_da$FDR[cells_in_nhood] <- nhood_summary$FDR[i]
      cell_da$Significant[cells_in_nhood] <- nhood_summary$Significant[i]
    }
  }

  plot_data <- cbind(coords, cell_da)

  p <- ggplot(plot_data, aes(x = Dim1, y = Dim2, color = logFC)) +
    geom_point(size = point.size, alpha = 0.6) +
    scale_color_gradient2(low = "blue", mid = "grey", high = "red",
                          midpoint = 0, na.value = "grey50") +
    theme_bw() +
    labs(title = "DA logFC on UMAP",
         subtitle = sprintf("Significant neighborhoods (FDR < %.2f) colored", alpha),
         color = "logFC") +
    theme(legend.position = "right")

  return(p)
}

#' Volcano plot for DA results
#'
#' @param da.res DA results from testNhoods
#' @param alpha FDR threshold (default: 0.1)
#' @param logfc.threshold LogFC threshold for labeling (default: 1)
#' @param highlight.nhoods Specific neighborhoods to highlight (optional)
#' @return ggplot object
#' @export
plot_milo_volcano <- function(da.res, alpha = 0.1, logfc.threshold = 1,
                              highlight.nhoods = NULL) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 is required for plotting")
  }

  plot_data <- data.frame(
    logFC = da.res$logFC,
    negLogP = -log10(da.res$PValue),
    FDR = da.res$SpatialFDR,
    Nhood = seq_len(nrow(da.res)),
    Significant = da.res$SpatialFDR < alpha
  )

  p <- ggplot(plot_data, aes(x = logFC, y = negLogP, color = Significant)) +
    geom_point(alpha = 0.6, size = 1) +
    scale_color_manual(values = c("grey70", "red"),
                       labels = c("Not Significant", "Significant")) +
    geom_hline(yintercept = -log10(0.05), linetype = "dashed", alpha = 0.5) +
    theme_bw() +
    labs(x = "log2 Fold Change",
         y = "-log10 P-value",
         title = "DA Volcano Plot",
         subtitle = sprintf("FDR < %.2f considered significant", alpha)) +
    theme(legend.position = "bottom")

  # Highlight specific neighborhoods if requested
  if (!is.null(highlight.nhoods)) {
    highlight_data <- plot_data[plot_data$Nhood %in% highlight.nhoods, ]
    p <- p + geom_point(data = highlight_data, color = "blue", size = 2) +
      geom_text(data = highlight_data, aes(label = Nhood),
                hjust = -0.2, vjust = 0.5, size = 3, color = "blue")
  }

  return(p)
}

#' Plot cell counts per neighborhood
#'
#' @param x Milo object
#' @param n.top Number of top neighborhoods to show (default: 50)
#' @return ggplot object
#' @export
plot_milo_counts <- function(x, n.top = 50) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  counts <- nhoodCounts(x)
  count_sums <- rowSums(counts)

  plot_data <- data.frame(
    Nhood = seq_len(length(count_sums)),
    Count = count_sums
  )

  # Select top neighborhoods by count
  plot_data <- plot_data[order(plot_data$Count, decreasing = TRUE), ]
  plot_data <- head(plot_data, n.top)
  plot_data$Nhood <- factor(plot_data$Nhood, levels = plot_data$Nhood)

  p <- ggplot(plot_data, aes(x = Nhood, y = Count)) +
    geom_bar(stat = "identity", fill = "steelblue") +
    theme_bw() +
    theme(axis.text.x = element_text(angle = 90, hjust = 1, size = 6)) +
    labs(title = "Cell Counts per Neighborhood",
         subtitle = sprintf("Top %d neighborhoods shown", n.top),
         x = "Neighborhood",
         y = "Total Cell Count")

  return(p)
}

#' Plot neighborhood size distribution
#'
#' @param x Milo object
#' @return ggplot object
#' @export
plot_milo_size_distribution <- function(x) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  nhoods_mat <- nhoods(x)
  sizes <- colSums(nhoods_mat > 0)

  plot_data <- data.frame(Size = sizes)

  p <- ggplot(plot_data, aes(x = Size)) +
    geom_histogram(bins = 50, fill = "steelblue", color = "white") +
    geom_vline(xintercept = median(sizes), color = "red", linetype = "dashed") +
    theme_bw() +
    labs(title = "Neighborhood Size Distribution",
         subtitle = sprintf("Median size: %.0f cells", median(sizes)),
         x = "Neighborhood Size (cells)",
         y = "Count")

  return(p)
}

#' Plot sample counts per neighborhood
#'
#' @param x Milo object
#' @param n.top Number of neighborhoods to show (default: 30)
#' @return ggplot object
#' @export
plot_milo_sample_counts <- function(x, n.top = 30) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  counts <- nhoodCounts(x)
  n_samples_per_nhood <- rowSums(counts > 0)

  plot_data <- data.frame(
    Nhood = seq_len(length(n_samples_per_nhood)),
    NSamples = n_samples_per_nhood
  )

  plot_data <- plot_data[order(plot_data$NSamples, decreasing = TRUE), ]
  plot_data <- head(plot_data, n.top)
  plot_data$Nhood <- factor(plot_data$Nhood, levels = plot_data$Nhood)

  p <- ggplot(plot_data, aes(x = Nhood, y = NSamples)) +
    geom_bar(stat = "identity", fill = "darkgreen") +
    theme_bw() +
    theme(axis.text.x = element_text(angle = 90, hjust = 1, size = 6)) +
    labs(title = "Number of Samples per Neighborhood",
         subtitle = sprintf("Top %d neighborhoods shown", n.top),
         x = "Neighborhood",
         y = "Number of Samples")

  return(p)
}

#' Create multi-panel DA summary plot
#'
#' @param x Milo object
#' @param da.res DA results from testNhoods
#' @param dimred Name of reduced dimension for embedding (default: "UMAP")
#' @param alpha FDR threshold (default: 0.1)
#' @param group.by Column for grouping beeswarm (optional)
#' @return List of ggplot objects
#' @export
plot_milo_summary <- function(x, da.res, dimred = "UMAP", alpha = 0.1,
                              group.by = NULL) {
  if (!is(x, "Milo")) {
    stop("Input must be Milo object")
  }

  plots <- list()

  # Volcano plot
  plots$volcano <- plot_milo_volcano(da.res, alpha = alpha)

  # Beeswarm plot
  plots$beeswarm <- plot_milo_beeswarm(da.res, group.by = group.by, alpha = alpha)

  # UMAP plot (if available)
  if (dimred %in% reducedDimNames(x)) {
    plots$umap <- plot_milo_umap_da(x, da.res, dimred = dimred, alpha = alpha)
  }

  # Neighborhood graph (if computable)
  tryCatch({
    plots$graph <- plot_milo_graph_da(x, da.res, alpha = alpha)
  }, error = function(e) {
    message("Could not create neighborhood graph plot: ", e$message)
  })

  # Size distribution
  plots$size_dist <- plot_milo_size_distribution(x)

  return(plots)
}

#' Save multiple miloR plots
#'
#' @param plots List of ggplot objects
#' @param output_dir Output directory (default: "./milo_plots")
#' @param width Plot width (default: 8)
#' @param height Plot height (default: 6)
#' @param dpi Resolution (default: 300)
#' @export
save_milo_plots <- function(plots, output_dir = "./milo_plots",
                            width = 8, height = 6, dpi = 300) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  for (name in names(plots)) {
    if (!is.null(plots[[name]])) {
      file_path <- file.path(output_dir, paste0(name, ".pdf"))
      ggsave(file_path, plots[[name]], width = width, height = height)
      message("Saved: ", file_path)
    }
  }
}

#' Plot marker gene heatmap for neighborhood groups
#'
#' @param marker.df Marker results from findNhoodMarkers
#' @param n.markers Number of top markers per group (default: 10)
#' @param group.cols Column pattern for groups (default: "logFC_")
#' @return ComplexHeatmap object
#' @export
plot_milo_marker_heatmap <- function(marker.df, n.markers = 10,
                                     group.cols = "logFC_") {
  if (!requireNamespace("ComplexHeatmap", quietly = TRUE)) {
    stop("ComplexHeatmap is required for this plot")
  }

  # Extract logFC columns for each group
  logfc_cols <- grep(group.cols, colnames(marker.df), value = TRUE)
  group_names <- gsub(group.cols, "", logfc_cols)

  # Get top markers per group
  top_markers <- list()
  for (i in seq_along(logfc_cols)) {
    col <- logfc_cols[i]
    marker.df$absFC <- abs(marker.df[[col]])
    top <- head(marker.df[order(marker.df$absFC, decreasing = TRUE), "GeneID"],
                n.markers)
    top_markers[[group_names[i]]] <- top
  }

  all_markers <- unique(unlist(top_markers))

  # Create matrix for heatmap
  mat <- as.matrix(marker.df[marker.df$GeneID %in% all_markers, logfc_cols])
  rownames(mat) <- marker.df$GeneID[marker.df$GeneID %in% all_markers]
  colnames(mat) <- group_names

  # Create heatmap
  ht <- ComplexHeatmap::Heatmap(mat,
                                name = "logFC",
                                col = colorRamp2(c(-2, 0, 2), c("blue", "white", "red")),
                                cluster_rows = TRUE,
                                cluster_columns = TRUE,
                                show_row_names = TRUE,
                                row_names_gp = grid::gpar(fontsize = 6),
                                column_title = "Neighborhood Groups")

  return(ht)
}

#' Plot DA neighborhood groups
#'
#' @param x Milo object
#' @param da.res DA results with NhoodGroup column
#' @param alpha FDR threshold (default: 0.1)
#' @return ggplot object
#' @export
plot_milo_groups <- function(x, da.res, alpha = 0.1) {
  if (!"NhoodGroup" %in% colnames(da.res)) {
    stop("da.res must contain NhoodGroup column. Run groupNhoods first.")
  }

  p <- ggplot(da.res, aes(x = NhoodGroup, y = logFC, color = SpatialFDR < alpha)) +
    geom_jitter(width = 0.2, alpha = 0.6) +
    scale_color_manual(values = c("grey70", "red"),
                       labels = c("Not Significant", "Significant")) +
    theme_bw() +
    labs(x = "Neighborhood Group",
         y = "logFC",
         color = "Significant",
         title = "DA by Neighborhood Group") +
    theme(axis.text.x = element_text(angle = 45, hjust = 1))

  return(p)
}
