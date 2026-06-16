#!/usr/bin/env Rscript
#' Test Suite for Augur Analysis Functions
#'
#' Run with: Rscript tests/test_augur_analysis.R

source("scripts/r/augur_analysis.R")

# Simple test runner
test_results <- list(passed = 0, failed = 0, errors = list())

run_test <- function(name, expr) {
  tryCatch({
    expr
    test_results$passed <<- test_results$passed + 1
    cat(sprintf("  PASS: %s\n", name))
  }, error = function(e) {
    test_results$failed <<- test_results$failed + 1
    test_results$errors[[name]] <<- conditionMessage(e)
    cat(sprintf("  FAIL: %s - %s\n", name, conditionMessage(e)))
  })
}

cat("Running Augur Analysis Tests\n")
cat(rep("=", 50), "\n", sep = "")

# ------------------------------------------------------------------------------
# Test 1: interpret_augur_score
# ------------------------------------------------------------------------------
cat("\nTest: interpret_augur_score\n")

run_test("Strong effect (>= 0.9)", {
  stopifnot(interpret_augur_score(0.95) == "Strong effect")
})

run_test("Moderate effect (0.7-0.9)", {
  stopifnot(interpret_augur_score(0.8) == "Moderate effect")
})

run_test("Weak effect (0.5-0.7)", {
  stopifnot(interpret_augur_score(0.6) == "Weak effect")
})

run_test("No effect (<= 0.5)", {
  stopifnot(interpret_augur_score(0.5) == "No effect (random)")
  stopifnot(interpret_augur_score(0.3) == "No effect (random)")
})

# ------------------------------------------------------------------------------
# Test 2: summarize_augur_results
# ------------------------------------------------------------------------------
cat("\nTest: summarize_augur_results\n")

run_test("Summary with AUC", {
  mock_augur <- list(
    AUC = data.frame(
      cell_type = c("A", "B", "C"),
      auc = c(0.95, 0.75, 0.55)
    )
  )
  stats <- summarize_augur_results(mock_augur)
  stopifnot(stats$n_cell_types == 3)
  stopifnot(stats$max_auc == 0.95)
  stopifnot(stats$most_affected == "A")
  stopifnot(stats$n_strong_effect == 1)
  stopifnot(stats$n_moderate_effect == 1)
  stopifnot(stats$n_weak_effect == 1)
})

run_test("Summary with CCC (regression)", {
  mock_augur <- list(
    CCC = data.frame(
      cell_type = c("A", "B"),
      ccc = c(0.8, 0.6)
    )
  )
  stats <- summarize_augur_results(mock_augur)
  stopifnot(stats$n_cell_types == 2)
  stopifnot(stats$mode == "regression")
})

run_test("Invalid object throws error", {
  tryCatch({
    summarize_augur_results(list(X = 1))
    stop("Should have thrown error")
  }, error = function(e) {
    stopifnot(grepl("Invalid Augur", conditionMessage(e)))
  })
})

# ------------------------------------------------------------------------------
# Test 3: get_prioritized_cell_types
# ------------------------------------------------------------------------------
cat("\nTest: get_prioritized_cell_types\n")

run_test("Filter by min_score", {
  mock_augur <- list(
    AUC = data.frame(
      cell_type = c("A", "B", "C"),
      auc = c(0.95, 0.75, 0.45)
    )
  )
  result <- get_prioritized_cell_types(mock_augur, min_score = 0.5)
  stopifnot(nrow(result) == 2)
})

run_test("Top N selection", {
  mock_augur <- list(
    AUC = data.frame(
      cell_type = c("A", "B", "C"),
      auc = c(0.95, 0.75, 0.55)
    )
  )
  result <- get_prioritized_cell_types(mock_augur, top_n = 2)
  stopifnot(nrow(result) == 2)
  stopifnot(result$cell_type[1] == "A")
})

# ------------------------------------------------------------------------------
# Test 4: get_top_features
# ------------------------------------------------------------------------------
cat("\nTest: get_top_features\n")

run_test("Get top features for all cell types", {
  mock_augur <- list(
    feature_importance = data.frame(
      cell_type = rep(c("A", "B"), each = 6),
      subsample_idx = rep(1, 12),
      fold = rep(1, 12),
      gene = rep(c("G1", "G2", "G3"), 4),
      importance = c(0.9, 0.5, 0.1, 0.8, 0.4, 0.2,
                     0.7, 0.3, 0.1, 0.6, 0.2, 0.1)
    )
  )
  result <- get_top_features(mock_augur, top_n = 2)
  stopifnot(nrow(result) > 0)
})

run_test("Get top features for specific cell type", {
  mock_augur <- list(
    feature_importance = data.frame(
      cell_type = rep(c("A", "B"), each = 3),
      subsample_idx = rep(1, 6),
      fold = rep(1, 6),
      gene = c("G1", "G2", "G3", "G4", "G5", "G6"),
      importance = c(0.9, 0.5, 0.1, 0.8, 0.4, 0.2)
    )
  )
  result <- get_top_features(mock_augur, cell_type = "A", top_n = 2)
  stopifnot(nrow(result) == 2)
})

run_test("Missing feature importance throws error", {
  tryCatch({
    get_top_features(list(AUC = data.frame()))
    stop("Should have thrown error")
  }, error = function(e) {
    stopifnot(grepl("No feature importance", conditionMessage(e)))
  })
})

# ------------------------------------------------------------------------------
# Test 5: validate_augur_data
# ------------------------------------------------------------------------------
cat("\nTest: validate_augur_data\n")

run_test("Valid Seurat-like input", {
  mock_meta <- data.frame(
    condition = c("control", "treatment", "control", "treatment"),
    cell_type = c("A", "A", "B", "B"),
    row.names = paste0("Cell", 1:4)
  )
  # Test with meta argument (simulating Seurat-like usage)
  result <- validate_augur_data(NULL, meta = mock_meta, label_col = "condition", cell_type_col = "cell_type")
  stopifnot(result$valid == TRUE)
  stopifnot(result$n_cells == 4)
  stopifnot(result$n_labels == 2)
  stopifnot(result$n_cell_types == 2)
})

run_test("Missing label column", {
  mock_meta <- data.frame(
    cell_type = c("A", "A", "B", "B")
  )
  result <- validate_augur_data(NULL, meta = mock_meta, label_col = "condition", cell_type_col = "cell_type")
  stopifnot(result$valid == FALSE)
  stopifnot(any(grepl("Label column", result$issues)))
})

run_test("Only one label", {
  mock_meta <- data.frame(
    condition = c("control", "control", "control", "control"),
    cell_type = c("A", "A", "B", "B")
  )
  result <- validate_augur_data(NULL, meta = mock_meta, label_col = "condition", cell_type_col = "cell_type")
  stopifnot(result$valid == FALSE)
  stopifnot(any(grepl("Need >= 2 labels", result$issues)))
})

run_test("Matrix input with metadata", {
  expr <- matrix(rnorm(20), nrow = 5)
  colnames(expr) <- paste0("Cell", 1:4)
  meta <- data.frame(
    condition = c("ctrl", "trt", "ctrl", "trt"),
    cell_type = c("A", "A", "B", "B"),
    row.names = paste0("Cell", 1:4)
  )
  result <- validate_augur_data(expr, meta = meta, label_col = "condition", cell_type_col = "cell_type")
  stopifnot(result$valid == TRUE)
})

run_test("Matrix without metadata fails", {
  expr <- matrix(rnorm(20), nrow = 5)
  result <- validate_augur_data(expr, meta = NULL)
  stopifnot(result$valid == FALSE)
})

# ------------------------------------------------------------------------------
# Test 6: export_augur_results
# ------------------------------------------------------------------------------
cat("\nTest: export_augur_results\n")

run_test("Export creates files", {
  tmp_dir <- tempfile("augur_test_")
  mock_augur <- list(
    AUC = data.frame(cell_type = "A", auc = 0.8),
    feature_importance = data.frame(
      cell_type = "A", subsample_idx = 1, fold = 1, gene = "G1", importance = 0.5
    )
  )
  export_augur_results(mock_augur, output_dir = tmp_dir, prefix = "test", verbose = FALSE)
  stopifnot(file.exists(file.path(tmp_dir, "test_auc_summary.csv")))
  stopifnot(file.exists(file.path(tmp_dir, "test_feature_importances.csv")))
  unlink(tmp_dir, recursive = TRUE)
})

# ------------------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------------------
cat("\n")
cat(rep("=", 50), "\n", sep = "")
cat(sprintf("Tests Passed: %d\n", test_results$passed))
cat(sprintf("Tests Failed: %d\n", test_results$failed))

if (test_results$failed > 0) {
  cat("\nFailed tests:\n")
  for (name in names(test_results$errors)) {
    cat(sprintf("  - %s: %s\n", name, test_results$errors[[name]]))
  }
  quit(status = 1)
} else {
  cat("\nAll tests passed!\n")
}
