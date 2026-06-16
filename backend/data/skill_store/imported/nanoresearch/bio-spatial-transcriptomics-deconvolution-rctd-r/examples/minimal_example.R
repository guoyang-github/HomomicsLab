# Minimal Example: RCTD Deconvolution
# =====================================
#
# Basic workflow for spatial transcriptomics deconvolution using RCTD

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("RCTD Minimal Example\n")
cat("=", rep("=", 70), "\n\n", sep = "")

# -----------------------------------------------------------------------------
# Step 1: Create test data
# -----------------------------------------------------------------------------
cat("[Step 1] Creating test data...\n")

test_data <- create_rctd_test_data(
  n_spots = 100,
  n_genes = 200,
  n_cell_types = 4,
  seed = 42
)

cat(sprintf("  Spatial: %d spots x %d genes\n",
            ncol(test_data$spatial_counts), nrow(test_data$spatial_counts)))
cat(sprintf("  Reference: %d cells (%d types)\n",
            ncol(test_data$reference_counts), length(unique(test_data$cell_types))))

# -----------------------------------------------------------------------------
# Step 2: Validate input
# -----------------------------------------------------------------------------
cat("\n[Step 2] Validating input...\n")

validation <- validate_rctd_input(
  spatial_counts = test_data$spatial_counts,
  spatial_coords = test_data$spatial_coords,
  reference_counts = test_data$reference_counts,
  cell_types = test_data$cell_types
)

cat(sprintf("  Valid: %s\n", validation$valid))
cat(sprintf("  Common genes: %d\n", validation$stats$n_common_genes))
cat(sprintf("  Cell types: %d\n", validation$stats$n_cell_types))

# -----------------------------------------------------------------------------
# Step 3: Get parameter recommendations
# -----------------------------------------------------------------------------
cat("\n[Step 3] Getting parameter recommendations...\n")

params <- recommend_rctd_params(
  n_spots = validation$stats$n_spots,
  n_cell_types = validation$stats$n_cell_types
)

cat(sprintf("  Recommended mode: %s\n", params$doublet_mode))
cat(sprintf("  Recommended cores: %d\n", params$max_cores))

# -----------------------------------------------------------------------------
# Step 4: Run RCTD (commented to avoid dependency requirement)
# -----------------------------------------------------------------------------
cat("\n[Step 4] Running RCTD deconvolution...\n")
cat("  (Commented out in example - requires spacexr package)\n")

# Uncomment to run with actual spacexr package:
# results <- run_rctd(
#   spatial_counts = test_data$spatial_counts,
#   spatial_coords = test_data$spatial_coords,
#   reference_counts = test_data$reference_counts,
#   cell_types = test_data$cell_types,
#   doublet_mode = params$doublet_mode,
#   max_cores = params$max_cores
# )

# -----------------------------------------------------------------------------
# Step 5: Example with mock results
# -----------------------------------------------------------------------------
cat("\n[Step 5] Creating mock results for demonstration...\n")

# Create mock RCTD-like results
mock_props <- matrix(
  runif(400, 0, 1),
  nrow = 100,
  ncol = 4
)
mock_props <- mock_props / rowSums(mock_props)
colnames(mock_props) <- test_data$cell_type_names
rownames(mock_props) <- paste0("spot_", 1:100)

# Summary statistics
cat("\nMock proportion summary:\n")
cat(sprintf("  Mean proportions:\n"))
print(round(colMeans(mock_props), 3))

dominant <- colnames(mock_props)[apply(mock_props, 1, which.max)]
cat(sprintf("\n  Dominant cell types:\n"))
print(table(dominant))

# -----------------------------------------------------------------------------
# Step 6: Export example
# -----------------------------------------------------------------------------
cat("\n[Step 6] Export example...\n")

export_df <- cbind(
  spot = rownames(mock_props),
  test_data$spatial_coords,
  mock_props
)

write.csv(export_df, "minimal_rctd_results.csv", row.names = FALSE)
cat("  Exported: minimal_rctd_results.csv\n")

cat("\n", rep("=", 70), "\n", sep = "")
cat("Minimal example complete!\n")
cat(rep("=", 70), "\n", sep = "")
