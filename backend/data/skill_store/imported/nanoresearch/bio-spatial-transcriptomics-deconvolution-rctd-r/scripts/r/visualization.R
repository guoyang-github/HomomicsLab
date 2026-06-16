#' RCTD Visualization Functions
#'
#' Spatial visualization and plotting functions for RCTD results.
#'
#' @author Yang Guo
#' @date 2026-04-07
#' @version 2.0.0

#' Plot Cell Type Proportions on Spatial Coordinates
#'
#' Creates spatial heatmaps of cell type proportions for selected cell types.
#'
#' @param rctd_results RCTD object
#' @param cell_types Character vector: cell types to plot (NULL = all)
#' @param spatial_coords DataFrame with x, y coordinates (optional, extracted from RCTD if available)
#' @param layout Plot layout: 'grid' or 'individual' (default: 'grid')
#' @param ncol Number of columns for grid layout (default: 3)
#' @param point_size Size of points (default: 1)
#' @param colors Color palette (default: viridis)
#'
#' @return ggplot object or list of plots
#' @export
plot_rctd_proportions <- function(
    rctd_results,
    cell_types = NULL,
    spatial_coords = NULL,
    layout = 'grid',
    ncol = 3,
    point_size = 1,
    colors = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results)

  # Get cell types to plot
  if (is.null(cell_types)) {
    cell_types <- colnames(props)
  } else {
    # Check if requested cell types exist
    missing <- setdiff(cell_types, colnames(props))
    if (length(missing) > 0) {
      warning(sprintf("Cell types not found: %s", paste(missing, collapse = ", ")))
      cell_types <- intersect(cell_types, colnames(props))
    }
  }

  if (length(cell_types) == 0) {
    stop("No valid cell types to plot")
  }

  # Get coordinates
  if (is.null(spatial_coords)) {
    if (nrow(rctd_results@spatialRNA@coords) > 0) {
      coords <- rctd_results@spatialRNA@coords
    } else {
      # Create fake grid coordinates
      n_spots <- nrow(props)
      grid_dim <- ceiling(sqrt(n_spots))
      coords <- data.frame(
        x = rep(1:grid_dim, length.out = n_spots),
        y = rep(1:grid_dim, each = grid_dim)[1:n_spots]
      )
      rownames(coords) <- rownames(props)
    }
  } else {
    coords <- spatial_coords
  }

  # Ensure coordinates match proportions
  common_spots <- intersect(rownames(props), rownames(coords))
  if (length(common_spots) == 0) {
    stop("No matching spot IDs between proportions and coordinates")
  }

  props <- props[common_spots, , drop = FALSE]
  coords <- coords[common_spots, , drop = FALSE]

  # Create plots
  plot_list <- lapply(cell_types, function(ct) {
    plot_data <- data.frame(
      x = coords$x,
      y = coords$y,
      proportion = props[[ct]]
    )

    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = proportion)) +
      ggplot2::geom_point(size = point_size) +
      ggplot2::scale_color_viridis_c(name = 'Proportion', option = 'plasma') +
      ggplot2::labs(
        title = ct,
        x = 'X coordinate',
        y = 'Y coordinate'
      ) +
      ggplot2::theme_minimal() +
      ggplot2::coord_fixed()

    return(p)
  })

  names(plot_list) <- cell_types

  # Return layout
  if (layout == 'grid' && length(plot_list) > 1) {
    if (requireNamespace("patchwork", quietly = TRUE)) {
      # Use patchwork for grid layout
      n_row <- ceiling(length(plot_list) / ncol)
      combined <- patchwork::wrap_plots(plot_list, ncol = ncol)
      return(combined)
    } else {
      # Return list if patchwork not available
      return(plot_list)
    }
  } else {
    if (length(plot_list) == 1) {
      return(plot_list[[1]])
    }
    return(plot_list)
  }
}

#' Plot Dominant Cell Type Classification
#'
#' Spatial plot showing the dominant cell type per spot.
#'
#' @param rctd_results RCTD object
#' @param spatial_coords DataFrame with x, y coordinates (optional)
#' @param min_proportion Minimum proportion to call a dominant type (default: 0.3)
#' @param point_size Point size (default: 1.5)
#'
#' @return ggplot object
#' @export
plot_rctd_dominant <- function(
    rctd_results,
    spatial_coords = NULL,
    min_proportion = 0.3,
    point_size = 1.5
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results)

  # Get dominant cell type per spot
  dominant <- colnames(props)[apply(props, 1, which.max)]
  max_prop <- apply(props, 1, max)

  # Mark uncertain spots
  dominant[max_prop < min_proportion] <- "Uncertain"

  # Get coordinates
  if (is.null(spatial_coords)) {
    if (nrow(rctd_results@spatialRNA@coords) > 0) {
      coords <- rctd_results@spatialRNA@coords
    } else {
      stop("No spatial coordinates available in RCTD object")
    }
  } else {
    coords <- spatial_coords
  }

  # Match spots
  common_spots <- intersect(rownames(props), rownames(coords))
  coords <- coords[common_spots, , drop = FALSE]
  dominant <- dominant[common_spots]

  # Create plot data
  plot_data <- data.frame(
    x = coords$x,
    y = coords$y,
    cell_type = factor(dominant),
    proportion = max_prop[common_spots]
  )

  # Get color palette
  n_types <- length(unique(dominant))
  if (n_types <= 8) {
    colors <- ggplot2::scale_color_brewer(palette = 'Set2')
  } else {
    colors <- ggplot2::scale_color_discrete()
  }

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = cell_type)) +
    ggplot2::geom_point(size = point_size, alpha = 0.8) +
    colors +
    ggplot2::labs(
      title = 'Dominant Cell Type per Spot',
      subtitle = sprintf('Minimum proportion: %.2f', min_proportion),
      x = 'X coordinate',
      y = 'Y coordinate',
      color = 'Cell Type'
    ) +
    ggplot2::theme_minimal() +
    ggplot2::coord_fixed()

  return(p)
}

#' Plot Doublet Classifications (Doublet Mode Only)
#'
#' Visualize doublet predictions from RCTD doublet mode.
#'
#' @param rctd_results RCTD object (must be run in doublet mode)
#' @param spatial_coords DataFrame with x, y coordinates (optional)
#' @param point_size Point size (default: 1)
#'
#' @return ggplot object
#' @export
plot_rctd_doublets <- function(
    rctd_results,
    spatial_coords = NULL,
    point_size = 1
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Check if doublet results exist
  if (!'results_df' %in% names(rctd_results@results)) {
    stop("No doublet results found. Was RCTD run in doublet mode?")
  }

  results_df <- rctd_results@results$results_df

  # Get coordinates
  if (is.null(spatial_coords)) {
    if (nrow(rctd_results@spatialRNA@coords) > 0) {
      coords <- rctd_results@spatialRNA@coords
    } else {
      stop("No spatial coordinates available")
    }
  } else {
    coords <- spatial_coords
  }

  # Match spots
  common_spots <- intersect(rownames(results_df), rownames(coords))
  coords <- coords[common_spots, , drop = FALSE]
  results_df <- results_df[common_spots, , drop = FALSE]

  # Get cell type names
  cell_type_names <- rctd_results@cell_type_info$renorm[[2]]

  # Create plot data
  plot_data <- data.frame(
    x = coords$x,
    y = coords$y,
    spot_class = results_df$spot_class,
    first_type = cell_type_names[results_df$first_type]
  )

  # Plot by spot class
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = spot_class)) +
    ggplot2::geom_point(size = point_size) +
    ggplot2::scale_color_manual(values = c(
      'singlet' = '#2ecc71',
      'doublet_certain' = '#e74c3c',
      'doublet_uncertain' = '#f39c12',
      'reject' = '#95a5a6'
    )) +
    ggplot2::labs(
      title = 'RCTD Spot Classification (Doublet Mode)',
      subtitle = sprintf('Singlet: %d | Doublet: %d | Uncertain: %d | Reject: %d',
                         sum(plot_data$spot_class == 'singlet'),
                         sum(plot_data$spot_class == 'doublet_certain'),
                         sum(plot_data$spot_class == 'doublet_uncertain'),
                         sum(plot_data$spot_class == 'reject')),
      x = 'X coordinate',
      y = 'Y coordinate',
      color = 'Spot Class'
    ) +
    ggplot2::theme_minimal() +
    ggplot2::coord_fixed()

  return(p)
}

#' Plot Proportion Distribution
#'
#' Boxplot/violin plot of cell type proportion distributions.
#'
#' @param rctd_results RCTD object
#' @param cell_types Cell types to plot (NULL = all)
#' @param plot_type 'boxplot' or 'violin' (default: 'violin')
#'
#' @return ggplot object
#' @export
plot_rctd_distribution <- function(
    rctd_results,
    cell_types = NULL,
    plot_type = 'violin'
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results)

  # Filter cell types
  if (!is.null(cell_types)) {
    props <- props[, cell_types, drop = FALSE]
  }

  # Reshape for plotting
  plot_data <- reshape2::melt(props, varnames = c('spot', 'cell_type'))

  # Create plot
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = cell_type, y = value, fill = cell_type))

  if (plot_type == 'violin') {
    p <- p + ggplot2::geom_violin(alpha = 0.7)
  } else {
    p <- p + ggplot2::geom_boxplot(alpha = 0.7)
  }

  p <- p +
    ggplot2::geom_jitter(width = 0.2, alpha = 0.1, size = 0.5) +
    ggplot2::labs(
      title = 'Cell Type Proportion Distribution',
      x = 'Cell Type',
      y = 'Proportion'
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
      legend.position = 'none'
    )

  return(p)
}

#' Plot Mean Proportions Bar Chart
#'
#' Bar chart showing mean proportion of each cell type.
#'
#' @param rctd_results RCTD object
#' @param cell_types Cell types to plot (NULL = all)
#' @param sort Logical: sort by proportion (default: TRUE)
#'
#' @return ggplot object
#' @export
plot_rctd_mean_props <- function(
    rctd_results,
    cell_types = NULL,
    sort = TRUE
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results)

  # Calculate means
  mean_props <- colMeans(props)

  # Filter cell types
  if (!is.null(cell_types)) {
    mean_props <- mean_props[cell_types]
  }

  # Create data frame
  plot_data <- data.frame(
    cell_type = names(mean_props),
    proportion = mean_props,
    stringsAsFactors = FALSE
  )

  # Sort if requested
  if (sort) {
    plot_data <- plot_data[order(plot_data$proportion, decreasing = TRUE), ]
    plot_data$cell_type <- factor(plot_data$cell_type, levels = plot_data$cell_type)
  }

  # Create plot
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = cell_type, y = proportion, fill = cell_type)) +
    ggplot2::geom_bar(stat = 'identity', alpha = 0.8) +
    ggplot2::geom_text(ggplot2::aes(label = sprintf('%.3f', proportion)),
                       vjust = -0.5, size = 3) +
    ggplot2::labs(
      title = 'Mean Cell Type Proportions',
      x = 'Cell Type',
      y = 'Mean Proportion'
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
      legend.position = 'none'
    )

  return(p)
}

#' Plot Proportion Heatmap
#'
#' Heatmap of cell type proportions across spots (sampled).
#'
#' @param rctd_results RCTD object
#' @param n_spots Number of spots to sample (default: 100)
#' @param cell_types Cell types to plot (NULL = all)
#' @param cluster Logical: cluster spots (default: TRUE)
#'
#' @return ggplot object
#' @export
plot_rctd_heatmap <- function(
    rctd_results,
    n_spots = 100,
    cell_types = NULL,
    cluster = TRUE
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results)

  # Filter cell types
  if (!is.null(cell_types)) {
    props <- props[, cell_types, drop = FALSE]
  }

  # Sample spots
  if (nrow(props) > n_spots) {
    set.seed(42)
    sampled_spots <- sample(rownames(props), n_spots)
    props <- props[sampled_spots, , drop = FALSE]
  }

  # Cluster if requested
  if (cluster && nrow(props) > 2) {
    # Cluster rows (spots)
    hc <- hclust(dist(props))
    row_order <- hc$order
    props <- props[row_order, , drop = FALSE]
  }

  # Reshape for plotting
  plot_data <- reshape2::melt(as.matrix(props))
  colnames(plot_data) <- c('spot', 'cell_type', 'proportion')

  # Create heatmap
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = cell_type, y = spot, fill = proportion)) +
    ggplot2::geom_tile() +
    ggplot2::scale_fill_viridis_c(name = 'Proportion', option = 'plasma') +
    ggplot2::labs(
      title = sprintf('Cell Type Proportions Heatmap (%d spots)', nrow(props)),
      x = 'Cell Type',
      y = 'Spot'
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      axis.text.y = ggplot2::element_blank(),
      axis.ticks.y = ggplot2::element_blank(),
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1)
    )

  return(p)
}

#' Plot Proportion Scatter Comparison
#'
#' Compare proportions between two cell types.
#'
#' @param rctd_results RCTD object
#' @param cell_type_x First cell type (x-axis)
#' @param cell_type_y Second cell type (y-axis)
#' @param color_by_third Optional: color by third cell type
#'
#' @return ggplot object
#' @export
plot_rctd_scatter <- function(
    rctd_results,
    cell_type_x,
    cell_type_y,
    color_by_third = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results)

  # Check cell types exist
  if (!(cell_type_x %in% colnames(props))) {
    stop(sprintf("Cell type '%s' not found", cell_type_x))
  }
  if (!(cell_type_y %in% colnames(props))) {
    stop(sprintf("Cell type '%s' not found", cell_type_y))
  }

  # Create plot data
  plot_data <- data.frame(
    x = props[[cell_type_x]],
    y = props[[cell_type_y]]
  )

  # Add color if specified
  if (!is.null(color_by_third)) {
    if (!(color_by_third %in% colnames(props))) {
      warning(sprintf("Color cell type '%s' not found", color_by_third))
    } else {
      plot_data$color <- props[[color_by_third]]
    }
  }

  # Create plot
  if ('color' %in% colnames(plot_data)) {
    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = color)) +
      ggplot2::scale_color_viridis_c(name = color_by_third)
  } else {
    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y)) +
      ggplot2::scale_color_manual(values = 'steelblue')
  }

  p <- p +
    ggplot2::geom_point(alpha = 0.6, size = 1) +
    ggplot2::geom_abline(intercept = 0, slope = 1, linetype = 'dashed', color = 'red') +
    ggplot2::labs(
      title = sprintf('Proportion Comparison: %s vs %s', cell_type_x, cell_type_y),
      x = sprintf('%s proportion', cell_type_x),
      y = sprintf('%s proportion', cell_type_y)
    ) +
    ggplot2::theme_minimal()

  return(p)
}

#' Create Comprehensive RCTD Summary Plot
#'
#' Multi-panel summary of RCTD results.
#'
#' @param rctd_results RCTD object
#' @param output_dir Directory to save plots (optional)
#' @param prefix File prefix (default: 'rctd')
#' @param cell_types Cell types to highlight (NULL = top 6)
#'
#' @return List of ggplot objects
#' @export
plot_rctd_summary <- function(
    rctd_results,
    output_dir = NULL,
    prefix = 'rctd',
    cell_types = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Get top cell types if not specified
  if (is.null(cell_types)) {
    summary <- summarize_rctd_results(rctd_results)
    cell_types <- names(sort(summary$mean_proportions, decreasing = TRUE))[1:min(6, length(summary$mean_proportions))]
  }

  # Create individual plots
  plots <- list()

  # 1. Mean proportions
  plots$mean_props <- plot_rctd_mean_props(rctd_results, cell_types = cell_types)

  # 2. Spatial plots (if coordinates available)
  if (nrow(rctd_results@spatialRNA@coords) > 0) {
    plots$spatial <- plot_rctd_proportions(rctd_results, cell_types = cell_types[1:min(4, length(cell_types))])
    plots$dominant <- plot_rctd_dominant(rctd_results)
  }

  # 3. Distribution
  plots$distribution <- plot_rctd_distribution(rctd_results, cell_types = cell_types)

  # 4. Doublet plot (if in doublet mode)
  doublet_mode <- rctd_results@config$doublet_mode %||% 'full'
  if (doublet_mode == 'doublet' && 'results_df' %in% names(rctd_results@results)) {
    plots$doublets <- plot_rctd_doublets(rctd_results)
  }

  # 5. Heatmap
  plots$heatmap <- plot_rctd_heatmap(rctd_results, cell_types = cell_types)

  # Save if output directory provided
  if (!is.null(output_dir)) {
    dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

    for (name in names(plots)) {
      if (!is.null(plots[[name]])) {
        filename <- file.path(output_dir, sprintf('%s_%s.pdf', prefix, name))
        ggplot2::ggsave(filename, plots[[name]], width = 10, height = 8)
      }
    }

    message(sprintf("Plots saved to %s", output_dir))
  }

  return(plots)
}

# Helper function for NULL default
`%||%` <- function(x, y) if (is.null(x)) y else x
