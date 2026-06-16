#' fastCNV Analysis for Spatial Transcriptomics
#'
#' R wrapper functions for fastCNV CNV analysis on spatial transcriptomics
#' and single-cell data. Based on fastCNV GitHub documentation.
#'
#' @author Yang Guo
#' @date 2026-04-13
#' @version 1.1.0

#' Run fastCNV on Spatial Transcriptomics or Single-Cell Data
#'
#' Main wrapper function for fastCNV analysis. Supports Visium and scRNA-seq data
#' with flexible reference handling. For Visium HD, use run_fastcnv_hd().
#'
#' @param seuratObj Seurat object or list of Seurat objects
#' @param sampleName Character string or vector of sample names
#' @param referenceVar Metadata column name for reference annotations (optional)
#' @param referenceLabel Character string or vector of reference labels (optional)
#' @param assay Assay to use (default: NULL, uses active assay)
#' @param aggregFactor Max counts per meta-spot for aggregation (default: 15000)
#' @param aggregateByVar Whether to aggregate by cluster + cell type (default: TRUE)
#' @param reCluster Whether to recluster if seurat_clusters exists (default: FALSE)
#' @param getCNVPerChromosomeArm Whether to compute per-chromosome-arm CNV (default: TRUE)
#' @param savePath Directory to save PDF heatmaps (default: ".")
#' @param printPlot Whether to print plots to console (default: TRUE)
#' @param denoise Whether to denoise results (default: TRUE)
#' @param outputType Output format: "png" or "pdf" (default: "png")
#' @param verbose Whether to print progress messages (default: TRUE)
#'
#' @return Seurat object or list of Seurat objects with CNV results
#'
#' @examples
#' \dontrun{
#' # Basic usage with reference
#' result <- run_fastcnv(
#'   seuratObj = seurat_obj,
#'   sampleName = "Sample1",
#'   referenceVar = "cell_type",
#'   referenceLabel = "Healthy"
#' )
#'
#' # Multiple samples with pooled reference
#' results <- run_fastcnv(
#'   seuratObj = list(s1, s2, s3),
#'   sampleName = c("S1", "S2", "S3"),
#'   referenceVar = "annot",
#'   referenceLabel = c("Healthy1", "Healthy2")
#' )
#' }
#'
#' @export
run_fastcnv <- function(
    seuratObj,
    sampleName,
    referenceVar = NULL,
    referenceLabel = NULL,
    assay = NULL,
    aggregFactor = 15000,
    aggregateByVar = TRUE,
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

  # Track if input was a single object for return unpacking
  is_single <- inherits(seuratObj, "Seurat")

  if (is_single) {
    # Single Seurat object: sampleName must be a single string
    if (length(sampleName) != 1) {
      stop("For a single Seurat object, sampleName must be a single character string")
    }
    n_samples <- 1
  } else {
    if (length(seuratObj) != length(sampleName)) {
      stop("seuratObj and sampleName must have the same length")
    }
    n_samples <- length(seuratObj)
  }

  if (verbose) {
    message(sprintf("Running fastCNV on %d sample(s)...", n_samples))
  }

  # Run fastCNV
  results <- fastCNV(
    seuratObj = seuratObj,
    sampleName = sampleName,
    referenceVar = referenceVar,
    referenceLabel = referenceLabel,
    assay = assay,
    aggregFactor = aggregFactor,
    aggregateByVar = aggregateByVar,
    reCluster = reCluster,
    getCNVPerChromosomeArm = getCNVPerChromosomeArm,
    savePath = savePath,
    printPlot = printPlot,
    denoise = denoise,
    outputType = outputType
  )

  # Return single object if input was single
  if (is_single && is.list(results) && length(results) == 1) {
    return(results[[1]])
  }

  return(results)
}


#' Run fastCNV on Visium HD Data
#'
#' Wrapper specifically for 10x Visium HD data. Uses fastCNV_10XHD().
#'
#' @param seuratObj Seurat object with Visium HD data (Seurat5)
#' @param sampleName Sample name
#' @param referenceVar Metadata column for reference
#' @param referenceLabel Reference label(s)
#' @param getCNVPerChromosome Whether to compute per-chromosome-arm CNV (default: TRUE)
#' @param savePath Directory to save plots (default: ".")
#' @param printPlot Whether to print plots (default: TRUE)
#' @param ... Additional arguments passed to fastCNV_10XHD()
#'
#' @return Seurat object with CNV results
#'
#' @examples
#' \dontrun{
#' result_hd <- run_fastcnv_hd(
#'   seuratObj = seurat_hd,
#'   sampleName = "HD_Sample",
#'   referenceVar = "annotations",
#'   referenceLabel = "Healthy"
#' )
#' }
#'
#' @export
run_fastcnv_hd <- function(
    seuratObj,
    sampleName,
    referenceVar = NULL,
    referenceLabel = NULL,
    getCNVPerChromosomeArm = TRUE,
    savePath = ".",
    printPlot = TRUE,
    ...
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  message(sprintf("Running fastCNV_10XHD on Visium HD data..."))

  results <- fastCNV::fastCNV_10XHD(
    seuratObjHD = seuratObj,
    sampleName = sampleName,
    referenceVar = referenceVar,
    referenceLabel = referenceLabel,
    getCNVPerChromosomeArm = getCNVPerChromosomeArm,
    savePath = savePath,
    printPlot = printPlot,
    ...
  )

  return(results)
}


#' Run fastCNV on Multiple Samples with Pooled Reference
#'
#' Convenience wrapper for multi-sample CNV analysis. fastCNV pools reference
#' cells/spots across all provided samples automatically when a list of Seurat
#' objects is provided.
#'
#' ## Reference Label Behavior (Critical)
#'
#' `referenceLabel` uses **global exact matching** across ALL samples — it is
#' **not** per-sample isolated:
#' - **Single label** (`referenceLabel = "Healthy"`): searches all samples for
#'   spots annotated as `"Healthy"`, pools them into one reference.
#' - **Multiple labels** (`referenceLabel = c("Normal", "Healthy")`): searches
#'   **all samples** for each label. Each matched label group computes its own
#'   scale factor; the final reference is the **median** across all label groups.
#' - **Minimum threshold**: each sample must have >= 5 spots matching a given
#'   label, or that sample is silently excluded from that label's pool.
#' - **Zero-match fallback**: if no spots match any label across all samples,
#'   fastCNV falls back to reference-free mode with a warning.
#'
#' @param seuratObjs List of Seurat objects. Must use `list()`, NOT `c()`.
#' @param sampleNames Character vector of sample names, same length as seuratObjs.
#' @param referenceVar Metadata column name for reference annotations.
#' @param referenceLabel Character vector of reference label(s). See behavior above.
#' @param ... Additional arguments passed to run_fastcnv().
#'
#' @return Named list of Seurat objects with CNV results.
#'
#' @examples
#' \dontrun{
#' # All samples share the same healthy label
#' results <- run_fastcnv_multi(
#'   seuratObjs = list(s1, s2, s3),
#'   sampleNames = c("S1", "S2", "S3"),
#'   referenceVar = "annot",
#'   referenceLabel = "Healthy"
#' )
#'
#' # Different samples use different healthy labels
#' results <- run_fastcnv_multi(
#'   seuratObjs = list(s1, s2, s3),
#'   sampleNames = c("S1", "S2", "S3"),
#'   referenceVar = "cell_type",
#'   referenceLabel = c("Normal", "Healthy", "Submucosa")
#' )
#' }
#'
#' @export
run_fastcnv_multi <- function(
    seuratObjs,
    sampleNames,
    referenceVar = NULL,
    referenceLabel = NULL,
    ...
) {
  if (!is.list(seuratObjs)) {
    stop("seuratObjs must be a list of Seurat objects. Use list(s1, s2, s3), NOT c(s1, s2, s3).")
  }

  if (length(seuratObjs) != length(sampleNames)) {
    stop(sprintf("seuratObjs (%d) and sampleNames (%d) must have the same length",
                 length(seuratObjs), length(sampleNames)))
  }

  if (!all(sapply(seuratObjs, inherits, "Seurat"))) {
    stop("All elements of seuratObjs must be Seurat objects")
  }

  if (is.null(names(seuratObjs))) {
    names(seuratObjs) <- sampleNames
  }

  if (!is.null(referenceVar) && !is.null(referenceLabel)) {
    message(sprintf("Running fastCNV on %d samples with pooled reference (labels: %s)...",
                    length(seuratObjs), paste(referenceLabel, collapse = ", ")))
  } else {
    message(sprintf("Running fastCNV on %d samples (no reference)...", length(seuratObjs)))
  }

  results <- run_fastcnv(
    seuratObj = seuratObjs,
    sampleName = sampleNames,
    referenceVar = referenceVar,
    referenceLabel = referenceLabel,
    ...
  )

  # Ensure results are named for consistent downstream access
  if (is.list(results) && is.null(names(results))) {
    names(results) <- sampleNames
  }

  return(results)
}


#' Prepare Counts for CNV Analysis
#'
#' Aggregate nearby spots for Visium samples with low read counts.
#' This wraps prepareCountsForCNVAnalysis().
#'
#' @param seuratObj Seurat object
#' @param sampleName Sample name
#' @param referenceVar Metadata column for reference
#' @param aggregFactor Target counts per aggregated spot (default: 15000)
#' @param clusterResolution Seurat clustering resolution (default: 0.8)
#' @param aggregateByVar Whether to aggregate by referenceVar (default: TRUE)
#' @param reCluster Whether to re-cluster (default: FALSE)
#'
#' @return Seurat object with aggregated counts
#'
#' @examples
#' \dontrun{
#' seurat_obj <- prepare_counts_for_cnv(
#'   seuratObj = seurat_obj,
#'   sampleName = "Sample1",
#'   referenceVar = "annotations",
#'   aggregFactor = 15000
#' )
#' }
#'
#' @export
prepare_counts_for_cnv <- function(
    seuratObj,
    sampleName,
    referenceVar = NULL,
    aggregFactor = 15000,
    clusterResolution = 0.8,
    aggregateByVar = TRUE,
    reCluster = FALSE
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  message("Preparing counts for CNV analysis...")

  result <- fastCNV::prepareCountsForCNVAnalysis(
    seuratObj = seuratObj,
    sampleName = sampleName,
    referenceVar = referenceVar,
    aggregateByVar = aggregateByVar,
    aggregFactor = aggregFactor,
    clusterResolution = clusterResolution,
    reCluster = reCluster
  )

  message("Done preparing counts!")
  return(result)
}


#' Map 8um Annotations to 16um for Visium HD
#'
#' When annotations are on 8um resolution but fastCNV defaults to 16um assay,
#' use this function to project annotations.
#'
#' @param seuratObj Seurat object with Visium HD data
#' @param referenceVar Metadata column containing 8um annotations
#'
#' @return Seurat object with projected annotation column
#'
#' @examples
#' \dontrun{
#' seurat_hd <- annotations_8um_to_16um(seurat_hd, referenceVar = "annots_8um")
#' }
#'
#' @export
annotations_8um_to_16um <- function(seuratObj, referenceVar) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::annotations8umTo16um(
    seuratObj = seuratObj,
    referenceVar = referenceVar
  )

  message(sprintf("New annotation column is named: projected_%s", referenceVar))
  return(result)
}


#' Perform CNV Clustering
#'
#' Run hierarchical clustering on CNV profiles to identify subclones.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param referenceVar Metadata column for reference annotations (optional)
#' @param cellTypesToCluster Cell types to include in clustering (optional)
#' @param k_clusters Number of clusters (NULL for auto)
#' @param h_clusters Height for dendrogram cut (NULL for auto)
#'
#' @return Seurat object with cnv_clusters in metadata
#'
#' @examples
#' \dontrun{
#' seurat_obj <- cnv_cluster(seurat_obj)
#' seurat_obj <- cnv_cluster(seurat_obj, referenceVar = "annot", cellTypesToCluster = "Tumor")
#' }
#'
#' @export
cnv_cluster <- function(
    seuratObj,
    referenceVar = NULL,
    cellTypesToCluster = NULL,
    k_clusters = NULL,
    h_clusters = NULL
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::CNVCluster(
    seuratObj = seuratObj,
    referenceVar = referenceVar,
    cellTypesToCluster = cellTypesToCluster,
    k = k_clusters,
    h = h_clusters
  )

  return(result)
}


#' Merge Correlated CNV Clusters
#'
#' Merge highly correlated CNV clusters to reduce redundancy.
#'
#' @param seuratObj Seurat object with CNV clusters
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
merge_cnv_clusters <- function(seuratObj, mergeThreshold = 0.95) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::mergeCNVClusters(
    seuratObj = seuratObj,
    mergeThreshold = mergeThreshold
  )

  return(result)
}


#' Classify CNVs as Gain / Loss / No Alteration
#'
#' Adds per-chromosome-arm classification columns to metadata.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param cnv_thresh Threshold for calling gain/loss (default: 0.09)
#'
#' @return Seurat object with classification columns
#'
#' @examples
#' \dontrun{
#' seurat_obj <- cnv_classification(seurat_obj, cnv_thresh = 0.09)
#' }
#'
#' @export
cnv_classification <- function(seuratObj, cnv_thresh = 0.09) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::CNVClassification(
    seuratObj = seuratObj,
    peaks = c(-cnv_thresh, 0, cnv_thresh)
  )

  return(result)
}


#' Build CNV Subclonality Tree
#'
#' Generate a phylogenetic tree based on CNV profiles.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param values Type of values: "calls" or "fractions" (default: "calls")
#' @param cnv_thresh Threshold for CNV calling (default: 0.09)
#' @param healthyClusters Cluster ID(s) representing healthy tissue (optional)
#'
#' @return Tree data object
#'
#' @examples
#' \dontrun{
#' tree_data <- cnv_tree(seurat_obj, values = "calls", cnv_thresh = 0.09, healthyClusters = "1")
#' }
#'
#' @export
cnv_tree <- function(
    seuratObj,
    values = "calls",
    cnv_thresh = 0.09,
    healthyClusters = NULL
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  result <- fastCNV::CNVTree(
    seuratObj = seuratObj,
    values = values,
    cnv_thresh = cnv_thresh,
    healthyClusters = healthyClusters
  )

  return(result)
}


#' Plot fastCNV Heatmap
#'
#' Generate CNV heatmap from fastCNV results.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param referenceVar Metadata column for reference annotations
#' @param clustersVar Metadata column for CNV clusters (default: "cnv_clusters")
#' @param splitPlotOnVar Variable to split plot on
#' @param denoise Whether to use denoised data (default: TRUE)
#' @param savePath Output directory (default: ".")
#' @param outputFile Output filename (optional)
#' @param printPlot Whether to print to console (default: FALSE)
#' @param referencePalette Color palette for reference
#' @param clusters_palette Color palette for clusters
#' @param raster_resize_mat Whether to rasterize (default: TRUE)
#' @param ... Additional arguments
#'
#' @return None (saves plot to file)
#'
#' @examples
#' \dontrun{
#' plot_fastcnv_heatmap(
#'   seuratObj = result,
#'   referenceVar = "cell_type",
#'   savePath = "./heatmaps",
#'   outputFile = "cnv_heatmap.pdf"
#' )
#' }
#'
#' @export
plot_fastcnv_heatmap <- function(
    seuratObj,
    referenceVar = NULL,
    clustersVar = "cnv_clusters",
    splitPlotOnVar = clustersVar,
    denoise = TRUE,
    savePath = ".",
    outputFile = NULL,
    printPlot = FALSE,
    referencePalette = "default",
    clusters_palette = "default",
    raster_resize_mat = TRUE,
    ...
) {
  if (!requireNamespace("fastCNV", quietly = TRUE)) {
    stop("fastCNV package required")
  }

  # Determine output type from filename if provided
  outputType <- "png"
  if (!is.null(outputFile)) {
    if (grepl("\\.pdf$", outputFile, ignore.case = TRUE)) {
      outputType <- "pdf"
    } else if (grepl("\\.png$", outputFile, ignore.case = TRUE)) {
      outputType <- "png"
    }
  }

  if (!dir.exists(savePath)) {
    dir.create(savePath, recursive = TRUE)
  }

  message("Generating CNV heatmap...")

  tryCatch({
    fastCNV::plotCNVResults(
      seuratObj = seuratObj,
      referenceVar = referenceVar,
      clustersVar = clustersVar,
      splitPlotOnVar = splitPlotOnVar,
      savePath = savePath,
      printPlot = printPlot,
      referencePalette = referencePalette,
      clusters_palette = clusters_palette,
      outputType = outputType,
      denoise = denoise,
      raster_resize_mat = raster_resize_mat,
      ...
    )
  }, error = function(e) {
    message("Rasterization failed, trying without...")
    fastCNV::plotCNVResults(
      seuratObj = seuratObj,
      referenceVar = referenceVar,
      clustersVar = clustersVar,
      splitPlotOnVar = splitPlotOnVar,
      savePath = savePath,
      printPlot = printPlot,
      referencePalette = referencePalette,
      clusters_palette = clusters_palette,
      outputType = outputType,
      denoise = denoise,
      raster_resize_mat = FALSE,
      ...
    )
  })

  message(sprintf("Heatmap saved to: %s", savePath))
}


#' Plot CNV Fraction Spatially
#'
#' Visualize CNV fraction on spatial coordinates.
#'
#' @param seuratObj Seurat object with fastCNV results and spatial coordinates
#' @param features Features to plot (default: "cnv_fraction")
#' @param group.by Grouping variable for clustering visualization
#' @param pt.size.factor Point size factor (default: 1.5)
#' @param ... Additional arguments passed to SpatialFeaturePlot/SpatialDimPlot
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' plot_cnv_fraction_spatial(result)
#' plot_cnv_fraction_spatial(result, group.by = "cnv_clusters")
#' }
#'
#' @export
plot_cnv_fraction_spatial <- function(
    seuratObj,
    features = "cnv_fraction",
    group.by = NULL,
    pt.size.factor = 1.5,
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(Seurat)

  if (length(Seurat::Images(seuratObj)) == 0) {
    stop("No spatial coordinates found in Seurat object")
  }

  if (!is.null(group.by)) {
    p <- SpatialDimPlot(
      seuratObj,
      group.by = group.by,
      pt.size.factor = pt.size.factor,
      ...
    )
  } else {
    if (!features %in% colnames(seuratObj@meta.data)) {
      stop(sprintf("'%s' not found in metadata. Run fastCNV first.", features))
    }
    p <- SpatialFeaturePlot(
      seuratObj,
      features = features,
      pt.size.factor = pt.size.factor,
      ...
    )
  }

  return(p)
}


#' Plot CNV per Chromosome Arm Spatially
#'
#' Visualize specific chromosome arm CNV on tissue with a diverging color scale.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param feature Chromosome arm feature name (e.g., "11.q_CNV")
#' @param pt.size.factor Point size factor (default: 1.5)
#' @param limits Color scale limits (default: c(-1, 1))
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' plot_chr_arm_spatial(result, feature = "11.q_CNV")
#' plot_chr_arm_spatial(result, feature = "8.q_CNV", limits = c(-0.5, 0.5))
#' }
#'
#' @export
plot_chr_arm_spatial <- function(
    seuratObj,
    feature,
    pt.size.factor = 1.5,
    limits = c(-1, 1)
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(Seurat)

  if (!feature %in% colnames(seuratObj@meta.data)) {
    stop(sprintf("'%s' not found in metadata.", feature))
  }

  p <- SpatialFeaturePlot(seuratObj, features = feature, pt.size.factor = pt.size.factor) +
    scale_fill_gradient2(
      low = "#2166AC",
      mid = "white",
      high = "#B2182B",
      midpoint = 0,
      limits = limits
    )

  return(p)
}


#' Extract CNV Results
#'
#' Extract CNV results from Seurat object into a data frame.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param include_chromosomes Whether to include per-chromosome CNV (default: TRUE)
#'
#' @return Data frame with CNV results
#'
#' @examples
#' \dontrun{
#' cnv_data <- extract_cnv_results(result)
#' head(cnv_data)
#' }
#'
#' @export
extract_cnv_results <- function(
    seuratObj,
    include_chromosomes = TRUE
) {
  cnv_cols <- c("cnv_fraction", "cnv_clusters")

  if (include_chromosomes) {
    # Match fastCNV chromosome-arm columns: e.g., "1.p_CNV", "11.q_CNV", "X.p_CNV"
    # Avoid matching user-defined columns ending in _CNV
    chr_cols <- grep("^[0-9XY]+\\.[pq]_CNV$", colnames(seuratObj@meta.data), value = TRUE)
    cnv_cols <- c(cnv_cols, chr_cols)
  }

  available_cols <- cnv_cols[cnv_cols %in% colnames(seuratObj@meta.data)]

  if (length(available_cols) == 0) {
    warning("No CNV results found in metadata. Run fastCNV first.")
    return(data.frame(cell = colnames(seuratObj)))
  }

  results <- seuratObj@meta.data[, available_cols, drop = FALSE]
  results$cell <- rownames(results)
  results <- results[, c("cell", available_cols)]

  return(results)
}


#' Summarize CNV by Group
#'
#' Summarize CNV results by a grouping variable.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param group.by Grouping variable (default: "cnv_clusters")
#' @param metric Metric to summarize (default: "cnv_fraction")
#'
#' @return Data frame with summary statistics
#'
#' @examples
#' \dontrun{
#' summary <- summarize_cnv_by_group(result, group.by = "cell_type")
#' print(summary)
#' }
#'
#' @export
summarize_cnv_by_group <- function(
    seuratObj,
    group.by = "cnv_clusters",
    metric = "cnv_fraction"
) {
  if (!group.by %in% colnames(seuratObj@meta.data)) {
    stop(sprintf("'%s' not found in metadata", group.by))
  }

  if (!metric %in% colnames(seuratObj@meta.data)) {
    stop(sprintf("'%s' not found in metadata", metric))
  }

  cnv_data <- seuratObj@meta.data[, c(group.by, metric)]
  colnames(cnv_data) <- c("group", "metric")

  summary <- aggregate(
    metric ~ group,
    data = cnv_data,
    FUN = function(x) c(
      mean = mean(x, na.rm = TRUE),
      median = median(x, na.rm = TRUE),
      sd = sd(x, na.rm = TRUE),
      min = min(x, na.rm = TRUE),
      max = max(x, na.rm = TRUE),
      n = sum(!is.na(x))
    )
  )

  summary_df <- data.frame(
    group = summary$group,
    mean = summary$metric[, "mean"],
    median = summary$metric[, "median"],
    sd = summary$metric[, "sd"],
    min = summary$metric[, "min"],
    max = summary$metric[, "max"],
    n = summary$metric[, "n"]
  )

  return(summary_df)
}


#' Export CNV Results
#'
#' Export fastCNV results to files.
#'
#' @param seuratObj Seurat object with fastCNV results
#' @param output_dir Output directory (default: "fastcnv_results")
#' @param prefix File prefix (default: "fastcnv")
#' @param export_matrix Whether to export CNV matrix (default: TRUE)
#'
#' @return None (saves files to directory)
#'
#' @examples
#' \dontrun{
#' export_cnv_results(result, output_dir = "./results", prefix = "sample1")
#' }
#'
#' @export
export_cnv_results <- function(
    seuratObj,
    output_dir = "fastcnv_results",
    prefix = "fastcnv",
    export_matrix = TRUE
) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  cnv_results <- extract_cnv_results(seuratObj)

  meta_file <- file.path(output_dir, sprintf("%s_metadata.csv", prefix))
  write.csv(cnv_results, meta_file, row.names = FALSE)
  message(sprintf("Saved metadata to: %s", meta_file))

  if (export_matrix && "CNV" %in% names(seuratObj@assays)) {
    if (packageVersion("SeuratObject") >= "5.0.0") {
      cnv_matrix <- Seurat::LayerData(seuratObj, assay = "CNV", layer = "data")
    } else {
      cnv_matrix <- Seurat::GetAssayData(seuratObj, assay = "CNV", slot = "data")
    }
    matrix_file <- file.path(output_dir, sprintf("%s_matrix.csv", prefix))
    # CNV matrix may be sparse (dgCMatrix); convert to dense first
    write.csv(as.data.frame(as.matrix(cnv_matrix)), matrix_file)
    message(sprintf("Saved CNV matrix to: %s", matrix_file))
  }

  rds_file <- file.path(output_dir, sprintf("%s_seurat.rds", prefix))
  saveRDS(seuratObj, rds_file)
  message(sprintf("Saved Seurat object to: %s", rds_file))

  message("Export complete!")
}
