#' GEO-specific loaders for spatial transcriptomics non-standard formats
#'
#' Reference: Seurat 5.0+
#'
#' Handles common GEO patterns for spatial data:
#' - GEO Visium: h5 file + spatial.tar.gz (not in standard outs/ structure)
#' - GEO Visium H5 only (no spatial images)

library(Seurat)


#' Prepare GEO Visium directory for standard loading
#'
#' GEO often provides Visium data as:
#'   - .h5 count file (e.g., GSM1234567_PA08.h5)
#'   - spatial.tar.gz (e.g., GSM1234567_PA08_spatial.tar.gz)
#'
#' This function restructures them into standard Space Ranger format:
#'   output_dir/
#'   ├── filtered_feature_bc_matrix.h5
#'   └── spatial/
#'       ├── tissue_positions_list.csv
#'       ├── scalefactors_json.json
#'       ├── tissue_lowres_image.png
#'       └── ...
#'
#' @param data.dir Directory containing GEO files
#' @param h5_pattern Pattern to match H5 file (default: '*.h5')
#' @param tar_pattern Pattern to match spatial tar.gz (default: '*spatial.tar.gz')
#' @param output_dir Where to create standard structure. If NULL, uses data.dir.
#' @return Path to the restructured directory ready for Load10X_Spatial()
#' @export
prepare_geo_visium_dir <- function(
  data.dir,
  h5_pattern = "*.h5",
  tar_pattern = "*spatial.tar.gz",
  output_dir = NULL
) {
  if (!dir.exists(data.dir)) {
    stop("Directory not found: ", data.dir)
  }

  if (is.null(output_dir)) {
    output_dir <- data.dir
  }

  # Create standard structure
  spatial_dir <- file.path(output_dir, "spatial")
  if (!dir.exists(spatial_dir)) {
    dir.create(spatial_dir, recursive = TRUE, showWarnings = FALSE)
  }

  # Find H5 file (pattern is a glob, convert to regex)
  h5_regex <- gsub("\\.", "\\\\.", gsub("\\*", ".*", h5_pattern))
  h5_files <- list.files(data.dir, pattern = h5_regex, full.names = TRUE)
  if (length(h5_files) == 0) {
    stop("No H5 file found in: ", data.dir)
  }

  # Find and extract spatial tar.gz
  tar_regex <- gsub("\\.", "\\\\.", gsub("\\*", ".*", tar_pattern))
  tar_files <- list.files(data.dir, pattern = tar_regex, full.names = TRUE)

  if (length(tar_files) > 0) {
    message(sprintf("Extracting spatial tar.gz: %s", basename(tar_files[1])))

    # Extract to temp first, then move
    temp_dir <- file.path(tempdir(), "geo_spatial_extract")
    if (dir.exists(temp_dir)) {
      unlink(temp_dir, recursive = TRUE)
    }
    dir.create(temp_dir, recursive = TRUE, showWarnings = FALSE)

    utils::untar(tar_files[1], exdir = temp_dir)

    # GEO tar.gz often contains a nested directory; find the actual spatial files
    extracted <- list.files(temp_dir, recursive = TRUE, full.names = TRUE)

    # Look for standard spatial files
    spatial_files <- extracted[
      grepl("tissue_positions|scalefactors|tissue_.*\\.png|detected_tissue_image",
            basename(extracted))
    ]

    if (length(spatial_files) == 0) {
      warning("No standard spatial files found in tar.gz. Using H5 only.")
    } else {
      # Move to spatial/ directory
      for (f in spatial_files) {
        file.copy(f, file.path(spatial_dir, basename(f)), overwrite = TRUE)
      }
      message(sprintf("  Copied %d spatial files to spatial/", length(spatial_files)))
    }

    unlink(temp_dir, recursive = TRUE)
  } else {
    warning("No spatial.tar.gz found. Loading H5 only.")
  }

  # Rename H5 to standard name
  target_h5 <- file.path(output_dir, "filtered_feature_bc_matrix.h5")
  if (h5_files[1] != target_h5) {
    file.copy(h5_files[1], target_h5, overwrite = TRUE)
    message(sprintf("  Copied H5 to: %s", basename(target_h5)))
  }

  return(output_dir)
}


#' Load GEO Visium data
#'
#' Handles GEO non-standard Visium format by restructuring files
#' and then calling Load10X_Spatial().
#'
#' @param data.dir Directory containing GEO files (.h5 + spatial.tar.gz)
#' @param sample_id Sample identifier to add to metadata
#' @param slice Slice name (default: "slice1")
#' @param prepare Logical. If TRUE, restructure files first. If FALSE,
#'   assume data.dir is already in standard format.
#' @param ... Additional arguments passed to Load10X_Spatial()
#' @return Seurat object with spatial data
#' @export
load_geo_visium <- function(
  data.dir,
  sample_id = NULL,
  slice = "slice1",
  prepare = TRUE,
  ...
) {
  if (prepare) {
    data.dir <- prepare_geo_visium_dir(data.dir)
  }

  obj <- Seurat::Load10X_Spatial(
    data.dir = data.dir,
    filename = "filtered_feature_bc_matrix.h5",
    slice = slice,
    ...
  )

  if (!is.null(sample_id)) {
    obj$sample_id <- sample_id
  }

  message(sprintf(
    "Loaded GEO Visium: %d spots x %d genes",
    ncol(obj), nrow(obj)
  ))

  return(obj)
}


#' Load GEO Visium H5 file only (no spatial images)
#'
#' For GEO entries that only provide the H5 count file without spatial data.
#'
#' @param h5_path Path to .h5 file
#' @param sample_id Sample identifier
#' @param assay Assay name (default: "Spatial")
#' @param ... Additional arguments passed to Read10X_h5()
#' @return Seurat object without spatial images
#' @export
load_geo_visium_h5 <- function(
  h5_path,
  sample_id = NULL,
  assay = "Spatial",
  ...
) {
  if (!file.exists(h5_path)) {
    stop("H5 file not found: ", h5_path)
  }

  counts <- Seurat::Read10X_h5(filename = h5_path, ...)
  obj <- Seurat::CreateSeuratObject(counts = counts, assay = assay)

  if (!is.null(sample_id)) {
    obj$sample_id <- sample_id
  }

  message(sprintf(
    "Loaded GEO Visium H5: %d spots x %d genes (no spatial images)",
    ncol(obj), nrow(obj)
  ))

  return(obj)
}
