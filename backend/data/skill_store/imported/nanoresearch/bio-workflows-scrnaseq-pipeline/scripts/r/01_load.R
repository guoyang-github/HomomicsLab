#' Step 1: Load Data — Single-Cell RNA-seq Pipeline (R)
#'
#' Reference: Seurat 5.0+, bio-single-cell-data-io
#'
#' Supports:
#' - 10X Cell Ranger output (filtered_feature_bc_matrix/)
#' - 10X H5 file (.h5)
#' - SampleSheet CSV (multi-sample)
#' - GEO non-standard formats (via bio-single-cell-data-io)
#'
#' Output State: [Raw]

library(Seurat)

# Load skill registry for dependency resolution
this_dir <- dirname(sys.frame(1)$ofile)
if (is.null(this_dir) || this_dir == ".") {
  this_dir <- getwd()
}
source(file.path(this_dir, "_skill_registry.R"))


# ---------------------------------------------------------------------------
# Single-sample loaders
# ---------------------------------------------------------------------------

load_10x_mtx <- function(data_dir, project = "scRNAseq", min.cells = 3, min.features = 200) {
  counts <- Read10X(data.dir = data_dir)
  # Ensure unique gene names to prevent downstream issues
  rownames(counts) <- make.names(rownames(counts), unique = TRUE)
  obj <- CreateSeuratObject(counts = counts, project = project,
                            min.cells = min.cells, min.features = min.features)
  message(sprintf("Loaded 10X MTX: %d cells x %d genes", ncol(obj), nrow(obj)))
  return(obj)
}

load_10x_h5 <- function(h5_path, project = "scRNAseq") {
  counts <- Read10X_h5(filename = h5_path)
  obj <- CreateSeuratObject(counts = counts, project = project)
  message(sprintf("Loaded 10X H5: %d cells x %d genes", ncol(obj), nrow(obj)))
  return(obj)
}

load_seurat_rds <- function(rds_path) {
  obj <- readRDS(rds_path)
  message(sprintf("Loaded RDS: %d cells x %d genes", ncol(obj), nrow(obj)))
  return(obj)
}


# ---------------------------------------------------------------------------
# Multi-sample loader via SampleSheet
# ---------------------------------------------------------------------------

load_from_samplesheet <- function(sheet_path, merge = TRUE) {
  #' Delegates to bio-single-cell-data-io skill via the skill registry.
  #' Resolution order: env var > registry file > relative fallback.
  data_io_dir <- resolve_skill_path("bio-single-cell-data-io", "scripts/r")
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

load_data <- function(path, project = "scRNAseq", ...) {
  #' Load single-cell data with automatic format detection.
  #'
  #' @param path Path to data file or directory.
  #' @param project Project name prefix.
  #' @param ... Additional arguments passed to format-specific loaders.
  #' @return Seurat object with state [Raw].

  if (grepl("\\.csv$", path, ignore.case = TRUE)) {
    # SampleSheet
    obj <- load_from_samplesheet(path, merge = TRUE)
  } else if (grepl("\\.h5$", path, ignore.case = TRUE)) {
    obj <- load_10x_h5(path, project = project)
  } else if (grepl("\\.rds$", path, ignore.case = TRUE)) {
    obj <- load_seurat_rds(path)
  } else if (dir.exists(path)) {
    # Check for 10X MTX structure
    if (file.exists(file.path(path, "matrix.mtx")) ||
        file.exists(file.path(path, "matrix.mtx.gz"))) {
      obj <- load_10x_mtx(path, project = project, ...)
    } else {
      stop("Directory does not contain recognized 10X MTX files: ", path)
    }
  } else {
    stop("Unsupported file format or path does not exist: ", path)
  }

  # Tag state
  obj@misc$pipeline_state <- "Raw"
  obj@misc$pipeline_project <- project

  return(obj)
}
