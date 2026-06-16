# Unit Tests for decoupleR Pathway/TF Activity Inference Skill
# =============================================================
#
# Comprehensive test suite for decoupleR wrapper functions
# Run with: Rscript tests/test_decoupler.R

library(testthat)
library(decoupleR)
library(Seurat)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# =============================================================================
# Test Core Analysis Functions
# =============================================================================

test_that("check_decoupler_dependencies works", {
  result <- check_decoupler_dependencies()
  expect_type(result, "list")
  expect_true("decoupler_installed" %in% names(result))
})

test_that("validate_decoupler_input validates correctly", {
  # Create test data
  n_samples <- 50
  n_genes <- 200

  mat <- matrix(rnorm(n_genes * n_samples), nrow = n_genes, ncol = n_samples)
  rownames(mat) <- paste0("GENE_", 1:n_genes)
  colnames(mat) <- paste0("Sample_", 1:n_samples)

  net <- data.frame(
    source = rep("PATHWAY_1", 20),
    target = sample(rownames(mat), 20),
    weight = rnorm(20),
    stringsAsFactors = FALSE
  )

  # Valid input
  result <- validate_decoupler_input(mat, net)
  expect_true(result$valid)
  expect_equal(result$stats$n_genes, n_genes)
  expect_equal(result$stats$n_samples, n_samples)
  expect_equal(result$stats$n_sources, 1)

  # Invalid matrix - no rownames
  bad_mat <- mat
  rownames(bad_mat) <- NULL
  result <- validate_decoupler_input(bad_mat, net)
  expect_false(result$valid)
  expect_true(any(grepl("rownames", result$errors)))

  # Invalid network - missing columns
  bad_net <- data.frame(a = 1:10, b = 1:10)
  result <- validate_decoupler_input(mat, bad_net)
  expect_false(result$valid)
  expect_true(any(grepl("missing required columns", result$errors)))

  # No overlap
  no_overlap_net <- data.frame(
    source = "PATHWAY_1",
    target = "NONEXISTENT_GENE",
    stringsAsFactors = FALSE
  )
  result <- validate_decoupler_input(mat, no_overlap_net)
  expect_false(result$valid)
  expect_true(any(grepl("No common genes", result$errors)))
})

test_that("validate_decoupler_matrix works", {
  n_samples <- 30
  n_genes <- 100

  mat <- matrix(rnorm(n_genes * n_samples), nrow = n_genes, ncol = n_samples)
  rownames(mat) <- paste0("GENE_", 1:n_genes)

  result <- validate_decoupler_matrix(mat)
  expect_true(result$valid)
  expect_equal(result$n_genes, n_genes)
  expect_equal(result$n_samples, n_samples)

  # Test with NAs
  mat_na <- mat
  mat_na[1, 1] <- NA
  result_na <- validate_decoupler_matrix(mat_na)
  expect_true(result_na$valid)
  expect_true(length(result_na$warnings) > 0)
})

test_that("validate_decoupler_network works", {
  net <- data.frame(
    source = rep("A", 5),
    target = paste0("G", 1:5),
    weight = 1:5,
    stringsAsFactors = FALSE
  )

  result <- validate_decoupler_network(net)
  expect_true(result$valid)
  expect_equal(result$n_sources, 1)
  expect_equal(result$n_targets, 5)

  # Missing required columns
  bad_net <- data.frame(a = 1:5, b = 1:5)
  result <- validate_decoupler_network(bad_net)
  expect_false(result$valid)
})

test_that("get_progeny_network works", {
  skip_if_not_installed("decoupleR")

  net <- get_progeny_network(organism = "human", top = 100)

  expect_s3_class(net, "data.frame")
  expect_true(all(c("source", "target", "weight") %in% colnames(net)))
  expect_gt(length(unique(net$source)), 0)
  expect_gt(nrow(net), 0)
})

test_that("get_dorothea_network works", {
  skip_if_not_installed("decoupleR")

  net <- get_dorothea_network(organism = "human", levels = c("A", "B"))

  expect_s3_class(net, "data.frame")
  expect_true(all(c("source", "target", "mor") %in% colnames(net)))
  expect_gt(length(unique(net$source)), 0)
})

test_that("get_collectri_network works", {
  skip_if_not_installed("decoupleR")

  net <- get_collectri_network(organism = "human")

  expect_s3_class(net, "data.frame")
  expect_true(all(c("source", "target") %in% colnames(net)))
  expect_gt(length(unique(net$source)), 0)
})

test_that("run_ulm_analysis works with mock data", {
  skip_if_not_installed("decoupleR")

  # Create test data
  n_samples <- 20
  n_genes <- 100

  mat <- matrix(rnorm(n_genes * n_samples), nrow = n_genes, ncol = n_samples)
  rownames(mat) <- paste0("GENE_", 1:n_genes)
  colnames(mat) <- paste0("Sample_", 1:n_samples)

  net <- data.frame(
    source = rep(c("PATHWAY_A", "PATHWAY_B"), each = 10),
    target = sample(rownames(mat), 20),
    weight = rnorm(20),
    stringsAsFactors = FALSE
  )

  result <- run_ulm_analysis(mat, net, minsize = 3)

  expect_s3_class(result, "data.frame")
  expect_true(all(c("source", "condition", "score", "statistic") %in% colnames(result)))
  expect_gt(nrow(result), 0)
  expect_equal(unique(result$statistic), "ulm")
})

test_that("run_mlm_analysis works with mock data", {
  skip_if_not_installed("decoupleR")

  n_samples <- 20
  n_genes <- 100

  mat <- matrix(rnorm(n_genes * n_samples), nrow = n_genes, ncol = n_samples)
  rownames(mat) <- paste0("GENE_", 1:n_genes)
  colnames(mat) <- paste0("Sample_", 1:n_samples)

  net <- data.frame(
    source = rep(c("PATHWAY_A", "PATHWAY_B"), each = 10),
    target = sample(rownames(mat), 20),
    weight = rnorm(20),
    stringsAsFactors = FALSE
  )

  result <- run_mlm_analysis(mat, net, minsize = 3)

  expect_s3_class(result, "data.frame")
  expect_true(all(c("source", "condition", "score", "statistic") %in% colnames(result)))
  expect_equal(unique(result$statistic), "mlm")
})

test_that("run_wsum_analysis works with mock data", {
  skip_if_not_installed("decoupleR")

  n_samples <- 20
  n_genes <- 100

  mat <- matrix(rnorm(n_genes * n_samples), nrow = n_genes, ncol = n_samples)
  rownames(mat) <- paste0("GENE_", 1:n_genes)
  colnames(mat) <- paste0("Sample_", 1:n_samples)

  net <- data.frame(
    source = rep(c("PATHWAY_A", "PATHWAY_B"), each = 10),
    target = sample(rownames(mat), 20),
    weight = rnorm(20),
    stringsAsFactors = FALSE
  )

  result <- run_wsum_analysis(mat, net, minsize = 3)

  expect_s3_class(result, "data.frame")
  expect_equal(unique(result$statistic), "wsum")
})

test_that("run_decoupler_multi works", {
  skip_if_not_installed("decoupleR")

  n_samples <- 20
  n_genes <- 100

  mat <- matrix(rnorm(n_genes * n_samples), nrow = n_genes, ncol = n_samples)
  rownames(mat) <- paste0("GENE_", 1:n_genes)
  colnames(mat) <- paste0("Sample_", 1:n_samples)

  net <- data.frame(
    source = rep(c("PATHWAY_A", "PATHWAY_B"), each = 10),
    target = sample(rownames(mat), 20),
    weight = rnorm(20),
    stringsAsFactors = FALSE
  )

  result <- run_decoupler_multi(mat, net, methods = c("ulm", "wsum"), minsize = 3)

  expect_s3_class(result, "data.frame")
  expect_equal(length(unique(result$statistic)), 2)
  expect_true(all(c("ulm", "wsum") %in% unique(result$statistic)))
})

test_that("run_decoupler_seurat works", {
  skip_if_not_installed("decoupleR")

  data("pbmc_small", package = "Seurat")
  seurat_obj <- pbmc_small

  net <- data.frame(
    source = rep("PATHWAY_1", 20),
    target = sample(rownames(seurat_obj), 20),
    weight = rnorm(20),
    stringsAsFactors = FALSE
  )

  result <- run_decoupler_seurat(seurat_obj, net, method = "ulm", minsize = 3)

  expect_s3_class(result, "data.frame")
  expect_gt(nrow(result), 0)
})

test_that("add_decoupler_to_seurat works", {
  skip_if_not_installed("decoupleR")

  data("pbmc_small", package = "Seurat")
  seurat_obj <- pbmc_small

  # Create mock results
  acts <- data.frame(
    source = rep("PATHWAY_1", ncol(seurat_obj)),
    condition = colnames(seurat_obj),
    score = rnorm(ncol(seurat_obj)),
    statistic = "ulm",
    stringsAsFactors = FALSE
  )

  # Test adding as metadata
  seurat_new <- add_decoupler_to_seurat(seurat_obj, acts, as_assay = FALSE)
  expect_true("decoupleR_PATHWAY_1" %in% colnames(seurat_new@meta.data))

  # Test adding as assay
  seurat_new2 <- add_decoupler_to_seurat(seurat_obj, acts, as_assay = TRUE)
  expect_true("decoupleR" %in% names(seurat_new2@assays))
})

test_that("create_consensus_score works", {
  skip_if_not_installed("decoupleR")

  # Create mock multi-method results
  acts <- data.frame(
    source = rep(c("A", "B"), each = 6),
    condition = rep(rep(paste0("S", 1:3), 2), 2),
    score = c(rnorm(3, 1), rnorm(3, 2), rnorm(3, 1.1), rnorm(3, 2.1)),
    statistic = rep(c("ulm", "wsum"), each = 6),
    stringsAsFactors = FALSE
  )

  consensus <- create_consensus_score(acts)

  expect_s3_class(consensus, "data.frame")
  expect_true("consensus" %in% consensus$statistic)
})

test_that("summarize_decoupler_results works", {
  acts <- data.frame(
    source = rep(c("A", "B"), each = 10),
    condition = rep(paste0("S", 1:10), 2),
    score = rnorm(20),
    statistic = "ulm",
    stringsAsFactors = FALSE
  )

  summary <- summarize_decoupler_results(acts)

  expect_type(summary, "list")
  expect_equal(summary$n_sources, 2)
  expect_equal(summary$n_conditions, 10)
  expect_equal(summary$n_scores, 20)
  expect_equal(summary$methods, "ulm")
  expect_true(!is.null(summary$score_mean))
})

# =============================================================================
# Test Utility Functions
# =============================================================================

test_that("create_decoupler_test_data works", {
  test_data <- create_decoupler_test_data(
    n_samples = 50,
    n_genes = 200,
    n_sources = 5,
    seed = 42
  )

  expect_type(test_data, "list")
  expect_true("mat" %in% names(test_data))
  expect_true("net" %in% names(test_data))
  expect_equal(ncol(test_data$mat), 50)
  expect_equal(nrow(test_data$mat), 200)
  expect_equal(length(unique(test_data$net$source)), 5)
})

test_that("recommend_decoupler_params works", {
  test_data <- create_decoupler_test_data(n_samples = 100, n_genes = 500)

  params <- recommend_decoupler_params(
    mat = test_data$mat,
    net = test_data$net
  )

  expect_type(params, "list")
  expect_true("methods" %in% names(params))
  expect_true("consensus" %in% names(params))
  expect_true("minsize" %in% names(params))
})

test_that("check_gene_overlap works", {
  test_data <- create_decoupler_test_data()

  overlap <- check_gene_overlap(test_data$mat, test_data$net)

  expect_type(overlap, "list")
  expect_true("n_overlap" %in% names(overlap))
  expect_true("overlap_fraction" %in% names(overlap))
  expect_gt(overlap$n_overlap, 0)
})

test_that("show_network_summary works", {
  test_data <- create_decoupler_test_data()

  summary <- show_network_summary(test_data$net)

  expect_type(summary, "list")
  expect_true("n_sources" %in% names(summary))
  expect_true("n_targets" %in% names(summary))
  expect_true("n_interactions" %in% names(summary))
})

test_that("filter_network_by_size works", {
  net <- data.frame(
    source = rep(c("A", "B", "C"), times = c(3, 10, 20)),
    target = paste0("G", 1:33),
    stringsAsFactors = FALSE
  )

  # Filter with minsize 5
  filtered <- filter_network_by_size(net, minsize = 5)
  expect_equal(length(unique(filtered$source)), 2)  # B and C only

  # Filter with minsize 15
  filtered2 <- filter_network_by_size(net, minsize = 15)
  expect_equal(length(unique(filtered2$source)), 1)  # C only
})

test_that("get_top_activities works", {
  acts <- data.frame(
    source = rep(c("A", "B", "C"), each = 5),
    condition = rep(paste0("S", 1:5), 3),
    score = c(rnorm(5, 5), rnorm(5, 0), rnorm(5, -5)),
    stringsAsFactors = FALSE
  )

  top <- get_top_activities(acts, n_top = 2)

  expect_s3_class(top, "data.frame")
  expect_lte(nrow(top), 10)  # 2 sources * up to 5 conditions
})

test_that("get_differential_activities works", {
  acts <- data.frame(
    source = rep(c("A", "B"), each = 4),
    condition = rep(c("Ctrl", "Ctrl", "Treat", "Treat"), 2),
    score = c(1, 1.1, 3, 3.2, 2, 2.1, 2.5, 2.4),
    stringsAsFactors = FALSE
  )

  diff <- get_differential_activities(acts, "Ctrl", "Treat")

  expect_s3_class(diff, "data.frame")
  expect_true("diff" %in% colnames(diff))
  expect_equal(nrow(diff), 2)
})

# =============================================================================
# Test Visualization Functions
# =============================================================================

test_that("plot_activity_heatmap returns plot object", {
  skip_if_not_installed("ggplot2")

  acts <- data.frame(
    source = rep(c("A", "B", "C"), each = 5),
    condition = rep(paste0("S", 1:5), 3),
    score = rnorm(15),
    statistic = "ulm",
    stringsAsFactors = FALSE
  )

  result <- plot_activity_heatmap(acts, n_top = 3)

  expect_true(inherits(result, "gg") || inherits(result, "Heatmap"))
})

test_that("plot_activity_scatter works", {
  skip_if_not_installed("ggplot2")

  acts <- data.frame(
    source = rep(c("A", "B", "C"), each = 4),
    condition = rep(rep(c("X", "Y"), each = 2), 3),
    score = c(1, 1.1, 2, 2.1, 3, 3.1, 4, 4.1, 5, 5.1, 6, 6.1),
    statistic = "ulm",
    stringsAsFactors = FALSE
  )

  p <- plot_activity_scatter(acts, "X", "Y")

  expect_s3_class(p, "gg")
})

test_that("plot_top_activities works", {
  skip_if_not_installed("ggplot2")

  acts <- data.frame(
    source = rep(c("A", "B", "C"), each = 3),
    condition = rep("S1", 9),
    score = c(5, 4, 3, 2, 1, 0.5, -1, -2, -3),
    statistic = "ulm",
    stringsAsFactors = FALSE
  )

  p <- plot_top_activities(acts, condition = "S1", n_top = 5)

  expect_s3_class(p, "gg")
})

test_that("plot_activity_volcano works", {
  skip_if_not_installed("ggplot2")

  diff_results <- data.frame(
    source = c("A", "B", "C"),
    diff = c(1.5, -0.5, 2.0),
    mean_score = c(1, 0.5, 1.5),
    stringsAsFactors = FALSE
  )

  p <- plot_activity_volcano(diff_results, fc_threshold = 0.3)

  expect_s3_class(p, "gg")
})

test_that("plot_consensus_scores works", {
  skip_if_not_installed("ggplot2")

  acts <- data.frame(
    source = rep(c("A", "B", "C"), each = 6),
    condition = rep(rep(paste0("S", 1:3), 2), 3),
    score = rnorm(18),
    statistic = rep(c("ulm", "wsum"), each = 9),
    stringsAsFactors = FALSE
  )

  p <- plot_consensus_scores(acts, top_n = 3)

  expect_s3_class(p, "gg")
})

# =============================================================================
# Integration Tests
# =============================================================================

test_that("complete pathway analysis workflow runs without errors", {
  skip_if_not_installed("decoupleR")

  # Create test data
  test_data <- create_decoupler_test_data(
    n_samples = 30,
    n_genes = 150,
    n_sources = 3,
    seed = 42
  )

  # Validate
  validation <- validate_decoupler_input(test_data$mat, test_data$net)
  expect_true(validation$valid)

  # Check overlap
  overlap <- check_gene_overlap(test_data$mat, test_data$net)
  expect_gt(overlap$n_overlap, 0)

  # Run analysis
  acts <- run_ulm_analysis(test_data$mat, test_data$net, minsize = 3)
  expect_gt(nrow(acts), 0)

  # Summarize
  summary <- summarize_decoupler_results(acts)
  expect_equal(summary$n_sources, 3)

  # Get top activities
  top <- get_top_activities(acts, n_top = 2)
  expect_gt(nrow(top), 0)

  # Create consensus from multi-method
  acts_multi <- run_decoupler_multi(
    test_data$mat,
    test_data$net,
    methods = c("ulm", "wsum"),
    minsize = 3
  )

  consensus <- create_consensus_score(acts_multi)
  expect_gt(nrow(consensus), 0)
})

test_that("Seurat integration workflow works", {
  skip_if_not_installed("decoupleR")

  data("pbmc_small", package = "Seurat")
  seurat_obj <- pbmc_small

  # Create network with genes from the object
  net <- data.frame(
    source = rep("TEST_PATHWAY", 20),
    target = sample(rownames(seurat_obj), 20),
    weight = rnorm(20),
    stringsAsFactors = FALSE
  )

  # Run with Seurat
  acts <- run_decoupler_seurat(seurat_obj, net, method = "ulm", minsize = 3)
  expect_gt(nrow(acts), 0)

  # Add to Seurat
  seurat_new <- add_decoupler_to_seurat(seurat_obj, acts, as_assay = FALSE)
  expect_true("decoupleR_TEST_PATHWAY" %in% colnames(seurat_new@meta.data))
})

# =============================================================================
# Edge Cases
# =============================================================================

test_that("handles empty results gracefully", {
  # Create network that will be filtered out
  mat <- matrix(rnorm(100), nrow = 10)
  rownames(mat) <- paste0("GENE_", 1:10)

  net <- data.frame(
    source = "PATHWAY_1",
    target = "NONEXISTENT",
    stringsAsFactors = FALSE
  )

  validation <- validate_decoupler_input(mat, net)
  expect_false(validation$valid)
})

test_that("handles single source correctly", {
  skip_if_not_installed("decoupleR")

  mat <- matrix(rnorm(100), nrow = 10, ncol = 10)
  rownames(mat) <- paste0("GENE_", 1:10)
  colnames(mat) <- paste0("SAMPLE_", 1:10)

  net <- data.frame(
    source = "PATHWAY_1",
    target = rownames(mat)[1:5],
    weight = 1,
    stringsAsFactors = FALSE
  )

  acts <- run_ulm_analysis(mat, net, minsize = 3)
  expect_equal(length(unique(acts$source)), 1)
})

# Run tests
if (interactive()) {
  cat("\nRun tests with: test_file('tests/test_decoupler.R')\n")
} else {
  cat("\nRunning tests...\n")
  test_results <- test_file("test_decoupler.R", reporter = "summary")
  cat("\nTest summary:", sum(test_results$passed), "passed,",
      sum(test_results$failed), "failed\n")
}
