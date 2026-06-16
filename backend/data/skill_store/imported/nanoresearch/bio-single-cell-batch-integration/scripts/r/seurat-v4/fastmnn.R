# fastMNN integration - Seurat V4
# Reference: batchelor 1.18+, SingleCellExperiment 1.24+, Seurat 4.4+
#
# MNN-based correction preserving rare populations.
# Input: merged Seurat object (prepared via prepare_input_v4).
# Output: Seurat object with MNN-corrected embedding.

library(Seurat)
library(batchelor)
library(SingleCellExperiment)


#------------------------------------------------------------------------------
# fastMNN Integration
#------------------------------------------------------------------------------

#' fastMNN Integration - Seurat V4
#'
#' MNN-based batch correction preserving rare cell populations.
#' Converts Seurat to SingleCellExperiment, runs fastMNN, extracts embedding.
#'
#' @param obj Merged Seurat object
#' @param batch_col Metadata column defining batches (default: "sample")
#' @param d fastMNN dimensions (default: 30)
#' @param k fastMNN k parameter (default: 20)
#'
#' @return Seurat object with MNN reduction. No downstream clustering performed.
#'
#' @examples
#' \dontrun{
#' source("scripts/r/utils.R")
#' prep <- prepare_input_v4(obj = merged_obj, batch_col = "sample")
#'
#' source("scripts/r/seurat-v4/fastmnn.R")
#' obj <- fastmnn_v4(obj = prep$obj, batch_col = "sample")
#' }
#'
#' @export
fastmnn_v4 <- function(obj, batch_col = "sample", d = 30, k = 20) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("batchelor", quietly = TRUE)) {
    stop("batchelor package required. Install: BiocManager::install('batchelor')")
  }
  if (!requireNamespace("SingleCellExperiment", quietly = TRUE)) {
    stop("SingleCellExperiment package required")
  }
  if (!inherits(obj, "Seurat")) {
    stop("'obj' must be a Seurat object")
  }
  if (!batch_col %in% colnames(obj@meta.data)) {
    stop(sprintf("Batch column '%s' not found in metadata", batch_col))
  }

  # Preprocess
  obj <- NormalizeData(obj)
  obj <- FindVariableFeatures(obj, selection.method = "vst", nfeatures = 2000)
  obj <- ScaleData(obj)
  obj <- RunPCA(obj, npcs = 50)

  # Convert to SingleCellExperiment
  sce <- as.SingleCellExperiment(obj)

  # Run fastMNN
  corrected <- fastMNN(sce, batch = colData(sce)[[batch_col]], d = d, k = k)

  # Extract corrected embedding back to Seurat
  reducedDim(sce, "MNN") <- reducedDim(corrected, "corrected")
  mnn_emb <- as.matrix(reducedDim(sce, "MNN"))
  obj[["mnn"]] <- CreateDimReducObject(embeddings = mnn_emb, key = "MNN_")

  return(obj)
}
