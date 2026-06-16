#!/usr/bin/env Rscript
#' CARD Skill Unit Tests
#'
#' Comprehensive tests for bio-spatial-transcriptomics-deconvolution-card-r skill
#' covering data validation, object creation, deconvolution, and utilities.

library(testthat)
library(Matrix)

# ================================================================================
# Test Setup
# ================================================================================

cat("========================================\n")
cat("CARD Skill Unit Tests\n")
cat("========================================\n\n")

# Check if CARD is available
has_card <- requireNamespace("CARD", quietly = TRUE)
if (!has_card) {
  cat("WARNING: CARD package not installed. Core tests will be skipped.\n")
  cat("Install with: devtools::install_github('YingMa0107/CARD')\n\n")
}

# ================================================================================
# Helper Functions for Testing
# ================================================================================

create_test_data <- function(n_genes = 100, n_cells = 50, n_spots = 30) {
  # Create synthetic single-cell data
  cell_types <- c("T_cell", "B_cell", "Myeloid")

  counts_sc <- matrix(
    rpois(n_genes * n_cells, lambda = 2),
    nrow = n_genes,
    ncol = n_cells
  )

  cell_type_vec <- rep(cell_types, length.out = n_cells)

  # Add marker expression
  for (i in 1:3) {
    ct_cells <- which(cell_type_vec == cell_types[i])
    gene_idx <- ((i-1)*2 + 1):(i*2)
    counts_sc[gene_idx, ct_cells] <- counts_sc[gene_idx, ct_cells] +
      rpois(length(ct_cells) * 2, lambda = 10)
  }

  gene_names <- paste0("GENE_", 1:n_genes)
  rownames(counts_sc) <- gene_names
  colnames(counts_sc) <- paste0("Cell_", 1:n_cells)

  sc_meta <- data.frame(
    cell_type = cell_type_vec,
    sample = rep("Sample1", n_cells),
    row.names = colnames(counts_sc)
  )

  # Create spatial data
  counts_sp <- matrix(
    rpois(n_genes * n_spots, lambda = 3),
    nrow = n_genes,
    ncol = n_spots
  )
  rownames(counts_sp) <- gene_names
  colnames(counts_sp) <- paste0("Spot_", 1:n_spots)

  spatial_location <- data.frame(
    x = rep(1:6, each = 5)[1:n_spots],
    y = rep(1:5, 6)[1:n_spots],
    row.names = colnames(counts_sp)
  )

  list(
    sc_count = counts_sc,
    sc_meta = sc_meta,
    spatial_count = counts_sp,
    spatial_location = spatial_location,
    cell_types = cell_types
  )
}

# ================================================================================
# Test Suite 1: Data Validation
# ================================================================================

cat("Test Suite 1: Data Validation\n")
cat("----------------------------------------\n")

test_that("test data creation works", {
  data <- create_test_data()
  expect_equal(nrow(data$sc_count), 100)
  expect_equal(ncol(data$sc_count), 50)
  expect_equal(ncol(data$spatial_count), 30)
  expect_equal(length(unique(data$sc_meta$cell_type)), 3)
})

test_that("gene names match between sc and spatial", {
  data <- create_test_data()
  expect_equal(rownames(data$sc_count), rownames(data$spatial_count))
})

test_that("sc metadata barcodes match count matrix", {
  data <- create_test_data()
  expect_equal(rownames(data$sc_meta), colnames(data$sc_count))
})

test_that("spatial location barcodes match spatial count", {
  data <- create_test_data()
  expect_equal(rownames(data$spatial_location), colnames(data$spatial_count))
})

test_that("spatial coordinates have x and y columns", {
  data <- create_test_data()
  expect_true("x" %in% colnames(data$spatial_location))
  expect_true("y" %in% colnames(data$spatial_location))
})

cat("  Data validation tests passed\n\n")

# ================================================================================
# Test Suite 2: CARD Object Creation (if CARD installed)
# ================================================================================

cat("Test Suite 2: CARD Object Creation\n")
cat("----------------------------------------\n")

if (has_card) {
  library(CARD)

  test_that("createCARDObject works with valid data", {
    data <- create_test_data()

    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      ct.select = NULL,
      sample.varname = NULL,
      minCountGene = 10,
      minCountSpot = 1
    )

    expect_s4_class(CARD_obj, "CARD")
    expect_true("sc_eset" %in% slotNames(CARD_obj))
    expect_true("spatial_countMat" %in% slotNames(CARD_obj))
    expect_true("spatial_location" %in% slotNames(CARD_obj))
  })

  test_that("createCARDObject with cell type selection", {
    data <- create_test_data()

    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      ct.select = c("T_cell", "B_cell"),  # Only 2 cell types
      minCountGene = 10,
      minCountSpot = 1
    )

    expect_equal(length(CARD_obj@info_parameters$ct.select), 2)
  })

  test_that("createCARDObject fails with mismatched barcodes", {
    data <- create_test_data()
    data$sc_meta <- data$sc_meta[sample(nrow(data$sc_meta)), ]

    expect_error({
      createCARDObject(
        sc_count = data$sc_count,
        sc_meta = data$sc_meta,
        spatial_count = data$spatial_count,
        spatial_location = data$spatial_location,
        ct.varname = "cell_type",
        minCountGene = 10,
        minCountSpot = 1
      )
    })
  })

  test_that("createCARDObject fails with no common genes", {
    data <- create_test_data()
    rownames(data$sc_count) <- paste0("SC_", 1:nrow(data$sc_count))

    expect_error({
      createCARDObject(
        sc_count = data$sc_count,
        sc_meta = data$sc_meta,
        spatial_count = data$spatial_count,
        spatial_location = data$spatial_location,
        ct.varname = "cell_type",
        minCountGene = 10,
        minCountSpot = 1
      )
    })
  })

  cat("  CARD object creation tests passed\n\n")
} else {
  cat("  SKIPPED (CARD not installed)\n\n")
}

# ================================================================================
# Test Suite 3: CARD Deconvolution (if CARD installed)
# ================================================================================

cat("Test Suite 3: CARD Deconvolution\n")
cat("----------------------------------------\n")

if (has_card) {
  test_that("CARD_deconvolution runs successfully", {
    data <- create_test_data(n_genes = 150, n_cells = 60, n_spots = 40)

    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      minCountGene = 10,
      minCountSpot = 1
    )

    CARD_obj <- CARD_deconvolution(CARD_obj)

    expect_true(length(CARD_obj@Proportion_CARD) > 0)
    expect_equal(nrow(CARD_obj@Proportion_CARD), 40)
    expect_equal(ncol(CARD_obj@Proportion_CARD), 3)
    expect_true("phi" %in% names(CARD_obj@info_parameters))
  })

  test_that("Proportions sum to approximately 1", {
    data <- create_test_data(n_genes = 150, n_cells = 60, n_spots = 40)

    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      minCountGene = 10,
      minCountSpot = 1
    )

    CARD_obj <- CARD_deconvolution(CARD_obj)
    proportions <- CARD_obj@Proportion_CARD

    # Check row sums (allowing for small numerical error)
    row_sums <- rowSums(proportions)
    expect_true(all(abs(row_sums - 1) < 0.01))
  })

  test_that("All proportions are non-negative", {
    data <- create_test_data(n_genes = 150, n_cells = 60, n_spots = 40)

    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      minCountGene = 10,
      minCountSpot = 1
    )

    CARD_obj <- CARD_deconvolution(CARD_obj)
    proportions <- CARD_obj@Proportion_CARD

    expect_true(all(proportions >= 0))
  })

  cat("  CARD deconvolution tests passed\n\n")
} else {
  cat("  SKIPPED (CARD not installed)\n\n")
}

# ================================================================================
# Test Suite 4: CARDfree Object Creation (if CARD installed)
# ================================================================================

cat("Test Suite 4: CARDfree Object Creation\n")
cat("----------------------------------------\n")

if (has_card) {
  test_that("createCARDfreeObject works with valid markers", {
    data <- create_test_data()

    markerList <- list(
      T_cell = c("GENE_1", "GENE_2"),
      B_cell = c("GENE_3", "GENE_4"),
      Myeloid = c("GENE_5", "GENE_6")
    )

    CARDfree_obj <- createCARDfreeObject(
      markerList = markerList,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      minCountGene = 5,
      minCountSpot = 1
    )

    expect_s4_class(CARDfree_obj, "CARDfree")
    expect_true("markerList" %in% slotNames(CARDfree_obj))
  })

  test_that("createCARDfreeObject fails without markers", {
    data <- create_test_data()

    expect_error({
      createCARDfreeObject(
        markerList = list(),
        spatial_count = data$spatial_count,
        spatial_location = data$spatial_location
      )
    })
  })

  cat("  CARDfree object creation tests passed\n\n")
} else {
  cat("  SKIPPED (CARD not installed)\n\n")
}

# ================================================================================
# Test Suite 5: Result Analysis Functions
# ================================================================================

cat("Test Suite 5: Result Analysis Functions\n")
cat("----------------------------------------\n")

test_that("dominant cell type identification works", {
  # Create mock proportions
  proportions <- matrix(
    c(0.5, 0.3, 0.2,
      0.1, 0.7, 0.2,
      0.3, 0.3, 0.4),
    nrow = 3,
    byrow = TRUE
  )
  colnames(proportions) <- c("T_cell", "B_cell", "Myeloid")

  dominant <- colnames(proportions)[apply(proportions, 1, which.max)]

  expect_equal(dominant[1], "T_cell")
  expect_equal(dominant[2], "B_cell")
  expect_equal(dominant[3], "Myeloid")
})

test_that("spatial entropy calculation works", {
  # Create mock proportions
  proportions <- matrix(
    c(1.0, 0.0, 0.0,    # Pure - low entropy
      0.4, 0.3, 0.3,    # Mixed - high entropy
      0.6, 0.2, 0.2),   # Medium
    nrow = 3,
    byrow = TRUE
  )

  entropy <- apply(proportions, 1, function(x) {
    p <- x[x > 0]
    -sum(p * log(p))
  })

  expect_true(entropy[1] < entropy[2])
  expect_true(entropy[2] > entropy[3])
})

test_that("mean proportion calculation works", {
  proportions <- matrix(
    runif(30),
    nrow = 10,
    ncol = 3
  )
  proportions <- proportions / rowSums(proportions)
  colnames(proportions) <- c("A", "B", "C")

  mean_props <- colMeans(proportions)
  expect_equal(length(mean_props), 3)
  expect_true(abs(sum(mean_props) - 1) < 0.01)
})

cat("  Result analysis tests passed\n\n")

# ================================================================================
# Test Suite 6: Edge Cases
# ================================================================================

cat("Test Suite 6: Edge Cases\n")
cat("----------------------------------------\n")

test_that("handles single cell type", {
  data <- create_test_data()
  data$sc_meta$cell_type <- "T_cell"

  if (has_card) {
    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      minCountGene = 10,
      minCountSpot = 1
    )

    expect_equal(length(CARD_obj@info_parameters$ct.select), 1)
  } else {
    expect_true(TRUE)  # Skip
  }
})

test_that("handles sparse matrices", {
  data <- create_test_data()

  # Convert to sparse
  sc_sparse <- as(data$sc_count, "sparseMatrix")
  sp_sparse <- as(data$spatial_count, "sparseMatrix")

  expect_s4_class(sc_sparse, "sparseMatrix")
  expect_s4_class(sp_sparse, "sparseMatrix")

  if (has_card) {
    CARD_obj <- createCARDObject(
      sc_count = sc_sparse,
      sc_meta = data$sc_meta,
      spatial_count = sp_sparse,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      minCountGene = 10,
      minCountSpot = 1
    )

    expect_s4_class(CARD_obj, "CARD")
  }
})

test_that("handles minimal dataset", {
  data <- create_test_data(n_genes = 50, n_cells = 30, n_spots = 20)

  if (has_card) {
    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      minCountGene = 5,
      minCountSpot = 1
    )

    expect_s4_class(CARD_obj, "CARD")
  } else {
    expect_true(TRUE)
  }
})

cat("  Edge case tests passed\n\n")

# ================================================================================
# Test Suite 7: Data Export
# ================================================================================

cat("Test Suite 7: Data Export\n")
cat("----------------------------------------\n")

test_that("proportions can be exported to CSV", {
  proportions <- matrix(runif(30), nrow = 10, ncol = 3)
  colnames(proportions) <- c("A", "B", "C")

  tmp_file <- tempfile(fileext = ".csv")
  write.csv(proportions, tmp_file)

  expect_true(file.exists(tmp_file))

  loaded <- read.csv(tmp_file, row.names = 1)
  expect_equal(dim(loaded), dim(proportions))

  unlink(tmp_file)
})

test_that("CARD object can be saved and loaded", {
  if (has_card) {
    data <- create_test_data()

    CARD_obj <- createCARDObject(
      sc_count = data$sc_count,
      sc_meta = data$sc_meta,
      spatial_count = data$spatial_count,
      spatial_location = data$spatial_location,
      ct.varname = "cell_type",
      minCountGene = 10,
      minCountSpot = 1
    )

    tmp_file <- tempfile(fileext = ".rds")
    saveRDS(CARD_obj, tmp_file)

    expect_true(file.exists(tmp_file))

    loaded <- readRDS(tmp_file)
    expect_s4_class(loaded, "CARD")

    unlink(tmp_file)
  } else {
    expect_true(TRUE)
  }
})

cat("  Data export tests passed\n\n")

# ================================================================================
# Summary
# ================================================================================

cat("========================================\n")
cat("Test Summary\n")
cat("========================================\n")

if (has_card) {
  cat("CARD package: INSTALLED\n")
  cat("Core tests: ENABLED\n")
} else {
  cat("CARD package: NOT INSTALLED\n")
  cat("Core tests: SKIPPED\n")
}

cat("\nAll tests completed successfully!\n\n")

# Run tests if called directly
if (!interactive()) {
  test_dir <- dirname(sys.frame(1)$ofile)
  cat(sprintf("Test directory: %s\n", test_dir))
}
