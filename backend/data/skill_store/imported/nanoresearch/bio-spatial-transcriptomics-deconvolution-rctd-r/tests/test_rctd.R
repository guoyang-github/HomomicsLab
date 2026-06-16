# Unit Tests for RCTD Deconvolution Skill
# =======================================
#
# Comprehensive test suite for RCTD wrapper functions

library(testthat)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/utils.R")

# =============================================================================
# Test Core Analysis Functions
# =============================================================================

test_that("check_rctd_dependencies works", {
  result <- check_rctd_dependencies()
  expect_type(result, "logical")
})

test_that("validate_rctd_input validates correctly", {
  # Create test data
  n_spots <- 50
  n_genes <- 100
  n_cells <- 100

  spatial_counts <- matrix(rpois(n_genes * n_spots, 5), nrow = n_genes)
  spatial_coords <- data.frame(x = 1:n_spots, y = 1:n_spots)
  reference_counts <- matrix(rpois(n_genes * n_cells, 5), nrow = n_genes)
  cell_types <- factor(rep(c("A", "B"), each = 50))

  colnames(spatial_counts) <- paste0("spot_", 1:n_spots)
  colnames(reference_counts) <- paste0("cell_", 1:n_cells)
  rownames(spatial_counts) <- rownames(reference_counts) <- paste0("gene_", 1:n_genes)
  names(cell_types) <- colnames(reference_counts)

  # Valid input
  result <- validate_rctd_input(spatial_counts, spatial_coords, reference_counts, cell_types)
  expect_true(result$valid)
  expect_equal(result$stats$n_spots, n_spots)
  expect_equal(result$stats$n_cell_types, 2)

  # Invalid: mismatched dimensions
  bad_coords <- data.frame(x = 1:10, y = 1:10)
  result <- validate_rctd_input(spatial_counts, bad_coords, reference_counts, cell_types)
  expect_false(result$valid)
  expect_true(length(result$errors) > 0)

  # Invalid: no common genes
  bad_ref <- reference_counts
  rownames(bad_ref) <- paste0("other_", 1:n_genes)
  result <- validate_rctd_input(spatial_counts, spatial_coords, bad_ref, cell_types)
  expect_false(result$valid)
})

test_that("create_rctd_test_data works", {
  test_data <- create_rctd_test_data(
    n_spots = 50,
    n_genes = 100,
    n_cell_types = 3,
    seed = 42
  )

  expect_type(test_data, "list")
  expect_true("spatial_counts" %in% names(test_data))
  expect_true("spatial_coords" %in% names(test_data))
  expect_true("reference_counts" %in% names(test_data))
  expect_true("cell_types" %in% names(test_data))

  expect_equal(ncol(test_data$spatial_counts), 50)
  expect_equal(nrow(test_data$spatial_counts), 100)
})

test_that("extract_proportions_rctd works with mock data", {
  # Create mock RCTD-like object
  mock_props <- matrix(runif(200), nrow = 50, ncol = 4)
  colnames(mock_props) <- c("A", "B", "C", "D")

  mock_RCTD <- list(
    results = list(weights = as(mock_props, "dgCMatrix")),
    config = list(doublet_mode = "full"),
    cell_type_info = list(renorm = list(NULL, colnames(mock_props), ncol(mock_props))),
    spatialRNA = list(coords = data.frame(x = 1:50, y = 1:50))
  )
  class(mock_RCTD) <- "RCTD"

  result <- extract_proportions_rctd(mock_RCTD)

  expect_s3_class(result, "data.frame")
  expect_equal(ncol(result), 4)
  expect_equal(nrow(result), 50)

  # Check normalization
  expect_true(all(abs(rowSums(result) - 1) < 1e-10))
})

test_that("summarize_rctd_results works", {
  mock_props <- matrix(runif(200), nrow = 50, ncol = 4)
  mock_props <- mock_props / rowSums(mock_props)
  colnames(mock_props) <- c("A", "B", "C", "D")

  mock_RCTD <- list(
    results = list(weights = as(mock_props, "dgCMatrix")),
    config = list(doublet_mode = "full", max_cores = 4, gene_cutoff = 0.000125, fc_cutoff = 0.5),
    cell_type_info = list(renorm = list(NULL, colnames(mock_props), ncol(mock_props))),
    spatialRNA = list(counts = matrix(0, nrow = 10, ncol = 50))
  )
  class(mock_RCTD) <- "RCTD"

  summary <- summarize_rctd_results(mock_RCTD)

  expect_type(summary, "list")
  expect_equal(summary$n_spots, 50)
  expect_equal(summary$n_cell_types, 4)
  expect_true("mean_proportions" %in% names(summary))
  expect_true("dominant_cell_types" %in% names(summary))
})

test_that("get_top_cell_types works", {
  mock_props <- matrix(c(0.5, 0.3, 0.2, 0.1, 0.7, 0.2), nrow = 2, byrow = TRUE)
  colnames(mock_props) <- c("A", "B", "C")
  rownames(mock_props) <- c("spot1", "spot2")

  mock_RCTD <- list(
    results = list(weights = as(mock_props, "dgCMatrix")),
    config = list(doublet_mode = "full")
  )
  class(mock_RCTD) <- "RCTD"

  result <- get_top_cell_types(mock_RCTD, n_top = 2)

  expect_s3_class(result, "data.frame")
  expect_equal(nrow(result), 4)  # 2 spots x 2 top types
  expect_true("spot" %in% colnames(result))
  expect_true("rank" %in% colnames(result))
  expect_true("cell_type" %in% colnames(result))
  expect_true("proportion" %in% colnames(result))
})

test_that("recommend_rctd_params works", {
  params <- recommend_rctd_params(n_spots = 1000, n_cell_types = 5)

  expect_type(params, "list")
  expect_true("max_cores" %in% names(params))
  expect_true("doublet_mode" %in% names(params))
  expect_true("gene_cutoff" %in% names(params))

  expect_true(params$max_cores >= 1)
  expect_true(params$doublet_mode %in% c("doublet", "full"))
})

test_that("export_rctd_results creates files", {
  mock_props <- matrix(runif(40), nrow = 10, ncol = 4)
  colnames(mock_props) <- c("A", "B", "C", "D")

  mock_RCTD <- list(
    results = list(
      weights = as(mock_props, "dgCMatrix"),
      weights_doublet = as(mock_props, "dgCMatrix")
    ),
    config = list(doublet_mode = "doublet", max_cores = 4, gene_cutoff = 0.000125, fc_cutoff = 0.5),
    cell_type_info = list(renorm = list(NULL, colnames(mock_props), ncol(mock_props))),
    spatialRNA = list(counts = matrix(0, nrow = 5, ncol = 10))
  )
  class(mock_RCTD) <- "RCTD"

  temp_dir <- tempdir()
  export_rctd_results(mock_RCTD, temp_dir, prefix = "test", export_object = FALSE)

  expect_true(file.exists(file.path(temp_dir, "test_proportions.csv")))
  expect_true(file.exists(file.path(temp_dir, "test_top_cell_types.csv")))
  expect_true(file.exists(file.path(temp_dir, "test_doublet_predictions.csv")))
})

test_that("create_rctd_report generates report", {
  mock_props <- matrix(runif(40), nrow = 10, ncol = 4)
  mock_props <- mock_props / rowSums(mock_props)
  colnames(mock_props) <- c("A", "B", "C", "D")

  mock_RCTD <- list(
    results = list(weights = as(mock_props, "dgCMatrix")),
    config = list(doublet_mode = "full", max_cores = 4, gene_cutoff = 0.000125, fc_cutoff = 0.5),
    cell_type_info = list(renorm = list(NULL, colnames(mock_props), ncol(mock_props))),
    spatialRNA = list(counts = matrix(0, nrow = 5, ncol = 10))
  )
  class(mock_RCTD) <- "RCTD"

  report <- create_rctd_report(mock_RCTD)

  expect_type(report, "character")
  expect_true(grepl("RCTD Deconvolution Analysis Report", report))
})

# =============================================================================
# Test Utility Functions
# =============================================================================

test_that("calculate_proportion_entropy works", {
  mock_props <- matrix(c(0.8, 0.1, 0.1, 0.33, 0.33, 0.34), nrow = 2, byrow = TRUE)
  colnames(mock_props) <- c("A", "B", "C")

  mock_RCTD <- list(
    results = list(weights = as(mock_props, "dgCMatrix")),
    config = list(doublet_mode = "full")
  )
  class(mock_RCTD) <- "RCTD"

  entropy <- calculate_proportion_entropy(mock_RCTD, normalized = TRUE)

  expect_type(entropy, "double")
  expect_equal(length(entropy), 2)
  # First spot should have lower entropy (more pure)
  expect_true(entropy[1] < entropy[2])
})

test_that("get_high_purity_spots works", {
  mock_props <- matrix(c(0.9, 0.05, 0.05, 0.4, 0.3, 0.3), nrow = 2, byrow = TRUE)
  colnames(mock_props) <- c("A", "B", "C")
  rownames(mock_props) <- c("spot1", "spot2")

  mock_RCTD <- list(
    results = list(weights = as(mock_props, "dgCMatrix")),
    config = list(doublet_mode = "full")
  )
  class(mock_RCTD) <- "RCTD"

  pure_spots <- get_high_purity_spots(mock_RCTD, purity_threshold = 0.8)

  expect_equal(length(pure_spots), 1)
  expect_equal(pure_spots[1], "spot1")
})

test_that("compare_rctd_results works", {
  # Create mock RCTD objects
  mock_props1 <- matrix(runif(40), nrow = 10, ncol = 4)
  mock_props2 <- matrix(runif(40), nrow = 10, ncol = 4)
  colnames(mock_props1) <- colnames(mock_props2) <- c("A", "B", "C", "D")

  RCTD_list <- list(
    Sample1 = structure(list(
      results = list(weights = as(mock_props1, "dgCMatrix")),
      config = list(doublet_mode = "full")
    ), class = "RCTD"),
    Sample2 = structure(list(
      results = list(weights = as(mock_props2, "dgCMatrix")),
      config = list(doublet_mode = "full")
    ), class = "RCTD")
  )

  result <- compare_rctd_results(RCTD_list)

  expect_s3_class(result, "data.frame")
  expect_equal(nrow(result), 8)  # 2 samples x 4 cell types
  expect_true("sample" %in% colnames(result))
  expect_true("cell_type" %in% colnames(result))
})

# =============================================================================
# Integration Test
# =============================================================================

test_that("complete workflow runs without errors", {
  # Create test data
  test_data <- create_rctd_test_data(
    n_spots = 30,
    n_genes = 50,
    n_cell_types = 3,
    seed = 42
  )

  # Validate
  validation <- validate_rctd_input(
    test_data$spatial_counts,
    test_data$spatial_coords,
    test_data$reference_counts,
    test_data$cell_types
  )
  expect_true(validation$valid)

  # Mock run results
  mock_props <- matrix(runif(90), nrow = 30, ncol = 3)
  mock_props <- mock_props / rowSums(mock_props)
  colnames(mock_props) <- c("CellType1", "CellType2", "CellType3")

  mock_RCTD <- list(
    results = list(weights = as(mock_props, "dgCMatrix")),
    config = list(doublet_mode = "doublet", max_cores = 4, gene_cutoff = 0.000125, fc_cutoff = 0.5),
    cell_type_info = list(renorm = list(NULL, colnames(mock_props), 3)),
    spatialRNA = list(counts = matrix(0, nrow = 5, ncol = 30))
  )
  class(mock_RCTD) <- "RCTD"

  # Extract and summarize
  props <- extract_proportions_rctd(mock_RCTD)
  summary <- summarize_rctd_results(mock_RCTD)

  expect_equal(nrow(props), 30)
  expect_equal(summary$n_spots, 30)
})
