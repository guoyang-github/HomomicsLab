#' SPOTlight Deconvolution for Spatial Transcriptomics
#'
#' NMF-based deconvolution with marker gene integration.
#'
#' @author Yang Guo
#' @date 2026-03-31
#' @version 1.0.0

#' Run SPOTlight Deconvolution
#'
#' Deconvolute spatial spots using NMF with marker genes.
#'
#' @param spatial_counts Gene expression matrix for spatial data (genes x spots)
#' @param reference_counts Gene expression matrix for reference (genes x cells)
#' @param cell_types Named vector of cell type labels
#' @param marker_genes List of marker genes per cell type (optional)
#' @param n_hvg Number of HVGs to use (default: 3000)
#' @param nmf_rank NMF rank (default: NULL, auto-detect)
#' @param min_prop Minimum cell type proportion (default: 0.01)
#' @param max_prop Maximum cell type proportion (default: 1)
#' @param max_cores Number of cores (default: 1)
#'
#' @return List with deconvolution results and NMF model
#'
#' @export
#'
#' @examples
#' \dontrun{
#' results <- run_spotlight(
#'   spatial_counts = spatial_counts,
#'   reference_counts = ref_counts,
#'   cell_types = cell_types,
#'   marker_genes = marker_list,
#'   n_hvg = 3000
#' )
#'
#' # Extract proportions
#' props <- results$proportions
#' }
run_spotlight <- function(
    spatial_counts,
    reference_counts,
    cell_types,
    marker_genes = NULL,
    hvg_genes = NULL,
    nmf_rank = NULL,
    min_prop = 0.01,
    max_prop = 1,
    max_cores = 1
) {
  # Check dependencies
  if (!requireNamespace("SPOTlight", quietly = TRUE)) {
    stop("SPOTlight package required. Install with: devtools::install_github('Marcello-Sergio/SPOTlight')")
  }

  library(SPOTlight)
  library(Matrix)

  # Validate inputs
  if (length(cell_types) != ncol(reference_counts)) {
    stop("Length of cell_types must match ncol(reference_counts)")
  }

  message(sprintf("Running SPOTlight with %d spots and %d reference cells...",
                  ncol(spatial_counts), ncol(reference_counts)))

  # Find common genes
  common_genes <- intersect(rownames(spatial_counts), rownames(reference_counts))
  message(sprintf("Using %d common genes", length(common_genes)))

  spatial_counts <- spatial_counts[common_genes, ]
  reference_counts <- reference_counts[common_genes, ]

  # Run SPOTlight
  # Build argument list dynamically
  spotlight_args <- list(
    x = reference_counts,
    y = spatial_counts,
    groups = cell_types,
    mgs = marker_genes,
    weight_id = "mean.AUC",
    group_id = "cluster",
    gene_id = "gene"
  )
  if (!is.null(hvg_genes)) {
    spotlight_args$hvg <- hvg_genes
  }
  spotlight_ls <- do.call(SPOTlight::spotlight, spotlight_args)

  # Extract results
  # Extract results: SPOTlight returns list(mat=..., NMF=...)
  proportions <- spotlight_ls$mat

  # Clean up proportions (remove very small values)
  proportions[proportions < min_prop] <- 0
  proportions <- proportions / rowSums(proportions)
  proportions[is.na(proportions)] <- 0

  message("SPOTlight complete!")

  return(list(
    proportions = proportions,
    nmf_model = spotlight_ls$NMF
  ))
}


#' Run SPOTlight with Seurat
#'
#' @param spatial_seurat Seurat object for spatial data
#' @param reference_seurat Seurat object for reference
#' @param cell_type_column Column with cell type labels
#' @param marker_seurat Seurat object with marker genes (optional)
#' @param ... Additional arguments for run_spotlight()
#'
#' @return SPOTlight results
#'
#' @export
run_spotlight_seurat <- function(
    spatial_seurat,
    reference_seurat,
    cell_type_column = 'cell_type',
    marker_seurat = NULL,
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(Seurat)

  # Extract data
  if (packageVersion("SeuratObject") >= "5.0.0") {
    spatial_counts <- GetAssayData(spatial_seurat, layer = "counts")
  } else {
    spatial_counts <- GetAssayData(spatial_seurat, slot = "counts")
  }
  if (packageVersion("SeuratObject") >= "5.0.0") {
    reference_counts <- GetAssayData(reference_seurat, layer = "counts")
  } else {
    reference_counts <- GetAssayData(reference_seurat, slot = "counts")
  }

  # Get cell types
  if (!cell_type_column %in% colnames(reference_seurat@meta.data)) {
    stop(sprintf("'%s' not found in reference metadata", cell_type_column))
  }

  cell_types <- setNames(
    reference_seurat@meta.data[[cell_type_column]],
    colnames(reference_seurat)
  )

  # Get marker genes if provided
  marker_genes <- NULL
  if (!is.null(marker_seurat)) {
    marker_genes <- Seurat::FindAllMarkers(
      marker_seurat,
      only.pos = TRUE,
      min.pct = 0.25,
      logfc.threshold = 0.25
    )
  }

  # Run SPOTlight
  results <- run_spotlight(
    spatial_counts = spatial_counts,
    reference_counts = reference_counts,
    cell_types = cell_types,
    marker_genes = marker_genes,
    ...
  )

  return(results)
}


#' Plot SPOTlight Results on Spatial Coordinates
#'
#' @param proportions Proportion matrix from SPOTlight
#' @param spatial_coords DataFrame with x, y coordinates
#' @param cell_type Cell type to visualize
#' @param ... Additional arguments for plot
#'
#' @return ggplot object
#'
#' @export
plot_spotlight_spatial <- function(
    proportions,
    spatial_coords,
    cell_type,
    ...
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  if (!cell_type %in% colnames(proportions)) {
    stop(sprintf("Cell type '%s' not found", cell_type))
  }

  plot_data <- data.frame(
    x = spatial_coords[, 1],
    y = spatial_coords[, 2],
    proportion = proportions[, cell_type]
  )

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y, color = proportion)) +
    ggplot2::geom_point(size = 2, alpha = 0.8) +
    ggplot2::scale_color_viridis_c(name = 'Proportion') +
    ggplot2::labs(
      title = sprintf('SPOTlight: %s', cell_type),
      x = 'X',
      y = 'Y'
    ) +
    ggplot2::theme_minimal() +
    ggplot2::coord_fixed()

  return(p)
}


#' Export SPOTlight Results
#'
#' @param spotlight_results Results from run_spotlight()
#' @param output_dir Output directory
#' @param prefix File prefix
#'
#' @export
export_spotlight_results <- function(
    spotlight_results,
    output_dir,
    prefix = "spotlight"
) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Export proportions
  write.csv(
    spotlight_results$proportions,
    file.path(output_dir, sprintf("%s_proportions.csv", prefix))
  )

  # Save full results
  saveRDS(spotlight_results, file.path(output_dir, sprintf("%s_results.rds", prefix)))

  message(sprintf("Results exported to %s", output_dir))
}
