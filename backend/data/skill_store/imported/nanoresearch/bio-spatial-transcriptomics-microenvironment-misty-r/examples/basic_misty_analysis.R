# Basic mistyR microenvironment analysis example

library(mistyR)
library(SpatialExperiment)
library(future)

# Enable parallel processing
plan(multisession, workers = 4)

# Create example spatial data
set.seed(42)
n_spots <- 100
n_genes <- 50

expr <- matrix(rnorm(n_spots * n_genes), nrow = n_genes)
coords <- matrix(runif(n_spots * 2, 0, 100), ncol = 2)

print("mistyR Microenvironment Analysis")
print(paste(rep("=", 40), collapse = ""))

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

print("\n3. Collect results:")
# results <- collect_results(misty_res)

print("\n4. Extract communities:")
# communities <- extract_interaction_communities(results$interactions)

print("\n5. Identify hub markers:")
# hubs <- identify_hub_markers(results$interactions)

print("\nNote: Uncomment code above to run actual analysis")
print("Requires mistyR package and sufficient memory")

# Plot results
# plot_view_contributions(results, top_n = 20)
# plot_communication_network(results$interactions)

plan(sequential)  # Clean up
