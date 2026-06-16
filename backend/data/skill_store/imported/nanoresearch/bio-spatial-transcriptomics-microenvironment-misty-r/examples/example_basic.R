#!/usr/bin/env Rscript
#' Basic mistyR microenvironment analysis example
#'
#' Demonstrates complete mistyR workflow with network analysis and Cytoscape export.
#'
#' @author Yang Guo
#' @date 2026-04-01

library(mistyR)
library(SpatialExperiment)
library(future)
library(igraph)

# Enable parallel processing
plan(multisession, workers = 4)

# Load all mistyR scripts
source("../scripts/r/misty_analysis.R")
source("../scripts/r/misty_network.R")
source("../scripts/r/misty_layouts.R")
source("../scripts/r/misty_cytoscape.R")

print("=== mistyR Microenvironment Analysis with Network Export ===")
print(paste(rep("=", 60), collapse = ""))

# Create example spatial data
set.seed(42)
n_spots <- 100
n_genes <- 50

expr <- matrix(rnorm(n_spots * n_genes), nrow = n_genes)
coords <- matrix(runif(n_spots * 2, 0, 100), ncol = 2)

rownames(expr) <- paste0("Gene", 1:n_genes)
colnames(expr) <- paste0("Spot", 1:n_spots)

print("\n1. Build mistyR views:")
views <- build_misty_views(
  expr_matrix = expr,
  coords = coords,
  para_radius = 20,
  juxta_neighbors = 4
)
print(views)

print("\n2. Run MISTy analysis:")
# misty_res <- run_misty(views, n.cv.folds = 10, seed = 42)
# results <- collect_results(misty_res)

print("\n   (Skipping actual mistyR run - requires real data)")
print("   See below for network analysis with synthetic interactions")

# Create synthetic interaction data for demonstration
print("\n3. Creating synthetic network for demonstration:")
set.seed(42)
n_nodes <- 30

# Create random graph with weights
edges <- data.frame(
  Predictor = sample(paste0("Gene", 1:20), 50, replace = TRUE),
  Target = sample(paste0("Gene", 1:20), 50, replace = TRUE),
  Importance = runif(50, 0.01, 0.5),
  view = sample(c("intra", "para.20", "juxta.4"), 50, replace = TRUE),
  stringsAsFactors = FALSE
)

# Remove self-loops
edges <- edges[edges$Predictor != edges$Target, ]
edges <- edges[!duplicated(edges[, c("Predictor", "Target")]), ]

print(sprintf("   Created %d edges", nrow(edges)))

print("\n4. Create interaction network:")
network <- create_interaction_network(
  edges,
  view_name = "para.20",
  importance_threshold = 0.05
)
print(sprintf("   Network: %d nodes, %d edges", vcount(network), ecount(network)))

print("\n5. Calculate network statistics:")
stats <- calculate_network_stats(network)
print("   Basic statistics:")
print(sprintf("     - Nodes: %d", stats$basic$n_nodes))
print(sprintf("     - Edges: %d", stats$basic$n_edges))
print(sprintf("     - Density: %.4f", stats$basic$density))
print(sprintf("     - Diameter: %d", stats$basic$diameter))

print("\n6. Calculate centrality:")
centrality <- calculate_centrality(network)
print("   Top 5 nodes by PageRank:")
top_nodes <- head(centrality[order(-centrality$page_rank), c("node", "page_rank", "betweenness")], 5)
print(top_nodes)

print("\n7. Identify hubs:")
hubs <- identify_network_hubs(network, method = "composite", top_n = 10)
print(sprintf("   Identified %d hub nodes", nrow(hubs)))
print("   Top 5 hubs:")
print(head(hubs[, c("node", "composite_score", "degree")], 5))

print("\n8. Extract communities:")
communities <- extract_network_communities(network, algorithm = "louvain")
print(sprintf("   Found %d communities (modularity: %.3f)",
              communities$summary$n_communities,
              communities$summary$modularity))
print("   Community sizes:")
print(table(communities$membership$community))

print("\n9. Apply layouts:")
layout_fr <- apply_layout(network, method = "fr")
layout_kk <- apply_layout(network, method = "kk")
layout_comm <- layout_with_communities(network, communities$communities)
print("   Applied: FR, KK, and community-aware layouts")

print("\n10. Export to Cytoscape:")
# Prepare node attributes
node_attrs <- data.frame(
  node = V(network)$name,
  degree = degree(network),
  betweenness = betweenness(network),
  page_rank = page_rank(network)$vector,
  community = communities$membership$community[
    match(V(network)$name, communities$membership$node)
  ],
  is_hub = V(network)$name %in% hubs$node,
  stringsAsFactors = FALSE
)

# Create output directory
dir.create("output", showWarnings = FALSE)

# Export
files <- export_complete_cytoscape(
  network,
  output_prefix = "output/misty_example",
  node_attrs = node_attrs,
  layout = layout_comm,
  communities = communities,
  create_style = TRUE,
  create_script = TRUE
)

print("\n   Exported files:")
for (name in names(files)) {
  print(sprintf("     - %s: %s", name, files[[name]]))
}

print("\n11. Network summary:")
cat(summarize_network(network, communities))

print("\n" + paste(rep("=", 60), collapse = ""))
print("Analysis complete!")
print("\nNext steps:")
print("  1. Open Cytoscape")
print("  2. Import: output/misty_example.graphml")
print("  3. Import style: output/misty_example_style.xml")
print("  4. Apply layout and customize visualization")
print("\nSee CYTOSCAPE_GUIDE.md for detailed instructions")

plan(sequential)  # Clean up
