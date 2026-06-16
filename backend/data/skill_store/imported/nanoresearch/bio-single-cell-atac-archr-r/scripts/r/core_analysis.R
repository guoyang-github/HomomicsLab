# ArchR Core Analysis Functions
# ==============================
#
# Main analysis functions for single-cell ATAC-seq analysis using ArchR

#' Check ArchR dependencies
#'
#' Check if required packages are installed
#'
#' @return Logical indicating if all dependencies are available
#' @export
check_archr_dependencies <- function() {
  required <- c("ArchR", "magick", "data.table", "Matrix", "ggplot2")
  missing <- required[!sapply(required, requireNamespace, quietly = TRUE)]

  if (length(missing) > 0) {
    warning(paste("Missing packages:", paste(missing, collapse = ", ")))
    return(FALSE)
  }
  return(TRUE)
}

#' Setup ArchR environment
#'
#' Configure ArchR threads and genome
#'
#' @param threads Number of threads (default: 4)
#' @param genome Genome annotation: "hg38", "hg19", "mm10", "mm9" (default: "hg38")
#' @return NULL
#' @export
setup_archr <- function(threads = 4, genome = "hg38") {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Set threads
  ArchR::addArchRThreads(threads = threads)
  message(sprintf("ArchR threads set to: %d", threads))

  # Set genome
  valid_genomes <- c("hg38", "hg19", "mm10", "mm9")
  if (!genome %in% valid_genomes) {
    stop(sprintf("Genome must be one of: %s", paste(valid_genomes, collapse = ", ")))
  }

  ArchR::addArchRGenome(genome)
  message(sprintf("ArchR genome set to: %s", genome))

  invisible(NULL)
}

#' Create Arrow files from fragment files
#'
#' Create Arrow files for efficient storage and analysis of scATAC-seq data
#'
#' @param input_files Character vector of fragment file paths (.tsv.gz)
#' @param sample_names Character vector of sample names (default: names of input_files)
#' @param output_names Character vector of output names (default: sample_names)
#' @param filter_tss TSS enrichment filter (default: 4)
#' @param filter_frags Minimum fragments per cell (default: 1000)
#' @param add_tile_mat Add tile matrix (default: TRUE)
#' @param add_gene_score_mat Add gene score matrix (default: TRUE)
#' @param valid_barcodes List of valid barcodes per sample (optional)
#' @param min_frags Minimum fragments for cell calling (default: 500)
#' @param max_frags Maximum fragments for cell calling (default: 1e6)
#' @param nuc_length Nucleosome length (default: 147)
#' @return Character vector of Arrow file paths
#' @export
create_arrow_files <- function(
    input_files,
    sample_names = names(input_files),
    output_names = sample_names,
    filter_tss = 4,
    filter_frags = 1000,
    add_tile_mat = TRUE,
    add_gene_score_mat = TRUE,
    valid_barcodes = NULL,
    min_frags = 500,
    max_frags = 1e6,
    nuc_length = 147
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Validate inputs
  if (!all(file.exists(input_files))) {
    missing <- input_files[!file.exists(input_files)]
    stop(sprintf("Input files not found: %s", paste(missing, collapse = ", ")))
  }

  if (is.null(sample_names)) {
    sample_names <- basename(input_files)
  }

  message(sprintf("Creating Arrow files for %d samples...", length(input_files)))
  message(sprintf("Filters: TSS >= %.1f, Frags >= %d", filter_tss, filter_frags))

  # Create Arrow files
  arrow_files <- ArchR::createArrowFiles(
    inputFiles = input_files,
    sampleNames = sample_names,
    outputNames = output_names,
    validBarcodes = valid_barcodes,
    filterTSS = filter_tss,
    filterFrags = filter_frags,
    addTileMat = add_tile_mat,
    addGeneScoreMat = add_gene_score_mat,
    minFrags = min_frags,
    maxFrags = max_frags,
    nucLength = nuc_length
  )

  message(sprintf("Created %d Arrow files", length(arrow_files)))
  return(arrow_files)
}

#' Create ArchR project
#'
#' Create an ArchRProject from Arrow files
#'
#' @param arrow_files Character vector of Arrow file paths
#' @param output_directory Output directory for project (default: "Save-ArchR")
#' @param copy_arrows Copy Arrow files to output directory (default: TRUE)
#' @param gene_annotation Gene annotation (default: NULL, uses ArchR default)
#' @param genome_annotation Genome annotation (default: NULL, uses ArchR default)
#' @param show_logo Show ArchR logo (default: FALSE)
#' @return ArchRProject object
#' @export
create_archr_project <- function(
    arrow_files,
    output_directory = "Save-ArchR",
    copy_arrows = TRUE,
    gene_annotation = NULL,
    genome_annotation = NULL,
    show_logo = FALSE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Validate Arrow files
  if (!all(file.exists(arrow_files))) {
    missing <- arrow_files[!file.exists(arrow_files)]
    stop(sprintf("Arrow files not found: %s", paste(missing, collapse = ", ")))
  }

  message(sprintf("Creating ArchR project: %s", output_directory))
  message(sprintf("Using %d Arrow files", length(arrow_files)))

  # Create project
  proj <- ArchR::ArchRProject(
    ArrowFiles = arrow_files,
    outputDirectory = output_directory,
    copyArrows = copy_arrows,
    geneAnnotation = gene_annotation,
    genomeAnnotation = genome_annotation,
    showLogo = show_logo
  )

  message(sprintf("Project created with %d cells", length(ArchR::getCellNames(proj))))
  return(proj)
}

#' Load existing ArchR project
#'
#' Load a previously saved ArchR project
#'
#' @param path Path to project directory
#' @param force Force load even if cells have been dropped (default: FALSE)
#' @param show_logo Show ArchR logo (default: FALSE)
#' @return ArchRProject object
#' @export
load_archr_project <- function(path = "./", force = FALSE, show_logo = FALSE) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  proj <- ArchR::loadArchRProject(
    path = path,
    force = force,
    showLogo = show_logo
  )

  message(sprintf("Loaded project with %d cells", length(ArchR::getCellNames(proj))))
  return(proj)
}

#' Save ArchR project
#'
#' Save an ArchR project to disk
#'
#' @param proj ArchRProject object
#' @param output_directory Output directory (default: project output directory)
#' @param overwrite Overwrite existing files (default: TRUE)
#' @param load Reload project after saving (default: TRUE)
#' @return ArchRProject object (reloaded if load=TRUE)
#' @export
save_archr_project <- function(
    proj,
    output_directory = NULL,
    overwrite = TRUE,
    load = TRUE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  proj <- ArchR::saveArchRProject(
    ArchRProj = proj,
    outputDirectory = output_directory,
    overwrite = overwrite,
    load = load
  )

  message("Project saved successfully")
  return(proj)
}

#' Add doublet scores
#'
#' Calculate doublet scores for each cell
#'
#' @param proj ArchRProject object
#' @param use_matrix Matrix to use (default: "TileMatrix")
#' @param k Number of nearest neighbors (default: 10)
#' @param n_trials Number of simulation trials (default: 5)
#' @param dims_to_use Dimensions to use (default: 1:30)
#' @param LSIMethod LSI method (default: 1)
#' @return ArchRProject object with doublet scores
#' @export
add_doublet_scores <- function(
    proj,
    use_matrix = "TileMatrix",
    k = 10,
    n_trials = 5,
    dims_to_use = 1:30,
    LSIMethod = 1
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  message("Computing doublet scores...")
  proj <- ArchR::addDoubletScores(
    input = proj,
    useMatrix = use_matrix,
    k = k,
    nTrials = n_trials,
    dimsToUse = dims_to_use,
    LSIMethod = LSIMethod
  )

  # Report doublet info
  doublet_scores <- ArchR::getCellColData(proj, select = "DoubletScore")
  message(sprintf("Doublet scores computed for %d cells", nrow(doublet_scores)))

  return(proj)
}

#' Filter doublets
#'
#' Remove predicted doublets from the project
#'
#' @param proj ArchRProject object
#' @param cut_enrich Cutoff for enrichment ratio (default: NULL, auto)
#' @param cut_score Cutoff for doublet score (default: NULL, auto)
#' @param filter_ratio Filter ratio (default: 1)
#' @return ArchRProject object with doublets removed
#' @export
filter_doublets <- function(
    proj,
    cut_enrich = NULL,
    cut_score = NULL,
    filter_ratio = 1
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  n_before <- length(ArchR::getCellNames(proj))
  message(sprintf("Filtering doublets from %d cells...", n_before))

  proj <- ArchR::filterDoublets(
    ArchRProj = proj,
    cutEnrich = cut_enrich,
    cutScore = cut_score,
    filterRatio = filter_ratio
  )

  n_after <- length(ArchR::getCellNames(proj))
  message(sprintf("Retained %d cells (%.1f%%)",
                  n_after, 100 * n_after / n_before))

  return(proj)
}

#' Add iterative LSI
#'
#' Perform iterative LSI dimensionality reduction
#'
#' @param proj ArchRProject object
#' @param use_matrix Matrix to use (default: "TileMatrix")
#' @param name Name for reduced dimensions (default: "IterativeLSI")
#' @param iterations Number of iterations (default: 2)
#' @param cluster_params Clustering parameters (default: list(resolution=2, sampleCells=10000))
#' @param var_features Number of variable features (default: 25000)
#' @param dims_to_use Dimensions to use (default: 1:30)
#' @param scale_to Scale factor (default: 10000)
#' @param total_features Total features (default: 5e5)
#' @param filter_quantile Filter quantile (default: 0.995)
#' @param binarize Binarize matrix (default: TRUE)
#' @param n_plot Number of iterations to plot (default: 3)
#' @return ArchRProject object with LSI dimensions
#' @export
add_iterative_lsi <- function(
    proj,
    use_matrix = "TileMatrix",
    name = "IterativeLSI",
    iterations = 2,
    cluster_params = list(resolution = 2, sampleCells = 10000),
    var_features = 25000,
    dims_to_use = 1:30,
    scale_to = 10000,
    total_features = 5e5,
    filter_quantile = 0.995,
    binarize = TRUE,
    n_plot = 3
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  message(sprintf("Running iterative LSI (%d iterations)...", iterations))

  proj <- ArchR::addIterativeLSI(
    ArchRProj = proj,
    useMatrix = use_matrix,
    name = name,
    iterations = iterations,
    clusterParams = cluster_params,
    varFeatures = var_features,
    dimsToUse = dims_to_use,
    scaleTo = scale_to,
    totalFeatures = total_features,
    filterQuantile = filter_quantile,
    binarize = binarize,
    nPlot = n_plot
  )

  message(sprintf("LSI dimensions '%s' added", name))
  return(proj)
}

#' Add clusters
#'
#' Cluster cells using reduced dimensions
#'
#' @param proj ArchRProject object
#' @param reduced_dims Name of reduced dimensions (default: "IterativeLSI")
#' @param name Name for clusters (default: "Clusters")
#' @param sample_cells Number of cells to sample (default: NULL, use all)
#' @param seed Random seed (default: 1)
#' @param method Clustering method (default: "Seurat")
#' @param resolution Clustering resolution (default: 0.8)
#' @param k_neighbors Number of nearest neighbors (default: 30)
#' @param n_outlier Minimum outlier filter (default: 50)
#' @param test_nndb Test for near-duplicate clusters (default: TRUE)
#' @param test_distance Test distance threshold (default: 0.01)
#' @return ArchRProject object with clusters
#' @export
add_clusters <- function(
    proj,
    reduced_dims = "IterativeLSI",
    name = "Clusters",
    sample_cells = NULL,
    seed = 1,
    method = "Seurat",
    resolution = 0.8,
    k_neighbors = 30,
    n_outlier = 50,
    test_nndb = TRUE,
    test_distance = 0.01
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  message(sprintf("Clustering cells (method=%s, resolution=%.2f)...", method, resolution))

  proj <- ArchR::addClusters(
    input = proj,
    reducedDims = reduced_dims,
    name = name,
    sampleCells = sample_cells,
    seed = seed,
    method = method,
    resolution = resolution,
    knnAssign = k_neighbors,
    nOutlier = n_outlier,
    testNNdB = test_nndb,
    testDist = test_distance
  )

  # Report clusters
  clusters <- ArchR::getCellColData(proj, select = name)
  n_clusters <- length(unique(clusters[[1]]))
  message(sprintf("Identified %d clusters", n_clusters))

  return(proj)
}

#' Add UMAP embedding
#'
#' Compute UMAP embedding from reduced dimensions
#'
#' @param proj ArchRProject object
#' @param reduced_dims Name of reduced dimensions (default: "IterativeLSI")
#' @param name Name for embedding (default: "UMAP")
#' @param n_neighbors Number of neighbors (default: 40)
#' @param min_dist Minimum distance (default: 0.4)
#' @param metric Distance metric (default: "cosine")
#' @param dims_to_use Dimensions to use (default: NULL, use all)
#' @param seed Random seed (default: 1)
#' @return ArchRProject object with UMAP
#' @export
add_umap <- function(
    proj,
    reduced_dims = "IterativeLSI",
    name = "UMAP",
    n_neighbors = 40,
    min_dist = 0.4,
    metric = "cosine",
    dims_to_use = NULL,
    seed = 1
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  message(sprintf("Computing UMAP (n_neighbors=%d, min_dist=%.2f)...", n_neighbors, min_dist))

  proj <- ArchR::addUMAP(
    ArchRProj = proj,
    reducedDims = reduced_dims,
    name = name,
    nNeighbors = n_neighbors,
    minDist = min_dist,
    metric = metric,
    dimsToUse = dims_to_use,
    seed = seed
  )

  message(sprintf("UMAP '%s' added", name))
  return(proj)
}

#' Add reproducible peak set
#'
#' Call peaks using MACS2 and create reproducible peak set
#'
#' @param proj ArchRProject object
#' @param group_by Grouping column for peak calling (default: "Clusters")
#' @param peak_method Peak calling method (default: "Macs2")
#' @param reproducibility Reproducibility requirement (default: "2")
#' @param peaks_per_cell Peaks per cell (default: 500)
#' @param max_peaks Maximum peaks (default: 250000)
#' @param min_cells Minimum cells per group (default: 25)
#' @param exclude_chr Chromosomes to exclude (default: c("chrM", "chrY"))
#' @param extend_peaks Peak extension (default: 250)
#' @param promoter_region Promoter region (default: c(2000, 100))
#' @param path_to_macs2 Path to MACS2 executable (default: NULL)
#' @param force Force re-run (default: FALSE)
#' @return ArchRProject object with peak set
#' @export
add_reproducible_peak_set <- function(
    proj,
    group_by = "Clusters",
    peak_method = "Macs2",
    reproducibility = "2",
    peaks_per_cell = 500,
    max_peaks = 250000,
    min_cells = 25,
    exclude_chr = c("chrM", "chrY"),
    extend_peaks = 250,
    promoter_region = c(2000, 100),
    path_to_macs2 = NULL,
    force = FALSE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  message(sprintf("Calling peaks by '%s'...", group_by))
  message(sprintf("Method: %s, Reproducibility: %s", peak_method, reproducibility))

  if (peak_method == "Macs2" && is.null(path_to_macs2)) {
    path_to_macs2 <- tryCatch({
      system("which macs2", intern = TRUE)
    }, error = function(e) NULL)
    if (is.null(path_to_macs2)) {
      warning("MACS2 not found in PATH. Provide path_to_macs2 parameter.")
    }
  }

  proj <- ArchR::addReproduciblePeakSet(
    ArchRProj = proj,
    groupBy = group_by,
    peakMethod = peak_method,
    reproducibility = reproducibility,
    peaksPerCell = peaks_per_cell,
    maxPeaks = max_peaks,
    minCells = min_cells,
    excludeChr = exclude_chr,
    extendPeaks = extend_peaks,
    promoterRegion = promoter_region,
    pathToMacs2 = path_to_macs2,
    force = force
  )

  # Report peaks
  peaks <- ArchR::getPeakSet(proj)
  message(sprintf("Peak set created: %d peaks", length(peaks)))

  return(proj)
}

#' Add peak matrix
#'
#' Add peak x cell count matrix to the project
#'
#' @param proj ArchRProject object
#' @param ceiling Maximum count per peak (default: 4)
#' @param binarize Binarize counts (default: FALSE)
#' @param return_matrix Return matrix (default: FALSE)
#' @return ArchRProject object with peak matrix (or matrix if return_matrix=TRUE)
#' @export
add_peak_matrix <- function(
    proj,
    ceiling = 4,
    binarize = FALSE,
    return_matrix = FALSE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  message("Adding peak matrix...")

  proj <- ArchR::addPeakMatrix(
    ArchRProj = proj,
    ceiling = ceiling,
    binarize = binarize
  )

  message("Peak matrix added successfully")

  if (return_matrix) {
    return(ArchR::getMatrixFromProject(proj, useMatrix = "PeakMatrix"))
  }

  return(proj)
}

#' Add motif annotations
#'
#' Add TF motif annotations to peak set
#'
#' @param proj ArchRProject object
#' @param motif_set Motif set: "cisbp", "encode", "homer", "jasparkellis" (default: "cisbp")
#' @param anno_name Name for annotation (default: "Motif")
#' @param species Species for JASPAR (default: NULL)
#' @param collection Collection for JASPAR (default: "CORE")
#' @param motif_pwms Custom PWMs (default: NULL)
#' @param cut_off P-value cutoff (default: 5e-05)
#' @param width Width for motif scanning (default: 7)
#' @param version Version (default: 2)
#' @return ArchRProject object with motif annotations
#' @export
add_motif_annotations <- function(
    proj,
    motif_set = "cisbp",
    anno_name = "Motif",
    species = NULL,
    collection = "CORE",
    motif_pwms = NULL,
    cut_off = 5e-05,
    width = 7,
    version = 2
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  message(sprintf("Adding motif annotations (set=%s)...", motif_set))

  proj <- ArchR::addMotifAnnotations(
    ArchRProj = proj,
    motifSet = motif_set,
    annoName = anno_name,
    species = species,
    collection = collection,
    motifPWMs = motif_pwms,
    cutOff = cut_off,
    width = width,
    version = version
  )

  message(sprintf("Motif annotations '%s' added", anno_name))
  return(proj)
}

#' Add deviations matrix
#'
#' Add chromVAR deviations matrix for motif analysis
#'
#' @param proj ArchRProject object
#' @param peak_annotation Peak annotation name (default: "Motif")
#' @param matrix_name Name for deviation matrix (default: auto)
#' @param bgd_peaks Background peaks (default: NULL)
#' @param out Output type: "z", "deviations", or "both" (default: "z")
#' @param binarize Binarize counts (default: FALSE)
#' @param force Force re-run (default: FALSE)
#' @return ArchRProject object with deviations matrix
#' @export
add_deviations_matrix <- function(
    proj,
    peak_annotation = "Motif",
    matrix_name = NULL,
    bgd_peaks = NULL,
    out = "z",
    binarize = FALSE,
    force = FALSE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  if (is.null(matrix_name)) {
    matrix_name <- paste0(peak_annotation, "Matrix")
  }

  message(sprintf("Adding deviations matrix for '%s'...", peak_annotation))

  proj <- ArchR::addDeviationsMatrix(
    ArchRProj = proj,
    peakAnnotation = peak_annotation,
    matrixName = matrix_name,
    bgdPeaks = bgd_peaks,
    out = out,
    binarize = binarize,
    force = force
  )

  message(sprintf("Deviations matrix '%s' added", matrix_name))
  return(proj)
}

#' Run standard ArchR workflow
#'
#' Run the complete standard ArchR analysis pipeline
#'
#' @param input_files Character vector of fragment file paths
#' @param sample_names Character vector of sample names
#' @param output_directory Output directory (default: "ArchR-Project")
#' @param genome Genome: "hg38", "hg19", "mm10" (default: "hg38")
#' @param threads Number of threads (default: 4)
#' @param filter_tss TSS enrichment filter (default: 4)
#' @param filter_frags Fragment filter (default: 1000)
#' @param lsi_iterations LSI iterations (default: 2)
#' @param cluster_resolution Clustering resolution (default: 0.8)
#' @param run_umap Run UMAP (default: TRUE)
#' @param run_doublet_filter Filter doublets (default: TRUE)
#' @param run_peak_calling Run peak calling (default: FALSE)
#' @param path_to_macs2 Path to MACS2 (default: NULL)
#' @return ArchRProject object
#' @export
run_archr_workflow <- function(
    input_files,
    sample_names = NULL,
    output_directory = "ArchR-Project",
    genome = "hg38",
    threads = 4,
    filter_tss = 4,
    filter_frags = 1000,
    lsi_iterations = 2,
    cluster_resolution = 0.8,
    run_umap = TRUE,
    run_doublet_filter = TRUE,
    run_peak_calling = FALSE,
    path_to_macs2 = NULL
) {
  # Setup
  setup_archr(threads = threads, genome = genome)

  # Create Arrow files
  arrow_files <- create_arrow_files(
    input_files = input_files,
    sample_names = sample_names,
    filter_tss = filter_tss,
    filter_frags = filter_frags
  )

  # Create project
  proj <- create_archr_project(
    arrow_files = arrow_files,
    output_directory = output_directory
  )

  # Filter doublets
  if (run_doublet_filter) {
    proj <- add_doublet_scores(proj)
    proj <- filter_doublets(proj)
  }

  # Dimensionality reduction
  proj <- add_iterative_lsi(proj, iterations = lsi_iterations)

  # Clustering
  proj <- add_clusters(proj, resolution = cluster_resolution)

  # UMAP
  if (run_umap) {
    proj <- add_umap(proj)
  }

  # Peak calling
  if (run_peak_calling) {
    proj <- add_reproducible_peak_set(proj, path_to_macs2 = path_to_macs2)
    proj <- add_peak_matrix(proj)
  }

  # Save project
  proj <- save_archr_project(proj)

  message("\n=== ArchR Workflow Complete ===")
  message(sprintf("Cells: %d", length(ArchR::getCellNames(proj))))
  message(sprintf("Clusters: %d", length(unique(ArchR::getCellColData(proj)$Clusters))))

  return(proj)
}

#' Get project summary
#'
#' Get summary statistics for ArchR project
#'
#' @param proj ArchRProject object
#' @return List with summary statistics
#' @export
get_archr_summary <- function(proj) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  cell_data <- ArchR::getCellColData(proj)

  summary <- list(
    n_cells = length(ArchR::getCellNames(proj)),
    n_samples = length(unique(cell_data$Sample)),
    samples = unique(cell_data$Sample),
    matrices = ArchR::getAvailableMatrices(proj),
    embeddings = names(ArchR::getEmbeddings(proj)),
    reduced_dims = names(ArchR::getReducedDims(proj))
  )

  # Add cluster info if available
  if ("Clusters" %in% colnames(cell_data)) {
    summary$n_clusters <- length(unique(cell_data$Clusters))
    summary$clusters_per_sample <- table(cell_data$Sample, cell_data$Clusters)
  }

  # Add peak info if available
  peaks <- tryCatch(ArchR::getPeakSet(proj), error = function(e) NULL)
  if (!is.null(peaks)) {
    summary$n_peaks <- length(peaks)
  }

  return(summary)
}

#' Export ArchR project metadata
#'
#' Export cell metadata to file
#'
#' @param proj ArchRProject object
#' @param output_file Output file path
#' @return Data frame of cell metadata
#' @export
export_cell_metadata <- function(proj, output_file = "cell_metadata.tsv") {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  metadata <- ArchR::getCellColData(proj)
  utils::write.table(
    as.data.frame(metadata),
    file = output_file,
    sep = "\t",
    quote = FALSE,
    row.names = TRUE
  )

  message(sprintf("Metadata exported to: %s", output_file))
  return(invisible(metadata))
}
