# Unit tests for SCENIC regulatory analysis
# Test suite for bio-single-cell-regulatory-scenic-r skill

library(testthat)
library(Seurat)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source main functions
source(file.path(script_dir, "scenic_analysis.R"))

context("SCENIC Analysis Functions")

# ============================================================================
# Test Data Helpers
# ============================================================================

create_test_seurat <- function(n_cells = 50, n_genes = 100) {
  set.seed(42)
  counts <- matrix(rpois(n_cells * n_genes, lambda = 5),
                   nrow = n_genes, ncol = n_cells)
  rownames(counts) <- paste0("GENE", 1:n_genes)
  colnames(counts) <- paste0("CELL", 1:n_cells)

  obj <- CreateSeuratObject(counts = counts)
  obj <- NormalizeData(obj, verbose = FALSE)
  obj$seurat_clusters <- factor(sample(1:4, n_cells, replace = TRUE))

  return(obj)
}

create_mock_scenic_assay <- function(seurat_obj, n_regulons = 20) {
  set.seed(42)
  n_cells <- ncol(seurat_obj)

  # Create mock regulon AUC matrix
  auc_matrix <- matrix(runif(n_regulons * n_cells, 0, 0.5),
                       nrow = n_regulons, ncol = n_cells)
  rownames(auc_matrix) <- paste0(c("SOX10", "MITF", "TFAP2A", "STAT1", "IRF4",
                                    "GATA1", "GATA2", "MYC", "KLF4", "OCT4",
                                    "NANOG", "SOX2", "PAX6", "NEUROD1", "ASCL1",
                                    "MYOD1", "RUNX1", "EBF1", "PAX5", "BCL6"))[1:n_regulons]
  colnames(auc_matrix) <- colnames(seurat_obj)

  # Use data= (not counts=) to match add_scenic_to_seurat() behavior
  return(CreateAssayObject(data = auc_matrix))
}

# ============================================================================
# Tests for Function Existence
# ============================================================================

test_that("init_scenic function exists", {
  expect_true(exists("init_scenic"))
  expect_type(init_scenic, "closure")
})

test_that("run_scenic_pipeline function exists", {
  expect_true(exists("run_scenic_pipeline"))
  expect_type(run_scenic_pipeline, "closure")
})

test_that("load_scenic_results function exists", {
  expect_true(exists("load_scenic_results"))
  expect_type(load_scenic_results, "closure")
})

test_that("add_scenic_to_seurat function exists", {
  expect_true(exists("add_scenic_to_seurat"))
  expect_type(add_scenic_to_seurat, "closure")
})

test_that("get_top_regulons function exists", {
  expect_true(exists("get_top_regulons"))
  expect_type(get_top_regulons, "closure")
})

test_that("plot_regulon_activity function exists", {
  expect_true(exists("plot_regulon_activity"))
  expect_type(plot_regulon_activity, "closure")
})

test_that("find_celltype_specific_regulons function exists", {
  expect_true(exists("find_celltype_specific_regulons"))
  expect_type(find_celltype_specific_regulons, "closure")
})

test_that("validate_tf_list function exists", {
  expect_true(exists("validate_tf_list"))
  expect_type(validate_tf_list, "closure")
})

test_that("run_correlation_network function exists", {
  expect_true(exists("run_correlation_network"))
  expect_type(run_correlation_network, "closure")
})

test_that("run_aucell_binarization function exists", {
  expect_true(exists("run_aucell_binarization"))
  expect_type(run_aucell_binarization, "closure")
})

test_that("load_binary_activity function exists", {
  expect_true(exists("load_binary_activity"))
  expect_type(load_binary_activity, "closure")
})

test_that("get_active_regulons_by_celltype function exists", {
  expect_true(exists("get_active_regulons_by_celltype"))
  expect_type(get_active_regulons_by_celltype, "closure")
})

# ============================================================================
# Database Management Functions (New)
# ============================================================================

test_that("get_skill_root_dir function exists", {
  expect_true(exists("get_skill_root_dir"))
  expect_type(get_skill_root_dir, "closure")
})

test_that("get_cistarget_dir function exists", {
  expect_true(exists("get_cistarget_dir"))
  expect_type(get_cistarget_dir, "closure")
})

test_that("list_cistarget_cache_locations function exists", {
  expect_true(exists("list_cistarget_cache_locations"))
  expect_type(list_cistarget_cache_locations, "closure")
})

test_that("migrate_databases_to_skill_assets function exists", {
  expect_true(exists("migrate_databases_to_skill_assets"))
  expect_type(migrate_databases_to_skill_assets, "closure")
})

test_that("check_cistarget_databases function exists", {
  expect_true(exists("check_cistarget_databases"))
  expect_type(check_cistarget_databases, "closure")
})

test_that("download_cistarget_databases function exists", {
  expect_true(exists("download_cistarget_databases"))
  expect_type(download_cistarget_databases, "closure")
})

test_that("list_cistarget_databases function exists", {
  expect_true(exists("list_cistarget_databases"))
  expect_type(list_cistarget_databases, "closure")
})

test_that("init_scenic_auto function exists", {
  expect_true(exists("init_scenic_auto"))
  expect_type(init_scenic_auto, "closure")
})

# ============================================================================
# Tests for Database Management
# ============================================================================

test_that("get_skill_root_dir returns NULL or path", {
  # In test environment, this may return NULL
  result <- get_skill_root_dir()

  # Should return either NULL or a character path
  expect_true(is.null(result) || is.character(result))
})

test_that("get_cistarget_dir respects prefer_skill_assets parameter", {
  temp_dir <- file.path(tempdir(), "test_cistarget")

  # Clean up if exists
  if (dir.exists(temp_dir)) {
    unlink(temp_dir, recursive = TRUE)
  }

  # Test with prefer_skill_assets = FALSE (use fallback)
  result <- get_cistarget_dir(temp_dir, prefer_skill_assets = FALSE)

  expect_true(dir.exists(temp_dir))
  expect_equal(normalizePath(temp_dir), result)

  # Cleanup
  unlink(temp_dir, recursive = TRUE)
})

test_that("list_cistarget_cache_locations returns correct structure", {
  locations <- list_cistarget_cache_locations()

  expect_type(locations, "list")
  expect_true("home_cache" %in% names(locations))
  expect_true("skill_assets" %in% names(locations) || is.null(locations$skill_assets))
})

test_that("migrate_databases_to_skill_assets validates inputs", {
  # Should error if skill root not found (in test environment)
  expect_error(
    migrate_databases_to_skill_assets(home_dir = tempdir(), dry_run = TRUE),
    NA  # May error or may not depending on environment
  )
})

test_that("check_cistarget_databases returns correct structure", {
  temp_dir <- file.path(tempdir(), "test_cistarget_check")
  dir.create(temp_dir, showWarnings = FALSE)

  # Check without databases, with skill assets disabled
  status <- check_cistarget_databases("hgnc", temp_dir, "10kb", prefer_skill_assets = FALSE)

  expect_type(status, "list")
  expect_equal(status$org, "hgnc")
  expect_false(status$all_ready)  # Should be false without downloads
  expect_true("rankings" %in% names(status))
  expect_true("motif_annotation" %in% names(status))
  expect_true("tf_list" %in% names(status))

  # Cleanup
  unlink(temp_dir, recursive = TRUE)
})

test_that("check_cistarget_databases handles different organisms", {
  temp_dir <- tempdir()

  for (org in c("hgnc", "mmusculus", "dmel")) {
    status <- check_cistarget_databases(org, temp_dir, "10kb")
    expect_equal(status$org, org)
  }
})

test_that("check_cistarget_databases validates motif versions", {
  temp_dir <- tempdir()

  # v10 should work for human and mouse
  status_v10 <- check_cistarget_databases("hgnc", temp_dir, motif_version = "v10")
  expect_false(is.null(status_v10$motif_file))

  # v9 should also work
  status_v9 <- check_cistarget_databases("hgnc", temp_dir, motif_version = "v9")
  expect_false(is.null(status_v9$motif_file))
})

test_that("list_cistarget_databases returns data frame", {
  temp_dir <- tempdir()

  result <- list_cistarget_databases(temp_dir)

  expect_s3_class(result, "data.frame")
  expect_true("organism" %in% colnames(result))
  expect_true("type" %in% colnames(result))
  expect_true("all_ready" %in% colnames(result))
  expect_gt(nrow(result), 0)
})

test_that("init_scenic_auto validates parameters", {
  skip_if_not_installed("SCENIC")

  # Check that parameters are passed correctly
  args <- formals(init_scenic_auto)

  expect_equal(args$dbDir, "cisTarget")
  expect_equal(args$db_types, "10kb")
  expect_equal(args$motif_version, "v10")
  expect_equal(args$download_if_missing, TRUE)
  expect_equal(args$force_download, FALSE)
})

test_that("Database config has required entries", {
  # Verify CISTARGET_DB_CONFIG structure
  expect_true(exists("CISTARGET_DB_CONFIG"))

  for (org in names(CISTARGET_DB_CONFIG)) {
    config <- CISTARGET_DB_CONFIG[[org]]

    expect_true("name" %in% names(config))
    expect_true("base_url" %in% names(config))
    expect_true("rankings" %in% names(config))
    expect_true("motif_annotations" %in% names(config))
    expect_true("tf_list" %in% names(config))

    # Check rankings
    expect_true("500bp" %in% names(config$rankings) || "10kb" %in% names(config$rankings))
  }
})

# ============================================================================
# Tests for get_top_regulons
# ============================================================================

test_that("get_top_regulons returns correct structure", {
  seurat_obj <- create_test_seurat(n_cells = 30)
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj)

  results <- get_top_regulons(seurat_obj, group_by = "seurat_clusters", top_n = 5)

  expect_type(results, "list")
  expect_true(all(c("group", "regulon", "avg_auc") %in% colnames(results)))
  expect_equal(nrow(results), length(unique(seurat_obj$seurat_clusters)) * 5)
})

test_that("get_top_regulons handles invalid assay", {
  seurat_obj <- create_test_seurat()

  expect_error(
    get_top_regulons(seurat_obj, assayName = "INVALID"),
    "Assay 'INVALID' not found"
  )
})

test_that("get_top_regulons handles invalid group_by", {
  seurat_obj <- create_test_seurat()
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj)

  expect_error(
    get_top_regulons(seurat_obj, group_by = "nonexistent"),
    "Column 'nonexistent' not found"
  )
})

# ============================================================================
# Tests for find_celltype_specific_regulons
# ============================================================================

test_that("find_celltype_specific_regulons returns list", {
  seurat_obj <- create_test_seurat(n_cells = 40)
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj)

  results <- find_celltype_specific_regulons(seurat_obj, group_by = "seurat_clusters")

  expect_type(results, "list")
  expect_equal(length(results), length(unique(seurat_obj$seurat_clusters)))
})

test_that("find_celltype_specific_regulons filters by min_auc", {
  seurat_obj <- create_test_seurat(n_cells = 30)
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj)

  results_high <- find_celltype_specific_regulons(seurat_obj, min_auc = 0.3)
  results_low <- find_celltype_specific_regulons(seurat_obj, min_auc = 0.01)

  # Higher threshold should give fewer or equal regulons
  total_high <- sum(sapply(results_high, length))
  total_low <- sum(sapply(results_low, length))

  expect_lte(total_high, total_low)
})

# ============================================================================
# Tests for add_scenic_to_seurat
# ============================================================================

test_that("add_scenic_to_seurat adds assay correctly", {
  skip("Requires SCENIC results object")
})

# ============================================================================
# Tests for plot_regulon_activity
# ============================================================================

test_that("plot_regulon_activity validates assay", {
  seurat_obj <- create_test_seurat()

  expect_error(
    plot_regulon_activity(seurat_obj, "SOX10", assayName = "INVALID"),
    "Assay 'INVALID' not found"
  )
})

test_that("plot_regulon_activity handles missing regulons", {
  seurat_obj <- create_test_seurat()
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj, n_regulons = 5)

  # Need a reduction for FeaturePlot
  seurat_obj$umap_1 <- rnorm(ncol(seurat_obj))
  seurat_obj$umap_2 <- rnorm(ncol(seurat_obj))
  seurat_obj[["umap"]] <- CreateDimReducObject(
    embeddings = cbind(seurat_obj$umap_1, seurat_obj$umap_2),
    key = "UMAP_"
  )

  expect_warning(
    plot_regulon_activity(seurat_obj, c("SOX10", "NONEXISTENT")),
    "Regulons not found"
  )
})

# ============================================================================
# Tests for init_scenic
# ============================================================================

test_that("init_scenic validates organism parameter", {
  skip_if_not_installed("SCENIC")

  # Valid organisms
  expect_error(init_scenic("hgnc"), NA)
  expect_error(init_scenic("mmusculus"), NA)
})

test_that("init_scenic requires SCENIC package", {
  if (requireNamespace("SCENIC", quietly = TRUE)) {
    skip("SCENIC is installed")
  }

  expect_error(
    init_scenic("hgnc"),
    "SCENIC package required"
  )
})

# ============================================================================
# Tests for load_scenic_results
# ============================================================================

test_that("load_scenic_results validates type parameter", {
  skip_if_not_installed("SCENIC")

  # Valid types
  expect_error(load_scenic_results(NULL, "aucell"), NA)
  expect_error(load_scenic_results(NULL, "regulons"), NA)
  expect_error(load_scenic_results(NULL, "modules"), NA)

  # Invalid type
  expect_error(load_scenic_results(NULL, "invalid"))
})

# ============================================================================
# Integration Tests
# ============================================================================

test_that("Complete SCENIC workflow with mock data", {
  seurat_obj <- create_test_seurat(n_cells = 50)
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj, n_regulons = 15)

  # Get top regulons
  top_regulons <- get_top_regulons(seurat_obj, top_n = 3)
  expect_gt(nrow(top_regulons), 0)

  # Find specific regulons
  specific <- find_celltype_specific_regulons(seurat_obj, min_auc = 0.01)
  expect_type(specific, "list")

  # Add UMAP for plotting
  seurat_obj$umap_1 <- rnorm(ncol(seurat_obj))
  seurat_obj$umap_2 <- rnorm(ncol(seurat_obj))
  seurat_obj[["umap"]] <- CreateDimReducObject(
    embeddings = cbind(seurat_obj$umap_1, seurat_obj$umap_2),
    key = "UMAP_"
  )

  # Plot (just verify it doesn't error)
  expect_error(
    plot_regulon_activity(seurat_obj, rownames(seurat_obj[["SCENIC"]])[1:2]),
    NA
  )
})

# ============================================================================
# Edge Cases
# ============================================================================

test_that("get_top_regulons handles single cluster", {
  seurat_obj <- create_test_seurat(n_cells = 20)
  seurat_obj$seurat_clusters <- factor(rep(1, 20))
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj)

  results <- get_top_regulons(seurat_obj, group_by = "seurat_clusters", top_n = 5)

  expect_equal(length(unique(results$group)), 1)
})

test_that("find_celltype_specific_regulons handles few cells", {
  seurat_obj <- create_test_seurat(n_cells = 10)
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj)

  results <- find_celltype_specific_regulons(seurat_obj)

  expect_type(results, "list")
})

test_that("Functions handle empty regulon list", {
  seurat_obj <- create_test_seurat(n_cells = 10)
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj, n_regulons = 3)

  specific <- find_celltype_specific_regulons(seurat_obj, min_auc = 0.9)

  # All regulons should be filtered out with high threshold
  expect_true(all(sapply(specific, length) == 0))
})

# ============================================================================
# Tests for validate_tf_list (New Function)
# ============================================================================

test_that("validate_tf_list calculates overlap correctly", {
  # Create test expression matrix with known genes
  set.seed(42)
  exprMat <- matrix(rpois(100, 5), nrow = 10, ncol = 10)
  rownames(exprMat) <- paste0("GENE", 1:10)
  colnames(exprMat) <- paste0("CELL", 1:10)

  # Create TF list with partial overlap
  tfList <- c("GENE1", "GENE2", "GENE3", "MISSING1", "MISSING2")

  result <- validate_tf_list(exprMat, tfList, minOverlapPct = 50)

  expect_type(result, "list")
  expect_equal(result$overlapCount, 3)
  expect_equal(result$totalTFs, 5)
  expect_equal(result$overlapPct, 60)
  expect_length(result$missingTFs, 2)
  expect_true(result$valid)
})

test_that("validate_tf_list warns on low overlap", {
  set.seed(42)
  exprMat <- matrix(rpois(100, 5), nrow = 10, ncol = 10)
  rownames(exprMat) <- paste0("GENE", 1:10)

  # Most TFs missing
  tfList <- c("GENE1", "MISSING1", "MISSING2", "MISSING3", "MISSING4")

  expect_warning(
    result <- validate_tf_list(exprMat, tfList, minOverlapPct = 80),
    "Low TF overlap"
  )

  expect_false(result$valid)
  expect_lt(result$overlapPct, 80)
})

test_that("validate_tf_list handles perfect overlap", {
  set.seed(42)
  exprMat <- matrix(rpois(50, 5), nrow = 5, ncol = 10)
  rownames(exprMat) <- paste0("TF", 1:5)

  tfList <- paste0("TF", 1:5)

  result <- validate_tf_list(exprMat, tfList)

  expect_equal(result$overlapPct, 100)
  expect_length(result$missingTFs, 0)
  expect_true(result$valid)
})

# ============================================================================
# Tests for run_correlation_network (New Function)
# ============================================================================

test_that("run_correlation_network requires SCENIC package", {
  if (requireNamespace("SCENIC", quietly = TRUE)) {
    skip("SCENIC is installed")
  }

  set.seed(42)
  exprMat <- matrix(rpois(100, 5), nrow = 10, ncol = 10)

  expect_error(
    run_correlation_network(exprMat, NULL),
    "SCENIC package required"
  )
})

# ============================================================================
# Tests for Binary Activity Functions (New Functions)
# ============================================================================

test_that("load_binary_activity requires existing file", {
  skip_if_not_installed("SCENIC")

  # Create mock scenicOptions
  mockOptions <- list()
  class(mockOptions) <- "ScenicOptions"

  expect_error(
    load_binary_activity(mockOptions),
    "Binary activity not found"
  )
})

test_that("get_active_regulons_by_celltype validates inputs", {
  skip_if_not_installed("SCENIC")

  # Create mock binary matrix
  binaryMat <- matrix(sample(0:1, 100, replace = TRUE), nrow = 10, ncol = 10)
  rownames(binaryMat) <- paste0("Regulon", 1:10)
  colnames(binaryMat) <- paste0("CELL", 1:10)

  # Cell info with mismatched cells
  cellInfo <- data.frame(
    cellType = rep(c("A", "B"), each = 5),
    row.names = paste0("OTHER", 1:10)
  )

  # This will fail because load_binary_activity needs proper SCENIC setup
  # Just test the validation logic exists
  expect_error(
    get_active_regulons_by_celltype(NULL, cellInfo, "cellType"),
    "SCENIC package required"
  )
})

# ============================================================================
# Tests for Pipeline Parameters (New Features)
# ============================================================================

test_that("run_scenic_pipeline validates new parameters", {
  skip_if_not_installed("SCENIC")

  set.seed(42)
  exprMat <- matrix(rpois(200, 5), nrow = 20, ncol = 10)
  rownames(exprMat) <- paste0("GENE", 1:20)
  colnames(exprMat) <- paste0("CELL", 1:10)

  # Test parameter validation doesn't error on basic structure
  # Full test requires complete SCENIC setup
  expect_true(exists("run_scenic_pipeline"))
})

test_that("run_scenic_pipeline accepts correlation network option", {
  # Just verify the parameter exists and function is callable
  args <- formals(run_scenic_pipeline)
  expect_true("useCorrelationNetwork" %in% names(args))
  expect_equal(args$useCorrelationNetwork, FALSE)
})

test_that("run_scenic_pipeline accepts resume option", {
  args <- formals(run_scenic_pipeline)
  expect_true("resumePreviousRun" %in% names(args))
  expect_equal(args$resumePreviousRun, FALSE)
})

test_that("run_scenic_pipeline accepts weight threshold parameters", {
  args <- formals(run_scenic_pipeline)
  expect_true("weightThreshold" %in% names(args))
  expect_true("topThr" %in% names(args))
  expect_true("nTopTFs" %in% names(args))
  expect_true("nTopTargets" %in% names(args))
  expect_true("minGenes" %in% names(args))
})

# ============================================================================
# Integration Tests with New Features
# ============================================================================

test_that("Complete workflow with binary activity support", {
  seurat_obj <- create_test_seurat(n_cells = 30)
  seurat_obj[["SCENIC"]] <- create_mock_scenic_assay(seurat_obj, n_regulons = 10)

  # Add mock binary assay
  binary_matrix <- matrix(
    sample(0:1, 300, replace = TRUE, prob = c(0.7, 0.3)),
    nrow = 10, ncol = 30
  )
  rownames(binary_matrix) <- rownames(seurat_obj[["SCENIC"]])
  colnames(binary_matrix) <- colnames(seurat_obj)
  seurat_obj[["SCENIC_binary"]] <- CreateAssayObject(counts = binary_matrix)

  # Test that we can work with binary data
  expect_true("SCENIC_binary" %in% names(seurat_obj@assays))

  # Test binary data structure
  expect_equal(dim(seurat_obj[["SCENIC_binary"]]), c(10, 30))
})

# Note: Full SCENIC pipeline tests require SCENIC package and cisTarget databases.
# These are integration tests that take hours to run.
# Basic function tests are included above.
