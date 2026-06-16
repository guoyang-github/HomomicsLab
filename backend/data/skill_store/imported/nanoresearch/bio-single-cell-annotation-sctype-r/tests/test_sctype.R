# ScType Annotation Tests
# Test suite for bio-single-cell-annotation-sctype-r skill

library(testthat)
library(Seurat)
library(HGNChelper)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source main functions
source(file.path(script_dir, "sctype_annotation.R"))
source(file.path(script_dir, "gene_sets_prepare.R"))
source(file.path(script_dir, "sctype_score.R"))

context("ScType Annotation")

# Create minimal test data
create_test_seurat <- function(n_cells = 100, n_genes = 200) {
  set.seed(42)
  counts <- matrix(rpois(n_cells * n_genes, lambda = 5),
                   nrow = n_genes, ncol = n_cells)
  rownames(counts) <- paste0("GENE", 1:n_genes)
  colnames(counts) <- paste0("CELL", 1:n_cells)

  # Add some marker genes
  marker_genes <- c("CD3D", "CD3E", "CD4", "CD8A", "CD8B",
                    "CD79A", "CD79B", "MS4A1",
                    "LYZ", "CD14", "FCGR3A",
                    "PPBP", "PF4")
  rownames(counts)[1:length(marker_genes)] <- marker_genes

  # Create expression patterns for different clusters
  clusters <- sample(1:4, n_cells, replace = TRUE)

  # Cluster 1: T cells
  counts[c("CD3D", "CD3E", "CD4"), clusters == 1] <-
    counts[c("CD3D", "CD3E", "CD4"), clusters == 1] + 20

  # Cluster 2: B cells
  counts[c("CD79A", "CD79B", "MS4A1"), clusters == 2] <-
    counts[c("CD79A", "CD79B", "MS4A1"), clusters == 2] + 20

  # Cluster 3: Monocytes
  counts[c("LYZ", "CD14", "FCGR3A"), clusters == 3] <-
    counts[c("LYZ", "CD14", "FCGR3A"), clusters == 3] + 20

  # Cluster 4: Platelets
  counts[c("PPBP", "PF4"), clusters == 4] <-
    counts[c("PPBP", "PF4"), clusters == 4] + 20

  obj <- CreateSeuratObject(counts = counts)
  obj@meta.data$seurat_clusters <- factor(clusters)

  # Normalize
  obj <- NormalizeData(obj)

  return(obj)
}

test_that("create_marker_list works correctly", {
  pos_markers <- list(
    "T_cell" = c("CD3D", "CD3E"),
    "B_cell" = c("CD79A", "MS4A1")
  )
  neg_markers <- list(
    "T_cell" = c("CD79A"),
    "B_cell" = c("CD3D")
  )

  marker_list <- create_marker_list(pos_markers, neg_markers)

  expect_type(marker_list, "list")
  expect_named(marker_list, c("gs_positive", "gs_negative"))
  expect_equal(marker_list$gs_positive, pos_markers)
  expect_equal(marker_list$gs_negative, neg_markers)
})

test_that("create_marker_list handles missing negative markers", {
  pos_markers <- list(
    "T_cell" = c("CD3D", "CD3E"),
    "B_cell" = c("CD79A", "MS4A1")
  )

  marker_list <- create_marker_list(pos_markers)

  expect_type(marker_list, "list")
  expect_equal(length(marker_list$gs_negative), 2)
  expect_equal(marker_list$gs_negative[["T_cell"]], character(0))
})

test_that("sctype_score calculates scores correctly", {
  # Create simple test matrix
  expr <- matrix(c(10, 5, 0, 8, 2, 0), nrow = 3, ncol = 2)
  rownames(expr) <- c("CD3D", "CD3E", "CD79A")
  colnames(expr) <- c("CELL1", "CELL2")

  gs <- list("T_cell" = c("CD3D", "CD3E"))
  gs2 <- list("T_cell" = c("CD79A"))

  scores <- sctype_score(expr, scaled = FALSE, gs = gs, gs2 = gs2)

  expect_type(scores, "double")
  # Handle both matrix (multi-type) and named vector (single-type) cases
  if (is.matrix(scores)) {
    expect_equal(nrow(scores), 1)
    expect_equal(ncol(scores), 2)
    expect_gt(scores["T_cell", "CELL1"], scores["T_cell", "CELL2"])
  } else {
    # Single row result is returned as named vector
    expect_equal(length(scores), 2)
    expect_gt(scores["CELL1"], scores["CELL2"])
  }
})

test_that("sctype_score handles gs2 = NULL", {
  expr <- matrix(c(10, 5, 8, 2), nrow = 2, ncol = 2)
  rownames(expr) <- c("CD3D", "CD3E")
  colnames(expr) <- c("CELL1", "CELL2")

  gs <- list("T_cell" = c("CD3D", "CD3E"))

  # Should not error when gs2 is NULL
  scores <- sctype_score(expr, scaled = FALSE, gs = gs, gs2 = NULL)

  expect_type(scores, "double")
  if (is.matrix(scores)) {
    expect_equal(nrow(scores), 1)
    expect_equal(ncol(scores), 2)
  } else {
    expect_equal(length(scores), 2)
  }
})

test_that("sctype_score handles zero-sd genes gracefully", {
  # Gene2 has zero standard deviation (constant across cells)
  expr <- matrix(c(10, 5, 8, 5), nrow = 2, ncol = 2)
  rownames(expr) <- c("CD3D", "CONSTANT")
  colnames(expr) <- c("CELL1", "CELL2")

  gs <- list("T_cell" = c("CD3D", "CONSTANT"))

  # Should not produce NaN/Inf scores
  scores <- sctype_score(expr, scaled = FALSE, gs = gs, gs2 = NULL)

  expect_type(scores, "double")
  expect_true(all(is.finite(scores)))
})

test_that("sctype_score handles single-marker sensitivity (scales fallback)", {
  # Only one marker gene in the set — all markers have same frequency
  expr <- matrix(c(10, 8, 5, 3), nrow = 1, ncol = 4)
  rownames(expr) <- c("CD3D")
  colnames(expr) <- c("C1", "C2", "C3", "C4")

  gs <- list("T_cell" = c("CD3D"))

  scores <- sctype_score(expr, scaled = FALSE, gs = gs, gs2 = NULL)

  expect_type(scores, "double")
  expect_true(all(is.finite(scores)))
})

test_that("run_sctype_annotation validates inputs", {
  # Test non-Seurat input
  expect_error(
    run_sctype_annotation(matrix(1:10, nrow = 2)),
    "Input must be a Seurat object"
  )
})

test_that("run_sctype_annotation rejects invalid db_source", {
  seurat_obj <- create_test_seurat()

  expect_error(
    run_sctype_annotation(
      seurat_obj,
      tissue = "Immune system",
      db_source = "invalid"
    ),
    "db_source must be 'full' or 'short'"
  )
})

test_that("run_sctype_annotation works with custom markers", {
  seurat_obj <- create_test_seurat()

  custom_markers <- create_marker_list(
    positive_markers = list(
      "T_cell" = c("CD3D", "CD3E"),
      "B_cell" = c("CD79A", "MS4A1"),
      "Monocyte" = c("LYZ", "CD14"),
      "Platelet" = c("PPBP", "PF4")
    )
  )

  result <- run_sctype_annotation(
    seurat_obj,
    marker_list = custom_markers,
    slot = "counts",
    score_threshold = 0
  )

  expect_s4_class(result, "Seurat")
  expect_true("sctype_cell_type" %in% colnames(result@meta.data))
  expect_gt(length(unique(result$sctype_cell_type)), 1)
})

test_that("run_sctype_annotation respects output column name", {
  seurat_obj <- create_test_seurat()

  custom_markers <- create_marker_list(
    positive_markers = list(
      "T_cell" = c("CD3D", "CD3E"),
      "B_cell" = c("CD79A", "MS4A1")
    )
  )

  result <- run_sctype_annotation(
    seurat_obj,
    marker_list = custom_markers,
    slot = "counts",
    output_col = "my_annotation",
    score_threshold = 0
  )

  expect_true("my_annotation" %in% colnames(result@meta.data))
})

test_that("run_sctype_annotation returns scores when requested", {
  seurat_obj <- create_test_seurat()

  custom_markers <- create_marker_list(
    positive_markers = list(
      "T_cell" = c("CD3D", "CD3E"),
      "B_cell" = c("CD79A", "MS4A1")
    )
  )

  result <- run_sctype_annotation(
    seurat_obj,
    marker_list = custom_markers,
    slot = "counts",
    return_scores = TRUE,
    score_threshold = 0
  )

  expect_true("sctype_cell_type_scores" %in% names(result@misc))
  expect_true("sctype_cell_type_cluster_scores" %in% names(result@misc))
})

test_that("gene_sets_prepare reads database correctly", {
  db_file <- file.path(getwd(), "..", "assets", "markers", "ScTypeDB_short.xlsx")
  if (!file.exists(db_file)) {
    db_file <- file.path(getwd(), "assets", "markers", "ScTypeDB_short.xlsx")
  }

  skip_if_not(file.exists(db_file), "Database file not found")

  gs_list <- gene_sets_prepare(db_file, "Immune system")

  expect_type(gs_list, "list")
  expect_named(gs_list, c("gs_positive", "gs_negative"))
  expect_gt(length(gs_list$gs_positive), 0)
})

test_that("run_sctype_annotation works with built-in database", {
  db_file <- file.path(getwd(), "..", "assets", "markers", "ScTypeDB_short.xlsx")
  if (!file.exists(db_file)) {
    db_file <- file.path(getwd(), "assets", "markers", "ScTypeDB_short.xlsx")
  }

  skip_if_not(file.exists(db_file), "Database file not found")

  seurat_obj <- create_test_seurat()

  # Use short database for faster testing
  result <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    db_source = "short",
    slot = "counts"
  )

  expect_s4_class(result, "Seurat")
  expect_true("sctype_cell_type" %in% colnames(result@meta.data))
})

# Note: Tests should be run using test_file() or test_dir() from testthat package
# Example: testthat::test_file("tests/test_sctype.R")
