#' Core Analysis Pipeline for CARD Deconvolution
#'
#' End-to-end pipeline functions that orchestrate the complete CARD workflow
#' from data validation through deconvolution, optional imputation, and export.
#'
#' @author Yang Guo
#' @date 2026-04-20

#' Run Complete CARD Pipeline
#'
#' Execute the full CARD analysis workflow including data validation,
#' object creation, deconvolution, optional high-resolution imputation,
#' visualization, and result export.
#'
#' @param sc_count Single-cell count matrix (genes x cells)
#' @param sc_meta Single-cell metadata data.frame with cell_type and sample columns
#' @param spatial_count Spatial count matrix (genes x spots)
#' @param spatial_location Spatial coordinates data.frame with x, y columns
#' @param ct.varname Column name for cell type in sc_meta (default: "cell_type")
#' @param ct.select Cell types to include (NULL = all)
#' @param sample.varname Column name for sample info in sc_meta (NULL = single sample)
#' @param minCountGene Minimum count per gene for filtering (default: 100)
#' @param minCountSpot Minimum count per spot for filtering (default: 5)
#' @param run_imputation Whether to run high-resolution imputation (default: FALSE)
#' @param NumGrids Approximate number of grid points for imputation (default: 2000)
#' @param ineibor Number of neighbors for imputation (default: 10)
#' @param output_dir Directory to save results (NULL = no export)
#' @param prefix File prefix for output files (default: "card")
#' @param create_plots Whether to generate summary plots (default: TRUE)
#' @param verbose Print progress messages (default: TRUE)
#' @return List containing CARD_obj, summary, and file paths
#' @export
run_card_pipeline <- function(
    sc_count,
    sc_meta,
    spatial_count,
    spatial_location,
    ct.varname = "cell_type",
    ct.select = NULL,
    sample.varname = NULL,
    minCountGene = 100,
    minCountSpot = 5,
    run_imputation = FALSE,
    NumGrids = 2000,
    ineibor = 10,
    output_dir = NULL,
    prefix = "card",
    create_plots = TRUE,
    verbose = TRUE
) {
  if (!requireNamespace("CARD", quietly = TRUE)) {
    stop("Package 'CARD' is required. Install with:\n",
         "  devtools::install_github('YingMa0107/CARD')")
  }

  library(CARD)

  # Source dependencies
  script_dir <- dirname(sys.frame(1)$ofile)
  if (!is.null(script_dir) && file.exists(file.path(script_dir, "utils.R"))) {
    source(file.path(script_dir, "utils.R"))
  }
  if (!is.null(script_dir) && file.exists(file.path(script_dir, "visualization.R"))) {
    source(file.path(script_dir, "visualization.R"))
  }

  results <- list(
    CARD_obj = NULL,
    summary = NULL,
    output_files = character(),
    success = FALSE
  )

  tryCatch({
    # ============================================================================
    # Step 1: Data Validation
    # ============================================================================
    if (verbose) {
      cat("========================================\n")
      cat("CARD Pipeline\n")
      cat("========================================\n\n")
      cat("Step 1: Validating input data...\n")
    }

    validation <- validate_card_data(
      sc_count = sc_count,
      spatial_count = spatial_count,
      spatial_location = spatial_location,
      sc_meta = sc_meta,
      min_cells = 20,
      min_genes = 100
    )

    if (verbose) {
      print_validation_results(validation)
    }

    if (!validation$valid) {
      stop("Data validation failed. Please check errors above.")
    }
    if (verbose) cat("\n")

    # ============================================================================
    # Step 2: Create CARD Object
    # ============================================================================
    if (verbose) {
      cat("Step 2: Creating CARD object...\n")
      cat(sprintf("  Cell types: %s\n",
                  ifelse(is.null(ct.select), "all", paste(ct.select, collapse = ", "))))
    }

    CARD_obj <- createCARDObject(
      sc_count = sc_count,
      sc_meta = sc_meta,
      spatial_count = spatial_count,
      spatial_location = spatial_location,
      ct.varname = ct.varname,
      ct.select = ct.select,
      sample.varname = sample.varname,
      minCountGene = minCountGene,
      minCountSpot = minCountSpot
    )

    if (verbose) {
      cat(sprintf("  CARD object created (%d spots x %d cell types)\n\n",
                  ncol(CARD_obj@spatial_countMat),
                  length(CARD_obj@info_parameters$ct.select)))
    }

    # ============================================================================
    # Step 3: Run Deconvolution
    # ============================================================================
    if (verbose) {
      cat("Step 3: Running CARD deconvolution...\n")
      cat("  (This may take several minutes for large datasets)\n")
    }

    CARD_obj <- CARD_deconvolution(CARD_obj)

    proportions <- CARD_obj@Proportion_CARD

    if (verbose) {
      cat(sprintf("  Deconvolution complete!\n"))
      cat(sprintf("  Optimal phi: %.3f\n", CARD_obj@info_parameters$phi))
      cat(sprintf("  Proportions: %d spots x %d cell types\n\n",
                  nrow(proportions), ncol(proportions)))
    }

    # ============================================================================
    # Step 4: Optional Imputation
    # ============================================================================
    if (run_imputation) {
      if (verbose) {
        cat("Step 4: Running high-resolution imputation...\n")
        cat(sprintf("  NumGrids: %d, ineibor: %d\n", NumGrids, ineibor))
      }

      if (requireNamespace("concaveman", quietly = TRUE)) {
        CARD_obj <- CARD.imputation(
          CARD_obj,
          NumGrids = NumGrids,
          ineibor = ineibor,
          exclude = NULL
        )

        if (verbose) {
          cat(sprintf("  Imputation complete!\n"))
          cat(sprintf("  Refined spots: %d\n", nrow(CARD_obj@refined_prop)))
          cat(sprintf("  Refined genes: %d\n\n", nrow(CARD_obj@refined_expression)))
        }
      } else {
        warning("concaveman not available. Skipping imputation. ",
                "Install with: install.packages('concaveman')")
        if (verbose) cat("  SKIPPED (concaveman not available)\n\n")
      }
    }

    # ============================================================================
    # Step 5: Summary
    # ============================================================================
    if (verbose) cat("Step 5: Generating summary...\n")

    summary <- summarize_card_results(CARD_obj)
    results$summary <- summary

    if (verbose) {
      cat(sprintf("  Spots: %d\n", summary$n_spots))
      cat(sprintf("  Cell types: %d\n", summary$n_cell_types))
      cat(sprintf("  Optimal phi: %.3f\n", summary$optimal_phi))
      cat(sprintf("  Mean entropy: %.3f\n", summary$mean_entropy))
      cat("\n")
    }

    # ============================================================================
    # Step 6: Optional Plots
    # ============================================================================
    if (create_plots && !is.null(output_dir)) {
      if (verbose) cat("Step 6: Creating plots...\n")

      if (requireNamespace("ggplot2", quietly = TRUE)) {
        plot_dir <- file.path(output_dir, "plots")
        dir.create(plot_dir, showWarnings = FALSE, recursive = TRUE)

        # Mean proportions barplot
        tryCatch({
          p <- plot_mean_proportions(CARD_obj)
          ggplot2::ggsave(
            file.path(plot_dir, sprintf("%s_mean_proportions.png", prefix)),
            p, width = 8, height = 6
          )
          results$output_files <- c(results$output_files,
            file.path(plot_dir, sprintf("%s_mean_proportions.png", prefix)))
          if (verbose) cat("  - mean_proportions.png\n")
        }, error = function(e) {
          if (verbose) cat("  - mean_proportions.png FAILED\n")
        })

        # Dominant distribution
        tryCatch({
          p <- plot_dominant_distribution(CARD_obj)
          ggplot2::ggsave(
            file.path(plot_dir, sprintf("%s_dominant_distribution.png", prefix)),
            p, width = 8, height = 6
          )
          results$output_files <- c(results$output_files,
            file.path(plot_dir, sprintf("%s_dominant_distribution.png", prefix)))
          if (verbose) cat("  - dominant_distribution.png\n")
        }, error = function(e) {
          if (verbose) cat("  - dominant_distribution.png FAILED\n")
        })

        # Spatial entropy
        tryCatch({
          p <- plot_spatial_entropy(CARD_obj)
          ggplot2::ggsave(
            file.path(plot_dir, sprintf("%s_spatial_entropy.png", prefix)),
            p, width = 8, height = 7
          )
          results$output_files <- c(results$output_files,
            file.path(plot_dir, sprintf("%s_spatial_entropy.png", prefix)))
          if (verbose) cat("  - spatial_entropy.png\n")
        }, error = function(e) {
          if (verbose) cat("  - spatial_entropy.png FAILED\n")
        })

        # Native CARD spatial proportion maps
        tryCatch({
          ct_to_plot <- colnames(proportions)[1:min(4, ncol(proportions))]
          p <- CARD.visualize.prop(
            proportion = proportions,
            spatial_location = spatial_location,
            ct.visualize = ct_to_plot,
            colors = c("lightblue", "lightyellow", "red"),
            NumCols = 2,
            pointSize = 3.0
          )
          ggplot2::ggsave(
            file.path(plot_dir, sprintf("%s_spatial_maps.png", prefix)),
            p, width = 12, height = 10
          )
          results$output_files <- c(results$output_files,
            file.path(plot_dir, sprintf("%s_spatial_maps.png", prefix)))
          if (verbose) cat("  - spatial_maps.png\n")
        }, error = function(e) {
          if (verbose) cat("  - spatial_maps.png FAILED\n")
        })

        if (verbose) cat("\n")
      } else {
        warning("ggplot2 not available. Skipping plot generation.")
        if (verbose) cat("  SKIPPED (ggplot2 not available)\n\n")
      }
    }

    # ============================================================================
    # Step 7: Export Results
    # ============================================================================
    if (!is.null(output_dir)) {
      if (verbose) cat("Step 7: Exporting results...\n")

      dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

      export_card_results(
        CARD_obj,
        output_dir = output_dir,
        prefix = prefix,
        export_proportions = TRUE,
        export_refined = run_imputation && length(CARD_obj@refined_prop) > 0,
        export_object = TRUE
      )

      results$output_files <- c(results$output_files,
        file.path(output_dir, sprintf("%s_proportions.csv", prefix)),
        file.path(output_dir, sprintf("%s_results.csv", prefix)),
        file.path(output_dir, sprintf("%s_object.rds", prefix))
      )

      if (run_imputation && length(CARD_obj@refined_prop) > 0) {
        results$output_files <- c(results$output_files,
          file.path(output_dir, sprintf("%s_refined_proportions.csv", prefix))
        )
      }

      # Export summary as text
      summary_file <- file.path(output_dir, sprintf("%s_summary.txt", prefix))
      writeLines(
        c(
          "CARD Analysis Summary",
          "=====================",
          "",
          sprintf("Spots analyzed: %d", summary$n_spots),
          sprintf("Cell types: %d", summary$n_cell_types),
          sprintf("Optimal phi: %.4f", summary$optimal_phi),
          sprintf("Mean entropy: %.4f", summary$mean_entropy),
          "",
          "Cell type proportions (mean):",
          paste(names(summary$mean_proportions),
                round(summary$mean_proportions, 4),
                sep = ": ",
                collapse = "\n"),
          "",
          "Dominant cell types:",
          paste(names(summary$dominant_cell_types),
                summary$dominant_cell_types,
                sep = ": ",
                collapse = "\n")
        ),
        summary_file
      )
      results$output_files <- c(results$output_files, summary_file)

      if (verbose) {
        cat(sprintf("  Results saved to: %s/\n", output_dir))
        cat("\n")
      }
    }

    results$CARD_obj <- CARD_obj
    results$success <- TRUE

    if (verbose) {
      cat("========================================\n")
      cat("Pipeline completed successfully!\n")
      cat("========================================\n")
    }

  }, error = function(e) {
    results$success <- FALSE
    results$error <- conditionMessage(e)
    if (verbose) {
      cat("\n========================================\n")
      cat("Pipeline failed:\n")
      cat(conditionMessage(e), "\n")
      cat("========================================\n")
    }
  })

  invisible(results)
}

#' Create Extended CARD Object
#'
#' Enhanced wrapper around createCARDObject with additional validation,
#' automatic cell type filtering, and informative error messages.
#'
#' @param sc_count Single-cell count matrix (genes x cells)
#' @param sc_meta Single-cell metadata data.frame
#' @param spatial_count Spatial count matrix (genes x spots)
#' @param spatial_location Spatial coordinates data.frame
#' @param ct.varname Column name for cell type (default: "cell_type")
#' @param ct.select Cell types to include (NULL = all)
#' @param sample.varname Column name for sample info (NULL = single sample)
#' @param minCountGene Minimum count per gene (default: 100)
#' @param minCountSpot Minimum count per spot (default: 5)
#' @param min_cells_per_type Minimum cells required per cell type (default: 20)
#' @param auto_filter_low_count Whether to auto-filter cell types below min_cells_per_type (default: TRUE)
#' @param verbose Print messages (default: TRUE)
#' @return CARD object
#' @export
create_card_object_extended <- function(
    sc_count,
    sc_meta,
    spatial_count,
    spatial_location,
    ct.varname = "cell_type",
    ct.select = NULL,
    sample.varname = NULL,
    minCountGene = 100,
    minCountSpot = 5,
    min_cells_per_type = 20,
    auto_filter_low_count = TRUE,
    verbose = TRUE
) {
  if (!requireNamespace("CARD", quietly = TRUE)) {
    stop("Package 'CARD' is required. Install with:\n",
         "  devtools::install_github('YingMa0107/CARD')")
  }

  library(CARD)

  # Validate data first
  validation <- validate_card_data(
    sc_count = sc_count,
    spatial_count = spatial_count,
    spatial_location = spatial_location,
    sc_meta = sc_meta,
    min_cells = min_cells_per_type,
    min_genes = 100
  )

  if (!validation$valid) {
    stop("Data validation failed:\n",
         paste("  -", validation$errors, collapse = "\n"))
  }

  if (length(validation$warnings) > 0 && verbose) {
    cat("Warnings:\n")
    for (w in validation$warnings) {
      cat(sprintf("  - %s\n", w))
    }
    cat("\n")
  }

  # Auto-filter low-count cell types if requested
  if (auto_filter_low_count && !is.null(sc_meta) && ct.varname %in% colnames(sc_meta)) {
    ct_counts <- table(sc_meta[[ct.varname]])
    low_ct <- names(ct_counts)[ct_counts < min_cells_per_type]

    if (length(low_ct) > 0) {
      if (verbose) {
        cat(sprintf("Filtering out cell types with <%d cells: %s\n",
                    min_cells_per_type, paste(low_ct, collapse = ", ")))
      }

      keep_cells <- which(!sc_meta[[ct.varname]] %in% low_ct)
      sc_count <- sc_count[, keep_cells, drop = FALSE]
      sc_meta <- sc_meta[keep_cells, , drop = FALSE]

      # Update ct.select to remove filtered types
      if (!is.null(ct.select)) {
        ct.select <- setdiff(ct.select, low_ct)
        if (length(ct.select) == 0) {
          stop("All selected cell types were filtered out due to insufficient cells.")
        }
      }
    }
  }

  if (verbose) {
    cat("Creating CARD object...\n")
    if (!is.null(ct.select)) {
      cat(sprintf("  Selected cell types: %s\n", paste(ct.select, collapse = ", ")))
    }
  }

  CARD_obj <- createCARDObject(
    sc_count = sc_count,
    sc_meta = sc_meta,
    spatial_count = spatial_count,
    spatial_location = spatial_location,
    ct.varname = ct.varname,
    ct.select = ct.select,
    sample.varname = sample.varname,
    minCountGene = minCountGene,
    minCountSpot = minCountSpot
  )

  if (verbose) {
    cat(sprintf("  Object created: %d spots x %d cell types\n",
                ncol(CARD_obj@spatial_countMat),
                length(CARD_obj@info_parameters$ct.select)))
  }

  invisible(CARD_obj)
}

#' Run Reference-Free CARD Pipeline (CARDfree)
#'
#' Complete pipeline for reference-free deconvolution using marker genes only.
#'
#' @param markerList Named list of marker genes per cell type
#' @param spatial_count Spatial count matrix (genes x spots)
#' @param spatial_location Spatial coordinates data.frame
#' @param minCountGene Minimum count per gene (default: 100)
#' @param minCountSpot Minimum count per spot (default: 5)
#' @param output_dir Directory to save results (NULL = no export)
#' @param prefix File prefix (default: "cardfree")
#' @param verbose Print progress messages (default: TRUE)
#' @return List containing CARDfree_obj, summary, and file paths
#' @export
run_cardfree_pipeline <- function(
    markerList,
    spatial_count,
    spatial_location,
    minCountGene = 100,
    minCountSpot = 5,
    output_dir = NULL,
    prefix = "cardfree",
    verbose = TRUE
) {
  if (!requireNamespace("CARD", quietly = TRUE)) {
    stop("Package 'CARD' is required. Install with:\n",
         "  devtools::install_github('YingMa0107/CARD')")
  }

  library(CARD)

  results <- list(
    CARDfree_obj = NULL,
    output_files = character(),
    success = FALSE
  )

  tryCatch({
    if (verbose) {
      cat("========================================\n")
      cat("CARDfree Pipeline (Reference-Free)\n")
      cat("========================================\n\n")
      cat("Step 1: Creating CARDfree object...\n")
      cat(sprintf("  Cell types: %d\n", length(markerList)))
      cat(sprintf("  Spatial data: %d genes x %d spots\n\n",
                  nrow(spatial_count), ncol(spatial_count)))
    }

    # Validate marker list
    if (length(markerList) == 0) {
      stop("markerList cannot be empty.")
    }

    for (ct in names(markerList)) {
      if (length(markerList[[ct]]) == 0) {
        stop(sprintf("Marker list for '%s' is empty.", ct))
      }
    }

    # Validate spatial data
    if (ncol(spatial_count) != nrow(spatial_location)) {
      stop("spatial_count columns must match spatial_location rows.")
    }

    if (!all(c("x", "y") %in% colnames(spatial_location))) {
      stop("spatial_location must have 'x' and 'y' columns.")
    }

    CARDfree_obj <- createCARDfreeObject(
      markerList = markerList,
      spatial_count = spatial_count,
      spatial_location = spatial_location,
      minCountGene = minCountGene,
      minCountSpot = minCountSpot
    )

    if (verbose) {
      cat("Step 2: Running reference-free deconvolution...\n")
    }

    CARDfree_obj <- CARD_refFree(CARDfree_obj)

    proportions <- CARDfree_obj@Proportion_CARD

    if (verbose) {
      cat(sprintf("  Deconvolution complete!\n"))
      cat(sprintf("  Optimal phi: %.3f\n", CARDfree_obj@info_parameters$phi))
      cat(sprintf("  Estimated reference: %s\n\n",
                  paste(dim(CARDfree_obj@estimated_refMatrix), collapse = " x ")))
    }

    # Export results
    if (!is.null(output_dir)) {
      dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

      write.csv(proportions,
                file.path(output_dir, sprintf("%s_proportions.csv", prefix)))

      results_df <- data.frame(
        spot = rownames(spatial_location),
        spatial_location,
        proportions,
        row.names = NULL
      )
      write.csv(results_df,
                file.path(output_dir, sprintf("%s_results.csv", prefix)),
                row.names = FALSE)

      saveRDS(CARDfree_obj,
              file.path(output_dir, sprintf("%s_object.rds", prefix)))

      results$output_files <- c(results$output_files,
        file.path(output_dir, sprintf("%s_proportions.csv", prefix)),
        file.path(output_dir, sprintf("%s_results.csv", prefix)),
        file.path(output_dir, sprintf("%s_object.rds", prefix))
      )

      if (verbose) {
        cat(sprintf("  Results saved to: %s/\n", output_dir))
      }
    }

    results$CARDfree_obj <- CARDfree_obj
    results$success <- TRUE

    if (verbose) {
      cat("\n========================================\n")
      cat("CARDfree pipeline completed successfully!\n")
      cat("========================================\n")
    }

  }, error = function(e) {
    results$success <- FALSE
    results$error <- conditionMessage(e)
    if (verbose) {
      cat("\n========================================\n")
      cat("CARDfree pipeline failed:\n")
      cat(conditionMessage(e), "\n")
      cat("========================================\n")
    }
  })

  invisible(results)
}
