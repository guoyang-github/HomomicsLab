#' SampleSheet-based single-cell data loading for Seurat
#'
#' Reference: Seurat 5.0+
#'
#' This module provides:
#' - read_samplesheet(): validate and read a SampleSheet CSV
#' - load_from_samplesheet(): load all samples and optionally merge
#'
#' SampleSheet format (CSV):
#'     sample_id,file_path,file_format,condition,batch,technology
#'     PA08,data/PA08/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3
#'     PA11,data/PA11/filtered_feature_bc_matrix,10x_mtx,High_NI,Batch1,10x_v3
#'
#' Required columns: sample_id, file_path, file_format
#' Optional columns: condition, batch, technology, sex, age, note

library(Seurat)


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

#' Load all samples from a SampleSheet
#'
#' @param sheet_path Path to SampleSheet CSV.
#' @param merge Logical. If TRUE (default), merge all samples into one
#'   Seurat object. If FALSE, return a named list of Seurat objects.
#' @param min.cells,min.features Passed to CreateSeuratObject.
#' @return Seurat object if merge=TRUE, named list if merge=FALSE.
#'   For a single sample, always returns a Seurat object.
#' @export
load_from_samplesheet <- function(
  sheet_path,
  merge = TRUE,
  min.cells = 3,
  min.features = 200
) {
  sheet <- read_samplesheet(sheet_path)

  obj_list <- list()

  for (i in seq_len(nrow(sheet))) {
    row <- sheet[i, ]
    sample_id <- row$sample_id
    file_path <- row$file_path
    fmt <- row$file_format

    # Route to format-specific loader
    obj <- .load_one_sample(
      file_path = file_path,
      fmt = fmt,
      sample_id = sample_id,
      sheet_row = row,
      min.cells = min.cells,
      min.features = min.features
    )

    # Inject metadata from SampleSheet optional columns
    for (col in c("condition", "batch", "technology", "sex", "age", "note")) {
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

  # Merge with add.cell.ids
  merged <- merge(
    obj_list[[1]],
    y = obj_list[-1],
    add.cell.ids = names(obj_list)
  )

  message(sprintf(
    "Merged %d samples: %d cells x %d features",
    length(obj_list), ncol(merged), nrow(merged)
  ))

  return(merged)
}


# ---------------------------------------------------------------------------
# Format-specific loaders
# ---------------------------------------------------------------------------

.load_one_sample <- function(
  file_path, fmt, sample_id, sheet_row,
  min.cells = 3, min.features = 200
) {
  if (fmt == "10x_mtx") {
    counts <- Read10X(data.dir = file_path)
    obj <- CreateSeuratObject(
      counts = counts, project = sample_id,
      min.cells = min.cells, min.features = min.features
    )
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "10x_h5") {
    counts <- Read10X_h5(filename = file_path)
    obj <- CreateSeuratObject(
      counts = counts, project = sample_id,
      min.cells = min.cells, min.features = min.features
    )
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "geo_mtx") {
    counts <- Read10X(data.dir = file_path)
    obj <- CreateSeuratObject(
      counts = counts, project = sample_id,
      min.cells = min.cells, min.features = min.features
    )
    obj$sample_id <- sample_id
    return(obj)
  }

  if (fmt == "geo_mtx_merged") {
    metadata_csv <- NULL
    if ("metadata_csv" %in% colnames(sheet_row) && !is.na(sheet_row$metadata_csv)) {
      metadata_csv <- sheet_row$metadata_csv
    } else {
      candidates <- c(
        file.path(dirname(file_path), paste0(sample_id, "_metadata.csv")),
        file.path(dirname(file_path), "metadata.csv"),
        file.path(dirname(file_path), "cell_metadata.csv")
      )
      for (cand in candidates) {
        if (file.exists(cand)) {
          metadata_csv <- cand
          break
        }
      }
    }
    if (is.null(metadata_csv)) {
      stop(
        "geo_mtx_merged requires metadata_csv. ",
        "Add 'metadata_csv' column to SampleSheet or place ",
        "metadata.csv in ", dirname(file_path)
      )
    }
    return(load_geo_mtx_merged(
      mtx_dir = file_path,
      metadata_csv = metadata_csv,
      sample_col = "sample_id",
      min.cells = min.cells,
      min.features = min.features
    ))
  }

  if (fmt == "geo_h5") {
    return(load_geo_h5(
      h5_path = file_path,
      sample_id = sample_id,
      min.cells = min.cells,
      min.features = min.features
    ))
  }

  if (fmt == "rds") {
    obj <- readRDS(file_path)
    if (!inherits(obj, "Seurat")) {
      stop("RDS file does not contain a Seurat object: ", file_path)
    }
    if (!("sample_id" %in% colnames(obj@meta.data))) {
      obj$sample_id <- sample_id
    }
    return(obj)
  }

  if (fmt == "h5ad") {
    stop(
      "Cannot load h5ad file '", file_path, "' in R. ",
      "Use Python workflow or convert to RDS first."
    )
  }

  stop("Unsupported format: ", fmt)
}
