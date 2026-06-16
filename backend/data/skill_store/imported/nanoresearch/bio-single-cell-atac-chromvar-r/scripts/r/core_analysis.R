# chromVAR Core Analysis Functions
# =================================
#
# Main analysis functions for chromatin accessibility variation analysis using chromVAR

#' Check chromVAR dependencies
#'
#' Check if required packages are installed
#'
#' @return Logical indicating if all dependencies are available
#' @export
check_chromvar_dependencies <- function() {
  required <- c("chromVAR", "SummarizedExperiment", "motifmatchr", "Matrix",
                "GenomicRanges", "IRanges", "BiocParallel", "BSgenome")
  missing <- required[!sapply(required, requireNamespace, quietly = TRUE)]

  if (length(missing) > 0) {
    warning(paste("Missing packages:", paste(missing, collapse = ", ")))
    return(FALSE)
  }
  return(TRUE)
}

#' Create chromVAR input from count matrix and peaks
#'
#' Create a RangedSummarizedExperiment for chromVAR analysis
#'
#' @param counts Count matrix (peaks x cells)
#' @param peaks GRanges object with peak coordinates or data frame with chr/start/end
#' @param cell_metadata Data frame with cell metadata (optional)
#' @return RangedSummarizedExperiment
#' @export
create_chromvar_object <- function(counts, peaks, cell_metadata = NULL) {
  if (!requireNamespace("SummarizedExperiment", quietly = TRUE)) {
    stop("SummarizedExperiment package required")
  }
  if (!requireNamespace("GenomicRanges", quietly = TRUE)) {
    stop("GenomicRanges package required")
  }

  # Convert peaks to GRanges if needed
  if (is.data.frame(peaks)) {
    if (!all(c("chr", "start", "end") %in% colnames(peaks))) {
      stop("peaks data frame must have chr, start, end columns")
    }
    peaks <- GenomicRanges::makeGRangesFromDataFrame(
      peaks,
      seqnames.field = "chr",
      start.field = "start",
      end.field = "end"
    )
  }

  if (!inherits(peaks, "GRanges")) {
    stop("peaks must be a GRanges object or data frame with chr/start/end columns")
  }

  # Ensure counts is a Matrix
  if (!inherits(counts, "Matrix")) {
    counts <- Matrix::Matrix(counts, sparse = TRUE)
  }

  # Check dimensions
  if (nrow(counts) != length(peaks)) {
    stop(sprintf("Dimension mismatch: counts has %d rows but peaks has %d elements",
                 nrow(counts), length(peaks)))
  }

  # Create colData
  if (is.null(cell_metadata)) {
    cell_metadata <- S4Vectors::DataFrame(
      cell_id = colnames(counts) %||% paste0("cell_", seq_len(ncol(counts)))
    )
  } else {
    cell_metadata <- S4Vectors::DataFrame(cell_metadata)
  }

  # Create RangedSummarizedExperiment
  rse <- SummarizedExperiment::SummarizedExperiment(
    assays = list(counts = counts),
    rowRanges = peaks,
    colData = cell_metadata
  )

  return(rse)
}

#' Validate chromVAR input
#'
#' Validate input data before running chromVAR analysis
#'
#' @param rse RangedSummarizedExperiment object
#' @return List with validation results
#' @export
validate_chromvar_input <- function(rse) {
  errors <- character()
  warnings <- character()
  stats <- list()

  # Check class
  if (!inherits(rse, "SummarizedExperiment")) {
    errors <- c(errors, "Input must be a SummarizedExperiment or RangedSummarizedExperiment")
    return(list(valid = FALSE, errors = errors, warnings = warnings, stats = stats))
  }

  # Check for counts assay
  if (!"counts" %in% SummarizedExperiment::assayNames(rse)) {
    errors <- c(errors, "Input must have a 'counts' assay")
  }

  # Get counts
  counts <- SummarizedExperiment::assay(rse, "counts")

  # Check dimensions
  stats$n_peaks <- nrow(rse)
  stats$n_cells <- ncol(rse)

  if (stats$n_peaks < 1000) {
    warnings <- c(warnings, paste("Low peak count:", stats$n_peaks, "- recommend at least 1000 peaks"))
  }

  if (stats$n_cells < 50) {
    warnings <- c(warnings, paste("Low cell count:", stats$n_cells, "- recommend at least 50 cells"))
  }

  # Check for zero peaks
  zero_peaks <- sum(Matrix::rowSums(counts) == 0)
  if (zero_peaks > 0) {
    warnings <- c(warnings, paste(zero_peaks, "peaks with zero counts will be filtered"))
  }

  # Check for rowRanges (needed for GC bias)
  if (!inherits(rse, "RangedSummarizedExperiment")) {
    if (is.null(SummarizedExperiment::rowRanges(rse))) {
      warnings <- c(warnings, "No rowRanges found - GC bias correction will require peaks parameter")
    }
  }

  # Check peak overlaps
  if (inherits(rse, "RangedSummarizedExperiment") || !is.null(SummarizedExperiment::rowRanges(rse))) {
    peaks <- SummarizedExperiment::rowRanges(rse)
    if (!GenomicRanges::isDisjoint(peaks)) {
      warnings <- c(warnings, "Peaks have overlaps - consider using filterPeaks with non_overlapping=TRUE")
    }
  }

  list(
    valid = length(errors) == 0,
    errors = errors,
    warnings = warnings,
    stats = stats
  )
}

#' Filter peaks for chromVAR analysis
#'
#' Filter peaks based on accessibility and remove overlaps
#'
#' @param rse RangedSummarizedExperiment object
#' @param min_fragments_per_peak Minimum fragments per peak across all samples (default: 1)
#' @param non_overlapping Remove overlapping peaks (default: TRUE)
#' @param ix_return Return indices instead of filtered object (default: FALSE)
#' @return Filtered RangedSummarizedExperiment or indices
#' @export
filter_peaks_chromvar <- function(rse,
                                   min_fragments_per_peak = 1,
                                   non_overlapping = TRUE,
                                   ix_return = FALSE) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }

  # Validate input
  validation <- validate_chromvar_input(rse)
  if (!validation$valid) {
    stop(paste("Validation errors:", paste(validation$errors, collapse = "\n")))
  }

  message(sprintf("Filtering peaks: min_fragments=%d, non_overlapping=%s",
                  min_fragments_per_peak, non_overlapping))

  # Use chromVAR's filterPeaks function
  filtered <- chromVAR::filterPeaks(
    rse,
    min_fragments_per_peak = min_fragments_per_peak,
    non_overlapping = non_overlapping,
    ix_return = ix_return
  )

  if (!ix_return) {
    message(sprintf("Filtered from %d to %d peaks", nrow(rse), nrow(filtered)))
  }

  return(filtered)
}

#' Add GC bias to chromVAR object
#'
#' Compute GC content for each peak and add to rowData
#'
#' @param rse RangedSummarizedExperiment object
#' @param genome BSgenome object or string (e.g., "BSgenome.Hsapiens.UCSC.hg38")
#' @return RangedSummarizedExperiment with GC bias added
#' @export
add_gc_bias <- function(rse, genome) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }

  # Handle genome string
  if (is.character(genome)) {
    if (!requireNamespace("BSgenome", quietly = TRUE)) {
      stop("BSgenome package required for genome string input")
    }
    genome <- BSgenome::getBSgenome(genome)
  }

  message("Computing GC bias...")
  rse <- chromVAR::addGCBias(rse, genome = genome)

  # Report GC bias stats
  gc <- SummarizedExperiment::rowData(rse)$bias
  message(sprintf("GC bias: mean=%.3f, range=[%.3f, %.3f]",
                  mean(gc, na.rm = TRUE),
                  min(gc, na.rm = TRUE),
                  max(gc, na.rm = TRUE)))

  return(rse)
}

#' Get background peaks for chromVAR
#'
#' Get background peaks for each peak based on GC content and accessibility
#'
#' @param rse RangedSummarizedExperiment object (with GC bias added)
#' @param niterations Number of background peaks to sample (default: 50)
#' @param w Parameter controlling similarity of background peaks (default: 0.1)
#' @param bs Bin size parameter (default: 50)
#' @return Matrix with background peak indices
#' @export
get_background_peaks <- function(rse, niterations = 50, w = 0.1, bs = 50) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }

  # Check for bias column
  if (is.null(SummarizedExperiment::rowData(rse)$bias)) {
    stop("GC bias not found. Run add_gc_bias() first.")
  }

  message(sprintf("Computing background peaks: niterations=%d, w=%.2f, bs=%d",
                  niterations, w, bs))

  bg <- chromVAR::getBackgroundPeaks(
    rse,
    niterations = niterations,
    w = w,
    bs = bs
  )

  message(sprintf("Background peaks matrix: %d peaks x %d iterations", nrow(bg), ncol(bg)))
  return(bg)
}

#' Match motifs to peaks
#'
#' Find motif matches in peak sequences
#'
#' @param rse RangedSummarizedExperiment object
#' @param motifs Motif PWM set (PWMatrixList) or database name ("jaspar2018", "jaspar2020")
#' @param genome BSgenome object or string
#' @return Motif matches object
#' @export
match_motifs_chromvar <- function(rse, motifs = "jaspar2018", genome = NULL) {
  if (!requireNamespace("motifmatchr", quietly = TRUE)) {
    stop("motifmatchr package required")
  }

  # Handle genome
  if (is.character(genome)) {
    if (!requireNamespace("BSgenome", quietly = TRUE)) {
      stop("BSgenome package required for genome string input")
    }
    genome <- BSgenome::getBSgenome(genome)
  }

  # Handle motif database names
  if (is.character(motifs) && length(motifs) == 1) {
    if (motifs %in% c("jaspar2018", "jaspar2020", "JASPAR2018", "JASPAR2020")) {
      message(sprintf("Using %s motif database", motifs))
      # Try to load from chromVAR compatible sources
      if (requireNamespace("JASPAR2020", quietly = TRUE)) {
        motifs <- JASPAR2020::JASPAR2020
      } else if (requireNamespace("JASPAR2018", quietly = TRUE)) {
        motifs <- JASPAR2018::JASPAR2018
      } else {
        stop("JASPAR database not found. Install JASPAR2020 or provide motif PWMs")
      }
    }
  }

  message("Matching motifs to peaks...")
  motif_ix <- motifmatchr::matchMotifs(
    pwms = motifs,
    subject = rse,
    genome = genome
  )

  message(sprintf("Matched %d motifs to %d peaks",
                  ncol(motif_ix), nrow(motif_ix)))
  return(motif_ix)
}

#' Compute deviations with chromVAR
#'
#' Main function to compute chromatin accessibility deviations
#'
#' @param rse RangedSummarizedExperiment object (filtered, with GC bias)
#' @param annotations Motif matches or other annotation (from match_motifs_chromvar)
#' @param background_peaks Background peaks matrix (optional, computed if NULL)
#' @param expectation Expectation vector (optional, computed if NULL)
#' @param validate Validate input before running (default: TRUE)
#' @return chromVARDeviations object
#' @export
compute_deviations_chromvar <- function(rse,
                                         annotations,
                                         background_peaks = NULL,
                                         expectation = NULL,
                                         validate = TRUE) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }

  # Validate input
  if (validate) {
    validation <- validate_chromvar_input(rse)
    if (!validation$valid) {
      stop(paste("Validation errors:", paste(validation$errors, collapse = "\n")))
    }
    message("Input validation passed")
  }

  # Compute background peaks if not provided
  if (is.null(background_peaks)) {
    background_peaks <- get_background_peaks(rse)
  }

  # Compute expectation if not provided
  if (is.null(expectation)) {
    expectation <- chromVAR::computeExpectations(rse)
  }

  message("Computing deviations...")
  dev <- chromVAR::computeDeviations(
    object = rse,
    annotations = annotations,
    background_peaks = background_peaks,
    expectation = expectation
  )

  message(sprintf("Computed deviations for %d annotations across %d cells",
                  nrow(dev), ncol(dev)))
  return(dev)
}

#' Compute variability with chromVAR
#'
#' Compute per-motif variability across cells
#'
#' @param dev chromVARDeviations object (output from compute_deviations_chromvar)
#' @param bootstrap_error Compute bootstrap confidence intervals (default: TRUE)
#' @param bootstrap_samples Number of bootstrap samples (default: 1000)
#' @return Data frame with variability statistics
#' @export
compute_variability_chromvar <- function(dev,
                                          bootstrap_error = TRUE,
                                          bootstrap_samples = 1000) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }

  message(sprintf("Computing variability (bootstrap=%s)...", bootstrap_error))

  var <- chromVAR::computeVariability(
    dev,
    bootstrap_error = bootstrap_error,
    bootstrap_samples = bootstrap_samples
  )

  message(sprintf("Computed variability for %d motifs", nrow(var)))
  return(var)
}

#' Run complete chromVAR workflow
#'
#' Run the complete chromVAR analysis pipeline
#'
#' @param rse RangedSummarizedExperiment object with counts and rowRanges
#' @param motifs Motif database or PWM set (default: "jaspar2018")
#' @param genome BSgenome object or string (e.g., "BSgenome.Hsapiens.UCSC.hg38")
#' @param filter_peaks Whether to filter peaks (default: TRUE)
#' @param min_fragments_per_peak Minimum fragments per peak (default: 1)
#' @param n_bg_iterations Background peak iterations (default: 50)
#' @param n_cores Number of parallel cores (default: 1)
#' @return List with chromVAR results
#' @export
run_chromvar <- function(rse,
                          motifs = "jaspar2018",
                          genome,
                          filter_peaks = TRUE,
                          min_fragments_per_peak = 1,
                          n_bg_iterations = 50,
                          n_cores = 1) {

  # Set up parallel processing
  if (n_cores > 1) {
    if (!requireNamespace("BiocParallel", quietly = TRUE)) {
      warning("BiocParallel not available, running serially")
    } else {
      BiocParallel::register(BiocParallel::MulticoreParam(n_cores))
      message(sprintf("Using %d cores", n_cores))
    }
  }

  # Validate input
  validation <- validate_chromvar_input(rse)
  if (!validation$valid) {
    stop(paste("Validation errors:", paste(validation$errors, collapse = "\n")))
  }
  message(sprintf("Input: %d peaks x %d cells", validation$stats$n_peaks, validation$stats$n_cells))

  # Step 1: Filter peaks
  if (filter_peaks) {
    rse <- filter_peaks_chromvar(rse, min_fragments_per_peak = min_fragments_per_peak)
  }

  # Step 2: Add GC bias
  rse <- add_gc_bias(rse, genome = genome)

  # Step 3: Match motifs
  motif_ix <- match_motifs_chromvar(rse, motifs = motifs, genome = genome)

  # Step 4: Compute deviations
  dev <- compute_deviations_chromvar(rse, annotations = motif_ix)

  # Step 5: Compute variability
  var <- compute_variability_chromvar(dev)

  # Return results
  list(
    rse = rse,
    motif_matches = motif_ix,
    deviations = dev,
    variability = var
  )
}

#' Extract top variable motifs
#'
#' Get the most variable motifs from chromVAR results
#'
#' @param var Variability data frame from compute_variability_chromvar
#' @param n Number of top motifs to return (default: 10)
#' @return Data frame with top variable motifs
#' @export
get_top_variable_motifs <- function(var, n = 10) {
  top <- var[order(var$variability, decreasing = TRUE), ][seq_len(min(n, nrow(var))), ]
  return(top)
}

#' Extract deviation scores for specific motifs
#'
#' Get deviation scores (z-scores) for specific motifs
#'
#' @param dev chromVARDeviations object
#' @param motif_names Character vector of motif names
#' @return Matrix of deviation scores (motifs x cells)
#' @export
get_motif_deviation_scores <- function(dev, motif_names = NULL) {
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }

  # Get z-scores (bias-corrected deviations)
  z_scores <- chromVAR::deviationScores(dev)

  if (!is.null(motif_names)) {
    # Find matching motif names
    available_names <- rownames(dev)
    if (!is.null(SummarizedExperiment::rowData(dev)$name)) {
      available_names <- SummarizedExperiment::rowData(dev)$name
    }

    matched <- match(motif_names, available_names)
    matched <- matched[!is.na(matched)]

    if (length(matched) == 0) {
      warning("No matching motifs found")
      return(NULL)
    }

    z_scores <- z_scores[matched, , drop = FALSE]
  }

  return(z_scores)
}

#' Summarize chromVAR results
#'
#' Generate summary statistics from chromVAR analysis
#'
#' @param results Results list from run_chromvar
#' @return List with summary statistics
#' @export
summarize_chromvar_results <- function(results) {
  if (!all(c("rse", "deviations", "variability") %in% names(results))) {
    stop("Invalid results object - must contain rse, deviations, and variability")
  }

  var <- results$variability

  summary <- list(
    n_peaks = nrow(results$rse),
    n_cells = ncol(results$rse),
    n_motifs = nrow(results$deviations),
    top_motif = var$name[which.max(var$variability)],
    max_variability = max(var$variability, na.rm = TRUE),
    median_variability = median(var$variability, na.rm = TRUE),
    significant_motifs = sum(var$p_value_adj < 0.05, na.rm = TRUE)
  )

  return(summary)
}

#' Export chromVAR results
#'
#' Export deviations and variability to files
#'
#' @param results Results list from run_chromvar
#' @param output_dir Output directory
#' @param prefix File prefix
#' @export
export_chromvar_results <- function(results,
                                     output_dir = "./chromvar_output",
                                     prefix = "sample") {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Export variability
  var_file <- file.path(output_dir, paste0(prefix, "_variability.txt"))
  write.table(
    results$variability,
    var_file,
    sep = "\t",
    row.names = FALSE,
    quote = FALSE
  )
  message(sprintf("Exported: %s", var_file))

  # Export deviations (z-scores)
  if (!requireNamespace("chromVAR", quietly = TRUE)) {
    stop("chromVAR package required")
  }
  z_scores <- chromVAR::deviationScores(results$deviations)
  dev_file <- file.path(output_dir, paste0(prefix, "_deviation_scores.txt"))
  write.table(
    as.data.frame(t(z_scores)),
    dev_file,
    sep = "\t",
    row.names = TRUE,
    quote = FALSE
  )
  message(sprintf("Exported: %s", dev_file))

  # Export summary
  summary <- summarize_chromvar_results(results)
  summary_file <- file.path(output_dir, paste0(prefix, "_summary.txt"))
  sink(summary_file)
  cat("chromVAR Analysis Summary\n")
  cat("=========================\n\n")
  cat(sprintf("Peaks: %d\n", summary$n_peaks))
  cat(sprintf("Cells: %d\n", summary$n_cells))
  cat(sprintf("Motifs: %d\n", summary$n_motifs))
  cat(sprintf("\nTop variable motif: %s (variability=%.3f)\n",
              summary$top_motif, summary$max_variability))
  cat(sprintf("Significant motifs (FDR<0.05): %d\n", summary$significant_motifs))
  sink()
  message(sprintf("Exported: %s", summary_file))
}

#' Create chromVAR report
#'
#' Generate a text summary report
#'
#' @param results Results list from run_chromvar
#' @param output_file Output file path (optional)
#' @return Report text
#' @export
create_chromvar_report <- function(results, output_file = NULL) {
  summary <- summarize_chromvar_results(results)
  var <- results$variability

  # Get top 10 motifs
  top_motifs <- head(var[order(var$variability, decreasing = TRUE), ], 10)

  report <- sprintf("
chromVAR Analysis Report
========================
Date: %s

Sample Summary
--------------
Peaks analyzed: %d
Cells analyzed: %d
Motifs tested: %d

Variability Summary
-------------------
Most variable motif: %s
Maximum variability: %.3f
Median variability: %.3f
Significant motifs (FDR<0.05): %d

Top 10 Variable Motifs
----------------------
%s

Notes
-----
- Variability measures the standard deviation of z-scores across cells
- Higher variability indicates cell-type or condition-specific TF activity
- Deviations > 0 indicate higher accessibility than expected
- Deviations < 0 indicate lower accessibility than expected
",
    format(Sys.time(), "%Y-%m-%d %H:%M"),
    summary$n_peaks,
    summary$n_cells,
    summary$n_motifs,
    summary$top_motif,
    summary$max_variability,
    summary$median_variability,
    summary$significant_motifs,
    paste(capture.output(print(top_motifs[, c("name", "variability", "p_value_adj")])), collapse = "\n")
  )

  if (!is.null(output_file)) {
    writeLines(report, output_file)
  }

  return(report)
}

# Helper: null default operator
`%||%` <- function(x, y) if (is.null(x)) y else x
