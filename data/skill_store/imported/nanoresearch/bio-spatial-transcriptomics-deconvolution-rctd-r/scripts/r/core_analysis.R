#' RCTD Deconvolution for Spatial Transcriptomics
#'
#' Reference-based cell type deconvolution with doublet detection.
#' Wrapper functions for spacexr package following best practices.
#'
#' @author Yang Guo
#' @date 2026-04-07
#' @version 2.0.0

#' Check RCTD Dependencies
#'
#' Verify that required packages are installed.
#'
#' @return Logical indicating if all dependencies are available
#' @export
check_rctd_dependencies <- function() {
  deps <- c("spacexr", "Matrix", "ggplot2")
  missing <- character()

  for (pkg in deps) {
    if (!requireNamespace(pkg, quietly = TRUE)) {
      missing <- c(missing, pkg)
    }
  }

  if (length(missing) > 0) {
    warning(sprintf("Missing packages: %s", paste(missing, collapse = ", ")))
    return(FALSE)
  }

  return(TRUE)
}

#' Validate RCTD Input Data
#'
#' Comprehensive validation of input data before running RCTD.
#'
#' @param spatial_counts Gene expression matrix for spatial data (genes x spots)
#' @param spatial_coords DataFrame with x, y coordinates (optional, rows = spots)
#' @param reference_counts Gene expression matrix for reference (genes x cells)
#' @param cell_types Named vector of cell type labels for reference cells
#' @param require_coords Logical: require spatial coordinates (default: FALSE)
#'
#' @return List with validation results: valid (logical), errors (list), warnings (list), stats (list)
#' @export
validate_rctd_input <- function(
    spatial_counts,
    spatial_coords = NULL,
    reference_counts,
    cell_types,
    require_coords = FALSE
) {
  errors <- character()
  warnings <- character()
  stats <- list()

  # Check dimensions
  if (length(cell_types) != ncol(reference_counts)) {
    errors <- c(errors, sprintf(
      "Length of cell_types (%d) must match ncol(reference_counts) (%d)",
      length(cell_types), ncol(reference_counts)
    ))
  }

  # Check cell type names
  if (is.null(names(cell_types))) {
    errors <- c(errors, "cell_types must be a named vector with cell barcodes as names")
  } else {
    # Check if names match reference column names
    name_overlap <- sum(names(cell_types) %in% colnames(reference_counts))
    if (name_overlap == 0) {
      errors <- c(errors, "Names of cell_types do not match colnames(reference_counts)")
    } else if (name_overlap < length(cell_types)) {
      warnings <- c(warnings, sprintf(
        "Only %d/%d cell type names match reference column names",
        name_overlap, length(cell_types)
      ))
    }
  }

  # Check for common genes
  common_genes <- intersect(rownames(spatial_counts), rownames(reference_counts))
  stats$n_common_genes <- length(common_genes)

  if (stats$n_common_genes == 0) {
    errors <- c(errors, "No common genes between spatial and reference data. Check rownames.")
  } else if (stats$n_common_genes < 100) {
    warnings <- c(warnings, sprintf(
      "Only %d common genes found. Recommended: >1000 for optimal results.",
      stats$n_common_genes
    ))
  }

  # Check cell type counts
  cell_type_counts <- table(cell_types)
  stats$n_cell_types <- length(cell_type_counts)
  stats$cell_type_counts <- as.list(cell_type_counts)

  low_count_types <- names(cell_type_counts)[cell_type_counts < 25]
  if (length(low_count_types) > 0) {
    warnings <- c(warnings, sprintf(
      "Cell types with <25 cells (RCTD may fail or perform poorly): %s",
      paste(low_count_types, collapse = ", ")
    ))
  }

  # Check spatial coordinates if provided
  if (!is.null(spatial_coords)) {
    if (nrow(spatial_coords) != ncol(spatial_counts)) {
      errors <- c(errors, sprintf(
        "nrow(spatial_coords) (%d) must match ncol(spatial_counts) (%d)",
        nrow(spatial_coords), ncol(spatial_counts)
      ))
    }

    if (!all(c("x", "y") %in% colnames(spatial_coords))) {
      errors <- c(errors, "spatial_coords must have 'x' and 'y' columns")
    }
  } else if (require_coords) {
    errors <- c(errors, "Spatial coordinates are required but not provided")
  }

  # Check for NA/Inf values
  if (any(is.na(spatial_counts))) {
    warnings <- c(warnings, "spatial_counts contains NA values")
  }
  if (any(is.na(reference_counts))) {
    warnings <- c(warnings, "reference_counts contains NA values")
  }

  stats$n_spots <- ncol(spatial_counts)
  stats$n_ref_cells <- ncol(reference_counts)

  list(
    valid = length(errors) == 0,
    errors = errors,
    warnings = warnings,
    stats = stats
  )
}

#' Create RCTD Objects from Matrices
#'
#' Create SpatialRNA and Reference objects for RCTD.
#'
#' @param spatial_counts Gene expression matrix (genes x spots)
#' @param spatial_coords DataFrame with x, y coordinates (optional)
#' @param reference_counts Gene expression matrix (genes x cells)
#' @param cell_types Named vector of cell type labels
#' @param require_coords Logical: require coordinates (default: FALSE)
#'
#' @return List containing spatial_rna (SpatialRNA) and reference (Reference) objects
#' @export
create_rctd_objects <- function(
    spatial_counts,
    spatial_coords = NULL,
    reference_counts,
    cell_types,
    require_coords = FALSE
) {
  if (!requireNamespace("spacexr", quietly = TRUE)) {
    stop("spacexr package required. Install with: devtools::install_github('dmcable/spacexr')")
  }

  library(spacexr)
  library(Matrix)

  # Ensure proper names
  if (is.null(names(cell_types))) {
    if (length(cell_types) == ncol(reference_counts)) {
      names(cell_types) <- colnames(reference_counts)
    } else {
      stop("cell_types must be named or have same length as reference columns")
    }
  }

  # Create Reference object
  message("Creating Reference object...")
  nUMI_ref <- colSums(reference_counts)

  reference <- Reference(
    counts = reference_counts,
    cell_types = cell_types,
    nUMI = nUMI_ref
  )

  # Create SpatialRNA object
  message("Creating SpatialRNA object...")
  nUMI_spatial <- colSums(spatial_counts)

  if (!is.null(spatial_coords)) {
    # Ensure rownames match colnames of spatial_counts
    rownames(spatial_coords) <- colnames(spatial_counts)

    spatial_rna <- SpatialRNA(
      coords = spatial_coords[, c("x", "y")],
      counts = spatial_counts,
      nUMI = nUMI_spatial
    )
  } else {
    # Use fake coordinates if not provided
    spatial_rna <- SpatialRNA(
      coords = NULL,
      counts = spatial_counts,
      nUMI = nUMI_spatial,
      use_fake_coords = TRUE
    )
  }

  list(
    spatial_rna = spatial_rna,
    reference = reference
  )
}

#' Run RCTD Deconvolution
#'
#' Complete RCTD workflow: validate, create objects, and run deconvolution.
#'
#' @param spatial_counts Gene expression matrix for spatial data (genes x spots)
#' @param spatial_coords DataFrame with x, y coordinates (optional)
#' @param reference_counts Gene expression matrix for reference (genes x cells)
#' @param cell_types Named vector of cell type labels for reference cells
#' @param doublet_mode Character: 'full', 'doublet', or 'multi' (default: 'doublet')
#' @param max_cores Number of CPU cores to use (default: 4)
#' @param gene_cutoff Minimum gene expression threshold (default: 0.000125)
#' @param fc_cutoff Fold change cutoff for marker selection (default: 0.5)
#' @param UMI_min Minimum UMI per spot (default: 100)
#' @param UMI_max Maximum UMI per spot (default: 20000000)
#' @param test_mode Logical: run in test mode for quick testing (default: FALSE)
#' @param validate Logical: validate inputs before running (default: TRUE)
#' @param keep_reference Logical: keep reference in RCTD object (default: FALSE)
#'
#' @return RCTD object with deconvolution results
#' @export
run_rctd <- function(
    spatial_counts,
    spatial_coords = NULL,
    reference_counts,
    cell_types,
    doublet_mode = 'doublet',
    max_cores = 4,
    gene_cutoff = 0.000125,
    fc_cutoff = 0.5,
    UMI_min = 100,
    UMI_max = 20000000,
    test_mode = FALSE,
    validate = TRUE,
    keep_reference = FALSE
) {
  # Check dependencies
  if (!check_rctd_dependencies()) {
    stop("Missing required dependencies. Please install spacexr, Matrix, and ggplot2.")
  }

  library(spacexr)
  library(Matrix)

  # Validate inputs
  if (validate) {
    message("Validating inputs...")
    validation <- validate_rctd_input(
      spatial_counts = spatial_counts,
      spatial_coords = spatial_coords,
      reference_counts = reference_counts,
      cell_types = cell_types
    )

    if (!validation$valid) {
      stop(paste("Validation errors:", paste(validation$errors, collapse = "\n")))
    }

    if (length(validation$warnings) > 0) {
      for (w in validation$warnings) {
        warning(w)
      }
    }

    message(sprintf("Validation passed: %d spots, %d cell types, %d common genes",
                    validation$stats$n_spots,
                    validation$stats$n_cell_types,
                    validation$stats$n_common_genes))
  }

  message(sprintf("Running RCTD with %d spots and %d reference cells...",
                  ncol(spatial_counts), ncol(reference_counts)))

  # Create objects
  objects <- create_rctd_objects(
    spatial_counts = spatial_counts,
    spatial_coords = spatial_coords,
    reference_counts = reference_counts,
    cell_types = cell_types
  )

  # Create RCTD object
  message("Initializing RCTD...")
  rctd <- create.RCTD(
    spatialRNA = objects$spatial_rna,
    reference = objects$reference,
    max_cores = max_cores,
    gene_cutoff = gene_cutoff,
    fc_cutoff = fc_cutoff,
    UMI_min = UMI_min,
    UMI_max = UMI_max,
    test_mode = test_mode,
    keep_reference = keep_reference
  )

  # Run RCTD
  message(sprintf("Running RCTD in '%s' mode...", doublet_mode))
  rctd <- run.RCTD(rctd, doublet_mode = doublet_mode)

  message("RCTD complete!")
  return(rctd)
}

#' Run RCTD with Seurat Objects
#'
#' Convenience wrapper for Seurat users.
#'
#' @param spatial_seurat Seurat object for spatial data
#' @param reference_seurat Seurat object for reference (with cell type labels)
#' @param cell_type_column Column name for cell types in reference metadata
#' @param coord_columns Column names for spatial coordinates (default: c("imagerow", "imagecol"))
#' @param assay Spatial assay to use (default: "Spatial")
#' @param slot Data slot to use (default: "counts")
#' @param ... Additional arguments passed to run_rctd()
#'
#' @return RCTD object
#' @export
run_rctd_seurat <- function(
    spatial_seurat,
    reference_seurat,
    cell_type_column = 'cell_type',
    coord_columns = c("imagerow", "imagecol"),
    assay = "Spatial",
    slot = 'counts',
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(Seurat)

  # Extract spatial data
  if (packageVersion("SeuratObject") >= "5.0.0") {
    spatial_counts <- GetAssayData(spatial_seurat, layer = slot, assay = assay)
  } else {
    spatial_counts <- GetAssayData(spatial_seurat, slot = slot, assay = assay)
  }

  # Extract coordinates from Seurat object
  spatial_coords <- NULL
  if (all(coord_columns %in% colnames(spatial_seurat@meta.data))) {
    spatial_coords <- spatial_seurat@meta.data[, coord_columns, drop = FALSE]
    colnames(spatial_coords) <- c("x", "y")
  } else {
    # Try to get coordinates using Seurat API (v4/v5 compatible)
    tryCatch({
      coords_obj <- Seurat::GetTissueCoordinates(spatial_seurat)
      spatial_coords <- data.frame(
        x = coords_obj[, "imagerow"],
        y = coords_obj[, "imagecol"],
        row.names = rownames(coords_obj)
      )
    }, error = function(e) {
      message("Could not extract spatial coordinates: ", conditionMessage(e))
    })
  }

  # Extract reference data
  if (packageVersion("SeuratObject") >= "5.0.0") {
    reference_counts <- GetAssayData(reference_seurat, layer = slot)
  } else {
    reference_counts <- GetAssayData(reference_seurat, slot = slot)
  }

  # Get cell types
  if (!cell_type_column %in% colnames(reference_seurat@meta.data)) {
    stop(sprintf("'%s' not found in reference metadata", cell_type_column))
  }

  cell_types <- setNames(
    as.character(reference_seurat@meta.data[[cell_type_column]]),
    colnames(reference_seurat)
  )
  cell_types <- factor(cell_types)

  # Run RCTD
  results <- run_rctd(
    spatial_counts = spatial_counts,
    spatial_coords = spatial_coords,
    reference_counts = reference_counts,
    cell_types = cell_types,
    ...
  )

  return(results)
}

#' Extract Cell Type Proportions from RCTD Results
#'
#' @param rctd_results RCTD object from run_rctd()
#' @param normalize Logical: normalize to sum to 1 (default: TRUE)
#' @param doublet_mode Which mode to extract: 'auto', 'full', 'doublet' (default: 'auto')
#'
#' @return DataFrame of cell type proportions (spots x cell_types)
#' @export
extract_proportions_rctd <- function(
    rctd_results,
    normalize = TRUE,
    doublet_mode = 'auto'
) {
  if (doublet_mode == 'auto') {
    doublet_mode <- rctd_results@config$doublet_mode %||% 'full'
  }

  # Extract weights based on mode
  if (doublet_mode == 'doublet' && 'weights_doublet' %in% names(rctd_results@results)) {
    weights <- rctd_results@results$weights_doublet
  } else if (doublet_mode == 'full' && 'weights' %in% names(rctd_results@results)) {
    weights <- rctd_results@results$weights
  } else {
    # Default to weights
    weights <- rctd_results@results$weights
  }

  # Convert to data frame
  props <- as.data.frame(as.matrix(weights))

  if (normalize && nrow(props) > 0) {
    # Normalize each row to sum to 1
    # Prefer spacexr::normalize_weights() if available; fall back to manual
    if (requireNamespace("spacexr", quietly = TRUE) &&
        exists("normalize_weights", where = asNamespace("spacexr"))) {
      props <- spacexr::normalize_weights(props)
    } else {
      row_sums <- rowSums(props)
      props <- props / row_sums
      props[is.na(props)] <- 0
    }
  }

  return(props)
}

#' Summarize RCTD Results
#'
#' Generate comprehensive summary statistics from RCTD results.
#'
#' @param rctd_results RCTD object
#' @param doublet_mode Which mode results to summarize (default: auto-detect)
#'
#' @return List with summary statistics
#' @export
summarize_rctd_results <- function(
    rctd_results,
    doublet_mode = NULL
) {
  if (is.null(doublet_mode)) {
    doublet_mode <- rctd_results@config$doublet_mode %||% 'full'
  }

  summary <- list(
    doublet_mode = doublet_mode,
    n_spots = ncol(rctd_results@spatialRNA@counts),
    n_cell_types = rctd_results@cell_type_info$renorm[[3]],
    cell_type_names = rctd_results@cell_type_info$renorm[[2]]
  )

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results, doublet_mode = doublet_mode)

  # Compute statistics
  summary$mean_proportions <- colMeans(props, na.rm = TRUE)
  summary$max_proportions <- apply(props, 2, max, na.rm = TRUE)

  # Dominant cell types
  dominant <- colnames(props)[apply(props, 1, which.max)]
  summary$dominant_cell_types <- table(dominant)

  # Spot classification (for doublet mode)
  if (doublet_mode == 'doublet' && 'results_df' %in% names(rctd_results@results)) {
    results_df <- rctd_results@results$results_df
    summary$spot_classes <- table(results_df$spot_class)

    # Confidence metrics
    summary$singlet_spots <- sum(results_df$spot_class == 'singlet')
    summary$doublet_certain <- sum(results_df$spot_class == 'doublet_certain')
    summary$doublet_uncertain <- sum(results_df$spot_class == 'doublet_uncertain')
    summary$rejected_spots <- sum(results_df$spot_class == 'reject')
  }

  # Purity metrics
  summary$pure_spots <- sum(apply(props, 1, max) > 0.8)
  summary$mixed_spots <- sum(apply(props, 1, max) <= 0.8)

  return(summary)
}

#' Get Top Cell Types per Spot
#'
#' @param rctd_results RCTD object
#' @param n_top Number of top cell types to return (default: 2)
#' @param doublet_mode Which mode to use (default: 'auto')
#'
#' @return DataFrame with top cell types per spot
#' @export
get_top_cell_types <- function(
    rctd_results,
    n_top = 2,
    doublet_mode = 'auto'
) {
  props <- extract_proportions_rctd(rctd_results, doublet_mode = doublet_mode)

  # Get top cell types for each spot
  result <- do.call(rbind, lapply(rownames(props), function(spot) {
    x <- props[spot, ]
    top_idx <- order(x, decreasing = TRUE)[1:min(n_top, length(x))]
    data.frame(
      spot = spot,
      rank = seq_along(top_idx),
      cell_type = names(x)[top_idx],
      proportion = x[top_idx],
      stringsAsFactors = FALSE
    )
  }))

  return(result)
}

#' Get Doublet Predictions
#'
#' Extract doublet predictions for doublet mode results.
#'
#' @param rctd_results RCTD object
#'
#' @return DataFrame with doublet predictions (spot_class, first_type, second_type)
#' @export
get_doublet_predictions <- function(rctd_results) {
  if (!'results_df' %in% names(rctd_results@results)) {
    stop("No doublet results found. Was RCTD run in doublet mode?")
  }

  results_df <- rctd_results@results$results_df

  # Get cell type names
  cell_type_names <- rctd_results@cell_type_info$renorm[[2]]

  # Create result data frame
  result <- data.frame(
    spot = rownames(results_df),
    spot_class = results_df$spot_class,
    first_type = cell_type_names[results_df$first_type],
    second_type = ifelse(
      results_df$spot_class %in% c('doublet_certain', 'doublet_uncertain'),
      cell_type_names[results_df$second_type],
      NA
    ),
    stringsAsFactors = FALSE
  )

  return(result)
}

#' Export RCTD Results
#'
#' @param rctd_results RCTD object
#' @param output_dir Output directory path
#' @param prefix File name prefix (default: 'rctd')
#' @param export_object Logical: save full RCTD object (default: TRUE)
#'
#' @return Invisible NULL
#' @export
export_rctd_results <- function(
    rctd_results,
    output_dir,
    prefix = 'rctd',
    export_object = TRUE
) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Export proportions (all modes)
  props <- extract_proportions_rctd(rctd_results)
  write.csv(props, file.path(output_dir, sprintf('%s_proportions.csv', prefix)))

  # Export top cell types
  top_types <- get_top_cell_types(rctd_results, n_top = 2)
  write.csv(top_types, file.path(output_dir, sprintf('%s_top_cell_types.csv', prefix)))

  # Export doublet predictions if in doublet mode
  doublet_mode <- rctd_results@config$doublet_mode %||% 'full'
  if (doublet_mode == 'doublet' && 'results_df' %in% names(rctd_results@results)) {
    doublet_preds <- get_doublet_predictions(rctd_results)
    write.csv(doublet_preds, file.path(output_dir, sprintf('%s_doublet_predictions.csv', prefix)))
  }

  # Export summary statistics
  summary <- summarize_rctd_results(rctd_results)
  summary_file <- file.path(output_dir, sprintf('%s_summary.txt', prefix))
  cat(create_rctd_report(rctd_results, summary_file), file = summary_file)

  # Save RCTD object
  if (export_object) {
    saveRDS(rctd_results, file.path(output_dir, sprintf('%s_object.rds', prefix)))
  }

  message(sprintf("Results exported to %s", output_dir))
  invisible(NULL)
}

#' Create RCTD Results Report
#'
#' Generate a text report of RCTD results.
#'
#' @param rctd_results RCTD object
#' @param output_file Optional: save report to file
#'
#' @return Character string containing the report
#' @export
create_rctd_report <- function(rctd_results, output_file = NULL) {
  summary <- summarize_rctd_results(rctd_results)

  report <- sprintf("
RCTD Deconvolution Analysis Report
==================================
Date: %s

Dataset Summary
---------------
Number of spots: %d
Number of cell types: %d
Cell types: %s

Analysis Parameters
-------------------
Mode: %s
Cores used: %d
Gene cutoff: %.6f
FC cutoff: %.2f

Results Summary
---------------
Mean cell type proportions:
%s

Dominant cell types (counts):
%s
",
    format(Sys.time(), "%Y-%m-%d %H:%M:%S"),
    summary$n_spots,
    summary$n_cell_types,
    paste(summary$cell_type_names, collapse = ", "),
    summary$doublet_mode,
    rctd_results@config$max_cores,
    rctd_results@config$gene_cutoff,
    rctd_results@config$fc_cutoff,
    paste(sprintf("  %s: %.3f", names(summary$mean_proportions), summary$mean_proportions), collapse = "\n"),
    paste(sprintf("  %s: %d", names(summary$dominant_cell_types), summary$dominant_cell_types), collapse = "\n")
  )

  # Add doublet-specific info
  if (summary$doublet_mode == 'doublet' && !is.null(summary$spot_classes)) {
    report <- paste0(report, sprintf("
Spot Classification (Doublet Mode)
-----------------------------------
Singlet spots: %d (%.1f%%)
Doublet certain: %d (%.1f%%)
Doublet uncertain: %d (%.1f%%)
Rejected spots: %d (%.1f%%)
",
      summary$singlet_spots, 100 * summary$singlet_spots / summary$n_spots,
      summary$doublet_certain, 100 * summary$doublet_certain / summary$n_spots,
      summary$doublet_uncertain, 100 * summary$doublet_uncertain / summary$n_spots,
      summary$rejected_spots, 100 * summary$rejected_spots / summary$n_spots
    ))
  }

  report <- paste0(report, sprintf("
Purity Metrics
--------------
Pure spots (>80%% single type): %d
Mixed spots: %d

Output Files Generated
----------------------
- {prefix}_proportions.csv: Cell type proportions per spot
- {prefix}_top_cell_types.csv: Top cell types per spot
",
    summary$pure_spots, summary$mixed_spots
  ))

  if (summary$doublet_mode == 'doublet') {
    report <- paste0(report, "- {prefix}_doublet_predictions.csv: Doublet predictions\n")
  }

  report <- paste0(report, "- {prefix}_object.rds: Full RCTD object\n")

  if (!is.null(output_file)) {
    cat(report, file = output_file)
  }

  return(report)
}

# Helper function for NULL default
`%||%` <- function(x, y) if (is.null(x)) y else x
