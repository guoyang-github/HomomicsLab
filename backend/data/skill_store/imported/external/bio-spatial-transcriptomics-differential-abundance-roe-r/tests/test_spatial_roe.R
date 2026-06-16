# Spatial Ro/e Analysis Tests
# Test suite for bio-spatial-transcriptomics-differential-abundance-roe-r skill

library(testthat)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source functions
source(file.path(script_dir, "spatial_roe_analysis.R"))
source(file.path(script_dir, "spatial_roe_visualization.R"))

context("Spatial Ro/e Co-occurrence Analysis")

# Create test data
create_test_spatial_data <- function() {
  set.seed(42)

  # Create 100 spots in a grid
  n_spots <- 100
  x <- rep(1:10, each = 10) * 100
  y <- rep(1:10, 10) * 100

  coords <- data.frame(x = x, y = y)

  # Create cell type patterns:
  # - Type A clusters in top-left (spots 1-25)
  # - Type B clusters in bottom-right (spots 76-100)
  # - Type C is randomly distributed
  # - Type D co-occurs with Type A

  cell_types <- c(
    rep("Type_A", 20), rep("Type_D", 5),   # Top-left cluster (with D co-occurring)
    rep("Type_A", 10), rep("Type_C", 10),  # Mixed
    rep("Type_C", 20),                     # Random
    rep("Type_C", 10), rep("Type_B", 10),  # Mixed
    rep("Type_B", 15),                     # Bottom-right cluster
    rep("Type_C", 10)
  )

  list(cell_types = cell_types, coords = coords)
}

test_that("calculate_spatial_roe returns correct structure", {
  test_data <- create_test_spatial_data()

  result <- calculate_spatial_roe(
    cell_types = test_data$cell_types,
    coords = test_data$coords,
    method = "radius",
    radius = 150
  )

  expect_s3_class(result, "spatial_roe_result")
  expect_named(result, c("roe", "observed", "expected", "neighbors", "statistics",
                         "method", "radius", "k", "n_spots", "n_cell_types",
                         "cell_type_names"))

  expect_equal(result$n_spots, 100)
  expect_equal(result$n_cell_types, 4)
  expect_equal(result$method, "radius")
  expect_equal(result$radius, 150)
})

test_that("radius neighborhood building works correctly", {
  coords <- data.frame(x = c(0, 100, 200), y = c(0, 0, 0))
  rownames(coords) <- c("A", "B", "C")

  neighbors <- build_radius_neighbors(coords, radius = 150, min_neighbors = 1)

  expect_equal(length(neighbors), 3)
  expect_equal(neighbors[["A"]], 2)  # B is within 150 of A
  expect_equal(neighbors[["B"]], c(1, 3))  # A and C within 150 of B
  expect_equal(neighbors[["C"]], 2)  # B is within 150 of C
})

test_that("knn neighborhood building works correctly", {
  coords <- data.frame(x = 1:10, y = rep(0, 10))
  rownames(coords) <- paste0("spot", 1:10)

  neighbors <- build_knn_neighbors(coords, k = 3, min_neighbors = 1)

  expect_equal(length(neighbors), 10)
  expect_equal(length(neighbors[[1]]), 3)  # Should have 3 neighbors
})

test_that("calculate_cooccurrence produces expected patterns", {
  test_data <- create_test_spatial_data()

  # Create one-hot matrix
  type_names <- unique(test_data$cell_types)
  type_matrix <- matrix(0, nrow = length(test_data$cell_types), ncol = length(type_names))
  colnames(type_matrix) <- type_names
  for (i in seq_along(type_names)) {
    type_matrix[, i] <- as.numeric(test_data$cell_types == type_names[i])
  }

  # Build neighbors
  neighbors <- build_radius_neighbors(test_data$coords, radius = 150, min_neighbors = 1)

  # Calculate co-occurrence
  cooccur <- calculate_cooccurrence(type_matrix, neighbors, method = "mean")

  expect_equal(nrow(cooccur), 4)
  expect_equal(ncol(cooccur), 4)
  expect_true(all(cooccur >= 0 & cooccur <= 1))
})

test_that("spatial Ro/e detects co-localization patterns", {
  test_data <- create_test_spatial_data()

  result <- calculate_spatial_roe(
    cell_types = test_data$cell_types,
    coords = test_data$coords,
    method = "radius",
    radius = 200
  )

  # Type_A and Type_D should co-localize (designed pattern)
  roe_ad <- result$roe["Type_A", "Type_D"]
  expect_gt(roe_ad, 1.0)  # Should be enriched

  # Type_A and Type_B should not co-localize (separate clusters)
  roe_ab <- result$roe["Type_A", "Type_B"]
  expect_lt(roe_ab, 1.0)  # Should be depleted
})

test_that("knn method produces valid results", {
  test_data <- create_test_spatial_data()

  result <- calculate_spatial_roe(
    cell_types = test_data$cell_types,
    coords = test_data$coords,
    method = "knn",
    k = 5
  )

  expect_s3_class(result, "spatial_roe_result")
  expect_equal(result$method, "knn")
  expect_equal(result$k, 5)
  expect_false(any(is.infinite(result$roe)))
})

test_that("spatial_roe_to_dataframe returns correct structure", {
  test_data <- create_test_spatial_data()

  result <- calculate_spatial_roe(
    cell_types = test_data$cell_types,
    coords = test_data$coords,
    method = "radius",
    radius = 150
  )

  df <- spatial_roe_to_dataframe(result)

  expect_s3_class(df, "data.frame")
  expect_true(all(c("cell_type_a", "cell_type_b", "roe", "observed",
                    "expected", "p_value_adj", "significant", "interaction") %in%
                    colnames(df)))

  # Should have n_types^2 rows
  expect_equal(nrow(df), 4 * 4)
})

test_that("plot functions return ggplot objects", {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    skip("ggplot2 not available")
  }

  test_data <- create_test_spatial_data()

  result <- calculate_spatial_roe(
    cell_types = test_data$cell_types,
    coords = test_data$coords,
    method = "radius",
    radius = 150
  )

  p_heatmap <- plot_spatial_roe_heatmap(result)
  expect_s3_class(p_heatmap, "ggplot")

  p_lollipop <- plot_spatial_roe_lollipop(result, n_top = 5)
  expect_s3_class(p_lollipop, "ggplot")

  p_map <- plot_neighborhood_map(result, test_data$coords)
  expect_s3_class(p_map, "ggplot")
})

test_that("plot_spatial_roe_network works with sufficient data", {
  if (!requireNamespace("ggraph", quietly = TRUE)) {
    skip("ggraph not available")
  }

  test_data <- create_test_spatial_data()

  result <- calculate_spatial_roe(
    cell_types = test_data$cell_types,
    coords = test_data$coords,
    method = "radius",
    radius = 200
  )

  # Should create network if there are edges
  p_network <- plot_spatial_roe_network(result, min_roe = 1.2)

  if (!is.null(p_network)) {
    expect_s3_class(p_network, "ggplot")
  }
})

test_that("print.spatial_roe_result works correctly", {
  test_data <- create_test_spatial_data()

  result <- calculate_spatial_roe(
    cell_types = test_data$cell_types,
    coords = test_data$coords,
    method = "radius",
    radius = 150
  )

  expect_output(print(result), "Spatial Ro/e Co-occurrence Analysis")
  expect_output(print(result), "radius")
  expect_output(print(result), "100")  # n_spots
})

test_that("handles proportion matrix input", {
  test_data <- create_test_spatial_data()

  # Convert to proportions (simulate deconvolution output)
  n_spots <- length(test_data$cell_types)
  prop_matrix <- matrix(runif(n_spots * 4), nrow = n_spots, ncol = 4)
  prop_matrix <- prop_matrix / rowSums(prop_matrix)  # Normalize to sum to 1
  colnames(prop_matrix) <- c("Type_A", "Type_B", "Type_C", "Type_D")

  result <- calculate_spatial_roe(
    cell_types = prop_matrix,
    coords = test_data$coords,
    method = "radius",
    radius = 150
  )

  expect_s3_class(result, "spatial_roe_result")
  expect_equal(result$n_cell_types, 4)
})

test_that("handles edge cases gracefully", {
  # Single cell type
  coords <- data.frame(x = 1:10, y = 1:10)
  result <- calculate_spatial_roe(
    cell_types = rep("A", 10),
    coords = coords,
    method = "knn",
    k = 3
  )
  expect_equal(result$n_cell_types, 1)

  # Sparse data
  coords <- data.frame(x = c(0, 1000), y = c(0, 1000))
  result <- calculate_spatial_roe(
    cell_types = c("A", "B"),
    coords = coords,
    method = "radius",
    radius = 100
  )
  # Should have 0 valid neighborhoods (min_neighbors = 3 default)
  valid_neighbors <- sum(sapply(result$neighbors, length) > 0)
  expect_equal(valid_neighbors, 0)
})

# Run tests
if (identical(Sys.getenv("R_TESTS"), "")) {
  test_results <- test_dir(dirname(sys.frame(1)$ofile))
}
