#' Visualization Helper Functions for CARD
#'
#' Additional plotting functions that complement native CARD visualizations.
#' For core plots, use CARD::CARD.visualize.*() functions directly.
#'
#' @author Yang Guo
#' @date 2026-04-07

#' Plot Mean Cell Type Proportions
#'
#' Create barplot of average proportions across all spots
#'
#' @param CARD_obj CARD object
#' @param n_top Number of top cell types to show (NULL = all)
#' @return ggplot object
#' @export
plot_mean_proportions <- function(CARD_obj, n_top = NULL) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  props <- CARD_obj@Proportion_CARD
  mean_props <- sort(colMeans(props), decreasing = TRUE)

  if (!is.null(n_top)) {
    mean_props <- mean_props[1:min(n_top, length(mean_props))]
  }

  plot_data <- data.frame(
    cell_type = factor(names(mean_props), levels = rev(names(mean_props))),
    proportion = mean_props
  )

  ggplot2::ggplot(plot_data, ggplot2::aes(x = proportion, y = cell_type)) +
    ggplot2::geom_bar(stat = "identity", fill = "steelblue") +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      x = "Mean Proportion",
      y = "Cell Type",
      title = "Average Cell Type Proportions"
    )
}

#' Plot Dominant Cell Type Distribution
#'
#' Show how many spots have each cell type as dominant
#'
#' @param CARD_obj CARD object
#' @return ggplot object
#' @export
plot_dominant_distribution <- function(CARD_obj) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  props <- CARD_obj@Proportion_CARD
  dominant <- colnames(props)[apply(props, 1, which.max)]
  dom_table <- sort(table(dominant), decreasing = TRUE)

  plot_data <- data.frame(
    cell_type = factor(names(dom_table), levels = rev(names(dom_table))),
    n_spots = as.numeric(dom_table)
  )

  ggplot2::ggplot(plot_data, ggplot2::aes(x = n_spots, y = cell_type)) +
    ggplot2::geom_bar(stat = "identity", fill = "darkgreen") +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      x = "Number of Spots",
      y = "Cell Type",
      title = "Dominant Cell Type per Spot"
    )
}

#' Plot Spatial Entropy
#'
#' Visualize cell type diversity (entropy) across spatial locations
#'
#' @param CARD_obj CARD object
#' @param colors Color gradient vector
#' @return ggplot object
#' @export
plot_spatial_entropy <- function(
    CARD_obj,
    colors = c("lightyellow", "orange", "red")
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  props <- CARD_obj@Proportion_CARD
  coords <- CARD_obj@spatial_location

  # Calculate entropy
  entropy <- apply(props, 1, function(x) {
    p <- x[x > 0]
    -sum(p * log(p))
  })

  plot_data <- data.frame(
    x = coords$x,
    y = coords$y,
    entropy = entropy
  )

  ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = entropy)) +
    ggplot2::geom_point(size = 2) +
    ggplot2::scale_color_gradientn(
      colors = colors,
      name = "Entropy"
    ) +
    ggplot2::coord_fixed() +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      title = "Cell Type Diversity (Entropy)",
      x = "X",
      y = "Y"
    )
}

#' Plot Cell Type Proportion Boxplot
#'
#' Boxplot of proportions for each cell type
#'
#' @param CARD_obj CARD object
#' @param cell_types Cell types to include (NULL = all)
#' @return ggplot object
#' @export
plot_proportion_boxplot <- function(CARD_obj, cell_types = NULL) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  props <- CARD_obj@Proportion_CARD

  if (!is.null(cell_types)) {
    props <- props[, cell_types, drop = FALSE]
  }

  plot_data <- stack(as.data.frame(props))
  colnames(plot_data) <- c("proportion", "cell_type")

  ggplot2::ggplot(plot_data, ggplot2::aes(x = cell_type, y = proportion)) +
    ggplot2::geom_boxplot(fill = "lightblue") +
    ggplot2::theme_minimal() +
    ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1)) +
    ggplot2::labs(
      x = "Cell Type",
      y = "Proportion",
      title = "Cell Type Proportion Distribution"
    )
}

#' Create Comprehensive Summary Plot
#'
#' Multi-panel summary of CARD results
#'
#' @param CARD_obj CARD object
#' @param output_file Optional file path to save plot
#' @return List of ggplot objects
#' @export
plot_card_summary <- function(CARD_obj, output_file = NULL) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Create individual plots
  p1 <- plot_mean_proportions(CARD_obj)
  p2 <- plot_dominant_distribution(CARD_obj)
  p3 <- plot_spatial_entropy(CARD_obj)

  plots <- list(mean_props = p1, dominant = p2, entropy = p3)

  # Save if requested
  if (!is.null(output_file)) {
    if (requireNamespace("cowplot", quietly = TRUE)) {
      combined <- cowplot::plot_grid(p1, p2, p3, ncol = 1)
      ggplot2::ggsave(output_file, combined, width = 8, height = 12)
    } else {
      warning("cowplot not available, cannot save combined plot")
    }
  }

  invisible(plots)
}
