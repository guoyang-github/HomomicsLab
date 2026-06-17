# Unit Tests for PROGENy Analysis
# ================================
#
# Tests for core_analysis.R, visualization.R, and utils.R modules.

library(testthat)

# Source the functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/utils.R")
source("../scripts/r/visualization.R")

# Check if progeny is available
progeny_available <- requireNamespace("progeny", quietly = TRUE)
seurat_available <- requireNamespace("Seurat", quietly = TRUE)

test_that("check_progeny_input validates inputs correctly", {
  skip_if(!seurat_available, "Seurat not installed")

  # Test with NULL
  expect_error(check_progeny_input(NULL))

  # Create minimal test data
  test_data <- matrix(rnorm(100), nrow=10)
  rownames(test_data) <- paste0("gene_", 1:10)
  colnames(test_data) <- paste0("cell_", 1:10)

  expect_true(check_progeny_input(test_data))
})

test_that("validate_gene_overlap works correctly", {
  skip_if(!progeny_available, "PROGENy not installed")

  # Test genes
  test_genes <- c("TP53", "EGFR", "MYC", "NONEXISTENT_GENE")

  result <- validate_gene_overlap(test_genes, organism = "Human", top = 100)

  expect_type(result, "list")
  expect_true("n_input_genes" %in% names(result))
  expect_true("n_overlap" %in% names(result))
  expect_true("overlap_fraction" %in% names(result))
  expect_equal(result$n_input_genes, 4)
})

test_that("get_pathway_summary_stats returns correct structure", {
  # Create test scores
  test_scores <- matrix(rnorm(100), ncol = 4)
  colnames(test_scores) <- c("MAPK", "PI3K", "TGFb", "TNFa")

  stats <- get_pathway_summary_stats(test_scores)

  expect_s3_class(stats, "data.frame")
  expect_equal(nrow(stats), 4)
  expect_true(all(c("mean", "sd", "min", "max") %in% colnames(stats)))
})

test_that("recommend_top_parameter returns appropriate values", {
  expect_equal(recommend_top_parameter(50), 500)
  expect_equal(recommend_top_parameter(500), 200)
  expect_equal(recommend_top_parameter(2000), 100)
})

test_that("list_progeny_pathways returns pathways", {
  skip_if(!progeny_available, "PROGENy not installed")

  pathways <- list_progeny_pathways(organism = "Human")

  expect_type(pathways, "character")
  expect_true(length(pathways) > 0)
  expect_true("MAPK" %in% pathways || "PI3K" %in% pathways)
})

test_that("get_progeny_model_info returns correct structure", {
  skip_if(!progeny_available, "PROGENy not installed")

  info <- get_progeny_model_info(organism = "Human", top = 100)

  expect_s3_class(info, "data.frame")
  expect_true("pathway" %in% colnames(info))
  expect_true("n_genes" %in% colnames(info))
  expect_true("mean_weight" %in% colnames(info))
})

test_that("compare_pathway_conditions returns correct structure", {
  # Create test data
  set.seed(42)
  scores <- matrix(rnorm(200), ncol = 4)
  colnames(scores) <- c("MAPK", "PI3K", "TGFb", "TNFa")

  metadata <- data.frame(
    condition = rep(c("A", "B"), each = 25)
  )

  result <- compare_pathway_conditions(
    scores,
    metadata,
    condition_col = "condition",
    condition1 = "A",
    condition2 = "B"
  )

  expect_s3_class(result, "data.frame")
  expect_equal(nrow(result), 4)
  expect_true("p_value" %in% colnames(result))
  expect_true("adj_p_value" %in% colnames(result))
})

test_that("export functions handle formats correctly", {
  test_scores <- matrix(rnorm(40), ncol = 4)
  colnames(test_scores) <- c("MAPK", "PI3K", "TGFb", "TNFa")
  rownames(test_scores) <- paste0("cell_", 1:10)

  # Test CSV export
  temp_file <- tempfile(fileext = ".csv")
  export_pathway_scores(test_scores, temp_file, "csv")
  expect_true(file.exists(temp_file))

  # Test RDS export
  temp_rds <- tempfile(fileext = ".rds")
  export_pathway_scores(test_scores, temp_rds, "rds")
  expect_true(file.exists(temp_rds))

  # Cleanup
  unlink(c(temp_file, temp_rds))
})

# Integration tests
test_that("Full workflow completes without errors", {
  skip_if(!progeny_available, "PROGENy not installed")
  skip_if(!seurat_available, "Seurat not installed")

  library(Seurat)

  # Create minimal Seurat object
  set.seed(42)
  counts <- matrix(rpois(1000, lambda = 5), nrow = 100)
  model_genes <- rownames(progeny::getModel("Human", top = 100))
  rownames(counts) <- sample(model_genes, 100)
  colnames(counts) <- paste0("cell_", 1:10)

  # Normalize
  seurat_obj <- CreateSeuratObject(counts = counts)
  seurat_obj <- NormalizeData(seurat_obj)

  # Run PROGENy
  result <- run_progeny(
    seurat_obj,
    organism = "Human",
    top = 100,
    scale = FALSE,
    return_assay = TRUE,
    verbose = FALSE
  )

  expect_s4_class(result, "Seurat")
  expect_true("progeny" %in% names(result@assays))
})

# =============================================================================
# Visualization Tests
# =============================================================================

test_that("plot_pathway_correlation works with matrix input", {
  skip_if_not_installed("pheatmap")

  test_scores <- matrix(rnorm(200), ncol = 4)
  colnames(test_scores) <- c("MAPK", "PI3K", "TGFb", "TNFa")

  p <- plot_pathway_correlation(test_scores, method = "pearson")
  expect_s3_class(p, "pheatmap")
})

test_that("plot_pathway_scatter works with mock data", {
  skip_if(!seurat_available, "Seurat not installed")
  skip_if_not_installed("ggplot2")

  set.seed(42)
  counts <- matrix(rpois(1000, lambda = 5), nrow = 100)
  rownames(counts) <- paste0("gene_", 1:100)
  colnames(counts) <- paste0("cell_", 1:10)

  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  seurat_obj <- Seurat::NormalizeData(seurat_obj)

  # Add mock progeny assay
  mock_scores <- matrix(rnorm(10 * 4), nrow = 4)
  rownames(mock_scores) <- c("MAPK", "PI3K", "TGFb", "TNFa")
  colnames(mock_scores) <- colnames(seurat_obj)
  seurat_obj[["progeny"]] <- Seurat::CreateAssayObject(data = mock_scores)

  p <- plot_pathway_scatter(seurat_obj, pathway_x = "MAPK", pathway_y = "PI3K")
  expect_s3_class(p, "ggplot")
})

test_that("plot_pathway_bar works", {
  skip_if_not_installed("ggplot2")

  avg_scores <- data.frame(
    group = c("A", "B"),
    MAPK = c(0.5, -0.3),
    PI3K = c(0.2, 0.4)
  )

  p <- plot_pathway_bar(avg_scores)
  expect_s3_class(p, "ggplot")
})

# Run all tests
cat("Running PROGENy tests...\n")
if (progeny_available && seurat_available) {
  cat("All packages available - running full test suite\n")
} else {
  cat("Some packages missing - running limited tests\n")
  cat("Missing:", paste(c(
    if (!progeny_available) "progeny",
    if (!seurat_available) "Seurat"
  ), collapse = ", "), "\n")
}
