##' mistyR Network Analysis Functions
#'
#' Network creation, statistics, and analysis for mistyR results.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

# Conditionally load packages
if (requireNamespace("igraph", quietly = TRUE)) {
  library(igraph)
}
if (requireNamespace("dplyr", quietly = TRUE)) {
  library(dplyr)
}

#' Create Interaction Network from mistyR Results
#'
#' Build an igraph network object from mistyR interaction data.
#'
#' @param interactions mistyR interactions dataframe
#' @param view_name View to use (default: "intra")
#' @param importance_threshold Minimum importance for edge inclusion
#' @param directed Whether network is directed (default: TRUE)
#'
#' @return igraph object
#' @export
#'
#' @examples
#' \dontrun{
#' network <- create_interaction_network(results$interactions, view_name = "para.100")
#' }
create_interaction_network <- function(interactions,
                                        view_name = "intra",
                                        importance_threshold = 0.01,
                                        directed = TRUE) {
  # Filter by view if specified
  if ("view" %in% colnames(interactions)) {
    edges_df <- interactions %>%
      filter(view == view_name, Importance > importance_threshold)
  } else {
    edges_df <- interactions %>%
      filter(Importance > importance_threshold)
  }

  if (nrow(edges_df) == 0) {
    warning("No edges pass the importance threshold")
    return(make_empty_graph(directed = directed))
  }

  # Create graph
  g <- graph_from_data_frame(
    d = data.frame(
      from = edges_df$Predictor,
      to = edges_df$Target,
      weight = edges_df$Importance,
      stringsAsFactors = FALSE
    ),
    directed = directed
  )

  # Add node attributes
  V(g)$name <- V(g)$name

  message(sprintf("Created network: %d nodes, %d edges", vcount(g), ecount(g)))

  return(g)
}


#' Create Multi-View Network
#'
#' Create a combined network from multiple mistyR views.
#'
#' @param interactions mistyR interactions dataframe
#' @param views Vector of view names to include
#' @param importance_threshold Minimum importance threshold
#'
#' @return igraph object with view attribute on edges
#' @export
#'
#' @examples
#' \dontrun{
#' network <- create_multi_view_network(
#'   results$interactions,
#'   views = c("intra", "para.100", "juxta.4")
#' )
#' }
create_multi_view_network <- function(interactions,
                                       views = c("intra"),
                                       importance_threshold = 0.01) {

  # Filter interactions
  edges_df <- interactions %>%
    filter(view %in% views, Importance > importance_threshold)

  if (nrow(edges_df) == 0) {
    warning("No edges pass the threshold")
    return(make_empty_graph())
  }

  # Create edge list with view info
  edge_list <- data.frame(
    from = edges_df$Predictor,
    to = edges_df$Target,
    weight = edges_df$Importance,
    view = edges_df$view,
    stringsAsFactors = FALSE
  )

  # Create graph
  g <- graph_from_data_frame(d = edge_list, directed = TRUE)

  message(sprintf("Multi-view network: %d nodes, %d edges from %d views",
                 vcount(g), ecount(g), length(views)))

  return(g)
}


#' Calculate Network Statistics
#'
#' Calculate comprehensive network statistics.
#'
#' @param g igraph object
#' @param detailed Include detailed statistics (default: TRUE)
#'
#' @return List with network statistics
#' @export
#'
#' @examples
#' \dontrun{
#' stats <- calculate_network_stats(network)
#' print(stats$basic)
#' }
calculate_network_stats <- function(g, detailed = TRUE) {
  # Basic statistics
  basic <- list(
    n_nodes = vcount(g),
    n_edges = ecount(g),
    density = edge_density(g),
    is_directed = is_directed(g),
    is_connected = is_connected(g, mode = "weak"),
    n_components = components(g, mode = "weak")$no,
    diameter = diameter(g, directed = is_directed(g)),
    avg_path_length = mean_distance(g, directed = is_directed(g)),
    transitivity = transitivity(g, type = "global")
  )

  # Degree statistics
  deg <- degree(g, mode = "all")
  in_deg <- if (is_directed(g)) degree(g, mode = "in") else deg
  out_deg <- if (is_directed(g)) degree(g, mode = "out") else deg

  degree_stats <- list(
    mean_degree = mean(deg),
    median_degree = median(deg),
    max_degree = max(deg),
    min_degree = min(deg),
    mean_in_degree = mean(in_deg),
    mean_out_degree = mean(out_deg)
  )

  # Weight statistics
  weights <- E(g)$weight
  weight_stats <- list(
    mean_weight = mean(weights, na.rm = TRUE),
    median_weight = median(weights, na.rm = TRUE),
    max_weight = max(weights, na.rm = TRUE),
    min_weight = min(weights, na.rm = TRUE),
    sd_weight = sd(weights, na.rm = TRUE)
  )

  result <- list(
    basic = basic,
    degree = degree_stats,
    weights = weight_stats
  )

  if (detailed) {
    # Component sizes
    comp <- components(g, mode = "weak")
    result$components <- list(
      sizes = sort(comp$csize, decreasing = TRUE),
      largest_component = max(comp$csize)
    )

    # Degree distribution
    result$degree_distribution <- table(deg)
  }

  return(result)
}


#' Calculate Centrality Metrics
#'
#' Calculate various centrality measures for network nodes.
#'
#' @param g igraph object
#' @param include_all Include all centrality measures (default: TRUE)
#'
#' @return Data frame with centrality scores per node
#' @export
#'
#' @examples
#' \dontrun{
#' centrality <- calculate_centrality(network)
#' head(centrality[order(-centrality$page_rank), ], 10)
#' }
calculate_centrality <- function(g, include_all = TRUE) {
  # Basic centrality measures
  centrality <- data.frame(
    node = V(g)$name,
    degree = degree(g, mode = "all"),
    in_degree = if (is_directed(g)) degree(g, mode = "in") else degree(g),
    out_degree = if (is_directed(g)) degree(g, mode = "out") else degree(g),
    stringsAsFactors = FALSE
  )

  # Weighted degree (strength)
  if (!is.null(E(g)$weight)) {
    centrality$strength <- strength(g, mode = "all", weights = E(g)$weight)
  }

  if (include_all) {
    # Betweenness centrality
    centrality$betweenness <- betweenness(g, directed = is_directed(g))

    # Closeness centrality
    centrality$closeness <- closeness(g, mode = "all")

    # Eigenvector centrality
    tryCatch({
      ev <- eigen_centrality(g, directed = is_directed(g))
      centrality$eigenvector <- ev$vector
    }, error = function(e) {
      centrality$eigenvector <- NA
    })

    # PageRank
    tryCatch({
      centrality$page_rank <- page_rank(g, directed = is_directed(g))$vector
    }, error = function(e) {
      centrality$page_rank <- NA
    })

    # Authority and Hub scores (for directed networks)
    if (is_directed(g)) {
      tryCatch({
        hs <- hub_score(g)
        as <- authority_score(g)
        centrality$hub_score <- hs$vector
        centrality$authority_score <- as$vector
      }, error = function(e) {
        centrality$hub_score <- NA
        centrality$authority_score <- NA
      })
    }
  }

  # Sort by PageRank or degree
  if ("page_rank" %in% colnames(centrality)) {
    centrality <- centrality[order(-centrality$page_rank), ]
  } else {
    centrality <- centrality[order(-centrality$degree), ]
  }

  return(centrality)
}


#' Identify Network Hubs
#'
#' Identify hub nodes based on multiple criteria.
#'
#' @param g igraph object
#' @param method Hub detection method: "degree", "betweenness", "pagerank", "composite"
#' @param top_n Number of top hubs to return
#' @param threshold Percentile threshold for hub classification
#'
#' @return Data frame with hub nodes
#' @export
#'
#' @examples
#' \dontrun{
#' hubs <- identify_network_hubs(network, method = "composite", top_n = 10)
#' }
identify_network_hubs <- function(g,
                                   method = c("composite", "degree", "betweenness", "pagerank"),
                                   top_n = 20,
                                   threshold = 0.9) {
  method <- match.arg(method)

  centrality <- calculate_centrality(g)

  if (method == "degree") {
    hubs <- centrality[order(-centrality$degree), ]
  } else if (method == "betweenness") {
    hubs <- centrality[order(-centrality$betweenness), ]
  } else if (method == "pagerank") {
    hubs <- centrality[order(-centrality$page_rank), ]
  } else {
    # Composite score (normalized sum of multiple centralities)
    cols <- c("degree", "betweenness", "page_rank")
    available_cols <- cols[cols %in% colnames(centrality)]

    if (length(available_cols) >= 2) {
      # Normalize each column to 0-1
      normalized <- as.data.frame(lapply(centrality[available_cols], function(x) {
        if (all(is.na(x))) return(rep(0, length(x)))
        (x - min(x, na.rm = TRUE)) / (max(x, na.rm = TRUE) - min(x, na.rm = TRUE))
      }))

      centrality$composite_score <- rowMeans(normalized, na.rm = TRUE)
      hubs <- centrality[order(-centrality$composite_score), ]
    } else {
      hubs <- centrality[order(-centrality$degree), ]
    }
  }

  # Mark hub status
  n_threshold <- ceiling(nrow(hubs) * (1 - threshold))
  hubs$is_hub <- FALSE
  hubs$is_hub[1:min(top_n, nrow(hubs))] <- TRUE

  return(head(hubs, top_n))
}


#' Extract Network Communities
#'
#' Detect and extract network communities using multiple algorithms.
#'
#' @param g igraph object
#' @param algorithm Community detection algorithm: "louvain", "walktrap", "infomap", "label_prop"
#' @param weights Use edge weights (default: TRUE)
#'
#' @return List with communities and membership
#' @export
#'
#' @examples
#' \dontrun{
#' comm <- extract_network_communities(network, algorithm = "louvain")
#' print(comm$summary)
#' }
extract_network_communities <- function(g,
                                         algorithm = c("louvain", "walktrap", "infomap", "label_prop"),
                                         weights = TRUE) {
  algorithm <- match.arg(algorithm)

  w <- if (weights && !is.null(E(g)$weight)) E(g)$weight else NULL

  # Run community detection
  communities <- switch(algorithm,
    "louvain" = cluster_louvain(as.undirected(g), weights = w),
    "walktrap" = cluster_walktrap(as.undirected(g), weights = w),
    "infomap" = cluster_infomap(g, e.weights = w),
    "label_prop" = cluster_label_prop(as.undirected(g), weights = w)
  )

  # Create membership dataframe
  membership_df <- data.frame(
    node = V(g)$name,
    community = membership(communities),
    stringsAsFactors = FALSE
  )

  # Calculate community statistics
  comm_sizes <- sizes(communities)
  mod <- modularity(communities)

  summary <- list(
    algorithm = algorithm,
    n_communities = length(comm_sizes),
    modularity = mod,
    sizes = as.vector(comm_sizes),
    mean_size = mean(comm_sizes),
    max_size = max(comm_sizes)
  )

  return(list(
    communities = communities,
    membership = membership_df,
    summary = summary
  ))
}


#' Compare Two Networks
#'
#' Compare two networks and identify differences.
#'
#' @param g1 First network
#' @param g2 Second network
#' @param name1 Name for first network
#' @param name2 Name for second network
#'
#' @return List with comparison results
#' @export
#'
#' @examples
#' \dontrun{
#' comparison <- compare_networks(network_control, network_treated)
#' }
compare_networks <- function(g1, g2, name1 = "Network1", name2 = "Network2") {
  # Basic stats comparison
  stats1 <- calculate_network_stats(g1, detailed = FALSE)
  stats2 <- calculate_network_stats(g2, detailed = FALSE)

  comparison <- list(
    stats1 = stats1,
    stats2 = stats2,
    names = c(name1, name2)
  )

  # Node overlap
  nodes1 <- V(g1)$name
  nodes2 <- V(g2)$name
  comparison$node_overlap <- list(
    common = intersect(nodes1, nodes2),
    only_in_1 = setdiff(nodes1, nodes2),
    only_in_2 = setdiff(nodes2, nodes1),
    jaccard = length(intersect(nodes1, nodes2)) / length(union(nodes1, nodes2))
  )

  # Edge overlap (simplified - by node pairs)
  edges1 <- paste(ends(g1, E(g1))[,1], ends(g1, E(g1))[,2], sep = "->")
  edges2 <- paste(ends(g2, E(g2))[,1], ends(g2, E(g2))[,2], sep = "->")
  comparison$edge_overlap <- list(
    common = length(intersect(edges1, edges2)),
    only_in_1 = length(setdiff(edges1, edges2)),
    only_in_2 = length(setdiff(edges2, edges1))
  )

  return(comparison)
}


#' Summarize Network
#'
#' Create a text summary of network properties.
#'
#' @param g igraph object
#' @param communities Community detection result (optional)
#'
#' @return Character string with summary
#' @export
#'
#' @examples
#' \dontrun{
#' cat(summarize_network(network))
#' }
summarize_network <- function(g, communities = NULL) {
  stats <- calculate_network_stats(g)

  lines <- c(
    "=== Network Summary ===",
    "",
    sprintf("Nodes: %d", stats$basic$n_nodes),
    sprintf("Edges: %d", stats$basic$n_edges),
    sprintf("Density: %.4f", stats$basic$density),
    sprintf("Directed: %s", ifelse(stats$basic$is_directed, "Yes", "No")),
    sprintf("Connected: %s", ifelse(stats$basic$is_connected, "Yes", "No")),
    sprintf("Components: %d", stats$basic$n_components),
    sprintf("Diameter: %.0f", stats$basic$diameter),
    sprintf("Avg Path Length: %.2f", stats$basic$avg_path_length),
    sprintf("Transitivity: %.4f", stats$basic$transitivity),
    "",
    sprintf("Mean Degree: %.2f", stats$degree$mean_degree),
    sprintf("Max Degree: %d", stats$degree$max_degree),
    "",
    sprintf("Mean Edge Weight: %.4f", stats$weights$mean_weight),
    sprintf("Weight Range: %.4f - %.4f", stats$weights$min_weight, stats$weights$max_weight)
  )

  if (!is.null(communities)) {
    lines <- c(lines,
      "",
      "=== Communities ===",
      sprintf("Algorithm: %s", communities$summary$algorithm),
      sprintf("Number of Communities: %d", communities$summary$n_communities),
      sprintf("Modularity: %.4f", communities$summary$modularity),
      sprintf("Community Sizes: %s", paste(head(communities$summary$sizes, 5), collapse = ", "))
    )
  }

  return(paste(lines, collapse = "\n"))
}
