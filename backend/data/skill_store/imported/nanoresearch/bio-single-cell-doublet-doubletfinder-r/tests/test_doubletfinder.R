# Unit Tests for DoubletFinder Analysis
# ======================================
#
# Tests for core_analysis.R, visualization.R, and utils.R modules.

library(testthat)

# Source the functions
source("../scripts/r/utils.R")
source("../scripts/r/core_analysis.R")

# Check if DoubletFinder and Seurat are available
df_available <- requireNamespace("DoubletFinder", quietly = TRUE)
seurat_available <- requireNamespace("Seurat", quietly = TRUE)

test_that("get_10x_doublet_rate calculates correctly", {
  # 1000 cells -> ~0.8% rate
  expect_equal(get_10x_doublet_rate(1000), 0.008, tolerance = 0.001)

  # 5000 cells -> ~4% rate
  expect_equal(get_10x_doublet_rate(5000), 0.04, tolerance = 0.001)

  # 10000 cells -> ~8% rate
  expect_equal(get_10x_doublet_rate(10000), 0.08, tolerance = 0.001)
})

test_that("estimate_expected_doublets returns reasonable values", {
  n_cells <- 5000

  # 10x v3
  n_exp <- estimate_expected_doublets(n_cells, platform = "10x_v3")
  expect_gt(n_exp, 0)
  expect_lt(n_exp, n_cells)

  # 10x v3.1 (lower doublet rate)
  n_exp_v31 <- estimate_expected_doublets(n_cells, platform = "10x_v3_1")
  n_exp_v3 <- estimate_expected_doublets(n_cells, platform = "10x_v3")
  expect_lt(n_exp_v31, n_exp_v3)
})

test_that("validate_expected_doublets identifies problematic rates", {
  # Very low rate (< 0.5%)
  expect_warning(validate_expected_doublets(1000, 3))

  # Very high rate (> 15%)
  expect_warning(validate_expected_doublets(1000, 200))

  # Normal rate
  expect_message(validate_expected_doublets(1000, 50), "reasonable")
})

test_that("recommend_pcs returns valid number", {
  skip_if(!seurat_available, "Seurat not installed")

  # Create minimal test data
  set.seed(42)
  counts <- matrix(rpois(2000, lambda = 5), nrow = 100)
  rownames(counts) <- paste0("gene-", 1:100)
  colnames(counts) <- paste0("cell-", 1:20)

  seu <- Seurat::CreateSeuratObject(counts = counts)
  seu <- Seurat::NormalizeData(seu)
  seu <- Seurat::FindVariableFeatures(seu)
  seu <- Seurat::ScaleData(seu)
  seu <- Seurat::RunPCA(seu, npcs = 10)

  n_pcs <- recommend_pcs(seu, variance_threshold = 0.8)

  expect_gt(n_pcs, 0)
  expect_lte(n_pcs, 10)
})

test_that("get_loading_recommendation calculates correctly", {
  target <- 5000
  loading <- get_loading_recommendation(target)

  expect_gt(loading, target)
  expect_equal(loading, 8000)  # 5000 * 1.6 = 8000
})

test_that("parse_df_column_name extracts parameters", {
  col_name <- "DF.classifications_0.25_0.09_500"
  params <- parse_df_column_name(col_name)

  expect_equal(params$pN, 0.25)
  expect_equal(params$pK, 0.09)
  expect_equal(params$nExp, 500)
})

test_that("parse_df_column_name handles errors", {
  expect_error(parse_df_column_name("invalid_column_name"))
})

# Integration tests (require full environment)
test_that("Complete workflow with minimal data", {
  skip_if(!df_available, "DoubletFinder not installed")
  skip_if(!seurat_available, "Seurat not installed")

  # Create minimal test data
  set.seed(42)
  counts <- matrix(rpois(2000, lambda = 5), nrow = 100)
  rownames(counts) <- paste0("gene_", 1:100)
  colnames(counts) <- paste0("cell_", 1:20)

  seu <- Seurat::CreateSeuratObject(counts = counts)
  seu <- Seurat::NormalizeData(seu)
  seu <- Seurat::FindVariableFeatures(seu, nfeatures = 50)
  seu <- Seurat::ScaleData(seu)
  seu <- Seurat::RunPCA(seu, npcs = 5)
  seu <- Seurat::RunUMAP(seu, dims = 1:5)
  seu <- Seurat::FindNeighbors(seu, dims = 1:5)
  seu <- Seurat::FindClusters(seu, resolution = 0.5)

  # Check preprocessing
  expect_true(check_seurat_for_df(seu))

  # Estimate doublets
  n_exp <- estimate_doublet_rate(ncol(seu))
  expect_gt(n_exp, 0)
})

test_that("modelHomotypic works correctly", {
  skip_if(!df_available, "DoubletFinder not installed")

  # Create test annotations
  annotations <- c(rep("A", 50), rep("B", 30), rep("C", 20))

  prop <- DoubletFinder::modelHomotypic(annotations)

  expect_gt(prop, 0)
  expect_lt(prop, 1)

  # Check calculation
  expected <- sum((table(annotations) / length(annotations))^2)
  expect_equal(prop, expected)
})

test_that("run_doubletfinder works", {
  skip_if_not_installed("Seurat")
  skip_if_not_installed("DoubletFinder")

  # Create minimal test data
  data("pbmc_small", package = "Seurat")
  seurat_obj <- pbmc_small

  # Test function exists
  expect_true(exists("run_doubletfinder"))
})

test_that("filter_doublets works", {
  skip_if_not_installed("Seurat")

  # Create minimal test data
  set.seed(42)
  counts <- matrix(rpois(2000, lambda = 5), nrow = 100)
  rownames(counts) <- paste0("gene-", 1:100)
  colnames(counts) <- paste0("cell-", 1:20)

  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)

  # Mock doublet predictions
  seurat_obj$doublet <- sample(c("Singlet", "Doublet"), ncol(seurat_obj), replace = TRUE)

  # Test filtering
  seurat_filtered <- filter_doublets(seurat_obj)

  expect_true(ncol(seurat_filtered) <= ncol(seurat_obj))
  expect_true("Singlet" %in% seurat_filtered$doublet)
})

# Run all tests
cat("Running DoubletFinder tests...\n")
if (df_available && seurat_available) {
  cat("All packages available - running full test suite\n")
} else {
  cat("Some packages missing - running limited tests\n")
  cat("Missing:", paste(c(
    if (!df_available) "DoubletFinder",
    if (!seurat_available) "Seurat"
  ), collapse = ", "), "\n")
}
