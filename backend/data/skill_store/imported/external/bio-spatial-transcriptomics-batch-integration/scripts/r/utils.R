# Spatial Transcriptomics Input Preparation for Batch Integration
# Reference: Seurat 5.0+
#
# This file provides input validation and preparation utilities for spatial
# batch integration. Key ST-specific handling:
#   - Image slot renaming before merge (prevents overwrite)
#   - Spatial data validation
#   - Platform detection
#
# Usage:
#   source("scripts/r/utils.R")
#   obj <- prepare_input_spatial(
#     file_paths = c("slice1.rds", "slice2.rds"),
#     sample_col = "sample"
#   )

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


' Build Names for Object List
#'
#' Names each object in the list for use as `add.cell.ids` during merge.
#' Also used as prefix for renaming image slots in spatial objects.
#'
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


#' Validate Merged Spatial Images
#'
#' Checks that all expected images are present and that coordinate rownames
#' match the merged cell barcodes.
#'
#' @param merged Merged Seurat object
#' @param obj_list Object list before merge
#'
#' @return Invisible NULL. Issues warnings for problems found.
#' @keywords internal
.validate_merged_images <- function(merged, obj_list) {
  n_expected <- sum(vapply(obj_list, function(o) length(o@images), integer(1L)))
  actual_images <- names(merged@images)

  if (length(actual_images) < n_expected) {
    warning(sprintf(
      "Merged object has %d image slot(s), expected %d. Some images may have been lost during merge.",
      length(actual_images), n_expected
    ))
  }

  all_cells <- colnames(merged)
  issues <- list()

  for (img_name in actual_images) {
    img <- merged@images[[img_name]]

    if (methods::.hasSlot(img, "coordinates")) {
      coords <- img@coordinates
      if (!is.null(coords) && nrow(coords) > 0) {
        coord_cells <- rownames(coords)
        unmatched <- setdiff(coord_cells, all_cells)
        if (length(unmatched) > 0) {
          issues[[img_name]] <- sprintf(
            "%d unmatched coordinates", length(unmatched)
          )
        }
      }
    }
  }

  if (length(issues) > 0) {
    msg <- paste(
      sprintf("  - %s: %s", names(issues), unlist(issues)),
      collapse = "\n"
    )
    warning(sprintf(
      "Image coordinate validation found issues in %d image(s):\n%s",
      length(issues), msg
    ))
  }

  invisible(NULL)
}


#' Validate and Set Spatial Assay
#'
#' Detects the spatial assay, sets it as default, and validates V5 StdAssay.
#'
#' @param obj Seurat object
#'
#' @return Invisibly validated object with spatial assay set as default
#' @keywords internal
.validate_and_set_spatial_assay <- function(obj) {
  spatial_assays <- c("Spatial", "Xenium", "CosMx", "MERFISH")
  spatial_assay <- spatial_assays[spatial_assays %in% names(obj@assays)][1]

  if (is.na(spatial_assay)) {
    spatial_assay <- DefaultAssay(obj)
    warning(sprintf(
      "No standard spatial assay found (%s). Falling back to default assay '%s'.",
      paste(spatial_assays, collapse = "/"),
      spatial_assay
    ))
  }

  DefaultAssay(obj) <- spatial_assay
  if (!inherits(obj[[spatial_assay]], "StdAssay")) {
    stop(sprintf(
      "Assay '%s' is not a V5 StdAssay. Spatial batch integration requires Seurat V5.",
      spatial_assay
    ))
  }
  return(obj)
}


#------------------------------------------------------------------------------
# Spatial Input Preparation
#------------------------------------------------------------------------------

#' Prepare Input for Spatial Batch Integration
#'
#' Accepts various input forms, validates spatial data, sets unique project
#' names to prevent merge conflicts, and returns a merged Seurat object with layers.
#'
#' CRITICAL: When merging multiple spatial objects, each object's images slot
#' must have unique names. Load10X_Spatial() defaults all images to "slice1",
#' which causes merge overwrite. This function auto-renames images before merge.
#'
#' Image slot renaming uses the same names as `add.cell.ids`, ensuring
#' consistency between image prefixes and cell barcodes.
#'
#' @param obj Merged spatial Seurat object (optional)
#' @param obj_list List of spatial Seurat objects (optional)
#' @param file_paths Character vector of .rds file paths (optional)
#' @param sample_col Metadata column defining samples/batches (default: "sample")
#'
#' @return Merged Seurat spatial object with:
#'   - Layers (V5) for batch-aware integration
#'   - Multiple uniquely-named image slots (one per original slice)
#'   - `sample_col` present in metadata
#'
#' @examples
#' \dontrun{
#' # From file paths
#' obj <- prepare_input_spatial(
#'   file_paths = c("slice1.rds", "slice2.rds"),
#'   sample_col = "sample"
#' )
#'
#' # From object list
#' obj <- prepare_input_spatial(
#'   obj_list = list(s1, s2),
#'   sample_col = "sample"
#' )
#'
#' # From already-merged object (validates + ensures layers)
#' obj <- prepare_input_spatial(obj = merged_obj, sample_col = "sample")
#' }
#'
#' @export
prepare_input_spatial <- function(obj = NULL, obj_list = NULL,
                                   file_paths = NULL, sample_col = "sample") {
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

  # From object list (or loaded from file_paths above): validate, build names, rename images, merge
  if (!is.null(obj_list)) {
    if (!is.list(obj_list) || length(obj_list) == 0) {
      stop("'obj_list' must be a non-empty list of Seurat objects")
    }
    if (any(!sapply(obj_list, inherits, "Seurat"))) {
      stop("All elements of 'obj_list' must be Seurat objects")
    }

    # Validate all are spatial objects
    for (i in seq_along(obj_list)) {
      o <- obj_list[[i]]
      if (length(o@images) == 0) {
        nm <- names(obj_list)[i]
        if (is.null(nm) || nm == "") nm <- sprintf("object_%d", i)
        stop(sprintf("'%s' has no images slot. Not a spatial object?", nm))
      }
    }

    # Detect platforms
    platforms <- vapply(obj_list, function(o) {
      assays <- names(o@assays)
      if ("Spatial" %in% assays) return("Visium")
      if ("Xenium" %in% assays) return("Xenium")
      if ("CosMx" %in% assays) return("CosMx")
      if ("MERFISH" %in% assays) return("MERFISH")
      return("Unknown")
    }, character(1))
    if (length(unique(platforms)) > 1) {
      warning(sprintf(
        "Multiple platforms detected: %s. Cross-platform integration is not recommended.",
        paste(unique(platforms), collapse = ", ")
      ))
    }

    # Build names (same logic as single-cell batch integration)
    obj_list <- .build_names(obj_list, sample_col, file_paths)

    # Sync sample_col to names(obj_list) for consistent batch separation after merge
    for (i in seq_along(obj_list)) {
      obj_list[[i]]@meta.data[[sample_col]] <- names(obj_list)[i]
    }

    # Rename image slots to prevent merge overwrite (all Visium images default to "slice1")
    for (i in seq_along(obj_list)) {
      prefix <- names(obj_list)[i]
      old_names <- names(obj_list[[i]]@images)
      names(obj_list[[i]]@images) <- paste0(prefix, "_", old_names)
    }

    # Set Project to names for consistent layer suffixes after merge
    for (i in seq_along(obj_list)) {
      Project(obj_list[[i]]) <- names(obj_list)[i]
    }

    # Merge with add.cell.ids = names(obj_list)
    merged <- merge(obj_list[[1]], y = obj_list[-1],
                    add.cell.ids = names(obj_list))

    # Validate: check all images present and coordinates match barcodes
    .validate_merged_images(merged, obj_list)

    merged <- .validate_and_set_spatial_assay(merged)

    # Note: v5 assay merge already produces independent layers (counts.S1, counts.S2).
    # No split() needed here.

    return(merged)
  }

  # From merged object: validate spatial + ensure layers
  if (!is.null(obj)) {
    if (!inherits(obj, "Seurat")) {
      stop("'obj' must be a Seurat object")
    }
    if (length(obj@images) == 0) {
      stop("'obj' has no images slot. Not a spatial object?")
    }
    if (!sample_col %in% colnames(obj@meta.data)) {
      stop(sprintf("Sample column '%s' not found in metadata. Columns: %s",
                   sample_col, paste(colnames(obj@meta.data), collapse = ", ")))
    }

    obj <- .validate_and_set_spatial_assay(obj)
    spatial_assay <- DefaultAssay(obj)

    # Ensure layers are split by batch (only for already-merged objects)
    count_layers <- Layers(obj[[spatial_assay]], search = "counts")
    if (length(count_layers) <= 1) {
      obj[[spatial_assay]] <- split(obj[[spatial_assay]], f = obj[[sample_col]])
    }

    return(obj)
  }
}


#------------------------------------------------------------------------------
# Utility: Extract image names per cell
#------------------------------------------------------------------------------

#' Get Image Name for Each Cell
#'
#' Maps each cell to the image slot it belongs to, based on which image's
#' coordinates contain the cell's barcode.
#'
#' @param obj Spatial Seurat object
#'
#' @return Named character vector: cell barcode -> image name
#'
#' @examples
#' \dontrun{
#' cell_images <- GetCellImageMapping(obj)
#' obj$image <- cell_images[colnames(obj)]
#' }
#'
#' @export
GetCellImageMapping <- function(obj) {
  if (length(obj@images) == 0) {
    stop("No images found in object")
  }

  mapping <- setNames(rep(NA_character_, ncol(obj)), colnames(obj))

  for (img_name in names(obj@images)) {
    img <- obj@images[[img_name]]
    if (is.null(img)) next

    cells_in_img <- NULL

    # Visium-style: coordinates rownames
    if (methods::.hasSlot(img, "coordinates")) {
      coords <- img@coordinates
      if (!is.null(coords)) {
        cells_in_img <- rownames(coords)
      }
    }

    # Xenium-style: centroids cells
    if (is.null(cells_in_img) && methods::.hasSlot(img, "centroids")) {
      centroids <- img@centroids
      if (!is.null(centroids) && methods::.hasSlot(centroids, "cells")) {
        cells_in_img <- centroids@cells
      }
    }

    if (!is.null(cells_in_img) && length(cells_in_img) > 0) {
      cells_in_obj <- intersect(cells_in_img, colnames(obj))
      mapping[cells_in_obj] <- img_name
    }
  }

  return(mapping)
}
