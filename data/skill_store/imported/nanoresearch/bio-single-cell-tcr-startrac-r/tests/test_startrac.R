#' STARTRAC Test Suite
#'
#' Tests for STARTRAC wrapper functions.
#' Run with: testthat::test_file("tests/test_startrac.R")

library(testthat)

# Source the functions to test
source("../scripts/r/startrac_analysis.R")
source("../scripts/r/startrac_visualization.R")
source("../scripts/r/startrac_utils.R")

# ============================================================================
# Test Data Setup
# ============================================================================

create_test_data <- function() {
    set.seed(123)
    data.frame(
        Cell_Name = paste0("Cell_", 1:100),
        clone.id = sample(paste0("Clone_", 1:20), 100, replace = TRUE),
        patient = rep(c("P1", "P2"), each = 50),
        majorCluster = sample(c("CD4", "CD8", "Treg"), 100, replace = TRUE),
        loc = sample(c("T", "N", "PB"), 100, replace = TRUE),
        stringsAsFactors = FALSE
    )
}

create_minimal_test_data <- function() {
    data.frame(
        Cell_Name = c("C1", "C2", "C3", "C4"),
        clone.id = c("A", "A", "B", "B"),
        patient = c("P1", "P1", "P1", "P1"),
        majorCluster = c("CD4", "CD4", "CD8", "CD8"),
        loc = c("T", "T", "N", "N"),
        stringsAsFactors = FALSE
    )
}

# ============================================================================
# Input Validation Tests
# ============================================================================

test_that("prepare_startrac_input validates Seurat object", {
    # This will fail without a real Seurat object
    # Just testing the error handling
    expect_error(
        prepare_startrac_input(data.frame(), clone_col = "clone"),
        "Input must be a Seurat object"
    )
})

test_that("validate_startrac_input checks required columns", {
    # Valid data
    valid_data <- create_test_data()
    expect_true(validate_startrac_input(valid_data, verbose = FALSE))

    # Missing columns
    invalid_data <- data.frame(Cell_Name = "C1", clone.id = "A")
    expect_false(validate_startrac_input(invalid_data, verbose = FALSE))

    # Empty data
    empty_data <- data.frame(
        Cell_Name = character(),
        clone.id = character(),
        patient = character(),
        majorCluster = character(),
        loc = character()
    )
    expect_false(validate_startrac_input(empty_data, verbose = FALSE))
})

test_that("validate_startrac_input handles NA values", {
    data <- create_test_data()
    data$clone.id[1:5] <- NA

    # Should return TRUE but with warnings
    expect_message(
        validate_startrac_input(data, verbose = TRUE),
        "WARNING"
    )
})

# ============================================================================
# Utility Function Tests
# ============================================================================

test_that("filter_clones removes singletons correctly", {
    data <- create_test_data()
    original_n_clones <- length(unique(data$clone.id))

    filtered <- filter_clones(data, min_size = 2)

    # Check all clones have at least 2 cells
    clone_counts <- table(filtered$clone.id)
    expect_true(all(clone_counts >= 2))

    # Check output structure
    expect_equal(colnames(filtered), colnames(data))
})

test_that("filter_clones applies max_size correctly", {
    data <- create_test_data()

    # Set a low max_size
    filtered <- filter_clones(data, min_size = 1, max_size = 5)

    clone_counts <- table(filtered$clone.id)
    expect_true(all(clone_counts <= 5))
})

test_that("summarize_clonotypes returns correct structure", {
    data <- create_test_data()
    summary <- summarize_clonotypes(data)

    # Check list structure
    expect_type(summary, "list")
    expect_named(summary, c("overall", "top_clones", "clonality_by_cluster",
                            "clonality_by_patient", "clonality_by_location"))

    # Check overall stats
    expect_equal(summary$overall$total_cells, nrow(data))
    expect_equal(summary$overall$total_clones, length(unique(data$clone.id)))

    # Check clonality data frames
    expect_true("n_cells" %in% colnames(summary$clonality_by_cluster))
    expect_true("clonality" %in% colnames(summary$clonality_by_cluster))
})

test_that("find_shared_clones calculates overlap correctly", {
    # Create data with known sharing
    data <- data.frame(
        Cell_Name = paste0("C", 1:8),
        clone.id = c("A", "A", "B", "B", "A", "C", "B", "C"),
        patient = rep("P1", 8),
        majorCluster = rep("CD4", 8),
        loc = c("T", "T", "T", "T", "N", "N", "N", "N"),
        stringsAsFactors = FALSE
    )

    shared <- find_shared_clones(data, group_by = "loc")

    # Check structure
    expect_type(shared, "list")
    expect_named(shared, c("groups", "clones_per_group", "overlap_matrix",
                           "jaccard_matrix", "shared_all", "n_shared_all"))

    # Clone A is in both T and N
    expect_true(shared$overlap_matrix["T", "N"] >= 1)
    expect_true(shared$overlap_matrix["N", "T"] >= 1)
})

test_that("calculate_clone_sharing works correctly", {
    data <- create_test_data()
    sharing <- calculate_clone_sharing(data, condition_col = "loc")

    expect_type(sharing, "list")
    expect_named(sharing, c("clone_details", "summary"))

    # Check clone details structure
    expect_true("n_cells" %in% colnames(sharing$clone_details))
    expect_true("n_conditions" %in% colnames(sharing$clone_details))
    expect_true("conditions" %in% colnames(sharing$clone_details))
})

# ============================================================================
# Export Function Tests
# ============================================================================

test_that("export_startrac_results validates input", {
    # Mock StartracOut object
    mock_result <- list(proj = "Test")
    class(mock_result) <- "StartracOut"

    # Will fail because mock object doesn't have proper slots
    expect_error(
        export_startrac_results(mock_result, "/tmp/test"),
        "trying to get slot"
    )
})

# ============================================================================
# Integration Tests
# ============================================================================

test_that("complete workflow runs without errors", {
    skip_if_not_installed("Startrac")

    data <- create_minimal_test_data()

    # Filter clones
    filtered <- filter_clones(data, min_size = 2)
    expect_gt(nrow(filtered), 0)

    # Validate
    expect_true(validate_startrac_input(filtered, verbose = FALSE))

    # Summarize
    summary <- summarize_clonotypes(filtered)
    expect_gt(summary$overall$total_cells, 0)

    # Run STARTRAC (if available)
    expect_silent({
        result <- run_startrac(filtered, proj = "Test", cores = 1, n.perm = NULL)
    })

    expect_s3_class(result, "StartracOut")
})

test_that("per-patient analysis works", {
    skip_if_not_installed("Startrac")

    data <- create_test_data()

    # Run by patient
    results <- run_startrac_by_patient(
        data,
        proj = "Test",
        cores = 1,
        n.perm = NULL,
        min_cells = 20
    )

    expect_type(results, "list")
})

# ============================================================================
# Run Tests
# ============================================================================

if (interactive()) {
    message("Running STARTRAC tests...")
    test_file("tests/test_startrac.R")
}
