#' GEO-specific loaders for non-standard single-cell data formats.
#'
#' Reference: Seurat 5.0+
#'
#' Handles common GEO patterns:
#' - Merged MTX + separate metadata CSV
#' - GEO H5 files (same API as 10X H5)

library(Seurat)


#' Load a GEO merged MTX matrix with a separate metadata CSV
#'
#' Common GEO pattern: all cells in one MTX directory, metadata CSV maps
#' barcodes to samples and other cell-level metadata.
#'
#' @param mtx_dir Directory containing matrix.mtx[.gz], features.tsv[.gz],
#'   barcodes.tsv[.gz].
#' @param metadata_csv CSV with cell metadata. First column should be cell
#'   barcodes (row names).
#' @param sample_col Column in metadata indicating sample origin.
#' @param min.cells,min.features Passed to CreateSeuratObject.
#' @return Seurat object with sample info and all metadata columns in
#'   meta.data.
#' @export
load_geo_mtx_merged <- function(
  mtx_dir,
  metadata_csv,
  sample_col = "sample",
  min.cells = 3,
  min.features = 200
) {
  if (!dir.exists(mtx_dir)) {
    stop("MTX directory not found: ", mtx_dir)
  }
  if (!file.exists(metadata_csv)) {
    stop("Metadata CSV not found: ", metadata_csv)
  }

  counts <- Read10X(data.dir = mtx_dir)
  meta <- read.csv(metadata_csv, row.names = 1, stringsAsFactors = FALSE,
                    check.names = FALSE)

  # Align barcodes
  common_cells <- intersect(colnames(counts), rownames(meta))

  if (length(common_cells) == 0) {
    # Try stripping -1, -2 suffixes from counts barcodes
    stripped <- gsub("-[0-9]+$", "", colnames(counts))
    common_cells <- intersect(stripped, rownames(meta))
    if (length(common_cells) > 0) {
      colnames(counts) <- stripped
    }
  }

  if (length(common_cells) == 0) {
    stop(
      "No barcodes overlap between MTX and metadata. ",
      "MTX example: ", colnames(counts)[1],
      ", Meta example: ", rownames(meta)[1]
    )
  }

  counts <- counts[, common_cells, drop = FALSE]
  meta <- meta[common_cells, , drop = FALSE]

  obj <- CreateSeuratObject(
    counts = counts,
    meta.data = meta,
    min.cells = min.cells,
    min.features = min.features
  )

  message(sprintf(
    "Loaded %d cells x %d features from GEO MTX. Samples: %s",
    ncol(obj), nrow(obj),
    paste(table(obj@meta.data[[sample_col]]), collapse = ", ")
  ))

  return(obj)
}


#' Load a GEO H5 file
#'
#' GEO H5 files use the same format as 10X Cell Ranger H5.
#' This is a thin wrapper around Read10X_h5 for clarity.
#'
#' @param h5_path Path to .h5 file.
#' @param sample_id If provided, add to obj$sample_id.
#' @param min.cells,min.features Passed to CreateSeuratObject.
#' @return Seurat object.
#' @export
load_geo_h5 <- function(
  h5_path,
  sample_id = NULL,
  min.cells = 3,
  min.features = 200
) {
  if (!file.exists(h5_path)) {
    stop("H5 file not found: ", h5_path)
  }

  counts <- Read10X_h5(filename = h5_path)
  obj <- CreateSeuratObject(
    counts = counts,
    min.cells = min.cells,
    min.features = min.features
  )

  if (!is.null(sample_id)) {
    obj$sample_id <- sample_id
  }

  message(sprintf(
    "Loaded %d cells x %d features from GEO H5",
    ncol(obj), nrow(obj)
  ))

  return(obj)
}
