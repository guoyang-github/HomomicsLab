# Harmony batch integration - Seurat V4
# Reference: Seurat 4.4+, harmony 1.0+
#
# Harmony directly corrects PCA embeddings without creating a new assay.
# Input: single merged Seurat object (prepared via prepare_input_v4).
#
# V4 SCT note: V4 lacks layers, so SCT must be run per-batch via SplitObject
# to avoid mixing batch effects in the regression model.

library(Seurat)
library(harmony)


#------------------------------------------------------------------------------
# Standard (LogNormalize) Integration
#------------------------------------------------------------------------------

#' Harmony Integration - Seurat V4 Standard
#'
#' Run Harmony batch correction on a merged V4 Seurat object
#' using LogNormalize + ScaleData workflow.
#'
#' @param obj Merged Seurat object (single matrix, no layers)
#' @param batch_col Metadata column(s) defining batches. Single string or character vector for multi-variable correction (e.g. c("sample", "condition")). (default: "sample")
#' @param nfeatures Number of variable features (default: 2000)
#' @param npcs PCs for PCA (default: 50)
#' @param dims_use Dimensions for Harmony (default: 1:30)
#'
#' @return Seurat object with harmony reduction. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' prep <- prepare_input_v4(obj = merged_obj, batch_col = "sample")
#'
#' source("scripts/r/seurat-v4/harmony.R")
#' obj <- harmony_v4_standard(obj = prep$obj, batch_col = "sample")
#' }
#'
#' @export
harmony_v4_standard <- function(obj, batch_col = "sample",
                                nfeatures = 2000, npcs = 50,
                                dims_use = 1:30) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("harmony", quietly = TRUE)) {
    stop("harmony package required. Install: install.packages('harmony')")
  }
  if (!inherits(obj, "Seurat")) {
    stop("'obj' must be a Seurat object")
  }
  missing_cols <- setdiff(batch_col, colnames(obj@meta.data))
  if (length(missing_cols) > 0) {
    stop(sprintf("Column(s) not found in metadata: %s",
                 paste(missing_cols, collapse = ", ")))
  }

  # Preprocess on merged object
  obj <- NormalizeData(obj)
  obj <- FindVariableFeatures(obj, selection.method = "vst",
                               nfeatures = nfeatures)
  obj <- ScaleData(obj)
  obj <- RunPCA(obj, npcs = npcs)

  # Harmony correction
  obj <- RunHarmony(obj, group.by.vars = batch_col,
                    reduction.use = "pca", dims = dims_use)

  return(obj)
}


#------------------------------------------------------------------------------
# SCTransform Integration
#------------------------------------------------------------------------------

#' Harmony Integration - Seurat V4 SCTransform
#'
#' Run Harmony on SCTransform-normalized V4 data.
#'
#' CRITICAL: V4 lacks layers, so SCTransform must be run per-batch
#' to avoid mixing batch effects in the regression model.
#' Flow: per-batch SCT -> merge -> RunPCA(SCT assay) -> RunHarmony
#'
#' @param obj_list List of Seurat objects (one per batch)
#' @param batch_col Metadata column(s) defining batches. Single string or character vector for multi-variable correction (e.g. c("sample", "condition")). (default: "sample")
#' @param npcs PCs for PCA (default: 50)
#' @param dims_use Dimensions for Harmony (default: 1:30)
#'
#' @return Seurat object with harmony reduction. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' prep <- prepare_input_v4(obj = merged_obj, batch_col = "sample")
#'
#' source("scripts/r/seurat-v4/harmony.R")
#' obj <- harmony_v4_sct(obj_list = prep$obj_list, batch_col = "sample")
#' }
#'
#' @export
harmony_v4_sct <- function(obj_list, batch_col = "sample",
                            npcs = 50, dims_use = 1:30) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("harmony", quietly = TRUE)) {
    stop("harmony package required")
  }
  if (!is.list(obj_list) || length(obj_list) == 0) {
    stop("'obj_list' must be a non-empty list of Seurat objects")
  }
  if (any(!sapply(obj_list, inherits, "Seurat"))) {
    stop("All elements of 'obj_list' must be Seurat objects")
  }

  # Validate batch_col columns exist in at least one object each
  for (col in batch_col) {
    found_in_any <- any(vapply(obj_list, function(o) col %in% colnames(o@meta.data), logical(1)))
    if (!found_in_any) {
      warning(sprintf("Column '%s' not found in any object's metadata. Will use fallback values after merge.", col))
    }
  }

  # Step 1: SCTransform per batch (V4: must split first)
  obj_list <- lapply(obj_list, function(x) {
    x <- SCTransform(x, vst.flavor = "v2", verbose = FALSE)
    return(x)
  })

  # Step 2: Merge and use SCT assay directly
  obj <- merge(obj_list[[1]], y = obj_list[-1])

  # Ensure batch_col exists after merge
  # Ensure all batch columns exist after merge
  for (col in batch_col) {
    if (!col %in% colnames(obj@meta.data)) {
      col_vals <- vapply(seq_along(obj_list), function(i) {
        o <- obj_list[[i]]
        if (col %in% colnames(o@meta.data)) {
          vals <- unique(o@meta.data[[col]])
          vals <- vals[!is.na(vals)]
          if (length(vals) == 1) return(as.character(vals))
        }
        nm <- names(obj_list)[i]
        if (is.null(nm) || nm == "" || is.na(nm)) return(as.character(i))
        return(nm)
      }, character(1))
      obj@meta.data[[col]] <- rep(col_vals, sapply(obj_list, ncol))
    }
  }

  DefaultAssay(obj) <- "SCT"
  # Variable features are lost during merge; restore from SCT scale.data
  VariableFeatures(obj) <- rownames(obj[["SCT"]]@scale.data)
  obj <- RunPCA(obj, npcs = npcs)

  # Step 3: Harmony correction
  obj <- RunHarmony(obj, group.by.vars = batch_col,
                    reduction.use = "pca", dims = dims_use)

  return(obj)
}
