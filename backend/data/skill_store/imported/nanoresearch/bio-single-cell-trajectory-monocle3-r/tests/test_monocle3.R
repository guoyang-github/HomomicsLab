#!/usr/bin/env Rscript
#' Unit Tests for Monocle3 Analysis Module
#'
#' Run with: Rscript test_monocle3.R

suppressPackageStartupMessages({
  library(monocle3)
})

# Source functions to test
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# ==============================================================================
# Test Suite
# ==============================================================================

test_results <- list(passed = 0, failed = 0, errors = list())

run_test <- function(test_name, test_expr) {
  tryCatch({
    test_expr
    cat("[PASS]", test_name, "\n")
    test_results$passed <<- test_results$passed + 1
  }, error = function(e) {
    cat("[FAIL]", test_name, "\n")
    cat("       Error:", conditionMessage(e), "\n")
    test_results$failed <<- test_results$failed + 1
    test_results$errors <<- c(test_results$errors, list(list(name = test_name, error = conditionMessage(e))))
  })
}

# ==============================================================================
# Create Test Data
# ==============================================================================

cat("Creating test data...\n")
set.seed(42)

n_cells <- 100
n_genes <- 200

expression_matrix <- matrix(rpois(n_cells * n_genes, lambda = 3),
                           nrow = n_genes, ncol = n_cells)

gene_metadata <- data.frame(
  gene_short_name = paste0("gene_", 1:n_genes),
  row.names = paste0("gene_", 1:n_genes)
)
rownames(expression_matrix) <- rownames(gene_metadata)

cell_metadata <- data.frame(
  cell_id = paste0("cell_", 1:n_cells),
  group = sample(c("A", "B"), n_cells, replace = TRUE),
  row.names = paste0("cell_", 1:n_cells)
)
colnames(expression_matrix) <- rownames(cell_metadata)

# ==============================================================================
# Test Data Creation
# ==============================================================================

cat("\n--- Testing Data Creation ---\n")

run_test("create_cds basic", {
  cds <- create_cds(expression_matrix, cell_metadata, gene_metadata)
  stopifnot(nrow(cds) == n_genes)
  stopifnot(ncol(cds) == n_cells)
})

run_test("create_cds without metadata", {
  cds <- create_cds(expression_matrix)
  stopifnot(nrow(cds) == n_genes)
  stopifnot(ncol(cds) == n_cells)
  stopifnot("gene_short_name" %in% colnames(rowData(cds)))
  stopifnot("cell_id" %in% colnames(colData(cds)))
})

# ==============================================================================
# Test Preprocessing (using official monocle3 functions)
# ==============================================================================

cat("\n--- Testing Preprocessing ---\n")

cds <- create_cds(expression_matrix, cell_metadata, gene_metadata)

run_test("preprocess_cds", {
  cds_prep <- preprocess_cds(cds, num_dim = 20)
  stopifnot(!is.null(cds_prep@reduce_dim_aux[["PCA"]]))
})

run_test("reduce_dimension", {
  cds_prep <- preprocess_cds(cds, num_dim = 20)
  cds_red <- reduce_dimension(cds_prep, reduction_method = "UMAP")
  stopifnot(!is.null(SingleCellExperiment::reducedDims(cds_red)[["UMAP"]]))
})

run_test("cluster_cells", {
  cds_prep <- preprocess_cds(cds, num_dim = 20)
  cds_red <- reduce_dimension(cds_prep)
  cds_clust <- cluster_cells(cds_red, resolution = 1e-5)
  stopifnot(!is.null(cds_clust@clusters[["UMAP"]]))
})

# ==============================================================================
# Test Trajectory Analysis
# ==============================================================================

cat("\n--- Testing Trajectory Analysis ---\n")

cds_prep <- preprocess_cds(cds, num_dim = 20)
cds_red <- reduce_dimension(cds_prep)
cds_clust <- cluster_cells(cds_red)

run_test("learn_graph", {
  cds_graph <- learn_graph(cds_clust)
  stopifnot(!is.null(principal_graph(cds_graph)[["UMAP"]]))
})

run_test("get_branch_nodes", {
  cds_graph <- learn_graph(cds_clust)
  branches <- get_branch_nodes(cds_graph)
  stopifnot(is.vector(branches) || is.integer(branches))
})

run_test("get_leaf_nodes", {
  cds_graph <- learn_graph(cds_clust)
  leaves <- get_leaf_nodes(cds_graph)
  stopifnot(is.vector(leaves) || is.integer(leaves))
})

run_test("get_root_nodes after ordering", {
  cds_graph <- learn_graph(cds_clust)
  root_cells <- colnames(cds_graph)[1:5]
  cds_ordered <- order_cells(cds_graph, root_cells = root_cells)
  roots <- get_root_nodes(cds_ordered)
  stopifnot(length(roots) > 0)
})

run_test("run_trajectory_analysis pipeline", {
  root_cells <- colnames(cds)[1:5]
  cds_full <- run_trajectory_analysis(cds, num_dim = 20, root_cells = root_cells)
  checks <- check_cds_completeness(cds_full)
  stopifnot(all(unlist(checks)))
})

# ==============================================================================
# Test Utilities
# ==============================================================================

cat("\n--- Testing Utilities ---\n")

run_test("get_clusters", {
  clusters_vec <- get_clusters(cds_clust)
  stopifnot(length(clusters_vec) == n_cells)
})

run_test("get_partitions", {
  partitions_vec <- get_partitions(cds_clust)
  stopifnot(length(partitions_vec) == n_cells)
})

run_test("annotate_clusters", {
  cl <- get_clusters(cds_clust)
  uniq_cl <- unique(cl)
  annotations <- setNames(paste0("type_", uniq_cl), as.character(uniq_cl))
  cds_annot <- annotate_clusters(cds_clust, annotations)
  stopifnot("cell_type" %in% colnames(colData(cds_annot)))
})

run_test("check_cds_completeness", {
  checks <- check_cds_completeness(cds_prep)
  stopifnot(is.list(checks))
  stopifnot(all(c("preprocessed", "reduced_dims", "clustered", "graph_learned",
                  "pseudotime_ordered") %in% names(checks)))
})

run_test("print_cds_summary runs without error", {
  print_cds_summary(cds_prep)
  stopifnot(TRUE)
})

# ==============================================================================
# Test Visualization Functions
# ==============================================================================

cat("\n--- Testing Visualization Functions ---\n")

cds_graph <- learn_graph(cds_clust)

run_test("plot_pseudotime_distribution", {
  root_cells <- colnames(cds_graph)[1:5]
  cds_ordered <- order_cells(cds_graph, root_cells = root_cells)
  p <- plot_pseudotime_distribution(cds_ordered, bins = 20)
  stopifnot(!is.null(p))
  stopifnot("ggplot" %in% class(p))
})

run_test("plot_trajectory_features", {
  plots <- plot_trajectory_features(cds_clust, features = c("group"))
  stopifnot(length(plots) == 1)
  stopifnot("ggplot" %in% class(plots[[1]]))
})

# ==============================================================================
# Test Differential Expression
# ==============================================================================

cat("\n--- Testing Differential Expression ---\n")

cds_ordered <- order_cells(cds_graph, root_cells = colnames(cds_graph)[1:5])

run_test("graph_test with principal_graph", {
  test_res <- graph_test(cds_ordered,
                         neighbor_graph = "principal_graph",
                         cores = 1)
  stopifnot(is.data.frame(test_res))
  stopifnot("q_value" %in% colnames(test_res))
})

run_test("find_trajectory_variable_genes", {
  sig_genes <- find_trajectory_variable_genes(cds_ordered,
                                              q_value_threshold = 0.1,
                                              cores = 1)
  stopifnot(is.data.frame(sig_genes))
})

# ==============================================================================
# Test Model Functions
# ==============================================================================

cat("\n--- Testing Model Functions ---\n")

run_test("fit_models", {
  model_genes <- rownames(cds)[1:3]
  cds_subset <- cds_ordered[model_genes, ]
  fits <- fit_models(cds_subset,
                     model_formula_str = "~pseudotime",
                     expression_family = "quasipoisson",
                     cores = 1)
  stopifnot(nrow(fits) == 3)
})

run_test("coefficient_table", {
  model_genes <- rownames(cds)[1:3]
  cds_subset <- cds_ordered[model_genes, ]
  fits <- fit_models(cds_subset, model_formula_str = "~pseudotime", cores = 1)
  coefs <- coefficient_table(fits)
  stopifnot(is.data.frame(coefs))
  stopifnot("q_value" %in% colnames(coefs))
})

run_test("compare_models", {
  model_genes <- rownames(cds)[1:3]
  cds_subset <- cds_ordered[model_genes, ]
  full <- fit_models(cds_subset, model_formula_str = "~pseudotime + group", cores = 1)
  reduced <- fit_models(cds_subset, model_formula_str = "~pseudotime", cores = 1)
  comp <- compare_models(full, reduced)
  stopifnot(is.data.frame(comp))
})

run_test("evaluate_fits", {
  if (!exists("evaluate_fits", where = asNamespace("monocle3"))) {
    stop("evaluate_fits not available in this monocle3 version")
  }
  model_genes <- rownames(cds)[1:3]
  cds_subset <- cds_ordered[model_genes, ]
  fits <- fit_models(cds_subset, model_formula_str = "~pseudotime", cores = 1)
  eval_res <- evaluate_fits(fits)
  stopifnot(is.data.frame(eval_res))
  stopifnot("AIC" %in% colnames(eval_res))
})

# ==============================================================================
# Test Gene Module Functions
# ==============================================================================

cat("\n--- Testing Gene Module Functions ---\n")

run_test("find_gene_modules", {
  model_genes <- rownames(cds)[1:20]
  cds_subset <- cds_ordered[model_genes, ]
  gene_module_df <- find_gene_modules(cds_subset, resolution = 1e-3, cores = 1)
  stopifnot(is.data.frame(gene_module_df))
  stopifnot("module" %in% colnames(gene_module_df))
})

# ==============================================================================
# Test Export Functions
# ==============================================================================

cat("\n--- Testing Export Functions ---\n")

run_test("export_pseudotime_data", {
  tmpfile <- tempfile(fileext = ".csv")
  export_pseudotime_data(cds_ordered, tmpfile)
  stopifnot(file.exists(tmpfile))
  df <- read.csv(tmpfile)
  stopifnot("pseudotime" %in% colnames(df))
  unlink(tmpfile)
})

# ==============================================================================
# Summary
# ==============================================================================

cat("\n", rep("=", 50), "\n", sep = "")
cat("Test Summary\n")
cat(rep("=", 50), "\n", sep = "")
cat("Passed:", test_results$passed, "\n")
cat("Failed:", test_results$failed, "\n")
cat("Total:", test_results$passed + test_results$failed, "\n")

if (test_results$failed > 0) {
  cat("\nFailed tests:\n")
  for (err in test_results$errors) {
    cat("  -", err$name, "\n")
  }
  quit(status = 1)
} else {
  cat("\nAll tests passed!\n")
  quit(status = 0)
}
