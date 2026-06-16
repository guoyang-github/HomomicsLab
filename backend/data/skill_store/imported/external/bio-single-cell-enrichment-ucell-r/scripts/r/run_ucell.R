#' UCell Analysis for Single-Cell Data
#'
#' U statistic-based gene set scoring for single-cell data.
#' Fast and robust for cross-dataset comparison.
#'
#' @author Yang Guo
#' @date 2026-03-31
#' @version 1.0.0

#' Run UCell Scoring
#'
#' Calculate U statistic scores for gene sets per cell.
#'
#' @param expr_matrix Expression matrix (genes x cells) or Seurat object
#' @param gene_sets Named list of gene sets
#' @param maxRank Maximum rank for calculation (default: 1500)
#' @param w_neg Weight on negative genes in signature (default: 1)
#' @param chunk_size Number of cells to process simultaneously (default: 100)
#' @param ncores Number of cores for parallel processing (default: 1)
#' @param force.gc Force garbage collection to save memory (default: FALSE)
#' @param seed Random seed for reproducibility (default: 123)
#'
#' @return DataFrame with UCell scores (cells x gene_sets)
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Basic usage
#' gene_sets <- list(
#'   T_cells = c("CD3D", "CD3E", "CD4", "CD8A"),
#'   B_cells = c("CD19", "CD79A", "MS4A1")
#' )
#'
#' scores <- run_ucell(
#'   expr_matrix = expr_matrix,
#'   gene_sets = gene_sets,
#'   maxRank = 1500
#' )
#'
#' # With Seurat
#' seurat_obj <- AddMetaData(seurat_obj, scores)
#' }
run_ucell <- function(
    expr_matrix,
    gene_sets,
    maxRank = 1500,
    w_neg = 1,
    chunk_size = 100,
    ncores = 1,
    force.gc = FALSE,
    seed = 123
) {
  # Check dependencies
  if (!requireNamespace("UCell", quietly = TRUE)) {
    stop("UCell package required. Install with: devtools::install_github('carmonalab/UCell')")
  }

  library(UCell)

  # Extract matrix from Seurat if needed
  if (inherits(expr_matrix, "Seurat")) {
    message("Extracting expression matrix from Seurat object...")
    if (packageVersion("SeuratObject") >= "5.0.0") {
      expr_matrix <- Seurat::GetAssayData(expr_matrix, layer = "data")
    } else {
      expr_matrix <- Seurat::GetAssayData(expr_matrix, slot = "data")
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

  message(sprintf("Running UCell with %d gene sets on %d cells...",
                  length(gene_sets), ncol(expr_matrix)))

  # Run UCell
  set.seed(seed)

  scores <- UCell::ScoreSignatures_UCell(
    expr_matrix,
    features = gene_sets,
    maxRank = maxRank,
    w_neg = w_neg,
    chunk.size = chunk_size,
    ncores = ncores,
    force.gc = force.gc
  )

  message("UCell complete!")
  return(as.data.frame(scores))
}


#' Run UCell with Seurat
#'
#' Convenience wrapper for Seurat users.
#'
#' @param seurat_obj Seurat object
#' @param gene_sets Named list of gene sets
#' @param slot Data slot to use (default: 'data')
#' @param prefix Prefix for metadata columns (default: "UCell.")
#' @param ... Additional arguments passed to run_ucell()
#'
#' @return Seurat object with UCell scores in metadata
#'
#' @export
run_ucell_seurat <- function(
    seurat_obj,
    gene_sets,
    slot = 'data',
    prefix = "UCell.",
    ...
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract data
  if (packageVersion("SeuratObject") >= "5.0.0") {
    expr_matrix <- Seurat::GetAssayData(seurat_obj, layer = slot)
  } else {
    expr_matrix <- Seurat::GetAssayData(seurat_obj, slot = slot)
  }

  # Run UCell
  scores <- run_ucell(expr_matrix, gene_sets, ...)

  # Add prefix to column names
  colnames(scores) <- paste0(prefix, colnames(scores))

  # Add to metadata
  for (col in colnames(scores)) {
    seurat_obj[[col]] <- scores[[col]]
  }

  return(seurat_obj)
}


#' Add Module Scores with UCell
#'
#' Convenience function similar to Seurat's AddModuleScore but using UCell.
#'
#' @param seurat_obj Seurat object
#' @param features List of gene sets
#' @param name Prefix for output columns (default: "UCell")
#' @param ... Additional arguments for run_ucell()
#'
#' @return Seurat object with module scores
#'
#' @export
AddModuleScore_UCell <- function(
    seurat_obj,
    features,
    name = "UCell",
    ...
) {
  if (!is.list(features)) {
    stop("features must be a list of gene vectors")
  }

  # Generate names if not provided
  if (is.null(names(features))) {
    names(features) <- paste0(name, "_", seq_along(features))
  }

  # Run UCell
  seurat_obj <- run_ucell_seurat(
    seurat_obj,
    gene_sets = features,
    prefix = paste0(name, "_"),
    ...
  )

  return(seurat_obj)
}


#' Plot UCell Distribution
#'
#' @param scores DataFrame with UCell scores
#' @param group_vector Vector of group labels
#' @param gene_set Gene set to visualize
#' @param plot_type Type: "violin", "box", "ridge" (default: "violin")
#'
#' @return ggplot object
#'
#' @export
plot_ucell_distribution <- function(
    scores,
    group_vector,
    gene_set,
    plot_type = "violin"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  if (!gene_set %in% colnames(scores)) {
    stop(sprintf("Gene set '%s' not found", gene_set))
  }

  plot_data <- data.frame(
    Score = scores[[gene_set]],
    Group = factor(group_vector)
  )

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = Group, y = Score, fill = Group))

  if (plot_type == "violin") {
    p <- p + ggplot2::geom_violin(alpha = 0.7) +
      ggplot2::geom_boxplot(width = 0.1, alpha = 0.5)
  } else if (plot_type == "box") {
    p <- p + ggplot2::geom_boxplot(alpha = 0.7)
  } else if (plot_type == "ridge") {
    if (!requireNamespace("ggridges", quietly = TRUE)) {
      stop("ggridges required for ridge plots")
    }
    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = Score, y = Group, fill = Group)) +
      ggridges::geom_density_ridges(alpha = 0.7)
  }

  p <- p + ggplot2::labs(
    title = sprintf("UCell: %s", gene_set),
    x = "Group",
    y = "UCell Score"
  ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "none")

  return(p)
}


#' Export UCell Results
#'
#' @param scores DataFrame with UCell scores
#' @param output_file Output file path
#' @param format Output format: "csv", "tsv", or "rds"
#'
#' @export
export_ucell_results <- function(
    scores,
    output_file,
    format = "csv"
) {
  if (format == "csv") {
    write.csv(scores, output_file, row.names = TRUE)
  } else if (format == "tsv") {
    write.table(scores, output_file, sep = "\t", row.names = TRUE, quote = FALSE)
  } else if (format == "rds") {
    saveRDS(scores, output_file)
  } else {
    stop("Format must be 'csv', 'tsv', or 'rds'")
  }

  message(sprintf("Results saved to %s", output_file))
}
