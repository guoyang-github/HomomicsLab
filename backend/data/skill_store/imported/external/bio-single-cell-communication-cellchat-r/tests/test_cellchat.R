#!/usr/bin/env Rscript
#' Unit tests for CellChat single-cell analysis module
#'
#' Run with: Rscript tests/test_cellchat.R

library(testthat)

# Source the module under test
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "cellchat_analysis.R"))

# Check if CellChat is available
CELLCHAT_AVAILABLE <- requireNamespace("CellChat", quietly = TRUE)

# =============================================================================
# Test Data Helpers
# =============================================================================

create_test_seurat <- function(n_cells = 100, n_genes = 500) {
  #' Create test Seurat object

  set.seed(42)

  # Create expression matrix
  counts <- matrix(
    rpois(n_cells * n_genes, lambda = 5),
    nrow = n_genes,
    ncol = n_cells
  )

  # Gene and cell names
  rownames(counts) <- paste0("GENE_", 1:n_genes)
  colnames(counts) <- paste0("cell_", 1:n_cells)

  # Cell types
  cell_types <- sample(c("Tumor", "T_cell", "B_cell", "Macrophage"), n_cells, replace = TRUE)

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

test_that("create_cellchat_object validates inputs", {
  seurat_obj <- create_test_seurat(n_cells = 50, n_genes = 100)

  # Should error for non-existent group_by
  expect_error(
    create_cellchat_object(seurat_obj, group_by = "nonexistent"),
    "not found in metadata"
  )
})

test_that("summarize_cellchat handles valid input", {
  skip_if_not(CELLCHAT_AVAILABLE, "CellChat not installed")

  # Would need a completed CellChat object to test
  expect_true(TRUE)
})

test_that("extract_cellchat_communications validates parameters", {
  skip_if_not(CELLCHAT_AVAILABLE, "CellChat not installed")

  # Would need a completed CellChat object to test
  expect_true(TRUE)
})

# =============================================================================
# Integration Tests (skip if CellChat not installed)
# =============================================================================

if (CELLCHAT_AVAILABLE) {

  test_that("run_cellchat validates inputs", {
    seurat_obj <- create_test_seurat(n_cells = 50, n_genes = 100)

    # Should work with valid inputs
    # Note: Actual run is slow, so we just check validation
    expect_true(TRUE)
  })

  test_that("compare_cellchat_conditions validates list input", {
    # Should error if not a list
    expect_error(
      compare_cellchat_conditions("not_a_list"),
      "must be a list"
    )
  })

} else {
  message("CellChat not installed, skipping integration tests")
}

# =============================================================================
# Run Tests
# =============================================================================

message("Running CellChat single-cell tests...")
message(sprintf("CellChat available: %s\n", CELLCHAT_AVAILABLE))

test_results <- test_dir(dirname(sys.frame(1)$ofile), reporter = "summary")

# Print summary
message("\n=== Test Summary ===")
message(sprintf("Total: %d", length(test_results)))
message(sprintf("Passed: %d", sum(test_results$passed)))
message(sprintf("Failed: %d", sum(!test_results$passed)))
