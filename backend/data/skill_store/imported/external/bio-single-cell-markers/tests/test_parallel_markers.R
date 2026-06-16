# Unit tests for parallel marker finding functions
# Test suite for bio-single-cell-markers parallel execution

library(testthat)
library(Seurat)
library(dplyr)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source parallel functions
source(file.path(script_dir, "parallel_find_markers.R"))

context("Parallel Marker Finding")

# ============================================================================
# Test Data Helpers
# ============================================================================

create_test_seurat <- function(n_cells = 200, n_genes = 100, n_clusters = 4) {
  set.seed(42)

  # Create counts matrix
  counts <- matrix(rpois(n_cells * n_genes, lambda = 3),
                   nrow = n_genes, ncol = n_cells)
  rownames(counts) <- paste0("GENE", 1:n_genes)
  colnames(counts) <- paste0("CELL", 1:n_cells)

  # Create cluster assignments
  clusters <- sample(0:(n_clusters-1), n_cells, replace = TRUE)

  # Create Seurat object
  seurat_obj <- CreateSeuratObject(counts = counts)
  seurat_obj$seurat_clusters <- factor(clusters)
  Idents(seurat_obj) <- seurat_obj$seurat_clusters

  # Normalize
  seurat_obj <- NormalizeData(seurat_obj, verbose = FALSE)

  return(seurat_obj)
}

# ============================================================================
# Tests for GetParallelRecommendations
# ============================================================================

test_that("GetParallelRecommendations returns valid structure", {
  rec <- GetParallelRecommendations()

  expect_type(rec, "list")
  expect_true("system" %in% names(rec))
  expect_true("recommendations" %in% names(rec))
  expect_true("packages" %in% names(rec))

  expect_true("n_cores" %in% names(rec$system))
  expect_true("plan" %in% names(rec$recommendations))
  expect_true("recommended_workers" %in% names(rec$recommendations))
})

test_that("GetParallelRecommendations returns valid values", {
  rec <- GetParallelRecommendations()

  expect_gt(rec$system$n_cores, 0)
  expect_gt(rec$recommendations$recommended_workers, 0)
  expect_lte(rec$recommendations$recommended_workers, rec$system$n_cores)

  expect_true(rec$recommendations$plan %in% c("multicore", "multisession"))
})

# ============================================================================
# Tests for FindAllMarkersParallel
# ============================================================================

test_that("FindAllMarkersParallel works with sequential fallback", {
  seurat_obj <- create_test_seurat(n_cells = 100, n_clusters = 3)

  # Test basic execution (will use sequential if future not installed)
  markers <- FindAllMarkersParallel(
    seurat_obj,
    n_workers = 1,
    verbose = FALSE
  )

  expect_type(markers, "list")
  expect_gt(nrow(markers), 0)
  expect_true("cluster" %in% colnames(markers))
  expect_true("gene" %in% colnames(markers))
})

test_that("FindAllMarkersParallel respects parameters", {
  seurat_obj <- create_test_seurat(n_cells = 100, n_clusters = 3)

  # Test with custom parameters
  markers <- FindAllMarkersParallel(
    seurat_obj,
    n_workers = 1,
    only.pos = TRUE,
    min.pct = 0.5,
    logfc.threshold = 0.5,
    verbose = FALSE
  )

  expect_type(markers, "list")
  if (nrow(markers) > 0) {
    expect_true(all(markers$pct.1 >= 0.5))
  }
})

test_that("FindAllMarkersParallel handles invalid input gracefully", {
  # Test with NULL
  expect_error(
    FindAllMarkersParallel(NULL, verbose = FALSE),
    "Input must be a Seurat object"
  )
})

# ============================================================================
# Tests for FindMarkersParallel
# ============================================================================

test_that("FindMarkersParallel returns list of results", {
  skip_if_not_installed("future")
  skip_if_not_installed("future.apply")

  seurat_obj <- create_test_seurat(n_cells = 100, n_clusters = 3)

  markers_list <- FindMarkersParallel(
    seurat_obj,
    clusters = c(0, 1),
    n_workers = 2,
    verbose = FALSE
  )

  expect_type(markers_list, "list")
  expect_true("0" %in% names(markers_list) || "1" %in% names(markers_list))
})

test_that("FindMarkersParallel handles empty clusters", {
  skip_if_not_installed("future")

  seurat_obj <- create_test_seurat(n_cells = 50, n_clusters = 2)

  # Request non-existent cluster - should handle gracefully
  # (suppress warnings from wilcoxon test about ties)
  suppressWarnings({
    markers_list <- FindMarkersParallel(
      seurat_obj,
      clusters = c(0, 1, 99),
      n_workers = 2,
      verbose = FALSE
    )
  })

  # Should return results for valid clusters
  expect_type(markers_list, "list")
})

# ============================================================================
# Tests for FindAllMarkersBatch
# ============================================================================

test_that("FindAllMarkersBatch processes multiple samples", {
  seurat_obj1 <- create_test_seurat(n_cells = 50, n_clusters = 2)
  seurat_obj2 <- create_test_seurat(n_cells = 50, n_clusters = 2)

  seurat_list <- list(
    sample1 = seurat_obj1,
    sample2 = seurat_obj2
  )

  results <- FindAllMarkersBatch(
    seurat_list,
    n_workers = 1,
    verbose = FALSE
  )

  expect_type(results, "list")
  expect_equal(length(results), 2)
  expect_true("sample1" %in% names(results))
  expect_true("sample2" %in% names(results))
})

test_that("FindAllMarkersBatch adds sample column", {
  seurat_obj <- create_test_seurat(n_cells = 50, n_clusters = 2)

  seurat_list <- list(sample1 = seurat_obj)

  results <- FindAllMarkersBatch(
    seurat_list,
    n_workers = 1,
    verbose = FALSE
  )

  if (nrow(results[[1]]) > 0) {
    expect_true("sample" %in% colnames(results[[1]]))
    expect_equal(unique(results[[1]]$sample), "sample1")
  }
})

# ============================================================================
# Tests for BenchmarkParallelMarkers
# ============================================================================

test_that("BenchmarkParallelMarkers returns benchmark results", {
  skip_if_not_installed("future")

  seurat_obj <- create_test_seurat(n_cells = 50, n_clusters = 2)

  # Test with single configuration
  results <- BenchmarkParallelMarkers(
    seurat_obj,
    n_workers = c(1),
    iterations = 1
  )

  expect_type(results, "list")
  expect_equal(nrow(results), 1)
  expect_true("workers" %in% colnames(results))
  expect_true("mean_time" %in% colnames(results))
})

test_that("BenchmarkParallelMarkers calculates speedup correctly", {
  skip_if_not_installed("future")

  seurat_obj <- create_test_seurat(n_cells = 50, n_clusters = 2)

  results <- BenchmarkParallelMarkers(
    seurat_obj,
    n_workers = c(1, 2),
    iterations = 1
  )

  if (nrow(results) >= 2) {
    expect_true("speedup" %in% colnames(results))
    expect_true("efficiency" %in% colnames(results))

    # Speedup should be positive
    expect_gt(results$speedup[1], 0)

    # Baseline (1 worker) should have speedup of 1
    expect_equal(results$speedup[1], 1.0)
  }
})

# ============================================================================
# Integration Tests
# ============================================================================

test_that("Complete parallel workflow works", {
  seurat_obj <- create_test_seurat(n_cells = 100, n_clusters = 3)

  # Get recommendations
  rec <- GetParallelRecommendations()

  # Run parallel marker finding
  markers <- FindAllMarkersParallel(
    seurat_obj,
    n_workers = 1,
    verbose = FALSE
  )

  # Process results
  top_markers <- markers %>%
    group_by(cluster) %>%
    slice_max(n = 5, order_by = avg_log2FC) %>%
    ungroup()

  expect_gt(nrow(top_markers), 0)
})

# ============================================================================
# Edge Cases
# ============================================================================

test_that("Functions handle single-cluster data", {
  seurat_obj <- create_test_seurat(n_cells = 50, n_clusters = 1)

  # Should handle gracefully
  expect_error(
    FindAllMarkersParallel(seurat_obj, n_workers = 1, verbose = FALSE),
    NA  # May error or return empty - both acceptable
  )
})

test_that("Functions handle very small datasets", {
  seurat_obj <- create_test_seurat(n_cells = 10, n_clusters = 2)

  markers <- FindAllMarkersParallel(
    seurat_obj,
    n_workers = 1,
    verbose = FALSE
  )

  # Should return result or error gracefully
  expect_true(is.data.frame(markers) || is.null(markers))
})

# Note: Full parallel tests require 'future' and 'future.apply' packages.
# Install with: install.packages(c('future', 'future.apply'))
