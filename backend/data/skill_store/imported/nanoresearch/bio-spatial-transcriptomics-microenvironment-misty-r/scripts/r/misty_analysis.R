# mistyR Microenvironment Analysis Functions
# Provides multi-view spatial modeling pipeline

# Conditionally load packages
if (requireNamespace("mistyR", quietly = TRUE)) {
  library(mistyR)
}
if (requireNamespace("future", quietly = TRUE)) {
  library(future)
}
if (requireNamespace("dplyr", quietly = TRUE)) {
  library(dplyr)
}
if (requireNamespace("igraph", quietly = TRUE)) {
  library(igraph)
}

#' Run complete mistyR pipeline
#'
#' @param expr_matrix Gene expression matrix (genes x spots)
#' @param coords Spatial coordinates matrix (spots x 2)
#' @param para_radius Radius for paraview (default: 100)
#' @param juxta_neighbors k for juxtaview (default: 4)
#' @param n.cv.folds Cross-validation folds (default: 10)
#' @param seed Random seed (default: 42)
#' @return List with mistyR results
#' @export
run_misty_pipeline <- function(expr_matrix, coords,
                                para_radius = 100,
                                juxta_neighbors = 4,
                                n.cv.folds = 10,
                                seed = 42) {

  message("Building mistyR views...")
  views <- build_misty_views(
    expr_matrix, coords,
    para_radius, juxta_neighbors
  )

  message("Running mistyR analysis...")
  misty_res <- run_misty(views, n.cv.folds = n.cv.folds, seed = seed)

  message("Collecting results...")
  results <- collect_results(misty_res)

  message("Done!")
  return(results)
}

#' Build multi-view model for mistyR
#'
#' @param expr_matrix Gene expression matrix (genes x spots)
#' @param coords Spatial coordinates (spots x 2)
#' @param para_radius Neighborhood radius for paraview
#' @param juxta_neighbors Number of neighbors for juxtaview
#' @return mistyR view composition object
#' @export
build_misty_views <- function(expr_matrix, coords,
                              para_radius = 100,
                              juxta_neighbors = 4) {

  # Create intraview (base)
  views <- create_initial_view(expr_matrix)

  # Add paraview (paracrine)
  views <- views %>%
    add_paraview(
      positions = coords,
      radius = para_radius,
      prefix = "para."
    )

  # Add juxtaview (direct contact)
  views <- views %>%
    add_juxtaview(
      positions = coords,
      neighbors = juxta_neighbors,
      prefix = "juxta."
    )

  return(views)
}

#' Extract interaction communities from mistyR results
#'
#' @param interactions mistyR interactions dataframe
#' @param importance_threshold Threshold for edge inclusion (default: 0.01)
#' @return Dataframe with community assignments
#' @export
extract_interaction_communities <- function(interactions,
                                             importance_threshold = 0.01) {

  # Build graph from interactions
  edges <- interactions %>%
    filter(Importance > importance_threshold) %>%
    select(from = Target, to = Predictor, weight = Importance)

  if (nrow(edges) == 0) {
    warning("No edges passed threshold")
    return(data.frame(marker = character(), community = integer()))
  }

  g <- graph_from_data_frame(edges, directed = TRUE)

  # Detect communities
  communities <- cluster_walktrap(g, weights = E(g)$weight)

  # Create result dataframe
  result <- data.frame(
    marker = V(g)$name,
    community = membership(communities)
  )

  return(result)
}

#' Identify hub markers from interaction network
#'
#' @param interactions mistyR interactions dataframe
#' @param importance_threshold Threshold for edges (default: 0.01)
#' @param top_n Return top N hubs (default: 20)
#' @return Dataframe with hub scores
#' @export
identify_hub_markers <- function(interactions,
                                  importance_threshold = 0.01,
                                  top_n = 20) {

  edges <- interactions %>%
    filter(Importance > importance_threshold) %>%
    select(from = Target, to = Predictor, weight = Importance)

  if (nrow(edges) == 0) {
    return(data.frame())
  }

  g <- graph_from_data_frame(edges, directed = TRUE)

  # Calculate centrality metrics
  hub_scores <- data.frame(
    marker = V(g)$name,
    in_degree = degree(g, mode = "in"),
    out_degree = degree(g, mode = "out"),
    betweenness = betweenness(g, weights = E(g)$weight),
    page_rank = page_rank(g, weights = E(g)$weight)$vector
  ) %>%
    arrange(desc(page_rank))

  return(head(hub_scores, top_n))
}

#' Plot view contributions
#'
#' @param results mistyR results list
#' @param top_n Number of top markers to plot (default: 20)
#' @return ggplot object
#' @export
plot_view_contributions <- function(results, top_n = 20) {

  # Get top markers by total importance
  top_markers <- results$importance %>%
    group_by(target) %>%
    summarize(total = sum(Importance), .groups = "drop") %>%
    arrange(desc(total)) %>%
    head(top_n) %>%
    pull(target)

  # Prepare plot data
  plot_data <- results$importance %>%
    filter(target %in% top_markers) %>%
    group_by(target) %>%
    mutate(total_imp = sum(Importance)) %>%
    ungroup() %>%
    mutate(target = factor(target, levels = rev(top_markers)))

  # Create plot
  p <- ggplot(plot_data,
              aes(x = target, y = Importance, fill = view)) +
    geom_bar(stat = "identity", position = "stack") +
    coord_flip() +
    scale_fill_brewer(palette = "Set2") +
    labs(
      x = "Marker",
      y = "Importance",
      fill = "View",
      title = paste("Top", top_n, "Markers by View Contribution")
    ) +
    theme_minimal()

  return(p)
}

#' Plot communication network
#'
#' @param interactions mistyR interactions dataframe
#' @param communities Community assignments (optional)
#' @param min_edge_weight Minimum edge weight to include (default: 0.01)
#' @param output_file Output file path (optional)
#' @export
plot_communication_network <- function(interactions,
                                        communities = NULL,
                                        min_edge_weight = 0.01,
                                        output_file = NULL) {

  edges <- interactions %>%
    filter(Importance > min_edge_weight) %>%
    select(from = Target, to = Predictor, weight = Importance)

  g <- graph_from_data_frame(edges, directed = TRUE)

  # Add community colors if provided
  if (!is.null(communities)) {
    V(g)$community <- communities$community[
      match(V(g)$name, communities$marker)
    ]
    vertex_color <- V(g)$community
  } else {
    vertex_color <- "lightblue"
  }

  # Create layout
  set.seed(42)
  layout <- layout_with_fr(g, weights = E(g)$weight)

  if (!is.null(output_file)) {
    png(output_file, width = 1200, height = 1200, res = 150)
  }

  plot(g,
       layout = layout,
       vertex.color = vertex_color,
       vertex.size = 5,
       vertex.label.cex = 0.6,
       vertex.label.dist = 1,
       edge.width = E(g)$weight * 5,
       edge.arrow.size = 0.3,
       edge.color = "gray70",
       main = "Spatial Communication Network")

  if (!is.null(output_file)) {
    dev.off()
    message("Network plot saved to: ", output_file)
  }
}

#' Compare view contributions between conditions
#'
#' @param results_list Named list of mistyR results
#' @return List with summary dataframe and ggplot
#' @export
compare_view_contributions <- function(results_list) {

  comparison <- lapply(names(results_list), function(cond) {
    results_list[[cond]]$importance %>%
      mutate(condition = cond)
  }) %>% bind_rows()

  summary <- comparison %>%
    group_by(condition, view) %>%
    summarize(mean_importance = mean(Importance, na.rm = TRUE),
              .groups = "drop")

  p <- ggplot(summary, aes(x = condition, y = mean_importance, fill = view)) +
    geom_bar(stat = "identity", position = "dodge") +
    scale_fill_brewer(palette = "Set2") +
    labs(x = "Condition", y = "Mean Importance", fill = "View") +
    theme_minimal()

  return(list(summary = summary, plot = p))
}

#' Export mistyR results to CSV files
#'
#' @param results mistyR results list
#' @param output_prefix Output file prefix
#' @export
export_misty_results <- function(results, output_prefix = "misty_results") {

  write.csv(results$importance,
            paste0(output_prefix, "_importance.csv"),
            row.names = FALSE)

  write.csv(results$improvements,
            paste0(output_prefix, "_improvements.csv"),
            row.names = FALSE)

  write.csv(results$interactions,
            paste0(output_prefix, "_interactions.csv"),
            row.names = FALSE)

  message("Results exported to: ", output_prefix, "*.csv")
}
