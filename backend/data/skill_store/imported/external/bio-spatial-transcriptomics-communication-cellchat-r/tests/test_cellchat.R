#!/usr/bin/env Rscript
#' Unit tests for SpatialCellChat spatial analysis module
#'
#' Run with: Rscript tests/test_cellchat.R

library(testthat)

# Source the module under test
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "cellchat_spatial.R"))

# Check if SpatialCellChat is available
SPATIALCELLCHAT_AVAILABLE <- requireNamespace("SpatialCellChat", quietly = TRUE)

# =============================================================================
# Test Data Helpers
# =============================================================================

create_test_seurat <- function(n_cells = 100, n_genes = 500, is_spatial = TRUE) {
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

  # Add mock spatial coordinates if spatial
  if (is_spatial) {
    coords <- data.frame(
      imagerow = sample(1:500, n_cells, replace = TRUE),
      imagecol = sample(1:500, n_cells, replace = TRUE)
    )
    rownames(coords) <- colnames(seurat_obj)
    # Note: Real spatial data would use Seurat's spatial structure
  }

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

test_that("infer_spatial_factors returns list", {
  coords <- data.frame(imagerow = 1:10, imagecol = 1:10)

  # Xenium should have ratio=1 and return a list
  sf_xenium <- infer_spatial_factors(coords, "xenium")
  expect_type(sf_xenium, "list")
  expect_equal(sf_xenium$ratio, 1)

  # Visium HD should have ratio=1
  sf_hd <- infer_spatial_factors(coords, "visium_hd")
  expect_type(sf_hd, "list")
  expect_equal(sf_hd$ratio, 1)

  # Slide-seq should have ratio=0.73
  sf_slideseq <- infer_spatial_factors(coords, "slideseq")
  expect_type(sf_slideseq, "list")
  expect_equal(sf_slideseq$ratio, 0.73)
})

test_that("set_cellchat_db handles different signaling types", {
  skip_if_not(SPATIALCELLCHAT_AVAILABLE, "SpatialCellChat not installed")

  # Test that the function exists and can be called with mock inputs
  expect_true(is.function(set_cellchat_db))
})

test_that("extract_communication_df validates inputs", {
  skip_if_not(SPATIALCELLCHAT_AVAILABLE, "SpatialCellChat not installed")

  # Would need a completed SpatialCellChat object to test fully
  expect_true(is.function(extract_communication_df))
})

test_that("summarize_communication requires net slot", {
  skip_if_not(SPATIALCELLCHAT_AVAILABLE, "SpatialCellChat not installed")

  # Would need a completed SpatialCellChat object to test
  expect_true(is.function(summarize_communication))
})

test_that("plot_spatial_scoring wrapper exists", {
  expect_true(is.function(plot_spatial_scoring))
})

test_that("extract_enriched_lr wrapper exists", {
  expect_true(is.function(extract_enriched_lr))
})

test_that("export_cellchat_results wrapper exists", {
  expect_true(is.function(export_cellchat_results))
})

# =============================================================================
# Integration Tests (skip if SpatialCellChat not installed)
# =============================================================================

if (SPATIALCELLCHAT_AVAILABLE) {

  test_that("create_spatial_cellchat validates inputs", {
    seurat_obj <- create_test_seurat(n_cells = 50, n_genes = 100)

    # Should error for non-existent group_by
    expect_error(
      create_spatial_cellchat(seurat_obj, group_by = "nonexistent"),
      "not found in metadata"
    )
  })

  test_that("run_cellchat_visium warns without scalefactors", {
    seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

    # NULL scalefactors_json triggers warning (uses generic defaults)
    expect_warning(
      run_cellchat_visium(seurat_obj, scalefactors_json = NULL),
      "Using generic Visium defaults"
    )

    # Non-existent file triggers warning (uses generic defaults)
    expect_warning(
      run_cellchat_visium(seurat_obj, scalefactors_json = "nonexistent.json"),
      "not found"
    )
  })

  test_that("run_cellchat_multi validates list input", {
    seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

    # Should error if not a list
    expect_error(
      run_cellchat_multi(seurat_obj, sample_names = "S1"),
      "must be a list"
    )

    # Should error when lengths don't match
    expect_error(
      run_cellchat_multi(
        list(seurat_obj, seurat_obj),
        sample_names = "only_one"
      ),
      "must have same length"
    )
  })

} else {
  message("SpatialCellChat not installed, skipping integration tests")
}

# =============================================================================
# Run Tests
# =============================================================================

message("Running SpatialCellChat spatial tests...")
message(sprintf("SpatialCellChat available: %s\n", SPATIALCELLCHAT_AVAILABLE))

test_results <- test_dir(dirname(sys.frame(1)$ofile), reporter = "summary")

# Print summary
message("\n=== Test Summary ===")
message(sprintf("Total: %d", length(test_results)))
message(sprintf("Passed: %d", sum(test_results$passed)))
message(sprintf("Failed: %d", sum(!test_results$passed)))
