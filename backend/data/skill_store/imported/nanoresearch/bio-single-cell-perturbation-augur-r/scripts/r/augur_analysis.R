#!/usr/bin/env Rscript
#' Augur Cell Type Prioritization Analysis (R)
#'
#' R wrapper functions for Augur cell type prioritization using the original
#' neurorestore/Augur R package.
#'
#' NOTE: Augur's internal `calculate_auc()` calls `GetAssayData()` without
#' the `layer` parameter, which is incompatible with Seurat v5.
#' This skill requires Seurat v4.x.
#'
#' Augur trains machine-learning classifiers to predict perturbation labels
#' and ranks cell types by classification accuracy (AUC). Cell types with
#' higher AUC are more affected by the perturbation.
#'
#' @author Yang Guo
#' @date 2026-04-22
#' @version 1.0.0

#' Run Augur Cell Type Prioritization
#'
#' Main wrapper for complete Augur analysis pipeline. Supports Seurat,
#' monocle3, SingleCellExperiment, matrix, and data frame inputs.
#'
#' @param input A Seurat object, monocle3 cell_data_set, SingleCellExperiment,
#'   matrix, or data frame with genes in rows and cells in columns.
#' @param meta Data frame with metadata. Required for matrix/data frame input;
#'   optional for Seurat/monocle3/SCE objects.
#' @param label_col Column in metadata containing condition labels
#'   (e.g., "control", "treatment"). Default: "label"
#' @param cell_type_col Column in metadata containing cell type annotations.
#'   Default: "cell_type"
#' @param n_subsamples Number of random subsamples per cell type. Default: 50.
#'   Set to 0 to disable subsampling.
#' @param subsample_size Cells per subsample per condition. Default: 20
#' @param folds Cross-validation folds. Default: 3
#' @param min_cells Minimum cells per cell type per condition. Default: subsample_size
#' @param var_quantile Quantile for highly variable gene selection. Default: 0.5
#' @param feature_perc Proportion of genes as features per subsample. Default: 0.5
#' @param n_threads Parallel threads. Default: 4
#' @param show_progress Show progress bar. Default: TRUE
#' @param augur_mode One of "default", "velocity", "permute".
#'   "permute" generates null distribution (uses n_subsamples=500).
#'   Default: "default"
#' @param classifier One of "rf" (random forest) or "lr" (logistic regression).
#'   Default: "rf"
#' @param rf_params List of random forest parameters:
#'   trees (default: 100), mtry (default: 2), min_n (default: NULL),
#'   importance (default: "accuracy").
#' @param lr_params List of logistic regression parameters:
#'   mixture (default: 1), penalty (default: "auto").
#' @param verbose Print progress messages. Default: TRUE
#'
#' @return List of class "Augur" with:
#'   - X: expression matrix
#'   - y: condition labels
#'   - cell_types: cell type labels
#'   - parameters: analysis parameters
#'   - results: detailed CV results
#'   - feature_importance: gene importance scores
#'   - AUC: summary mean AUC per cell type (classification)
#'   - CCC: summary mean CCC per cell type (regression)
#'
#' @examples
#' \dontrun{
#' # Seurat object
#' augur <- run_augur(seurat_obj, label_col = "condition", cell_type_col = "cell_type")
#'
#' # Matrix + metadata
#' augur <- run_augur(expr_matrix, meta = meta_df, label_col = "treatment")
#'
#' # Permutation test (null distribution)
#' augur_null <- run_augur(seurat_obj, augur_mode = "permute")
#' }
#'
#' @export
run_augur <- function(
    input,
    meta = NULL,
    label_col = "label",
    cell_type_col = "cell_type",
    n_subsamples = 50,
    subsample_size = 20,
    folds = 3,
    min_cells = NULL,
    var_quantile = 0.5,
    feature_perc = 0.5,
    n_threads = 4,
    show_progress = TRUE,
    augur_mode = "default",
    classifier = "rf",
    rf_params = list(trees = 100, mtry = 2, min_n = NULL, importance = "accuracy"),
    lr_params = list(mixture = 1, penalty = "auto"),
    verbose = TRUE
) {
  if (!requireNamespace("Augur", quietly = TRUE)) {
    stop("Augur package required. Install with: devtools::install_github('neurorestore/Augur')")
  }

  # Check Seurat version compatibility (Augur uses 'slot' internally)
  if (inherits(input, "Seurat")) {
    if (!requireNamespace("SeuratObject", quietly = TRUE)) {
      stop("SeuratObject package required for Seurat version checking")
    }
    seurat_ver <- utils::packageVersion("SeuratObject")
    if (seurat_ver >= package_version("5.0.0")) {
      stop(sprintf(
        "[Augur] Seurat v%s detected. This skill requires Seurat v4.x (< 5.0.0).\n",
        "Augur's internal `calculate_auc()` calls `GetAssayData()` without ",
        "the `layer` parameter, which is incompatible with Seurat v5.\n",
        "Please use a Seurat v4 environment, or extract matrix + metadata manually:\n",
        "  expr_matrix <- Seurat::GetAssayData(seurat_obj, slot = 'data')\n",
        "  meta_df <- seurat_obj@meta.data\n",
        "  augur <- run_augur(expr_matrix, meta = meta_df, label_col = 'condition')\n",
        seurat_ver
      ))
    }
  }

  library(Augur)

  if (verbose) {
    message(sprintf("Running Augur analysis..."))
    message(sprintf("  Label column: %s", label_col))
    message(sprintf("  Cell type column: %s", cell_type_col))
    message(sprintf("  Classifier: %s", classifier))
    message(sprintf("  Subsamples: %d, Size: %d, Folds: %d", n_subsamples, subsample_size, folds))
  }

  # Run Augur
  result <- Augur::calculate_auc(
    input = input,
    meta = meta,
    label_col = label_col,
    cell_type_col = cell_type_col,
    n_subsamples = n_subsamples,
    subsample_size = subsample_size,
    folds = folds,
    min_cells = min_cells,
    var_quantile = var_quantile,
    feature_perc = feature_perc,
    n_threads = n_threads,
    show_progress = show_progress,
    augur_mode = augur_mode,
    classifier = classifier,
    rf_params = rf_params,
    lr_params = lr_params
  )

  if (verbose) {
    if ("AUC" %in% names(result)) {
      message(sprintf("  Completed: %d cell types analyzed", nrow(result$AUC)))
      message(sprintf("  Top cell type: %s (AUC = %.3f)",
                      result$AUC$cell_type[1], result$AUC$auc[1]))
    } else if ("CCC" %in% names(result)) {
      message(sprintf("  Completed: %d cell types analyzed (regression mode)", nrow(result$CCC)))
    }
  }

  result
}


#' Run Differential Prioritization
#'
#' Compare cell type prioritization between two conditions using a permutation
#' test to identify statistically significant differences in AUC.
#'
#' @param augur1 Augur results from condition 1
#' @param augur2 Augur results from condition 2
#' @param permuted1 Permuted Augur results from condition 1 (augur_mode = "permute")
#' @param permuted2 Permuted Augur results from condition 2 (augur_mode = "permute")
#' @param n_subsamples Number of subsamples to pool per permutation. Default: 50
#' @param n_permutations Total number of mean AUCs from background distribution.
#'   Default: 1000
#' @param verbose Print progress. Default: TRUE
#'
#' @return Data frame with:
#'   - cell_type, auc.x, auc.y, delta_auc
#'   - b, m, z, pval, padj
#'
#' @examples
#' \dontrun{
#' # Run Augur for two conditions
#' augur_disease <- run_augur(seurat_disease, label_col = "condition")
#' augur_control <- run_augur(seurat_control, label_col = "condition")
#'
#' # Run permuted versions
#' perm_disease <- run_augur(seurat_disease, augur_mode = "permute")
#' perm_control <- run_augur(seurat_control, augur_mode = "permute")
#'
#' # Differential prioritization
#' diff <- run_differential_prioritization(
#'   augur_disease, augur_control,
#'   perm_disease, perm_control
#' )
#' }
#'
#' @export
run_differential_prioritization <- function(
    augur1,
    augur2,
    permuted1,
    permuted2,
    n_subsamples = 50,
    n_permutations = 1000,
    verbose = TRUE
) {
  if (!requireNamespace("Augur", quietly = TRUE)) {
    stop("Augur package required.")
  }

  if (verbose) message("Running differential prioritization...")

  result <- Augur::calculate_differential_prioritization(
    augur1 = augur1,
    augur2 = augur2,
    permuted1 = permuted1,
    permuted2 = permuted2,
    n_subsamples = n_subsamples,
    n_permutations = n_permutations
  )

  if (verbose) {
    sig <- sum(result$padj < 0.05, na.rm = TRUE)
    message(sprintf("  Significant cell types (padj < 0.05): %d / %d", sig, nrow(result)))
  }

  result
}


#' Summarize Augur Results
#'
#' Generate summary statistics from Augur analysis.
#'
#' @param augur Augur result object from run_augur()
#'
#' @return List with summary statistics
#'
#' @export
summarize_augur_results <- function(augur) {
  if ("AUC" %in% names(augur)) {
    auc_df <- augur$AUC
    list(
      n_cell_types = nrow(auc_df),
      mean_auc = mean(auc_df$auc, na.rm = TRUE),
      median_auc = stats::median(auc_df$auc, na.rm = TRUE),
      min_auc = min(auc_df$auc, na.rm = TRUE),
      max_auc = max(auc_df$auc, na.rm = TRUE),
      sd_auc = stats::sd(auc_df$auc, na.rm = TRUE),
      most_affected = auc_df$cell_type[which.max(auc_df$auc)],
      least_affected = auc_df$cell_type[which.min(auc_df$auc)],
      n_strong_effect = sum(auc_df$auc >= 0.9, na.rm = TRUE),
      n_moderate_effect = sum(auc_df$auc >= 0.7 & auc_df$auc < 0.9, na.rm = TRUE),
      n_weak_effect = sum(auc_df$auc > 0.5 & auc_df$auc < 0.7, na.rm = TRUE),
      n_no_effect = sum(auc_df$auc <= 0.5, na.rm = TRUE)
    )
  } else if ("CCC" %in% names(augur)) {
    ccc_df <- augur$CCC
    list(
      n_cell_types = nrow(ccc_df),
      mean_ccc = mean(ccc_df$ccc, na.rm = TRUE),
      median_ccc = stats::median(ccc_df$ccc, na.rm = TRUE),
      mode = "regression"
    )
  } else {
    stop("Invalid Augur result object")
  }
}


#' Interpret Augur Score
#'
#' Convert AUC value to human-readable interpretation.
#'
#' @param score AUC value (0 to 1)
#'
#' @return Character string interpretation
#'
#' @export
interpret_augur_score <- function(score) {
  if (score >= 0.9) {
    "Strong effect"
  } else if (score >= 0.7) {
    "Moderate effect"
  } else if (score > 0.5) {
    "Weak effect"
  } else {
    "No effect (random)"
  }
}


#' Get Prioritized Cell Types
#'
#' Extract cell types ranked by Augur score.
#'
#' @param augur Augur result object
#' @param min_score Minimum score threshold. Default: 0.5
#' @param top_n Return only top N cell types. Default: NULL (all)
#'
#' @return Data frame with prioritized cell types
#'
#' @export
get_prioritized_cell_types <- function(augur, min_score = 0.5, top_n = NULL) {
  if ("AUC" %in% names(augur)) {
    df <- augur$AUC
    df <- df[df$auc >= min_score, ]
    df <- df[order(df$auc, decreasing = TRUE), ]
    if (!is.null(top_n)) {
      df <- head(df, top_n)
    }
    df
  } else {
    stop("AUC not found in Augur results")
  }
}


#' Get Top Features
#'
#' Get top important genes per cell type from Augur results.
#'
#' @param augur Augur result object
#' @param cell_type Specific cell type, or NULL for all. Default: NULL
#' @param top_n Number of top genes. Default: 10
#'
#' @return Data frame with top features
#'
#' @export
get_top_features <- function(augur, cell_type = NULL, top_n = 10) {
  if (!"feature_importance" %in% names(augur)) {
    stop("No feature importance found. Ensure classifier = 'rf' was used.")
  }

  imp <- augur$feature_importance

  if (!is.null(cell_type)) {
    imp <- imp[imp$cell_type == cell_type, ]
    if (nrow(imp) == 0) {
      stop(sprintf("Cell type '%s' not found in feature importances", cell_type))
    }
  }

  # Calculate mean importance per gene per cell type
  imp_summary <- aggregate(importance ~ cell_type + gene, data = imp, FUN = mean)

  if (!is.null(cell_type)) {
    imp_summary <- imp_summary[order(imp_summary$importance, decreasing = TRUE), ]
    head(imp_summary, top_n)
  } else {
    # Get top N for each cell type
    do.call(rbind, by(imp_summary, imp_summary$cell_type, function(x) {
      x <- x[order(x$importance, decreasing = TRUE), ]
      head(x, top_n)
    }))
  }
}


#' Plot Augur Lollipop
#'
#' Create a lollipop plot of cell type prioritizations.
#'
#' @param augur Augur result object
#' @param ... Additional arguments passed to Augur::plot_lollipop()
#'
#' @return ggplot object
#'
#' @export
plot_augur_lollipop <- function(augur, ...) {
  if (!requireNamespace("Augur", quietly = TRUE)) {
    stop("Augur package required.")
  }
  Augur::plot_lollipop(augur, ...)
}


#' Plot Augur Scatterplot
#'
#' Compare two Augur results in a scatterplot.
#'
#' @param augur1 First Augur result
#' @param augur2 Second Augur result
#' @param top_n Number of top cell types to label. Default: 0
#' @param ... Additional arguments passed to Augur::plot_scatterplot()
#'
#' @return ggplot object
#'
#' @export
plot_augur_scatterplot <- function(augur1, augur2, top_n = 0, ...) {
  if (!requireNamespace("Augur", quietly = TRUE)) {
    stop("Augur package required.")
  }
  Augur::plot_scatterplot(augur1, augur2, top_n = top_n, ...)
}


#' Plot Augur UMAP
#'
#' Superimpose cell type prioritizations onto a dimensionality reduction plot.
#'
#' @param augur Augur result object
#' @param sc Seurat, monocle3, or SingleCellExperiment object with reduction
#' @param mode "default" (raw AUCs) or "rank". Default: "default"
#' @param reduction Dimensionality reduction to use. Default: "umap"
#' @param palette Color palette. Default: "cividis"
#' @param top_n Number of top cell types to label. Default: 0
#' @param cell_type_col Cell type column. Default: "cell_type"
#' @param ... Additional arguments passed to Augur::plot_umap()
#'
#' @return ggplot object
#'
#' @export
plot_augur_umap <- function(
    augur, sc,
    mode = "default",
    reduction = "umap",
    palette = "cividis",
    top_n = 0,
    cell_type_col = "cell_type",
    ...
) {
  if (!requireNamespace("Augur", quietly = TRUE)) {
    stop("Augur package required.")
  }
  Augur::plot_umap(
    augur = augur, sc = sc, mode = mode,
    reduction = reduction, palette = palette,
    top_n = top_n, cell_type_col = cell_type_col, ...
  )
}


#' Plot Differential Prioritization
#'
#' Plot results of differential prioritization analysis.
#'
#' @param diff_results Result from run_differential_prioritization()
#' @param top_n Number of top significant cell types to label. Default: 0
#' @param ... Additional arguments passed to Augur::plot_differential_prioritization()
#'
#' @return ggplot object
#'
#' @export
plot_augur_differential <- function(diff_results, top_n = 0, ...) {
  if (!requireNamespace("Augur", quietly = TRUE)) {
    stop("Augur package required.")
  }
  Augur::plot_differential_prioritization(results = diff_results, top_n = top_n, ...)
}


#' Export Augur Results
#'
#' Export Augur results to CSV files.
#'
#' @param augur Augur result object
#' @param output_dir Output directory path
#' @param prefix File prefix. Default: "augur"
#' @param export_summary Export AUC/CCC summary. Default: TRUE
#' @param export_importances Export feature importances. Default: TRUE
#' @param export_detailed Export detailed CV results. Default: FALSE
#' @param verbose Print messages. Default: TRUE
#'
#' @export
export_augur_results <- function(
    augur,
    output_dir,
    prefix = "augur",
    export_summary = TRUE,
    export_importances = TRUE,
    export_detailed = FALSE,
    verbose = TRUE
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Export summary
  if (export_summary && "AUC" %in% names(augur)) {
    path <- file.path(output_dir, sprintf("%s_auc_summary.csv", prefix))
    utils::write.csv(augur$AUC, path, row.names = FALSE)
    if (verbose) message(sprintf("Exported: %s", path))
  }

  if (export_summary && "CCC" %in% names(augur)) {
    path <- file.path(output_dir, sprintf("%s_ccc_summary.csv", prefix))
    utils::write.csv(augur$CCC, path, row.names = FALSE)
    if (verbose) message(sprintf("Exported: %s", path))
  }

  # Export feature importances
  if (export_importances && "feature_importance" %in% names(augur)) {
    path <- file.path(output_dir, sprintf("%s_feature_importances.csv", prefix))
    utils::write.csv(augur$feature_importance, path, row.names = FALSE)
    if (verbose) message(sprintf("Exported: %s", path))
  }

  # Export detailed results
  if (export_detailed && "results" %in% names(augur)) {
    path <- file.path(output_dir, sprintf("%s_detailed_results.csv", prefix))
    utils::write.csv(augur$results, path, row.names = FALSE)
    if (verbose) message(sprintf("Exported: %s", path))
  }
}


#' Validate Augur Input Data
#'
#' Check if input data meets Augur requirements.
#'
#' @param input Seurat object, matrix, or data frame
#' @param meta Metadata data frame (if input is matrix/df)
#' @param label_col Label column name. Default: "label"
#' @param cell_type_col Cell type column name. Default: "cell_type"
#' @param min_cells Minimum cells per cell type per condition. Default: 20
#'
#' @return List with validation results
#'
#' @export
validate_augur_data <- function(
    input,
    meta = NULL,
    label_col = "label",
    cell_type_col = "cell_type",
    min_cells = 20
) {
  issues <- character()
  warnings_list <- character()

  # Extract metadata based on input type
  if (inherits(input, "Seurat")) {
    if (!requireNamespace("Seurat", quietly = TRUE)) {
      stop("Seurat package required for Seurat input.")
    }
    meta_df <- tryCatch(input@meta.data, error = function(e) input$meta.data)
  } else if (!is.null(meta)) {
    meta_df <- meta
  } else {
    issues <- c(issues, "Metadata required for non-Seurat input")
    return(list(valid = FALSE, issues = issues, warnings = warnings_list))
  }

  # Check columns exist
  if (!(label_col %in% colnames(meta_df))) {
    issues <- c(issues, sprintf("Label column '%s' not found in metadata", label_col))
  }
  if (!(cell_type_col %in% colnames(meta_df))) {
    issues <- c(issues, sprintf("Cell type column '%s' not found in metadata", cell_type_col))
  }

  if (length(issues) > 0) {
    return(list(valid = FALSE, issues = issues, warnings = warnings_list))
  }

  labels <- meta_df[[label_col]]
  cell_types <- meta_df[[cell_type_col]]

  # Check at least 2 labels
  n_labels <- length(unique(labels))
  if (n_labels < 2) {
    issues <- c(issues, sprintf("Need >= 2 labels, found %d", n_labels))
  }

  # Check for NAs
  na_labels <- sum(is.na(labels))
  na_cell_types <- sum(is.na(cell_types))
  if (na_labels > 0) {
    issues <- c(issues, sprintf("Label column contains %d NA values", na_labels))
  }
  if (na_cell_types > 0) {
    issues <- c(issues, sprintf("Cell type column contains %d NA values", na_cell_types))
  }

  # Check cell type counts per label
  crosstab <- table(cell_types, labels)
  low_count <- apply(crosstab, 1, function(x) any(x < min_cells))

  if (any(low_count)) {
    low_cell_types <- rownames(crosstab)[low_count]
    warnings_list <- c(
      warnings_list,
      sprintf("Cell types with < %d cells in some conditions: %s",
              min_cells, paste(low_cell_types, collapse = ", "))
    )
  }

  # Check dimensions for matrix input
  if (inherits(input, "matrix") || inherits(input, "data.frame")) {
    if (ncol(input) != nrow(meta_df)) {
      issues <- c(issues, sprintf(
        "Cell count mismatch: expression has %d cols, metadata has %d rows",
        ncol(input), nrow(meta_df)
      ))
    }
  }

  list(
    valid = length(issues) == 0,
    issues = issues,
    warnings = warnings_list,
    n_cells = nrow(meta_df),
    n_labels = n_labels,
    n_cell_types = length(unique(cell_types)),
    cell_type_counts = as.data.frame.matrix(crosstab)
  )
}


#' Print Validation Results
#'
#' Pretty-print validation results.
#'
#' @param validation Result from validate_augur_data()
#'
#' @export
print_validation_results <- function(validation) {
  cat(rep("=", 50), "\n", sep = "")
  cat("Augur Data Validation\n")
  cat(rep("=", 50), "\n", sep = "")

  if (validation$valid) {
    cat("Status: PASSED\n")
  } else {
    cat("Status: FAILED\n")
  }

  cat("\nDataset Summary:\n")
  cat(sprintf("  Cells: %d\n", validation$n_cells))
  cat(sprintf("  Labels: %d\n", validation$n_labels))
  cat(sprintf("  Cell types: %d\n", validation$n_cell_types))

  if (length(validation$issues) > 0) {
    cat(sprintf("\nErrors (%d):\n", length(validation$issues)))
    for (issue in validation$issues) {
      cat(sprintf("  - %s\n", issue))
    }
  }

  if (length(validation$warnings) > 0) {
    cat(sprintf("\nWarnings (%d):\n", length(validation$warnings)))
    for (warning in validation$warnings) {
      cat(sprintf("  - %s\n", warning))
    }
  }
}
