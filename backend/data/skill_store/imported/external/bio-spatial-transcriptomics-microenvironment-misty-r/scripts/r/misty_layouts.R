#' mistyR Network Layout Functions
#'
#' Multiple layout algorithms for network visualization.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

library(igraph)

#' Apply Network Layout
#'
#' Apply a specified layout algorithm to the network.
#'
#' @param g igraph object
#' @param method Layout method: "fr", "kk", "drl", "lgl", "graphopt", "mds", "circle", "grid"
#' @param weights Use edge weights (default: TRUE)
#' @param seed Random seed for reproducibility (default: 42)
#'
#' @return Matrix with x,y coordinates
#' @export
#'
#' @examples
#' \dontrun{
#' layout_matrix <- apply_layout(network, method = "fr")
#' }
apply_layout <- function(g,
                         method = c("fr", "kk", "drl", "lgl", "graphopt",
                                   "mds", "circle", "grid", "star", "sugiyama"),
                         weights = TRUE,
                         seed = 42) {
  method <- match.arg(method)
  set.seed(seed)

  # Get weights if available and requested
  w <- if (weights && !is.null(E(g)$weight)) E(g)$weight else NULL

  # Apply layout
  coords <- switch(method,
    "fr" = layout_with_fr(g, weights = w),
    "kk" = layout_with_kk(g, weights = w),
    "drl" = layout_with_drl(g, weights = w),
    "lgl" = layout_with_lgl(g),
    "graphopt" = layout_with_graphopt(g, weights = w),
    "mds" = layout_with_mds(g, dist = NULL),
    "circle" = layout_in_circle(g),
    "grid" = layout_on_grid(g),
    "star" = layout_as_star(g),
    "sugiyama" = layout_with_sugiyama(g)$layout
  )

  return(coords)
}


#' Layout with Community Preservation
#'
#' Layout that preserves community structure using FR with community-aware initialization.
#'
#' @param g igraph object
#' @param communities Community object from cluster_* functions
#' @param expand Expand factor for communities (default: 2)
#' @param seed Random seed
#'
#' @return Matrix with x,y coordinates
#' @export
#'
#' @examples
#' \dontrun{
#' comm <- cluster_louvain(network)
#' layout <- layout_with_communities(network, comm)
#' }
layout_with_communities <- function(g, communities, expand = 2, seed = 42) {
  set.seed(seed)

  # Get community membership
  membership <- membership(communities)

  # Initialize positions based on communities
  n_comm <- max(membership)
  comm_angles <- seq(0, 2 * pi, length.out = n_comm + 1)[-1]
  comm_centers <- cbind(cos(comm_angles), sin(comm_angles)) * expand

  # Initial layout: place nodes near their community center
  init_layout <- matrix(0, nrow = vcount(g), ncol = 2)
  for (i in seq_len(vcount(g))) {
    comm <- membership[i]
    noise <- rnorm(2, sd = 0.3)
    init_layout[i, ] <- comm_centers[comm, ] + noise
  }

  # Refine with FR layout
  final_layout <- layout_with_fr(g, coords = init_layout, start.temp = 0.1)

  return(final_layout)
}


#' Hierarchical Layout
#'
#' Layout for hierarchical/networks with clear levels.
#'
#' @param g igraph object
#' @param levels Optional predefined levels for nodes
#' @param level_attr Attribute name for levels if stored in graph
#' @param orientation "TB" (top-bottom), "BT", "LR" (left-right), "RL"
#'
#' @return Matrix with x,y coordinates
#' @export
#'
#' @examples
#' \dontrun{
#' layout <- layout_hierarchical(network, orientation = "TB")
#' }
layout_hierarchical <- function(g,
                                levels = NULL,
                                level_attr = NULL,
                                orientation = c("TB", "BT", "LR", "RL")) {
  orientation <- match.arg(orientation)

  # Use Sugiyama layout for directed acyclic graphs
  if (is_dag(g)) {
    layout_result <- layout_with_sugiyama(g)
    coords <- layout_result$layout[, 2:1]  # Swap x and y

    # Adjust orientation
    coords <- switch(orientation,
      "TB" = coords * c(1, -1),  # Flip y
      "BT" = coords,
      "LR" = coords[, c(2, 1)],
      "RL" = coords[, c(2, 1)] * c(-1, 1)
    )
  } else {
    # Use layering approach for general graphs
    if (!is.null(levels)) {
      # User-provided levels
      y_pos <- levels
    } else if (!is.null(level_attr) && level_attr %in% vertex_attr_names(g)) {
      # Levels from graph attribute
      y_pos <- vertex_attr(g, level_attr)
    } else {
      # Estimate levels from distance to sources
      sources <- which(degree(g, mode = "in") == 0)
      if (length(sources) == 0) sources <- 1
      y_pos <- distances(g, v = sources, mode = "in")[1, ]
      y_pos <- ifelse(is.finite(y_pos), y_pos, max(y_pos, na.rm = TRUE) + 1)
    }

    # Assign x positions within each level
    x_pos <- ave(seq_along(y_pos), y_pos, FUN = function(x) {
      seq(-length(x)/2, length(x)/2, length.out = length(x))
    })

    coords <- cbind(x_pos, y_pos)

    # Adjust for orientation
    coords <- switch(orientation,
      "TB" = coords[, c(1, -y_pos + max(y_pos) + 1)],
      "BT" = coords,
      "LR" = coords[, c(2, 1)],
      "RL" = coords[, c(-y_pos - 1, 1)]
    )
  }

  return(coords)
}


#' Multi-Dimensional Scaling Layout
#'
#' Layout using MDS on graph distances.
#'
#' @param g igraph object
#' @param dim Number of dimensions (2 or 3)
#' @param method Distance method: "shortest", "adjacency"
#'
#' @return Matrix with coordinates
#' @export
#'
#' @examples
#' \dontrun{
#' layout <- layout_mds(network, dim = 2)
#' }
layout_mds <- function(g, dim = 2, method = c("shortest", "adjacency")) {
  method <- match.arg(method)

  if (method == "shortest") {
    # Use shortest path distances
    dist_matrix <- distances(g)
    dist_matrix[!is.finite(dist_matrix)] <- max(dist_matrix[is.finite(dist_matrix)]) + 1
  } else {
    # Use adjacency matrix distances
    adj <- as_adjacency_matrix(g, sparse = FALSE)
    dist_matrix <- as.matrix(dist(adj))
  }

  # Perform MDS
  if (dim == 2) {
    coords <- cmdscale(dist_matrix, k = 2)
  } else {
    coords <- cmdscale(dist_matrix, k = 3)
  }

  return(coords)
}


#' Force-Directed Layout with Constraints
#'
#' Force-directed layout with optional constraints.
#'
#' @param g igraph object
#' @param fixed_nodes Vector of node indices to fix
#' @param fixed_positions Matrix of fixed positions for fixed nodes
#' @param weights Edge weights
#' @param niter Number of iterations
#' @param seed Random seed
#'
#' @return Matrix with coordinates
#' @export
#'
#' @examples
#' \dontrun{
#' # Fix hub nodes in place
#' hubs <- which(degree(network) > 10)
#' layout <- layout_constrained(network, fixed_nodes = hubs)
#' }
layout_constrained <- function(g,
                               fixed_nodes = NULL,
                               fixed_positions = NULL,
                               weights = NULL,
                               niter = 500,
                               seed = 42) {
  set.seed(seed)

  # Initial layout
  if (!is.null(fixed_positions) && !is.null(fixed_nodes)) {
    # Start with fixed positions
    init <- matrix(rnorm(vcount(g) * 2), ncol = 2)
    init[fixed_nodes, ] <- fixed_positions
  } else {
    init <- layout_with_fr(g, niter = 50)
  }

  # Run FR layout with custom parameters
  coords <- layout_with_fr(g,
                           coords = init,
                           niter = niter,
                           start.temp = 0.1,
                           weights = weights)

  # Restore fixed positions if specified
  if (!is.null(fixed_nodes) && !is.null(fixed_positions)) {
    coords[fixed_nodes, ] <- fixed_positions
  }

  return(coords)
}


#' Layout Comparison
#'
#' Generate multiple layouts and compare their quality.
#'
#' @param g igraph object
#' @param methods Vector of layout methods to compare
#' @param plot Whether to create comparison plot
#'
#' @return List with layouts and quality metrics
#' @export
#'
#' @examples
#' \dontrun{
#' comparison <- compare_layouts(network, methods = c("fr", "kk", "drl"))
#' }
compare_layouts <- function(g,
                            methods = c("fr", "kk", "drl"),
                            plot = TRUE) {

  results <- list()
  metrics <- data.frame(method = character(),
                        edge_crossings = numeric(),
                        area_coverage = numeric(),
                        stress = numeric(),
                        stringsAsFactors = FALSE)

  for (method in methods) {
    # Apply layout
    coords <- tryCatch({
      apply_layout(g, method = method)
    }, error = function(e) {
      message(sprintf("Layout %s failed: %s", method, e$message))
      NULL
    })

    if (is.null(coords)) next

    results[[method]] <- coords

    # Calculate metrics
    # Edge crossings (approximate)
    crossings <- count_edge_crossings(g, coords)

    # Area coverage (bounding box area / convex hull area)
    bbox_area <- diff(range(coords[, 1])) * diff(range(coords[, 2]))

    # Stress (difference between layout distances and graph distances)
    stress <- calculate_layout_stress(g, coords)

    metrics <- rbind(metrics, data.frame(
      method = method,
      edge_crossings = crossings,
      area_coverage = bbox_area,
      stress = stress,
      stringsAsFactors = FALSE
    ))
  }

  # Create comparison plot if requested
  if (plot && length(results) > 0) {
    n <- length(results)
    cols <- ceiling(sqrt(n))
    rows <- ceiling(n / cols)

    par(mfrow = c(rows, cols))
    for (method in names(results)) {
      plot(g, layout = results[[method]],
           main = method,
           vertex.size = 3,
           vertex.label = NA,
           edge.width = 0.5,
           edge.arrow.size = 0.3)
    }
    par(mfrow = c(1, 1))
  }

  return(list(layouts = results, metrics = metrics))
}


#' Count Edge Crossings
#'
#' Helper function to count edge crossings in a layout.
#'
#' @param g igraph object
#' @param layout Layout matrix
#'
#' @return Approximate number of edge crossings
#' @keywords internal
count_edge_crossings <- function(g, layout) {
  edges <- as_edgelist(g)
  n_crossings <- 0

  for (i in 1:(nrow(edges) - 1)) {
    for (j in (i + 1):nrow(edges)) {
      # Skip if edges share a node
      if (length(intersect(edges[i, ], edges[j, ])) > 0) next

      # Check line segment intersection
      p1 <- layout[edges[i, 1], ]
      p2 <- layout[edges[i, 2], ]
      p3 <- layout[edges[j, 1], ]
      p4 <- layout[edges[j, 2], ]

      if (segments_intersect(p1, p2, p3, p4)) {
        n_crossings <- n_crossings + 1
      }
    }
  }

  return(n_crossings)
}


#' Check Line Segment Intersection
#'
#' Check if two line segments intersect.
#'
#' @param p1, p2 Endpoints of first segment
#' @param p3, p4 Endpoints of second segment
#'
#' @return TRUE if segments intersect
#' @keywords internal
segments_intersect <- function(p1, p2, p3, p4) {
  # Cross product helper
  cross <- function(a, b) a[1] * b[2] - a[2] * b[1]

  r <- p2 - p1
  s <- p4 - p3
  rxs <- cross(r, s)
  qp <- p3 - p1
  qpxr <- cross(qp, r)

  if (abs(rxs) < 1e-10) return(FALSE)  # Parallel

  t <- cross(qp, s) / rxs
  u <- qpxr / rxs

  return(t >= 0 && t <= 1 && u >= 0 && u <= 1)
}


#' Calculate Layout Stress
#'
#' Calculate stress metric for a layout.
#'
#' @param g igraph object
#' @param layout Layout matrix
#'
#' @return Stress value
#' @keywords internal
calculate_layout_stress <- function(g, layout) {
  # Get graph distances
  graph_dist <- distances(g)
  graph_dist[!is.finite(graph_dist)] <- max(graph_dist[is.finite(graph_dist)]) + 1

  # Get layout distances
  layout_dist <- as.matrix(dist(layout))

  # Calculate stress (sum of squared differences)
  stress <- sum((graph_dist - layout_dist)^2, na.rm = TRUE)

  return(sqrt(stress))
}


#' Interactive Layout Adjustment
#'
#' Create an interactive plot for manual layout adjustment.
#'
#' @param g igraph object
#' @param initial_layout Initial layout matrix
#' @param output_file File to save adjusted layout
#'
#' @return Adjusted layout matrix
#' @export
#'
#' @examples
#' \dontrun{
#' layout <- interactive_layout(network)
#' }
interactive_layout <- function(g, initial_layout = NULL, output_file = NULL) {
  if (!requireNamespace("igraph", quietly = TRUE)) {
    stop("igraph package required")
  }

  # Use initial layout or compute one
  if (is.null(initial_layout)) {
    coords <- layout_with_fr(g)
  } else {
    coords <- initial_layout
  }

  # Create tkplot for interactive adjustment
  if (interactive()) {
    tk_id <- tkplot(g, layout = coords,
                    vertex.size = 5,
                    vertex.label = V(g)$name,
                    edge.width = 1,
                    edge.arrow.size = 0.5)

    message("Interactive layout opened. Adjust nodes as needed.")
    message("Use tkplot.getcoords() to retrieve final layout.")

    return(tk_id)
  } else {
    message("Non-interactive session. Returning initial layout.")
    return(coords)
  }
}


#' Get Layout for Plotting
#'
#' Convenience function to get layout with proper scaling.
#'
#' @param g igraph object
#' @param method Layout method
#' @param rescale Whether to rescale to [-1, 1] range
#' @param aspect_ratio Target aspect ratio (width/height)
#'
#' @return Scaled layout matrix
#' @export
#'
#' @examples
#' \dontrun{
#' layout <- get_plot_layout(network, method = "fr")
#' plot(network, layout = layout)
#' }
get_plot_layout <- function(g,
                            method = "fr",
                            rescale = TRUE,
                            aspect_ratio = 1) {
  coords <- apply_layout(g, method = method)

  if (rescale) {
    # Rescale to [-1, 1] range
    x_range <- range(coords[, 1])
    y_range <- range(coords[, 2])

    coords[, 1] <- (coords[, 1] - mean(x_range)) / diff(x_range) * 2
    coords[, 2] <- (coords[, 2] - mean(y_range)) / diff(y_range) * 2 * aspect_ratio
  }

  return(coords)
}
