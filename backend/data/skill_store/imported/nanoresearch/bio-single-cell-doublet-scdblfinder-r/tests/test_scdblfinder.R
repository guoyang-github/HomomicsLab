# Unit Tests for scDblFinder Doublet Detection Skill
# ===================================================
#
# Comprehensive test suite for scDblFinder wrapper functions

library(testthat)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/utils.R")
source("../scripts/r/visualization.R")

# =============================================================================
# Test Core Analysis Functions
# =============================================================================

test_that("check_scdblfinder_dependencies works", {
  result <- check_scdblfinder_dependencies()
  expect_type(result, "logical")
})

test_that("validate_scdblfinder_input validates correctly", {
  # Create test data
  n_cells <- 100
  n_genes <- 500

  counts <- matrix(rpois(n_genes * n_cells, 5), nrow = n_genes)
  rownames(counts) <- paste0("GENE_", 1:n_genes)
  colnames(counts) <- paste0("Cell_", 1:n_cells)

  # Valid input
  result <- validate_scdblfinder_input(counts)
  expect_true(result$valid)
  expect_equal(result$stats$n_cells, n_cells)
  expect_equal(result$stats$n_genes, n_genes)

  # Too few cells
  small_counts <- counts[, 1:30]
  result <- validate_scdblfinder_input(small_counts)
  expect_false(result$valid)

  # No rownames (warning, not error)
  bad_counts <- counts
  rownames(bad_counts) <- NULL
  result <- validate_scdblfinder_input(bad_counts)
  expect_true(result$valid)
  expect_gt(length(result$warnings), 0)
})

test_that("create_scdblfinder_test_data works", {
  test_data <- create_scdblfinder_test_data(
    n_cells = 100,
    n_genes = 500,
    doublet_rate = 0.05,
    seed = 42
  )

  expect_type(test_data, "list")
  expect_true("counts" %in% names(test_data))
  expect_true("sample_info" %in% names(test_data))

  expect_equal(ncol(test_data$counts), 100)
  expect_equal(nrow(test_data$counts), 500)
  expect_equal(length(test_data$sample_info), 100)
})

test_that("extract_doublet_scores works with mock data", {
  # Create mock SCE
  n_cells <- 50
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  # Add mock results
  SummarizedExperiment::colData(mock_sce)$scDblFinder.score <- runif(n_cells)
  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- sample(c("singlet", "doublet"), n_cells, replace = TRUE)

  result <- extract_doublet_scores(mock_sce)

  expect_s3_class(result, "data.frame")
  expect_true("cell" %in% colnames(result))
  expect_true("scDblFinder.score" %in% colnames(result))
  expect_true("scDblFinder.class" %in% colnames(result))
})

test_that("get_doublet_cells and get_singlet_cells work", {
  n_cells <- 50
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )
  colnames(mock_sce) <- paste0("Cell_", 1:n_cells)

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- c(
    rep("singlet", 40),
    rep("doublet", 10)
  )

  doublets <- get_doublet_cells(mock_sce)
  expect_equal(length(doublets), 10)

  singlets <- get_singlet_cells(mock_sce)
  expect_equal(length(singlets), 40)
})

test_that("summarize_scdblfinder_results works", {
  n_cells <- 100
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- c(
    rep("singlet", 90),
    rep("doublet", 10)
  )
  SummarizedExperiment::colData(mock_sce)$scDblFinder.score <- c(
    runif(90, 0, 0.5),
    runif(10, 0.5, 1)
  )

  summary <- summarize_scdblfinder_results(mock_sce)

  expect_type(summary, "list")
  expect_equal(summary$n_cells, 100)
  expect_equal(summary$n_doublets, 10)
  expect_equal(summary$n_singlets, 90)
  expect_equal(summary$doublet_rate, 0.1)
  expect_true(!is.null(summary$mean_score))
})

test_that("filter_scdblfinder works", {
  n_cells <- 100
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- c(
    rep("singlet", 85),
    rep("doublet", 15)
  )

  filtered <- filter_scdblfinder(mock_sce, remove_doublets = TRUE)
  expect_equal(ncol(filtered), 85)

  filtered2 <- filter_scdblfinder(mock_sce, remove_doublets = FALSE)
  expect_equal(ncol(filtered2), 100)
})

test_that("export_scdblfinder_results creates files", {
  n_cells <- 50
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- sample(c("singlet", "doublet"), n_cells, replace = TRUE)
  SummarizedExperiment::colData(mock_sce)$scDblFinder.score <- runif(n_cells)

  temp_dir <- tempdir()
  export_scdblfinder_results(mock_sce, temp_dir, prefix = "test")

  expect_true(file.exists(file.path(temp_dir, "test_classifications.csv")))
  expect_true(file.exists(file.path(temp_dir, "test_summary.txt")))
})

test_that("create_scdblfinder_report generates report", {
  n_cells <- 100
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- c(
    rep("singlet", 90),
    rep("doublet", 10)
  )
  SummarizedExperiment::colData(mock_sce)$scDblFinder.score <- runif(n_cells)

  report <- create_scdblfinder_report(mock_sce)

  expect_type(report, "character")
  expect_true(grepl("scDblFinder Analysis Report", report))
  expect_true(grepl("Doublets", report))
})

# =============================================================================
# Test Utility Functions
# =============================================================================

test_that("recommend_scdblfinder_params works", {
  params <- recommend_scdblfinder_params(
    n_cells = 5000,
    n_samples = 2,
    is_10x = TRUE
  )

  expect_type(params, "list")
  expect_true("nfeatures" %in% names(params))
  expect_true("dims" %in% names(params))
  expect_true("dbr.per1k" %in% names(params))
  expect_true(params$dbr.per1k == 0.008)  # 10X rate
})

test_that("estimate_doublet_rate works", {
  # Standard 10X
  dbr <- estimate_doublet_rate(5000, platform = "10x_standard")
  expect_equal(dbr, 0.008 * 5, tolerance = 0.01)

  # HT 10X
  dbr_ht <- estimate_doublet_rate(5000, platform = "10x_ht")
  expect_equal(dbr_ht, 0.004 * 5, tolerance = 0.01)
})

test_that("filter_doublets works", {
  n_cells <- 100
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- c(
    rep("singlet", 85),
    rep("doublet", 15)
  )

  filtered <- filter_doublets(mock_sce, keep_singlets = TRUE)
  expect_equal(ncol(filtered), 85)
})

test_that("compare_scdblfinder_results works", {
  # Create mock SCE objects
  sce1 <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * 100, 5), nrow = 100))
  )
  SummarizedExperiment::colData(sce1)$scDblFinder.class <- c(rep("singlet", 90), rep("doublet", 10))
  SummarizedExperiment::colData(sce1)$scDblFinder.score <- runif(100)

  sce2 <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * 150, 5), nrow = 100))
  )
  SummarizedExperiment::colData(sce2)$scDblFinder.class <- c(rep("singlet", 130), rep("doublet", 20))
  SummarizedExperiment::colData(sce2)$scDblFinder.score <- runif(150)

  comparison <- compare_scdblfinder_results(list(Sample1 = sce1, Sample2 = sce2))

  expect_s3_class(comparison, "data.frame")
  expect_equal(nrow(comparison), 2)
  expect_true("sample" %in% colnames(comparison))
  expect_true("doublet_rate" %in% colnames(comparison))
})

test_that("check_doublet_enrichment works", {
  n_cells <- 100
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- c(
    rep("singlet", 85),
    rep("doublet", 15)
  )
  SummarizedExperiment::colData(mock_sce)$cluster <- rep(c("A", "B", "C", "D"), each = 25)

  enrichment <- check_doublet_enrichment(mock_sce, cluster_col = "cluster")

  expect_s3_class(enrichment, "data.frame")
  expect_true("cluster" %in% colnames(enrichment))
  expect_true("doublet_rate" %in% colnames(enrichment))
  expect_true("enrichment" %in% colnames(enrichment))
})

test_that("create_scdblfinder_qc_report works", {
  n_cells <- 100
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- c(
    rep("singlet", 90),
    rep("doublet", 10)
  )
  SummarizedExperiment::colData(mock_sce)$scDblFinder.score <- runif(n_cells)

  report <- create_scdblfinder_qc_report(mock_sce)

  expect_type(report, "character")
  expect_true(grepl("QC Report", report))
  expect_true(grepl("OK|CHECK", report))
})

# =============================================================================
# Integration Test
# =============================================================================

test_that("complete workflow runs without errors", {
  # Create test data
  test_data <- create_scdblfinder_test_data(
    n_cells = 100,
    n_genes = 500,
    doublet_rate = 0.05,
    seed = 42
  )

  sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = test_data$counts)
  )

  # Validate
  validation <- validate_scdblfinder_input(sce)
  expect_true(validation$valid)

  # Mock results
  SummarizedExperiment::colData(sce)$scDblFinder.score <- runif(100)
  SummarizedExperiment::colData(sce)$scDblFinder.class <- c(
    rep("singlet", 95),
    rep("doublet", 5)
  )

  # Summarize
  summary <- summarize_scdblfinder_results(sce)
  expect_equal(summary$n_cells, 100)

  # Filter
  filtered <- filter_scdblfinder(sce, remove_doublets = TRUE)
  expect_equal(ncol(filtered), 95)

  # Get cells
  doublets <- get_doublet_cells(sce)
  expect_equal(length(doublets), 5)
})

# =============================================================================
# Visualization Tests
# =============================================================================

test_that("plot_doublet_score_distribution works", {
  skip_if_not_installed("ggplot2")

  n_cells <- 50
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )
  SummarizedExperiment::colData(mock_sce)$scDblFinder.score <- runif(n_cells)

  p <- plot_doublet_score_distribution(mock_sce)
  expect_s3_class(p, "ggplot")
})

test_that("plot_doublet_scores_by_class works", {
  skip_if_not_installed("ggplot2")

  n_cells <- 50
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )
  SummarizedExperiment::colData(mock_sce)$scDblFinder.score <- runif(n_cells)
  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- sample(c("singlet", "doublet"), n_cells, replace = TRUE)

  p <- plot_doublet_scores_by_class(mock_sce)
  expect_s3_class(p, "ggplot")
})

test_that("plot_doublets_reduced works", {
  skip_if_not_installed("ggplot2")

  n_cells <- 50
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )
  SummarizedExperiment::colData(mock_sce)$scDblFinder.class <- sample(c("singlet", "doublet"), n_cells, replace = TRUE)

  # Add mock UMAP
  SingleCellExperiment::reducedDim(mock_sce, "UMAP") <- matrix(runif(n_cells * 2), ncol = 2)

  p <- plot_doublets_reduced(mock_sce, dimred = "UMAP")
  expect_s3_class(p, "ggplot")
})

test_that("plot_doublets_reduced handles missing color_by gracefully", {
  skip_if_not_installed("ggplot2")

  n_cells <- 50
  mock_sce <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(rpois(100 * n_cells, 5), nrow = 100))
  )

  SingleCellExperiment::reducedDim(mock_sce, "UMAP") <- matrix(runif(n_cells * 2), ncol = 2)

  p <- plot_doublets_reduced(mock_sce, dimred = "UMAP", color_by = "nonexistent")
  expect_s3_class(p, "ggplot")
})
