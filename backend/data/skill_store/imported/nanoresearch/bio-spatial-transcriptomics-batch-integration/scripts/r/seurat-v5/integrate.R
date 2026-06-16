# Seurat V5 Spatial Batch Integration
# Reference: Seurat 5.0+
#
# All V5 integration methods (Harmony, CCA, RPCA, fastMNN) share the same
# IntegrateLayers workflow. Only the `method` parameter differs.
#
# Spatial-specific notes:
#   - Input must be a spatial Seurat object (has @images slot)
#   - prepare_input_spatial() handles image slot renaming before merge
#   - This function preserves spatial images and coordinates
#   - Downstream validation should use SpatialDimPlot per slice
#
# Input: merged spatial Seurat object with layers (prepared via prepare_input_spatial).
# Output: Seurat object with integration-specific reduction (images preserved).
#
# Note: This function stops at reduction creation. Downstream clustering
# and spatial visualization should be handled separately.

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

#' Seurat V5 Spatial Integration - Standard
#'
#' Batch integration for spatial transcriptomics via IntegrateLayers with
#' LogNormalize workflow. Supports Harmony, CCA, RPCA, and fastMNN.
#'
#' Preserves spatial images and coordinates from the input object.
#' IntegrateLayers identifies batches from the assay's layer structure
#' automatically; no batch column or split is required here.
#'
#' @param obj Merged spatial Seurat object with layers
#' @param method Integration method: "harmony", "cca", "rpca", "fastmnn" (default: "harmony")
#' @param npcs PCs for PCA (default: 50)
#'
#' @return Seurat object with integration reduction. Images and coordinates
#'   are preserved. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' obj <- prepare_input_spatial(
#'   file_paths = c("slice1.rds", "slice2.rds"),
#'   sample_col = "sample"
#' )
#'
#' source("scripts/r/seurat-v5/integrate.R")
#' obj <- integrate_spatial_v5_standard(obj = obj, method = "harmony")
#' }
#'
#' @export
integrate_spatial_v5_standard <- function(obj, method = "harmony", npcs = 50) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!inherits(obj, "Seurat")) {
    stop("'obj' must be a Seurat object")
  }
  if (length(obj@images) == 0) {
    warning("'obj' has no images slot. Use integrate_v5_standard() from bio-single-cell-batch-integration for non-spatial data.")
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

#' Seurat V5 Spatial Integration - SCTransform
#'
#' Batch integration for spatial transcriptomics via IntegrateLayers with
#' SCTransform normalization.
#'
#' NOTE: SCTransform assumes single-cell resolution. Visium spots contain
#' multiple cells (~55um diameter), so the regression model's sequencing depth
#' correction may be less accurate. Consider Standard normalization first.
#'
#' @param obj Merged spatial Seurat object with layers
#' @param method Integration method: "harmony", "cca", "rpca", "fastmnn" (default: "harmony")
#' @param npcs PCs for PCA (default: 50)
#'
#' @return Seurat object with integration reduction. Images preserved.
#'   No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' obj <- prepare_input_spatial(
#'   file_paths = c("slice1.rds", "slice2.rds"),
#'   sample_col = "sample"
#' )
#'
#' source("scripts/r/seurat-v5/integrate.R")
#' obj <- integrate_spatial_v5_sct(obj = obj, method = "harmony")
#' }
#'
#' @export
integrate_spatial_v5_sct <- function(obj, method = "harmony", npcs = 50) {
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
  spatial_assay <- DefaultAssay(obj)

  # SCTransform (auto per-layer in V5 on default assay)
  obj <- SCTransform(obj, vst.flavor = "v2", verbose = FALSE, assay = spatial_assay)
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

#' Seurat V5 Spatial Harmony Integration - RunHarmony Compatible
#'
#' Batch integration for spatial data via harmony::RunHarmony on joined data.
#' Supports multi-variable batch correction (e.g. sample + condition + technology).
#'
#' Unlike IntegrateLayers (which infers batches from layer structure),
#' this function reads batch information from metadata columns. This
#' enables multi-variable correction.
#'
#' @param obj Merged spatial Seurat object with layers
#' @param group.by.vars Character vector of metadata column(s) defining batches
#' @param npcs PCs for PCA (default: 50)
#'
#' @return Seurat object with `harmony` reduction. Images preserved.
#'   No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' obj <- prepare_input_spatial(
#'   file_paths = c("slice1.rds", "slice2.rds"),
#'   sample_col = "sample"
#' )
#'
#' source("scripts/r/seurat-v5/integrate.R")
#' obj <- harmony_spatial_v5_compat(
#'   obj = obj,
#'   group.by.vars = c("sample", "condition")
#' )
#' }
#'
#' @export
harmony_spatial_v5_compat <- function(obj, group.by.vars, npcs = 50) {
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

  # JoinLayers first — RunHarmony needs unified matrix
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
