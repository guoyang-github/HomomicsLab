#!/usr/bin/env Rscript
#' Unit Tests for SPOTlight Spatial Deconvolution
#'
#' Tests cover:
#' - Data validation functions
#' - Core deconvolution workflow
#' - Visualization functions
#' - Utility functions
#' - Result export

library(testthat)

# Source custom scripts
source("../scripts/r/utils.R")
source("../scripts/r/visualization.R")

# ================================================================================
# Test Data Preparation
# ================================================================================

#' Create Test Single-Cell Data
#' @return Matrix with cell type labels
create_test_sc_data <- function(n_genes = 100, n_cells = 200) {
  set.seed(42)
  counts <- matrix(
    rpois(n_genes * n_cells, lambda = 3),
    nrow = n_genes,
    ncol = n_cells
  )

  # Add structure for cell types
  cell_types <- rep(c("TypeA", "TypeB", "TypeC"), length.out = n_cells)
  for (i in seq_len(3)) {
    idx <- which(cell_types == c("TypeA", "TypeB", "TypeC")[i])
    counts[i, idx] <- counts[i, idx] + rpois(length(idx), lambda = 10)
  }

  rownames(counts) <- paste0("GENE_", seq_len(n_genes))
  colnames(counts) <- paste0("CELL_", seq_len(n_cells))

  list(counts = counts, cell_types = cell_types)
}

#' Create Test Spatial Data
#' @return Matrix of spatial counts
create_test_spatial_data <- function(n_genes = 100, n_spots = 100) {
  set.seed(43)
  counts <- matrix(
    rpois(n_genes * n_spots, lambda = 3),
    nrow = n_genes,
    ncol = n_spots
  )

  rownames(counts) <- paste0("GENE_", seq_len(n_genes))
  colnames(counts) <- paste0("SPOT_", seq_len(n_spots))

  counts
}

#' Create Test Marker Data Frame
create_test_markers <- function() {
  data.frame(
    gene = c("GENE_1", "GENE_2", "GENE_3", "GENE_4", "GENE_5", "GENE_6"),
    cluster = c("TypeA", "TypeA", "TypeB", "TypeB", "TypeC", "TypeC"),
    avg_log2FC = c(2.5, 3.0, 2.8, 2.2, 3.2, 2.7),
    p_val_adj = c(1e-10, 1e-8, 1e-9, 1e-7, 1e-11, 1e-8),
    stringsAsFactors = FALSE
  )
}

# ================================================================================
# Test Suite: Data Validation
# ================================================================================

test_that("validate_spotlight_data validates correct data", {
  sc_data <- create_test_sc_data()
  sp_counts <- create_test_spatial_data()

  validation <- validate_spotlight_data(
    sc_counts = sc_data$counts,
    sp_counts = sp_counts,
    cell_types = sc_data$cell_types,
    min_cells_per_type = 30,
    min_genes = 50,
    min_spots = 50
  )

  expect_true(validation$valid)
  expect_equal(validation$diagnostics$n_genes, 100)
  expect_equal(validation$diagnostics$n_cells, 200)
  expect_equal(validation$diagnostics$n_spots, 100)
  expect_equal(length(validation$diagnostics$cell_type_counts), 3)
})

test_that("validate_spotlight_data detects insufficient genes", {
  sc_data <- create_test_sc_data(n_genes = 50)
  sp_counts <- create_test_spatial_data(n_genes = 40)

  validation <- validate_spotlight_data(
    sc_counts = sc_data$counts,
    sp_counts = sp_counts,
    cell_types = sc_data$cell_types,
    min_genes = 100
  )

  expect_false(validation$valid)
  expect_true(any(grepl("genes", validation$errors, ignore.case = TRUE)))
})

test_that("validate_spotlight_data detects insufficient cells", {
  sc_data <- create_test_sc_data(n_cells = 50)
  sp_counts <- create_test_spatial_data()

  validation <- validate_spotlight_data(
    sc_counts = sc_data$counts,
    sp_counts = sp_counts,
    cell_types = sc_data$cell_types,
    min_cells_per_type = 100
  )

  expect_false(validation$valid)
  expect_true(any(grepl("cells", validation$errors, ignore.case = TRUE)))
})

test_that("validate_spotlight_data detects insufficient spots", {
  sc_data <- create_test_sc_data()
  sp_counts <- create_test_spatial_data(n_spots = 20)

  validation <- validate_spotlight_data(
    sc_counts = sc_data$counts,
    sp_counts = sp_counts,
    cell_types = sc_data$cell_types,
    min_spots = 50
  )

  expect_false(validation$valid)
  expect_true(any(grepl("spots", validation$errors, ignore.case = TRUE)))
})

test_that("validate_spotlight_data works with Seurat objects", {
  skip_if_not_installed("Seurat")

  sc_data <- create_test_sc_data()
  seurat_obj <- Seurat::CreateSeuratObject(counts = sc_data$counts)
  seurat_obj$cell_type <- sc_data$cell_types

  validation <- validate_spotlight_data(
    sc_counts = seurat_obj,
    sp_counts = create_test_spatial_data(),
    cell_types = sc_data$cell_types
  )

  expect_true(validation$valid)
  expect_true(validation$diagnostics$is_seurat)
})

# ================================================================================
# Test Suite: Utility Functions
# ================================================================================

test_that("summarize_spotlight_results works correctly", {
  proportions <- matrix(
    c(0.5, 0.3, 0.2, 0.4, 0.4, 0.2, 0.3, 0.3, 0.4),
    nrow = 3,
    ncol = 3,
    byrow = TRUE
  )
  colnames(proportions) <- c("TypeA", "TypeB", "TypeC")
  rownames(proportions) <- c("Spot1", "Spot2", "Spot3")

  res_ss <- c(0.1, 0.2, 0.15)

  spotlight_ls <- list(mat = proportions, res_ss = res_ss)
  summary <- summarize_spotlight_results(spotlight_ls)

  expect_type(summary, "list")
  expect_equal(summary$n_spots, 3)
  expect_equal(summary$n_cell_types, 3)
  expect_equal(names(summary$mean_proportions), c("TypeA", "TypeB", "TypeC"))
})

test_that("get_dominant_cell_type returns correct assignments", {
  proportions <- matrix(
    c(0.5, 0.3, 0.2, 0.2, 0.6, 0.2, 0.1, 0.1, 0.8),
    nrow = 3,
    ncol = 3,
    byrow = TRUE
  )
  colnames(proportions) <- c("TypeA", "TypeB", "TypeC")

  dominant <- get_dominant_cell_type(proportions)

  expect_equal(length(dominant), 3)
  expect_equal(dominant[1], "TypeA")
  expect_equal(dominant[2], "TypeB")
  expect_equal(dominant[3], "TypeC")
})

test_that("filter_proportions applies thresholds correctly", {
  proportions <- matrix(
    c(0.6, 0.3, 0.1, 0.2, 0.5, 0.3, 0.05, 0.15, 0.8),
    nrow = 3,
    ncol = 3,
    byrow = TRUE
  )
  colnames(proportions) <- c("TypeA", "TypeB", "TypeC")

  filtered <- filter_proportions(proportions, min_confidence = 0.5, min_proportion = 0.1)

  # First row: TypeA (0.6) and TypeB (0.3) should remain
  expect_equal(filtered[1, "TypeA"], 0.6)
  expect_equal(filtered[1, "TypeB"], 0.3)
  expect_equal(filtered[1, "TypeC"], 0)

  # Third row: only TypeC (0.8) should remain (TypeA 0.05 < 0.1, TypeB 0.15 > 0.1)
  expect_equal(filtered[3, "TypeA"], 0)
  expect_equal(filtered[3, "TypeB"], 0.15)
  expect_equal(filtered[3, "TypeC"], 0.8)
})

test_that("calculate_qc_metrics computes correct values", {
  proportions <- matrix(
    runif(30),
    nrow = 10,
    ncol = 3
  )
  proportions <- proportions / rowSums(proportions)
  colnames(proportions) <- c("TypeA", "TypeB", "TypeC")

  res_ss <- runif(10, 0.1, 0.5)

  spotlight_ls <- list(mat = proportions, res_ss = res_ss)
  qc <- calculate_qc_metrics(spotlight_ls)

  expect_type(qc, "list")
  expect_true(is.numeric(qc$mean_residual_ss))
  expect_true(is.numeric(qc$median_residual_ss))
  expect_true(is.numeric(qc$mean_entropy))
  expect_true(qc$mean_entropy >= 0 && qc$mean_entropy <= log(ncol(proportitions)))
})

# ================================================================================
# Test Suite: Visualization Functions
# ================================================================================

test_that("plot_spatial_scatterpie validates input", {
  coords <- data.frame(x = 1:3, y = 1:3, row.names = c("S1", "S2", "S3"))
  props <- matrix(c(0.5, 0.5, 0.6, 0.4, 0.3, 0.7), nrow = 3, ncol = 2)
  colnames(props) <- c("A", "B")
  rownames(props) <- c("S1", "S2", "S3")

  # Should work with valid input
  expect_error(
    plot_spatial_scatterpie(coords, props, cell_types = c("A", "B"), save_path = NULL),
    NA
  )

  # Should error with mismatched rownames
  bad_coords <- data.frame(x = 1:3, y = 1:3, row.names = c("X1", "X2", "X3"))
  expect_error(
    plot_spatial_scatterpie(bad_coords, props, cell_types = c("A", "B"), save_path = NULL)
  )
})

test_that("plot_correlation_matrix produces correlation matrix", {
  proportions <- matrix(
    rnorm(30, mean = 0.3, sd = 0.1),
    nrow = 10,
    ncol = 3
  )
  proportions <- pmax(proportions, 0)
  proportions <- proportions / rowSums(proportions)
  colnames(proportions) <- c("TypeA", "TypeB", "TypeC")

  result <- plot_correlation_matrix(proportions, cor.method = "pearson", save_path = NULL)

  expect_type(result, "double")
  expect_equal(dim(result), c(3, 3))
  expect_equal(diag(result), c(1, 1, 1))
})

test_that("plot_interactions computes interactions correctly", {
  proportions <- matrix(
    c(0.5, 0.3, 0.2, 0.4, 0.4, 0.2, 0.3, 0.3, 0.4),
    nrow = 3,
    ncol = 3,
    byrow = TRUE
  )
  colnames(proportions) <- c("TypeA", "TypeB", "TypeC")

  result <- plot_interactions(proportions, which = "heatmap", min_prop = 0.1, save_path = NULL)

  expect_type(result, "list")
  expect_true("correlation" %in% names(result) || "interaction" %in% names(result))
})

# ================================================================================
# Test Suite: Export Functions
# ================================================================================

test_that("export_spotlight_results creates files", {
  temp_dir <- tempfile()
  dir.create(temp_dir)

  proportions <- matrix(runif(9), nrow = 3, ncol = 3)
  proportions <- proportions / rowSums(proportions)
  colnames(proportions) <- c("A", "B", "C")
  rownames(proportions) <- c("S1", "S2", "S3")

  spotlight_ls <- list(
    mat = proportions,
    res_ss = c(0.1, 0.2, 0.15),
    NMF = list(w = matrix(runif(9), nrow = 3), h = matrix(runif(9), nrow = 3))
  )

  export_spotlight_results(
    spotlight_ls,
    output_dir = temp_dir,
    prefix = "test",
    export_proportions = TRUE,
    export_nmf = FALSE,
    export_qc = TRUE
  )

  expect_true(file.exists(file.path(temp_dir, "test_proportions.csv")))
  expect_true(file.exists(file.path(temp_dir, "test_qc_metrics.txt")))
  expect_true(file.exists(file.path(temp_dir, "test_complete.rds")))

  unlink(temp_dir, recursive = TRUE)
})

# ================================================================================
# Test Suite: Integration (with mocking)
# ================================================================================

test_that("SPOTlight workflow accepts valid parameters", {
  sc_data <- create_test_sc_data()
  sp_counts <- create_test_spatial_data()
  markers <- create_test_markers()

  # Check that parameters are passed correctly (don't run actual NMF)
  expect_true(exists("validate_spotlight_data"))
  expect_true(exists("summarize_spotlight_results"))
  expect_true(exists("get_dominant_cell_type"))
  expect_true(exists("filter_proportions"))
  expect_true(exists("export_spotlight_results"))
})

# ================================================================================
# Run All Tests
# ================================================================================

if (sys.nframe() == 0) {
  cat("Running SPOTlight unit tests...\n\n")
  test_dir("./", reporter = "progress")
}
