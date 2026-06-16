# Signac Core Analysis Functions
# ==============================
#
# Main analysis functions for single-cell ATAC-seq analysis using Signac

#' Check Signac dependencies
#'
#' Check if required packages are installed
#'
#' @return Logical indicating if all dependencies are available
#' @export
check_signac_dependencies <- function() {
  required <- c("Signac", "Seurat", "GenomeInfoDb", "BiocGenerics",
                "S4Vectors", "IRanges", "GenomicRanges")
  missing <- required[!sapply(required, requireNamespace, quietly = TRUE)]

  if (length(missing) > 0) {
    warning(paste("Missing packages:", paste(missing, collapse = ", ")))
    return(FALSE)
  }
  return(TRUE)
}

#' Helper: Check Signac version and dispatch to correct assay constructor
#' @noRd
.create_assay_compat <- function(counts, sep, genome, fragments, min.cells, min.features) {
  if (utils::packageVersion("Signac") >= package_version("1.9999")) {
    message("Using Signac v2 CreateGRangesAssay...")
    return(Signac::CreateGRangesAssay(
      counts = counts, sep = sep, genome = genome,
      fragments = fragments, min.cells = min.cells, min.features = min.features
    ))
  } else {
    message("Using Signac v1 CreateChromatinAssay...")
    return(Signac::CreateChromatinAssay(
      counts = counts, sep = sep, genome = genome,
      fragments = fragments, min.cells = min.cells, min.features = min.features
    ))
  }
}

#' Create Seurat object from 10x output
#'
#' Create a Seurat object with ChromatinAssay/GRangesAssay from 10x Genomics output
#'
#' @param counts_file Path to counts file (HDF5 or MatrixMarket)
#' @param fragments_file Path to fragments.tsv.gz file
#' @param metadata_file Path to metadata CSV file (optional)
#' @param sep Peak name separator (default: c(":", "-"))
#' @param genome Genome assembly: "hg38", "hg19", "mm10" (default: "hg38")
#' @param min_cells Minimum cells per feature (default: 0)
#' @param min_features Minimum features per cell (default: 0)
#' @return Seurat object with ChromatinAssay
#' @export
create_signac_object <- function(
    counts_file,
    fragments_file,
    metadata_file = NULL,
    sep = c(":", "-"),
    genome = "hg38",
    min_cells = 0,
    min_features = 0
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Validate files
  if (!file.exists(counts_file)) {
    stop(sprintf("Counts file not found: %s", counts_file))
  }
  if (!file.exists(fragments_file)) {
    stop(sprintf("Fragments file not found: %s", fragments_file))
  }

  # Load counts
  message(sprintf("Loading counts from: %s", counts_file))
  if (grepl("\\.h5$", counts_file)) {
    counts <- Seurat::Read10X_h5(counts_file)
  } else {
    counts <- Seurat::Read10X(counts_file)
  }

  # Load metadata if provided
  metadata <- NULL
  if (!is.null(metadata_file)) {
    if (!file.exists(metadata_file)) {
      stop(sprintf("Metadata file not found: %s", metadata_file))
    }
    metadata <- utils::read.csv(metadata_file, header = TRUE, row.names = 1)
    message(sprintf("Loaded metadata: %d cells", nrow(metadata)))
  }

  # Create ChromatinAssay or GRangesAssay (Signac v2)
  chrom_assay <- .create_assay_compat(
    counts = counts, sep = sep, genome = genome,
    fragments = fragments_file, min.cells = min_cells, min.features = min_features
  )

  # Create Seurat object
  message("Creating Seurat object...")
  seurat_obj <- Seurat::CreateSeuratObject(
    counts = chrom_assay,
    assay = "peaks",
    meta.data = metadata
  )

  message(sprintf("Created object: %d cells x %d peaks", ncol(seurat_obj), nrow(seurat_obj)))
  return(seurat_obj)
}

#' Compute QC metrics
#'
#' Compute nucleosome signal and TSS enrichment (Signac v1) or ATACqc (Signac v2)
#'
#' @param seurat_obj Seurat object with ChromatinAssay
#' @param assay Name of assay (default: "peaks")
#' @param compute_nucleosome Compute nucleosome signal (default: TRUE)
#' @param compute_tss Compute TSS enrichment (default: TRUE)
#' @param tss_fast Use fast mode for TSS (default: TRUE)
#' @param n Number of fragments to sample for nucleosome signal (default: NULL)
#' @param verbose Print progress (default: TRUE)
#' @return Seurat object with QC metrics
#' @export
compute_qc_metrics <- function(
    seurat_obj,
    assay = "peaks",
    compute_nucleosome = TRUE,
    compute_tss = TRUE,
    tss_fast = TRUE,
    n = NULL,
    verbose = TRUE
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  # Compute QC metrics (version-aware)
  if (utils::packageVersion("Signac") >= package_version("1.9999")) {
    message("Computing ATAC QC metrics (Signac v2)...")
    seurat_obj <- Signac::ATACqc(
      object = seurat_obj,
      assay = assay,
      verbose = verbose
    )
  } else {
    # Compute nucleosome signal
    if (compute_nucleosome) {
      message("Computing nucleosome signal...")
      seurat_obj <- Signac::NucleosomeSignal(
        object = seurat_obj,
        assay = assay,
        n = n %||% (ncol(seurat_obj) * 5e3),
        verbose = verbose
      )
    }

    # Compute TSS enrichment
    if (compute_tss) {
      message("Computing TSS enrichment...")
      seurat_obj <- Signac::TSSEnrichment(
        object = seurat_obj,
        assay = assay,
        fast = tss_fast,
        verbose = verbose
      )
    }
  }

  # Add percent reads in peaks
  if ("peak_region_fragments" %in% colnames(seurat_obj@meta.data)) {
    seurat_obj$pct_reads_in_peaks <- seurat_obj$peak_region_fragments /
                                       seurat_obj$passed_filters * 100
  }

  message("QC metrics computed successfully")
  return(seurat_obj)
}

#' Add blacklist ratio
#'
#' Compute fraction of reads in blacklist regions
#'
#' @param seurat_obj Seurat object
#' @param blacklist Blacklist regions (GRanges or string)
#' @param assay Name of assay (default: "peaks")
#' @return Seurat object with blacklist_ratio
#' @export
add_blacklist_ratio <- function(
    seurat_obj,
    blacklist = NULL,
    assay = "peaks"
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  # Auto-detect blacklist if not provided
  if (is.null(blacklist)) {
    if (utils::packageVersion("Signac") >= package_version("1.9999")) {
      # Signac v2: blacklist data objects are accessed directly (e.g., blacklist_hg38)
      genome <- seurat_obj@assays[[assay]]@seqinfo@genome[1]
      if (!is.na(genome)) {
        blacklist_obj_name <- paste0("blacklist_", genome)
        blacklist <- tryCatch(
          get(blacklist_obj_name, envir = asNamespace("Signac")),
          error = function(e) {
            warning(sprintf("No built-in blacklist for genome '%s'. Please provide blacklist path.", genome))
            NULL
          }
        )
        if (!is.null(blacklist)) {
          message(sprintf("Using built-in blacklist for %s", genome))
        }
      }
    } else {
      # Signac v1: legacy blacklist data objects
      genome <- seurat_obj@assays[[assay]]@seqinfo@genome[1]
      if (!is.na(genome)) {
        blacklist <- sprintf("%s-blacklist.v2.bed", genome)
        message(sprintf("Using default blacklist: %s", blacklist))
      }
    }
  }

  seurat_obj$blacklist_ratio <- Signac::FractionCountsInRegion(
    object = seurat_obj,
    assay = assay,
    regions = blacklist
  )

  return(seurat_obj)
}

#' Filter cells by QC metrics
#'
#' Filter cells based on QC thresholds
#'
#' @param seurat_obj Seurat object
#' @param min_counts Minimum counts per cell (default: 1000)
#' @param max_counts Maximum counts per cell (default: NULL)
#' @param min_tss Minimum TSS enrichment (default: 2)
#' @param max_ns Maximum nucleosome signal (default: 4)
#' @param min_rip Minimum percent reads in peaks (default: 15)
#' @param max_bl Maximum blacklist ratio (default: 0.05)
#' @param return_filtered Return filtered object (default: TRUE)
#' @return Filtered Seurat object or logical vector
#' @export
filter_cells_signac <- function(
    seurat_obj,
    min_counts = 1000,
    max_counts = NULL,
    min_tss = 2,
    max_ns = 4,
    min_rip = 15,
    max_bl = 0.05,
    return_filtered = TRUE
) {
  # Build subset expression
  subset_expr <- rep(TRUE, ncol(seurat_obj))

  if (!is.null(min_counts) && "nCount_peaks" %in% colnames(seurat_obj@meta.data)) {
    subset_expr <- subset_expr & seurat_obj$nCount_peaks >= min_counts
  }

  if (!is.null(max_counts) && "nCount_peaks" %in% colnames(seurat_obj@meta.data)) {
    subset_expr <- subset_expr & seurat_obj$nCount_peaks <= max_counts
  }

  if (!is.null(min_tss) && "TSS.enrichment" %in% colnames(seurat_obj@meta.data)) {
    subset_expr <- subset_expr & seurat_obj$TSS.enrichment >= min_tss
  }

  if (!is.null(max_ns) && "nucleosome_signal" %in% colnames(seurat_obj@meta.data)) {
    subset_expr <- subset_expr & seurat_obj$nucleosome_signal <= max_ns
  }

  if (!is.null(min_rip) && "pct_reads_in_peaks" %in% colnames(seurat_obj@meta.data)) {
    subset_expr <- subset_expr & seurat_obj$pct_reads_in_peaks >= min_rip
  }

  if (!is.null(max_bl) && "blacklist_ratio" %in% colnames(seurat_obj@meta.data)) {
    subset_expr <- subset_expr & seurat_obj$blacklist_ratio <= max_bl
  }

  n_before <- ncol(seurat_obj)
  n_after <- sum(subset_expr)

  message(sprintf("Filtering: %d -> %d cells (%.1f%% retained)",
                  n_before, n_after, 100 * n_after / n_before))

  if (return_filtered) {
    return(seurat_obj[, subset_expr])
  } else {
    return(subset_expr)
  }
}

#' Run TF-IDF normalization
#'
#' Run term frequency-inverse document frequency normalization
#'
#' @param seurat_obj Seurat object
#' @param assay Name of assay (default: "peaks")
#' @param method TF-IDF method: 1, 2, or 3 (default: 1)
#' @param scale_factor Scale factor (default: 10000)
#' @return Seurat object with TF-IDF normalized data
#' @export
run_tfidf <- function(
    seurat_obj,
    assay = "peaks",
    method = 1,
    scale_factor = 10000
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  message(sprintf("Running TF-IDF (method=%d)...", method))
  seurat_obj <- Signac::RunTFIDF(
    object = seurat_obj,
    assay = assay,
    method = method,
    scale.factor = scale_factor
  )

  return(seurat_obj)
}

#' Find top features
#'
#' Identify most accessible features
#'
#' @param seurat_obj Seurat object
#' @param assay Name of assay (default: "peaks")
#' @param min_cutoff Minimum cutoff: "qX" for quantile or numeric (default: "q0")
#' @param n_features Number of top features to select (default: NULL)
#' @return Seurat object with variable features
#' @export
find_top_features <- function(
    seurat_obj,
    assay = "peaks",
    min_cutoff = "q0",
    n_features = NULL
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  message(sprintf("Finding top features (min_cutoff=%s)...", min_cutoff))
  seurat_obj <- Signac::FindTopFeatures(
    object = seurat_obj,
    assay = assay,
    min.cutoff = min_cutoff
  )

  n_var <- length(Seurat::VariableFeatures(seurat_obj))
  message(sprintf("Selected %d variable features", n_var))

  return(seurat_obj)
}

#' Run SVD dimensionality reduction (LSI)
#'
#' Run singular value decomposition for dimensionality reduction
#'
#' @param seurat_obj Seurat object
#' @param assay Name of assay (default: "peaks")
#' @param reduction_name Name for reduction (default: "lsi")
#' @param dims Number of dimensions (default: 50)
#' @param scale_max Maximum value for scaling (default: NULL)
#' @param features Features to use (default: NULL, use VariableFeatures)
#' @return Seurat object with LSI reduction
#' @export
run_lsi <- function(
    seurat_obj,
    assay = "peaks",
    reduction_name = "lsi",
    dims = 50,
    scale_max = NULL,
    features = NULL
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  message(sprintf("Running LSI (%d dimensions)...", dims))
  seurat_obj <- Signac::RunSVD(
    object = seurat_obj,
    assay = assay,
    reduction.name = reduction_name,
    n = dims,
    scale.max = scale_max,
    features = features
  )

  return(seurat_obj)
}

#' Run standard Signac workflow
#'
#' Run the complete standard Signac analysis pipeline
#'
#' @param seurat_obj Seurat object with ChromatinAssay
#' @param dims Dimensions to use for UMAP/clustering (default: 2:30)
#' @param resolution Clustering resolution (default: 0.8)
#' @param run_umap Run UMAP (default: TRUE)
#' @param run_clustering Run clustering (default: TRUE)
#' @param tfidf_method TF-IDF method (default: 1)
#' @param min_cutoff Minimum cutoff for features (default: "q0")
#' @return Seurat object with analysis results
#' @export
run_signac_workflow <- function(
    seurat_obj,
    dims = 2:30,
    resolution = 0.8,
    run_umap = TRUE,
    run_clustering = TRUE,
    tfidf_method = 1,
    min_cutoff = "q0"
) {
  message("=== Running Signac Workflow ===")

  # TF-IDF
  seurat_obj <- run_tfidf(seurat_obj, method = tfidf_method)

  # Find top features
  seurat_obj <- find_top_features(seurat_obj, min_cutoff = min_cutoff)

  # LSI
  seurat_obj <- run_lsi(seurat_obj)

  # UMAP
  if (run_umap) {
    message("Running UMAP...")
    seurat_obj <- Seurat::RunUMAP(
      object = seurat_obj,
      reduction = "lsi",
      dims = dims
    )
  }

  # Clustering
  if (run_clustering) {
    message(sprintf("Clustering (resolution=%.2f)...", resolution))
    seurat_obj <- Seurat::FindNeighbors(
      object = seurat_obj,
      reduction = "lsi",
      dims = dims
    )
    seurat_obj <- Seurat::FindClusters(
      object = seurat_obj,
      resolution = resolution,
      verbose = FALSE
    )
  }

  message("=== Workflow Complete ===")
  return(seurat_obj)
}

#' Create gene activity matrix
#'
#' Create gene activity scores from peaks
#'
#' @param seurat_obj Seurat object
#' @param assay Name of assay (default: "peaks")
#' @param annotation Gene annotation (default: NULL, auto-detect)
#' @param features Genes to include (default: NULL, all)
#' @param extend_upstream Upstream extension (default: 2000)
#' @param extend_downstream Downstream extension (default: 0)
#' @param biotypes Gene biotypes (default: "protein_coding")
#' @param max_width Maximum gene body width (default: 500000)
#' @return Seurat object with gene activity assay
#' @export
create_gene_activity <- function(
    seurat_obj,
    assay = "peaks",
    annotation = NULL,
    features = NULL,
    extend_upstream = 2000,
    extend_downstream = 0,
    biotypes = "protein_coding",
    max_width = 500000
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  message("Creating gene activity matrix...")
  gene_activities <- Signac::GeneActivity(
    object = seurat_obj,
    assay = assay,
    annotation = annotation,
    features = features,
    extend.upstream = extend_upstream,
    extend.downstream = extend_downstream,
    biotypes = biotypes,
    max.width = max_width
  )

  # Add as RNA assay
  seurat_obj[["RNA"]] <- Seurat::CreateAssayObject(counts = gene_activities)

  # Normalize
  seurat_obj <- Seurat::NormalizeData(
    object = seurat_obj,
    assay = "RNA",
    normalization.method = "LogNormalize",
    scale.factor = median(seurat_obj$nCount_RNA)
  )

  message(sprintf("Gene activity matrix: %d genes", nrow(seurat_obj[["RNA"]])))
  return(seurat_obj)
}

#' Call peaks
#'
#' Call peaks using MACS2/MACS3
#'
#' @param seurat_obj Seurat object
#' @param group_by Grouping variable (default: NULL, all cells)
#' @param macs2_path Path to MACS2/MACS3 executable (default: "macs2")
#' @param effective_genome_size Effective genome size (default: 2.7e9)
#' @param shift Shift for MACS2 (default: -100)
#' @param extsize Extension size (default: 200)
#' @param pvalue P-value threshold (default: 0.01)
#' @param return_seurat Return Seurat object with new peaks (default: TRUE)
#' @return Seurat object or GRanges with peaks
#' @export
call_peaks_signac <- function(
    seurat_obj,
    group_by = NULL,
    macs2_path = NULL,
    effective_genome_size = 2.7e9,
    shift = -100,
    extsize = 200,
    pvalue = 0.01,
    return_seurat = TRUE
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  # Auto-detect MACS binary based on Signac version if not provided
  if (is.null(macs2_path)) {
    if (utils::packageVersion("Signac") >= package_version("1.9999")) {
      macs2_path <- "macs3"
      message("Signac v2 detected. Auto-selecting MACS3.")
    } else {
      macs2_path <- "macs2"
      message("Signac v1 detected. Auto-selecting MACS2.")
    }
  }

  # Check MACS2/MACS3
  macs_check <- tryCatch(
    system(sprintf("%s --version", macs2_path), intern = TRUE),
    error = function(e) NULL
  )
  if (is.null(macs_check)) {
    stop(sprintf("'%s' not found. Install with: pip install MACS2 or pip install MACS3", macs2_path))
  }

  if (utils::packageVersion("Signac") >= package_version("1.9999")) {
    message(sprintf("Calling peaks with %s (Signac v2 defaults to MACS3)...", macs2_path))
  } else {
    message(sprintf("Calling peaks with %s...", macs2_path))
  }
  peaks <- Signac::CallPeaks(
    object = seurat_obj,
    group.by = group_by,
    macs2.path = macs2_path,
    effective.genome.size = effective_genome_size,
    shift = shift,
    extsize = extsize,
    pvalue = pvalue
  )

  message(sprintf("Called %d peaks", length(peaks)))

  if (return_seurat) {
    # Quantify new peaks
    message("Quantifying peaks...")
    peak_counts <- Signac::FeatureMatrix(
      fragments = SeuratObject::Fragments(seurat_obj),
      features = peaks,
      cells = colnames(seurat_obj)
    )

    if (utils::packageVersion("Signac") >= package_version("1.9999")) {
      new_assay <- Signac::CreateGRangesAssay(
        counts = peak_counts,
        fragments = SeuratObject::Fragments(seurat_obj),
        annotation = Signac::Annotation(seurat_obj)
      )
    } else {
      new_assay <- Signac::CreateChromatinAssay(
        counts = peak_counts,
        fragments = SeuratObject::Fragments(seurat_obj),
        annotation = Signac::Annotation(seurat_obj)
      )
    }
    seurat_obj[["peaks"]] <- new_assay

    return(seurat_obj)
  } else {
    return(peaks)
  }
}

#' Get QC summary
#'
#' Get summary statistics for QC metrics
#'
#' @param seurat_obj Seurat object
#' @return Data frame with QC summary
#' @export
get_qc_summary <- function(seurat_obj) {
  qc_cols <- c("nCount_peaks", "nFeature_peaks", "TSS.enrichment",
               "nucleosome_signal", "pct_reads_in_peaks", "blacklist_ratio")

  available_cols <- qc_cols[qc_cols %in% colnames(seurat_obj@meta.data)]

  if (length(available_cols) == 0) {
    warning("No QC metrics found")
    return(NULL)
  }

  summary_stats <- do.call(rbind, lapply(available_cols, function(col) {
    data.frame(
      metric = col,
      mean = mean(seurat_obj@meta.data[[col]], na.rm = TRUE),
      median = median(seurat_obj@meta.data[[col]], na.rm = TRUE),
      min = min(seurat_obj@meta.data[[col]], na.rm = TRUE),
      max = max(seurat_obj@meta.data[[col]], na.rm = TRUE),
      stringsAsFactors = FALSE
    )
  }))

  return(summary_stats)
}

#' Export Signac results
#'
#' Export cell metadata and embeddings
#'
#' @param seurat_obj Seurat object
#' @param output_dir Output directory
#' @param prefix File prefix
#' @export
export_signac_results <- function(
    seurat_obj,
    output_dir = "./signac_output",
    prefix = "sample"
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # Export metadata
  metadata_file <- file.path(output_dir, paste0(prefix, "_metadata.tsv"))
  utils::write.table(
    seurat_obj@meta.data,
    metadata_file,
    sep = "\t",
    quote = FALSE,
    row.names = TRUE
  )
  message(sprintf("Exported metadata: %s", metadata_file))

  # Export embeddings if available
  for (red_name in names(seurat_obj@reductions)) {
    embedding_file <- file.path(output_dir,
                                 paste0(prefix, "_", red_name, ".tsv"))
    utils::write.table(
      seurat_obj@reductions[[red_name]]@cell.embeddings,
      embedding_file,
      sep = "\t",
      quote = FALSE,
      row.names = TRUE
    )
    message(sprintf("Exported %s: %s", red_name, embedding_file))
  }

  # Export QC summary
  qc_summary <- get_qc_summary(seurat_obj)
  if (!is.null(qc_summary)) {
    qc_file <- file.path(output_dir, paste0(prefix, "_qc_summary.tsv"))
    utils::write.table(
      qc_summary,
      qc_file,
      sep = "\t",
      quote = FALSE,
      row.names = FALSE
    )
    message(sprintf("Exported QC summary: %s", qc_file))
  }
}

#' Helper: null default operator
`%||%` <- function(x, y) if (is.null(x)) y else x
