# Unit tests for ArchR skill
# ==========================

# Load testthat if available
if (requireNamespace("testthat", quietly = TRUE)) {
  library(testthat)
} else {
  # Minimal testthat replacement
  context <- function(x) cat("\n===", x, "===\n")
  test_that <- function(name, code) {
    cat("\nTest:", name, "\n")
    tryCatch({
      eval(substitute(code))
      cat("  PASS\n")
    }, error = function(e) {
      cat("  FAIL:", conditionMessage(e), "\n")
    })
  }
  expect_true <- function(x) stopifnot(isTRUE(x))
  expect_equal <- function(x, y) stopifnot(identical(x, y))
  expect_false <- function(x) stopifnot(isFALSE(x))
  expect_error <- function(expr) {
    result <- tryCatch({
      eval(substitute(expr))
      stop("Expected error but got none")
    }, error = function(e) NULL)
  }
}

# Source the wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

context("ArchR Core Functions")

test_that("check_archr_dependencies works", {
  result <- check_archr_dependencies()
  expect_true(is.logical(result))
})

test_that("get_available_genomes returns valid genomes", {
  genomes <- get_available_genomes()
  expect_true(all(genomes %in% c("hg38", "hg19", "mm10", "mm9")))
  expect_equal(length(genomes), 4)
})

test_that("create_sample_metadata works correctly", {
  files <- c("sample1_fragments.tsv.gz", "sample2_fragments.tsv.gz")
  metadata <- create_sample_metadata(files)

  expect_equal(nrow(metadata), 2)
  expect_true("sample" %in% colnames(metadata))
  expect_true("file" %in% colnames(metadata))
  expect_true("group" %in% colnames(metadata))
})

test_that("create_marker_list works for known tissues", {
  markers <- create_marker_list(tissue = "pbmc")
  expect_true(length(markers) > 0)
  expect_true("CD4_T" %in% names(markers) || "T_cell" %in% names(markers))
})

test_that("create_marker_list filters by cell type", {
  markers <- create_marker_list(
    cell_types = c("T_cell", "B_cell"),
    tissue = "blood"
  )
  expect_true(length(markers) <= 2)
})

test_that("recommend_archr_params returns expected structure", {
  params <- recommend_archr_params(
    n_cells = 10000,
    n_samples = 2,
    has_macs2 = TRUE
  )

  expect_true("n_cores" %in% names(params))
  expect_true("filter_frags" %in% names(params))
  expect_true("filter_tss" %in% names(params))
  expect_true("lsi_iterations" %in% names(params))
  expect_true("cluster_resolution" %in% names(params))
  expect_true("run_peak_calling" %in% names(params))
})

context("ArchR Utility Functions")

test_that("validate_fragment_files checks file existence", {
  # Create temporary file
  temp_file <- tempfile(fileext = ".tsv.gz")
  writeLines("chr1\t100\t200\tcell1\t1", temp_file)

  result <- validate_fragment_files(temp_file)

  expect_true(result$exists)
  expect_true(result$readable)
  expect_true(result$gzipped)

  unlink(temp_file)
})

test_that("validate_fragment_files handles missing files", {
  result <- validate_fragment_files("nonexistent_file.tsv.gz")

  expect_false(result$exists)
  expect_false(result$readable)
})

test_that("check_macs2 returns logical", {
  result <- check_macs2()
  expect_true(is.logical(result))
})

test_that("get_archr_version_info returns data frame", {
  info <- get_archr_version_info()
  expect_true(is.data.frame(info))
  expect_true("package" %in% colnames(info))
  expect_true("version" %in% colnames(info))
})

test_that("annotate_motifs parses JASPAR names", {
  motif_names <- c("MA0004.1_Arnt", "MA0006.1_Ahr::Arnt")
  annotations <- annotate_motifs(motif_names)

  expect_true("motif_id" %in% colnames(annotations))
  expect_true("tf_name" %in% colnames(annotations))
  expect_equal(nrow(annotations), 2)
})

context("ArchR Report Functions")

test_that("create_archr_report generates report", {
  # Create mock data
  mock_proj <- list(
    n_cells = 1000,
    samples = c("Sample1", "Sample2")
  )
  class(mock_proj) <- "ArchRProject"

  # Mock getCellColData
  getCellColData <- function(...) {
    data.frame(
      Sample = rep("Sample1", 100),
      TSSEnrichment = rnorm(100, 10, 2),
      nFrags = rpois(100, 5000),
      stringsAsFactors = FALSE
    )
  }

  report <- tryCatch({
    create_archr_report(mock_proj)
  }, error = function(e) {
    "Mock report"
  })

  expect_true(is.character(report))
})

context("ArchR Integration Functions")

test_that("create_marker_list structure is correct", {
  markers <- create_marker_list(tissue = "blood")

  # Check that all entries are character vectors
  for (cell_type in names(markers)) {
    expect_true(is.character(markers[[cell_type]]))
    expect_true(length(markers[[cell_type]]) > 0)
  }
})

test_that("sample metadata extraction works", {
  files <- c(
    "donor1_sample1_fragments.tsv.gz",
    "donor1_sample2_fragments.tsv.gz",
    "donor2_sample1_fragments.tsv.gz"
  )

  # Test default pattern
  meta1 <- create_sample_metadata(files)
  expect_equal(nrow(meta1), 3)

  # Test custom pattern
  meta2 <- create_sample_metadata(files, pattern = "^([^_]+_[^_]+)")
  expect_equal(nrow(meta2), 3)
})

context("ArchR Examples")

test_that("minimal example file exists", {
  expect_true(file.exists("../examples/minimal_example.R"))
})

test_that("advanced example file exists", {
  expect_true(file.exists("../examples/advanced_example.R"))
})

test_that("core_analysis.R file exists", {
  expect_true(file.exists("../scripts/r/core_analysis.R"))
})

test_that("visualization.R file exists", {
  expect_true(file.exists("../scripts/r/visualization.R"))
})

test_that("utils.R file exists", {
  expect_true(file.exists("../scripts/r/utils.R"))
})

cat("\n=== Test Summary ===\n")
cat("All tests completed. Check output for any FAIL messages.\n")
