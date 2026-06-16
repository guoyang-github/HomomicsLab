# Seurat V5 Unified Batch Integration
# Reference: Seurat 5.0+
#
# All V5 integration methods (Harmony, CCA, RPCA, fastMNN) share the same
# IntegrateLayers workflow. Only the `method` parameter differs.
#
# Input: merged Seurat object with layers (prepared via prepare_input_v5).
# Output: Seurat object with integration-specific reduction.
#
# Note: This function stops at reduction creation. Downstream clustering
# (FindNeighbors, FindClusters, RunUMAP) should be handled separately.

library(Seurat)


#------------------------------------------------------------------------------
# Method mapping
#------------------------------------------------------------------------------

.METHOD_MAP <- list(
  harmony = list(method = "HarmonyIntegration", reduction = "harmony"),
  cca = list(method = "CCAIntegration", reduction = "integrated.cca"),
  rpca = list(method = "RPCAIntegration", reduction = "integrated.rpca"),
  fastmnn = list(method = "FastMNNIntegration", reduction = "integrated.mnn")
)


#------------------------------------------------------------------------------
# Standard (LogNormalize)
#------------------------------------------------------------------------------

#' Seurat V5 Unified Integration - Standard
#'
#' Batch integration via IntegrateLayers with LogNormalize workflow.
#' Supports Harmony, CCA, RPCA, and fastMNN via the `method` parameter.
#'
#' IntegrateLayers identifies batches from the assay's layer structure
#' automatically; no batch column or split is required here.
#'
#' @param obj Merged Seurat object with layers
#' @param method Integration method: "harmony", "cca", "rpca", "fastmnn" (default: "harmony")
#' @param npcs PCs for PCA (default: 50)
#'
#' @return Seurat object with integration reduction. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")
#'
#' source("scripts/r/seurat-v5/integrate.R")
#' obj <- integrate_v5_standard(obj = obj, method = "harmony")
#' }
#'
#' @export
integrate_v5_standard <- function(obj, method = "harmony", npcs = 50) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!inherits(obj, "Seurat")) {
    stop("'obj' must be a Seurat object")
  }
  if (!method %in% names(.METHOD_MAP)) {
    stop(sprintf("Unknown method '%s'. Choose: %s",
                 method, paste(names(.METHOD_MAP), collapse = ", ")))
  }

  cfg <- .METHOD_MAP[[method]]

  # Preprocess (auto per-layer in V5)
  obj <- NormalizeData(obj)
  obj <- FindVariableFeatures(obj)
  obj <- ScaleData(obj)
  obj <- RunPCA(obj, npcs = npcs)

  # IntegrateLayers uses layers to identify batches automatically
  obj <- IntegrateLayers(
    object = obj,
    method = cfg$method,
    orig.reduction = "pca",
    new.reduction = cfg$reduction
  )

  # Join layers before DE (required for LogNormalize)
  assay <- DefaultAssay(obj)
  obj[[assay]] <- JoinLayers(obj[[assay]])

  return(obj)
}


#------------------------------------------------------------------------------
# SCTransform
#------------------------------------------------------------------------------

#' Seurat V5 Unified Integration - SCTransform
#'
#' Batch integration via IntegrateLayers with SCTransform normalization.
#' Supports Harmony, CCA, RPCA, and fastMNN via the `method` parameter.
#'
#' IntegrateLayers identifies batches from SCTModel.list levels automatically;
#' no batch column or explicit split is required here.
#'
#' @param obj Merged Seurat object with layers
#' @param method Integration method: "harmony", "cca", "rpca", "fastmnn" (default: "harmony")
#' @param npcs PCs for PCA (default: 50)
#'
#' @return Seurat object with integration reduction. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")
#'
#' source("scripts/r/seurat-v5/integrate.R")
#' obj <- integrate_v5_sct(obj = obj, method = "harmony")
#' }
#'
#' @export
integrate_v5_sct <- function(obj, method = "harmony", npcs = 50) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!inherits(obj, "Seurat")) {
    stop("'obj' must be a Seurat object")
  }
  if (!method %in% names(.METHOD_MAP)) {
    stop(sprintf("Unknown method '%s'. Choose: %s",
                 method, paste(names(.METHOD_MAP), collapse = ", ")))
  }

  cfg <- .METHOD_MAP[[method]]

  # SCTransform (auto per-layer in V5 on default assay)
  obj <- SCTransform(obj, vst.flavor = "v2", verbose = FALSE)
  obj <- RunPCA(obj, npcs = npcs)

  # IntegrateLayers uses SCTModel.list levels to identify batches
  obj <- IntegrateLayers(
    object = obj,
    method = cfg$method,
    normalization.method = "SCT",
    orig.reduction = "pca",
    new.reduction = cfg$reduction
  )

  # No JoinLayers needed for SCT

  return(obj)
}


#------------------------------------------------------------------------------
# Harmony Compatible (RunHarmony)
#------------------------------------------------------------------------------

#' Seurat V5 Harmony Integration - RunHarmony Compatible
#'
#' Batch integration via harmony::RunHarmony on joined data.
#' Supports multi-variable batch correction via `group.by.vars`.
#'
#' Unlike IntegrateLayers (which infers batches from layer structure),
#' this function reads batch information from metadata columns. This
#' enables multi-variable correction (e.g. c("batch", "condition")).
#'
#' @param obj Merged Seurat object with layers
#' @param group.by.vars Character vector of metadata column(s) defining batches
#' @param npcs PCs for PCA (default: 50)
#'
#' @return Seurat object with `harmony` reduction. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")
#'
#' source("scripts/r/seurat-v5/integrate.R")
#' obj <- harmony_v5_compat(obj = obj, group.by.vars = c("batch", "condition"))
#' }
#'
#' @export
harmony_v5_compat <- function(obj, group.by.vars, npcs = 50) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("harmony", quietly = TRUE)) {
    stop("harmony package required")
  }
  if (!inherits(obj, "Seurat")) {
    stop("'obj' must be a Seurat object")
  }
  missing_vars <- setdiff(group.by.vars, colnames(obj@meta.data))
  if (length(missing_vars) > 0) {
    stop(sprintf("group.by.vars not found in metadata: %s",
                 paste(missing_vars, collapse = ", ")))
  }

  # JoinLayers first — RunHarmony needs unified matrix, not split layers
  assay <- DefaultAssay(obj)
  obj[[assay]] <- JoinLayers(obj[[assay]])

  # Standard preprocess on joined data
  obj <- NormalizeData(obj)
  obj <- FindVariableFeatures(obj)
  obj <- ScaleData(obj)
  obj <- RunPCA(obj, npcs = npcs)

  # RunHarmony with explicit metadata columns
  obj <- harmony::RunHarmony(obj, group.by.vars = group.by.vars, reduction.use = "pca")

  return(obj)
}
