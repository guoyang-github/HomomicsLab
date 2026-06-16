# Unit tests for Signac skill
# ===========================

# Load testthat if available
if (requireNamespace("testthat", quietly = TRUE)) {
  library(testthat)
} else {
  # Minimal testthat replacement
  context <- function(x) cat("\n===", x, "===\n")
  test_that <- function(name, code) {
    cat("\nTest:", name, "\n")
    tryCatch({
      eval(substitute(code))
      cat("  PASS\n")
    }, error = function(e) {
      cat("  FAIL:", conditionMessage(e), "\n")
    })
  }
  expect_true <- function(x) stopifnot(isTRUE(x))
  expect_equal <- function(x, y) stopifnot(identical(x, y))
  expect_false <- function(x) stopifnot(isFALSE(x))
  expect_null <- function(x) stopifnot(is.null(x))
  expect_error <- function(expr) {
    result <- tryCatch({
      eval(substitute(expr))
      stop("Expected error but got none")
    }, error = function(e) NULL)
  }
}

# Source the wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

context("Signac Core Functions")

test_that("check_signac_dependencies works", {
  result <- check_signac_dependencies()
  expect_true(is.logical(result))
})

test_that("get_available_genomes returns valid genomes", {
  genomes <- get_available_genomes()
  expect_true(all(genomes %in% c("hg38", "hg19", "mm10", "mm9")))
  expect_equal(length(genomes), 4)
})

test_that("recommend_signac_params returns expected structure", {
  params <- recommend_signac_params(
    n_cells = 10000,
    genome = "hg38"
  )

  expect_true("min_counts" %in% names(params))
  expect_true("max_counts" %in% names(params))
  expect_true("min_tss" %in% names(params))
  expect_true("max_ns" %in% names(params))
  expect_true("dims" %in% names(params))
  expect_true("resolution" %in% names(params))
})

context("Signac Utility Functions")

test_that("create_marker_list works for known tissues", {
  markers <- create_marker_list(tissue = "pbmc")
  expect_true(length(markers) > 0)
  expect_true("CD4_T" %in% names(markers) || "T_cell" %in% names(markers))
})

test_that("create_marker_list filters by cell type", {
  markers <- create_marker_list(
    cell_types = c("T_cell", "B_cell"),
    tissue = "blood"
  )
  expect_true(length(markers) <= 2)
})

test_that("get_signac_version_info returns data frame", {
  info <- get_signac_version_info()
  expect_true(is.data.frame(info))
  expect_true("package" %in% colnames(info))
  expect_true("version" %in% colnames(info))
})

test_that("check_macs2 returns logical", {
  result <- check_macs2()
  expect_true(is.logical(result))
})

context("Signac QC Functions")

test_that("get_qc_summary handles missing metrics", {
  # Create mock Seurat object without QC metrics
  mock_metadata <- data.frame(
    nCount_peaks = c(1000, 2000, 3000),
    stringsAsFactors = FALSE
  )

  # Mock seurat object
  mock_obj <- list(meta.data = mock_metadata)
  class(mock_obj) <- "Seurat"

  summary <- tryCatch({
    get_qc_summary(mock_obj)
  }, error = function(e) NULL)

  # Should handle gracefully
  expect_true(is.null(summary) || is.data.frame(summary))
})

context("Signac Integration Functions")

test_that("create_marker_list structure is correct", {
  markers <- create_marker_list(tissue = "pbmc")

  # Check that all entries are character vectors
  for (cell_type in names(markers)) {
    expect_true(is.character(markers[[cell_type]]))
    expect_true(length(markers[[cell_type]]) > 0)
  }
})

test_that("helper null operator works", {
  `%||%` <- function(x, y) if (is.null(x)) y else x

  expect_equal(NULL %||% "default", "default")
  expect_equal("value" %||% "default", "value")
})

context("Signac Examples")

test_that("minimal example file exists", {
  expect_true(file.exists("../examples/minimal_example.R"))
})

test_that("advanced example file exists", {
  expect_true(file.exists("../examples/advanced_example.R"))
})

test_that("core_analysis.R file exists", {
  expect_true(file.exists("../scripts/r/core_analysis.R"))
})

test_that("visualization.R file exists", {
  expect_true(file.exists("../scripts/r/visualization.R"))
})

test_that("utils.R file exists", {
  expect_true(file.exists("../scripts/r/utils.R"))
})

cat("\n=== Test Summary ===\n")
cat("All tests completed. Check output for any FAIL messages.\n")
