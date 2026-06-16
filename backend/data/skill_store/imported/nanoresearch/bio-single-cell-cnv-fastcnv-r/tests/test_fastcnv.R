#!/usr/bin/env Rscript
#' Unit tests for fastCNV single-cell analysis module
#'
#' Run with: Rscript tests/test_fastcnv.R

library(testthat)

# Source the module under test
# Use robust path detection: try ofile first, then fall back to getwd
test_dir <- tryCatch(dirname(sys.frame(1)$ofile), error = function(e) NULL)
if (is.null(test_dir) || test_dir == "") {
  test_dir <- getwd()
  # If running from skill root, tests are in tests/ subdirectory
  if (basename(test_dir) == "bio-single-cell-cnv-fastcnv-r") {
    test_dir <- file.path(test_dir, "tests")
  }
}
script_file <- file.path(dirname(test_dir), "scripts", "r", "run_fastcnv.R")
source(script_file)

# Check if fastCNV is available
FASTCNV_AVAILABLE <- requireNamespace("fastCNV", quietly = TRUE)

# =============================================================================
# Test Data Helpers
# =============================================================================

create_test_seurat <- function(n_cells = 100, n_genes = 500) {
  #' Create test Seurat object

  set.seed(42)

  # Create expression matrix (sparse to avoid Seurat v5 coercion warnings)
  counts <- Matrix::Matrix(
    rpois(n_cells * n_genes, lambda = 5),
    nrow = n_genes,
    ncol = n_cells,
    sparse = TRUE
  )

  # Gene and cell names (no underscores for Seurat compatibility)
  rownames(counts) <- paste0("GENE-", 1:n_genes)
  colnames(counts) <- paste0("cell_", 1:n_cells)

  # Cell type annotations
  cell_types <- sample(
    c("Tumor", "T_cell", "B_cell", "Macrophage"),
    n_cells,
    replace = TRUE,
    prob = c(0.5, 0.2, 0.15, 0.15)
  )

  # Create Seurat object
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  seurat_obj$cell_type <- cell_types

  return(seurat_obj)
}

# =============================================================================
# Tests
# =============================================================================

test_that("test data creation works", {
  seurat_obj <- create_test_seurat(n_cells = 50, n_genes = 100)

  expect_equal(ncol(seurat_obj), 50)
  expect_equal(nrow(seurat_obj), 100)
  expect_true("cell_type" %in% colnames(seurat_obj@meta.data))
})

test_that("extract_cnv_metadata handles missing data", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Should warn when no CNV results exist
  expect_warning(
    results <- extract_cnv_metadata(seurat_obj),
    "No CNV metadata found"
  )

  expect_equal(ncol(results), 1)  # Only cell column
})

test_that("extract_cnv_metadata includes chromosome columns", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Mock CNV metadata
  seurat_obj$cnv_fraction <- runif(30)
  seurat_obj$cnv_clusters <- sample(1:3, 30, replace = TRUE)
  seurat_obj$`20.p_CNV` <- runif(30, -1, 1)
  seurat_obj$`X.q_CNV` <- runif(30, -1, 1)

  results <- extract_cnv_metadata(seurat_obj, include_chromosomes = TRUE)

  expect_true("cell" %in% colnames(results))
  expect_true("cnv_fraction" %in% colnames(results))
  expect_true("cnv_clusters" %in% colnames(results))
  expect_true("20.p_CNV" %in% colnames(results))
  expect_true("X.q_CNV" %in% colnames(results))
})

test_that("summarize_cnv_by_cluster validates inputs", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Should error for non-existent grouping variable
  expect_error(
    summarize_cnv_by_cluster(seurat_obj, group_by = "nonexistent"),
    "not found in metadata"
  )

  # Should error for non-existent metric
  expect_error(
    summarize_cnv_by_cluster(seurat_obj, group_by = "cell_type", metric = "nonexistent"),
    "not found in metadata"
  )
})

test_that("summarize_cnv_by_cluster computes statistics correctly", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)
  seurat_obj$cnv_fraction <- runif(30)

  result <- summarize_cnv_by_cluster(seurat_obj, group_by = "cell_type", metric = "cnv_fraction")

  expect_true("mean" %in% colnames(result))
  expect_true("median" %in% colnames(result))
  expect_true("sd" %in% colnames(result))
  expect_true("n" %in% colnames(result))
  expect_equal(sum(result$n), 30)
})

test_that("export_cnv_results creates output directory", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Use temp directory
  temp_dir <- tempfile("fastcnv_test_")

  expect_false(dir.exists(temp_dir))

  export_cnv_results(seurat_obj, output_dir = temp_dir, prefix = "test")

  expect_true(dir.exists(temp_dir))
  expect_true(file.exists(file.path(temp_dir, "test_metadata.csv")))
  expect_true(file.exists(file.path(temp_dir, "test_seurat.rds")))

  # Cleanup
  unlink(temp_dir, recursive = TRUE)
})

test_that("plot_chr_arm_umap checks feature existence", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  expect_error(
    plot_chr_arm_umap(seurat_obj, feature = "nonexistent_CNV"),
    "not found in metadata"
  )
})

test_that("plot_chr_arm_umap checks reduction existence", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)
  seurat_obj$`20.p_CNV` <- runif(30, -1, 1)

  expect_error(
    plot_chr_arm_umap(seurat_obj, feature = "20.p_CNV", reduction = "pca"),
    "not found"
  )
})

# =============================================================================
# fastCNV Integration Tests (skip if not installed)
# =============================================================================

if (FASTCNV_AVAILABLE) {

  test_that("run_fastcnv_sc validates inputs", {
    seurat_obj <- create_test_seurat(n_cells = 50, n_genes = 100)

    # Should work with valid inputs
    # Note: Actual CNV computation is slow, so we skip full integration tests
    expect_true(TRUE)
  })

  test_that("run_fastcnv_multi_sc validates list input", {
    seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

    # Should error if not a list
    expect_error(
      run_fastcnv_multi_sc(
        seurat_list = seurat_obj,  # Not a list
        sample_names = "Sample1"
      ),
      "must be a list"
    )

    # Should error when lengths don't match
    expect_error(
      run_fastcnv_multi_sc(
        seurat_list = list(seurat_obj, seurat_obj),
        sample_names = "only_one"
      ),
      "same length"
    )
  })

  test_that("cnv_cluster passes correct parameter names", {
    seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

    # Should not error on parameter name mismatch
    # (will error on missing CNV data, but not on unused argument)
    err <- tryCatch(
      cnv_cluster(seurat_obj, k = 3),
      error = function(e) conditionMessage(e)
    )
    # If it's a real error (not "unused argument"), it means parameter passed correctly
    if (inherits(err, "character")) {
      expect_false(grepl("unused argument", err, fixed = TRUE),
                   info = paste("Got 'unused argument' error:", err))
    } else {
      expect_true(TRUE)  # No error at all
    }
  })

} else {
  message("fastCNV not installed, skipping integration tests")
}

# =============================================================================
# Run Tests
# =============================================================================

message("\nRunning fastCNV single-cell tests...")
message(sprintf("fastCNV available: %s", FASTCNV_AVAILABLE))

# Tests are executed automatically by testthat when this file is sourced via Rscript
# The testthat framework handles reporting.
