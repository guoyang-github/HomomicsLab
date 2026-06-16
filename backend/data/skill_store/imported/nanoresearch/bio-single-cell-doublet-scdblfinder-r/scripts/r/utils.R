# scDblFinder Utility Functions
# ==============================
#
# Utility functions for scDblFinder doublet detection

#' Create test data for scDblFinder
#'
#' Generate synthetic test data for testing scDblFinder workflow
#'
#' @param n_cells Number of cells (default: 200)
#' @param n_genes Number of genes (default: 1000)
#' @param doublet_rate Expected doublet rate (default: 0.05)
#' @param seed Random seed (default: 42)
#' @return List with test data
#' @export
create_scdblfinder_test_data <- function(
    n_cells = 200,
    n_genes = 1000,
    doublet_rate = 0.05,
    seed = 42
) {
  set.seed(seed)

  n_singlets <- round(n_cells * (1 - doublet_rate))
  n_doublets <- n_cells - n_singlets

  # Create gene names
  gene_names <- paste0("GENE_", 1:n_genes)

  # Create cell names
  singlet_cells <- paste0("Singlet_", 1:n_singlets)
  doublet_cells <- paste0("Doublet_", 1:n_doublets)
  cell_names <- c(singlet_cells, doublet_cells)

  # Generate singlet counts (simple Poisson)
  singlet_counts <- matrix(
    rpois(n_genes * n_singlets, lambda = 3),
    nrow = n_genes,
    ncol = n_singlets
  )

  # Generate doublet counts (higher expression)
  doublet_counts <- matrix(
    rpois(n_genes * n_doublets, lambda = 6),
    nrow = n_genes,
    ncol = n_doublets
  )

  # Combine
  counts <- cbind(singlet_counts, doublet_counts)
  rownames(counts) <- gene_names
  colnames(counts) <- cell_names

  # Create sample info (simulate 2 samples)
  half <- n_cells %/% 2
  sample_info <- c(rep("Sample1", half), rep("Sample2", n_cells - half))

  list(
    counts = counts,
    n_cells = n_cells,
    n_genes = n_genes,
    n_singlets = n_singlets,
    n_doublets = n_doublets,
    cell_names = cell_names,
    sample_info = sample_info,
    seed = seed
  )
}

#' Recommend scDblFinder parameters
#'
#' Get recommended parameters based on data characteristics
#'
#' @param n_cells Number of cells
#' @param n_samples Number of samples (default: 1)
#' @param is_10x Whether data is from 10X Genomics
#' @return List with recommended parameters
#' @export
recommend_scdblfinder_params <- function(
    n_cells,
    n_samples = 1,
    is_10x = TRUE
) {
  # Recommend dbr.per1k based on platform
  if (is_10x) {
    # Standard 10X: ~1% per 1000 cells
    # HT 10X: ~0.5% per 1000 cells
    dbr_per1k <- 0.008  # Conservative estimate
  } else {
    dbr_per1k <- 0.01  # Higher for other platforms
  }

  # Calculate expected doublet rate
  expected_dbr <- dbr_per1k * (n_cells / 1000)
  expected_dbr <- min(expected_dbr, 0.5)  # Cap at 50%

  # Recommend nfeatures
  if (n_cells < 500) {
    nfeatures <- 1000
  } else if (n_cells < 5000) {
    nfeatures <- 1500
  } else {
    nfeatures <- 2000
  }

  # Recommend dims
  dims <- min(20, round(n_cells / 100))
  dims <- max(5, dims)

  # Recommend k
  k <- min(30, round(n_cells / 50))
  k <- max(5, k)

  # Recommend clusters setting
  clusters <- ifelse(n_cells < 500, FALSE, TRUE)

  params <- list(
    nfeatures = nfeatures,
    dims = dims,
    k = k,
    dbr.per1k = dbr_per1k,
    expected_dbr = expected_dbr,
    clusters = clusters,
    message = sprintf(
"Recommended parameters for %d cells across %d sample(s):
  - nfeatures: %d
  - dims: %d
  - k: %d
  - dbr.per1k: %.3f
  - expected_dbr: %.2f%%
  - clusters: %s (auto-clustering)
  - multiSampleMode: 'split' (if multi-sample)
",
      n_cells, n_samples,
      nfeatures, dims, k,
      dbr_per1k, 100 * expected_dbr,
      ifelse(clusters, "TRUE", "FALSE")
    )
  )

  return(params)
}

#' Estimate expected doublet rate
#'
#' Estimate expected doublet rate based on cell number and platform
#'
#' @param n_cells Number of cells
#' @param platform Sequencing platform: "10x_standard", "10x_ht", "other"
#' @param dbr.per1k Doublet rate per 1000 cells (overrides platform)
#' @return Expected doublet rate
#' @export
estimate_doublet_rate <- function(
    n_cells,
    platform = c("10x_standard", "10x_ht", "other"),
    dbr.per1k = NULL
) {
  platform <- match.arg(platform)

  if (is.null(dbr.per1k)) {
    dbr.per1k <- switch(platform,
                         "10x_standard" = 0.008,
                         "10x_ht" = 0.004,
                         "other" = 0.01)
  }

  # Calculate rate (approximately linear with cell number)
  dbr <- dbr.per1k * (n_cells / 1000)

  # Cap at reasonable maximum
  dbr <- min(dbr, 0.5)

  return(dbr)
}

#' Filter cells by doublet classification
#'
#' Filter SingleCellExperiment to remove doublets
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param keep_singlets Keep only singlets (default: TRUE)
#' @param keep_unclassified Keep unclassified cells (default: TRUE)
#' @return Filtered SingleCellExperiment
#' @export
filter_doublets <- function(
    sce,
    keep_singlets = TRUE,
    keep_unclassified = TRUE
) {
  cd <- SummarizedExperiment::colData(sce)

  if (!"scDblFinder.class" %in% colnames(cd)) {
    stop("No scDblFinder classification found. Run scDblFinder first.")
  }

  if (keep_singlets) {
    keep <- cd$scDblFinder.class == "singlet"
    if (keep_unclassified) {
      keep <- keep | is.na(cd$scDblFinder.class)
    }
  } else {
    keep <- rep(TRUE, nrow(cd))
  }

  cat(sprintf("Filtering: keeping %d/%d cells (%.1f%%)\n",
              sum(keep), length(keep), 100 * sum(keep) / length(keep)))

  return(sce[, keep])
}

#' Compare scDblFinder results across samples
#'
#' Compare doublet rates across multiple samples
#'
#' @param sce_list Named list of SingleCellExperiments with scDblFinder results
#' @return Data frame with comparison results
#' @export
compare_scdblfinder_results <- function(sce_list) {
  comparisons <- lapply(names(sce_list), function(name) {
    sce <- sce_list[[name]]
    cd <- SummarizedExperiment::colData(sce)

    if (!"scDblFinder.class" %in% colnames(cd)) {
      stop(paste("No scDblFinder results found for", name))
    }

    n_doublets <- sum(cd$scDblFinder.class == "doublet")
    n_singlets <- sum(cd$scDblFinder.class == "singlet")

    data.frame(
      sample = name,
      total_cells = nrow(cd),
      doublets = n_doublets,
      singlets = n_singlets,
      doublet_rate = n_doublets / nrow(cd),
      mean_score = mean(cd$scDblFinder.score, na.rm = TRUE),
      stringsAsFactors = FALSE
    )
  })

  do.call(rbind, comparisons)
}

#' Get cells by doublet origin
#'
#' Get cells classified as originating from specific clusters
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param origin_cluster Cluster of origin (or vector of clusters)
#' @return Vector of cell names
#' @export
get_cells_by_origin <- function(sce, origin_cluster) {
  cd <- SummarizedExperiment::colData(sce)

  if (!"scDblFinder.mostLikelyOrigin" %in% colnames(cd)) {
    stop("scDblFinder.mostLikelyOrigin not found. Run scDblFinder with cluster-based approach.")
  }

  # Parse origin
  origins <- cd$scDblFinder.mostLikelyOrigin

  # Find cells with specified origin
  if (length(origin_cluster) == 1) {
    matches <- origins == origin_cluster
  } else {
    matches <- origins %in% origin_cluster
  }

  cells <- rownames(cd)[matches]

  return(cells)
}

#' Subset SCE by cells
#'
#' Wrapper to subset SingleCellExperiment by cell names
#'
#' @param sce SingleCellExperiment
#' @param cells Cell names to keep
#' @return Subsetted SingleCellExperiment
#' @export
subset_sce_cells <- function(sce, cells) {
  keep <- colnames(sce) %in% cells

  if (sum(keep) == 0) {
    warning("No cells matched. Returning empty object.")
  }

  return(sce[, keep])
}

#' Check for cluster-enriched doublets
#'
#' Check if doublets are enriched in specific clusters
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param cluster_col Column with cluster assignments
#' @return Data frame with enrichment statistics
#' @export
check_doublet_enrichment <- function(sce, cluster_col = "cluster") {
  cd <- as.data.frame(SummarizedExperiment::colData(sce))

  if (!"scDblFinder.class" %in% colnames(cd)) {
    stop("scDblFinder results not found")
  }

  if (!cluster_col %in% colnames(cd)) {
    stop(paste("Cluster column", cluster_col, "not found"))
  }

  # Calculate doublet rate by cluster
  result <- aggregate(
    cd$scDblFinder.class == "doublet",
    by = list(cluster = cd[[cluster_col]]),
    FUN = function(x) c(sum(x), length(x), sum(x) / length(x))
  )

  result <- do.call(data.frame, result)
  colnames(result) <- c("cluster", "n_doublets", "n_cells", "doublet_rate")

  # Add overall rate for comparison
  overall_rate <- sum(cd$scDblFinder.class == "doublet") / nrow(cd)
  result$enrichment <- result$doublet_rate / overall_rate

  # Sort by enrichment
  result <- result[order(-result$enrichment), ]

  return(result)
}

#' Merge scDblFinder results from multiple runs
#'
#' Merge scDblFinder results from separately processed samples
#'
#' @param sce_list Named list of SingleCellExperiments
#' @return Merged SingleCellExperiment
#' @export
merge_scdblfinder_results <- function(sce_list) {
  # Check all have scDblFinder results
  for (name in names(sce_list)) {
    cd <- SummarizedExperiment::colData(sce_list[[name]])
    if (!"scDblFinder.class" %in% colnames(cd)) {
      stop(paste("No scDblFinder results found for", name))
    }
  }

  # Combine using cbind
  merged <- do.call(cbind, sce_list)

  return(merged)
}

#' Create scDblFinder QC report
#'
#' Comprehensive QC report for scDblFinder results
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param output_file Output file path (optional)
#' @return QC report text
#' @export
create_scdblfinder_qc_report <- function(sce, output_file = NULL) {
  cd <- SummarizedExperiment::colData(sce)

  if (!"scDblFinder.class" %in% colnames(cd)) {
    stop("scDblFinder results not found")
  }

  n_doublets <- sum(cd$scDblFinder.class == "doublet")
  n_singlets <- sum(cd$scDblFinder.class == "singlet")
  doublet_rate <- n_doublets / nrow(cd)

  # Calculate score statistics
  if ("scDblFinder.score" %in% colnames(cd)) {
    scores_doublets <- cd$scDblFinder.score[cd$scDblFinder.class == "doublet"]
    scores_singlets <- cd$scDblFinder.score[cd$scDblFinder.class == "singlet"]

    score_summary <- sprintf("
Score Statistics
----------------
Doublets - Mean: %.3f, Median: %.3f
Singlets - Mean: %.3f, Median: %.3f
Separation (mean difference): %.3f
",
                              mean(scores_doublets, na.rm = TRUE),
                              median(scores_doublets, na.rm = TRUE),
                              mean(scores_singlets, na.rm = TRUE),
                              median(scores_singlets, na.rm = TRUE),
                              mean(scores_doublets, na.rm = TRUE) - mean(scores_singlets, na.rm = TRUE)
    )

    separation_status <- if ((mean(scores_doublets) - mean(scores_singlets)) > 0.1) "Good" else "Poor"
  } else {
    score_summary <- ""
    separation_status <- "N/A"
  }

  report <- sprintf("
scDblFinder QC Report
=====================
Date: %s

Summary Statistics
------------------
Total cells: %d
Doublets: %d (%.1f%%)
Singlets: %d (%.1f%%)

%s

QC Checks
---------
1. Doublet rate: %s (expected ~%.1f%% for %d cells)
2. Score separation: %s
3. Classification: %s

Recommendations
---------------
- Doublet rate within expected range: %s
- If doublet rate too high: Check if samples were processed separately
- If score separation poor: Consider adjusting nfeatures or dims
- Visualize doublets on UMAP to check distribution
",
                    format(Sys.time(), "%Y-%m-%d %H:%M"),
                    nrow(cd), n_doublets, 100 * doublet_rate,
                    n_singlets, 100 * n_singlets / nrow(cd),
                    score_summary,
                    ifelse(doublet_rate > 0.02 && doublet_rate < 0.3, "OK", "CHECK"),
                    0.008 * (nrow(cd) / 1000) * 100, nrow(cd),
                    separation_status,
                    ifelse(doublet_rate > 0, "Complete", "No classifications"),
                    ifelse(doublet_rate > 0.02 && doublet_rate < 0.3, "Yes", "Review needed")
  )

  if (!is.null(output_file)) {
    writeLines(report, output_file)
  }

  return(report)
}
