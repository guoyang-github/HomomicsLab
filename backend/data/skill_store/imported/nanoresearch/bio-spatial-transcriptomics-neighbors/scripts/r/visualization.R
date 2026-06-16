#' Visualization Functions for Spatial Neighbor Graphs
#'
#' @author Yang Guo
#' @date 2026-04-13

#' Plot Spatial Neighbor Graph
#'
#' Visualize the spatial neighbor graph overlaid on tissue coordinates.
#'
#' @param seurat_obj Seurat object with neighbor graph
#' @param assay Name of neighbor graph assay (default: "spatial_neighbors")
#' @param spot_size Size of spots (default: 1)
#' @param edge_alpha Transparency of edges (default: 0.2)
#' @param edge_color Color of edges (default: "black")
#' @param coords Columns containing spatial coordinates
#' @param title Plot title
#'
#' @return ggplot object
#'
#' @export
PlotSpatialNeighborGraph <- function(
    seurat_obj,
    assay = "spatial_neighbors",
    spot_size = 1,
    edge_alpha = 0.2,
    edge_color = "black",
    coords = c("imagerow", "imagecol"),
    title = "Spatial Neighbor Graph"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  if (is.null(seurat_obj@misc[[assay]])) {
    stop(sprintf("No neighbor graph found in @misc[['%s']]", assay))
  }

  # Get coordinates
  if (!all(coords %in% colnames(seurat_obj@meta.data))) {
    if (length(seurat_obj@images) > 0) {
      img_name <- names(seurat_obj@images)[1]
      coords_df <- Seurat::GetTissueCoordinates(seurat_obj, image = img_name)
      coord_df <- data.frame(
        x = coords_df$imagecol,
        y = coords_df$imagerow,
        row.names = rownames(coords_df)
      )
    } else {
      stop("Coordinates not found")
    }
  } else {
    coord_df <- data.frame(
      x = seurat_obj@meta.data[, coords[2]],  # imagecol (x)
      y = seurat_obj@meta.data[, coords[1]],  # imagerow (y)
      row.names = colnames(seurat_obj)
    )
  }

  # Get connectivities
  conn <- seurat_obj@misc[[assay]]$connectivities

  # Create edge data frame
  edges_df <- data.frame(x1 = numeric(), y1 = numeric(), x2 = numeric(), y2 = numeric())

  for (i in 1:nrow(conn)) {
    neighbors <- which(conn[i, ] > 0)
    for (j in neighbors) {
      if (i < j) {  # Avoid duplicate edges
        spot_i <- rownames(conn)[i]
        spot_j <- colnames(conn)[j]
        if (spot_i %in% rownames(coord_df) && spot_j %in% rownames(coord_df)) {
          edges_df <- rbind(edges_df, data.frame(
            x1 = coord_df[spot_i, "x"],
            y1 = coord_df[spot_i, "y"],
            x2 = coord_df[spot_j, "x"],
            y2 = coord_df[spot_j, "y"]
          ))
        }
      }
    }
  }

  # Plot
  p <- ggplot2::ggplot() +
    ggplot2::geom_segment(
      data = edges_df,
      ggplot2::aes(x = x1, y = y1, xend = x2, yend = y2),
      color = edge_color,
      alpha = edge_alpha,
      linewidth = 0.3
    ) +
    ggplot2::geom_point(
      data = coord_df,
      ggplot2::aes(x = x, y = y),
      size = spot_size,
      color = "blue",
      alpha = 0.6
    ) +
    ggplot2::coord_fixed() +
    ggplot2::theme_minimal() +
    ggplot2::labs(title = title, x = "X", y = "Y") +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"),
      axis.text = ggplot2::element_blank(),
      axis.title = ggplot2::element_blank()
    )

  return(p)
}


#' Plot Neighbor Degree Distribution
#'
#' Plot distribution of neighbor counts per spot.
#'
#' @param seurat_obj Seurat object with neighbor graph
#' @param assay Name of neighbor graph assay (default: "spatial_neighbors")
#' @param plot_type Type of plot: "histogram" or "boxplot" (default: "histogram")
#'
#' @return ggplot object
#'
#' @export
PlotNeighborDegree <- function(
    seurat_obj,
    assay = "spatial_neighbors",
    plot_type = "histogram"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  if (is.null(seurat_obj@misc[[assay]])) {
    stop(sprintf("No neighbor graph found in @misc[['%s']]", assay))
  }

  conn <- seurat_obj@misc[[assay]]$connectivities
  degrees <- Matrix::rowSums(conn > 0)

  degree_df <- data.frame(degree = degrees)

  if (plot_type == "histogram") {
    p <- ggplot2::ggplot(degree_df, ggplot2::aes(x = degree)) +
      ggplot2::geom_histogram(bins = 30, fill = "steelblue", color = "white") +
      ggplot2::theme_minimal() +
      ggplot2::labs(
        title = "Neighbor Degree Distribution",
        x = "Number of Neighbors",
        y = "Count"
      ) +
      ggplot2::theme(plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"))
  } else {
    p <- ggplot2::ggplot(degree_df, ggplot2::aes(y = degree)) +
      ggplot2::geom_boxplot(fill = "steelblue", alpha = 0.7) +
      ggplot2::theme_minimal() +
      ggplot2::labs(
        title = "Neighbor Degree Distribution",
        y = "Number of Neighbors"
      ) +
      ggplot2::theme(plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"))
  }

  return(p)
}


#' Plot Neighbor Distance Distribution
#'
#' Plot distribution of distances to neighbors.
#'
#' @param seurat_obj Seurat object with neighbor graph
#' @param assay Name of neighbor graph assay (default: "spatial_neighbors")
#'
#' @return ggplot object
#'
#' @export
PlotNeighborDistance <- function(seurat_obj, assay = "spatial_neighbors") {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  if (is.null(seurat_obj@misc[[assay]])) {
    stop(sprintf("No neighbor graph found in @misc[['%s']]", assay))
  }

  dist <- seurat_obj@misc[[assay]]$distances
  distances <- dist@x[dist@x > 0]

  dist_df <- data.frame(distance = distances)

  ggplot2::ggplot(dist_df, ggplot2::aes(x = distance)) +
    ggplot2::geom_histogram(bins = 50, fill = "steelblue", color = "white") +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      title = "Neighbor Distance Distribution",
      x = "Distance",
      y = "Count"
    ) +
    ggplot2::theme(plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"))
}


#' Compare Two Neighbor Graphs
#'
#' Visual comparison of two different neighbor graph methods.
#'
#' @param seurat_obj Seurat object
#' @param assay1 First neighbor graph assay name
#' @param assay2 Second neighbor graph assay name
#' @param coords Columns containing spatial coordinates
#'
#' @return ggplot object (side-by-side comparison)
#'
#' @export
CompareNeighborGraphs <- function(
    seurat_obj,
    assay1 = "spatial_neighbors_knn",
    assay2 = "spatial_neighbors_radius",
    coords = c("imagerow", "imagecol")
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("patchwork", quietly = TRUE)) {
    stop("patchwork package required")
  }

  p1 <- PlotSpatialNeighborGraph(seurat_obj, assay = assay1, title = assay1) +
    ggplot2::theme(legend.position = "none")

  p2 <- PlotSpatialNeighborGraph(seurat_obj, assay = assay2, title = assay2) +
    ggplot2::theme(legend.position = "none")

  p1 + p2
}
