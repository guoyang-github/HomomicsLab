#' SCEVAN: Single Cell CNV Analysis
#'
#' Single-cell CNV inference and tumor/normal classification.
#' SCEVAN pipelineCNA returns a classDf (data frame) with cell classifications.
#' CNV matrices and plots are saved to the working directory automatically.
#'
#' @author Yang Guo
#' @date 2026-03-31

#' Run SCEVAN Pipeline
#'
#' Wrapper around SCEVAN::pipelineCNA with input validation.
#'
#' @param count_mtx Raw count matrix (genes x cells). Rownames must be gene symbols.
#' @param sample_name Sample name used for output files (default: "Sample")
#' @param par_cores Number of parallel cores (default: 4)
#' @param norm_cell Character vector of known normal cell barcodes, or NULL for auto-detection
#' @param SUBCLONES Whether to identify subclones (default: TRUE)
#' @param beta_vega Segmentation parameter (default: 0.5). Lower = more segments.
#' @param organism "human" or "mouse" (default: "human")
#'
#' @return classDf data frame with cell classifications:
#'   - class: "malignant" or "non-malignant"
#'   - subclone: subclone ID (if SUBCLONES = TRUE)
#'
#' @export
run_scevan <- function(
    count_mtx,
    sample_name = "Sample",
    par_cores = 4,
    norm_cell = NULL,
    SUBCLONES = TRUE,
    beta_vega = 0.5,
    organism = "human"
) {
  if (!requireNamespace("SCEVAN", quietly = TRUE)) {
    stop("SCEVAN required. Install: devtools::install_github('AntonioDeFalco/SCEVAN')")
  }

  if (is.null(rownames(count_mtx))) {
    stop("count_mtx must have gene symbols as rownames")
  }

  # Warn if rownames look like ENSEMBL IDs (common mistake)
  if (any(grepl("^ENSG[0-9]{11}", head(rownames(count_mtx), 100)))) {
    warning("Rownames appear to be ENSEMBL IDs. SCEVAN requires gene symbols (e.g. 'TP53'). ",
            "Convert IDs before running or results will be invalid.")
  }

  if (!is.null(norm_cell)) {
    missing <- setdiff(norm_cell, colnames(count_mtx))
    if (length(missing) > 0) {
      stop(length(missing), " norm_cell barcodes not found in count_mtx")
    }
  }

  message("Running SCEVAN on ", ncol(count_mtx), " cells...")

  results <- SCEVAN::pipelineCNA(
    count_mtx = count_mtx,
    sample_name = sample_name,
    par_cores = par_cores,
    norm_cell = norm_cell,
    SUBCLONES = SUBCLONES,
    beta_vega = beta_vega,
    organism = organism
  )

  message("SCEVAN complete. Outputs saved to working directory:")
  message("  - ", sample_name, "_CNAmtx.RData")
  message("  - ", sample_name, "_CNV_plot.png")
  if (SUBCLONES) {
    message("  - ", sample_name, "_subclones.png")
  }

  return(results)
}


#' Run SCEVAN with Seurat Object
#'
#' Extracts counts from Seurat and runs SCEVAN pipeline.
#' Auto-detects Seurat v4 (slot=) vs v5 (layer=).
#'
#' @param seurat_obj Seurat object
#' @param assay Assay to use (default: "RNA")
#' @param sample_name Sample name for output files
#' @param norm_cell Known normal cell barcodes, or NULL for auto-detection
#' @param ... Additional arguments passed to run_scevan()
#'
#' @return classDf with cell classifications
#' @export
run_scevan_seurat <- function(
    seurat_obj,
    assay = "RNA",
    sample_name = "Sample",
    norm_cell = NULL,
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  # Extract counts (v4/v5 compatible)
  if (requireNamespace("SeuratObject", quietly = TRUE) &&
      packageVersion("SeuratObject") >= "5.0.0") {
    counts <- Seurat::GetAssayData(seurat_obj, layer = "counts", assay = assay)
  } else {
    counts <- Seurat::GetAssayData(seurat_obj, slot = "counts", assay = assay)
  }

  # Validate norm_cell barcodes exist in Seurat
  if (!is.null(norm_cell)) {
    missing <- setdiff(norm_cell, colnames(seurat_obj))
    if (length(missing) > 0) {
      stop(length(missing), " norm_cell barcodes not found in Seurat object")
    }
  }

  results <- run_scevan(
    count_mtx = counts,
    sample_name = sample_name,
    norm_cell = norm_cell,
    ...
  )

  return(results)
}


#' Add SCEVAN Results to Seurat Object
#'
#' Merges SCEVAN classifications and subclones into Seurat metadata.
#'
#' @param seurat_obj Seurat object
#' @param scevan_results Results from run_scevan() or run_scevan_seurat()
#' @param prefix Column name prefix (default: "scevan_")
#'
#' @return Seurat object with added metadata columns
#' @export
add_scevan_to_seurat <- function(seurat_obj, scevan_results, prefix = "scevan_") {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  # scevan_results is a data frame with cells as rownames
  cells <- colnames(seurat_obj)

  # Check for cells missing from SCEVAN results (SCEVAN may filter some cells)
  missing_cells <- setdiff(cells, rownames(scevan_results))
  if (length(missing_cells) > 0) {
    warning(length(missing_cells), " cells from Seurat object are missing from SCEVAN results. ",
            "These cells will be assigned NA. Example: ", missing_cells[1])
  }

  # Classification (malignant vs non-malignant)
  if ("class" %in% colnames(scevan_results)) {
    class_vec <- scevan_results[cells, "class", drop = TRUE]
    seurat_obj[[paste0(prefix, "class")]] <- class_vec
  } else {
    warning("'class' column not found in SCEVAN results")
  }

  # Subclones (if SUBCLONES = TRUE)
  if ("subclone" %in% colnames(scevan_results)) {
    subclone_vec <- scevan_results[cells, "subclone", drop = TRUE]
    seurat_obj[[paste0(prefix, "subclone")]] <- subclone_vec
  }

  return(seurat_obj)
}


#' Plot SCEVAN Cell Classification
#'
#' Visualizes malignant vs non-malignant classifications on UMAP or as a bar plot.
#' Note: SCEVAN generates its own CNV heatmap during pipeline execution.
#' This function provides a quick view of the classification results.
#'
#' @param seurat_obj Seurat object with SCEVAN classifications (must have run add_scevan_to_seurat first)
#' @param reduction Dimensionality reduction to use for UMAP plot (default: "umap")
#' @param output_file Optional output file path for saving plot
#'
#' @return ggplot object
#' @export
plot_scevan_classification <- function(seurat_obj, reduction = "umap", output_file = NULL) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  class_col <- "scevan_class"
  if (!class_col %in% colnames(seurat_obj@meta.data)) {
    stop("SCEVAN classification not found. Run add_scevan_to_seurat() first.")
  }

  p <- Seurat::DimPlot(seurat_obj, group.by = class_col, reduction = reduction, label = TRUE)

  if (!is.null(output_file)) {
    ggplot2::ggsave(output_file, p, width = 8, height = 6, dpi = 150)
    message("Plot saved to: ", output_file)
  }

  return(p)
}


#' Summarize SCEVAN Results
#'
#' Prints summary statistics from SCEVAN classification.
#'
#' @param scevan_results Results from run_scevan()
#' @export
summarize_scevan <- function(scevan_results) {
  cat("SCEVAN Results Summary\n")
  cat(strrep("=", 40), "\n")

  n_cells <- nrow(scevan_results)
  cat("Total cells:", n_cells, "\n")

  if ("class" %in% colnames(scevan_results)) {
    cat("\nClassification:\n")
    print(table(scevan_results$class, useNA = "ifany"))
  }

  if ("subclone" %in% colnames(scevan_results)) {
    cat("\nSubclones:\n")
    print(table(scevan_results$subclone, useNA = "ifany"))
  }
}
