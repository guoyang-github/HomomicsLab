#' fastCNV Analysis for Single-Cell Data
#'
#' R wrapper functions for fastCNV CNV analysis on single-cell RNA-seq data.
#' Based on fastCNV scRNA-seq vignette: https://must-bioinfo.github.io/fastCNV/articles/fastCNV_sc.html
#'
#' @author Yang Guo
#' @date 2026-04-13
#' @version 1.2.0

#' Run fastCNV on Single-Cell Data
#'
#' Main wrapper function for fastCNV analysis on scRNA-seq data.
#' fastCNV internally runs: prepareCountsForCNVAnalysis, CNVAnalysis,
#' CNVPerChromosome, CNVCluster, and plotCNVResults.
#'
#' @param seurat_obj Seurat object or list of Seurat objects
#' @param sample_name Sample name (character) or vector of sample names
#' @param reference_var Metadata column for reference annotations (optional)
#' @param reference_label Character string or vector of reference labels (optional)
#' @param assay Assay to use (default: NULL, uses active assay)
#' @param reCluster Whether to recluster if seurat_clusters exists (default: FALSE)
#' @param getCNVPerChromosomeArm Whether to compute per-chromosome-arm CNV (default: TRUE)
#' @param savePath Directory to save PDF heatmaps (default: ".")
#' @param printPlot Whether to print plots to console (default: TRUE)
#' @param denoise Whether to denoise results (default: TRUE)
#' @param outputType Output format: "png" or "pdf" (default: "png")
#' @param verbose Whether to print progress (default: TRUE)
#'
#' @return Seurat object or list of Seurat objects with CNV results
#'
#' @examples
#' \dontrun{
#' # With reference on single sample
#' result <- run_fastcnv_sc(
#'   seurat_obj = seurat_obj,
#'   sample_name = "Tumor1",
#'   reference_var = "annot",
#'   reference_label = c("TNKILC", "Myeloid", "B", "Mast", "Plasma")
#' )
#'
#' # Without reference
#' result <- run_fastcnv_sc(
#'   seurat_obj = seurat_obj,
#'   sample_name = "Tumor1"
#' )
#' }
#'
#' @export
run_fastcnv_sc <- function(
    seurat_obj,
    sample_name,
    reference_var = NULL,
    reference_label = NULL,
    assay = NULL,
    reCluster = FALSE,
    getCNVPerChromosomeArm = TRUE,
    savePath = ".",
    printPlot = TRUE,
    denoise = TRUE,
    outputType = "png",
    verbose = TRUE
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required. Install with: remotes::install_github('must-bioinfo/fastCNV')")
  }

  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(fastCNV)
  library(Seurat)

  is_single <- inherits(seurat_obj, "Seurat")

  if (verbose) {
    if (is_single) {
      message(sprintf("Running fastCNV on sample: %s (%d cells, %d genes)",
                      sample_name, ncol(seurat_obj), nrow(seurat_obj)))
    } else {
      message(sprintf("Running fastCNV on %d samples...", length(seurat_obj)))
    }
    if (!is.null(reference_var)) {
      message(sprintf("  Reference: %s = %s", reference_var,
                      paste(reference_label, collapse = ", ")))
    }
  }

  # Run fastCNV
  result <- fastCNV(
    seuratObj = seurat_obj,
    sampleName = sample_name,
    referenceVar = reference_var,
    referenceLabel = reference_label,
    assay = assay,
    reCluster = reCluster,
    getCNVPerChromosomeArm = getCNVPerChromosomeArm,
    savePath = savePath,
    printPlot = printPlot,
    denoise = denoise,
    outputType = outputType
  )

  # fastCNV may return a list for single object; extract it
  if (is_single && is.list(result) && length(result) == 1) {
    result <- result[[1]]
  }

  if (verbose) {
    message("fastCNV analysis complete!")
    if (is_single && "cnv_clusters" %in% colnames(result@meta.data)) {
      n_clusters <- length(unique(result@meta.data$cnv_clusters))
      message(sprintf("  CNV clusters identified: %d", n_clusters))
    }
  }

  return(result)
}


#' Run fastCNV on Multiple Single-Cell Samples
#'
#' Analyze multiple samples with pooled reference. When a named list is passed,
#' fastCNV automatically pools reference cells across all samples.
#'
#' @param seurat_list List of Seurat objects
#' @param sample_names Character vector of sample names
#' @param reference_var Metadata column for reference
#' @param reference_label Reference label(s)
#' @param ... Additional arguments passed to run_fastcnv_sc()
#'
#' @return Named list of Seurat objects with CNV results
#'
#' @examples
#' \dontrun{
#' results <- run_fastcnv_multi_sc(
#'   seurat_list = list(s1, s2, s3),
#'   sample_names = c("S1", "S2", "S3"),
#'   reference_var = "annot",
#'   reference_label = c("Plasma", "TNKILC", "Myeloid", "B", "Mast")
#' )
#' }
#'
#' @export
run_fastcnv_multi_sc <- function(
    seurat_list,
    sample_names,
    reference_var = NULL,
    reference_label = NULL,
    ...
) {
  if (!is.list(seurat_list)) {
    stop("seurat_list must be a list of Seurat objects")
  }

  if (length(seurat_list) != length(sample_names)) {
    stop("seurat_list and sample_names must have the same length")
  }

  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  message(sprintf("Running fastCNV on %d samples with pooled reference...", length(seurat_list)))

  # Name the list
  names(seurat_list) <- sample_names

  # Run fastCNV
  results <- fastCNV(
    seuratObj = seurat_list,
    sampleName = sample_names,
    referenceVar = reference_var,
    referenceLabel = reference_label,
    ...
  )

  # Ensure results are named
  if (is.null(names(results))) {
    names(results) <- sample_names
  }

  message("Multi-sample analysis complete!")
  return(results)
}


#' CNV Cluster
#'
#' Perform hierarchical clustering on CNV profiles to identify subclones.
#'
#' @param seurat_obj Seurat object with fastCNV results
#' @param reference_var Metadata column for reference annotations (optional)
#' @param cellTypesToCluster Cell types to include in clustering (optional)
#' @param k Number of clusters (NULL for auto)
#' @param h Height for dendrogram cut (NULL for auto)
#'
#' @return Seurat object with cnv_clusters in metadata
#'
#' @examples
#' \dontrun{
#' seurat_obj <- cnv_cluster(seurat_obj)
#' seurat_obj <- cnv_cluster(seurat_obj, reference_var = "annot", cellTypesToCluster = "Tumor")
#' }
#'
#' @export
cnv_cluster <- function(
    seurat_obj,
    reference_var = NULL,
    cellTypesToCluster = NULL,
    k = NULL,
    h = NULL
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::CNVCluster(
    seuratObj = seurat_obj,
    referenceVar = reference_var,
    cellTypesToCluster = cellTypesToCluster,
    k = k,
    h = h
  )

  return(result)
}


#' Merge Correlated CNV Clusters
#'
#' Merge highly correlated CNV clusters to reduce redundancy.
#'
#' @param seurat_obj Seurat object with CNV clusters
#' @param mergeThreshold Correlation threshold for merging (default: 0.95)
#'
#' @return Seurat object with merged clusters
#'
#' @examples
#' \dontrun{
#' seurat_obj <- merge_cnv_clusters(seurat_obj, mergeThreshold = 0.95)
#' }
#'
#' @export
merge_cnv_clusters <- function(seurat_obj, mergeThreshold = 0.95) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::mergeCNVClusters(
    seuratObj = seurat_obj,
    mergeThreshold = mergeThreshold
  )

  return(result)
}


#' Classify CNVs as Gain / Loss / No Alteration
#'
#' Adds per-chromosome-arm classification columns to metadata.
#'
#' @param seurat_obj Seurat object with fastCNV results
#' @param cnv_thresh Threshold for calling gain/loss. Internally converted to
#'   peaks = c(-cnv_thresh, 0, cnv_thresh) for fastCNV::CNVClassification.
#'   Default 0.1 matches fastCNV's default peaks = c(-0.1, 0, 0.1).
#'
#' @return Seurat object with classification columns
#'
#' @examples
#' \dontrun{
#' seurat_obj <- cnv_classification(seurat_obj, cnv_thresh = 0.1)
#' }
#'
#' @export
cnv_classification <- function(seurat_obj, cnv_thresh = 0.1) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  peaks <- c(-cnv_thresh, 0, cnv_thresh)

  result <- fastCNV::CNVClassification(
    seuratObj = seurat_obj,
    peaks = peaks
  )

  return(result)
}


#' Build CNV Subclonality Tree
#'
#' Generate a phylogenetic tree based on CNV profiles.
#'
#' @param seurat_obj Seurat object with fastCNV results
#' @param values Type of values: "scores" (default) or "fractions"
#' @param cnv_thresh Threshold for CNV calling (default: 0.15)
#' @param healthyClusters Cluster ID(s) representing healthy tissue (optional)
#'
#' @return Tree data object
#'
#' @examples
#' \dontrun{
#' tree_data <- cnv_tree(seurat_obj, values = "scores", cnv_thresh = 0.15, healthyClusters = "1")
#' }
#'
#' @export
cnv_tree <- function(
    seurat_obj,
    values = "scores",
    cnv_thresh = 0.15,
    healthyClusters = NULL
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::CNVTree(
    seuratObj = seurat_obj,
    values = values,
    cnv_thresh = cnv_thresh,
    healthyClusters = healthyClusters
  )

  return(result)
}


#' Extract CNV Metadata
#'
#' Extract CNV results from Seurat object metadata.
#'
#' @param seurat_obj Seurat object with fastCNV results
#' @param include_chromosomes Whether to include per-chromosome CNV (default: TRUE)
#'
#' @return Data frame with CNV metadata
#'
#' @examples
#' \dontrun{
#' cnv_data <- extract_cnv_metadata(result)
#' head(cnv_data)
#' }
#'
#' @export
extract_cnv_metadata <- function(
    seurat_obj,
    include_chromosomes = TRUE
) {
  # Core CNV columns
  core_cols <- c("cnv_fraction", "cnv_clusters")

  # Add per-chromosome columns if requested
  # fastCNV names them like "20.p_CNV", "X.q_CNV"
  if (include_chromosomes) {
    # Use strict pattern to match chromosome.arm_CNV format only
    chr_cols <- grep("^[0-9XY]+\\.[pq]_CNV$", colnames(seurat_obj@meta.data), value = TRUE)
    all_cols <- c(core_cols, chr_cols)
  } else {
    all_cols <- core_cols
  }

  # Find available columns
  available <- all_cols[all_cols %in% colnames(seurat_obj@meta.data)]

  if (length(available) == 0) {
    warning("No CNV metadata found. Run fastCNV first.")
    return(data.frame(cell = colnames(seurat_obj)))
  }

  # Extract metadata
  cnv_data <- seurat_obj@meta.data[, available, drop = FALSE]
  cnv_data$cell <- rownames(cnv_data)

  # Reorder columns
  cnv_data <- cnv_data[, c("cell", available)]

  return(cnv_data)
}


#' Plot CNV Heatmap
#'
#' Generate CNV heatmap from fastCNV results.
#'
#' @param seurat_obj Seurat object with fastCNV results
#' @param reference_var Metadata column for reference annotations (optional)
#' @param clusters_var Metadata column for CNV clusters (default: "cnv_clusters")
#' @param denoise Whether to use denoised data (default: TRUE)
#' @param output_file Output file path (optional). Only used to infer `outputType`
#'   (`pdf` or `png`) and `save_path` (directory). The actual filename is controlled
#'   by fastCNV, not this parameter.
#' @param save_path Output directory (default: ".")
#' @param print_plot Whether to print to console (default: FALSE)
#' @param ... Additional arguments
#'
#' @return None (saves plot to file)
#'
#' @examples
#' \dontrun{
#' plot_cnv_heatmap(result, output_file = "cnv_heatmap.pdf")
#' }
#'
#' @export
plot_cnv_heatmap <- function(
    seurat_obj,
    reference_var = NULL,
    clusters_var = "cnv_clusters",
    denoise = TRUE,
    output_file = NULL,
    save_path = ".",
    print_plot = FALSE,
    ...
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  # Determine output type
  output_type <- "png"
  if (!is.null(output_file)) {
    if (grepl("\\.pdf$", output_file, ignore.case = TRUE)) {
      output_type <- "pdf"
      save_path <- dirname(output_file)
    } else if (grepl("\\.png$", output_file, ignore.case = TRUE)) {
      output_type <- "png"
      save_path <- dirname(output_file)
    }
  }

  # Create directory if needed
  if (!dir.exists(save_path)) {
    dir.create(save_path, recursive = TRUE)
  }

  message("Generating CNV heatmap...")

  # Call fastCNV plot function with error handling
  tryCatch({
    fastCNV::plotCNVResults(
      seuratObj = seurat_obj,
      referenceVar = reference_var,
      clustersVar = clusters_var,
      splitPlotOnVar = clusters_var,
      savePath = save_path,
      printPlot = print_plot,
      outputType = output_type,
      denoise = denoise,
      raster_resize_mat = TRUE,
      ...
    )
  }, error = function(e) {
    message("Rasterization failed, trying without...")
    fastCNV::plotCNVResults(
      seuratObj = seurat_obj,
      referenceVar = reference_var,
      clustersVar = clusters_var,
      splitPlotOnVar = clusters_var,
      savePath = save_path,
      printPlot = print_plot,
      outputType = output_type,
      denoise = denoise,
      raster_resize_mat = FALSE,
      ...
    )
  })

  message(sprintf("Heatmap saved to: %s", save_path))
}


#' Plot CNV per Chromosome Arm on UMAP
#'
#' Visualize specific chromosome arm CNV on UMAP with a diverging color scale.
#'
#' @param seurat_obj Seurat object with fastCNV results and UMAP reduction
#' @param feature Chromosome arm feature name (e.g., "20.p_CNV")
#' @param reduction Dimensionality reduction to use (default: "umap")
#' @param limits Color scale limits (default: c(-1, 1))
#' @param common_theme Optional ggplot theme
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' plot_chr_arm_umap(result, feature = "20.p_CNV")
#' plot_chr_arm_umap(result, feature = "X.q_CNV", limits = c(-0.5, 0.5))
#' }
#'
#' @export
plot_chr_arm_umap <- function(
    seurat_obj,
    feature,
    reduction = "umap",
    limits = c(-1, 1),
    common_theme = NULL
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("scales", quietly = TRUE)) {
    stop("scales package required")
  }

  library(Seurat)
  library(scales)

  if (!feature %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("'%s' not found in metadata.", feature))
  }

  # Check reduction exists
  if (!reduction %in% names(seurat_obj@reductions)) {
    available <- paste(names(seurat_obj@reductions), collapse = ", ")
    stop(sprintf("Reduction '%s' not found. Available: %s", reduction, available))
  }

  if (is.null(common_theme)) {
    common_theme <- ggplot2::theme(
      plot.title = ggplot2::element_text(size = 10),
      legend.text = ggplot2::element_text(size = 8),
      legend.title = ggplot2::element_text(size = 8),
      axis.title = ggplot2::element_text(size = 8),
      axis.text = ggplot2::element_text(size = 6)
    )
  }

  p <- FeaturePlot(seurat_obj, features = feature, reduction = reduction) +
    scale_color_distiller(
      palette = "RdBu",
      direction = -1,
      limits = limits,
      rescaler = function(x, to = c(0, 1), from = NULL) {
        rescale_mid(x, to = to, mid = 0)
      }
    ) +
    common_theme

  return(p)
}


#' Summarize CNV by Cluster
#'
#' Summarize CNV metrics by grouping variable.
#'
#' @param seurat_obj Seurat object with fastCNV results
#' @param group_by Grouping variable (default: "cnv_clusters")
#' @param metric Metric to summarize (default: "cnv_fraction")
#'
#' @return Data frame with summary statistics
#'
#' @examples
#' \dontrun{
#' # By CNV cluster
#' summarize_cnv_by_cluster(result, group_by = "cnv_clusters")
#'
#' # By cell type
#' summarize_cnv_by_cluster(result, group_by = "cell_type")
#' }
#'
#' @export
summarize_cnv_by_cluster <- function(
    seurat_obj,
    group_by = "cnv_clusters",
    metric = "cnv_fraction"
) {
  if (!group_by %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("'%s' not found in metadata", group_by))
  }

  if (!metric %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("'%s' not found in metadata", metric))
  }

  # Get data
  data <- data.frame(
    group = seurat_obj@meta.data[[group_by]],
    value = seurat_obj@meta.data[[metric]]
  )

  # Remove NA groups
  data <- data[!is.na(data$group), , drop = FALSE]

  if (nrow(data) == 0) {
    stop("No non-NA data available for summarization")
  }

  # Summarize
  summary <- aggregate(
    value ~ group,
    data = data,
    FUN = function(x) c(
      mean = mean(x, na.rm = TRUE),
      median = median(x, na.rm = TRUE),
      sd = sd(x, na.rm = TRUE),
      min = min(x, na.rm = TRUE),
      max = max(x, na.rm = TRUE),
      n = sum(!is.na(x))
    )
  )

  # Flatten
  result <- data.frame(
    group = summary$group,
    mean = summary$value[, "mean"],
    median = summary$value[, "median"],
    sd = summary$value[, "sd"],
    min = summary$value[, "min"],
    max = summary$value[, "max"],
    n = as.integer(summary$value[, "n"])
  )

  # Sort by mean CNV
  result <- result[order(-result$mean), ]

  return(result)
}


#' Export CNV Results
#'
#' Export fastCNV results to CSV and RDS files.
#'
#' @param seurat_obj Seurat object with fastCNV results
#' @param output_dir Output directory (default: "fastcnv_results")
#' @param prefix File prefix (default: "fastcnv")
#' @param export_matrix Whether to export CNV matrix (default: FALSE)
#'
#' @return None (saves files)
#'
#' @examples
#' \dontrun{
#' export_cnv_results(result, output_dir = "./results", prefix = "sample1")
#' }
#'
#' @export
export_cnv_results <- function(
    seurat_obj,
    output_dir = "fastcnv_results",
    prefix = "fastcnv",
    export_matrix = FALSE
) {
  # Create directory
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Extract and save metadata
  cnv_data <- extract_cnv_metadata(seurat_obj, include_chromosomes = TRUE)
  meta_file <- file.path(output_dir, sprintf("%s_metadata.csv", prefix))
  write.csv(cnv_data, meta_file, row.names = FALSE)
  message(sprintf("Saved: %s", meta_file))

  # Save CNV matrix if available and requested
  # Use Seurat v5-compatible assay access
  cnv_assay <- NULL
  if ("CNV" %in% names(seurat_obj@assays)) {
    cnv_assay <- seurat_obj[["CNV"]]
  }

  if (export_matrix && !is.null(cnv_assay)) {
    layer_data <- SeuratObject::LayerData(cnv_assay)
    # LayerData may return a sparse matrix (dgCMatrix); convert to dense first
    if (inherits(layer_data, "Matrix")) {
      layer_data <- as.matrix(layer_data)
    }
    cnv_matrix <- as.data.frame(layer_data)
    matrix_file <- file.path(output_dir, sprintf("%s_matrix.csv", prefix))
    write.csv(cnv_matrix, matrix_file)
    message(sprintf("Saved: %s", matrix_file))
  }

  # Save Seurat object
  rds_file <- file.path(output_dir, sprintf("%s_seurat.rds", prefix))
  saveRDS(seurat_obj, rds_file)
  message(sprintf("Saved: %s", rds_file))

  message("Export complete!")
}
