# Unit tests for scMetabolism analysis skill
# Tests the wrapper functions in scripts/r/

library(testthat)

# Source functions to test
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

source(file.path(script_dir, "run_scmetabolism.R"))
source(file.path(script_dir, "visualize_scmetabolism.R"))

# ============================================================================
# Test Data Setup
# ============================================================================

create_test_seurat <- function(n_genes = 200, n_cells = 100) {
  set.seed(42)

  # Create count matrix with some metabolic genes
  counts <- matrix(rpois(n_genes * n_cells, lambda = 3), nrow = n_genes, ncol = n_cells)

  # Add metabolic marker genes
  metabolic_genes <- c(
    "HK1", "HK2", "GPI", "PFKM", "ALDOA", "GAPDH", "PGK1", "ENO1", "PKM", "LDHA",
    "CS", "ACO2", "IDH1", "IDH2", "OGDH", "SDHA", "FH", "MDH1",
    "NDUFS1", "COX1", "ATP5F1A"
  )

  rownames(counts) <- c(
    metabolic_genes,
    paste0("GENE", (length(metabolic_genes) + 1):n_genes)
  )[1:n_genes]
  colnames(counts) <- paste0("CELL", 1:n_cells)

  # Create Seurat object
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  seurat_obj <- Seurat::NormalizeData(seurat_obj)
  seurat_obj <- Seurat::FindVariableFeatures(seurat_obj, nfeatures = min(100, n_genes))
  seurat_obj <- Seurat::ScaleData(seurat_obj)
  seurat_obj <- Seurat::RunPCA(seurat_obj, npcs = 10, verbose = FALSE)
  seurat_obj <- Seurat::FindNeighbors(seurat_obj, dims = 1:5, verbose = FALSE)
  seurat_obj <- Seurat::FindClusters(seurat_obj, resolution = 0.5, verbose = FALSE)
  seurat_obj <- Seurat::RunUMAP(seurat_obj, dims = 1:5, verbose = FALSE)

  return(seurat_obj)
}

# ============================================================================
# Tests for run_scmetabolism.R
# ============================================================================

test_that("get_metabolic_pathways returns correct format", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("GSEABase")

  kegg <- get_metabolic_pathways("KEGG")
  expect_type(kegg, "character")
  expect_gt(length(kegg), 80)  # Should have ~85 pathways

  reactome <- get_metabolic_pathways("REACTOME")
  expect_type(reactome, "character")
  expect_gt(length(reactome), 80)
})

test_that("get_metabolic_pathways validates input", {
  expect_error(get_metabolic_pathways("INVALID"), "KEGG or REACTOME")
})

test_that("run_scmetabolism validates inputs", {
  seurat_obj <- create_test_seurat()

  # Test invalid method
  expect_error(
    run_scmetabolism(seurat_obj, method = "INVALID"),
    "Invalid method"
  )

  # Test invalid database
  expect_error(
    run_scmetabolism(seurat_obj, metabolism.type = "INVALID"),
    "Invalid metabolism.type"
  )

  # Test invalid assay
  expect_error(
    run_scmetabolism(seurat_obj, assay = "INVALID"),
    "not found"
  )
})

test_that("run_scmetabolism works with different methods", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("Seurat")

  seurat_obj <- create_test_seurat()

  # Test with VISION (skip if VISION not installed)
  skip_if_not_installed("VISION")
  result <- run_scmetabolism(
    seurat_obj,
    method = "VISION",
    ncores = 1,
    return_matrix = TRUE
  )

  expect_type(result, "list")
  expect_true("seurat_obj" %in% names(result))
  expect_true("metabolism_matrix" %in% names(result))
  expect_s4_class(result$seurat_obj, "Seurat")
  expect_true("METABOLISM" %in% names(result$seurat_obj@assays))
})

test_that("run_scmetabolism_matrix works on raw matrix", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  counts <- matrix(rpois(1000, 5), nrow = 50, ncol = 20)
  rownames(counts) <- paste0("GENE", 1:50)
  colnames(counts) <- paste0("CELL", 1:20)

  # Add some metabolic genes
  rownames(counts)[1:10] <- c("HK1", "HK2", "GPI", "PFKM", "ALDOA",
                             "CS", "IDH1", "SDHA", "ATP5F1A", "GAPDH")

  result <- run_scmetabolism_matrix(
    countexp = as.data.frame(counts),
    method = "VISION",
    ncores = 1
  )

  expect_s3_class(result, "data.frame")
  expect_gt(nrow(result), 50)  # Should have many pathways
  expect_equal(ncol(result), 20)  # Same number of cells
})

test_that("extract_metabolism_scores works correctly", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  # Extract all scores
  all_scores <- extract_metabolism_scores(seurat_obj)
  expect_s3_class(all_scores, "data.frame")
  expect_equal(ncol(all_scores), ncol(seurat_obj))

  # Extract specific pathways
  pathways <- rownames(all_scores)[1:3]
  subset_scores <- extract_metabolism_scores(seurat_obj, pathways = pathways)
  expect_equal(nrow(subset_scores), 3)
  expect_equal(rownames(subset_scores), pathways)
})

test_that("extract_metabolism_scores validates input", {
  seurat_obj <- create_test_seurat()

  expect_error(
    extract_metabolism_scores(seurat_obj, assay = "INVALID"),
    "not found"
  )

  # Should warn about missing pathways but not error
  seurat_obj[["METABOLISM"]] <- Seurat::CreateAssayObject(
    data = matrix(1:20, nrow = 2, ncol = 10)
  )
  rownames(seurat_obj@assays$METABOLISM) <- c("Pathway1", "Pathway2")

  expect_warning(
    extract_metabolism_scores(seurat_obj, pathways = c("Pathway1", "Missing")),
    "not found"
  )
})

test_that("get_top_variable_pathways returns correct number", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  top5 <- get_top_variable_pathways(seurat_obj, n_top = 5)
  expect_equal(length(top5), 5)
  expect_type(top5, "character")

  top10 <- get_top_variable_pathways(seurat_obj, n_top = 10)
  expect_equal(length(top10), 10)
})

test_that("compare_metabolism works correctly", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  comparison <- compare_metabolism(
    seurat_obj,
    group.by = "seurat_clusters",
    pathways = get_top_variable_pathways(seurat_obj, 5)
  )

  expect_s3_class(comparison, "data.frame")
  expect_true(all(c("pathway", "group", "mean", "sd", "median", "n") %in% colnames(comparison)))
})

test_that("export_scmetabolism_results creates files", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  temp_dir <- tempdir()
  prefix <- "test_export"

  export_scmetabolism_results(seurat_obj, output_dir = temp_dir, prefix = prefix)

  expect_true(file.exists(file.path(temp_dir, paste0(prefix, "_scores.csv"))))
  expect_true(file.exists(file.path(temp_dir, paste0(prefix, "_params.txt"))))
  expect_true(file.exists(file.path(temp_dir, paste0(prefix, "_mean_by_group.csv"))))
})

# ============================================================================
# Tests for visualize_scmetabolism.R
# ============================================================================

test_that("dimplot_metabolism creates valid plot", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  pathways <- rownames(result$metabolism_matrix)

  p <- dimplot_metabolism(seurat_obj, pathway = pathways[1])
  expect_s3_class(p, "ggplot")
})

test_that("dimplot_metabolism validates inputs", {
  seurat_obj <- create_test_seurat()

  # Should error without METABOLISM assay
  expect_error(
    dimplot_metabolism(seurat_obj, pathway = "Test"),
    "not found"
  )

  # Add mock assay
  seurat_obj[["METABOLISM"]] <- Seurat::CreateAssayObject(
    data = matrix(1:20, nrow = 2, ncol = 10)
  )
  rownames(seurat_obj@assays$METABOLISM) <- c("Pathway1", "Pathway2")

  # Should error for missing pathway
  expect_error(
    dimplot_metabolism(seurat_obj, pathway = "Missing"),
    "not found"
  )
})

test_that("dotplot_metabolism creates valid plot", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  pathways <- rownames(result$metabolism_matrix)[1:3]

  p <- dotplot_metabolism(
    seurat_obj,
    pathways = pathways,
    group.by = "seurat_clusters"
  )
  expect_s3_class(p, "ggplot")
})

test_that("boxplot_metabolism creates valid plot", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  pathways <- rownames(result$metabolism_matrix)[1:2]

  p <- boxplot_metabolism(
    seurat_obj,
    pathways = pathways,
    group.by = "seurat_clusters"
  )
  expect_s3_class(p, "ggplot")
})

test_that("violinplot_metabolism creates valid plot", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  pathways <- rownames(result$metabolism_matrix)[1]

  p <- violinplot_metabolism(
    seurat_obj,
    pathways = pathways,
    group.by = "seurat_clusters"
  )
  expect_s3_class(p, "ggplot")
})

test_that("heatmap_metabolism creates valid plot", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")
  skip_if_not_installed("pheatmap")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  pathways <- rownames(result$metabolism_matrix)[1:5]

  p <- heatmap_metabolism(
    seurat_obj,
    pathways = pathways,
    group.by = "seurat_clusters"
  )
  expect_type(p, "list")  # pheatmap returns a list
})

test_that("ridgeplot_metabolism creates valid plot", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")
  skip_if_not_installed("ggridges")

  seurat_obj <- create_test_seurat()
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  seurat_obj <- result$seurat_obj

  pathways <- rownames(result$metabolism_matrix)[1:2]

  p <- ridgeplot_metabolism(
    seurat_obj,
    pathways = pathways,
    group.by = "seurat_clusters"
  )
  expect_s3_class(p, "ggplot")
})

# ============================================================================
# Integration Tests
# ============================================================================

test_that("complete workflow executes successfully", {
  skip_if_not_installed("scMetabolism")
  skip_if_not_installed("VISION")

  # Create test data
  seurat_obj <- create_test_seurat()

  # Run analysis
  result <- run_scmetabolism(seurat_obj, ncores = 1, return_matrix = TRUE)
  expect_type(result, "list")

  seurat_obj <- result$seurat_obj

  # Extract scores
  scores <- extract_metabolism_scores(seurat_obj)
  expect_s3_class(scores, "data.frame")

  # Get top pathways
  top <- get_top_variable_pathways(seurat_obj, n_top = 5)
  expect_equal(length(top), 5)

  # Create visualizations
  p1 <- dimplot_metabolism(seurat_obj, pathway = top[1])
  expect_s3_class(p1, "ggplot")

  p2 <- dotplot_metabolism(seurat_obj, pathways = top[1:3])
  expect_s3_class(p2, "ggplot")

  # Compare groups
  comparison <- compare_metabolism(seurat_obj, group.by = "seurat_clusters")
  expect_s3_class(comparison, "data.frame")
})

# ============================================================================
# Run tests
# ============================================================================

if (interactive()) {
  test_dir(dirname(sys.frame(1)$ofile))
}
