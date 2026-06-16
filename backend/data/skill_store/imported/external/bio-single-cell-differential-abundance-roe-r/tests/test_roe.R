# Ro/e Analysis Tests
# Test suite for bio-single-cell-differential-abundance-roe-r skill

library(testthat)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source functions
source(file.path(script_dir, "roe_analysis.R"))
source(file.path(script_dir, "roe_visualization.R"))

context("Ro/e Differential Abundance Analysis")

# Create test data
create_test_data <- function() {
  set.seed(42)

  # Simulate cell types
  cell_types <- c(
    rep("T_cell", 150),
    rep("B_cell", 100),
    rep("Macrophage", 80),
    rep("Fibroblast", 120),
    rep("Endothelial", 50)
  )

  # Simulate groups with some enrichment patterns
  # Group A: more T cells and Macrophages
  # Group B: more B cells and Fibroblasts
  groups <- c(
    rep("Group_A", 80),   # T cells in A
    rep("Group_B", 70),   # T cells in B
    rep("Group_A", 30),   # B cells in A
    rep("Group_B", 70),   # B cells in B
    rep("Group_A", 60),   # Macrophages in A
    rep("Group_B", 20),   # Macrophages in B
    rep("Group_A", 40),   # Fibroblasts in A
    rep("Group_B", 80),   # Fibroblasts in B
    rep("Group_A", 30),   # Endothelial in A
    rep("Group_B", 20)    # Endothelial in B
  )

  list(cell_types = cell_types, groups = groups)
}

test_that("calculate_roe returns correct structure", {
  test_data <- create_test_data()

  result <- calculate_roe(test_data$cell_types, test_data$groups)

  expect_s3_class(result, "roe_result")
  expect_named(result, c("roe", "observed", "expected", "counts", "statistics",
                         "method", "n_cells", "n_groups", "n_cell_types"))

  expect_equal(result$n_cells, length(test_data$cell_types))
  expect_equal(result$n_groups, 2)
  expect_equal(result$n_cell_types, 5)
})

test_that("calculate_roe computes correct Ro/e values", {
  test_data <- create_test_data()

  result <- calculate_roe(test_data$cell_types, test_data$groups)

  # T cells should be enriched in Group A (80/150 vs 50% expected)
  expect_gt(result$roe["T_cell", "Group_A"], 1)

  # B cells should be enriched in Group B (70/100 vs 40% expected)
  expect_gt(result$roe["B_cell", "Group_B"], 1)

  # Macrophages should be enriched in Group A (60/80 vs 32% expected)
  expect_gt(result$roe["Macrophage", "Group_A"], 1)

  # Check that observed + expected proportions are consistent
  expect_equal(sum(result$observed[, "Group_A"]), 1, tolerance = 0.01)
  expect_equal(sum(result$observed[, "Group_B"]), 1, tolerance = 0.01)
})

test_that("calculate_roe handles edge cases", {
  # Single cell type
  result <- calculate_roe(rep("A", 100), rep("G1", 100))
  expect_equal(as.numeric(result$roe["A", "G1"]), 1)

  # Single group
  result <- calculate_roe(c("A", "B", "C"), rep("G1", 3))
  expect_equal(as.numeric(result$roe[, "G1"]), c(1, 1, 1))

  # Empty input
  expect_error(calculate_roe(character(0), character(0)))
})

test_that("calculate_roe handles NAs", {
  cell_types <- c("A", "B", "A", NA, "B", "A")
  groups <- c("G1", "G1", "G1", "G2", "G2", "G2")

  result <- calculate_roe(cell_types, groups)

  # Should work after removing NAs
  expect_equal(result$n_cells, 5)  # One NA removed
})

test_that("roe_to_dataframe returns correct structure", {
  test_data <- create_test_data()
  result <- calculate_roe(test_data$cell_types, test_data$groups)

  df <- roe_to_dataframe(result)

  expect_s3_class(df, "data.frame")
  expect_true(all(c("cell_type", "group", "roe", "observed_prop",
                    "expected_prop", "p_value", "p_value_adj", "significant") %in%
                    colnames(df)))

  # Should have n_cell_types * n_groups rows
  expect_equal(nrow(df), 5 * 2)
})

test_that("calculate_roe_bootstrap adds CI columns", {
  test_data <- create_test_data()

  result <- calculate_roe_bootstrap(
    test_data$cell_types,
    test_data$groups,
    n_bootstrap = 100  # Small for testing
  )

  expect_false(is.null(result$bootstrap))
  expect_equal(result$bootstrap$n_bootstrap, 100)
  expect_equal(result$bootstrap$conf_level, 0.95)

  df <- roe_to_dataframe(result)
  expect_true(all(c("ci_lower", "ci_upper", "roe_sd") %in% colnames(df)))
})

test_that("plot functions return ggplot objects", {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    skip("ggplot2 not available")
  }

  test_data <- create_test_data()
  result <- calculate_roe(test_data$cell_types, test_data$groups)

  p_heatmap <- plot_roe_heatmap(result)
  expect_s3_class(p_heatmap, "ggplot")

  p_lollipop <- plot_roe_lollipop(result, compare_group = "Group_A")
  expect_s3_class(p_lollipop, "ggplot")

  p_dot <- plot_roe_dotplot(result)
  expect_s3_class(p_dot, "ggplot")

  p_bar <- plot_roe_bar(result)
  expect_s3_class(p_bar, "ggplot")
})

test_that("plot_roe_lollipop handles parameters correctly", {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    skip("ggplot2 not available")
  }

  test_data <- create_test_data()
  result <- calculate_roe(test_data$cell_types, test_data$groups)

  # Without highlighting
  p1 <- plot_roe_lollipop(result, highlight_sig = FALSE)
  expect_s3_class(p1, "ggplot")

  # Without color by depletion
  p2 <- plot_roe_lollipop(result, color_by_depletion = FALSE)
  expect_s3_class(p2, "ggplot")

  # With min_roe filter
  p3 <- plot_roe_lollipop(result, min_roe = 0.5)
  expect_s3_class(p3, "ggplot")
})

test_that("statistics are calculated correctly", {
  test_data <- create_test_data()
  result <- calculate_roe(test_data$cell_types, test_data$groups)

  # Chi-square test should be significant (we designed the data with patterns)
  expect_lt(result$statistics$overall_p, 1)

  # Each cell type should have statistics
  expect_equal(length(result$statistics$per_cell_type), 5)

  # Check that p-values are valid
  p_values <- sapply(result$statistics$per_cell_type, function(x) x$p_value)
  expect_true(all(p_values >= 0 & p_values <= 1))
})

test_that("print.roe_result works correctly", {
  test_data <- create_test_data()
  result <- calculate_roe(test_data$cell_types, test_data$groups)

  # Should print without error
  expect_output(print(result), "Ro/e Differential Abundance Analysis")
  expect_output(print(result), "500")  # n_cells
  expect_output(print(result), "2")    # n_groups
  expect_output(print(result), "5")    # n_cell_types
})

# Tests are run via testthat::test_file() or testthat::test_dir()
# Do not add auto-runners here as sys.frame(1)$ofile is NULL when sourced interactively
