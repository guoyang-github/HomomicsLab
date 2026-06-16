# Unit Tests for miloR Differential Abundance Analysis Skill
# ===========================================================
#
# Comprehensive test suite for the miloR wrapper functions

library(testthat)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# Skip tests if miloR is not installed
if (!requireNamespace("miloR", quietly = TRUE)) {
  skip("miloR not installed")
}

# =============================================================================
# Test Core Analysis Functions
# =============================================================================

test_that("check_milor_dependencies works", {
  skip_if_not_installed("miloR")

  expect_true(check_milor_dependencies())
})

test_that("validate_milor_input validates correctly", {
  skip_if_not_installed("SingleCellExperiment")

  # Create test SCE
  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)

  # Valid input
  result <- validate_milor_input(sce, sample_col = "sample_id", condition_col = "condition")
  expect_true(result$valid)
  expect_equal(result$type, "SingleCellExperiment")

  # Invalid sample column
  expect_error(
    validate_milor_input(sce, sample_col = "nonexistent"),
    "not found in colData"
  )

  # Invalid condition column
  expect_error(
    validate_milor_input(sce, condition_col = "nonexistent"),
    "not found in colData"
  )
})

test_that("create_milo_object works", {
  skip_if_not_installed("miloR")
  skip_if_not_installed("SingleCellExperiment")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)

  expect_s4_class(milo_obj, "Milo")
  expect_equal(ncol(milo_obj), ncol(sce))
  expect_equal(nrow(milo_obj), nrow(sce))
})

test_that("build_milo_graph works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)

  expect_false(is.null(graph(milo_obj)))
  expect_true(length(graph(milo_obj)) > 0)
})

test_that("make_milo_neighborhoods works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.2, k = 10, d = 10, seed = 123)

  expect_true(ncol(nhoods(milo_obj)) > 0)
})

test_that("count_milo_cells works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.2, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  expect_true(ncol(nhoodCounts(milo_obj)) > 0)
  expect_equal(ncol(nhoodCounts(milo_obj)), length(unique(sce$sample_id)))
})

test_that("test_milo_da works", {
  skip_if_not_installed("miloR")
  skip_if_not_installed("edgeR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  da_res <- test_milo_da(milo_obj, design = ~ condition, design.df = design_df)

  expect_s3_class(da_res, "data.frame")
  expect_true("logFC" %in% colnames(da_res))
  expect_true("PValue" %in% colnames(da_res))
  expect_true("SpatialFDR" %in% colnames(da_res))
})

test_that("run_milo_pipeline works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  results <- run_milo_pipeline(
    sce,
    sample_col = "sample_id",
    design = ~ condition,
    design.df = design_df,
    k = 10,
    d = 10,
    prop = 0.3,
    verbose = FALSE
  )

  expect_type(results, "list")
  expect_true("milo" %in% names(results))
  expect_true("da_results" %in% names(results))
  expect_s4_class(results$milo, "Milo")
})

test_that("annotate_milo_neighborhoods works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  sce$cell_type <- sample(c("A", "B", "C"), ncol(sce), replace = TRUE)

  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  da_res <- test_milo_da(milo_obj, design = ~ condition, design.df = design_df)
  da_res <- annotate_milo_neighborhoods(milo_obj, da_res, colData_col = "cell_type")

  expect_true("cell_type" %in% colnames(da_res))
})

# =============================================================================
# Test Utility Functions
# =============================================================================

test_that("create_milo_test_data works", {
  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, n_genes = 500, seed = 123)

  expect_s4_class(sce, "SingleCellExperiment")
  expect_equal(ncol(sce), 400)
  expect_equal(nrow(sce), 500)
  expect_true("sample_id" %in% colnames(colData(sce)))
  expect_true("condition" %in% colnames(colData(sce)))
})

test_that("create_milo_design works", {
  samples <- c("S1", "S2", "S3", "S4")
  conditions <- c("A", "A", "B", "B")

  design <- create_milo_design(samples, conditions)

  expect_equal(nrow(design), 4)
  expect_equal(rownames(design), samples)
  expect_equal(design$condition, factor(conditions))
})

test_that("get_top_da_nhoods works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  da_res <- test_milo_da(milo_obj, design = ~ condition, design.df = design_df)
  top <- get_top_da_nhoods(da_res, n_top = 5)

  expect_equal(nrow(top), 5)
})

test_that("get_significant_nhoods works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  da_res <- test_milo_da(milo_obj, design = ~ condition, design.df = design_df)
  sig <- get_significant_nhoods(da_res, alpha = 0.1)

  expect_type(sig, "integer")
})

test_that("summarize_milo_results works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  da_res <- test_milo_da(milo_obj, design = ~ condition, design.df = design_df)
  summary <- summarize_milo_results(da_res, alpha = 0.1)

  expect_type(summary, "list")
  expect_true("n_total" %in% names(summary))
  expect_true("n_significant" %in% names(summary))
})

test_that("recommend_milo_k works", {
  expect_equal(recommend_milo_k(500), 10)
  expect_equal(recommend_milo_k(5000), 30)
  expect_equal(recommend_milo_k(50000), 50)
  expect_equal(recommend_milo_k(500000), 100)
})

test_that("recommend_milo_prop works", {
  expect_equal(recommend_milo_prop(500), 0.2)
  expect_equal(recommend_milo_prop(5000), 0.1)
  expect_equal(recommend_milo_prop(50000), 0.05)
  expect_equal(recommend_milo_prop(500000), 0.01)
})

# =============================================================================
# Test Visualization Functions
# =============================================================================

test_that("plot_milo_volcano returns ggplot object", {
  skip_if_not_installed("ggplot2")
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  da_res <- test_milo_da(milo_obj, design = ~ condition, design.df = design_df)
  p <- plot_milo_volcano(da_res, alpha = 0.1)

  expect_s3_class(p, "ggplot")
})

test_that("plot_milo_size_distribution returns ggplot object", {
  skip_if_not_installed("ggplot2")
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)

  p <- plot_milo_size_distribution(milo_obj)

  expect_s3_class(p, "ggplot")
})

test_that("plot_milo_counts returns ggplot object", {
  skip_if_not_installed("ggplot2")
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 100, n_samples = 4, seed = 123)
  milo_obj <- create_milo_object(sce)
  milo_obj <- build_milo_graph(milo_obj, k = 10, d = 10)
  milo_obj <- make_milo_neighborhoods(milo_obj, prop = 0.3, k = 10, d = 10, seed = 123)
  milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

  p <- plot_milo_counts(milo_obj, n.top = 10)

  expect_s3_class(p, "ggplot")
})

# =============================================================================
# Integration Tests
# =============================================================================

test_that("complete pipeline with grouping works", {
  skip_if_not_installed("miloR")

  sce <- create_milo_test_data(n_cells = 200, n_samples = 6, seed = 123)

  design_df <- unique(data.frame(
    sample_id = sce$sample_id,
    condition = sce$condition
  ))
  rownames(design_df) <- design_df$sample_id

  results <- run_milo_pipeline(
    sce,
    sample_col = "sample_id",
    design = ~ condition,
    design.df = design_df,
    k = 15,
    d = 15,
    prop = 0.3,
    verbose = FALSE
  )

  # Test grouping
  da_res <- group_milo_neighborhoods(
    results$milo,
    da.res = results$da_results,
    da.fdr = 0.5,  # Relaxed for testing
    overlap = 1
  )

  expect_true("NhoodGroup" %in% colnames(da_res))
})
