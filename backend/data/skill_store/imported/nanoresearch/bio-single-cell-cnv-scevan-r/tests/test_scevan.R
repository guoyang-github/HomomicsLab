# Unit tests for SCEVAN CNV Analysis Module
# Test suite for bio-single-cell-cnv-scevan-r skill

library(testthat)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source main functions
source(file.path(script_dir, "run_scevan.R"))

context("SCEVAN CNV Analysis Functions")

# ============================================================================
# Test Data Helpers
# ============================================================================

create_test_counts <- function(n_cells = 50, n_genes = 100) {
  set.seed(42)
  counts <- matrix(rpois(n_cells * n_genes, lambda = 5),
                   nrow = n_genes, ncol = n_cells)
  rownames(counts) <- paste0("GENE", 1:n_genes)
  colnames(counts) <- paste0("CELL", 1:n_cells)
  return(counts)
}

create_mock_scevan_results <- function(cells) {
  data.frame(
    class = sample(c("malignant", "non-malignant"), length(cells), replace = TRUE),
    subclone = NA_character_,
    row.names = cells
  )
}

# ============================================================================
# Tests for function existence
# ============================================================================

test_that("run_scevan function exists", {
  expect_true(exists("run_scevan"))
  expect_type(run_scevan, "closure")
})

test_that("run_scevan_seurat function exists", {
  expect_true(exists("run_scevan_seurat"))
  expect_type(run_scevan_seurat, "closure")
})

test_that("add_scevan_to_seurat function exists", {
  expect_true(exists("add_scevan_to_seurat"))
  expect_type(add_scevan_to_seurat, "closure")
})

test_that("plot_scevan_classification function exists", {
  expect_true(exists("plot_scevan_classification"))
  expect_type(plot_scevan_classification, "closure")
})

test_that("summarize_scevan function exists", {
  expect_true(exists("summarize_scevan"))
  expect_type(summarize_scevan, "closure")
})

# ============================================================================
# Tests for input validation
# ============================================================================

test_that("run_scevan validates count matrix rownames", {
  counts_no_rownames <- create_test_counts()
  rownames(counts_no_rownames) <- NULL

  expect_error(
    run_scevan(counts_no_rownames, sample_name = "Test"),
    "gene symbols as rownames"
  )
})

test_that("run_scevan warns on ENSEMBL IDs", {
  counts_ensembl <- create_test_counts()
  rownames(counts_ensembl) <- paste0("ENSG", sprintf("%011d", 1:nrow(counts_ensembl)))

  expect_warning(
    run_scevan(counts_ensembl, sample_name = "Test"),
    "ENSEMBL IDs"
  )
})

test_that("run_scevan validates norm_cell barcodes", {
  counts <- create_test_counts()
  invalid_norm <- c("CELL1", "CELL2", "NONEXISTENT")

  expect_error(
    run_scevan(counts, sample_name = "Test", norm_cell = invalid_norm),
    "norm_cell barcodes not found"
  )
})

test_that("run_scevan_seurat validates input", {
  skip_if_not_installed("Seurat")

  expect_error(run_scevan_seurat(NULL), "must be a Seurat object")
  expect_error(run_scevan_seurat(data.frame()), "must be a Seurat object")
})

test_that("run_scevan_seurat validates norm_cell in Seurat", {
  skip_if_not_installed("Seurat")

  counts <- create_test_counts()
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  invalid_norm <- c("CELL1", "NONEXISTENT")

  expect_error(
    run_scevan_seurat(seurat_obj, norm_cell = invalid_norm),
    "norm_cell barcodes not found"
  )
})

# ============================================================================
# Tests for add_scevan_to_seurat
# ============================================================================

test_that("add_scevan_to_seurat merges classifications correctly", {
  skip_if_not_installed("Seurat")

  counts <- create_test_counts(n_cells = 10)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)

  results <- create_mock_scevan_results(colnames(seurat_obj))

  result_obj <- add_scevan_to_seurat(seurat_obj, results)

  expect_true("scevan_class" %in% colnames(result_obj@meta.data))
  expect_equal(length(result_obj$scevan_class), ncol(seurat_obj))
})

test_that("add_scevan_to_seurat warns on missing cells", {
  skip_if_not_installed("Seurat")

  counts <- create_test_counts(n_cells = 10)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)

  # Results missing some cells
  results <- create_mock_scevan_results(colnames(seurat_obj)[1:5])

  expect_warning(
    add_scevan_to_seurat(seurat_obj, results),
    "cells from Seurat object are missing"
  )
})

test_that("add_scevan_to_seurat handles custom prefix", {
  skip_if_not_installed("Seurat")

  counts <- create_test_counts(n_cells = 5)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)

  results <- create_mock_scevan_results(colnames(seurat_obj))

  result_obj <- add_scevan_to_seurat(seurat_obj, results, prefix = "cnv_")

  expect_true("cnv_class" %in% colnames(result_obj@meta.data))
})

test_that("add_scevan_to_seurat warns without class column", {
  skip_if_not_installed("Seurat")

  counts <- create_test_counts(n_cells = 5)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)

  bad_results <- data.frame(other_col = 1:5, row.names = colnames(seurat_obj))

  expect_warning(
    add_scevan_to_seurat(seurat_obj, bad_results),
    "'class' column not found"
  )
})

# ============================================================================
# Tests for plot_scevan_classification
# ============================================================================

test_that("plot_scevan_classification errors without classification", {
  skip_if_not_installed("Seurat")

  counts <- create_test_counts(n_cells = 10)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)

  expect_error(
    plot_scevan_classification(seurat_obj),
    "Run add_scevan_to_seurat\\(\\) first"
  )
})

# ============================================================================
# Tests for summarize_scevan
# ============================================================================

test_that("summarize_scevan prints without error", {
  results <- create_mock_scevan_results(paste0("CELL", 1:20))

  # capture.output suppresses printed output
  out <- capture.output(summarize_scevan(results))

  expect_true(length(out) > 0)
  expect_true(any(grepl("Total cells", out)))
})

test_that("summarize_scevan handles results without subclone", {
  results <- data.frame(
    class = c("malignant", "non-malignant"),
    row.names = c("CELL1", "CELL2")
  )

  out <- capture.output(summarize_scevan(results))

  expect_true(any(grepl("Classification", out)))
})
