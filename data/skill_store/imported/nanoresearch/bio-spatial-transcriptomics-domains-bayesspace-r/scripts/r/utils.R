#' Utility Functions for BayesSpace Spatial Domain Analysis
#'
#' Helper functions for data preparation, result processing, and analysis.
#' These utilities complement the native BayesSpace package functions.
#'
#' @author Yang Guo
#' @date 2026-04-07

#' Validate BayesSpace Input Data
#'
#' Check data consistency before running BayesSpace analysis
#'
#' @param sce SingleCellExperiment object
#' @return List with validation results
#' @export
validate_bayesspace_data <- function(sce) {
  errors <- c()
  warnings <- c()

  # Check basic structure
  if (ncol(sce) == 0) {
    errors <- c(errors, "No spots in data")
  }
  if (nrow(sce) == 0) {
    errors <- c(errors, "No genes in data")
  }

  # Check required colData columns
  required_cols <- c("array_row", "array_col")
  missing_cols <- required_cols[!required_cols %in% colnames(colData(sce))]
  if (length(missing_cols) > 0) {
    errors <- c(errors, sprintf("Missing required columns: %s", paste(missing_cols, collapse = ", ")))
  }

  # Check spatial coordinates
  if (all(required_cols %in% colnames(colData(sce)))) {
    if (any(is.na(sce$array_row)) || any(is.na(sce$array_col))) {
      warnings <- c(warnings, "Spatial coordinates contain NA values")
    }
    if (any(sce$array_row < 0) || any(sce$array_col < 0)) {
      warnings <- c(warnings, "Spatial coordinates contain negative values")
    }
  }

  # Check for count data
  if (!"counts" %in% assayNames(sce)) {
    warnings <- c(warnings, "No 'counts' assay found. Preprocessing may fail.")
  }

  # Check PCA
  if (!"PCA" %in% reducedDimNames(sce)) {
    warnings <- c(warnings, "PCA not computed. Run spatialPreprocess() first.")
  }

  list(
    valid = length(errors) == 0,
    errors = errors,
    warnings = warnings,
    n_spots = ncol(sce),
    n_genes = nrow(sce),
    has_spatial = all(required_cols %in% colnames(colData(sce))),
    has_pca = "PCA" %in% reducedDimNames(sce)
  )
}

#' Print Validation Results
#'
#' @param validation Validation result list from validate_bayesspace_data()
#' @export
print_validation_results <- function(validation) {
  if (validation$valid) {
    cat("Validation: PASSED\n")
  } else {
    cat("Validation: FAILED\n")
  }

  cat(sprintf("  Spots: %d\n", validation$n_spots))
  cat(sprintf("  Genes: %d\n", validation$n_genes))
  cat(sprintf("  Spatial coordinates: %s\n", ifelse(validation$has_spatial, "Yes", "No")))
  cat(sprintf("  PCA computed: %s\n", ifelse(validation$has_pca, "Yes", "No")))

  if (length(validation$errors) > 0) {
    cat("\nErrors:\n")
    for (err in validation$errors) {
      cat(sprintf("  - %s\n", err))
    }
  }

  if (length(validation$warnings) > 0) {
    cat("\nWarnings:\n")
    for (warn in validation$warnings) {
      cat(sprintf("  - %s\n", warn))
    }
  }
}

#' Create Test SingleCellExperiment
#'
#' Generate synthetic spatial data for testing
#'
#' @param n_spots Number of spots
#' @param n_genes Number of genes
#' @param n_domains Number of spatial domains
#' @param seed Random seed
#' @return SingleCellExperiment
#' @export
create_test_sce <- function(n_spots = 200, n_genes = 500, n_domains = 4, seed = 42) {
  set.seed(seed)

  grid_size <- ceiling(sqrt(n_spots))
  array_col <- rep(1:grid_size, each = grid_size)[1:n_spots]
  array_row <- rep(1:grid_size, times = grid_size)[1:n_spots]

  counts <- matrix(rpois(n_genes * n_spots, lambda = 2), nrow = n_genes)

  domain_labels <- rep(0, n_spots)
  genes_per_domain <- n_genes / n_domains

  for (i in 1:n_spots) {
    xi <- array_col[i]
    yi <- array_row[i]

    if (xi <= grid_size / 2 && yi <= grid_size / 2) {
      domain <- 1
    } else if (xi > grid_size / 2 && yi <= grid_size / 2) {
      domain <- 2
    } else if (xi <= grid_size / 2 && yi > grid_size / 2) {
      domain <- 3
    } else {
      domain <- min(4, n_domains)
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
      ground_truth = factor(domain_labels)
    )
  )

  rownames(sce) <- paste0("Gene_", 1:n_genes)
  colnames(sce) <- paste0("Spot_", sprintf("%04d", 1:n_spots))

  sce
}

#' Summarize BayesSpace Results
#'
#' Generate summary statistics from BayesSpace clustering
#'
#' @param sce SingleCellExperiment with BayesSpace results
#' @return List with summary statistics
#' @export
summarize_bayesspace_results <- function(sce) {
  summary <- list(
    n_spots = ncol(sce),
    n_genes = nrow(sce)
  )

  # Cluster information
  if ("spatial.cluster" %in% colnames(colData(sce))) {
    clusters <- sce$spatial.cluster
    summary$n_clusters <- length(unique(clusters))
    summary$cluster_sizes <- as.list(table(clusters))
    summary$cluster_props <- as.list(prop.table(table(clusters)))
  }

  # Enhancement information
  if ("BayesSpace.data" %in% names(metadata(sce))) {
    summary$platform <- metadata(sce)$BayesSpace.data$platform
    summary$is.enhanced <- metadata(sce)$BayesSpace.data$is.enhanced
  }

  # PCA information
  if ("PCA" %in% reducedDimNames(sce)) {
    pca <- reducedDim(sce, "PCA")
    summary$n_pcs <- ncol(pca)
  }

  summary
}

#' Export BayesSpace Results
#'
#' Save BayesSpace clustering results to files
#'
#' @param sce SingleCellExperiment with results
#' @param output_dir Output directory
#' @param prefix File prefix
#' @param export_clusters Export cluster assignments
#' @param export_pca Export PCA coordinates
#' @param export_sce Save SCE object
#' @export
export_bayesspace_results <- function(sce, output_dir, prefix = "bayesspace",
                                      export_clusters = TRUE, export_pca = FALSE,
                                      export_sce = TRUE) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Export clusters
  if (export_clusters && "spatial.cluster" %in% colnames(colData(sce))) {
    cluster_df <- data.frame(
      spot = colnames(sce),
      cluster = sce$spatial.cluster,
      array_row = sce$array_row,
      array_col = sce$array_col
    )
    write.csv(cluster_df, file.path(output_dir, paste0(prefix, "_clusters.csv")), row.names = FALSE)
    cat(sprintf("Exported: %s_clusters.csv\n", prefix))
  }

  # Export PCA
  if (export_pca && "PCA" %in% reducedDimNames(sce)) {
    pca_df <- as.data.frame(reducedDim(sce, "PCA"))
    pca_df$spot <- rownames(pca_df)
    write.csv(pca_df, file.path(output_dir, paste0(prefix, "_pca.csv")), row.names = FALSE)
    cat(sprintf("Exported: %s_pca.csv\n", prefix))
  }

  # Save SCE
  if (export_sce) {
    saveRDS(sce, file.path(output_dir, paste0(prefix, "_results.rds")))
    cat(sprintf("Exported: %s_results.rds\n", prefix))
  }
}

#' Compare Clustering Solutions
#'
#' Compare BayesSpace clusters with ground truth or other methods
#'
#' @param sce SingleCellExperiment with clusters
#' @param reference Reference labels (column name or vector)
#' @return Confusion matrix and ARI
#' @export
compare_clusters <- function(sce, reference) {
  if (!"spatial.cluster" %in% colnames(colData(sce))) {
    stop("spatial.cluster not found in sce")
  }

  if (is.character(reference) && length(reference) == 1) {
    if (!reference %in% colnames(colData(sce))) {
      stop(sprintf("Reference column '%s' not found", reference))
    }
    ref_labels <- sce[[reference]]
  } else {
    ref_labels <- reference
  }

  pred_labels <- sce$spatial.cluster

  # Confusion matrix
  conf_matrix <- table(Predicted = pred_labels, Reference = ref_labels)

  # Adjusted Rand Index (if mclust available)
  ari <- NA
  if (requireNamespace("mclust", quietly = TRUE)) {
    ari <- mclust::adjustedRandIndex(pred_labels, ref_labels)
  }

  list(
    confusion_matrix = conf_matrix,
    ari = ari,
    n_clusters_pred = length(unique(pred_labels)),
    n_clusters_ref = length(unique(ref_labels))
  )
}

#' Select Optimal Number of Clusters
#'
#' Use silhouette score or other metrics to select optimal q
#'
#' @param sce SingleCellExperiment with PCA
#' @param q_range Range of q values to test
#' @param platform Spatial platform
#' @param nrep MCMC iterations
#' @param metric Evaluation metric ("silhouette")
#' @return Data frame with metrics for each q
#' @export
select_optimal_q <- function(sce, q_range = 2:10, platform = "Visium",
                             nrep = 1000, metric = "silhouette") {
  results <- data.frame(q = integer(), metric_value = numeric())

  for (q in q_range) {
    cat(sprintf("Testing q=%d...\n", q))

    sce_temp <- spatialCluster(sce, q = q, platform = platform,
                               nrep = nrep, burn.in = nrep / 5,
                               verbose = FALSE)

    if (metric == "silhouette" && requireNamespace("cluster", quietly = TRUE)) {
      # Calculate silhouette score
      dist_matrix <- dist(reducedDim(sce_temp, "PCA")[, 1:10])
      sil <- cluster::silhouette(as.numeric(sce_temp$spatial.cluster), dist_matrix)
      metric_value <- mean(sil[, 3])
    } else {
      metric_value <- NA
    }

    results <- rbind(results, data.frame(q = q, metric_value = metric_value))
  }

  results
}

#' Prepare Seurat Data for BayesSpace
#'
#' Convert Seurat object to SingleCellExperiment for BayesSpace
#'
#' @param seurat_obj Seurat object with spatial data
#' @param image_name Name of image slot in Seurat
#' @return SingleCellExperiment
#' @export
prepare_bayesspace_seurat <- function(seurat_obj, image_name = NULL) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract counts
  if (packageVersion("SeuratObject") >= "5.0.0") {
    counts <- Seurat::GetAssayData(seurat_obj, layer = "counts")
  } else {
    counts <- Seurat::GetAssayData(seurat_obj, slot = "counts")
  }

  # Get metadata
  col_data <- as.data.frame(seurat_obj@meta.data)

  # Get spatial coordinates
  if (is.null(image_name)) {
    image_name <- names(seurat_obj@images)[1]
  }

  if (!is.null(image_name) && image_name %in% names(seurat_obj@images)) {
    # Use GetTissueCoordinates for Seurat v4/v5/FOV compatibility
    coords <- Seurat::GetTissueCoordinates(seurat_obj, image = image_name)
    col_data$array_row <- coords$row
    col_data$array_col <- coords$col
    if ("imagerow" %in% colnames(coords)) {
      col_data$pxl_row_in_fullres <- coords$imagerow
      col_data$pxl_col_in_fullres <- coords$imagecol
    }
  }

  # Create SCE
  sce <- SingleCellExperiment(
    assays = list(counts = counts),
    colData = col_data
  )

  sce
}
