#' Spatial Neighbor Graphs for Seurat Objects
#'
#' Build spatial neighbor graphs for spatial transcriptomics data.
#' Supports KNN, radius-based, and Delaunay triangulation methods.
#'
#' @author Yang Guo
#' @date 2026-04-13
#' @version 1.0.0

#' Create Spatial Neighbors (KNN Method)
#'
#' Build K-nearest neighbor graph based on spatial coordinates.
#'
#' @param seurat_obj Seurat object with spatial coordinates
#' @param n_neighbors Number of nearest neighbors (default: 6)
#' @param coords Columns containing spatial coordinates (default: c("imagerow", "imagecol"))
#' @param assay Name for storing neighbor graph in misc (default: "spatial_neighbors")
#' @param verbose Print progress messages (default: TRUE)
#'
#' @return Seurat object with neighbor graph stored in @misc[[assay]]
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Standard Visium (6 neighbors for hexagonal grid)
#' seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 6)
#'
#' # High-resolution data with more neighbors
#' seurat_obj <- CreateSpatialNeighbors(seurat_obj, n_neighbors = 10)
#' }
CreateSpatialNeighbors <- function(
    seurat_obj,
    n_neighbors = 6,
    coords = c("imagerow", "imagecol"),
    assay = "spatial_neighbors",
    verbose = TRUE
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("FNN", quietly = TRUE)) {
    stop("FNN package required. Install with: install.packages('FNN')")
  }

  # Extract coordinates
  if (!all(coords %in% colnames(seurat_obj@meta.data))) {
    # Try to get from images slot (Visium)
    if (length(seurat_obj@images) > 0) {
      img_name <- names(seurat_obj@images)[1]
      coords_df <- Seurat::GetTissueCoordinates(seurat_obj, image = img_name)
      if (all(c("imagerow", "imagecol") %in% colnames(coords_df))) {
        coord_matrix <- as.matrix(coords_df[, c("imagerow", "imagecol")])
        rownames(coord_matrix) <- rownames(coords_df)
      } else {
        stop(sprintf("Coordinates not found in metadata or images. Expected columns: %s",
                     paste(coords, collapse = ", ")))
      }
    } else {
      stop(sprintf("Coordinate columns not found: %s", paste(coords, collapse = ", ")))
    }
  } else {
    coord_matrix <- as.matrix(seurat_obj@meta.data[, coords])
  }

  # Ensure spot order matches Seurat object
  common_cells <- intersect(colnames(seurat_obj), rownames(coord_matrix))
  if (length(common_cells) == 0) {
    stop("No matching cell IDs between coordinates and Seurat object")
  }
  coord_matrix <- coord_matrix[common_cells, , drop = FALSE]

  if (verbose) {
    message(sprintf("Building KNN graph with k=%d for %d spots...", n_neighbors, nrow(coord_matrix)))
  }

  # Build KNN using FNN
  knn_result <- FNN::get.knn(coord_matrix, k = n_neighbors)

  # Create sparse connectivity matrix
  n_spots <- nrow(coord_matrix)
  i <- rep(1:n_spots, each = n_neighbors)
  j <- as.vector(t(knn_result$nn.index))
  x <- rep(1, length(i))

  conn_matrix <- Matrix::sparseMatrix(
    i = i,
    j = j,
    x = x,
    dims = c(n_spots, n_spots)
  )
  rownames(conn_matrix) <- rownames(coord_matrix)
  colnames(conn_matrix) <- rownames(coord_matrix)

  # Make symmetric (if A is neighbor of B, B is neighbor of A)
  conn_matrix <- conn_matrix + Matrix::t(conn_matrix)
  conn_matrix@x <- rep(1, length(conn_matrix@x))

  # Create distance matrix
  dist_i <- rep(1:n_spots, each = n_neighbors)
  dist_j <- as.vector(t(knn_result$nn.index))
  dist_x <- as.vector(t(knn_result$nn.dist))

  dist_matrix <- Matrix::sparseMatrix(
    i = dist_i,
    j = dist_j,
    x = dist_x,
    dims = c(n_spots, n_spots)
  )
  rownames(dist_matrix) <- rownames(coord_matrix)
  colnames(dist_matrix) <- rownames(coord_matrix)

  # Store in Seurat object
  if (is.null(seurat_obj@misc[[assay]])) {
    seurat_obj@misc[[assay]] <- list()
  }
  seurat_obj@misc[[assay]]$connectivities <- conn_matrix
  seurat_obj@misc[[assay]]$distances <- dist_matrix
  seurat_obj@misc[[assay]]$params <- list(
    method = "knn",
    n_neighbors = n_neighbors,
    coords = coords
  )

  # Calculate statistics
  degrees <- Matrix::rowSums(conn_matrix)
  seurat_obj@misc[[assay]]$stats <- list(
    n_spots = n_spots,
    n_edges = sum(conn_matrix@x > 0) / 2,
    mean_degree = mean(degrees),
    median_degree = median(degrees)
  )

  if (verbose) {
    message(sprintf("Graph created: %d spots, %.0f edges, mean degree: %.1f",
                    n_spots,
                    seurat_obj@misc[[assay]]$stats$n_edges,
                    seurat_obj@misc[[assay]]$stats$mean_degree))
  }

  return(seurat_obj)
}


#' Create Spatial Neighbors (Radius Method)
#'
#' Build radius-based neighbor graph connecting all spots within specified distance.
#'
#' @param seurat_obj Seurat object with spatial coordinates
#' @param radius Distance threshold in coordinate units (microns or pixels)
#' @param coords Columns containing spatial coordinates (default: c("imagerow", "imagecol"))
#' @param assay Name for storing neighbor graph in misc (default: "spatial_neighbors")
#' @param verbose Print progress messages (default: TRUE)
#'
#' @return Seurat object with neighbor graph stored in @misc[[assay]]
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Connect spots within 100 microns
#' seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 100)
#'
#' # For Visium HD with 2um bins
#' seurat_obj <- CreateSpatialNeighborsRadius(seurat_obj, radius = 8)
#' }
CreateSpatialNeighborsRadius <- function(
    seurat_obj,
    radius,
    coords = c("imagerow", "imagecol"),
    assay = "spatial_neighbors",
    verbose = TRUE
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract coordinates
  if (!all(coords %in% colnames(seurat_obj@meta.data))) {
    if (length(seurat_obj@images) > 0) {
      img_name <- names(seurat_obj@images)[1]
      coords_df <- Seurat::GetTissueCoordinates(seurat_obj, image = img_name)
      if (all(c("imagerow", "imagecol") %in% colnames(coords_df))) {
        coord_matrix <- as.matrix(coords_df[, c("imagerow", "imagecol")])
        rownames(coord_matrix) <- rownames(coords_df)
      } else {
        stop(sprintf("Coordinates not found. Expected columns: %s",
                     paste(coords, collapse = ", ")))
      }
    } else {
      stop(sprintf("Coordinate columns not found: %s", paste(coords, collapse = ", ")))
    }
  } else {
    coord_matrix <- as.matrix(seurat_obj@meta.data[, coords])
  }

  common_cells <- intersect(colnames(seurat_obj), rownames(coord_matrix))
  if (length(common_cells) == 0) {
    stop("No matching cell IDs between coordinates and Seurat object")
  }
  coord_matrix <- coord_matrix[common_cells, , drop = FALSE]

  if (verbose) {
    message(sprintf("Building radius graph (r=%.1f) for %d spots...", radius, nrow(coord_matrix)))
  }

  # Build radius-based graph
  n_spots <- nrow(coord_matrix)
  i_list <- c()
  j_list <- c()
  dist_list <- c()

  # Use efficient distance calculation
  for (spot_idx in 1:n_spots) {
    spot_coord <- coord_matrix[spot_idx, ]
    distances <- sqrt(rowSums((coord_matrix - matrix(spot_coord, nrow = n_spots, ncol = 2, byrow = TRUE))^2))
    neighbors <- which(distances <= radius & distances > 0)

    if (length(neighbors) > 0) {
      i_list <- c(i_list, rep(spot_idx, length(neighbors)))
      j_list <- c(j_list, neighbors)
      dist_list <- c(dist_list, distances[neighbors])
    }
  }

  if (length(i_list) == 0) {
    warning("No neighbors found with given radius. Try increasing radius.")
  }

  # Create sparse matrices
  conn_matrix <- Matrix::sparseMatrix(
    i = i_list,
    j = j_list,
    x = rep(1, length(i_list)),
    dims = c(n_spots, n_spots)
  )
  rownames(conn_matrix) <- rownames(coord_matrix)
  colnames(conn_matrix) <- rownames(coord_matrix)

  dist_matrix <- Matrix::sparseMatrix(
    i = i_list,
    j = j_list,
    x = dist_list,
    dims = c(n_spots, n_spots)
  )
  rownames(dist_matrix) <- rownames(coord_matrix)
  colnames(dist_matrix) <- rownames(coord_matrix)

  # Store in Seurat object
  if (is.null(seurat_obj@misc[[assay]])) {
    seurat_obj@misc[[assay]] <- list()
  }
  seurat_obj@misc[[assay]]$connectivities <- conn_matrix
  seurat_obj@misc[[assay]]$distances <- dist_matrix
  seurat_obj@misc[[assay]]$params <- list(
    method = "radius",
    radius = radius,
    coords = coords
  )

  degrees <- Matrix::rowSums(conn_matrix > 0)
  seurat_obj@misc[[assay]]$stats <- list(
    n_spots = n_spots,
    n_edges = sum(conn_matrix@x > 0) / 2,
    mean_degree = mean(degrees),
    median_degree = median(degrees),
    radius = radius
  )

  if (verbose) {
    message(sprintf("Graph created: %d spots, %.0f edges, mean degree: %.1f",
                    n_spots,
                    seurat_obj@misc[[assay]]$stats$n_edges,
                    seurat_obj@misc[[assay]]$stats$mean_degree))
  }

  return(seurat_obj)
}


#' Create Spatial Neighbors (Delaunay Triangulation)
#'
#' Build Delaunay triangulation graph for natural neighbor relationships.
#' Best for irregular spatial layouts.
#'
#' @param seurat_obj Seurat object with spatial coordinates
#' @param coords Columns containing spatial coordinates (default: c("imagerow", "imagecol"))
#' @param assay Name for storing neighbor graph in misc (default: "spatial_neighbors")
#' @param verbose Print progress messages (default: TRUE)
#'
#' @return Seurat object with neighbor graph stored in @misc[[assay]]
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Delaunay triangulation for irregular spot layout
#' seurat_obj <- CreateSpatialNeighborsDelaunay(seurat_obj)
#' }
CreateSpatialNeighborsDelaunay <- function(
    seurat_obj,
    coords = c("imagerow", "imagecol"),
    assay = "spatial_neighbors",
    verbose = TRUE
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("deldir", quietly = TRUE)) {
    stop("deldir package required. Install with: install.packages('deldir')")
  }

  # Extract coordinates
  if (!all(coords %in% colnames(seurat_obj@meta.data))) {
    if (length(seurat_obj@images) > 0) {
      img_name <- names(seurat_obj@images)[1]
      coords_df <- Seurat::GetTissueCoordinates(seurat_obj, image = img_name)
      if (all(c("imagerow", "imagecol") %in% colnames(coords_df))) {
        coord_matrix <- as.matrix(coords_df[, c("imagerow", "imagecol")])
        rownames(coord_matrix) <- rownames(coords_df)
      } else {
        stop(sprintf("Coordinates not found. Expected columns: %s",
                     paste(coords, collapse = ", ")))
      }
    } else {
      stop(sprintf("Coordinate columns not found: %s", paste(coords, collapse = ", ")))
    }
  } else {
    coord_matrix <- as.matrix(seurat_obj@meta.data[, coords])
  }

  common_cells <- intersect(colnames(seurat_obj), rownames(coord_matrix))
  if (length(common_cells) == 0) {
    stop("No matching cell IDs between coordinates and Seurat object")
  }
  coord_matrix <- coord_matrix[common_cells, , drop = FALSE]

  if (verbose) {
    message(sprintf("Building Delaunay triangulation for %d spots...", nrow(coord_matrix)))
  }

  # Compute Delaunay triangulation
  del <- deldir::deldir(coord_matrix[, 1], coord_matrix[, 2])

  # Extract edges from triangulation
  edges <- del$delsgs[, c("ind1", "ind2")]

  n_spots <- nrow(coord_matrix)

  # Create connectivity matrix
  i <- c(edges$ind1, edges$ind2)
  j <- c(edges$ind2, edges$ind1)
  x <- rep(1, length(i))

  conn_matrix <- Matrix::sparseMatrix(
    i = i,
    j = j,
    x = x,
    dims = c(n_spots, n_spots)
  )
  rownames(conn_matrix) <- rownames(coord_matrix)
  colnames(conn_matrix) <- rownames(coord_matrix)

  # Calculate distances for edges
  dists <- sqrt(rowSums((coord_matrix[edges$ind1, ] - coord_matrix[edges$ind2, ])^2))
  dist_i <- c(edges$ind1, edges$ind2)
  dist_j <- c(edges$ind2, edges$ind1)
  dist_x <- c(dists, dists)

  dist_matrix <- Matrix::sparseMatrix(
    i = dist_i,
    j = dist_j,
    x = dist_x,
    dims = c(n_spots, n_spots)
  )
  rownames(dist_matrix) <- rownames(coord_matrix)
  colnames(dist_matrix) <- rownames(coord_matrix)

  # Store in Seurat object
  if (is.null(seurat_obj@misc[[assay]])) {
    seurat_obj@misc[[assay]] <- list()
  }
  seurat_obj@misc[[assay]]$connectivities <- conn_matrix
  seurat_obj@misc[[assay]]$distances <- dist_matrix
  seurat_obj@misc[[assay]]$params <- list(
    method = "delaunay",
    coords = coords
  )

  degrees <- Matrix::rowSums(conn_matrix > 0)
  seurat_obj@misc[[assay]]$stats <- list(
    n_spots = n_spots,
    n_edges = sum(conn_matrix@x > 0) / 2,
    mean_degree = mean(degrees),
    median_degree = median(degrees)
  )

  if (verbose) {
    message(sprintf("Delaunay graph created: %d spots, %.0f edges, mean degree: %.1f",
                    n_spots,
                    seurat_obj@misc[[assay]]$stats$n_edges,
                    seurat_obj@misc[[assay]]$stats$mean_degree))
  }

  return(seurat_obj)
}


#' Get Spatial Neighbors
#'
#' Retrieve neighbor indices and distances for a specific spot.
#'
#' @param seurat_obj Seurat object with neighbor graph
#' @param spot_id Spot identifier (cell barcode)
#' @param assay Name of neighbor graph assay (default: "spatial_neighbors")
#'
#' @return Data frame with neighbor indices and distances
#'
#' @export
GetSpatialNeighbors <- function(seurat_obj, spot_id, assay = "spatial_neighbors") {
  if (is.null(seurat_obj@misc[[assay]])) {
    stop(sprintf("No neighbor graph found in @misc[['%s']]", assay))
  }

  conn <- seurat_obj@misc[[assay]]$connectivities
  dist <- seurat_obj@misc[[assay]]$distances

  if (!spot_id %in% rownames(conn)) {
    stop(sprintf("Spot '%s' not found in neighbor graph", spot_id))
  }

  spot_idx <- which(rownames(conn) == spot_id)
  neighbor_indices <- which(conn[spot_idx, ] > 0)

  if (length(neighbor_indices) == 0) {
    return(data.frame(
      neighbor = character(),
      distance = numeric(),
      stringsAsFactors = FALSE
    ))
  }

  neighbor_ids <- colnames(conn)[neighbor_indices]
  distances <- dist[spot_idx, neighbor_indices]

  data.frame(
    neighbor = neighbor_ids,
    distance = as.vector(distances),
    stringsAsFactors = FALSE
  )
}


#' Summarize Spatial Neighbor Graph
#'
#' Print summary statistics of the neighbor graph.
#'
#' @param seurat_obj Seurat object with neighbor graph
#' @param assay Name of neighbor graph assay (default: "spatial_neighbors")
#'
#' @export
SummarizeSpatialNeighbors <- function(seurat_obj, assay = "spatial_neighbors") {
  if (is.null(seurat_obj@misc[[assay]])) {
    stop(sprintf("No neighbor graph found in @misc[['%s']]", assay))
  }

  stats <- seurat_obj@misc[[assay]]$stats
  params <- seurat_obj@misc[[assay]]$params

  cat("Spatial Neighbor Graph Summary\n")
  cat("==============================\n")
  cat(sprintf("Method: %s\n", params$method))
  if (!is.null(params$n_neighbors)) {
    cat(sprintf("KNN k: %d\n", params$n_neighbors))
  }
  if (!is.null(params$radius)) {
    cat(sprintf("Radius: %.2f\n", params$radius))
  }
  cat(sprintf("Spots: %d\n", stats$n_spots))
  cat(sprintf("Edges: %.0f\n", stats$n_edges))
  cat(sprintf("Mean degree: %.2f\n", stats$mean_degree))
  cat(sprintf("Median degree: %.2f\n", stats$median_degree))
}


#' Create Grid Neighbors (Visium-specific)
#'
#' Build neighbor graph matching Visium hexagonal grid structure.
#' Uses n_rings parameter to define neighborhood size.
#'
#' @param seurat_obj Seurat object with spatial coordinates
#' @param n_rings Number of hexagonal rings around each spot (default: 1)
#' @param coords Columns containing spatial coordinates (default: c("imagerow", "imagecol"))
#' @param assay Name for storing neighbor graph in misc (default: "spatial_neighbors")
#' @param verbose Print progress messages (default: TRUE)
#'
#' @return Seurat object with neighbor graph stored in @misc[[assay]]
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Visium immediate neighbors (6 neighbors)
#' seurat_obj <- CreateGridNeighbors(seurat_obj, n_rings = 1)
#'
#' # Extended neighborhood (18 neighbors)
#' seurat_obj <- CreateGridNeighbors(seurat_obj, n_rings = 2)
#' }
CreateGridNeighbors <- function(
    seurat_obj,
    n_rings = 1,
    coords = c("imagerow", "imagecol"),
    assay = "spatial_neighbors",
    verbose = TRUE
) {
  if (n_rings == 1) {
    # For 1 ring, use KNN with k=6
    if (verbose) message("Using KNN with k=6 for single-ring grid neighborhood")
    return(CreateSpatialNeighbors(seurat_obj, n_neighbors = 6, coords = coords, assay = assay, verbose = verbose))
  } else {
    # For multiple rings, use radius based on spot spacing
    # Estimate spot spacing from nearest neighbor distances
    coord_matrix <- as.matrix(seurat_obj@meta.data[, coords])
    knn_result <- FNN::get.knn(coord_matrix, k = 1)
    spot_spacing <- median(knn_result$nn.dist)

    # Radius for n rings (approximate)
    radius <- spot_spacing * (n_rings + 0.5)

    if (verbose) message(sprintf("Using radius %.1f for %d-ring grid neighborhood", radius, n_rings))
    return(CreateSpatialNeighborsRadius(seurat_obj, radius = radius, coords = coords, assay = assay, verbose = verbose))
  }
}
