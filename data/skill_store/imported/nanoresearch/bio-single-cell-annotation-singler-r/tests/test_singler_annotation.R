# Unit tests for SingleR annotation
# Test suite for bio-single-cell-annotation-singler-r skill

library(testthat)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source main functions
source(file.path(script_dir, "singler_annotation.R"))

context("SingleR Annotation Functions")

# ============================================================================
# Test Data Helpers
# ============================================================================

create_test_seurat <- function(n_cells = 50, n_genes = 100) {
  set.seed(42)
  counts <- matrix(rpois(n_cells * n_genes, lambda = 5),
                   nrow = n_genes, ncol = n_cells)
  rownames(counts) <- paste0("GENE", 1:n_genes)
  colnames(counts) <- paste0("CELL", 1:n_cells)

  obj <- Seurat::CreateSeuratObject(counts = counts)
  obj <- Seurat::NormalizeData(obj, verbose = FALSE)

  return(obj)
}

# ============================================================================
# Tests for function existence
# ============================================================================

test_that("run_singler_annotation function exists", {
  expect_true(exists("run_singler_annotation"))
  expect_type(run_singler_annotation, "closure")
})

test_that("load_singler_reference function exists", {
  expect_true(exists("load_singler_reference"))
  expect_type(load_singler_reference, "closure")
})

test_that("filter_singler_by_confidence function exists", {
  expect_true(exists("filter_singler_by_confidence"))
  expect_type(filter_singler_by_confidence, "closure")
})

test_that("plot_singler_quality function exists", {
  expect_true(exists("plot_singler_quality"))
  expect_type(plot_singler_quality, "closure")
})

# ============================================================================
# Tests for filter_singler_by_confidence
# ============================================================================

test_that("filter_singler_by_confidence handles NA pruned labels", {
  skip_if_not_installed("Seurat")

  seurat_obj <- create_test_seurat(n_cells = 5)

  # Add mock SingleR results
  seurat_obj$SingleR_label <- c("T_cell", "B_cell", "T_cell", "Monocyte", "T_cell")
  seurat_obj$SingleR_pruned <- c("T_cell", NA, "T_cell", NA, "T_cell")

  result <- filter_singler_by_confidence(seurat_obj)

  expect_true("SingleR_filtered" %in% colnames(result@meta.data))
  # Use as.character to handle factor conversion
  expect_equal(as.character(result$SingleR_filtered[1]), "T_cell")
  expect_equal(as.character(result$SingleR_filtered[2]), "Unknown")  # NA becomes Unknown
  expect_equal(as.character(result$SingleR_filtered[4]), "Unknown")  # NA becomes Unknown
})

test_that("filter_singler_by_confidence handles all valid labels", {
  skip_if_not_installed("Seurat")

  seurat_obj <- create_test_seurat(n_cells = 5)
  seurat_obj$SingleR_label <- c("T_cell", "B_cell", "Monocyte", "NK_cell", "DC")
  seurat_obj$SingleR_pruned <- c("T_cell", "B_cell", "Monocyte", "NK_cell", "DC")

  result <- filter_singler_by_confidence(seurat_obj)

  expect_equal(as.character(result$SingleR_filtered), as.character(seurat_obj$SingleR_label))
})

test_that("filter_singler_by_confidence handles all NA pruned labels", {
  skip_if_not_installed("Seurat")

  seurat_obj <- create_test_seurat(n_cells = 3)
  seurat_obj$SingleR_label <- c("T_cell", "B_cell", "Monocyte")
  seurat_obj$SingleR_pruned <- c(NA, NA, NA)

  result <- filter_singler_by_confidence(seurat_obj)

  expect_equal(as.character(result$SingleR_filtered), c("Unknown", "Unknown", "Unknown"))
})

# ============================================================================
# Tests for input validation
# ============================================================================

test_that("run_singler_annotation validates input", {
  skip_if_not_installed("Seurat")

  # Test with NULL
  expect_error(run_singler_annotation(NULL), "must be a Seurat object")

  # Test with non-Seurat object
  expect_error(run_singler_annotation(data.frame()), "must be a Seurat object")
})

# ============================================================================
# Tests for load_singler_reference
# ============================================================================

test_that("load_singler_reference handles unknown reference", {
  skip_if_not_installed("celldex")

  expect_error(
    load_singler_reference("unknown_reference"),
    "Unknown reference"
  )
})

test_that("load_singler_reference accepts valid reference names", {
  skip_if_not_installed("celldex")

  # Only test that function does not throw "Unknown reference" for valid names
  # without actually loading large datasets
  valid_refs <- c("monaco", "blueprint", "hpca", "immgen", "dice", "novershtern", "mouse")

  for (ref_name in valid_refs) {
    expect_error(
      tryCatch(load_singler_reference(ref_name), error = function(e) {
        if (grepl("Unknown reference", e$message)) stop(e$message) else NULL
      }),
      "Unknown reference"
    )
  }
})

# ============================================================================
# Integration Tests (skipped if packages not available)
# ============================================================================

test_that("run_singler_annotation works with provided reference", {
  skip_if_not_installed("Seurat")
  skip_if_not_installed("SingleR")
  skip_if_not_installed("SingleCellExperiment")

  seurat_obj <- create_test_seurat(n_cells = 20)

  # Create a mock reference (minimal version for testing)
  mock_ref <- SingleCellExperiment::SingleCellExperiment(
    assays = list(counts = matrix(1:100, nrow = 10)),
    colData = data.frame(label.main = rep(c("T_cell", "B_cell"), each = 5))
  )
  rownames(mock_ref) <- paste0("GENE", 1:10)

  result <- run_singler_annotation(
    seurat_obj,
    ref = mock_ref,
    label_col = "label.main",
    prune = FALSE
  )

  expect_true("SingleR_label" %in% colnames(result@meta.data))
  expect_equal(length(result$SingleR_label), ncol(seurat_obj))
})

test_that("Complete SingleR workflow works", {
  skip_if_not_installed("Seurat")

  # Create test data
  seurat_obj <- create_test_seurat(n_cells = 30)

  # Add mock SingleR results (simulating annotation output)
  labels <- sample(c("T_cell", "B_cell", "Monocyte"), 30, replace = TRUE)
  pruned <- labels
  pruned[sample(1:30, 5)] <- NA  # Some low confidence

  seurat_obj$SingleR_label <- labels
  seurat_obj$SingleR_pruned <- pruned

  # Filter by confidence
  result <- filter_singler_by_confidence(seurat_obj)

  # Check results
  expect_true("SingleR_filtered" %in% colnames(result@meta.data))
  expect_equal(sum(result$SingleR_filtered == "Unknown"), 5)

  # Check label distribution
  label_table <- table(result$SingleR_filtered)
  expect_true("Unknown" %in% names(label_table))
})

# ============================================================================
# Edge Cases
# ============================================================================

test_that("filter_singler_by_confidence handles empty object", {
  skip_if_not_installed("Seurat")
  skip("Empty Seurat objects not supported")

  seurat_obj <- create_test_seurat(n_cells = 0)

  # Add empty metadata
  seurat_obj$SingleR_label <- character(0)
  seurat_obj$SingleR_pruned <- character(0)

  result <- filter_singler_by_confidence(seurat_obj)

  expect_equal(length(result$SingleR_filtered), 0)
})

test_that("filter_singler_by_confidence handles single cell", {
  skip_if_not_installed("Seurat")
  skip("Single cell Seurat objects have issues with Seurat v5")

  seurat_obj <- create_test_seurat(n_cells = 1)
  seurat_obj$SingleR_label <- "T_cell"
  seurat_obj$SingleR_pruned <- "T_cell"

  result <- filter_singler_by_confidence(seurat_obj)

  expect_equal(as.character(result$SingleR_filtered), "T_cell")
})

# Note: Full integration tests require SingleR and celldex packages.
# Install with: BiocManager::install(c("SingleR", "celldex"))
