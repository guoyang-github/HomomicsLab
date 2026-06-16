#' Utility Functions for CARD Deconvolution
#'
#' Helper functions for data preparation, result processing, and analysis.
#' These utilities complement the native CARD package functions.
#'
#' @author Yang Guo
#' @date 2026-04-07

#' Validate CARD Input Data
#'
#' Check data consistency before creating CARD object
#'
#' @param sc_count Single-cell count matrix
#' @param spatial_count Spatial count matrix
#' @param spatial_location Spatial coordinates data frame
#' @param sc_meta Single-cell metadata
#' @param min_cells Minimum cells per cell type
#' @param min_genes Minimum common genes required
#' @return List with validation results
#' @export
validate_card_data <- function(
    sc_count,
    spatial_count,
    spatial_location,
    sc_meta = NULL,
    min_cells = 20,
    min_genes = 100
) {
  errors <- c()
  warnings <- c()

  # Check dimensions
  if (!is.null(sc_meta)) {
    if (nrow(sc_meta) != ncol(sc_count)) {
      errors <- c(errors, "sc_meta rows must match sc_count columns")
    }
    if (!all(rownames(sc_meta) == colnames(sc_count))) {
      errors <- c(errors, "sc_meta rownames must match sc_count colnames")
    }
  }

  if (ncol(spatial_count) != nrow(spatial_location)) {
    errors <- c(errors, "spatial_count columns must match spatial_location rows")
  }

  if (!all(colnames(spatial_count) == rownames(spatial_location))) {
    errors <- c(errors, "spatial_count colnames must match spatial_location rownames")
  }

  # Check spatial coordinates
  if (!all(c("x", "y") %in% colnames(spatial_location))) {
    errors <- c(errors, "spatial_location must have 'x' and 'y' columns")
  }

  # Check gene overlap
  common_genes <- intersect(rownames(sc_count), rownames(spatial_count))
  if (length(common_genes) == 0) {
    errors <- c(errors, "No common genes between sc_count and spatial_count")
  } else if (length(common_genes) < min_genes) {
    warnings <- c(warnings, sprintf("Only %d common genes found (recommended: %d+)",
                                    length(common_genes), min_genes))
  }

  # Check cell type counts
  if (!is.null(sc_meta) && "cell_type" %in% colnames(sc_meta)) {
    ct_counts <- table(sc_meta$cell_type)
    low_ct <- names(ct_counts)[ct_counts < min_cells]
    if (length(low_ct) > 0) {
      warnings <- c(warnings, sprintf("Cell types with <%d cells: %s",
                                      min_cells, paste(low_ct, collapse = ", ")))
    }
  }

  list(
    valid = length(errors) == 0,
    errors = errors,
    warnings = warnings,
    n_sc_cells = ncol(sc_count),
    n_spots = ncol(spatial_count),
    n_common_genes = length(common_genes)
  )
}

#' Print Validation Results
#'
#' @param validation Validation result list from validate_card_data()
#' @export
print_validation_results <- function(validation) {
  if (validation$valid) {
    cat("Validation: PASSED\n")
  } else {
    cat("Validation: FAILED\n")
  }

  cat(sprintf("  scRNA-seq cells: %d\n", validation$n_sc_cells))
  cat(sprintf("  Spatial spots: %d\n", validation$n_spots))
  cat(sprintf("  Common genes: %d\n", validation$n_common_genes))

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

#' Summarize CARD Results
#'
#' Generate summary statistics from CARD deconvolution
#'
#' @param CARD_obj CARD object
#' @return List with summary statistics
#' @export
summarize_card_results <- function(CARD_obj) {
  props <- CARD_obj@Proportion_CARD

  # Overall statistics
  mean_props <- colMeans(props)
  max_props <- apply(props, 2, max)

  # Dominant cell type per spot
  dominant_ct <- colnames(props)[apply(props, 1, which.max)]
  dominant_table <- table(dominant_ct)

  # Cell type diversity
  entropy <- apply(props, 1, function(x) {
    p <- x[x > 0]
    -sum(p * log(p))
  })

  list(
    n_spots = nrow(props),
    n_cell_types = ncol(props),
    optimal_phi = CARD_obj@info_parameters$phi,
    mean_proportions = sort(mean_props, decreasing = TRUE),
    max_proportions = sort(max_props, decreasing = TRUE),
    dominant_cell_types = sort(dominant_table, decreasing = TRUE),
    mean_entropy = mean(entropy),
    spots_with_high_diversity = sum(entropy > median(entropy))
  )
}

#' Get Dominant Cell Type
#'
#' Get the dominant cell type for each spot
#'
#' @param proportions Proportion matrix (spots x cell types)
#' @return Named vector of dominant cell types
#' @export
get_dominant_cell_type <- function(proportions) {
  colnames(proportions)[apply(proportions, 1, which.max)]
}

#' Calculate Spatial Entropy
#'
#' Calculate Shannon entropy for cell type diversity per spot
#'
#' @param proportions Proportion matrix (spots x cell types)
#' @return Named vector of entropy values
#' @export
calculate_spatial_entropy <- function(proportions) {
  apply(proportions, 1, function(x) {
    p <- x[x > 0]
    -sum(p * log(p))
  })
}

#' Export CARD Results
#'
#' Save CARD deconvolution results to files
#'
#' @param CARD_obj CARD object
#' @param output_dir Output directory path
#' @param prefix File prefix for output files
#' @param export_proportions Export proportion matrix
#' @param export_refined Export refined proportions if available
#' @param export_object Save CARD object as RDS
#' @export
export_card_results <- function(
    CARD_obj,
    output_dir,
    prefix = "card",
    export_proportions = TRUE,
    export_refined = TRUE,
    export_object = TRUE
) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Export proportions
  if (export_proportions) {
    props <- CARD_obj@Proportion_CARD
    write.csv(props, file.path(output_dir, sprintf("%s_proportions.csv", prefix)))

    # Export with coordinates
    results_df <- data.frame(
      spot = rownames(CARD_obj@spatial_location),
      CARD_obj@spatial_location,
      props,
      row.names = NULL
    )
    write.csv(results_df, file.path(output_dir, sprintf("%s_results.csv", prefix)),
              row.names = FALSE)
  }

  # Export refined results if available
  if (export_refined && length(CARD_obj@refined_prop) > 0) {
    write.csv(CARD_obj@refined_prop,
              file.path(output_dir, sprintf("%s_refined_proportions.csv", prefix)))
  }

  # Save CARD object
  if (export_object) {
    saveRDS(CARD_obj, file.path(output_dir, sprintf("%s_object.rds", prefix)))
  }

  cat(sprintf("Results exported to: %s/\n", output_dir))
}

#' Create Test Data for CARD
#'
#' Generate simulated data for testing CARD workflow
#'
#' @param n_genes Number of genes
#' @param n_cells Number of single cells
#' @param n_spots Number of spatial spots
#' @param n_cell_types Number of cell types
#' @param seed Random seed
#' @return List with test data
#' @export
create_card_test_data <- function(
    n_genes = 100,
    n_cells = 60,
    n_spots = 40,
    n_cell_types = 3,
    seed = 42
) {
  set.seed(seed)

  cell_types <- paste0("CellType", 1:n_cell_types)

  # Create single-cell data with marker genes
  counts_sc <- matrix(rpois(n_genes * n_cells, lambda = 2), nrow = n_genes)
  cell_type_vec <- rep(cell_types, length.out = n_cells)

  # Add marker expression
  for (i in 1:n_cell_types) {
    marker_idx <- ((i-1)*2 + 1):min(i*2, n_genes)
    ct_cells <- which(cell_type_vec == cell_types[i])
    counts_sc[marker_idx, ct_cells] <- counts_sc[marker_idx, ct_cells] +
      rpois(length(ct_cells) * length(marker_idx), lambda = 15)
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
  counts_sp <- matrix(rpois(n_genes * n_spots, lambda = 3), nrow = n_genes)
  rownames(counts_sp) <- gene_names
  colnames(counts_sp) <- paste0("Spot_", 1:n_spots)

  # Spatial coordinates
  grid_size <- ceiling(sqrt(n_spots))
  coords <- expand.grid(x = 1:grid_size, y = 1:grid_size)[1:n_spots, ]
  rownames(coords) <- colnames(counts_sp)

  list(
    sc_count = counts_sc,
    sc_meta = sc_meta,
    spatial_count = counts_sp,
    spatial_location = coords,
    cell_types = cell_types
  )
}

#' Prepare Seurat Data for CARD
#'
#' Extract and format data from Seurat objects for CARD
#'
#' @param spatial_seurat Spatial Seurat object
#' @param reference_seurat Reference Seurat object
#' @param cell_type_column Column with cell type labels
#' @return List with formatted data
#' @export
prepare_card_seurat <- function(
    spatial_seurat,
    reference_seurat,
    cell_type_column = "cell_type"
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract counts
  if (packageVersion("SeuratObject") >= "5.0.0") {
    spatial_count <- Seurat::GetAssayData(spatial_seurat, layer = "counts")
  } else {
    spatial_count <- Seurat::GetAssayData(spatial_seurat, slot = "counts")
  }
  if (packageVersion("SeuratObject") >= "5.0.0") {
    sc_count <- Seurat::GetAssayData(reference_seurat, layer = "counts")
  } else {
    sc_count <- Seurat::GetAssayData(reference_seurat, slot = "counts")
  }

  # Extract cell types
  if (!cell_type_column %in% colnames(reference_seurat@meta.data)) {
    stop(sprintf("Column '%s' not found in reference metadata", cell_type_column))
  }

  sc_meta <- data.frame(
    cell_type = reference_seurat@meta.data[[cell_type_column]],
    sample = rep("sample1", ncol(reference_seurat)),
    row.names = colnames(reference_seurat)
  )

  # Extract coordinates
  spatial_location <- Seurat::GetTissueCoordinates(spatial_seurat)
  if (all(c("imagerow", "imagecol") %in% colnames(spatial_location))) {
    spatial_location <- spatial_location[, c("imagerow", "imagecol")]
    colnames(spatial_location) <- c("x", "y")
  }

  list(
    sc_count = sc_count,
    sc_meta = sc_meta,
    spatial_count = spatial_count,
    spatial_location = spatial_location
  )
}
