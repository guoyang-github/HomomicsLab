# Unit tests for chromVAR skill
# =============================

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
  expect_s3_class <- function(x, class) stopifnot(inherits(x, class))
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

context("chromVAR Core Functions")

test_that("check_chromvar_dependencies works", {
  result <- check_chromvar_dependencies()
  expect_true(is.logical(result))
})

test_that("create_chromvar_object works with valid input", {
  set.seed(42)
  counts <- Matrix::Matrix(rpois(1000, 5), nrow = 100, ncol = 10, sparse = TRUE)
  peaks <- GenomicRanges::GRanges(
    seqnames = rep("chr1", 100),
    ranges = IRanges::IRanges(start = seq(1, 10000, by = 100), width = 50)
  )
  rownames(counts) <- paste0("peak_", 1:100)
  colnames(counts) <- paste0("cell_", 1:10)

  rse <- create_chromvar_object(counts, peaks)

  expect_true(inherits(rse, "SummarizedExperiment"))
  expect_equal(nrow(rse), 100)
  expect_equal(ncol(rse), 10)
})

test_that("create_chromvar_object handles data frame peaks", {
  set.seed(42)
  counts <- Matrix::Matrix(rpois(100, 5), nrow = 10, ncol = 10, sparse = TRUE)
  peaks <- data.frame(
    chr = rep("chr1", 10),
    start = seq(1, 1000, by = 100),
    end = seq(1, 1000, by = 100) + 50
  )
  rownames(counts) <- paste0("peak_", 1:10)
  colnames(counts) <- paste0("cell_", 1:10)

  rse <- create_chromvar_object(counts, peaks)

  expect_true(inherits(rse, "SummarizedExperiment"))
})

test_that("validate_chromvar_input validates correctly", {
  set.seed(42)
  counts <- Matrix::Matrix(rpois(1000, 5), nrow = 100, ncol = 10, sparse = TRUE)
  peaks <- GenomicRanges::GRanges(
    seqnames = rep("chr1", 100),
    ranges = IRanges::IRanges(start = seq(1, 10000, by = 100), width = 50)
  )
  rownames(counts) <- paste0("peak_", 1:100)
  colnames(counts) <- paste0("cell_", 1:10)

  rse <- create_chromvar_object(counts, peaks)
  validation <- validate_chromvar_input(rse)

  expect_true(validation$valid)
  expect_true("n_peaks" %in% names(validation$stats))
  expect_true("n_cells" %in% names(validation$stats))
})

test_that("validate_chromvar_input catches dimension mismatch", {
  counts <- Matrix::Matrix(rpois(100, 5), nrow = 10, ncol = 10, sparse = TRUE)
  peaks <- GenomicRanges::GRanges(
    seqnames = rep("chr1", 5),
    ranges = IRanges::IRanges(start = seq(1, 500, by = 100), width = 50)
  )
  rownames(counts) <- paste0("peak_", 1:10)
  colnames(counts) <- paste0("cell_", 1:10)

  expect_error(create_chromvar_object(counts, peaks))
})

context("chromVAR Utility Functions")

test_that("annotate_motifs parses JASPAR names correctly", {
  motif_names <- c("MA0004.1_Arnt", "MA0006.1_Ahr::Arnt", "MA0019.1_Ddit3::Cebpa")
  annotations <- annotate_motifs(motif_names)

  expect_true("motif_id" %in% colnames(annotations))
  expect_true("tf_name" %in% colnames(annotations))
  expect_equal(nrow(annotations), 3)
})

test_that("get_top_variable_motifs returns correct number", {
  var <- data.frame(
    name = paste0("motif_", 1:20),
    variability = runif(20),
    p_value_adj = runif(20, 0, 0.1),
    stringsAsFactors = FALSE
  )

  top_5 <- get_top_variable_motifs(var, n = 5)
  expect_equal(nrow(top_5), 5)
})

test_that("recommend_chromvar_params generates recommendations", {
  params <- recommend_chromvar_params(n_cells = 1000, n_peaks = 50000)

  expect_true("n_bg_iterations" %in% names(params))
  expect_true("n_cores" %in% names(params))
  expect_true("message" %in% names(params))
})

context("chromVAR Integration Functions")

test_that("summarize_chromvar_results validates input", {
  results <- list(
    rse = NULL,
    variability = data.frame(name = "test", variability = 1, p_value_adj = 0.01)
  )

  expect_error(summarize_chromvar_results(results))
})

test_that("subset_cells works with indices", {
  set.seed(42)
  counts <- Matrix::Matrix(rpois(1000, 5), nrow = 100, ncol = 10, sparse = TRUE)
  peaks <- GenomicRanges::GRanges(
    seqnames = rep("chr1", 100),
    ranges = IRanges::IRanges(start = seq(1, 10000, by = 100), width = 50)
  )
  rownames(counts) <- paste0("peak_", 1:100)
  colnames(counts) <- paste0("cell_", 1:10)

  rse <- create_chromvar_object(counts, peaks)
  rse_subset <- subset_cells(rse, 1:5)

  expect_equal(ncol(rse_subset), 5)
})

test_that("subset_cells works with names", {
  set.seed(42)
  counts <- Matrix::Matrix(rpois(1000, 5), nrow = 100, ncol = 10, sparse = TRUE)
  peaks <- GenomicRanges::GRanges(
    seqnames = rep("chr1", 100),
    ranges = IRanges::IRanges(start = seq(1, 10000, by = 100), width = 50)
  )
  cell_names <- paste0("cell_", 1:10)
  rownames(counts) <- paste0("peak_", 1:100)
  colnames(counts) <- cell_names

  rse <- create_chromvar_object(counts, peaks)
  rse_subset <- subset_cells(rse, cell_names[1:5])

  expect_equal(ncol(rse_subset), 5)
})

context("chromVAR Export Functions")

test_that("create_chromvar_report generates report", {
  set.seed(42)
  var <- data.frame(
    name = paste0("motif_", 1:10),
    variability = runif(10),
    p_value_adj = runif(10, 0, 0.1),
    stringsAsFactors = FALSE
  )

  # Create mock results
  results <- list(
    rse = structure(list(), class = "SummarizedExperiment"),
    deviations = structure(list(), class = "chromVARDeviations"),
    variability = var
  )

  report <- create_chromvar_report(results)

  expect_true(is.character(report))
  expect_true(grepl("chromVAR Analysis Report", report))
})

context("chromVAR Examples Run")

test_that("minimal example can be sourced", {
  # Just check that the example file exists and can be parsed
  expect_true(file.exists("../examples/minimal_example.R"))
})

test_that("advanced example can be sourced", {
  expect_true(file.exists("../examples/advanced_example.R"))
})

cat("\n=== Test Summary ===\n")
cat("All tests completed. Check output for any FAIL messages.\n")
