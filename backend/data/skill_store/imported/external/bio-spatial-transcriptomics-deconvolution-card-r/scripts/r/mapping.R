#' Single-Cell Mapping Functions for CARD
#'
#' Wrapper and helper functions for CARD::CARD_SCMapping() that add parameter
#' validation, progress logging, mapped data extraction, and export utilities.
#'
#' @author Yang Guo
#' @date 2026-04-20

#' Run CARD Single-Cell Mapping
#'
#' Wrapper around CARD::CARD_SCMapping() with additional validation,
#' error handling, and progress reporting.
#'
#' @param CARD_object CARD object with deconvolution results
#' @param shapeSpot Cell distribution shape: "Square" or "Circle" (default: "Square")
#' @param numCell Number of cells per spot (default: 5)
#'   - ST technology: ~20
#'   - 10x Visium: ~7
#'   - Slide-seq: ~2
#' @param ncore Number of parallel cores (default: 10)
#' @param seed Random seed for reproducibility (default: 12345)
#' @param verbose Print progress messages (default: TRUE)
#' @return SingleCellExperiment object with mapped single cells
#' @export
run_card_mapping <- function(
    CARD_object,
    shapeSpot = "Square",
    numCell = 5,
    ncore = 10,
    seed = 12345,
    verbose = TRUE
) {
  if (!requireNamespace("CARD", quietly = TRUE)) {
    stop("Package 'CARD' is required. Install with:\n",
         "  devtools::install_github('YingMa0107/CARD')")
  }

  if (!requireNamespace("SingleCellExperiment", quietly = TRUE)) {
    stop("Package 'SingleCellExperiment' is required. Install with:\n",
         "  BiocManager::install('SingleCellExperiment')")
  }

  # Validate CARD object
  if (is.null(CARD_object@Proportion_CARD) || length(CARD_object@Proportion_CARD) == 0) {
    stop("CARD object does not contain deconvolution results. ",
         "Run CARD_deconvolution() before single-cell mapping.")
  }

  # Validate parameters
  if (!shapeSpot %in% c("Square", "Circle")) {
    stop("shapeSpot must be 'Square' or 'Circle'.")
  }

  if (numCell < 1 || numCell > 100) {
    warning(sprintf("numCell = %d seems unusual. Typical values: Visium=7, ST=20, Slide-seq=2",
                    numCell))
  }

  if (verbose) {
    cat("Running CARD single-cell mapping...\n")
    cat(sprintf("  Original spots: %d\n", nrow(CARD_object@Proportion_CARD)))
    cat(sprintf("  Cells per spot: %d\n", numCell))
    cat(sprintf("  Total mapped cells: ~%d\n", nrow(CARD_object@Proportion_CARD) * numCell))
    cat(sprintf("  Shape: %s\n", shapeSpot))
    cat(sprintf("  Cores: %d\n", ncore))
    cat("  (This may take several minutes)\n\n")
  }

  start_time <- Sys.time()

  tryCatch({
    set.seed(seed)

    sce_mapped <- CARD_SCMapping(
      CARD_object,
      shapeSpot = shapeSpot,
      numCell = numCell,
      ncore = ncore
    )

    elapsed <- difftime(Sys.time(), start_time, units = "secs")

    if (verbose) {
      cat(sprintf("Mapping complete! (%.1f seconds)\n", as.numeric(elapsed)))
      cat(sprintf("  Mapped cells: %d\n", ncol(sce_mapped)))
      cat(sprintf("  Genes: %d\n", nrow(sce_mapped)))
      cat(sprintf("  Cell types: %d\n", length(unique(sce_mapped$cellType))))
    }

    invisible(sce_mapped)

  }, error = function(e) {
    stop(sprintf("Single-cell mapping failed: %s", conditionMessage(e)))
  })
}

#' Extract Mapped Cell Data
#'
#' Extract count matrix, coordinates, and cell type assignments from
#' the mapped SingleCellExperiment object.
#'
#' @param sce_mapped SingleCellExperiment returned by CARD_SCMapping()
#' @return List with counts, coordinates, cell_types, and spot_ids
#' @export
extract_mapped_data <- function(sce_mapped) {
  if (!requireNamespace("SingleCellExperiment", quietly = TRUE)) {
    stop("SingleCellExperiment package required.")
  }

  if (!is(sce_mapped, "SingleCellExperiment")) {
    stop("Input must be a SingleCellExperiment object.")
  }

  # Extract counts
  counts <- SingleCellExperiment::counts(sce_mapped)

  # Extract coordinates from colData
  col_data <- SummarizedExperiment::colData(sce_mapped)

  coords <- NULL
  if (all(c("x", "y") %in% colnames(col_data))) {
    coords <- data.frame(
      x = col_data$x,
      y = col_data$y,
      row.names = colnames(sce_mapped)
    )
  }

  # Extract cell types
  cell_types <- NULL
  if ("cellType" %in% colnames(col_data)) {
    cell_types <- col_data$cellType
    names(cell_types) <- colnames(sce_mapped)
  }

  # Extract spot IDs if available
  spot_ids <- NULL
  if ("spotID" %in% colnames(col_data)) {
    spot_ids <- col_data$spotID
    names(spot_ids) <- colnames(sce_mapped)
  }

  list(
    counts = counts,
    coordinates = coords,
    cell_types = cell_types,
    spot_ids = spot_ids,
    n_cells = ncol(sce_mapped),
    n_genes = nrow(sce_mapped)
  )
}

#' Export Mapped Single Cells
#'
#' Save mapped single-cell data to files including counts, coordinates,
#' and cell type annotations.
#'
#' @param sce_mapped SingleCellExperiment returned by CARD_SCMapping()
#' @param output_dir Output directory path
#' @param prefix File prefix (default: "card_mapped")
#' @param export_counts Export count matrix as CSV (default: TRUE)
#' @param export_metadata Export metadata as CSV (default: TRUE)
#' @param export_object Save SCE object as RDS (default: TRUE)
#' @return Character vector of exported file paths
#' @export
export_mapped_cells <- function(
    sce_mapped,
    output_dir,
    prefix = "card_mapped",
    export_counts = TRUE,
    export_metadata = TRUE,
    export_object = TRUE
) {
  if (!requireNamespace("SingleCellExperiment", quietly = TRUE)) {
    stop("SingleCellExperiment package required.")
  }

  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  exported <- character()
  extracted <- extract_mapped_data(sce_mapped)

  # Export counts (sparse-friendly: write as sparse if large)
  if (export_counts) {
    counts_file <- file.path(output_dir, sprintf("%s_counts.csv", prefix))

    if (nrow(extracted$counts) * ncol(extracted$counts) > 1e7) {
      # For large matrices, save as RDS instead of CSV
      counts_file <- file.path(output_dir, sprintf("%s_counts.rds", prefix))
      saveRDS(extracted$counts, counts_file)
    } else {
      write.csv(as.matrix(extracted$counts), counts_file)
    }
    exported <- c(exported, counts_file)
  }

  # Export metadata
  if (export_metadata) {
    meta_df <- data.frame(
      cell_id = colnames(sce_mapped),
      stringsAsFactors = FALSE
    )

    if (!is.null(extracted$cell_types)) {
      meta_df$cell_type <- extracted$cell_types
    }

    if (!is.null(extracted$spot_ids)) {
      meta_df$spot_id <- extracted$spot_ids
    }

    if (!is.null(extracted$coordinates)) {
      meta_df$x <- extracted$coordinates$x
      meta_df$y <- extracted$coordinates$y
    }

    meta_file <- file.path(output_dir, sprintf("%s_metadata.csv", prefix))
    write.csv(meta_df, meta_file, row.names = FALSE)
    exported <- c(exported, meta_file)
  }

  # Export object
  if (export_object) {
    obj_file <- file.path(output_dir, sprintf("%s_object.rds", prefix))
    saveRDS(sce_mapped, obj_file)
    exported <- c(exported, obj_file)
  }

  cat(sprintf("Exported %d mapped cell file(s) to: %s/\n", length(exported), output_dir))
  invisible(exported)
}

#' Summarize Mapped Cell Distribution
#'
#' Generate summary statistics about the spatial distribution of mapped cells.
#'
#' @param sce_mapped SingleCellExperiment returned by CARD_SCMapping()
#' @return List with distribution statistics
#' @export
summarize_mapped_distribution <- function(sce_mapped) {
  extracted <- extract_mapped_data(sce_mapped)

  if (is.null(extracted$cell_types)) {
    stop("No cell type information found in mapped object.")
  }

  # Cell type counts
  ct_counts <- table(extracted$cell_types)
  ct_props <- prop.table(ct_counts)

  # Per-spot statistics
  if (!is.null(extracted$spot_ids)) {
    spot_ct <- table(extracted$spot_ids, extracted$cell_types)
    spot_diversity <- apply(spot_ct, 1, function(x) sum(x > 0))

    spot_stats <- list(
      mean_cell_types_per_spot = mean(spot_diversity),
      max_cell_types_per_spot = max(spot_diversity),
      min_cell_types_per_spot = min(spot_diversity)
    )
  } else {
    spot_stats <- NULL
  }

  # Spatial extent
  if (!is.null(extracted$coordinates)) {
    spatial_range <- list(
      x_range = range(extracted$coordinates$x, na.rm = TRUE),
      y_range = range(extracted$coordinates$y, na.rm = TRUE),
      n_unique_x = length(unique(extracted$coordinates$x)),
      n_unique_y = length(unique(extracted$coordinates$y))
    )
  } else {
    spatial_range <- NULL
  }

  list(
    n_cells = extracted$n_cells,
    n_genes = extracted$n_genes,
    n_cell_types = length(ct_counts),
    cell_type_counts = sort(ct_counts, decreasing = TRUE),
    cell_type_proportions = sort(ct_props, decreasing = TRUE),
    spot_stats = spot_stats,
    spatial_range = spatial_range
  )
}

#' Validate Mapping Parameters
#'
#' Check that mapping parameters are appropriate for the technology
#' and dataset size before running CARD_SCMapping.
#'
#' @param CARD_object CARD object
#' @param numCell Number of cells per spot
#' @param ncore Number of cores
#' @param technology Optional technology hint: "Visium", "ST", "Slide-seq" (default: NULL)
#' @return List with validation results and recommendations
#' @export
validate_mapping_params <- function(
    CARD_object,
    numCell = 5,
    ncore = 10,
    technology = NULL
) {
  warnings <- c()
  info <- c()

  n_spots <- nrow(CARD_object@Proportion_CARD)
  estimated_cells <- n_spots * numCell

  # Technology-specific recommendations
  if (!is.null(technology)) {
    tech_recs <- list(
      Visium = 7,
      ST = 20,
      `Slide-seq` = 2
    )

    if (technology %in% names(tech_recs)) {
      rec <- tech_recs[[technology]]
      if (numCell != rec) {
        warnings <- c(warnings,
                      sprintf("For %s, recommended numCell is %d (you have %d)",
                              technology, rec, numCell))
      } else {
        info <- c(info, sprintf("numCell (%d) matches %s recommendation.", numCell, technology))
      }
    }
  }

  # Dataset size warnings
  if (estimated_cells > 50000) {
    warnings <- c(warnings,
                  sprintf("Estimated %d mapped cells may require significant memory. Consider reducing numCell.",
                          estimated_cells))
  }

  if (ncore > parallel::detectCores()) {
    warnings <- c(warnings,
                  sprintf("ncore (%d) exceeds available cores (%d).",
                          ncore, parallel::detectCores()))
  }

  # Check deconvolution results
  if (is.null(CARD_object@Proportion_CARD) || length(CARD_object@Proportion_CARD) == 0) {
    stop("CARD object missing deconvolution results. Run CARD_deconvolution() first.")
  }

  list(
    valid = TRUE,
    warnings = warnings,
    info = info,
    n_spots = n_spots,
    numCell = numCell,
    estimated_cells = estimated_cells,
    ncore = ncore
  )
}

#' Create Spatial Plot of Mapped Cells
#'
#' Generate a ggplot scatter plot showing mapped single cells colored by cell type.
#'
#' @param sce_mapped SingleCellExperiment returned by CARD_SCMapping()
#' @param cell_types Cell types to include (NULL = all)
#' @param pointSize Point size (default: 0.5)
#' @param alpha Point transparency (default: 0.6)
#' @return ggplot object
#' @export
plot_mapped_cells <- function(
    sce_mapped,
    cell_types = NULL,
    pointSize = 0.5,
    alpha = 0.6
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting.")
  }

  extracted <- extract_mapped_data(sce_mapped)

  if (is.null(extracted$coordinates)) {
    stop("No coordinate information found in mapped object.")
  }

  if (is.null(extracted$cell_types)) {
    stop("No cell type information found in mapped object.")
  }

  plot_data <- data.frame(
    x = extracted$coordinates$x,
    y = extracted$coordinates$y,
    cell_type = extracted$cell_types,
    stringsAsFactors = FALSE
  )

  # Filter cell types if requested
  if (!is.null(cell_types)) {
    plot_data <- plot_data[plot_data$cell_type %in% cell_types, ]
    if (nrow(plot_data) == 0) {
      stop("No cells match the requested cell types.")
    }
  }

  ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = cell_type)) +
    ggplot2::geom_point(size = pointSize, alpha = alpha) +
    ggplot2::coord_fixed() +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      title = "Mapped Single Cells",
      x = "X",
      y = "Y",
      color = "Cell Type"
    ) +
    ggplot2::theme(
      legend.position = "right",
      plot.title = ggplot2::element_text(hjust = 0.5)
    )
}
