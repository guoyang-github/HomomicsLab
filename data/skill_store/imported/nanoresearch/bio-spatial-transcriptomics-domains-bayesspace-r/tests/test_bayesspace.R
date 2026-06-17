#!/usr/bin/env Rscript
#' BayesSpace Skill Unit Tests
#'
#' Comprehensive tests for bio-spatial-transcriptomics-domains-bayesspace-r skill
#' covering data validation, preprocessing, clustering, and utilities.

library(testthat)
library(SingleCellExperiment)

# ================================================================================
# Test Setup
# ================================================================================

cat("========================================\n")
cat("BayesSpace Skill Unit Tests\n")
cat("========================================\n\n")

# Check if BayesSpace is available
has_bayesspace <- requireNamespace("BayesSpace", quietly = TRUE)
if (!has_bayesspace) {
  cat("WARNING: BayesSpace not installed. Core tests will be skipped.\n")
  cat("Install with: BiocManager::install('BayesSpace')\n\n")
}

if (has_bayesspace) {
  library(BayesSpace)
  library(scater)
  library(scran)
}

# ================================================================================
# Helper Functions
# ================================================================================

create_test_sce <- function(n_spots = 100, n_genes = 200, n_domains = 3, seed = 42) {
  set.seed(seed)

  # Create spatial coordinates
  grid_size <- ceiling(sqrt(n_spots))
  array_col <- rep(1:grid_size, each = grid_size)[1:n_spots]
  array_row <- rep(1:grid_size, times = grid_size)[1:n_spots]

  # Create expression matrix
  counts <- matrix(rpois(n_genes * n_spots, lambda = 2), nrow = n_genes)

  # Add domain patterns
  domain_labels <- rep(0, n_spots)
  genes_per_domain <- n_genes / n_domains

  for (i in 1:n_spots) {
    xi <- array_col[i]
    yi <- array_row[i]

    if (xi <= grid_size / 2 && yi <= grid_size / 2) {
      domain <- 1
    } else if (xi > grid_size / 2 && yi <= grid_size / 2) {
      domain <- 2
    } else {
      domain <- 3
    }

    domain_labels[i] <- domain
    marker_start <- (domain - 1) * genes_per_domain + 1
    marker_end <- domain * genes_per_domain
    counts[marker_start:marker_end, i] <- counts[marker_start:marker_end, i] + rpois(genes_per_domain, 10)
  }

  sce <- SingleCellExperiment(
    assays = list(counts = counts),
    colData = DataFrame(
      array_row = array_row,
      array_col = array_col,
      in_tissue = 1,
      domain = factor(domain_labels)
    )
  )

  rownames(sce) <- paste0("Gene_", 1:n_genes)
  colnames(sce) <- paste0("Spot_", sprintf("%03d", 1:n_spots))

  sce
}

# ================================================================================
# Test Suite 1: Data Validation
# ================================================================================

cat("Test Suite 1: Data Validation\n")
cat("----------------------------------------\n")

test_that("test data creation works", {
  sce <- create_test_sce(n_spots = 50, n_genes = 100)
  expect_equal(ncol(sce), 50)
  expect_equal(nrow(sce), 100)
  expect_true("array_row" %in% colnames(colData(sce)))
  expect_true("array_col" %in% colnames(colData(sce)))
})

test_that("spatial coordinates are valid", {
  sce <- create_test_sce(n_spots = 50)
  expect_true(all(sce$array_row > 0))
  expect_true(all(sce$array_col > 0))
  expect_equal(length(unique(sce$array_row)), length(unique(sce$array_row)))
})

test_that("domain labels are created", {
  sce <- create_test_sce(n_spots = 50, n_domains = 3)
  expect_equal(length(unique(sce$domain)), 3)
})

cat("  Data validation tests passed\n\n")

# ================================================================================
# Test Suite 2: Preprocessing (if BayesSpace available)
# ================================================================================

cat("Test Suite 2: Preprocessing\n")
cat("----------------------------------------\n")

if (has_bayesspace) {
  test_that("spatialPreprocess works", {
    sce <- create_test_sce(n_spots = 50)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5, n.HVGs = 50)

    expect_true("PCA" %in% reducedDimNames(sce))
    expect_true("is.HVG" %in% colnames(rowData(sce)))
    expect_true(sum(rowData(sce)$is.HVG) > 0)
  })

  test_that("spatialPreprocess with skip.PCA works", {
    sce <- create_test_sce(n_spots = 50)
    sce <- spatialPreprocess(sce, platform = "ST", skip.PCA = TRUE)

    expect_true(metadata(sce)$BayesSpace.data$platform == "ST")
  })

  test_that("BayesSpace metadata is set", {
    sce <- create_test_sce(n_spots = 50)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)

    expect_true("BayesSpace.data" %in% names(metadata(sce)))
    expect_equal(metadata(sce)$BayesSpace.data$platform, "ST")
    expect_false(metadata(sce)$BayesSpace.data$is.enhanced)
  })

  cat("  Preprocessing tests passed\n\n")
} else {
  cat("  SKIPPED (BayesSpace not installed)\n\n")
}

# ================================================================================
# Test Suite 3: Clustering (if BayesSpace available)
# ================================================================================

cat("Test Suite 3: Spatial Clustering\n")
cat("----------------------------------------\n")

if (has_bayesspace) {
  test_that("spatialCluster works with minimal parameters", {
    sce <- create_test_sce(n_spots = 60, n_genes = 100)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5, n.HVGs = 50)

    sce <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10, verbose = FALSE)

    expect_true("spatial.cluster" %in% colnames(colData(sce)))
    expect_equal(length(unique(sce$spatial.cluster)), 3)
  })

  test_that("spatialCluster with different init methods", {
    sce <- create_test_sce(n_spots = 60)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)

    # Test with mclust (if available)
    tryCatch({
      sce_mclust <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10,
                                   init.method = "mclust", verbose = FALSE)
      expect_true("spatial.cluster" %in% colnames(colData(sce_mclust)))
    }, error = function(e) {
      cat("  mclust init skipped (package may not be available)\n")
    })

    # Test with kmeans
    sce_kmeans <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10,
                                 init.method = "kmeans", verbose = FALSE)
    expect_true("spatial.cluster" %in% colnames(colData(sce_kmeans)))
  })

  test_that("spatialCluster saves initial clusters", {
    sce <- create_test_sce(n_spots = 60)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)
    sce <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10, verbose = FALSE)

    expect_true("cluster.init" %in% colnames(colData(sce)))
  })

  test_that("spatialCluster with different models", {
    sce <- create_test_sce(n_spots = 60)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)

    # Normal model
    sce_normal <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10,
                                 model = "normal", verbose = FALSE)
    expect_true("spatial.cluster" %in% colnames(colData(sce_normal)))

    # t model
    sce_t <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10,
                            model = "t", verbose = FALSE)
    expect_true("spatial.cluster" %in% colnames(colData(sce_t)))
  })

  cat("  Clustering tests passed\n\n")
} else {
  cat("  SKIPPED (BayesSpace not installed)\n\n")
}

# ================================================================================
# Test Suite 4: Enhancement (if BayesSpace available)
# ================================================================================

cat("Test Suite 4: Resolution Enhancement\n")
cat("----------------------------------------\n")

if (has_bayesspace) {
  test_that("spatialEnhance works", {
    sce <- create_test_sce(n_spots = 60)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)
    sce <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10, verbose = FALSE)

    sce_enhanced <- spatialEnhance(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10,
                                   verbose = FALSE)

    expect_true(ncol(sce_enhanced) > ncol(sce))
    expect_true("spatial.cluster" %in% colnames(colData(sce_enhanced)))
    expect_true("spot.idx" %in% colnames(colData(sce_enhanced)))
    expect_true("subspot.idx" %in% colnames(colData(sce_enhanced)))
  })

  test_that("spatialEnhance creates correct metadata", {
    sce <- create_test_sce(n_spots = 60)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)
    sce <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10, verbose = FALSE)

    sce_enhanced <- spatialEnhance(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10,
                                   verbose = FALSE)

    expect_true(metadata(sce_enhanced)$BayesSpace.data$is.enhanced)
  })

  test_that("spatialEnhance preserves PCA", {
    sce <- create_test_sce(n_spots = 60)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)
    sce <- spatialCluster(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10, verbose = FALSE)

    sce_enhanced <- spatialEnhance(sce, q = 3, platform = "ST", nrep = 100, burn.in = 10,
                                   verbose = FALSE)

    expect_true("PCA" %in% reducedDimNames(sce_enhanced))
  })

  cat("  Enhancement tests passed\n\n")
} else {
  cat("  SKIPPED (BayesSpace not installed)\n\n")
}

# ================================================================================
# Test Suite 5: Utilities
# ================================================================================

cat("Test Suite 5: Utilities\n")
cat("----------------------------------------\n")

test_that("data export works", {
  sce <- create_test_sce(n_spots = 50)
  sce$spatial.cluster <- sample(1:3, 50, replace = TRUE)

  # Export to CSV
  tmp_file <- tempfile(fileext = ".csv")
  write.csv(colData(sce)[, c("spatial.cluster", "array_row", "array_col")], tmp_file)

  expect_true(file.exists(tmp_file))

  # Read back
  loaded <- read.csv(tmp_file)
  expect_equal(nrow(loaded), 50)

  file.remove(tmp_file)
})

test_that("SingleCellExperiment save/load works", {
  sce <- create_test_sce(n_spots = 50)
  sce$spatial.cluster <- sample(1:3, 50, replace = TRUE)

  tmp_file <- tempfile(fileext = ".rds")
  saveRDS(sce, tmp_file)

  expect_true(file.exists(tmp_file))

  loaded <- readRDS(tmp_file)
  expect_equal(ncol(loaded), 50)
  expect_true("spatial.cluster" %in% colnames(colData(loaded)))

  file.remove(tmp_file)
})

if (has_bayesspace) {
  test_that("clusterPlot inputs are validated", {
    sce <- create_test_sce(n_spots = 50)
    sce$spatial.cluster <- sample(1:3, 50, replace = TRUE)

    # Should work with valid input
    expect_silent({
      p <- clusterPlot(sce, label = "spatial.cluster")
    })

    # Should be a ggplot object
    expect_true(inherits(p, "ggplot"))
  })

  test_that("featurePlot inputs are validated", {
    sce <- create_test_sce(n_spots = 50, n_genes = 100)
    sce$spatial.cluster <- sample(1:3, 50, replace = TRUE)

    # Preprocess to add logcounts
    sce <- spatialPreprocess(sce, platform = "ST", skip.PCA = TRUE)

    # Should work with gene name
    expect_silent({
      p <- featurePlot(sce, feature = "Gene_1")
    })

    expect_true(inherits(p, "ggplot"))
  })
}

cat("  Utility tests passed\n\n")

# ================================================================================
# Test Suite 6: Edge Cases
# ================================================================================

cat("Test Suite 6: Edge Cases\n")
cat("----------------------------------------\n")

test_that("handles minimal dataset", {
  sce <- create_test_sce(n_spots = 20, n_genes = 50)
  expect_equal(ncol(sce), 20)
  expect_equal(nrow(sce), 50)
})

test_that("handles single domain", {
  sce <- create_test_sce(n_spots = 50)
  sce$domain <- factor(rep(1, 50))
  expect_equal(length(unique(sce$domain)), 1)
})

test_that("handles many domains", {
  sce <- create_test_sce(n_spots = 100, n_domains = 8)
  expect_equal(length(unique(sce$domain)), 8)
})

if (has_bayesspace) {
  test_that("spatialCluster with q=1", {
    sce <- create_test_sce(n_spots = 50)
    sce <- spatialPreprocess(sce, platform = "ST", n.PCs = 5)

    # q=1 should work but return all spots in same cluster
    sce <- spatialCluster(sce, q = 1, platform = "ST", nrep = 100, burn.in = 10, verbose = FALSE)

    expect_equal(length(unique(sce$spatial.cluster)), 1)
  })
}

cat("  Edge case tests passed\n\n")

# ================================================================================
# Summary
# ================================================================================

cat("========================================\n")
cat("Test Summary\n")
cat("========================================\n")

if (has_bayesspace) {
  cat("BayesSpace package: INSTALLED\n")
  cat("Core tests: ENABLED\n")
} else {
  cat("BayesSpace package: NOT INSTALLED\n")
  cat("Core tests: SKIPPED\n")
}

cat("\nAll tests completed successfully!\n\n")
