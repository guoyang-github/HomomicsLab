# chromVAR Utility Functions
# ==========================
#
# Helper and utility functions for chromVAR analysis

#' Install chromVAR and dependencies
#'
#' Install chromVAR and required Bioconductor packages
#'
#' @param install_suggests Also install suggested packages (default: FALSE)
#' @export
install_chromvar_deps <- function(install_suggests = FALSE) {
  if (!requireNamespace("BiocManager", quietly = TRUE)) {
    install.packages("BiocManager")
  }

  # Core dependencies
  core_packages <- c(
    "chromVAR",
    "SummarizedExperiment",
    "GenomicRanges",
    "IRanges",
    "Matrix",
    "BiocParallel",
    "motifmatchr",
    "BSgenome",
    "JASPAR2020"
  )

  message("Installing core chromVAR dependencies...")
  BiocManager::install(core_packages, ask = FALSE)

  if (install_suggests) {
    suggests <- c(
      "ggplot2",
      "pheatmap",
      "reshape2",
      "cowplot",
      "plotly",
      "BSgenome.Hsapiens.UCSC.hg19",
      "BSgenome.Hsapiens.UCSC.hg38",
      "BSgenome.Mmusculus.UCSC.mm10"
    )
    message("Installing suggested packages...")
    BiocManager::install(suggests, ask = FALSE)
  }

  message("Installation complete!")
}

#' Load JASPAR motifs for chromVAR
#'
#' Load motif PWMs from JASPAR database
#'
#' @param species Species code (default: 9606 for human)
#' @param collection Collection to use (default: "CORE")
#' @param matrix_type Matrix type: "PWM" or "ICM" (default: "PWM")
#' @return PWMatrixList object
#' @export
load_jaspar_motifs <- function(species = 9606,
                               collection = "CORE",
                               matrix_type = "PWM") {
  if (!requireNamespace("TFBSTools", quietly = TRUE)) {
    stop("TFBSTools package required")
  }

  # Try to load JASPAR2020 first, then fall back to JASPAR2018
  jaspar_pkg <- NULL
  if (requireNamespace("JASPAR2020", quietly = TRUE)) {
    jaspar_pkg <- JASPAR2020::JASPAR2020
  } else if (requireNamespace("JASPAR2018", quietly = TRUE)) {
    jaspar_pkg <- JASPAR2018::JASPAR2018
    message("Using JASPAR2018 (JASPAR2020 not available)")
  } else {
    stop("JASPAR database not found. Install JASPAR2020 or JASPAR2018")
  }

  opts <- list()
  opts["species"] <- species
  opts["collection"] <- collection
  opts["matrixtype"] <- matrix_type

  message(sprintf("Loading JASPAR motifs for species %d...", species))
  motifs <- TFBSTools::getMatrixSet(jaspar_pkg, opts)

  # Ensure names are properly set
  if (!isTRUE(all.equal(TFBSTools::name(motifs), names(motifs)))) {
    names(motifs) <- paste(names(motifs), TFBSTools::name(motifs), sep = "_")
  }

  message(sprintf("Loaded %d motifs", length(motifs)))
  return(motifs)
}

#' Load peaks from BED file
#'
#' Read peak coordinates from a BED file
#'
#' @param bed_file Path to BED file
#' @param sort_peaks Whether to sort peaks (default: TRUE)
#' @return GRanges object
#' @export
load_peaks_from_bed <- function(bed_file, sort_peaks = TRUE) {
  if (!requireNamespace("GenomicRanges", quietly = TRUE)) {
    stop("GenomicRanges package required")
  }

  if (!file.exists(bed_file)) {
    stop(sprintf("BED file not found: %s", bed_file))
  }

  message(sprintf("Loading peaks from %s...", bed_file))

  # Read BED file
  bed <- utils::read.delim(
    bed_file,
    header = FALSE,
    sep = "\t",
    stringsAsFactors = FALSE
  )[, 1:3]

  colnames(bed) <- c("chr", "start", "end")

  # Convert to GRanges (BED is 0-based, GRanges is 1-based)
  bed$start <- bed$start + 1

  peaks <- GenomicRanges::makeGRangesFromDataFrame(
    bed,
    seqnames.field = "chr",
    start.field = "start",
    end.field = "end"
  )

  if (sort_peaks) {
    peaks <- sort(GenomeInfoDb::sortSeqlevels(peaks))
  }

  message(sprintf("Loaded %d peaks", length(peaks)))
  return(peaks)
}

#' Load count matrix
#'
#' Load peak x cell count matrix from various formats
#'
#' @param file Path to count matrix file
#' @param format Format: "mtx", "tsv", "csv" (default: auto-detect)
#' @return Sparse matrix (peaks x cells)
#' @export
load_count_matrix <- function(file, format = NULL) {
  if (is.null(format)) {
    format <- tools::file_ext(file)
  }

  format <- tolower(format)

  message(sprintf("Loading count matrix from %s...", file))

  if (format %in% c("mtx", "mm", "mmx")) {
    if (!requireNamespace("Matrix", quietly = TRUE)) {
      stop("Matrix package required for MTX format")
    }
    counts <- Matrix::readMM(file)
    counts <- as(counts, "sparseMatrix")
  } else if (format %in% c("tsv", "txt")) {
    counts <- utils::read.delim(file, row.names = 1, check.names = FALSE)
    counts <- Matrix::Matrix(as.matrix(counts), sparse = TRUE)
  } else if (format == "csv") {
    counts <- utils::read.csv(file, row.names = 1, check.names = FALSE)
    counts <- Matrix::Matrix(as.matrix(counts), sparse = TRUE)
  } else if (format %in% c("rds", "rdata", "rda")) {
    counts <- readRDS(file)
    if (!inherits(counts, "Matrix")) {
      counts <- Matrix::Matrix(as.matrix(counts), sparse = TRUE)
    }
  } else {
    stop(sprintf("Unknown format: %s", format))
  }

  message(sprintf("Loaded matrix: %d peaks x %d cells", nrow(counts), ncol(counts)))
  return(counts)
}

#' Get genome BSgenome object
#'
#' Get BSgenome object by name
#'
#' @param genome Genome name: "hg19", "hg38", "mm10", etc.
#' @return BSgenome object
#' @export
get_genome <- function(genome) {
  if (!requireNamespace("BSgenome", quietly = TRUE)) {
    stop("BSgenome package required")
  }

  genome_map <- list(
    "hg19" = "BSgenome.Hsapiens.UCSC.hg19",
    "hg38" = "BSgenome.Hsapiens.UCSC.hg38",
    "mm10" = "BSgenome.Mmusculus.UCSC.mm10",
    "mm9" = "BSgenome.Mmusculus.UCSC.mm9"
  )

  if (genome %in% names(genome_map)) {
    pkg <- genome_map[[genome]]
    if (!requireNamespace(pkg, quietly = TRUE)) {
      stop(sprintf("Package %s not installed. Run: BiocManager::install('%s')", pkg, pkg))
    }
    return(getExportedValue(pkg, genome))
  }

  # Try to load directly
  tryCatch({
    return(BSgenome::getBSgenome(genome))
  }, error = function(e) {
    stop(sprintf("Could not load genome: %s", genome))
  })
}

#' Subset chromVAR object by cells
#'
#' Subset a RangedSummarizedExperiment to specific cells
#'
#' @param rse RangedSummarizedExperiment
#' @param cells Vector of cell names or indices to keep
#' @return Subsetted RangedSummarizedExperiment
#' @export
subset_cells <- function(rse, cells) {
  if (is.character(cells)) {
    cells <- match(cells, colnames(rse))
    cells <- cells[!is.na(cells)]
  }

  if (length(cells) == 0) {
    stop("No valid cells found")
  }

  return(rse[, cells])
}

#' Merge multiple chromVAR results
#'
#' Combine chromVAR results from multiple samples
#'
#' @param results_list List of results from run_chromvar
#' @param sample_names Names for each sample
#' @return Merged results list
#' @export
merge_chromvar_results <- function(results_list, sample_names = NULL) {
  if (is.null(sample_names)) {
    sample_names <- names(results_list)
    if (is.null(sample_names)) {
      sample_names <- paste0("sample_", seq_along(results_list))
    }
  }

  # Extract and combine variability
  all_var <- lapply(seq_along(results_list), function(i) {
    var <- results_list[[i]]$variability
    var$sample <- sample_names[i]
    return(var)
  })

  combined_var <- do.call(rbind, all_var)

  list(
    variability = combined_var,
    n_samples = length(results_list),
    sample_names = sample_names
  )
}

#' Annotate motifs with TF information
#'
#' Add transcription factor information to motif names
#'
#' @param motif_names Character vector of motif names
#' @return Data frame with motif annotations
#' @export
annotate_motifs <- function(motif_names) {
  # Parse JASPAR-style names (e.g., "MA0004.1_Arnt")
  annotations <- data.frame(
    motif_id = motif_names,
    stringsAsFactors = FALSE
  )

  # Try to extract TF name
  tf_names <- gsub("^[A-Za-z0-9\\.]+_", "", motif_names)
  tf_names <- gsub("\\(.*\\)", "", tf_names)  # Remove parentheses

  annotations$tf_name <- tf_names
  annotations$tf_family <- NA  # Would need additional database lookup

  return(annotations)
}

#' Compute correlation between motif deviations and gene expression
#'
#' Correlate TF motif deviations with their corresponding gene expression
#'
#' @param dev chromVARDeviations object
#' @param gene_expression Gene expression matrix (genes x cells)
#' @param tf_gene_map Data frame mapping motifs to gene symbols
#' @return Data frame with correlation results
#' @export
correlate_deviations_with_expression <- function(dev,
                                                 gene_expression,
                                                 tf_gene_map = NULL) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }

  z_scores <- chromVAR::deviationScores(dev)

  # Get motif names
  motif_names <- if (!is.null(SummarizedExperiment::rowData(dev)$name)) {
    SummarizedExperiment::rowData(dev)$name
  } else {
    rownames(dev)
  }

  # If no mapping provided, try to match by name
  if (is.null(tf_gene_map)) {
    # Extract potential gene symbols from motif names
    potential_genes <- gsub("^[A-Za-z0-9\\.]+_", "", motif_names)
    potential_genes <- gsub("\\(.*\\)", "", potential_genes)
    potential_genes <- gsub("::.*", "", potential_genes)  # Remove heterodimers

    tf_gene_map <- data.frame(
      motif = motif_names,
      gene = potential_genes,
      stringsAsFactors = FALSE
    )
  }

  # Compute correlations
  results <- list()
  for (i in seq_len(nrow(tf_gene_map))) {
    motif <- tf_gene_map$motif[i]
    gene <- tf_gene_map$gene[i]

    motif_idx <- match(motif, motif_names)
    if (is.na(motif_idx)) next

    if (gene %in% rownames(gene_expression)) {
      corr <- cor(z_scores[motif_idx, ],
                  gene_expression[gene, ],
                  use = "pairwise.complete.obs")

      results[[length(results) + 1]] <- data.frame(
        motif = motif,
        gene = gene,
        correlation = corr,
        stringsAsFactors = FALSE
      )
    }
  }

  if (length(results) == 0) {
    warning("No matching gene-motif pairs found")
    return(NULL)
  }

  do.call(rbind, results)
}

#' Get chromVAR version information
#'
#' Get version info for chromVAR and dependencies
#'
#' @return Data frame with version information
#' @export
get_chromvar_version_info <- function() {
  packages <- c("chromVAR", "SummarizedExperiment", "GenomicRanges",
                "IRanges", "Matrix", "BiocParallel", "motifmatchr")

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

#' Print chromVAR parameters
#'
#' Print recommended parameters based on data characteristics
#'
#' @param n_cells Number of cells
#' @param n_peaks Number of peaks
#' @return List of recommended parameters
#' @export
recommend_chromvar_params <- function(n_cells, n_peaks) {
  # Recommend background iterations
  n_bg <- min(100, max(50, n_cells / 10))

  # Recommend cores
  n_cores <- min(4, parallel::detectCores() %||% 1)

  # Recommend filtering
  min_fragments <- if (n_peaks > 100000) 5 else 1

  params <- list(
    n_bg_iterations = round(n_bg),
    n_cores = n_cores,
    min_fragments_per_peak = min_fragments,
    filter_peaks = n_peaks > 50000,
    message = sprintf(
"chromVAR Parameter Recommendations:
  - Background iterations: %d (based on %d cells)
  - Parallel cores: %d
  - Min fragments per peak: %d
  - Filter peaks: %s
  - Notes: %s",
      round(n_bg),
      n_cells,
      n_cores,
      min_fragments,
      ifelse(n_peaks > 50000, "YES (high peak count)", "optional"),
      ifelse(n_peaks > 100000,
             "Large peak set - consider more stringent filtering",
             "Standard parameters should work well")
    )
  )

  cat(params$message, "\n")
  return(params)
}

# Helper: null default operator
`%||%` <- function(x, y) if (is.null(x)) y else x
