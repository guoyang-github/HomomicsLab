# Centralized Input Preparation for Batch Integration
# Reference: Seurat 4.4+ / 5.0+
#
# This file provides input validation and preparation utilities used by
# all integration methods in seurat-v4/ and seurat-v5/.
#
# Usage:
#   source("scripts/r/utils.R")
#   prep <- prepare_input_v4(obj = merged_obj, sample_col = "sample")
#   # or: prep <- prepare_input_v4(file_paths = c("s1.rds", "s2.rds"), sample_col = "sample")
#   # or: prep <- prepare_input_v4(obj_list = list(s1, s2), sample_col = "sample")

library(Seurat)


#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

#' Sanitize Name for add.cell.ids / Image Slots
#'
#' Cleans special characters from names to ensure compatibility with
#' Seurat merge(add.cell.ids) and R list element names.
#'
#' Rules:
#'   - Spaces and special chars -> underscore
#'   - Consecutive underscores compressed
#'   - Leading/trailing underscores removed
#'   - Empty/NA names fallback to S{index}
#'   - Duplicate names resolved with numeric suffix
#'
#' @param name Raw name string
#' @param index Optional index for fallback naming
#' @param existing Optional character vector of already-sanitized names (for dedup)
#'
#' @return Cleaned name string
#' @keywords internal
.sanitize_name <- function(name, index = NULL, existing = NULL) {
  name <- gsub("[^a-zA-Z0-9_]", "_", name)
  name <- gsub("_+", "_", name)
  name <- gsub("^_|_$", "", name)

  if (name == "" || is.na(name)) {
    name <- sprintf("S%s", if (is.null(index)) "X" else as.character(index))
  }

  if (!is.null(existing) && name %in% existing) {
    name <- make.unique(c(existing, name))[length(existing) + 1]
  }

  return(name)
}


#' Validate and Set V5 Assay
#'
#' Checks that the "RNA" assay is a V5 StdAssay, sets it as default.
#' Errors if not V5.
#'
#' @param obj Seurat object
#' @return Invisibly validated object with RNA assay set as default
#' @keywords internal
.validate_and_set_v5_assay <- function(obj) {
  if (!("RNA" %in% names(obj@assays) && inherits(obj[["RNA"]], "StdAssay"))) {
    stop("No V5 RNA assay found. Use prepare_input_v4() for V4 objects.")
  }
  if (DefaultAssay(obj) != "RNA") {
    DefaultAssay(obj) <- "RNA"
  }
  return(obj)
}


#' Ensure V4 RNA Default Assay
#'
#' V4 Standard path requires RNA assay; switch back if SCT is active.
#'
#' @param obj Seurat object
#' @return Modified object with RNA as default if applicable
#' @keywords internal
.ensure_v4_rna_assay <- function(obj) {
  if (DefaultAssay(obj) == "SCT" && "RNA" %in% names(obj@assays)) {
    DefaultAssay(obj) <- "RNA"
  }
  return(obj)
}


#' Build Names for Object List
#'
#' Names each object in the list for use as `add.cell.ids` during merge.
#' Priority:
#'   1. Unique value from sample_col in object metadata (most reliable)
#'   2. User-provided identifier: basename(file_paths) or names(obj_list)
#'   3. S1, S2, ... (fallback)
#'
#' All names are sanitized via `.sanitize_name()` before assignment.
#'
#' @param obj_list List of Seurat objects
#' @param sample_col Metadata column to extract name from (default: "sample")
#' @param file_paths Optional file paths for basename fallback
#'
#' @return Named obj_list
#' @keywords internal
.build_names <- function(obj_list, sample_col = "sample", file_paths = NULL) {
  raw_names <- character(length(obj_list))

  for (i in seq_along(obj_list)) {
    o <- obj_list[[i]]
    nm <- NULL

    # 1. sample_col value (highest priority — from data itself)
    if (sample_col %in% colnames(o@meta.data)) {
      vals <- unique(o@meta.data[[sample_col]])
      vals <- vals[!is.na(vals)]
      if (length(vals) == 1) {
        nm <- as.character(vals)
      }
    }

    # 2. user-provided identifier
    if (is.null(nm)) {
      if (!is.null(file_paths) && i <= length(file_paths)) {
        nm <- gsub("\\.rds$", "", basename(file_paths[i]))
      } else {
        nm <- names(obj_list)[i]
        if (is.null(nm) || nm == "" || is.na(nm)) {
          nm <- NULL
        }
      }
    }

    # 3. S+index fallback
    if (is.null(nm)) {
      nm <- sprintf("S%d", i)
    }

    raw_names[i] <- nm
  }

  # Sanitize all names with deduplication
  sanitized <- character(length(raw_names))
  for (i in seq_along(raw_names)) {
    sanitized[i] <- .sanitize_name(raw_names[i], i, sanitized[seq_len(i - 1)])
  }

  names(obj_list) <- sanitized
  return(obj_list)
}


#------------------------------------------------------------------------------
# V4 Input Preparation
#------------------------------------------------------------------------------

#' Prepare Input for V4 Integration
#'
#' Accepts various input forms, validates, and outputs both a merged object
#' and a per-batch list. V4 functions use `prep$obj` (Harmony, fastMNN) or
#' `prep$obj_list` (CCA, RPCA).
#'
#' When multiple objects/files are provided, automatically names the obj_list
#' and passes names as `add.cell.ids` during merge.
#'
#' @param obj Merged Seurat object (optional)
#' @param obj_list List of Seurat objects per batch (optional)
#' @param file_paths Character vector of .rds file paths (optional)
#' @param sample_col Metadata column defining samples/batches (default: "sample")
#'
#' @return Named list with:
#'   - `obj`: merged Seurat object
#'   - `obj_list`: list of objects split by sample
#'
#' @examples
#' \dontrun{
#' prep <- prepare_input_v4(obj = merged_obj, sample_col = "sample")
#' prep <- prepare_input_v4(
#'   file_paths = c("s1.rds", "s2.rds", "s3.rds"),
#'   sample_col = "sample"
#' )
#' prep <- prepare_input_v4(obj_list = list(s1, s2), sample_col = "sample")
#' }
#'
#' @export
prepare_input_v4 <- function(obj = NULL, obj_list = NULL,
                             file_paths = NULL, sample_col = "sample") {
  if (sum(!sapply(list(obj, obj_list, file_paths), is.null)) != 1) {
    stop("Provide exactly one of: obj, obj_list, or file_paths")
  }

  # From file paths: load into obj_list, then fall through to obj_list branch
  if (!is.null(file_paths)) {
    if (!all(file.exists(file_paths))) {
      missing <- file_paths[!file.exists(file_paths)]
      stop(sprintf("File(s) not found: %s", paste(missing, collapse = ", ")))
    }
    obj_list <- lapply(file_paths, readRDS)
  }

  # From object list (or loaded from file_paths above): validate, build names, merge, split
  if (!is.null(obj_list)) {
    if (!is.list(obj_list) || length(obj_list) == 0) {
      stop("'obj_list' must be a non-empty list of Seurat objects")
    }
    if (any(!sapply(obj_list, inherits, "Seurat"))) {
      stop("All elements of 'obj_list' must be Seurat objects")
    }

    obj_list <- .build_names(obj_list, sample_col, file_paths)

    # Sync sample_col to names(obj_list) for consistent batch separation after merge
    for (i in seq_along(obj_list)) {
      obj_list[[i]]@meta.data[[sample_col]] <- names(obj_list)[i]
    }

    obj <- merge(obj_list[[1]], y = obj_list[-1],
                 add.cell.ids = names(obj_list))

    obj <- .ensure_v4_rna_assay(obj)

    obj_list <- SplitObject(obj, split.by = sample_col)
    return(list(obj = obj, obj_list = obj_list))
  }

  # From merged object: validate and split
  if (!is.null(obj)) {
    if (!inherits(obj, "Seurat")) {
      stop("'obj' must be a Seurat object")
    }
    if (!sample_col %in% colnames(obj@meta.data)) {
      stop(sprintf("Sample column '%s' not found in metadata. Columns: %s",
                   sample_col, paste(colnames(obj@meta.data), collapse = ", ")))
    }

    obj <- .ensure_v4_rna_assay(obj)

    obj_list <- SplitObject(obj, split.by = sample_col)
    return(list(obj = obj, obj_list = obj_list))
  }
}


#------------------------------------------------------------------------------
# V5 Input Preparation
#------------------------------------------------------------------------------

#' Prepare Input for V5 Integration
#'
#' Accepts merged object, object list, or file paths, validates, and returns
#' a merged Seurat object with V5 layers. V5 merge() auto-creates split layers.
#'
#' When multiple objects/files are provided, automatically names the obj_list
#' and passes names as `add.cell.ids` during merge.
#'
#' @param obj Merged Seurat object (optional)
#' @param obj_list List of Seurat objects per batch (optional)
#' @param file_paths Character vector of .rds file paths (optional)
#' @param sample_col Metadata column defining samples/batches (default: "sample")
#'
#' @return Merged Seurat object with layers.
#'
#' @examples
#' \dontrun{
#' obj <- prepare_input_v5(obj = merged_obj, sample_col = "sample")
#' obj <- prepare_input_v5(obj_list = list(s1, s2), sample_col = "sample")
#' obj <- prepare_input_v5(
#'   file_paths = c("s1.rds", "s2.rds", "s3.rds"),
#'   sample_col = "sample"
#' )
#' }
#'
#' @export
prepare_input_v5 <- function(obj = NULL, obj_list = NULL, file_paths = NULL,
                             sample_col = "sample") {
  if (sum(!sapply(list(obj, obj_list, file_paths), is.null)) != 1) {
    stop("Provide exactly one of: obj, obj_list, or file_paths")
  }

  # From file paths: load into obj_list
  if (!is.null(file_paths)) {
    if (!all(file.exists(file_paths))) {
      missing <- file_paths[!file.exists(file_paths)]
      stop(sprintf("File(s) not found: %s", paste(missing, collapse = ", ")))
    }
    obj_list <- lapply(file_paths, readRDS)
  }

  # From object list: validate, build names, merge
  if (!is.null(obj_list)) {
    if (!is.list(obj_list) || length(obj_list) == 0) {
      stop("'obj_list' must be a non-empty list of Seurat objects")
    }
    if (any(!sapply(obj_list, inherits, "Seurat"))) {
      stop("All elements of 'obj_list' must be Seurat objects")
    }

    obj_list <- .build_names(obj_list, sample_col, file_paths)

    # Sync sample_col to names(obj_list) for consistent batch separation after merge
    for (i in seq_along(obj_list)) {
      obj_list[[i]]@meta.data[[sample_col]] <- names(obj_list)[i]
    }

    # Set Project to names for consistent layer suffixes after merge
    for (i in seq_along(obj_list)) {
      Project(obj_list[[i]]) <- names(obj_list)[i]
    }

    obj <- merge(obj_list[[1]], y = obj_list[-1],
                 add.cell.ids = names(obj_list))

    obj <- .validate_and_set_v5_assay(obj)

    # Note: v5 assay merge already produces independent layers.
    # No split() needed here.

    return(obj)
  }

  # From merged object: validate and ensure layer mode
  if (!is.null(obj)) {
    if (!inherits(obj, "Seurat")) {
      stop("'obj' must be a Seurat object")
    }
    if (!sample_col %in% colnames(obj@meta.data)) {
      stop(sprintf("Sample column '%s' not found in metadata. Columns: %s",
                   sample_col, paste(colnames(obj@meta.data), collapse = ", ")))
    }

    obj <- .validate_and_set_v5_assay(obj)

    # Ensure layers are split by batch (only for already-merged objects)
    count_layers <- Layers(obj[["RNA"]], search = "counts")
    if (length(count_layers) <= 1) {
      # In Seurat v5, obj[[sample_col]] returns a data.frame; split() needs a vector/factor
      batch_vec <- obj@meta.data[[sample_col]]
      if (is.null(batch_vec)) {
        stop(sprintf("Sample column '%s' not found in metadata", sample_col))
      }
      obj[["RNA"]] <- split(obj[["RNA"]], f = batch_vec)
    }

    return(obj)
  }
}
