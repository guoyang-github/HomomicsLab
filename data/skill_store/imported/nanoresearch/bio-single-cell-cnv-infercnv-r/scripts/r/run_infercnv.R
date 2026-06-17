#' inferCNV for Single-Cell CNV Analysis
#'
#' Infer copy number variations from single-cell RNA-seq data.
#'
#' @author Yang Guo
#' @date 2026-03-31
#' @version 1.0.0

#' Run inferCNV
#'
#' @param raw_counts Raw count matrix (genes x cells)
#' @param gene_order DataFrame with gene chromosome positions
#' @param annotations DataFrame with cell type annotations
#' @param ref_group_names Vector of reference (normal) cell type names
#' @param cutoff Cutoff for expression (default: 0.1)
#' @param out_dir Output directory (default: "./infercnv_output")
#' @param cluster_by_groups Whether to cluster by groups (default: FALSE)
#' @param denoise Whether to denoise (default: FALSE)
#' @param HMM Whether to run HMM (default: FALSE)
#' @param num_threads Number of threads (default: 4)
#'
#' @return inferCNV object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' infercnv_obj <- run_infercnv(
#'   raw_counts = counts,
#'   gene_order = gene_order,
#'   annotations = annotations,
#'   ref_group_names = c("Immune", "Endothelial"),
#'   out_dir = "./infercnv_output"
#' )
#' }
run_infercnv <- function(
    raw_counts,
    gene_order,
    annotations,
    ref_group_names,
    cutoff = 0.1,
    out_dir = "./infercnv_output",
    cluster_by_groups = FALSE,
    denoise = TRUE,
    HMM = FALSE,
    num_threads = 4
) {
  if (!requireNamespace("infercnv", quietly = TRUE)) {
    stop("infercnv package required. Install with: BiocManager::install('infercnv')")
  }

  library(infercnv)

  # Validate annotations format
  if (is.data.frame(annotations)) {
    if (ncol(annotations) != 2) {
      stop(sprintf("annotations must have exactly 2 columns (cell, cell_type), got %d", ncol(annotations)))
    }
    # Validate ref_group_names exist in annotations
    actual_types <- unique(annotations[[2]])
    missing_refs <- setdiff(ref_group_names, actual_types)
    if (length(missing_refs) > 0) {
      stop(sprintf(
        "ref_group_names not found in annotations: %s. Available types: %s",
        paste(missing_refs, collapse = ", "),
        paste(actual_types, collapse = ", ")
      ))
    }
  }

  # Validate raw_counts dimensions
  if (nrow(raw_counts) == 0 || ncol(raw_counts) == 0) {
    stop("raw_counts matrix is empty (0 genes or 0 cells)")
  }

  message("Creating inferCNV object...")

  # Write gene_order and annotations to temp files if they are data frames
  if (is.data.frame(gene_order)) {
    gene_order_file <- tempfile(pattern = "gene_order_", fileext = ".txt")
    write.table(gene_order, gene_order_file, sep = "\t", row.names = FALSE, col.names = FALSE, quote = FALSE)
    on.exit(unlink(gene_order_file), add = TRUE)
  } else {
    gene_order_file <- gene_order
  }

  if (is.data.frame(annotations)) {
    annotations_file <- tempfile(pattern = "annotations_", fileext = ".txt")
    write.table(annotations, annotations_file, sep = "\t", row.names = FALSE, col.names = FALSE, quote = FALSE)
    on.exit(unlink(annotations_file), add = TRUE)
  } else {
    annotations_file <- annotations
  }

  # Create inferCNV object
  infercnv_obj <- CreateInfercnvObject(
    raw_counts_matrix = raw_counts,
    gene_order_file = gene_order_file,
    annotations_file = annotations_file,
    ref_group_names = ref_group_names,
    delim = "\t",
    max_cells_per_group = NULL,
    min_max_counts_per_cell = c(100, +Inf),
    chr_exclude = c("chrX", "chrY", "chrMT")
  )

  message("Running inferCNV analysis...")

  # Run inferCNV
  infercnv_obj <- run(
    infercnv_obj,
    cutoff = cutoff,
    min_cells_per_gene = 3,
    out_dir = out_dir,
    cluster_by_groups = cluster_by_groups,
    plot_steps = FALSE,
    scale_data = FALSE,
    denoise = denoise,
    noise_filter = NA,
    sd_amplifier = 1.5,
    HMM = HMM,
    HMM_type = "i6",
    BayesMaxPNormal = 0,
    num_threads = num_threads,
    no_prelim_plot = TRUE,
    no_plot = TRUE
  )

  message("inferCNV complete!")
  return(infercnv_obj)
}


#' Run inferCNV with Seurat
#'
#' @param seurat_obj Seurat object
#' @param cell_type_column Column with cell type annotations
#' @param ref_cell_types Vector of reference cell types
#' @param gene_order_file Path to gene order file (or NULL for auto)
#' @param ... Additional arguments for run_infercnv()
#'
#' @return inferCNV object
#'
#' @export
run_infercnv_seurat <- function(
    seurat_obj,
    cell_type_column = "cell_type",
    ref_cell_types,
    gene_order_file = NULL,
    assay = "RNA",
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(Seurat)

  # Validate ref_cell_types
  if (length(ref_cell_types) == 0) {
    stop("ref_cell_types cannot be empty")
  }

  # Extract counts (handle both Seurat v4 and v5)
  if (packageVersion("SeuratObject") >= "5.0.0") {
    counts <- GetAssayData(seurat_obj, layer = "counts", assay = assay)
  } else {
    counts <- GetAssayData(seurat_obj, slot = "counts", assay = assay)
  }

  # Extract annotations
  if (!cell_type_column %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("'%s' not found in metadata", cell_type_column))
  }

  annotations <- data.frame(
    cell = colnames(seurat_obj),
    cell_type = seurat_obj@meta.data[[cell_type_column]]
  )

  # Validate ref_cell_types exist in metadata
  actual_types <- unique(seurat_obj@meta.data[[cell_type_column]])
  missing_refs <- setdiff(ref_cell_types, actual_types)
  if (length(missing_refs) > 0) {
    stop(sprintf(
      "ref_cell_types not found in '%s': %s. Available types: %s",
      cell_type_column,
      paste(missing_refs, collapse = ", "),
      paste(actual_types, collapse = ", ")
    ))
  }

  # Create gene order if not provided
  if (is.null(gene_order_file)) {
    gene_order <- create_gene_order(rownames(counts))
  } else {
    gene_order <- read.delim(gene_order_file, header = FALSE)
  }

  # Run inferCNV
  infercnv_obj <- run_infercnv(
    raw_counts = counts,
    gene_order = gene_order,
    annotations = annotations,
    ref_group_names = ref_cell_types,
    ...
  )

  return(infercnv_obj)
}


#' Create Gene Order File
#'
#' Create gene order from gene symbols using biomaRt. Automatically queries
#' gene chromosome positions and formats for inferCNV.
#'
#' @param gene_symbols Vector of gene symbols
#' @param genome Genome version: "hg38", "hg19", or "mm10" (default: "hg38")
#' @param organism Organism: "human" or "mouse" (default: "human")
#' @param dedup_method How to handle duplicate genes: "first", "longest", or "all"
#'   (default: "first")
#' @param missing_action Action for genes not found: "warn", "error", or "ignore"
#'   (default: "warn")
#' @param output_file Optional path to save gene order file
#' @param mart_host biomaRt host URL (default: "https://www.ensembl.org")
#'
#' @return DataFrame with columns: gene, chr, start, end
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Basic usage
#' gene_order <- create_gene_order(rownames(seurat_obj))
#'
#' # Save to file with specific genome
#' gene_order <- create_gene_order(
#'   gene_symbols = rownames(seurat_obj),
#'   genome = "hg19",
#'   output_file = "gene_order.txt"
#' )
#'
#' # Mouse data
#' gene_order <- create_gene_order(
#'   gene_symbols = rownames(seurat_obj),
#'   organism = "mouse",
#'   genome = "mm10"
#' )
#' }
create_gene_order <- function(
    gene_symbols,
    genome = "hg38",
    organism = "human",
    dedup_method = "first",
    missing_action = "warn",
    output_file = NULL,
    mart_host = "https://www.ensembl.org"
) {
  if (!requireNamespace("biomaRt", quietly = TRUE)) {
    stop("biomaRt package required. Install with: BiocManager::install('biomaRt')")
  }

  library(biomaRt)

  # Validate inputs
  if (length(gene_symbols) == 0 || all(is.na(gene_symbols))) {
    stop("gene_symbols cannot be empty or all NA")
  }
  # Remove NA values
  gene_symbols <- gene_symbols[!is.na(gene_symbols)]
  if (length(gene_symbols) == 0) {
    stop("gene_symbols is empty after removing NA values")
  }

  dedup_method <- match.arg(dedup_method, c("first", "longest", "all"))
  missing_action <- match.arg(missing_action, c("warn", "error", "ignore"))

  # Determine Ensembl dataset
  dataset <- switch(organism,
    "human" = "hsapiens_gene_ensembl",
    "mouse" = "mmusculus_gene_ensembl",
    stop(sprintf("Unsupported organism: %s", organism))
  )

  message(sprintf("Fetching gene positions from biomaRt (%s, %s)...", organism, genome))

  # Connect to biomaRt with fallback mirror
  ensembl <- tryCatch({
    useMart("ensembl", dataset = dataset, host = mart_host)
  }, error = function(e) {
    message("Failed to connect to primary host, trying mirror...")
    useMart("ensembl", dataset = dataset, host = "https://useast.ensembl.org")
  })

  # Map genome version to Ensembl attributes
  chr_attr <- switch(genome,
    "hg38" = "chromosome_name",
    "hg19" = "chromosome_name",
    "mm10" = "chromosome_name",
    "chromosome_name"
  )

  # Query gene positions - use organism-specific attributes
  attrs <- switch(organism,
    "human" = c("hgnc_symbol", chr_attr, "start_position", "end_position"),
    "mouse" = c("mgi_symbol", chr_attr, "start_position", "end_position")
  )

  gene_positions <- getBM(
    attributes = attrs,
    filters = switch(organism, "human" = "hgnc_symbol", "mouse" = "mgi_symbol"),
    values = gene_symbols,
    mart = ensembl
  )

  # Use appropriate symbol column
  symbol_col <- switch(organism, "human" = "hgnc_symbol", "mouse" = "mgi_symbol")

  # Filter to standard chromosomes
  std_chrs <- c(1:22, "X", "Y", "MT")
  if (organism == "mouse") {
    std_chrs <- c(1:19, "X", "Y", "MT")
  }

  gene_positions <- gene_positions[
    gene_positions[[chr_attr]] %in% std_chrs,
  ]

  if (nrow(gene_positions) == 0) {
    stop("No genes found with standard chromosome annotations")
  }

  # Handle duplicates
  gene_positions <- .deduplicate_genes(gene_positions, symbol_col, dedup_method)

  # Format for inferCNV
  gene_order <- data.frame(
    gene = gene_positions[[symbol_col]],
    chr = paste0("chr", gene_positions[[chr_attr]]),
    start = as.integer(gene_positions$start_position),
    end = as.integer(gene_positions$end_position),
    stringsAsFactors = FALSE
  )

  # Sort by chromosome and position
  gene_order <- .sort_gene_order(gene_order, organism)

  # Check for missing genes
  found_genes <- gene_order$gene
  missing_genes <- setdiff(gene_symbols, found_genes)

  if (length(missing_genes) > 0) {
    msg <- sprintf("%d genes not found in biomaRt", length(missing_genes))
    if (missing_action == "error") {
      stop(msg)
    } else if (missing_action == "warn") {
      warning(sprintf("%s (showing first 10): %s",
                     msg, paste(head(missing_genes, 10), collapse = ", ")))
    }
  }

  message(sprintf("Created gene order for %d genes (%d unique chromosomes)",
                 nrow(gene_order), length(unique(gene_order$chr))))

  # Save to file if requested
  if (!is.null(output_file)) {
    write.table(gene_order, output_file,
                sep = "\t", row.names = FALSE, col.names = FALSE, quote = FALSE)
    message(sprintf("Gene order saved to: %s", output_file))
  }

  return(gene_order)
}


#' Deduplicate Genes
#'
#' Handle genes with multiple positions or annotations.
#'
#' @param gene_positions DataFrame from biomaRt
#' @param symbol_col Column name for gene symbols
#' @param method Deduplication method
#'
#' @return Deduplicated DataFrame
#' @keywords internal
.deduplicate_genes <- function(gene_positions, symbol_col, method = "first") {
  # Count occurrences
  gene_counts <- table(gene_positions[[symbol_col]])
  dup_genes <- names(gene_counts[gene_counts > 1])

  if (length(dup_genes) > 0) {
    message(sprintf("Found %d genes with multiple positions, using '%s' method",
                   length(dup_genes), method))

    if (method == "first") {
      # Keep first occurrence
      gene_positions <- gene_positions[!duplicated(gene_positions[[symbol_col]]), ]

    } else if (method == "longest") {
      # Keep longest transcript
      gene_positions$length <- gene_positions$end_position - gene_positions$start_position

      # Sort by symbol (descending) and length (descending)
      gene_positions <- gene_positions[order(
        gene_positions[[symbol_col]],
        -gene_positions$length
      ), ]

      gene_positions <- gene_positions[!duplicated(gene_positions[[symbol_col]]), ]
      gene_positions$length <- NULL

    } else if (method == "all") {
      # Append suffix to duplicates
      for (gene in dup_genes) {
        mask <- gene_positions[[symbol_col]] == gene
        indices <- which(mask)
        for (i in seq_along(indices)[-1]) {
          gene_positions[[symbol_col]][indices[i]] <- sprintf("%s_dup%d", gene, i - 1)
        }
      }
    }
  }

  return(gene_positions)
}


#' Sort Gene Order by Chromosome
#'
#' Sort genes by chromosome order and position.
#'
#' @param gene_order DataFrame with chr, start columns
#' @param organism Organism for chromosome ordering
#'
#' @return Sorted DataFrame
#' @keywords internal
.sort_gene_order <- function(gene_order, organism = "human") {
  # Define chromosome order
  chr_order <- if (organism == "mouse") {
    c(paste0("chr", 1:19), "chrX", "chrY", "chrMT")
  } else {
    c(paste0("chr", 1:22), "chrX", "chrY", "chrMT")
  }

  # Identify unknown chromosomes and warn
  unknown_chrs <- setdiff(unique(gene_order$chr), chr_order)
  if (length(unknown_chrs) > 0) {
    warning(sprintf(
      "Unknown chromosomes found (will be placed at end): %s",
      paste(unknown_chrs, collapse = ", ")
    ))
  }

  # Append unknown chromosomes to the end of the order
  full_chr_order <- c(chr_order, unknown_chrs)

  # Create factor for proper sorting
  gene_order$chr <- factor(gene_order$chr, levels = full_chr_order)

  # Sort by chromosome and start position
  gene_order <- gene_order[order(gene_order$chr, gene_order$start), ]

  # Convert back to character (preserves original names, no NA conversion)
  gene_order$chr <- as.character(gene_order$chr)

  return(gene_order)
}


#' Load Gene Order File
#'
#' Load and validate a gene order file for inferCNV.
#'
#' @param file_path Path to gene order file
#' @param expected_genes Optional vector of expected gene symbols to validate
#'
#' @return DataFrame with gene order
#' @export
load_gene_order <- function(file_path, expected_genes = NULL) {
  if (!file.exists(file_path)) {
    stop(sprintf("Gene order file not found: %s", file_path))
  }

  gene_order <- read.delim(file_path, header = FALSE, stringsAsFactors = FALSE)

  # Validate format
  if (ncol(gene_order) < 4) {
    stop("Gene order file must have 4 columns: gene, chr, start, end")
  }

  colnames(gene_order)[1:4] <- c("gene", "chr", "start", "end")

  # Convert types
  gene_order$start <- as.integer(gene_order$start)
  gene_order$end <- as.integer(gene_order$end)

  # Validate expected genes if provided
  if (!is.null(expected_genes)) {
    missing <- setdiff(expected_genes, gene_order$gene)
    if (length(missing) > 0) {
      warning(sprintf("%d expected genes not in gene order file", length(missing)))
    }
  }

  message(sprintf("Loaded gene order: %d genes on %d chromosomes",
                 nrow(gene_order), length(unique(gene_order$chr))))

  return(gene_order)
}


#' Plot inferCNV Results
#'
#' @param infercnv_obj inferCNV object
#' @param output_file Output file path
#'
#' @export
plot_infercnv <- function(infercnv_obj, output_file = "infercnv_heatmap.png") {
  if (!requireNamespace("infercnv", quietly = TRUE)) {
    stop("infercnv package required")
  }
  if (!requireNamespace("ComplexHeatmap", quietly = TRUE)) {
    stop("ComplexHeatmap package required for plotting. Install with: BiocManager::install('ComplexHeatmap')")
  }

  plot_cnv(
    infercnv_obj,
    out_dir = dirname(output_file),
    output_filename = basename(output_file),
    x.center = 1,
    x.range = c(0.5, 1.5),
    title = "inferCNV Heatmap"
  )

  message(sprintf("Plot saved to %s", output_file))
}


#' Export CNV Results
#'
#' @param infercnv_obj inferCNV object
#' @param output_dir Output directory
#'
#' @export
export_infercnv_results <- function(infercnv_obj, output_dir) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Write expression matrix
  write.csv(
    infercnv_obj@expr.data,
    file.path(output_dir, "cnv_matrix.csv")
  )

  # Write gene order (no row.names since gene column already exists)
  write.csv(
    infercnv_obj@gene_order,
    file.path(output_dir, "gene_order.csv"),
    row.names = FALSE
  )

  message(sprintf("Results exported to %s", output_dir))
}
