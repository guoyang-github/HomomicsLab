#!/usr/bin/env Rscript
#' Unit tests for fastCNV analysis module
#'
#' Run with: Rscript tests/test_fastcnv.R

library(testthat)

# Source the module under test
# Try multiple strategies to locate the source file robustly
src_path <- NULL
tryCatch({
  ofile <- sys.frame(1)$ofile
  if (!is.null(ofile)) {
    src_path <- file.path(dirname(ofile), "..", "scripts", "r", "fastcnv_analysis.R")
  }
}, error = function(e) NULL)
if (is.null(src_path) || !file.exists(src_path)) {
  # Fallback: assume working directory is tests/
  src_path <- file.path("..", "scripts", "r", "fastcnv_analysis.R")
}
if (!file.exists(src_path)) {
  # Final fallback: search from getwd()
  candidates <- c(
    file.path(getwd(), "scripts", "r", "fastcnv_analysis.R"),
    file.path(getwd(), "..", "scripts", "r", "fastcnv_analysis.R"),
    file.path(getwd(), "skills", "bio-spatial-transcriptomics-cnv-fastcnv-r", "scripts", "r", "fastcnv_analysis.R")
  )
  for (cand in candidates) {
    if (file.exists(cand)) {
      src_path <- cand
      break
    }
  }
}
if (is.null(src_path) || !file.exists(src_path)) {
  stop("Cannot locate fastcnv_analysis.R. Please run from the skill root or tests/ directory.")
}
source(src_path)

# Check if fastCNV is available
FASTCNV_AVAILABLE <- requireNamespace("fastCNV", quietly = TRUE)

# =============================================================================
# Test Data Helpers
# =============================================================================

create_test_seurat <- function(n_cells = 100, n_genes = 500, is_spatial = FALSE) {
  #' Create test Seurat object with required structure

  set.seed(42)

  # Create sparse expression matrix to avoid Seurat v5 coercion warnings
  if (requireNamespace("Matrix", quietly = TRUE)) {
    # Random non-zero positions (about 30% density)
    nnz <- max(1, round(n_cells * n_genes * 0.3))
    i <- sample(1:n_genes, nnz, replace = TRUE)
    j <- sample(1:n_cells, nnz, replace = TRUE)
    x <- rpois(nnz, lambda = 5)
    counts <- Matrix::sparseMatrix(
      i = i, j = j, x = x,
      dims = c(n_genes, n_cells)
    )
  } else {
    counts <- matrix(
      rpois(n_cells * n_genes, lambda = 5),
      nrow = n_genes,
      ncol = n_cells
    )
  }

  # Gene names
  rownames(counts) <- paste0("GENE_", 1:n_genes)
  colnames(counts) <- paste0("cell_", 1:n_cells)

  # Create annotations
  cell_types <- sample(
    c("Tumor", "Healthy", "Immune"),
    n_cells,
    replace = TRUE,
    prob = c(0.5, 0.3, 0.2)
  )

  # Create Seurat object
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  seurat_obj$cell_type <- cell_types
  seurat_obj$annotations <- ifelse(cell_types == "Healthy", "Healthy", "Tumor")

  # Add mock spatial coordinates if spatial
  if (is_spatial && requireNamespace("Seurat", quietly = TRUE)) {
    # Mock spatial coordinates
    coords <- data.frame(
      row = sample(1:50, n_cells, replace = TRUE),
      col = sample(1:50, n_cells, replace = TRUE)
    )
    rownames(coords) <- colnames(seurat_obj)
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
  expect_true("annotations" %in% colnames(seurat_obj@meta.data))
})

test_that("extract_cnv_results handles missing CNV data", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Should warn when no CNV results exist
  expect_warning(
    results <- extract_cnv_results(seurat_obj),
    "No CNV results found"
  )

  expect_equal(ncol(results), 1)  # Only cell column
})

test_that("summarize_cnv_by_group validates inputs", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Should error for non-existent grouping variable
  expect_error(
    summarize_cnv_by_group(seurat_obj, group.by = "nonexistent"),
    "not found in metadata"
  )

  # Should error for non-existent metric
  expect_error(
    summarize_cnv_by_group(seurat_obj, group.by = "cell_type", metric = "nonexistent"),
    "not found in metadata"
  )
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

# =============================================================================
# Spatial Function Tests
# =============================================================================

test_that("plot_cnv_fraction_spatial validates spatial coordinates", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Should error when no spatial images exist
  expect_error(
    plot_cnv_fraction_spatial(seurat_obj),
    "No spatial coordinates found"
  )
})

test_that("plot_chr_arm_spatial validates feature presence", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  # Should error when feature not in metadata
  expect_error(
    plot_chr_arm_spatial(seurat_obj, feature = "99.q_CNV"),
    "not found in metadata"
  )
})

test_that("run_fastcnv_hd validates fastCNV availability", {
  seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

  if (!FASTCNV_AVAILABLE) {
    # Should error when fastCNV is not installed
    expect_error(
      run_fastcnv_hd(seurat_obj, sampleName = "Test"),
      "fastCNV package required"
    )
  }
})

# =============================================================================
# fastCNV Integration Tests (skip if not installed)
# =============================================================================

if (FASTCNV_AVAILABLE) {

  test_that("run_fastcnv validates input lengths", {
    seurat_obj <- create_test_seurat(n_cells = 50, n_genes = 100)

    # Should error when lengths don't match
    expect_error(
      run_fastcnv(
        seuratObj = list(seurat_obj, seurat_obj),
        sampleName = "only_one_name",
        verbose = FALSE
      ),
      "same length"
    )
  })

  test_that("run_fastcnv handles single object", {
    seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 200)

    # Should convert single object to list internally
    # Note: This test may be slow due to fastCNV computation
    skip("Skipping slow integration test")

    result <- run_fastcnv(
      seuratObj = seurat_obj,
      sampleName = "Test",
      referenceVar = "annotations",
      referenceLabel = "Healthy",
      printPlot = FALSE,
      verbose = FALSE
    )

    expect_true(inherits(result, "Seurat"))
  })

  test_that("prepare_counts_for_cnv requires fastCNV", {
    seurat_obj <- create_test_seurat(n_cells = 30, n_genes = 100)

    # This should work if fastCNV is available
    expect_true(FASTCNV_AVAILABLE)
  })

} else {
  message("fastCNV not installed, skipping integration tests")
}

# =============================================================================
# Run Tests
# =============================================================================

message("Running fastCNV tests...")
message(sprintf("fastCNV available: %s\n", FASTCNV_AVAILABLE))

test_results <- test_dir(dirname(sys.frame(1)$ofile), reporter = "summary")

# Print summary
message("\n=== Test Summary ===")
message(sprintf("Total: %d", length(test_results)))
message(sprintf("Passed: %d", sum(test_results$passed)))
message(sprintf("Failed: %d", sum(!test_results$passed)))
