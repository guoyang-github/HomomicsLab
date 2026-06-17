#' High-Resolution Imputation Functions for CARD
#'
#' Wrapper and helper functions for CARD.imputation() that add parameter validation,
#' progress logging, refined result extraction, and convenient export utilities.
#'
#' @author Yang Guo
#' @date 2026-04-20

#' Run CARD High-Resolution Imputation
#'
#' Wrapper around CARD::CARD.imputation() with additional validation,
#' error handling, and progress reporting.
#'
#' @param CARD_object CARD object with deconvolution results
#' @param NumGrids Approximate number of new grid locations (default: 2000)
#' @param ineibor Number of neighbors for imputation (default: 10)
#' @param concavity Concavity parameter for shape detection (default: 2.0)
#' @param exclude Spots to exclude from shape detection (default: NULL)
#' @param verbose Print progress messages (default: TRUE)
#' @return CARD object with refined_prop and refined_expression slots populated
#' @export
run_card_imputation <- function(
    CARD_object,
    NumGrids = 2000,
    ineibor = 10,
    concavity = 2.0,
    exclude = NULL,
    verbose = TRUE
) {
  if (!requireNamespace("CARD", quietly = TRUE)) {
    stop("Package 'CARD' is required. Install with:\n",
         "  devtools::install_github('YingMa0107/CARD')")
  }

  if (!requireNamespace("concaveman", quietly = TRUE)) {
    stop("Package 'concaveman' is required for imputation. Install with:\n",
         "  install.packages('concaveman')")
  }

  # Validate CARD object
  if (is.null(CARD_object@Proportion_CARD) || length(CARD_object@Proportion_CARD) == 0) {
    stop("CARD object does not contain deconvolution results. ",
         "Run CARD_deconvolution() before imputation.")
  }

  if (verbose) {
    cat("Running CARD high-resolution imputation...\n")
    cat(sprintf("  Original spots: %d\n", nrow(CARD_object@Proportion_CARD)))
    cat(sprintf("  Target grids: ~%d\n", NumGrids))
    cat(sprintf("  Neighbors: %d\n", ineibor))
    cat("  (This may take several minutes)\n\n")
  }

  start_time <- Sys.time()

  tryCatch({
    CARD_object <- CARD.imputation(
      CARD_object,
      NumGrids = NumGrids,
      ineibor = ineibor,
      exclude = exclude
    )

    elapsed <- difftime(Sys.time(), start_time, units = "secs")

    if (verbose) {
      cat(sprintf("Imputation complete! (%.1f seconds)\n", as.numeric(elapsed)))
      cat(sprintf("  Refined spots: %d\n", nrow(CARD_object@refined_prop)))
      cat(sprintf("  Refined genes: %d\n", nrow(CARD_object@refined_expression)))
      cat(sprintf("  Cell types: %d\n", ncol(CARD_object@refined_prop)))
    }

    invisible(CARD_object)

  }, error = function(e) {
    stop(sprintf("Imputation failed: %s", conditionMessage(e)))
  })
}

#' Extract Refined Spatial Coordinates
#'
#' Parse row names from CARD refined proportion matrix to extract
#' x and y coordinates. CARD uses a "xxxxyyyy" naming convention
#' where coordinates are concatenated with an "x" separator.
#'
#' @param refined_prop Refined proportion matrix from CARD object
#' @return Data.frame with x, y columns and spot IDs as row names
#' @export
extract_refined_coordinates <- function(refined_prop) {
  if (is.null(refined_prop) || nrow(refined_prop) == 0) {
    stop("refined_prop is empty. Run imputation first.")
  }

  spot_ids <- rownames(refined_prop)

  # CARD uses format like "12.345x67.890" or "123x456"
  split_parts <- strsplit(spot_ids, "x")

  # Handle cases where split produces more or fewer than 2 parts
  x_vals <- sapply(split_parts, function(p) {
    if (length(p) >= 2) {
      as.numeric(p[1])
    } else {
      NA_real_
    }
  })

  y_vals <- sapply(split_parts, function(p) {
    if (length(p) >= 2) {
      as.numeric(p[2])
    } else {
      NA_real_
    }
  })

  if (any(is.na(x_vals)) || any(is.na(y_vals))) {
    warning(sprintf("Could not parse coordinates for %d spots. Check row name format.",
                    sum(is.na(x_vals) | is.na(y_vals))))
  }

  coords <- data.frame(
    x = x_vals,
    y = y_vals,
    row.names = spot_ids
  )

  invisible(coords)
}

#' Validate Imputation Results
#'
#' Check that refined proportions are valid (non-negative, approximately sum to 1).
#'
#' @param CARD_object CARD object with imputation results
#' @param tol Tolerance for row sum deviation from 1 (default: 0.01)
#' @return List with validation results
#' @export
validate_imputation_results <- function(CARD_object, tol = 0.01) {
  if (is.null(CARD_object@refined_prop) || length(CARD_object@refined_prop) == 0) {
    return(list(valid = FALSE, errors = "No refined proportions found. Run imputation first."))
  }

  errors <- c()
  warnings <- c()

  refined <- CARD_object@refined_prop

  # Check non-negative
  if (any(refined < -tol)) {
    errors <- c(errors,
                sprintf("Found %d negative proportion values", sum(refined < -tol)))
  }

  # Check row sums
  row_sums <- rowSums(refined)
  bad_sums <- which(abs(row_sums - 1) > tol)
  if (length(bad_sums) > 0) {
    warnings <- c(warnings,
                  sprintf("%d refined spots have proportions not summing to 1 (tolerance: %.3f)",
                          length(bad_sums), tol))
  }

  # Check expression matrix
  if (is.null(CARD_object@refined_expression) ||
      length(CARD_object@refined_expression) == 0) {
    warnings <- c(warnings, "No refined expression matrix found.")
  } else {
    expr <- CARD_object@refined_expression
    if (ncol(expr) != nrow(refined)) {
      errors <- c(errors,
                  sprintf("Refined expression columns (%d) do not match refined spots (%d)",
                          ncol(expr), nrow(refined)))
    }
    if (any(expr < 0)) {
      warnings <- c(warnings, "Refined expression contains negative values.")
    }
  }

  list(
    valid = length(errors) == 0,
    errors = errors,
    warnings = warnings,
    n_refined_spots = nrow(refined),
    n_cell_types = ncol(refined),
    n_genes = ifelse(is.null(CARD_object@refined_expression), 0,
                     nrow(CARD_object@refined_expression)),
    mean_row_sum = mean(row_sums),
    max_row_sum_deviation = max(abs(row_sums - 1))
  )
}

#' Export Refined Imputation Results
#'
#' Save high-resolution refined proportions and expression to files.
#'
#' @param CARD_object CARD object with imputation results
#' @param output_dir Output directory path
#' @param prefix File prefix (default: "card_refined")
#' @param export_proportions Export refined proportion matrix (default: TRUE)
#' @param export_expression Export refined expression matrix (default: TRUE)
#' @param export_coordinates Export refined coordinates (default: TRUE)
#' @return Character vector of exported file paths
#' @export
export_refined_results <- function(
    CARD_object,
    output_dir,
    prefix = "card_refined",
    export_proportions = TRUE,
    export_expression = TRUE,
    export_coordinates = TRUE
) {
  if (is.null(CARD_object@refined_prop) || length(CARD_object@refined_prop) == 0) {
    stop("No refined results found. Run imputation first.")
  }

  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  exported <- character()

  # Export proportions
  if (export_proportions) {
    prop_file <- file.path(output_dir, sprintf("%s_proportions.csv", prefix))
    write.csv(CARD_object@refined_prop, prop_file)
    exported <- c(exported, prop_file)
  }

  # Export expression
  if (export_expression && !is.null(CARD_object@refined_expression) &&
      length(CARD_object@refined_expression) > 0) {
    expr_file <- file.path(output_dir, sprintf("%s_expression.csv", prefix))
    write.csv(CARD_object@refined_expression, expr_file)
    exported <- c(exported, expr_file)
  }

  # Export coordinates
  if (export_coordinates) {
    coords <- tryCatch({
      extract_refined_coordinates(CARD_object@refined_prop)
    }, error = function(e) {
      warning("Could not extract refined coordinates: ", conditionMessage(e))
      NULL
    })

    if (!is.null(coords)) {
      coords_file <- file.path(output_dir, sprintf("%s_coordinates.csv", prefix))
      write.csv(coords, coords_file)
      exported <- c(exported, coords_file)
    }
  }

  cat(sprintf("Exported %d refined result file(s) to: %s/\n", length(exported), output_dir))
  invisible(exported)
}

#' Compare Original and Refined Proportions
#'
#' Compute summary statistics comparing original spot-level proportions
#' with high-resolution refined proportions.
#'
#' @param CARD_object CARD object with both deconvolution and imputation results
#' @return Data.frame with comparison statistics per cell type
#' @export
compare_refined_proportions <- function(CARD_object) {
  if (is.null(CARD_object@Proportion_CARD) || length(CARD_object@Proportion_CARD) == 0) {
    stop("No original proportions found.")
  }
  if (is.null(CARD_object@refined_prop) || length(CARD_object@refined_prop) == 0) {
    stop("No refined proportions found. Run imputation first.")
  }

  orig <- CARD_object@Proportion_CARD
  refined <- CARD_object@refined_prop

  # Ensure same cell types
  common_ct <- intersect(colnames(orig), colnames(refined))
  if (length(common_ct) == 0) {
    stop("No common cell types between original and refined proportions.")
  }

  orig <- orig[, common_ct, drop = FALSE]
  refined <- refined[, common_ct, drop = FALSE]

  stats <- data.frame(
    cell_type = common_ct,
    original_mean = colMeans(orig),
    refined_mean = colMeans(refined),
    original_max = apply(orig, 2, max),
    refined_max = apply(refined, 2, max),
    original_sd = apply(orig, 2, sd),
    refined_sd = apply(refined, 2, sd),
    stringsAsFactors = FALSE
  )

  stats$mean_diff <- stats$refined_mean - stats$original_mean
  stats$refinement_factor <- nrow(refined) / nrow(orig)

  rownames(stats) <- NULL
  invisible(stats)
}

#' Visualize Refined Proportions
#'
#' Create spatial plots for refined (high-resolution) cell type proportions.
#' Falls back to a ggplot-based approach if CARD::CARD.visualize.prop fails.
#'
#' @param CARD_object CARD object with imputation results
#' @param ct.visualize Cell types to plot (NULL = first 4)
#' @param colors Color gradient vector (default: c("lightblue", "lightyellow", "red"))
#' @param NumCols Number of columns in faceted plot (default: 2)
#' @param pointSize Point size for ggplot fallback (default: 1.5)
#' @return ggplot object or list of plots
#' @export
visualize_refined_proportions <- function(
    CARD_object,
    ct.visualize = NULL,
    colors = c("lightblue", "lightyellow", "red"),
    NumCols = 2,
    pointSize = 1.5
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting.")
  }

  if (is.null(CARD_object@refined_prop) || length(CARD_object@refined_prop) == 0) {
    stop("No refined proportions found. Run imputation first.")
  }

  refined <- CARD_object@refined_prop
  coords <- extract_refined_coordinates(refined)

  if (is.null(ct.visualize)) {
    ct.visualize <- colnames(refined)[1:min(4, ncol(refined))]
  }

  ct.visualize <- intersect(ct.visualize, colnames(refined))
  if (length(ct.visualize) == 0) {
    stop("None of the requested cell types found in refined proportions.")
  }

  # Try native CARD visualization first
  tryCatch({
    p <- CARD.visualize.prop(
      proportion = refined[, ct.visualize, drop = FALSE],
      spatial_location = coords,
      ct.visualize = ct.visualize,
      colors = colors,
      NumCols = NumCols,
      pointSize = pointSize
    )
    return(p)
  }, error = function(e) {
    # Fallback to ggplot
    plot_data <- data.frame(
      x = coords$x,
      y = coords$y,
      refined[, ct.visualize, drop = FALSE]
    )

    plot_data_long <- stack(plot_data[, ct.visualize])
    plot_data_long$x <- rep(coords$x, length(ct.visualize))
    plot_data_long$y <- rep(coords$y, length(ct.visualize))
    colnames(plot_data_long) <- c("proportion", "cell_type", "x", "y")

    p <- ggplot2::ggplot(plot_data_long,
                         ggplot2::aes(x = x, y = y, color = proportion)) +
      ggplot2::geom_point(size = pointSize) +
      ggplot2::scale_color_gradientn(colors = colors, name = "Proportion") +
      ggplot2::facet_wrap(~cell_type, ncol = NumCols) +
      ggplot2::coord_fixed() +
      ggplot2::theme_minimal() +
      ggplot2::labs(title = "Refined Cell Type Proportions",
                    x = "X", y = "Y")

    return(p)
  })
}
