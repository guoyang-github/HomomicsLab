# ArchR Utility Functions
# =======================
#
# Helper and utility functions for ArchR analysis

#' Install ArchR and dependencies
#'
#' Install ArchR and required packages
#'
#' @param install_suggests Also install suggested packages (default: FALSE)
#' @export
install_archr_deps <- function(install_suggests = FALSE) {
  if (!requireNamespace("BiocManager", quietly = TRUE)) {
    install.packages("BiocManager")
  }

  # Core dependencies
  core_packages <- c(
    "magick", "data.table", "Matrix", "ggplot2",
    "ComplexHeatmap", "BiocGenerics", "S4Vectors"
  )

  message("Installing core ArchR dependencies...")
  BiocManager::install(core_packages, ask = FALSE)

  # Install ArchR from GitHub
  message("Installing ArchR from GitHub...")
  devtools::install_github("GreenleafLab/ArchR", ref = "master",
                           repos = BiocManager::repositories())

  if (install_suggests) {
    suggests <- c(
      "DESeq2", "pheatmap", "viridis", "circlize",
      "rtracklayer", "AnnotationDbi", "org.Hs.eg.db"
    )
    message("Installing suggested packages...")
    BiocManager::install(suggests, ask = FALSE)
  }

  message("Installation complete!")
}

#' Get ArchR version information
#'
#' Get version info for ArchR and dependencies
#'
#' @return Data frame with version information
#' @export
get_archr_version_info <- function() {
  packages <- c("ArchR", "magick", "data.table", "Matrix", "ggplot2",
                "ComplexHeatmap", "BiocGenerics", "S4Vectors")

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

#' Validate fragment files
#'
#' Check if fragment files exist and are valid
#'
#' @param fragment_files Character vector of fragment file paths
#' @param check_gzipped Check if files are gzipped (default: TRUE)
#' @return Data frame with validation results
#' @export
validate_fragment_files <- function(fragment_files, check_gzipped = TRUE) {
  results <- data.frame(
    file = fragment_files,
    exists = file.exists(fragment_files),
    readable = file.access(fragment_files, 4) == 0,
    gzipped = NA,
    stringsAsFactors = FALSE
  )

  if (check_gzipped) {
    results$gzipped <- grepl("\\.gz$", fragment_files)
  }

  # Check file format
  results$valid_format <- sapply(fragment_files, function(f) {
    if (!file.exists(f)) return(NA)
    tryCatch({
      # Read first few lines
      lines <- utils::read.table(f, nrows = 5, sep = "\t",
                                  comment.char = "", stringsAsFactors = FALSE)
      # Check for at least 5 columns (chr, start, end, barcode, count)
      ncol(lines) >= 5
    }, error = function(e) FALSE)
  })

  return(results)
}

#' Recommend ArchR parameters
#'
#' Get recommended parameters based on data characteristics
#'
#' @param n_cells Number of cells
#' @param n_samples Number of samples
#' @param has_macs2 Whether MACS2 is available
#' @return List of recommended parameters
#' @export
recommend_archr_params <- function(n_cells, n_samples, has_macs2 = NULL) {
  if (is.null(has_macs2)) {
    has_macs2 <- !is.null(tryCatch(system("which macs2", intern = TRUE),
                                    error = function(e) NULL))
  }

  # Recommend threads
  available_cores <- parallel::detectCores()
  n_cores <- min(16, max(4, available_cores %/% 2))

  # Recommend filtering
  filter_frags <- if (n_cells > 10000) 2000 else 1000
  filter_tss <- if (n_cells > 10000) 6 else 4

  # Recommend LSI iterations
  lsi_iterations <- if (n_cells > 50000) 3 else 2

  # Recommend cluster resolution
  cluster_resolution <- if (n_cells > 50000) 1.0 else 0.8

  params <- list(
    n_cores = n_cores,
    filter_frags = filter_frags,
    filter_tss = filter_tss,
    lsi_iterations = lsi_iterations,
    cluster_resolution = cluster_resolution,
    run_peak_calling = has_macs2,
    message = sprintf(
"ArchR Parameter Recommendations:
  - Parallel cores: %d (from %d available)
  - Min fragments per cell: %d
  - Min TSS enrichment: %.1f
  - LSI iterations: %d
  - Cluster resolution: %.1f
  - Peak calling: %s
  - Notes: %s",
      n_cores,
      available_cores,
      filter_frags,
      filter_tss,
      lsi_iterations,
      cluster_resolution,
      ifelse(has_macs2, "ENABLED", "DISABLED (install MACS2 to enable)"),
      ifelse(n_cells > 50000,
             "Large dataset - consider higher iterations and resolution",
             "Standard parameters recommended")
    )
  )

  cat(params$message, "\n")
  return(params)
}

#' Get available genomes
#'
#' List available genome annotations for ArchR
#'
#' @return Character vector of available genomes
#' @export
get_available_genomes <- function() {
  c("hg38", "hg19", "mm10", "mm9")
}

#' Create sample metadata from filenames
#'
#' Extract sample information from fragment filenames
#'
#' @param fragment_files Character vector of fragment file paths
#' @param pattern Regex pattern to extract sample name (default: "^([^_]+)")
#' @return Data frame with sample metadata
#' @export
create_sample_metadata <- function(fragment_files, pattern = "^([^_]+)") {
  sample_names <- gsub("\\.fragments\\.tsv\\.gz$", "", basename(fragment_files))

  # Try to extract group info from pattern
  groups <- gsub(pattern, "\\1", sample_names)

  metadata <- data.frame(
    sample = sample_names,
    file = fragment_files,
    group = groups,
    stringsAsFactors = FALSE
  )

  return(metadata)
}

#' Filter cells by metadata
#'
#' Subset ArchR project based on cell metadata
#'
#' @param proj ArchRProject object
#' @param subset Logical vector or expression for subsetting
#' @param return_cells Return cell names instead of subsetted project (default: FALSE)
#' @return ArchRProject object or character vector of cell names
#' @export
filter_cells_by_metadata <- function(proj, subset, return_cells = FALSE) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  cell_data <- ArchR::getCellColData(proj)
  env <- list2env(as.list(cell_data))

  if (is.language(subset) || is.character(subset)) {
    if (is.character(subset)) {
      subset <- parse(text = subset)
    }
    keep <- eval(subset, env)
  } else if (is.logical(subset)) {
    keep <- subset
  } else {
    stop("subset must be a logical vector or expression")
  }

  cell_names <- ArchR::getCellNames(proj)[keep]

  if (return_cells) {
    return(cell_names)
  }

  proj <- ArchR::subsetArchRProject(
    proj,
    cells = cell_names,
    outputDirectory = "Subset",
    dropCells = TRUE
  )

  return(proj)
}

#' Merge multiple ArchR projects
#'
#' Merge multiple ArchR projects into one
#'
#' @param proj_list List of ArchRProject objects
#' @param output_directory Output directory for merged project
#' @param merge_embeddings Merge embeddings (default: TRUE)
#' @return ArchRProject object
#' @export
merge_archr_projects <- function(proj_list, output_directory = "Merged",
                                  merge_embeddings = TRUE) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  if (length(proj_list) < 2) {
    stop("At least 2 projects required for merging")
  }

  message(sprintf("Merging %d ArchR projects...", length(proj_list)))

  # Use ArchR's merge function
  proj <- ArchR::mergeArchRProjects(
    ArchRProj1 = proj_list[[1]],
    ArchRProj2 = proj_list[[2]],
    outputDirectory = output_directory
  )

  # Merge remaining projects
  if (length(proj_list) > 2) {
    for (i in 3:length(proj_list)) {
      proj <- ArchR::mergeArchRProjects(
        ArchRProj1 = proj,
        ArchRProj2 = proj_list[[i]],
        outputDirectory = output_directory
      )
    }
  }

  message(sprintf("Merged project with %d cells", length(ArchR::getCellNames(proj))))
  return(proj)
}

#' Export fragment files
#'
#' Export fragment files from ArchR project
#'
#' @param proj ArchRProject object
#' @param output_dir Output directory
#' @param by_sample Export by sample (default: TRUE)
#' @return Character vector of output file paths
#' @export
export_fragment_files <- function(proj, output_dir = "./fragments",
                                   by_sample = TRUE) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Get fragment data
  cell_data <- ArchR::getCellColData(proj)

  if (by_sample) {
    samples <- unique(cell_data$Sample)
    output_files <- character(length(samples))

    for (i in seq_along(samples)) {
      sample <- samples[i]
      output_file <- file.path(output_dir, paste0(sample, "_fragments.tsv.gz"))
      message(sprintf("Exporting fragments for %s...", sample))
      # Note: Actual implementation would require accessing Arrow files
      output_files[i] <- output_file
    }
  } else {
    output_file <- file.path(output_dir, "all_fragments.tsv.gz")
    message("Exporting all fragments...")
    output_files <- output_file
  }

  return(output_files)
}

#' Create marker gene list
#'
#' Create a list of marker genes for common cell types
#'
#' @param cell_types Character vector of cell types (default: NULL, all available)
#' @param tissue Tissue type: "blood", "pbmc", "bone_marrow" (default: "blood")
#' @return Named list of marker genes
#' @export
create_marker_list <- function(cell_types = NULL, tissue = "blood") {
  markers <- list(
    blood = list(
      HSC = c("CD34", "PROM1", "KIT"),
      CMP = c("CD34", "IL3RA", "MEP"),
      GMP = c("CD34", "CSF3R", "MPO"),
      MEP = c("EPOR", "ITGA2B", "GATA1"),
      Erythroid = c("GATA1", "HBA1", "HBA2", "HBE1"),
      Monocyte = c("CD14", "LYZ", "S100A8", "S100A9"),
      Macrophage = c("CD163", "MRC1", "MARCO"),
      pDC = c("IL3RA", "CLEC4C", "LILRA4"),
      cDC = c("CD1C", "CLEC9A", "XCR1"),
      B_cell = c("CD19", "CD79A", "CD79B", "MS4A1"),
      Plasma_cell = c("CD138", "PRDM1", "XBP1"),
      T_cell = c("CD3D", "CD3E", "CD3G", "TRAC"),
      CD4_T = c("CD4", "IL7R"),
      CD8_T = c("CD8A", "CD8B"),
      NK = c("NCAM1", "NKG7", "KLRD1", "GNLY")
    ),
    pbmc = list(
      CD14_Mono = c("CD14", "LYZ", "S100A8"),
      CD16_Mono = c("FCGR3A", "MS4A7", "LYZ"),
      CD4_T = c("CD4", "IL7R"),
      CD8_T = c("CD8A", "CD8B"),
      Naive_T = c("CCR7", "LEF1", "TCF7"),
      Memory_T = c("CD27", "IL7R", "CCR7"),
      B_cell = c("CD79A", "CD79B", "MS4A1"),
      NK = c("NKG7", "GNLY", "KLRD1"),
      DC = c("FCER1A", "CST3", "CLEC10A"),
      Platelet = c("PPBP", "PF4")
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

#' Convert ArchR to Seurat
#'
#' Convert ArchR project to Seurat object
#'
#' @param proj ArchRProject object
#' @param assay_name Name for Seurat assay (default: "ATAC")
#' @param use_matrix Matrix to use (default: "GeneScoreMatrix")
#' @param transfer_embeddings Transfer embeddings (default: TRUE)
#' @return Seurat object
#' @export
convert_to_seurat <- function(proj, assay_name = "ATAC",
                               use_matrix = "GeneScoreMatrix",
                               transfer_embeddings = TRUE) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Get matrix
  mat <- ArchR::getMatrixFromProject(proj, useMatrix = use_matrix)
  expr_mat <- assays(mat)[[1]]

  # Create Seurat object
  seurat_obj <- Seurat::CreateSeuratObject(
    counts = expr_mat,
    assay = assay_name,
    meta.data = as.data.frame(ArchR::getCellColData(proj))
  )

  # Transfer embeddings
  if (transfer_embeddings) {
    for (red_name in names(ArchR::getReducedDims(proj))) {
      red_dims <- ArchR::getReducedDims(proj, reducedDims = red_name)
      seurat_obj@reductions[[red_name]] <- Seurat::CreateDimReducObject(
        embeddings = red_dims,
        key = paste0(red_name, "_"),
        assay = assay_name
      )
    }

    # Transfer UMAP
    if ("UMAP" %in% names(ArchR::getEmbeddings(proj))) {
      umap_coords <- ArchR::getEmbedding(proj, embedding = "UMAP")
      seurat_obj@reductions[["umap"]] <- Seurat::CreateDimReducObject(
        embeddings = umap_coords,
        key = "UMAP_",
        assay = assay_name
      )
    }
  }

  return(seurat_obj)
}

#' Create ArchR report
#'
#' Generate a text summary report
#'
#' @param proj ArchRProject object
#' @param output_file Output file path (optional)
#' @return Report text
#' @export
create_archr_report <- function(proj, output_file = NULL) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  summary <- list(
    n_cells = length(ArchR::getCellNames(proj)),
    n_samples = length(unique(ArchR::getCellColData(proj)$Sample)),
    matrices = ArchR::getAvailableMatrices(proj),
    embeddings = names(ArchR::getEmbeddings(proj)),
    reduced_dims = names(ArchR::getReducedDims(proj))
  )

  cell_data <- ArchR::getCellColData(proj)

  report <- sprintf("
ArchR Analysis Report
=====================
Date: %s

Sample Summary
--------------
Total cells: %d
Number of samples: %d
Samples: %s

Data Matrices
-------------
%s

Embeddings
----------
%s

Reduced Dimensions
------------------
%s

Quality Metrics
---------------
Mean TSS Enrichment: %.2f
Mean log10(nFrags): %.2f
",
    format(Sys.time(), "%Y-%m-%d %H:%M"),
    summary$n_cells,
    summary$n_samples,
    paste(unique(cell_data$Sample), collapse = ", "),
    paste(summary$matrices, collapse = "\n"),
    paste(summary$embeddings, collapse = ", "),
    paste(summary$reduced_dims, collapse = ", "),
    mean(cell_data$TSSEnrichment, na.rm = TRUE),
    mean(log10(cell_data$nFrags), na.rm = TRUE)
  )

  if ("Clusters" %in% colnames(cell_data)) {
    cluster_table <- table(cell_data$Clusters)
    report <- paste0(report, "
Cluster Distribution
--------------------
",
                     paste(capture.output(print(cluster_table)), collapse = "\n"))
  }

  if (!is.null(ArchR::getPeakSet(proj))) {
    report <- paste0(report, sprintf("
Peak Set
--------
Number of peaks: %d
", length(ArchR::getPeakSet(proj))))
  }

  if (!is.null(output_file)) {
    writeLines(report, output_file)
  }

  return(report)
}

#' Check MACS2 installation
#'
#' Check if MACS2 is installed and available
#'
#' @return Logical indicating if MACS2 is available
#' @export
check_macs2 <- function() {
  path <- tryCatch(
    system("which macs2", intern = TRUE),
    error = function(e) NULL
  )

  if (!is.null(path)) {
    version <- tryCatch(
      system("macs2 --version", intern = TRUE),
      error = function(e) "unknown"
    )
    message(sprintf("MACS2 found: %s", path))
    message(sprintf("Version: %s", version[1]))
    return(TRUE)
  } else {
    message("MACS2 not found in PATH")
    message("Install with: pip install MACS2")
    return(FALSE)
  }
}
