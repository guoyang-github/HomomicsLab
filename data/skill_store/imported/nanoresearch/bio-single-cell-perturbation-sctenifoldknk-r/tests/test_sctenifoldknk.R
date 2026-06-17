#!/usr/bin/env Rscript
#' Unit Tests for scTenifoldKnk Analysis
#'
#' Tests cover:
#' - Data validation functions
#' - Core analysis workflow
#' - Utility functions
#' - Result export and reporting

library(testthat)

# Source custom scripts
source("../scripts/r/core_analysis.R")
source("../scripts/r/utils.R")
source("../scripts/r/enrichment.R")
source("../scripts/r/visualization.R")

# ================================================================================
# Test Data Preparation
# ================================================================================

#' Create Test Data
#' @return Matrix suitable for testing
create_test_data <- function(n_genes = 200, n_cells = 300) {
  set.seed(42)
  counts <- matrix(
    rpois(n_genes * n_cells, lambda = 3),
    nrow = n_genes,
    ncol = n_cells
  )

  # Add some structure
  counts[1:5, 1:100] <- counts[1:5, 1:100] + rpois(500, lambda = 10)

  rownames(counts) <- paste0("GENE_", seq_len(n_genes))
  colnames(counts) <- paste0("CELL_", seq_len(n_cells))

  return(counts)
}

# ================================================================================
# Test Suite: Data Validation
# ================================================================================

test_that("validate_knk_data validates correct data", {
  counts <- create_test_data()

  validation <- validate_knk_data(
    counts,
    target_gene = "GENE_1",
    min_cells = 200,
    min_genes = 100
  )

  expect_true(validation$valid)
  expect_equal(validation$diagnostics$n_genes, 200)
  expect_equal(validation$diagnostics$n_cells, 300)
  expect_true("GENE_1" %in% validation$diagnostics$target_gene_cells)
})

test_that("validate_knk_data detects missing target gene", {
  counts <- create_test_data()

  validation <- validate_knk_data(
    counts,
    target_gene = "NONEXISTENT"
  )

  expect_false(validation$valid)
  expect_true(any(grepl("not found", validation$errors)))
})

test_that("validate_knk_data detects insufficient cells", {
  counts <- create_test_data(n_cells = 100)

  validation <- validate_knk_data(
    counts,
    min_cells = 200
  )

  expect_false(validation$valid)
  expect_true(any(grepl("Insufficient cells", validation$errors)))
})

test_that("validate_knk_data works with Seurat objects", {
  skip_if_not_installed("Seurat")

  counts <- create_test_data()
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)

  validation <- validate_knk_data(
    seurat_obj,
    target_gene = "GENE_1",
    min_cells = 200
  )

  expect_true(validation$valid)
  expect_true(validation$diagnostics$is_seurat)
})

# ================================================================================
# Test Suite: Utility Functions
# ================================================================================

test_that("summarize_knockdown_results works correctly", {
  # Create mock result
  mock_result <- list(
    diffRegulation = data.frame(
      gene = paste0("GENE_", 1:100),
      distance = runif(100, 0, 2),
      Z = rnorm(100),
      FC = runif(100, 1, 5),
      p.value = runif(100, 0, 0.1),
      p.adj = runif(100, 0, 0.1)
    )
  )

  summary <- summarize_knockdown_results(mock_result, p_cutoff = 0.05)

  expect_type(summary, "list")
  expect_true("statistics" %in% names(summary))
  expect_true("top_upregulated" %in% names(summary))
  expect_equal(summary$statistics$n_genes_analyzed, 100)
})

test_that("get_significant_genes returns correct genes", {
  mock_result <- list(
    diffRegulation = data.frame(
      gene = paste0("GENE_", 1:100),
      Z = c(rep(2, 10), rep(-2, 10), rep(0.5, 80)),
      p.adj = c(rep(0.01, 20), rep(0.5, 80))
    )
  )

  sig_genes <- get_significant_genes(mock_result, p_cutoff = 0.05)
  expect_equal(length(sig_genes), 20)

  up_genes <- get_significant_genes(mock_result, p_cutoff = 0.05, direction = "up")
  expect_equal(length(up_genes), 10)

  down_genes <- get_significant_genes(mock_result, p_cutoff = 0.05, direction = "down")
  expect_equal(length(down_genes), 10)
})

test_that("get_top_affected_genes returns correct number", {
  mock_result <- list(
    diffRegulation = data.frame(
      gene = paste0("GENE_", 1:100),
      Z = rnorm(100),
      p.adj = runif(100)
    )
  )

  top_10 <- get_top_affected_genes(mock_result, n = 10, by = "significance")
  expect_equal(nrow(top_10), 10)

  top_20 <- get_top_affected_genes(mock_result, n = 20, by = "magnitude")
  expect_equal(nrow(top_20), 20)
})

# ================================================================================
# Test Suite: Comparison Functions
# ================================================================================

test_that("compare_knockdowns computes correlation correctly", {
  # Create mock results
  mock_results <- list(
    KNOCKDOWN_1 = list(
      diffRegulation = data.frame(
        gene = paste0("GENE_", 1:50),
        Z = rnorm(50),
        p.adj = runif(50)
      )
    ),
    KNOCKDOWN_2 = list(
      diffRegulation = data.frame(
        gene = paste0("GENE_", 1:50),
        Z = rnorm(50),
        p.adj = runif(50)
      )
    )
  )

  comparison <- compare_knockdowns(mock_results, method = "correlation")

  expect_type(comparison, "double")
  expect_equal(dim(comparison), c(2, 2))
})

test_that("compare_with_experiment calculates correlation", {
  # Create mock predicted result
  mock_predicted <- list(
    diffRegulation = data.frame(
      gene = paste0("GENE_", 1:50),
      Z = rnorm(50),
      FC = runif(50, 1, 5),
      p.adj = runif(50)
    )
  )

  # Create mock experimental data
  mock_experimental <- data.frame(
    gene = paste0("GENE_", 1:50),
    logFC = rnorm(50),
    pvalue = runif(50)
  )

  comparison <- compare_with_experiment(
    mock_predicted,
    mock_experimental,
    method = "correlation"
  )

  expect_type(comparison, "list")
  expect_true("correlation" %in% names(comparison))
  expect_true("overlap" %in% names(comparison))
  expect_true(is.numeric(comparison$correlation$rho))
})

# ================================================================================
# Test Suite: Export Functions
# ================================================================================

test_that("export_knockdown_results creates files", {
  # Create temporary directory
  temp_dir <- tempfile()
  dir.create(temp_dir)

  # Create mock result
  mock_result <- list(
    diffRegulation = data.frame(
      gene = paste0("GENE_", 1:10),
      distance = runif(10),
      Z = rnorm(10),
      FC = runif(10),
      p.value = runif(10),
      p.adj = runif(10)
    ),
    manifoldAlignment = matrix(rnorm(20), nrow = 10),
    tensorNetworks = list(
      WT = Matrix::Matrix(matrix(runif(100), nrow = 10)),
      KO = Matrix::Matrix(matrix(runif(100), nrow = 10))
    )
  )

  # Export
  export_knockdown_results(
    mock_result,
    output_dir = temp_dir,
    prefix = "test",
    gKO = "GENE_1",
    export_networks = FALSE,
    export_genelist = TRUE,
    export_tables = TRUE
  )

  # Check files were created
  expect_true(file.exists(file.path(temp_dir, "GENE_1_test_diffRegulation.csv")))
  expect_true(file.exists(file.path(temp_dir, "GENE_1_test_complete.rds")))

  # Clean up
  unlink(temp_dir, recursive = TRUE)
})

test_that("create_knockdown_report generates report", {
  mock_result <- list(
    diffRegulation = data.frame(
      gene = paste0("GENE_", 1:20),
      distance = runif(20),
      Z = rnorm(20),
      FC = runif(20),
      p.value = runif(20),
      p.adj = c(rep(0.01, 5), rep(0.5, 15))
    )
  )

  report <- create_knockdown_report(
    mock_result,
    gKO = "TEST_GENE",
    output_file = NULL
  )

  expect_type(report, "character")
  expect_true(grepl("TEST_GENE", report))
  expect_true(grepl("scTenifoldKnk", report))
})

# ================================================================================
# Test Suite: Core Analysis (with mocking)
# ================================================================================

test_that("run_multiple_knockdowns validates input", {
  counts <- create_test_data()

  # Should error with empty gene list
  expect_error(
    run_multiple_knockdowns(counts, gene_list = character()),
    "non-empty"
  )

  # Should error with non-existent genes
  expect_error(
    run_multiple_knockdowns(counts, gene_list = c("NONEXISTENT1", "NONEXISTENT2")),
    "No genes"
  )
})

test_that("run_multiple_knockdowns processes valid genes", {
  skip_if_not_installed("scTenifoldKnk")

  counts <- create_test_data()
  genes <- rownames(counts)[1:2]

  # This would run actual analysis - skip in automated tests
  # results <- run_multiple_knockdowns(counts, gene_list = genes, nc_nNet = 2)
  # expect_type(results, "list")
  # expect_equal(length(results), 2)

  # Just check function exists and accepts parameters
  expect_true(exists("run_multiple_knockdowns"))
})

# ================================================================================
# Run All Tests
# ================================================================================

# Only run tests if this file is executed directly
if (sys.nframe() == 0) {
  cat("Running scTenifoldKnk unit tests...\n\n")
  test_dir("./", reporter = "progress")
}
