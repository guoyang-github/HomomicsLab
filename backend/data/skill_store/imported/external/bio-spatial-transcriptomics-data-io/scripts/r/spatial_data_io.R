#' Spatial Transcriptomics Data I/O (R)
#'
#' R wrapper functions for loading spatial transcriptomics data into Seurat objects.
#' Supports 10X Visium, Xenium, MERFISH (Vizgen), and CosMx.
#'
#' @author Yang Guo
#' @date 2026-04-14
#' @version 1.0.0

#' Load 10X Visium Spatial Data
#'
#' Reads Space Ranger output into a Seurat object with spatial images and coordinates.
#'
#' @param data.dir Path to Space Ranger output directory (containing spatial/ and filtered_feature_bc_matrix.h5)
#' @param filename Name of the h5 count file (default: "filtered_feature_bc_matrix.h5")
#' @param assay Assay name (default: "Spatial")
#' @param slice Slice/image name (default: "slice1")
#' @param filter.matrix Whether to filter the matrix (default: TRUE)
#' @param ... Additional arguments passed to Load10X_Spatial()
#'
#' @return Seurat object with spatial data
#'
#' @examples
#' \dontrun{
#' seurat_obj <- load_visium("spaceranger_output/")
#' }
#'
#' @export
load_visium <- function(
    data.dir,
    filename = "filtered_feature_bc_matrix.h5",
    assay = "Spatial",
    slice = "slice1",
    filter.matrix = TRUE,
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (!dir.exists(data.dir)) {
    stop(sprintf("Directory not found: %s", data.dir))
  }

  message(sprintf("Loading Visium data from: %s", data.dir))

  seurat_obj <- Seurat::Load10X_Spatial(
    data.dir = data.dir,
    filename = filename,
    assay = assay,
    slice = slice,
    filter.matrix = filter.matrix,
    ...
  )

  message(sprintf("Loaded %d spots x %d genes", ncol(seurat_obj), nrow(seurat_obj)))

  return(seurat_obj)
}


#' Load 10X Visium from H5 File Only
#'
#' Loads Visium h5 file without spatial images. Useful when only expression is needed.
#' Use load_visium() for full spatial data.
#'
#' @param filename Path to .h5 file
#' @param assay Assay name (default: "Spatial")
#' @param ... Additional arguments passed to Read10X_h5()
#'
#' @return Seurat object
#'
#' @export
load_visium_h5 <- function(
    filename,
    assay = "Spatial",
    ...
) {
  if (!file.exists(filename)) {
    stop(sprintf("File not found: %s", filename))
  }

  message(sprintf("Loading Visium h5 file: %s", filename))

  counts <- Seurat::Read10X_h5(filename = filename, ...)
  seurat_obj <- Seurat::CreateSeuratObject(counts = counts, assay = assay)

  message(sprintf("Loaded %d spots x %d genes", ncol(seurat_obj), nrow(seurat_obj)))

  return(seurat_obj)
}


#' Load 10X Xenium Spatial Data
#'
#' Reads Xenium output into a Seurat object with single-cell resolution spatial coordinates.
#'
#' @param data.dir Path to Xenium output directory
#' @param fov Name of the field of view (default: "fov")
#' @param assay Assay name (default: "Xenium")
#' @param ... Additional arguments passed to LoadXenium()
#'
#' @return Seurat object with single-cell spatial data
#'
#' @examples
#' \dontrun{
#' seurat_obj <- load_xenium("xenium_output/")
#' }
#'
#' @export
load_xenium <- function(
    data.dir,
    fov = "fov",
    assay = "Xenium",
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (!dir.exists(data.dir)) {
    stop(sprintf("Directory not found: %s", data.dir))
  }

  message(sprintf("Loading Xenium data from: %s", data.dir))

  seurat_obj <- Seurat::LoadXenium(
    data.dir = data.dir,
    fov = fov,
    assay = assay,
    ...
  )

  message(sprintf("Loaded %d cells x %d genes", ncol(seurat_obj), nrow(seurat_obj)))

  return(seurat_obj)
}


#' Load Nanostring CosMx Spatial Data
#'
#' Reads CosMx output into a Seurat object.
#'
#' @param data.dir Path to CosMx output directory
#' @param assay Assay name (default: "CosMx")
#' @param ... Additional arguments passed to LoadCosMx()
#'
#' @return Seurat object
#'
#' @export
load_cosmx <- function(
    data.dir,
    assay = "CosMx",
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (!dir.exists(data.dir)) {
    stop(sprintf("Directory not found: %s", data.dir))
  }

  message(sprintf("Loading CosMx data from: %s", data.dir))

  seurat_obj <- Seurat::LoadCosMx(
    data.dir = data.dir,
    assay = assay,
    ...
  )

  message(sprintf("Loaded %d cells x %d genes", ncol(seurat_obj), nrow(seurat_obj)))

  return(seurat_obj)
}


#' Load MERFISH (Vizgen) Spatial Data
#'
#' Reads MERFISH/Vizgen output into a Seurat object.
#'
#' @param data.dir Path to Vizgen output directory
#' @param fov Name of the field of view (default: "merfish")
#' @param assay Assay name (default: "MERFISH")
#' @param ... Additional arguments passed to LoadMERFISH()
#'
#' @return Seurat object
#'
#' @export
load_merfish <- function(
    data.dir,
    fov = "merfish",
    assay = "MERFISH",
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (!dir.exists(data.dir)) {
    stop(sprintf("Directory not found: %s", data.dir))
  }

  message(sprintf("Loading MERFISH data from: %s", data.dir))

  seurat_obj <- Seurat::LoadMERFISH(
    data.dir = data.dir,
    fov = fov,
    assay = assay,
    ...
  )

  message(sprintf("Loaded %d cells x %d genes", ncol(seurat_obj), nrow(seurat_obj)))

  return(seurat_obj)
}


#' Get Spatial Coordinates from Seurat Object
#'
#' Extracts spatial coordinates as a data frame.
#'
#' @param seurat_obj Seurat object with spatial data
#' @param image Name of the image/slice (default: NULL, auto-detects first image)
#' @param scale Scale factor to apply (default: NULL, returns coordinates in pixel space)
#'
#' @return Data frame with spatial coordinates (columns depend on technology)
#'
#' @export
get_spatial_coords <- function(seurat_obj, image = NULL, scale = NULL) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (is.null(image)) {
    image <- Seurat::Images(seurat_obj)[1]
  }

  if (is.null(image) || is.na(image)) {
    stop("No spatial images found in Seurat object")
  }

  coords <- Seurat::GetTissueCoordinates(seurat_obj, image = image, scale = scale)

  message(sprintf("Extracted coordinates for %d cells/spots", nrow(coords)))

  return(coords)
}


#' Get Scale Factors from Visium Seurat Object
#'
#' Extracts scale factors from the spatial image slot.
#'
#' @param seurat_obj Seurat object with Visium spatial data
#' @param image Name of the image/slice (default: NULL, auto-detects first image)
#'
#' @return List with scale factors
#'
#' @export
get_scalefactors <- function(seurat_obj, image = NULL) {
  if (is.null(image)) {
    image <- Seurat::Images(seurat_obj)[1]
  }

  if (is.null(image) || is.na(image)) {
    stop("No spatial images found in Seurat object")
  }

  sf <- seurat_obj@images[[image]]@scale.factors

  return(sf)
}


#' Load Scale Factors from JSON File
#'
#' Reads the scalefactors_json.json file produced by Space Ranger.
#'
#' @param json_path Path to scalefactors_json.json
#'
#' @return List with scale factors
#'
#' @export
load_scalefactors_json <- function(json_path) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("jsonlite package required")
  }

  if (!file.exists(json_path)) {
    stop(sprintf("File not found: %s", json_path))
  }

  sf <- jsonlite::fromJSON(txt = json_path)

  message(sprintf("Loaded scalefactors from: %s", json_path))

  return(sf)
}


#' Merge Multiple Spatial Samples
#'
#' Merges a list of Seurat spatial objects and joins layers.
#'
#' @param seurat_list List of Seurat objects
#' @param sample_names Character vector of sample names
#' @param merge.data Whether to merge data slots (default: TRUE)
#'
#' @return Merged Seurat object
#'
#' @examples
#' \dontrun{
#' merged <- merge_spatial_samples(
#'   seurat_list = list(s1, s2, s3),
#'   sample_names = c("S1", "S2", "S3")
#' )
#' }
#'
#' @export
merge_spatial_samples <- function(
    seurat_list,
    sample_names = NULL,
    merge.data = TRUE
) {
  if (!is.list(seurat_list) || length(seurat_list) < 2) {
    stop("seurat_list must be a list of at least 2 Seurat objects")
  }

  if (is.null(sample_names)) {
    sample_names <- paste0("Sample", seq_along(seurat_list))
  }

  if (length(seurat_list) != length(sample_names)) {
    stop("seurat_list and sample_names must have the same length")
  }

  message(sprintf("Merging %d spatial samples...", length(seurat_list)))

  # Merge all objects
  merged <- Seurat::merge(
    x = seurat_list[[1]],
    y = seurat_list[-1],
    add.cell.ids = sample_names,
    merge.data = merge.data
  )

  # Join layers for Seurat v5
  if (methods::is(merged[[Seurat::DefaultAssay(merged)]], "Assay5")) {
    merged <- SeuratObject::JoinLayers(merged)
    message("Joined layers for Seurat v5")
  }

  # Add sample metadata
  origin <- sapply(strsplit(colnames(merged), "_"), `[`, 1)
  merged$sample <- origin

  message(sprintf("Merged object: %d spots/cells x %d genes", ncol(merged), nrow(merged)))

  return(merged)
}


#' Read Spatial H5AD into Seurat
#'
#' Converts an h5ad file to Seurat via h5Seurat intermediate format.
#' Requires SeuratDisk.
#'
#' @param h5ad_path Path to .h5ad file
#' @param cleanup Whether to remove the intermediate .h5seurat file (default: TRUE)
#'
#' @return Seurat object
#'
#' @examples
#' \dontrun{
#' seurat_obj <- read_spatial_h5ad("spatial_data.h5ad")
#' }
#'
#' @export
read_spatial_h5ad <- function(h5ad_path, cleanup = TRUE) {
  if (!requireNamespace("SeuratDisk", quietly = TRUE)) {
    stop("SeuratDisk package required. Install with: remotes::install_github('mojaveazure/seurat-disk')")
  }

  if (!file.exists(h5ad_path)) {
    stop(sprintf("File not found: %s", h5ad_path))
  }

  h5seurat_path <- sub("\\.h5ad$", ".h5seurat", h5ad_path)

  message("Converting h5ad to h5seurat...")
  SeuratDisk::Convert(h5ad_path, dest = "h5seurat", overwrite = TRUE)

  message("Loading h5seurat into Seurat...")
  seurat_obj <- SeuratDisk::LoadH5Seurat(h5seurat_path)

  if (cleanup && file.exists(h5seurat_path)) {
    unlink(h5seurat_path)
    message("Cleaned up intermediate h5seurat file")
  }

  return(seurat_obj)
}


#' Save Seurat Spatial Object
#'
#' Saves a Seurat object to RDS format.
#'
#' @param seurat_obj Seurat object
#' @param file Output file path (default: "seurat_obj.rds")
#'
#' @export
save_seurat <- function(seurat_obj, file = "seurat_obj.rds") {
  saveRDS(seurat_obj, file = file)
  message(sprintf("Saved to: %s", file))
}
