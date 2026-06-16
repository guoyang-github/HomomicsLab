# Seurat CCA integration - Seurat V4
# Reference: Seurat 4.4+
#
# Anchor-based integration using Canonical Correlation Analysis.
# Input: list of Seurat objects (one per batch), prepared via prepare_input_v4.
# Output: integrated Seurat object with "integrated" assay.

library(Seurat)


#------------------------------------------------------------------------------
# Standard (LogNormalize) CCA
#------------------------------------------------------------------------------

#' Seurat CCA Integration - Seurat V4 Standard
#'
#' Anchor-based CCA integration with LogNormalize workflow.
#'
#' @param obj_list List of Seurat objects (one per batch)
#' @param anchor_features Number of integration features (default: 2000)
#' @param dims Dimensions for anchor finding (default: 1:30)
#'
#' @return Integrated Seurat object with "integrated" assay. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' prep <- prepare_input_v4(obj = merged_obj, batch_col = "sample")
#'
#' source("scripts/r/seurat-v4/seurat_cca.R")
#' integrated <- seurat_cca_v4_standard(obj_list = prep$obj_list)
#' }
#'
#' @export
seurat_cca_v4_standard <- function(obj_list, anchor_features = 2000,
                                   dims = 1:30) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!is.list(obj_list) || length(obj_list) == 0) {
    stop("'obj_list' must be a non-empty list of Seurat objects")
  }
  if (any(!sapply(obj_list, inherits, "Seurat"))) {
    stop("All elements of 'obj_list' must be Seurat objects")
  }

  # Normalize and find HVG per object
  obj_list <- lapply(obj_list, function(x) {
    x <- NormalizeData(x)
    x <- FindVariableFeatures(x, selection.method = "vst",
                              nfeatures = anchor_features)
    return(x)
  })

  # Select integration features
  features <- SelectIntegrationFeatures(
    object.list = obj_list,
    nfeatures = anchor_features
  )

  # Find anchors and integrate
  anchors <- FindIntegrationAnchors(
    object.list = obj_list,
    anchor.features = features,
    dims = dims,
    reduction = "cca"
  )
  integrated <- IntegrateData(anchorset = anchors, dims = dims)

  # Scale and PCA on integrated assay
  DefaultAssay(integrated) <- "integrated"
  integrated <- ScaleData(integrated)
  integrated <- RunPCA(integrated, npcs = 50)

  return(integrated)
}


#------------------------------------------------------------------------------
# SCTransform CCA
#------------------------------------------------------------------------------

#' Seurat CCA Integration - Seurat V4 SCTransform
#'
#' Anchor-based CCA integration with SCTransform per-batch normalization.
#' Flow: per-batch SCT -> SelectIntegrationFeatures ->
#'       PrepSCTIntegration -> FindIntegrationAnchors(SCT) -> IntegrateData(SCT)
#'
#' @param obj_list List of Seurat objects (one per batch)
#' @param anchor_features Number of integration features (default: 3000)
#' @param dims Dimensions for anchor finding (default: 1:30)
#'
#' @return Integrated Seurat object with SCT assay. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' prep <- prepare_input_v4(obj = merged_obj, batch_col = "sample")
#'
#' source("scripts/r/seurat-v4/seurat_cca.R")
#' integrated <- seurat_cca_v4_sct(obj_list = prep$obj_list)
#' }
#'
#' @export
seurat_cca_v4_sct <- function(obj_list, anchor_features = 3000,
                              dims = 1:30) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!is.list(obj_list) || length(obj_list) == 0) {
    stop("'obj_list' must be a non-empty list of Seurat objects")
  }
  if (any(!sapply(obj_list, inherits, "Seurat"))) {
    stop("All elements of 'obj_list' must be Seurat objects")
  }

  # SCTransform per batch (required for V4)
  obj_list <- lapply(obj_list, function(x) {
    x <- SCTransform(x, vst.flavor = "v2", verbose = FALSE)
    return(x)
  })

  # Select features and prep for SCT integration
  features <- SelectIntegrationFeatures(
    object.list = obj_list,
    nfeatures = anchor_features
  )
  obj_list <- PrepSCTIntegration(
    object.list = obj_list,
    anchor.features = features
  )

  # Find anchors (must specify normalization.method = "SCT")
  anchors <- FindIntegrationAnchors(
    object.list = obj_list,
    normalization.method = "SCT",
    anchor.features = features,
    dims = dims,
    reduction = "cca"
  )
  integrated <- IntegrateData(
    anchorset = anchors,
    normalization.method = "SCT",
    dims = dims
  )

  integrated <- RunPCA(integrated, npcs = 50)

  return(integrated)
}
