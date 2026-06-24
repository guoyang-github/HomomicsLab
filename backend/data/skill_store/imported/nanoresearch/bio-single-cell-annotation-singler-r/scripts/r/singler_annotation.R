# SingleR reference-based cell type annotation

# Conditionally load packages
if (requireNamespace("SingleR", quietly = TRUE)) {
  library(SingleR)
}
if (requireNamespace("celldex", quietly = TRUE)) {
  library(celldex)
}
if (requireNamespace("SingleCellExperiment", quietly = TRUE)) {
  library(SingleCellExperiment)
}
if (requireNamespace("Seurat", quietly = TRUE)) {
  library(Seurat)
}

#' Run SingleR annotation
#'
#' @param seurat_obj Seurat object
#' @param ref Reference dataset from celldex
#' @param label_col Column in ref containing labels
#' @param de.method DE method for scoring
#' @param prune Whether to prune low-confidence labels
#' @return Seurat object with SingleR annotations
#' @export
run_singler_annotation <- function(seurat_obj,
                                    ref = NULL,
                                    label_col = "label.main",
                                    de.method = "wilcox",
                                    prune = TRUE,
                                    assay = NULL) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("SingleCellExperiment", quietly = TRUE)) {
    stop("SingleCellExperiment package required")
  }

  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Locate the as.SingleCellExperiment generic. In different Bioconductor/Seurat
  # versions it is exported from SingleCellExperiment, Seurat, or SeuratObject.
  # Using :: on the wrong package fails, so we dispatch dynamically.
  as_sce <- NULL
  for (pkg in c("SingleCellExperiment", "Seurat", "SeuratObject")) {
    if (requireNamespace(pkg, quietly = TRUE) &&
        exists("as.SingleCellExperiment", envir = asNamespace(pkg))) {
      as_sce <- get("as.SingleCellExperiment", envir = asNamespace(pkg))
      break
    }
  }
  if (is.null(as_sce)) {
    stop("Could not find as.SingleCellExperiment(). Please ensure SingleCellExperiment and Seurat are installed.")
  }

  # Convert to SingleCellExperiment (assay param for Seurat v5 compatibility)
  if (!is.null(assay)) {
    sce <- as_sce(seurat_obj, assay = assay)
  } else {
    sce <- as_sce(seurat_obj)
  }

  # Default to MonacoImmuneData if no reference provided
  if (is.null(ref)) {
    message("Using MonacoImmuneData as reference")
    ref <- celldex::MonacoImmuneData()
  }

  # Validate label_col exists in reference
  if (!label_col %in% names(SummarizedExperiment::colData(ref))) {
    available <- paste(names(SummarizedExperiment::colData(ref)), collapse = ", ")
    stop("label_col '", label_col, "' not found in reference. Available: ", available)
  }

  # Get labels from reference
  labels <- ref[[label_col]]

  # Gene overlap pre-check
  overlap_count <- sum(rownames(sce) %in% rownames(ref))
  overlap_pct <- round(100 * overlap_count / nrow(ref), 1)
  if (overlap_pct < 50) {
    warning("Low gene overlap: only ", overlap_count, " genes (", overlap_pct,
            "%) match between data and reference. ",
            "Check gene ID format (ENSEMBL vs gene symbols).")
  }

  message("Running SingleR annotation (", overlap_count, " genes overlap)...")
  pred <- SingleR(
    test = sce,
    ref = ref,
    labels = labels,
    de.method = de.method,
    prune = prune
  )

  # Add to Seurat object
  seurat_obj$SingleR_label <- pred$labels
  seurat_obj$SingleR_pruned <- pred$pruned.labels
  # Store full prediction object for downstream plotting (scores, deltas, etc.)
  seurat_obj@misc$SingleR_pred <- pred

  message("Annotation complete!")
  return(seurat_obj)
}

#' Load common SingleR references
#'
#' @param name Reference name
#' @return Reference dataset
#' @export
load_singler_reference <- function(name = "monaco") {
  if (!requireNamespace("celldex", quietly = TRUE)) {
    stop("celldex package required. Install with: BiocManager::install('celldex')")
  }

  ref <- switch(name,
    "monaco" = celldex::MonacoImmuneData(),
    "blueprint" = celldex::BlueprintEncodeData(),
    "hpca" = celldex::HumanPrimaryCellAtlasData(),
    "immgen" = celldex::ImmGenData(),
    "dice" = celldex::DatabaseImmuneCellExpressionData(),
    "novershtern" = celldex::NovershternHematopoieticData(),
    "mouse" = celldex::MouseRNAseqData(),
    stop("Unknown reference: ", name,
         ". Valid names: monaco, blueprint, hpca, immgen, dice, novershtern, mouse")
  )
  return(ref)
}

#' Plot SingleR quality metrics
#'
#' @param seurat_obj Seurat object with SingleR results
#' @param output_file Optional output file path
#' @export
plot_singler_quality <- function(seurat_obj, output_file = NULL) {
  # Retrieve full prediction object with scores (stored by run_singler_annotation)
  pred <- seurat_obj@misc$SingleR_pred

  if (is.null(pred)) {
    stop("Full SingleR prediction object not found. Ensure run_singler_annotation() was run first, which stores the prediction object in seurat_obj@misc$SingleR_pred")
  }

  if (!is.null(output_file)) {
    pdf(output_file, width = 10, height = 8)
  }

  # Score heatmap (requires full prediction object with scores matrix)
  if ("scores" %in% names(pred)) {
    SingleR::plotScoreHeatmap(pred)
  } else {
    message("Warning: SingleR scores matrix not available. Skipping score heatmap.")
  }

  # Delta distribution (check that delta values are available)
  if ("delta.next" %in% names(pred) || "scores" %in% names(pred)) {
    SingleR::plotDeltaDistribution(pred)
  } else {
    message("Warning: Delta distribution data not available. Skipping delta plot.")
  }

  if (!is.null(output_file)) {
    dev.off()
    message("Plots saved to: ", output_file)
  }
}

#' Filter SingleR annotations by confidence
#'
#' Replaces low-confidence (pruned) labels with "Unknown".
#' Pruned labels are NA when SingleR cannot confidently assign a cell type.
#'
#' @param seurat_obj Seurat object with SingleR results
#' @return Seurat object with `SingleR_filtered` column
#' @export
filter_singler_by_confidence <- function(seurat_obj) {
  if (!("SingleR_pruned" %in% colnames(seurat_obj@meta.data))) {
    stop("SingleR_pruned column not found. Run run_singler_annotation() first.")
  }

  # Pruned labels are NA for low confidence
  seurat_obj$SingleR_filtered <- ifelse(
    is.na(seurat_obj$SingleR_pruned),
    "Unknown",
    seurat_obj$SingleR_label
  )

  n_unknown <- sum(seurat_obj$SingleR_filtered == "Unknown")
  message("Filtered annotations: ", n_unknown, " cells marked as Unknown (low confidence)")

  return(seurat_obj)
}
