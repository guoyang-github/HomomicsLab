#' Utility functions for single-cell data loading.
#'
#' Reference: Seurat 5.0+, dplyr 1.1+


SUPPORTED_FORMATS <- c(
  "10x_mtx", "10x_h5", "geo_mtx", "geo_mtx_merged",
  "geo_h5", "h5ad", "rds"
)


#' Auto-detect file format from path
#'
#' Returns one of: 10x_mtx, 10x_h5, rds, h5ad, unknown.
#'
#' @param path File or directory path.
#' @return Character string format identifier.
#' @keywords internal
detect_format_from_path <- function(path) {
  if (dir.exists(path)) {
    has_matrix <- length(list.files(path, pattern = "matrix\\.mtx")) > 0
    has_features <- length(list.files(path, pattern = "features\\.tsv|genes\\.tsv")) > 0
    has_barcodes <- length(list.files(path, pattern = "barcodes\\.tsv")) > 0
    if (has_matrix && has_features && has_barcodes) {
      return("10x_mtx")
    }
    return("unknown")
  }

  ext <- tolower(tools::file_ext(path))
  if (ext == "h5") return("10x_h5")
  if (ext == "rds") return("rds")
  if (ext == "h5ad") return("h5ad")

  return("unknown")
}


#' Strip common barcode suffixes for alignment
#'
#' @param barcodes Character vector of barcodes.
#' @param suffixes Suffixes to strip (default: "-1", "-2").
#' @return Character vector with suffixes removed.
#' @keywords internal
strip_barcode_suffix <- function(barcodes, suffixes = c("-1", "-2")) {
  for (suf in suffixes) {
    barcodes <- gsub(paste0(suf, "$"), "", barcodes)
  }
  return(barcodes)
}
