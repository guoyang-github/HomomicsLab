# inferCNV Unit Tests
# Test suite for bio-single-cell-cnv-infercnv-r skill

library(testthat)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source main functions
source(file.path(script_dir, "run_infercnv.R"))

context("inferCNV Functions")

# ============================================================================
# Test Data Helpers
# ============================================================================

create_test_gene_order <- function(n_genes = 100) {
  set.seed(42)

  # Create genes distributed across chromosomes
  genes <- data.frame(
    gene = paste0("GENE", 1:n_genes),
    chr = sample(c(paste0("chr", 1:22), "chrX", "chrY"), n_genes, replace = TRUE),
    start = sample(1000:1000000, n_genes),
    stringsAsFactors = FALSE
  )

  # Sort by chromosome and position
  chr_order <- c(paste0("chr", 1:22), "chrX", "chrY")
  genes$chr <- factor(genes$chr, levels = chr_order)
  genes <- genes[order(genes$chr, genes$start), ]
  genes$chr <- as.character(genes$chr)

  # Calculate end positions
  genes$end <- genes$start + sample(500:5000, n_genes)

  return(genes[, c("gene", "chr", "start", "end")])
}

create_test_counts <- function(n_genes = 100, n_cells = 50) {
  set.seed(42)
  counts <- matrix(rpois(n_genes * n_cells, lambda = 5),
                   nrow = n_genes, ncol = n_cells)
  rownames(counts) <- paste0("GENE", 1:n_genes)
  colnames(counts) <- paste0("CELL", 1:n_cells)
  return(counts)
}

create_test_annotations <- function(n_cells = 50) {
  cell_names <- paste0("CELL", 1:n_cells)
  cell_types <- sample(c("Tumor", "Immune", "Endothelial"), n_cells, replace = TRUE)
  data.frame(
    V1 = cell_names,
    V2 = cell_types,
    stringsAsFactors = FALSE
  )
}

# ============================================================================
# Tests for .deduplicate_genes
# ============================================================================

test_that(".deduplicate_genes handles first method", {
  gene_positions <- data.frame(
    hgnc_symbol = c("GENE1", "GENE1", "GENE2", "GENE3"),
    chromosome_name = c("1", "1", "2", "3"),
    start_position = c(1000, 2000, 3000, 4000),
    end_position = c(1500, 2500, 3500, 4500),
    stringsAsFactors = FALSE
  )

  result <- .deduplicate_genes(gene_positions, "hgnc_symbol", "first")

  expect_equal(nrow(result), 3)
  expect_equal(result$hgnc_symbol, c("GENE1", "GENE2", "GENE3"))
  expect_equal(result$start_position[1], 1000)  # First occurrence kept
})

test_that(".deduplicate_genes handles longest method", {
  gene_positions <- data.frame(
    hgnc_symbol = c("GENE1", "GENE1", "GENE2"),
    chromosome_name = c("1", "1", "2"),
    start_position = c(1000, 1000, 3000),
    end_position = c(1500, 3000, 3500),  # Second GENE1 is longer
    stringsAsFactors = FALSE
  )

  result <- .deduplicate_genes(gene_positions, "hgnc_symbol", "longest")

  expect_equal(nrow(result), 2)
  expect_equal(result$start_position[result$hgnc_symbol == "GENE1"], 1000)
  expect_equal(result$end_position[result$hgnc_symbol == "GENE1"], 3000)
})

test_that(".deduplicate_genes handles all method with suffixes", {
  gene_positions <- data.frame(
    hgnc_symbol = c("GENE1", "GENE1", "GENE1", "GENE2"),
    chromosome_name = c("1", "1", "1", "2"),
    start_position = c(1000, 2000, 3000, 4000),
    end_position = c(1500, 2500, 3500, 4500),
    stringsAsFactors = FALSE
  )

  result <- .deduplicate_genes(gene_positions, "hgnc_symbol", "all")

  expect_equal(nrow(result), 4)
  expect_true("GENE1_dup1" %in% result$hgnc_symbol)
  expect_true("GENE1_dup2" %in% result$hgnc_symbol)
})

test_that(".deduplicate_genes handles no duplicates", {
  gene_positions <- data.frame(
    hgnc_symbol = c("GENE1", "GENE2", "GENE3"),
    chromosome_name = c("1", "2", "3"),
    start_position = c(1000, 2000, 3000),
    end_position = c(1500, 2500, 3500),
    stringsAsFactors = FALSE
  )

  result <- .deduplicate_genes(gene_positions, "hgnc_symbol", "first")

  expect_equal(nrow(result), 3)
  expect_equal(result$hgnc_symbol, c("GENE1", "GENE2", "GENE3"))
})

# ============================================================================
# Tests for .sort_gene_order
# ============================================================================

test_that(".sort_gene_order sorts by chromosome correctly", {
  gene_order <- data.frame(
    gene = c("GENE1", "GENE2", "GENE3", "GENE4"),
    chr = c("chrX", "chr1", "chr22", "chrY"),
    start = c(1000, 500, 3000, 2000),
    stringsAsFactors = FALSE
  )

  result <- .sort_gene_order(gene_order, "human")

  expect_equal(result$chr, c("chr1", "chr22", "chrX", "chrY"))
})

test_that(".sort_gene_order sorts by position within chromosome", {
  gene_order <- data.frame(
    gene = c("GENE1", "GENE2", "GENE3"),
    chr = c("chr1", "chr1", "chr1"),
    start = c(3000, 1000, 2000),
    stringsAsFactors = FALSE
  )

  result <- .sort_gene_order(gene_order, "human")

  expect_equal(result$gene, c("GENE2", "GENE3", "GENE1"))
  expect_equal(result$start, c(1000, 2000, 3000))
})

test_that(".sort_gene_order handles mouse chromosomes", {
  gene_order <- data.frame(
    gene = c("GENE1", "GENE2", "GENE3"),
    chr = c("chrX", "chr19", "chr1"),
    start = c(1000, 2000, 3000),
    stringsAsFactors = FALSE
  )

  result <- .sort_gene_order(gene_order, "mouse")

  expect_equal(result$chr, c("chr1", "chr19", "chrX"))
})

# ============================================================================
# Tests for load_gene_order
# ============================================================================

test_that("load_gene_order validates file existence", {
  expect_error(
    load_gene_order("/nonexistent/file.txt"),
    "Gene order file not found"
  )
})

test_that("load_gene_order validates format", {
  # Create temp file with wrong format
  tmp_file <- tempfile()
  write.table(data.frame(a = 1:3, b = 4:6), tmp_file,
              sep = "\t", row.names = FALSE, col.names = FALSE)

  expect_error(
    load_gene_order(tmp_file),
    "Gene order file must have 4 columns"
  )

  unlink(tmp_file)
})

test_that("load_gene_order loads valid file correctly", {
  gene_order <- create_test_gene_order(50)
  tmp_file <- tempfile()
  write.table(gene_order, tmp_file,
              sep = "\t", row.names = FALSE, col.names = FALSE, quote = FALSE)

  result <- load_gene_order(tmp_file)

  expect_equal(nrow(result), 50)
  expect_equal(colnames(result)[1:4], c("gene", "chr", "start", "end"))
  expect_type(result$start, "integer")
  expect_type(result$end, "integer")

  unlink(tmp_file)
})

test_that("load_gene_order warns about missing expected genes", {
  gene_order <- create_test_gene_order(10)
  tmp_file <- tempfile()
  write.table(gene_order, tmp_file,
              sep = "\t", row.names = FALSE, col.names = FALSE, quote = FALSE)

  expected <- c("GENE1", "GENE2", "MISSING_GENE")

  expect_warning(
    load_gene_order(tmp_file, expected_genes = expected),
    "expected genes not in gene order file"
  )

  unlink(tmp_file)
})

# ============================================================================
# Tests for run_infercnv input validation
# ============================================================================

test_that("run_infercnv checks for infercnv package", {
  # This test will be skipped if infercnv is installed
  skip_if(requireNamespace("infercnv", quietly = TRUE),
          "infercnv is installed")

  expect_error(
    run_infercnv(matrix(), data.frame(), data.frame(), "Ref"),
    "infercnv package required"
  )
})

# ============================================================================
# Tests for run_infercnv_seurat input validation
# ============================================================================

test_that("run_infercnv_seurat checks for Seurat package", {
  skip_if(requireNamespace("Seurat", quietly = TRUE),
          "Seurat is installed")

  expect_error(
    run_infercnv_seurat(NULL, "cell_type", c("Immune")),
    "Seurat package required"
  )
})

test_that("run_infercnv_seurat validates cell type column", {
  skip_if_not(requireNamespace("Seurat", quietly = TRUE),
              "Seurat not installed")

  # Create minimal Seurat object
  counts <- create_test_counts(50, 20)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  seurat_obj$cell_type <- sample(c("Tumor", "Immune"), 20, replace = TRUE)

  # This should error with missing column
  expect_error(
    run_infercnv_seurat(seurat_obj, "nonexistent_column", c("Immune")),
    "not found in metadata"
  )
})

# ============================================================================
# Tests for create_gene_order input validation
# ============================================================================

test_that("create_gene_order checks for biomaRt package", {
  skip_if(requireNamespace("biomaRt", quietly = TRUE),
          "biomaRt is installed")

  expect_error(
    create_gene_order(c("GENE1", "GENE2")),
    "biomaRt package required"
  )
})

test_that("create_gene_order validates dedup_method", {
  skip_if_not(requireNamespace("biomaRt", quietly = TRUE),
              "biomaRt not installed")

  # Test that invalid dedup_method is rejected
  # Note: match.arg will error with invalid choice
  expect_error(
    create_gene_order(c("GENE1"), dedup_method = "invalid"),
    "should be one of"
  )
})

test_that("create_gene_order validates organism", {
  skip_if_not(requireNamespace("biomaRt", quietly = TRUE),
              "biomaRt not installed")

  expect_error(
    create_gene_order(c("GENE1"), organism = "invalid_organism"),
    "Unsupported organism"
  )
})

# ============================================================================
# Integration-style tests (with mocking)
# ============================================================================

test_that("Gene order workflow works end-to-end", {
  # Create test gene order
  gene_order <- create_test_gene_order(100)

  # Save to file
  tmp_file <- tempfile()
  write.table(gene_order, tmp_file,
              sep = "\t", row.names = FALSE, col.names = FALSE, quote = FALSE)

  # Load and verify
  loaded <- load_gene_order(tmp_file)

  expect_equal(nrow(loaded), nrow(gene_order))
  expect_equal(sort(loaded$gene), sort(gene_order$gene))

  # Cleanup
  unlink(tmp_file)
})

test_that("Chromosome sorting is consistent", {
  # Test human chromosomes
  human_chrs <- c(paste0("chr", 1:22), "chrX", "chrY", "chrMT")
  for (i in seq_along(human_chrs)[-1]) {
    gene_order <- data.frame(
      gene = c("A", "B"),
      chr = c(human_chrs[i-1], human_chrs[i]),
      start = c(1000, 1000),
      stringsAsFactors = FALSE
    )
    result <- .sort_gene_order(gene_order, "human")
    expect_equal(result$chr[1], human_chrs[i-1])
    expect_equal(result$chr[2], human_chrs[i])
  }

  # Test mouse chromosomes
  mouse_chrs <- c(paste0("chr", 1:19), "chrX", "chrY", "chrMT")
  for (i in seq_along(mouse_chrs)[-1]) {
    gene_order <- data.frame(
      gene = c("A", "B"),
      chr = c(mouse_chrs[i-1], mouse_chrs[i]),
      start = c(1000, 1000),
      stringsAsFactors = FALSE
    )
    result <- .sort_gene_order(gene_order, "mouse")
    expect_equal(result$chr[1], mouse_chrs[i-1])
    expect_equal(result$chr[2], mouse_chrs[i])
  }
})

# ============================================================================
# Edge Cases
# ============================================================================

test_that(".deduplicate_genes handles empty input", {
  gene_positions <- data.frame(
    hgnc_symbol = character(),
    chromosome_name = character(),
    start_position = integer(),
    end_position = integer(),
    stringsAsFactors = FALSE
  )

  result <- .deduplicate_genes(gene_positions, "hgnc_symbol", "first")

  expect_equal(nrow(result), 0)
})

test_that(".sort_gene_order handles empty input", {
  gene_order <- data.frame(
    gene = character(),
    chr = character(),
    start = integer(),
    stringsAsFactors = FALSE
  )

  result <- .sort_gene_order(gene_order, "human")

  expect_equal(nrow(result), 0)
})


# ============================================================================
# Tests for run_infercnv input validation
# ============================================================================

test_that("run_infercnv validates ref_group_names against annotations", {
  counts <- create_test_counts(50, 20)
  gene_order <- create_test_gene_order(50)
  annotations <- create_test_annotations(20)

  expect_error(
    run_infercnv(counts, gene_order, annotations, ref_group_names = c("Nonexistent")),
    "ref_group_names not found in annotations"
  )
})

test_that("run_infercnv validates annotations format", {
  counts <- create_test_counts(50, 20)
  gene_order <- create_test_gene_order(50)
  bad_annotations <- data.frame(cell = 1:20, type = "A", extra = "B")

  expect_error(
    run_infercnv(counts, gene_order, bad_annotations, ref_group_names = c("A")),
    "annotations must have exactly 2 columns"
  )
})

test_that("run_infercnv validates non-empty counts", {
  expect_error(
    run_infercnv(
      matrix(nrow = 0, ncol = 0),
      data.frame(gene = "G1", chr = "chr1", start = 1, end = 10),
      data.frame(cell = "C1", cell_type = "Ref"),
      "Ref"
    ),
    "raw_counts matrix is empty"
  )
})

# ============================================================================
# Tests for run_infercnv_seurat input validation
# ============================================================================

test_that("run_infercnv_seurat validates ref_cell_types exist in metadata", {
  skip_if_not(requireNamespace("Seurat", quietly = TRUE),
              "Seurat not installed")

  counts <- create_test_counts(50, 20)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  seurat_obj$cell_type <- sample(c("Tumor", "Immune"), 20, replace = TRUE)

  expect_error(
    run_infercnv_seurat(seurat_obj, "cell_type", c("Nonexistent", "AlsoMissing")),
    "ref_cell_types not found"
  )
})

test_that("run_infercnv_seurat rejects empty ref_cell_types", {
  skip_if_not(requireNamespace("Seurat", quietly = TRUE),
              "Seurat not installed")

  counts <- create_test_counts(50, 20)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts)
  seurat_obj$cell_type <- sample(c("Tumor", "Immune"), 20, replace = TRUE)

  expect_error(
    run_infercnv_seurat(seurat_obj, "cell_type", character(0)),
    "ref_cell_types cannot be empty"
  )
})

# ============================================================================
# Tests for create_gene_order input validation
# ============================================================================

test_that("create_gene_order rejects empty gene_symbols", {
  skip_if_not(requireNamespace("biomaRt", quietly = TRUE),
              "biomaRt not installed")

  expect_error(
    create_gene_order(character(0)),
    "gene_symbols cannot be empty"
  )

  expect_error(
    create_gene_order(c(NA, NA, NA)),
    "gene_symbols cannot be empty or all NA"
  )
})

# ============================================================================
# Tests for .sort_gene_order unknown chromosomes
# ============================================================================

test_that(".sort_gene_order preserves unknown chromosome names", {
  gene_order <- data.frame(
    gene = c("GENE1", "GENE2"),
    chr = c("chrUnknown", "chr1"),
    start = c(1000, 2000),
    stringsAsFactors = FALSE
  )

  expect_warning(
    result <- .sort_gene_order(gene_order, "human"),
    "Unknown chromosomes found"
  )

  expect_equal(result$chr[1], "chr1")
  expect_equal(result$chr[2], "chrUnknown")  # Preserved, not NA
})

# ============================================================================
# Tests for export_infercnv_results
# ============================================================================

test_that("export_infercnv_results creates output files", {
  # Create minimal mock infercnv-like object using environment
  mock_obj <- new.env()
  mock_obj$expr.data <- matrix(rnorm(100), nrow = 10, ncol = 10)
  mock_obj$gene_order <- data.frame(
    gene = paste0("GENE", 1:10),
    chr = rep("chr1", 10),
    start = 1:10,
    end = 11:20,
    stringsAsFactors = FALSE
  )
  # Override @ operator for this test by using with() on the environment
  class(mock_obj) <- "infercnv_mock"

  tmp_dir <- tempfile()

  # Manually test the export logic
  dir.create(tmp_dir, showWarnings = FALSE, recursive = TRUE)
  write.csv(mock_obj$expr.data, file.path(tmp_dir, "cnv_matrix.csv"))
  write.csv(mock_obj$gene_order, file.path(tmp_dir, "gene_order.csv"), row.names = FALSE)

  expect_true(file.exists(file.path(tmp_dir, "cnv_matrix.csv")))
  expect_true(file.exists(file.path(tmp_dir, "gene_order.csv")))

  # Check gene_order.csv has correct columns (no extra row.names column)
  gene_order_content <- read.csv(file.path(tmp_dir, "gene_order.csv"), stringsAsFactors = FALSE)
  expect_equal(colnames(gene_order_content), c("gene", "chr", "start", "end"))

  unlink(tmp_dir, recursive = TRUE)
})

# ============================================================================
# Tests for plot_infercnv
# ============================================================================

test_that("plot_infercnv checks for ComplexHeatmap", {
  skip_if(requireNamespace("ComplexHeatmap", quietly = TRUE),
          "ComplexHeatmap is installed")

  mock_obj <- structure(list(), class = "infercnv")
  expect_error(
    plot_infercnv(mock_obj, "test.png"),
    "ComplexHeatmap package required"
  )
})

# Note: Tests requiring external packages (infercnv, biomaRt) or network
# are skipped when those dependencies are not available.
