#' SampleSheet-based spatial transcriptomics data loading for Seurat
#'
#' Reference: Seurat 5.0+
#'
#' This module provides:
#' - read_samplesheet(): validate and read a SampleSheet CSV
#' - load_from_samplesheet(): load all samples and optionally merge
#'
#' SampleSheet format (CSV):
#'     sample_id,file_path,file_format,technology,condition,batch,slide,slice
#'     PA08,data/PA08,visium,Tumor,Batch1,V10U01,slice1
#'     PA11,data/PA11,visium,Tumor,Batch1,V10U02,slice1
#'
#' Required columns: sample_id, file_path, file_format
#' Optional columns: technology, condition, batch, slide, slice, note

library(Seurat)


SUPPORTED_FORMATS <- c(
  "visium", "visium_h5", "xenium", "cosmx", "merfish",
  "geo_visium", "geo_visium_h5"
)


# ---------------------------------------------------------------------------
# SampleSheet I/O
# ---------------------------------------------------------------------------

#' Read and validate a SampleSheet CSV
#'
#' Validation rules:
#' - Required columns: sample_id, file_path, file_format
#' - sample_id must be unique and non-empty
#' - file_path must exist
#' - file_format must be in SUPPORTED_FORMATS
#' - Warns if batch column missing when n_samples > 1
#'
#' @param sheet_path Path to SampleSheet CSV.
#' @return Validated data.frame with one row per sample.
#' @export
read_samplesheet <- function(sheet_path) {
  if (!file.exists(sheet_path)) {
    stop("SampleSheet not found: ", sheet_path)
  }

  sheet <- read.csv(sheet_path, stringsAsFactors = FALSE, check.names = FALSE)

  # Required columns
  required <- c("sample_id", "file_path", "file_format")
  missing <- setdiff(required, colnames(sheet))
  if (length(missing) > 0) {
    stop("SampleSheet missing required columns: ", paste(missing, collapse = ", "))
  }

  # Unique sample_id
  if (any(duplicated(sheet$sample_id))) {
    dups <- unique(sheet$sample_id[duplicated(sheet$sample_id)])
    stop("Duplicate sample_id found: ", paste(dups, collapse = ", "))
  }

  # Non-empty sample_id
  empty_ids <- is.na(sheet$sample_id) | nzchar(trimws(sheet$sample_id)) == FALSE
  if (any(empty_ids)) {
    stop("sample_id contains empty or NA values")
  }

  # File existence
  for (i in seq_len(nrow(sheet))) {
    if (!file.exists(sheet$file_path[i])) {
      stop(
        "Path not found for sample '", sheet$sample_id[i], "': ",
        sheet$file_path[i]
      )
    }
  }

  # Format validation
  invalid <- setdiff(sheet$file_format, SUPPORTED_FORMATS)
  if (length(invalid) > 0) {
    stop(
      "Unsupported file_format: ", paste(invalid, collapse = ", "),
      ". Supported: ", paste(SUPPORTED_FORMATS, collapse = ", ")
    )
  }

  # Warn if batch missing with >1 sample
  if (nrow(sheet) > 1 && !("batch" %in% colnames(sheet))) {
    warning(
      "Multiple samples detected but 'batch' column not found. ",
      "Consider adding batch info for downstream integration.",
      call. = FALSE
    )
  }

  return(sheet)
}


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

#' Load all spatial samples from a SampleSheet
#'
#' @param sheet_path Path to SampleSheet CSV.
#' @param merge Logical. If TRUE (default), merge all samples into one
#'   Seurat object. If FALSE, return a named list of Seurat objects.
#' @param ... Additional arguments passed to technology-specific loaders.
#' @return Seurat object if merge=TRUE, named list if merge=FALSE.
#'   For a single sample, always returns a Seurat object.
#' @export
load_from_samplesheet <- function(sheet_path, merge = TRUE, ...) {
  sheet <- read_samplesheet(sheet_path)

  obj_list <- list()

  for (i in seq_len(nrow(sheet))) {
    row <- sheet[i, ]
    sample_id <- row$sample_id
    file_path <- row$file_path
    fmt <- row$file_format

    # Route to format-specific loader
    obj <- .load_one_spatial_sample(
      file_path = file_path,
      fmt = fmt,
      sample_id = sample_id,
      sheet_row = row,
      ...
    )

    # Inject metadata from SampleSheet optional columns
    for (col in c("condition", "batch", "technology", "slide", "slice", "note")) {
      if (col %in% colnames(row) && !is.na(row[[col]])) {
        obj[[col]] <- row[[col]]
      }
    }

    obj_list[[sample_id]] <- obj
  }

  # Single sample: return directly
  if (length(obj_list) == 1) {
    return(obj_list[[1]])
  }

  if (!merge) {
    return(obj_list)
  }

  # Merge spatial samples using existing utility
  script_dir <- dirname(sys.frame(1)$ofile)
  if (is.null(script_dir) || script_dir == ".") {
    script_dir <- getwd()
  }
  source(file.path(script_dir, "spatial_data_io.R"))
  merged <- merge_spatial_samples(
    seurat_list = obj_list,
    sample_names = names(obj_list)
  )

  return(merged)
}


# ---------------------------------------------------------------------------
# Format-specific loaders
# ---------------------------------------------------------------------------

.load_one_spatial_sample <- function(
  file_path, fmt, sample_id, sheet_row, ...
) {
  # Resolve script directory for sourcing helpers
  script_dir <- dirname(sys.frame(1)$ofile)
  if (is.null(script_dir) || script_dir == ".") {
    script_dir <- getwd()
  }
  # Source existing loaders
  source(file.path(script_dir, "spatial_data_io.R"))

  if (fmt == "visium") {
    slice_name <- if ("slice" %in% colnames(sheet_row) && !is.na(sheet_row$slice)) {
      sheet_row$slice
    } else {
      "slice1"
    }
    obj <- load_visium(
      data.dir = file_path,
      slice = slice_name,
      ...
    )
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "visium_h5") {
    obj <- load_visium_h5(filename = file_path, ...)
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "xenium") {
    fov_name <- if ("slice" %in% colnames(sheet_row) && !is.na(sheet_row$slice)) {
      sheet_row$slice
    } else {
      "fov"
    }
    obj <- load_xenium(data.dir = file_path, fov = fov_name, ...)
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "cosmx") {
    obj <- load_cosmx(data.dir = file_path, ...)
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "merfish") {
    fov_name <- if ("slice" %in% colnames(sheet_row) && !is.na(sheet_row$slice)) {
      sheet_row$slice
    } else {
      "merfish"
    }
    obj <- load_merfish(data.dir = file_path, fov = fov_name, ...)
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "geo_visium") {
    # GEO Visium: directory with h5 + spatial.tar.gz
    source(file.path(script_dir, "geo_loaders.R"))
    obj <- load_geo_visium(
      data.dir = file_path,
      sample_id = sample_id,
      ...
    )
    return(obj)
  }

  if (fmt == "geo_visium_h5") {
    # GEO Visium H5 only (no spatial images)
    source(file.path(script_dir, "geo_loaders.R"))
    obj <- load_geo_visium_h5(
      h5_path = file_path,
      sample_id = sample_id,
      ...
    )
    return(obj)
  }

  stop("Unsupported format: ", fmt)
}
