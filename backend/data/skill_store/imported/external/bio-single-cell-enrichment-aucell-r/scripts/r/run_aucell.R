#' AUCell Analysis for Single-Cell Data
#'
#' Calculate Area Under the Curve (AUC) scores for gene sets in single-cell data.
#' AUCell is robust to dropouts and suitable for sparse scRNA-seq data.
#'
#' @author Yang Guo
#' @date 2026-03-31
#' @version 1.0.0

#' Run AUCell Analysis
#'
#' Calculate AUC scores for gene sets per cell.
#'
#' @param expr_matrix Expression matrix (genes x cells). Can be matrix, dgCMatrix, or Seurat object.
#' @param gene_sets Named list of gene sets (each element is a character vector of genes)
#' @param auc_threshold Numeric between 0 and 1. Threshold for calculating AUC (default: 0.05)
#' @param nCores Number of cores for parallel processing (default: 1)
#' @param keep_zeroes_as_na Convert zeroes to NA in rankings instead of random end placement (default: FALSE)
#' @param norm_auc Normalize maximum possible AUC to 1 (default: TRUE)
#' @param verbose Print progress messages (default: TRUE)
#'
#' @return AUCellResults object with AUC scores
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Basic usage with matrix
#' data(expr_matrix)
#' gene_sets <- list(
#'   T_cell = c("CD3D", "CD3E", "CD4", "CD8A"),
#'   B_cell = c("CD19", "CD79A", "CD79B", "MS4A1")
#' )
#' auc_results <- run_aucell(expr_matrix, gene_sets)
#'
#' # With Seurat object
#' auc_results <- run_aucell(seurat_obj, gene_sets, auc_threshold = 0.05)
#'
#' # Access results
#' auc_matrix <- getAUC(auc_results)
#' }
run_aucell <- function(
    expr_matrix,
    gene_sets,
    auc_threshold = 0.05,
    nCores = 1,
    keep_zeroes_as_na = FALSE,
    norm_auc = TRUE,
    verbose = TRUE
) {
  # Check if AUCell is installed
  if (!requireNamespace("AUCell", quietly = TRUE)) {
    stop("AUCell package required. Install with: BiocManager::install('AUCell')")
  }

  library(AUCell)

  # Extract matrix from Seurat if needed
  if (inherits(expr_matrix, "Seurat")) {
    if (verbose) message("Extracting expression matrix from Seurat object...")
    if (packageVersion("SeuratObject") >= "5.0.0") {
      expr_matrix <- GetAssayData(expr_matrix, layer = "counts")
    } else {
      expr_matrix <- GetAssayData(expr_matrix, slot = "counts")
    }
  }

  # Validate inputs
  if (!is.list(gene_sets)) {
    stop("gene_sets must be a named list")
  }

  if (is.null(names(gene_sets))) {
    stop("gene_sets must be named")
  }

  # Remove empty gene sets
  gene_sets <- gene_sets[sapply(gene_sets, length) > 0]

  if (length(gene_sets) == 0) {
    stop("No valid gene sets provided")
  }

  if (verbose) {
    message(sprintf("Running AUCell with %d gene sets on %d cells...",
                    length(gene_sets), ncol(expr_matrix)))
  }

  # Step 1: Build gene expression rankings
  if (verbose) message("Building gene expression rankings...")
  rankings <- AUCell_buildRankings(
    exprMat = expr_matrix,
    nCores = nCores,
    plotStats = FALSE,
    keepZeroesAsNA = keep_zeroes_as_na,
    verbose = verbose
  )

  # Step 2: Calculate AUC
  if (verbose) message("Calculating AUC scores...")
  auc <- AUCell_calcAUC(
    geneSets = gene_sets,
    rankings = rankings,
    nCores = nCores,
    aucMaxRank = nrow(rankings) * auc_threshold,
    normAUC = norm_auc,
    verbose = verbose
  )

  if (verbose) message("AUCell analysis complete!")

  return(auc)
}


#' Create Custom Gene Sets from Markers
#'
#' Convert marker gene lists to AUCell-compatible format.
#'
#' @param markers Named list where each element contains marker genes for a cell type
#' @param min_genes Minimum number of genes per set (default: 3)
#' @param max_genes Maximum number of genes per set (default: 100)
#'
#' @return Named list of gene sets
#'
#' @export
#'
#' @examples
#' markers <- list(
#'   T_cells = c("CD3D", "CD3E", "CD4", "CD8A", "CD8B"),
#'   B_cells = c("CD19", "CD20", "CD79A", "CD79B")
#' )
#' gene_sets <- create_gene_sets_from_markers(markers)
create_gene_sets_from_markers <- function(
    markers,
    min_genes = 3,
    max_genes = 100
) {
  # Filter by size
  markers <- markers[sapply(markers, length) >= min_genes]
  markers <- lapply(markers, function(x) head(x, max_genes))

  # Remove empty
  markers <- markers[sapply(markers, length) > 0]

  return(markers)
}


#' Add AUCell Scores to Seurat Object
#'
#' @param seurat_obj Seurat object
#' @param auc_results AUCellResults object
#' @param key_prefix Prefix for metadata columns (default: "AUC.")
#'
#' @return Seurat object with AUC scores added to metadata
#'
#' @export
add_aucell_to_seurat <- function(
    seurat_obj,
    auc_results,
    key_prefix = "AUC."
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract AUC matrix
  auc_matrix <- as.data.frame(t(getAUC(auc_results)))

  # Add prefix to column names
  colnames(auc_matrix) <- paste0(key_prefix, colnames(auc_matrix))

  # Add to metadata
  for (col in colnames(auc_matrix)) {
    seurat_obj[[col]] <- auc_matrix[[col]]
  }

  return(seurat_obj)
}


#' Plot AUCell Distribution
#'
#' Visualize AUC score distributions across groups.
#'
#' @param auc_results AUCellResults object
#' @param group_vector Vector of group labels (length = n_cells)
#' @param gene_set Name of gene set to plot
#' @param plot_type Type of plot: "violin", "box", or "ridge" (default: "violin")
#'
#' @return ggplot object
#'
#' @export
plot_aucell_distribution <- function(
    auc_results,
    group_vector,
    gene_set,
    plot_type = "violin"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Extract scores
  auc_matrix <- getAUC(auc_results)

  if (!gene_set %in% rownames(auc_matrix)) {
    stop(sprintf("Gene set '%s' not found", gene_set))
  }

  # Create data frame
  plot_data <- data.frame(
    AUC = as.numeric(auc_matrix[gene_set, ]),
    Group = factor(group_vector)
  )

  # Create plot
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = Group, y = AUC, fill = Group))

  if (plot_type == "violin") {
    p <- p + ggplot2::geom_violin(alpha = 0.7) +
      ggplot2::geom_boxplot(width = 0.1, alpha = 0.5)
  } else if (plot_type == "box") {
    p <- p + ggplot2::geom_boxplot(alpha = 0.7)
  } else if (plot_type == "ridge") {
    if (!requireNamespace("ggridges", quietly = TRUE)) {
      stop("ggridges package required for ridge plots")
    }
    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = AUC, y = Group, fill = Group)) +
      ggridges::geom_density_ridges(alpha = 0.7)
  }

  p <- p + ggplot2::labs(
    title = sprintf("AUCell: %s", gene_set),
    x = "Group",
    y = "AUC Score"
  ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "none")

  return(p)
}


#' Filter Cells by AUC Threshold
#'
#' Identify cells with significant enrichment for a gene set.
#'
#' @param auc_results AUCellResults object
#' @param gene_set Gene set name
#' @param threshold_method Method to determine threshold: "auto" or numeric value
#' @param return_names Return cell names (TRUE) or logical vector (FALSE)
#'
#' @return Cell names or logical vector
#'
#' @export
filter_cells_by_auc <- function(
    auc_results,
    gene_set,
    threshold_method = "auto",
    return_names = TRUE
) {
  auc_matrix <- getAUC(auc_results)

  if (!gene_set %in% rownames(auc_matrix)) {
    stop(sprintf("Gene set '%s' not found", gene_set))
  }

  scores <- as.numeric(auc_matrix[gene_set, ])

  if (threshold_method == "auto") {
    # Use Otsu-like threshold (bimodal distribution assumption)
    # Simplified: use mean + 1 SD as threshold
    threshold <- mean(scores) + sd(scores)
  } else if (is.numeric(threshold_method)) {
    threshold <- threshold_method
  } else {
    stop("threshold_method must be 'auto' or numeric")
  }

  is_positive <- scores > threshold

  if (return_names) {
    return(colnames(auc_matrix)[is_positive])
  } else {
    return(is_positive)
  }
}


#' Export AUCell Results
#'
#' Save AUC scores to file.
#'
#' @param auc_results AUCellResults object
#' @param output_file Output file path
#' @param format Output format: "csv", "tsv", or "rds"
#'
#' @export
export_aucell_results <- function(
    auc_results,
    output_file,
    format = "csv"
) {
  auc_matrix <- as.data.frame(t(getAUC(auc_results)))

  if (format == "csv") {
    write.csv(auc_matrix, output_file, row.names = TRUE)
  } else if (format == "tsv") {
    write.table(auc_matrix, output_file, sep = "\t", row.names = TRUE, quote = FALSE)
  } else if (format == "rds") {
    saveRDS(auc_results, output_file)
  } else {
    stop("Format must be 'csv', 'tsv', or 'rds'")
  }

  message(sprintf("Results saved to %s", output_file))
}
