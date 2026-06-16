#' Step 1: Load Spatial Data — Spatial Transcriptomics Pipeline (R)
#'
#' Reference: Seurat 5.0+, SeuratObject, bio-spatial-transcriptomics-data-io
#'
#' Supports:
#' - 10X Visium (Space Ranger output directory)
#' - 10X Xenium (output directory)
#' - Seurat RDS / h5Seurat (resume)
#' - SampleSheet CSV (multi-sample)
#'
#' Output State: [Raw]

library(Seurat)

# Load skill registry for dependency resolution
.this_file <- if (!is.null(sys.frame(1)$ofile)) sys.frame(1)$ofile else NULL
if (is.null(.this_file) || .this_file == ".") {
  this_dir <- getwd()
} else {
  this_dir <- dirname(.this_file)
}
source(file.path(this_dir, "_skill_registry.R"))


# ---------------------------------------------------------------------------
# Single-sample loaders
# ---------------------------------------------------------------------------

load_visium <- function(data_dir, project = "Spatial") {
  #' Load 10X Visium Space Ranger output.
  obj <- Load10X_Spatial(data.dir = data_dir, project = project)
  message(sprintf("Loaded Visium: %d spots x %d genes", ncol(obj), nrow(obj)))
  return(obj)
}

load_xenium <- function(data_dir, project = "Xenium") {
  #' Load 10X Xenium output.
  obj <- LoadXenium(data.dir = data_dir, outs = "cells")
  message(sprintf("Loaded Xenium: %d cells x %d genes", ncol(obj), nrow(obj)))
  return(obj)
}

load_seurat_rds <- function(rds_path) {
  #' Load existing Seurat RDS or h5Seurat.
  if (grepl("\\.h5seurat$", rds_path, ignore.case = TRUE)) {
    if (!requireNamespace("SeuratDisk", quietly = TRUE)) {
      stop("h5Seurat requires SeuratDisk. Install: remotes::install_github('mojaveazure/seurat-disk')")
    }
    obj <- SeuratDisk::LoadH5Seurat(rds_path)
  } else {
    obj <- readRDS(rds_path)
  }
  message(sprintf("Loaded RDS: %d spots x %d genes", ncol(obj), nrow(obj)))
  return(obj)
}


# ---------------------------------------------------------------------------
# Multi-sample loader via SampleSheet
# ---------------------------------------------------------------------------

load_from_samplesheet <- function(sheet_path, merge = TRUE) {
  #' Delegates to bio-spatial-transcriptomics-data-io skill via registry.
  data_io_dir <- resolve_skill_path("bio-spatial-transcriptomics-data-io", "scripts/r")
  local_env <- new.env()
  source(file.path(data_io_dir, "samplesheet.R"), local = local_env)
  if (!exists("load_from_samplesheet", envir = local_env)) {
    stop("samplesheet.R does not define 'load_from_samplesheet'")
  }
  loader <- get("load_from_samplesheet", envir = local_env)
  obj <- loader(sheet_path, merge = merge)
  return(obj)
}


# ---------------------------------------------------------------------------
# Main entry: auto-detect format and load
# ---------------------------------------------------------------------------

load_spatial_data <- function(path, project = "Spatial", ...) {
  #' Load spatial transcriptomics data with automatic format detection.
  #'
  #' @param path Path to data file or directory.
  #' @param project Project name prefix.
  #' @param ... Additional arguments passed to format-specific loaders.
  #' @return Seurat object with state [Raw] and spatial coords in images slot.

  if (grepl("\\.csv$", path, ignore.case = TRUE)) {
    obj <- load_from_samplesheet(path, merge = TRUE)
  } else if (grepl("\\.(rds|h5seurat)$", path, ignore.case = TRUE)) {
    obj <- load_seurat_rds(path)
  } else if (dir.exists(path)) {
    # Auto-detect Visium vs Xenium
    if (file.exists(file.path(path, "spatial")) ||
        file.exists(file.path(path, "tissue_positions_list.csv")) ||
        file.exists(file.path(path, "spatial", "tissue_positions_list.csv"))) {
      obj <- load_visium(path, project = project)
    } else if (file.exists(file.path(path, "cells.parquet")) ||
               file.exists(file.path(path, "cell_feature_matrix.h5"))) {
      obj <- load_xenium(path, project = project)
    } else {
      stop("Directory does not contain recognized spatial data: ", path)
    }
  } else {
    stop("Unsupported file format or path does not exist: ", path)
  }

  # Validate spatial data presence
  if (length(obj@images) == 0) {
    warning("No spatial images found. Some spatial analyses may not work.")
  }

  obj@misc$pipeline_state <- "Raw"
  obj@misc$pipeline_project <- project

  return(obj)
}
