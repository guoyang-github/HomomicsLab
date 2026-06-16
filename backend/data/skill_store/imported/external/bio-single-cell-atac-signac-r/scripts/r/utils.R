# Signac Utility Functions
# ========================
#
# Helper and utility functions for Signac analysis

#' Install Signac and dependencies
#'
#' Install Signac and required Bioconductor packages
#'
#' @param install_suggests Also install suggested packages (default: FALSE)
#' @export
install_signac_deps <- function(install_suggests = FALSE) {
  if (!requireNamespace("BiocManager", quietly = TRUE)) {
    install.packages("BiocManager")
  }

  # Core dependencies
  core_packages <- c(
    "Signac", "Seurat", "GenomeInfoDb", "BiocGenerics",
    "S4Vectors", "IRanges", "GenomicRanges", "AnnotationHub"
  )

  message("Installing core Signac dependencies...")
  BiocManager::install(core_packages, ask = FALSE)

  if (install_suggests) {
    suggests <- c(
      "EnsDb.Hsapiens.v86", "BSgenome.Hsapiens.UCSC.hg38",
      "chromVAR", "TFBSTools", "JASPAR2020",
      "ggbio", "Gviz"
    )
    message("Installing suggested packages...")
    BiocManager::install(suggests, ask = FALSE)
  }

  message("Installation complete!")
}

#' Get Signac version information
#'
#' Get version info for Signac and dependencies
#'
#' @return Data frame with version information
#' @export
get_signac_version_info <- function() {
  packages <- c("Signac", "Seurat", "GenomeInfoDb", "BiocGenerics",
                "S4Vectors", "IRanges", "GenomicRanges")

  versions <- sapply(packages, function(pkg) {
    if (requireNamespace(pkg, quietly = TRUE)) {
      as.character(utils::packageVersion(pkg))
    } else {
      "NOT INSTALLED"
    }
  })

  data.frame(
    package = packages,
    version = versions,
    stringsAsFactors = FALSE
  )
}

#' Get available genomes
#'
#' List available genome annotations
#'
#' @return Character vector of available genomes
#' @export
get_available_genomes <- function() {
  c("hg38", "hg19", "mm10", "mm9")
}

#' Get blacklist regions
#'
#' Get blacklist regions for a genome
#'
#' @param genome Genome assembly: "hg38", "hg19", "mm10" (default: "hg38")
#' @return GRanges object with blacklist regions
#' @export
get_blacklist_regions <- function(genome = "hg38") {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  # Try to get from Signac (Signac v1/v2 provide blacklist as direct data objects)
  blacklist_obj_name <- paste0("blacklist_", genome)
  tryCatch({
    blacklist <- get(blacklist_obj_name, envir = asNamespace("Signac"))
    return(blacklist)
  }, error = function(e) {
    message(sprintf("Blacklist for %s not found in Signac", genome))
    return(NULL)
  })
}

#' Get gene annotation
#'
#' Get gene annotation for a genome
#'
#' @param genome Genome assembly: "hg38", "hg19", "mm10" (default: "hg38")
#' @param version Ensembl version (default: 86 for hg38)
#' @return GRanges object with gene annotation
#' @export
get_gene_annotation <- function(genome = "hg38", version = NULL) {
  if (!requireNamespace("AnnotationHub", quietly = TRUE)) {
    stop("AnnotationHub package required")
  }

  if (is.null(version)) {
    version <- switch(genome,
                      "hg38" = 86,
                      "hg19" = 75,
                      "mm10" = 79,
                      86)
  }

  # Try to load from installed packages
  pkg_name <- sprintf("EnsDb.%s.v%d",
                      switch(genome, "hg38" = "Hsapiens", "hg19" = "Hsapiens",
                             "mm10" = "Mmusculus", "Hsapiens"),
                      version)

  if (requireNamespace(pkg_name, quietly = TRUE)) {
    message(sprintf("Loading annotation from %s", pkg_name))
    edb <- getExportedValue(pkg_name, pkg_name)
    return(edb)
  }

  # Fall back to AnnotationHub
  message("Fetching annotation from AnnotationHub...")
  ah <- AnnotationHub::AnnotationHub()
  query <- sprintf("EnsDb.%s", switch(genome, "hg38" = "Hsapiens", "mm10" = "Mmusculus"))
  edb <- ah[[names(ah)[grep(query, ah$title)][1]]]

  return(edb)
}

#' Recommend Signac parameters
#'
#' Get recommended parameters based on data characteristics
#'
#' @param n_cells Number of cells
#' @param genome Genome assembly
#' @return List of recommended parameters
#' @export
recommend_signac_params <- function(n_cells, genome = "hg38") {
  # QC thresholds
  min_counts <- if (n_cells > 10000) 3000 else 1000
  max_counts <- if (n_cells > 10000) 50000 else 20000
  min_tss <- 2
  max_ns <- 4

  # Dimensionality reduction
  dims <- if (n_cells > 50000) 2:50 else 2:30

  params <- list(
    min_counts = min_counts,
    max_counts = max_counts,
    min_tss = min_tss,
    max_ns = max_ns,
    dims = dims,
    resolution = 0.8,
    message = sprintf(
"Signac Parameter Recommendations:
  - Min counts: %d
  - Max counts: %d
  - Min TSS enrichment: %.1f
  - Max nucleosome signal: %.1f
  - Dimensions: %s
  - Cluster resolution: %.1f
  - Notes: %s",
      min_counts,
      max_counts,
      min_tss,
      max_ns,
      paste(range(dims), collapse = "-"),
      0.8,
      ifelse(n_cells > 50000,
             "Large dataset - consider higher dimensions",
             "Standard parameters recommended")
    )
  )

  cat(params$message, "\n")
  return(params)
}

#' Create marker gene list
#'
#' Create a list of marker genes for common cell types
#'
#' @param cell_types Character vector of cell types (default: NULL, all available)
#' @param tissue Tissue type: "blood", "pbmc", "bone_marrow" (default: "pbmc")
#' @return Named list of marker genes
#' @export
create_marker_list <- function(cell_types = NULL, tissue = "pbmc") {
  markers <- list(
    pbmc = list(
      CD14_Mono = c("LYZ", "S100A8", "S100A9", "CD14"),
      CD16_Mono = c("FCGR3A", "MS4A7", "LYZ"),
      CD4_T = c("CD3D", "IL7R", "CD4"),
      CD8_T = c("CD3D", "CD8A", "CD8B"),
      Naive_T = c("CCR7", "LEF1", "TCF7"),
      Memory_T = c("CD27", "IL7R"),
      B_cell = c("CD79A", "CD79B", "MS4A1", "CD19"),
      Plasma = c("MZB1", "JCHAIN", "SDC1"),
      NK = c("NKG7", "GNLY", "KLRD1", "NCAM1"),
      DC = c("FCER1A", "CST3", "CLEC10A"),
      Platelet = c("PPBP", "PF4")
    ),
    blood = list(
      HSC = c("CD34", "PROM1", "KIT"),
      CMP = c("CD34", "IL3RA"),
      GMP = c("CD34", "CSF3R", "MPO"),
      MEP = c("ITGA2B", "GATA1"),
      Erythroid = c("GATA1", "HBA1", "HBA2"),
      Monocyte = c("CD14", "LYZ", "S100A8"),
      Macrophage = c("CD163", "MRC1"),
      pDC = c("IL3RA", "CLEC4C"),
      cDC = c("CD1C", "CLEC9A"),
      B_cell = c("CD19", "CD79A", "MS4A1"),
      T_cell = c("CD3D", "CD3E", "CD3G"),
      NK = c("NKG7", "GNLY", "NCAM1")
    )
  )

  if (!tissue %in% names(markers)) {
    stop(sprintf("Tissue '%s' not available. Choose from: %s",
                 tissue, paste(names(markers), collapse = ", ")))
  }

  marker_list <- markers[[tissue]]

  if (!is.null(cell_types)) {
    available <- names(marker_list)
    missing <- cell_types[!cell_types %in% available]
    if (length(missing) > 0) {
      warning(sprintf("Cell types not available: %s", paste(missing, collapse = ", ")))
    }
    marker_list <- marker_list[cell_types[cell_types %in% available]]
  }

  return(marker_list)
}

#' Add sample metadata
#'
#' Add sample information to Seurat object
#'
#' @param seurat_obj Seurat object
#' @param sample_info Named vector or data frame with sample info
#' @param by Column to match by (default: "orig.ident")
#' @return Seurat object with added metadata
#' @export
add_sample_metadata <- function(seurat_obj, sample_info, by = "orig.ident") {
  if (is.vector(sample_info)) {
    # Named vector
    seurat_obj$sample <- sample_info[seurat_obj@meta.data[[by]]]
  } else if (is.data.frame(sample_info)) {
    # Data frame
    seurat_obj@meta.data <- merge(
      seurat_obj@meta.data,
      sample_info,
      by.x = by,
      by.y = 1,
      all.x = TRUE
    )
    rownames(seurat_obj@meta.data) <- colnames(seurat_obj)
  }

  return(seurat_obj)
}

#' Merge multiple Signac objects
#'
#' Merge multiple Seurat objects with ChromatinAssay
#'
#' @param object_list List of Seurat objects
#' @param add.cell.ids Prefixes for cell names (default: NULL)
#' @param merge.data Merge data slots (default: TRUE)
#' @return Merged Seurat object
#' @export
merge_signac_objects <- function(object_list, add.cell.ids = NULL,
                                  merge.data = TRUE) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (length(object_list) < 2) {
    stop("At least 2 objects required for merging")
  }

  message(sprintf("Merging %d objects...", length(object_list)))

  # Merge using Seurat
  merged <- Seurat::merge(
    x = object_list[[1]],
    y = object_list[-1],
    add.cell.ids = add.cell.ids,
    merge.data = merge.data
  )

  message(sprintf("Merged object: %d cells", ncol(merged)))
  return(merged)
}

#' Subset by sample
#'
#' Subset Seurat object by sample
#'
#' @param seurat_obj Seurat object
#' @param samples Samples to keep
#' @param invert Invert selection (default: FALSE)
#' @return Subsetted Seurat object
#' @export
subset_by_sample <- function(seurat_obj, samples, invert = FALSE) {
  if (!"orig.ident" %in% colnames(seurat_obj@meta.data)) {
    stop("orig.ident not found in metadata")
  }

  cells <- seurat_obj$orig.ident %in% samples
  if (invert) cells <- !cells

  return(seurat_obj[, cells])
}

#' Downsample cells
#'
#' Downsample to a maximum number of cells per group
#'
#' @param seurat_obj Seurat object
#' @param group_by Grouping variable (default: "orig.ident")
#' @param max_cells Maximum cells per group (default: 1000)
#' @return Downsampled Seurat object
#' @export
downsample_cells <- function(seurat_obj, group_by = "orig.ident",
                              max_cells = 1000) {
  groups <- seurat_obj@meta.data[[group_by]]
  unique_groups <- unique(groups)

  cells_keep <- unlist(lapply(unique_groups, function(g) {
    group_cells <- colnames(seurat_obj)[groups == g]
    if (length(group_cells) > max_cells) {
      sample(group_cells, max_cells)
    } else {
      group_cells
    }
  }))

  return(seurat_obj[, cells_keep])
}

#' Create Signac report
#'
#' Generate a text summary report
#'
#' @param seurat_obj Seurat object
#' @param output_file Output file path (optional)
#' @return Report text
#' @export
create_signac_report <- function(seurat_obj, output_file = NULL) {
  # QC summary
  qc_summary <- list(
    n_cells = ncol(seurat_obj),
    n_features = nrow(seurat_obj),
    assays = names(seurat_obj@assays),
    reductions = names(seurat_obj@reductions)
  )

  # Get QC stats if available
  if ("nCount_peaks" %in% colnames(seurat_obj@meta.data)) {
    qc_summary$mean_counts <- mean(seurat_obj$nCount_peaks)
    qc_summary$median_counts <- median(seurat_obj$nCount_peaks)
  }

  if ("TSS.enrichment" %in% colnames(seurat_obj@meta.data)) {
    qc_summary$mean_tss <- mean(seurat_obj$TSS.enrichment, na.rm = TRUE)
    qc_summary$median_tss <- median(seurat_obj$TSS.enrichment, na.rm = TRUE)
  }

  # Build report
  report <- sprintf("
Signac Analysis Report
======================
Date: %s

Sample Summary
--------------
Cells: %d
Features (peaks): %d
Assays: %s
Reductions: %s

Quality Metrics
---------------
Mean counts: %.1f
Median counts: %.1f
Mean TSS enrichment: %.2f
Median TSS enrichment: %.2f

Notes
-----
- Signac extends Seurat for scATAC-seq analysis
- Gene activity scores approximate gene expression
- Peak-gene links require Cicero or similar methods
",
    format(Sys.time(), "%Y-%m-%d %H:%M"),
    qc_summary$n_cells,
    qc_summary$n_features,
    paste(qc_summary$assays, collapse = ", "),
    paste(qc_summary$reductions, collapse = ", "),
    qc_summary$mean_counts %||% NA,
    qc_summary$median_counts %||% NA,
    qc_summary$mean_tss %||% NA,
    qc_summary$median_tss %||% NA
  )

  if (!is.null(output_file)) {
    writeLines(report, output_file)
  }

  return(report)
}

# Helper: null default operator
`%||%` <- function(x, y) if (is.null(x)) y else x
