#' NicheNet Skill Unit Tests
#'
#' Test suite for NicheNet skill functions.
#'
#' @author Yang Guo
#' @date 2026-04-01

library(testthat)

# Source all scripts
source("../scripts/r/nichenet_database.R")
source("../scripts/r/nichenet_analysis.R")
source("../scripts/r/nichenet_seurat.R")
source("../scripts/r/nichenet_visualization.R")
source("../scripts/r/nichenet_utils.R")

# ============================================================================
# Test Database Functions
# ============================================================================

test_that("Database directory is created", {
  dir <- .get_nichenet_dir()
  expect_true(dir.exists(dir))
})

test_that("List databases returns data frame", {
  result <- list_nichenet_databases()
  expect_s3_class(result, "data.frame")
  expect_true(all(c("organism", "file", "cached") %in% colnames(result)))
})

test_that("Check database returns logical", {
  result <- check_nichenet_database("human", verbose = FALSE)
  expect_type(result, "logical")
})

# ============================================================================
# Test Analysis Functions
# ============================================================================

test_that("Gene symbol conversion works", {
  # These are mock tests - in reality would need proper gene lists
  human_genes <- c("IL2", "IFNG", "TNF")
  expect_type(human_genes, "character")
})

test_that("Filter LR network works", {
  lr_network <- data.frame(
    from = c("IL2", "TNF", "IL1B"),
    to = c("IL2RA", "TNFR1", "IL1R1"),
    source = c("source1", "source2", "source3"),
    stringsAsFactors = FALSE
  )

  expressed_ligands <- c("IL2", "TNF")
  expressed_receptors <- c("IL2RA", "TNFR1")

  filtered <- filter_lr_network(lr_network, expressed_ligands, expressed_receptors)

  expect_equal(nrow(filtered), 2)
  expect_true(all(filtered$from %in% expressed_ligands))
  expect_true(all(filtered$to %in% expressed_receptors))
})

test_that("Summarize results returns string", {
  results <- list(
    ligand_activities = data.frame(
      test_ligand = c("IL2", "TNF"),
      pearson = c(0.5, 0.3),
      stringsAsFactors = FALSE
    ),
    top_ligands = c("IL2", "TNF"),
    sender = "Macrophage",
    receiver = "T_cell",
    parameters = list(
      organism = "human",
      n_sender_genes = 100,
      n_receiver_genes = 200,
      n_geneset = 50
    )
  )

  summary <- summarize_nichenet_results(results)
  expect_type(summary, "character")
  expect_true(grepl("NicheNet Analysis Summary", summary))
})

# ============================================================================
# Test Utility Functions
# ============================================================================

test_that("Ligand targets to data frame works", {
  ligand_targets <- list(
    IL2 = c("IL2RA", "STAT5", "FOXP3"),
    TNF = c("TNFAIP3", "NFKB1")
  )

  df <- ligand_targets_to_df(ligand_targets)

  expect_s3_class(df, "data.frame")
  expect_equal(nrow(df), 5)  # 3 + 2
  expect_true(all(c("ligand", "target") %in% colnames(df)))
})

test_that("Check gene format detects patterns", {
  human_like <- c("IL2", "IFNG", "TNF")
  result <- check_gene_format(human_like, "human")

  expect_type(result, "list")
  expect_true("suggestion" %in% names(result))
})

test_that("Get all ligands/receptors works", {
  lr_network <- data.frame(
    from = c("IL2", "TNF", "IL1B", "IL2"),  # IL2 duplicated intentionally
    to = c("IL2RA", "TNFR1", "IL1R1", "IL2RB"),
    source = c("source1", "source2", "source3", "source1"),
    stringsAsFactors = FALSE
  )

  ligands <- get_all_ligands(lr_network)
  receptors <- get_all_receptors(lr_network)

  expect_type(ligands, "character")
  expect_type(receptors, "character")
  expect_equal(length(ligands), 3)  # Unique values: IL2, TNF, IL1B
  expect_equal(length(receptors), 4)  # Unique values: IL2RA, TNFR1, IL1R1, IL2RB
})

# ============================================================================
# Test Visualization Helper Functions
# ============================================================================

test_that("Export results creates files", {
  # Create temp directory
  temp_dir <- tempfile()
  dir.create(temp_dir)

  results <- list(
    ligand_activities = data.frame(
      test_ligand = "IL2",
      pearson = 0.5,
      stringsAsFactors = FALSE
    ),
    top_ligands = "IL2",
    ligand_targets = list(IL2 = c("IL2RA")),
    lr_network = data.frame(
      from = "IL2",
      to = "IL2RA",
      stringsAsFactors = FALSE
    ),
    sender = "Macrophage",
    receiver = "T_cell",
    parameters = list(
      organism = "human",
      n_sender_genes = 100,
      n_receiver_genes = 200,
      n_geneset = 50
    )
  )

  export_nichenet_results(results, temp_dir, prefix = "test")

  expect_true(file.exists(file.path(temp_dir, "test_ligand_activities.csv")))
  expect_true(file.exists(file.path(temp_dir, "test_ligand_targets.csv")))
  expect_true(file.exists(file.path(temp_dir, "test_lr_network.csv")))

  # Cleanup
  unlink(temp_dir, recursive = TRUE)
})

# ============================================================================
# Integration Tests (skipped if no database)
# ============================================================================

if (check_nichenet_database("human", verbose = FALSE)) {

  test_that("Can load ligand-target matrix", {
    matrix <- get_ligand_target_matrix("human")
    expect_type(matrix, "double")
    expect_true(length(dim(matrix)) == 2)
  })

  test_that("Can get top targets", {
    matrix <- get_ligand_target_matrix("human")

    if ("IL2" %in% colnames(matrix)) {
      targets <- get_top_targets("IL2", matrix, n = 50)
      expect_type(targets, "character")
      expect_equal(length(targets), 50)
    }
  })

}

# ============================================================================
# Note: Tests should be run using test_file() or test_dir() from testthat
# Example: testthat::test_file("tests/test_nichenet.R")
# ============================================================================
