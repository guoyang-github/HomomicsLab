# Unit Tests for diffcyt Differential Analysis Skill
# ==================================================
#
# Comprehensive test suite for the diffcyt wrapper functions

library(testthat)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# Skip tests if diffcyt is not installed
if (!requireNamespace("diffcyt", quietly = TRUE)) {
  skip("diffcyt not installed")
}

# =============================================================================
# Test Core Analysis Functions
# =============================================================================

test_that("check_diffcyt_dependencies works", {
  skip_if_not_installed("diffcyt")

  expect_true(check_diffcyt_dependencies())
})

test_that("validate_diffcyt_input validates correctly", {
  # Create test data
  d_input <- list(
    sample1 = matrix(rnorm(1000), nrow = 100, ncol = 10),
    sample2 = matrix(rnorm(1000), nrow = 100, ncol = 10)
  )

  experiment_info <- data.frame(
    sample_id = factor(c("sample1", "sample2")),
    group_id = factor(c("A", "B"))
  )

  marker_info <- data.frame(
    marker_name = paste0("marker", 1:10),
    marker_class = factor(c(rep("type", 5), rep("state", 5)))
  )

  # Valid input
  result <- validate_diffcyt_input(d_input, experiment_info, marker_info)
  expect_true(result$valid)
  expect_false(result$is_catalyst)

  # Missing experiment_info
  expect_error(
    validate_diffcyt_input(d_input, NULL, marker_info),
    "experiment_info.*must be provided"
  )

  # Missing sample_id column
  bad_exp_info <- data.frame(group_id = factor(c("A", "B")))
  expect_error(
    validate_diffcyt_input(d_input, bad_exp_info, marker_info),
    "sample_id"
  )
})

test_that("create_experiment_info works", {
  sample_ids <- c("s1", "s2", "s3", "s4")
  group_ids <- c("A", "A", "B", "B")

  exp_info <- create_experiment_info(sample_ids, group_ids)

  expect_equal(nrow(exp_info), 4)
  expect_equal(exp_info$sample_id, factor(sample_ids))
  expect_equal(exp_info$group_id, factor(group_ids))
})

test_that("create_marker_info works", {
  marker_names <- paste0("marker", 1:10)
  marker_classes <- c(rep("type", 5), rep("state", 5))

  marker_info <- create_marker_info(marker_names, marker_classes)

  expect_equal(nrow(marker_info), 10)
  expect_equal(marker_info$marker_name, marker_names)
  expect_equal(as.character(marker_info$marker_class), marker_classes)

  # Invalid marker class
  expect_error(
    create_marker_info(marker_names, c(rep("invalid", 10))),
    "marker_classes must be one of"
  )
})

test_that("create_test_data generates valid data", {
  test_data <- create_test_data(
    n_samples = 4,
    n_cells_per_sample = 100,
    n_markers = 10,
    seed = 123
  )

  expect_equal(length(test_data$d_input), 4)
  expect_equal(nrow(test_data$experiment_info), 4)
  expect_equal(nrow(test_data$marker_info), 10)
  expect_equal(ncol(test_data$d_input[[1]]), 10)
})

test_that("summarize_results calculates correct statistics", {
  skip_if_not_installed("SummarizedExperiment")
  skip_if_not_installed("S4Vectors")

  # Create mock results
  mock_res <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = matrix(1:100, nrow = 10)),
    rowData = data.frame(
      cluster_id = 1:10,
      logFC = c(1, -1, 2, -2, 0.5, -0.5, 3, -3, 0.1, -0.1),
      p_adj = c(0.001, 0.01, 0.05, 0.1, 0.5, 0.6, 0.0001, 0.02, 0.8, 0.9)
    )
  )

  summary <- summarize_results(mock_res, p_threshold = 0.05)

  expect_equal(summary$n_total, 10)
  expect_equal(summary$n_significant, 4)  # p < 0.05
  expect_equal(summary$n_upregulated, 2)   # p < 0.05 & logFC > 0
  expect_equal(summary$n_downregulated, 2) # p < 0.05 & logFC < 0
})

test_that("get_significant_clusters identifies correct clusters", {
  skip_if_not_installed("SummarizedExperiment")

  mock_res <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = matrix(1:100, nrow = 10)),
    rowData = data.frame(
      cluster_id = 1:10,
      logFC = rnorm(10),
      p_adj = c(0.001, 0.01, 0.05, 0.1, 0.5, 0.6, 0.0001, 0.02, 0.8, 0.9)
    )
  )

  sig_clusters <- get_significant_clusters(mock_res, p_threshold = 0.05)

  expect_equal(length(sig_clusters), 4)
  expect_true(all(sig_clusters %in% c(1, 2, 3, 7)))
})

test_that("compare_two_groups calculates fold changes correctly", {
  skip_if_not_installed("SummarizedExperiment")

  counts <- matrix(
    c(10, 20, 30,  # cluster 1
      40, 50, 60,  # cluster 2
      5,  10, 15,  # cluster 3
      20, 25, 30), # cluster 4
    nrow = 4, byrow = TRUE
  )
  colnames(counts) <- c("s1", "s2", "s3")
  rownames(counts) <- c("c1", "c2", "c3", "c4")

  d_counts <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = counts)
  )

  result <- compare_two_groups(d_counts, group1 = c("s1", "s2"), group2 = "s3")

  expect_equal(nrow(result), 4)
  expect_equal(result$cluster_id, c("c1", "c2", "c3", "c4"))
  expect_true(all(result$logFC != 0))
})

test_that("subsample_cells works correctly", {
  d_input <- list(
    sample1 = matrix(rnorm(1000), nrow = 100, ncol = 10),
    sample2 = matrix(rnorm(500), nrow = 50, ncol = 10)
  )

  # Subsample to 30 cells
  subsampled <- subsample_cells(d_input, n_sub = 30, seed = 123)

  expect_equal(nrow(subsampled[[1]]), 30)
  expect_equal(nrow(subsampled[[2]]), 30)

  # No subsampling if n < n_sub
  subsampled2 <- subsample_cells(d_input, n_sub = 200, seed = 123)
  expect_equal(nrow(subsampled2[[1]]), 100)
  expect_equal(nrow(subsampled2[[2]]), 50)
})

test_that("normalize_counts produces valid output", {
  skip_if_not_installed("edgeR")
  skip_if_not_installed("SummarizedExperiment")

  counts <- matrix(
    rpois(100, lambda = 50),
    nrow = 10, ncol = 10
  )

  d_counts <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = counts)
  )

  norm_counts <- normalize_counts(d_counts, method = "TMM")

  expect_equal(dim(norm_counts), dim(counts))
  expect_true(all(norm_counts >= 0))
})

# =============================================================================
# Test Visualization Functions (basic structure tests)
# =============================================================================

test_that("plot_volcano returns ggplot object", {
  skip_if_not_installed("ggplot2")
  skip_if_not_installed("SummarizedExperiment")

  mock_res <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = matrix(1:100, nrow = 10)),
    rowData = data.frame(
      cluster_id = 1:10,
      logFC = rnorm(10),
      p_adj = runif(10, 0, 1)
    )
  )

  p <- plot_volcano(mock_res)

  expect_s3_class(p, "ggplot")
})

test_that("plot_ma returns ggplot object", {
  skip_if_not_installed("ggplot2")
  skip_if_not_installed("SummarizedExperiment")

  mock_res <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = matrix(1:100, nrow = 10)),
    rowData = data.frame(
      cluster_id = 1:10,
      logFC = rnorm(10),
      logCPM = rnorm(10, mean = 5),
      p_adj = runif(10, 0, 1)
    )
  )

  p <- plot_ma(mock_res)

  expect_s3_class(p, "ggplot")
})

test_that("plot_cluster_abundance returns ggplot object", {
  skip_if_not_installed("ggplot2")
  skip_if_not_installed("SummarizedExperiment")
  skip_if_not_installed("reshape2")

  counts <- matrix(
    rpois(100, lambda = 50),
    nrow = 10, ncol = 10
  )

  d_counts <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = counts)
  )

  p <- plot_cluster_abundance(d_counts)

  expect_s3_class(p, "ggplot")
})

# =============================================================================
# Integration Tests
# =============================================================================

test_that("complete pipeline runs without errors", {
  skip_if_not_installed("diffcyt")

  # Create test data
  test_data <- create_test_data(
    n_samples = 4,
    n_cells_per_sample = 100,
    n_markers = 10,
    seed = 123
  )

  # Run pipeline
  expect_error(
    results <- run_diffcyt_pipeline(
      d_input = test_data$d_input,
      experiment_info = test_data$experiment_info,
      marker_info = test_data$marker_info,
      analysis_type = "DA",
      method_DA = "edgeR",
      transform = TRUE,
      xdim = 5,
      ydim = 5,
      verbose = FALSE
    ),
    NA  # Expect no error
  )

  expect_type(results, "list")
  expect_true("res" %in% names(results))
  expect_true("d_se" %in% names(results))
  expect_true("d_counts" %in% names(results))
})

# =============================================================================
# Test Utility Functions
# =============================================================================

test_that("filter_clusters_by_abundance works correctly", {
  skip_if_not_installed("SummarizedExperiment")

  counts <- matrix(
    c(100, 50, 10,  # cluster 1: all samples have > 3 cells
      5,   2,  1,   # cluster 2: only 1 sample has > 3 cells
      20,  15, 8),  # cluster 3: 2 samples have > 3 cells
    nrow = 3, byrow = TRUE
  )
  colnames(counts) <- c("s1", "s2", "s3")

  d_counts <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = counts)
  )

  filtered <- filter_clusters_by_abundance(
    d_counts,
    min_cells = 3,
    min_samples = 2
  )

  expect_equal(nrow(filtered), 2)  # clusters 1 and 3
})

test_that("merge_da_ds_results works correctly", {
  skip_if_not_installed("SummarizedExperiment")

  da_res <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = matrix(1:100, nrow = 10)),
    rowData = data.frame(
      cluster_id = 1:10,
      logFC_DA = rnorm(10),
      p_adj_DA = runif(10)
    )
  )

  ds_res <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = matrix(1:100, nrow = 10)),
    rowData = data.frame(
      cluster_id = 1:10,
      logFC_DS = rnorm(10),
      p_adj_DS = runif(10)
    )
  )

  merged <- merge_da_ds_results(da_res, ds_res)

  expect_equal(nrow(merged), 10)
  expect_true("logFC_DA" %in% colnames(merged))
  expect_true("logFC_DS" %in% colnames(merged))
})

test_that("filter_clusters_by_abundance pre-filtering works", {
  skip_if_not_installed("SummarizedExperiment")

  counts <- matrix(
    c(100, 50, 10,
      5,   2,  1,
      20,  15, 8),
    nrow = 3, byrow = TRUE
  )
  colnames(counts) <- c("s1", "s2", "s3")

  d_counts <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = counts)
  )

  # All clusters pass with loose filtering
  filtered_all <- filter_clusters_by_abundance(
    d_counts,
    min_cells = 1,
    min_samples = 1
  )
  expect_equal(nrow(filtered_all), 3)

  # Strict filtering removes all
  filtered_none <- filter_clusters_by_abundance(
    d_counts,
    min_cells = 200,
    min_samples = 3
  )
  expect_equal(nrow(filtered_none), 0)
})
