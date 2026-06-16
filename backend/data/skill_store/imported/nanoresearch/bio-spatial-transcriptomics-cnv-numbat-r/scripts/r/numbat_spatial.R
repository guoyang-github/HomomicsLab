#' Numbat Spatial Transcriptomics Analysis Functions
#'
#' Wrapper functions for running Numbat on spatial transcriptomics data
#' with optimized parameters for Visium and other spatial platforms.
#'
#' @author Yang Guo
#' @date 2026-04-13

#' Run Numbat on Spatial Transcriptomics Data
#'
#' Wrapper for run_numbat() with spatial-optimized default parameters.
#' Key difference: max_entropy = 0.8 (vs default 0.5) for sparse allele data.
#'
#' @param count_mat Gene x cell raw UMI count matrix
#' @param lambdas_ref Gene x cell type reference expression matrix
#' @param df_allele Allele dataframe from pileup_and_phase
#' @param genome Genome version: "hg38", "hg19", or "mm10"
#' @param max_entropy Max uncertainty threshold (default: 0.8 for spatial)
#' @param t HMM transition probability (default: 1e-5)
#' @param gamma Allele overdispersion (default: 20)
#' @param ncores Number of cores
#' @param out_dir Output directory
#' @param ... Additional parameters passed to run_numbat()
#'
#' @return Numbat object with CNV results
#'
#' @examples
#' \dontrun{
#' nb <- run_numbat_spatial(
#'   count_mat = counts,
#'   lambdas_ref = ref_hca,
#'   df_allele = allele_counts,
#'   out_dir = "./numbat_output"
#' )
#' }
#'
#' @export
run_numbat_spatial <- function(
    count_mat,
    lambdas_ref,
    df_allele,
    genome = "hg38",
    max_entropy = 0.8,
    t = 1e-5,
    gamma = 20,
    ncores = 4,
    out_dir = "./numbat_output",
    ...
) {
  if (!requireNamespace("numbat", quietly = TRUE)) {
    stop("numbat package required. Install with: devtools::install_github('kharchenkolab/numbat')")
  }

  # Validate inputs
  if (!is.matrix(count_mat) && !inherits(count_mat, "Matrix")) {
    stop("count_mat must be a matrix or sparse Matrix object")
  }
  if (!("cell" %in% colnames(df_allele))) {
    stop("df_allele must contain a 'cell' column")
  }
  if (!is.matrix(lambdas_ref) && !is.data.frame(lambdas_ref)) {
    stop("lambdas_ref must be a matrix or data.frame")
  }
  if (nrow(lambdas_ref) != nrow(count_mat)) {
    stop(sprintf("lambdas_ref row count (%d) does not match count_mat row count (%d)",
                 nrow(lambdas_ref), nrow(count_mat)))
  }

  message(sprintf("Running Numbat on spatial data (max_entropy = %.1f)", max_entropy))

  # Run Numbat with spatial-optimized parameters
  nb <- numbat::run_numbat(
    count_mat = count_mat,
    lambdas_ref = lambdas_ref,
    df_allele = df_allele,
    genome = genome,
    max_entropy = max_entropy,
    t = t,
    gamma = gamma,
    ncores = ncores,
    out_dir = out_dir,
    ...
  )

  return(nb)
}


#' Export Numbat Results
#'
#' Export all Numbat analysis results to CSV files.
#'
#' @param nb Numbat object
#' @param output_dir Output directory path
#' @param prefix Prefix for output files
#'
#' @return None (writes files to disk)
#'
#' @export
export_numbat_results <- function(
    nb,
    output_dir = "./numbat_export",
    prefix = "sample"
) {
  if (!requireNamespace("data.table", quietly = TRUE)) {
    stop("data.table package required")
  }

  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Export clone assignments
  if (!is.null(nb$clone_post)) {
    data.table::fwrite(
      nb$clone_post,
      file.path(output_dir, paste0(prefix, "_clone_assignments.csv"))
    )
    message(sprintf("Exported: %s_clone_assignments.csv", prefix))
  }

  # Export CNV events
  if (!is.null(nb$joint_post)) {
    data.table::fwrite(
      nb$joint_post,
      file.path(output_dir, paste0(prefix, "_cnv_events.csv"))
    )
    message(sprintf("Exported: %s_cnv_events.csv", prefix))
  }

  # Export consensus segments
  if (!is.null(nb$segs_consensus)) {
    data.table::fwrite(
      nb$segs_consensus,
      file.path(output_dir, paste0(prefix, "_consensus_segments.csv"))
    )
    message(sprintf("Exported: %s_consensus_segments.csv", prefix))
  }

  # Export phylogeny (if available)
  if (!is.null(nb$gtree)) {
    if (!requireNamespace("ape", quietly = TRUE)) {
      stop("ape package required for phylogeny export")
    }
    tree_file <- file.path(output_dir, paste0(prefix, "_phylogeny.newick"))
    ape::write.tree(nb$gtree, tree_file)
    message(sprintf("Exported: %s_phylogeny.newick", prefix))
  }

  message(sprintf("All results exported to: %s", output_dir))
}


#' Plot CNV Probability on Spatial Tissue
#'
#' Visualize mutant vs normal probabilities on tissue coordinates.
#'
#' @param nb Numbat object
#' @param spots Spatial coordinates dataframe (from tissue_positions.csv)
#' @param title Plot title
#' @param color_low Color for normal (default: "darkgreen")
#' @param color_mid Color for mixed (default: "yellow")
#' @param color_high Color for mutant (default: "red3")
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' spots <- fread("spatial/tissue_positions.csv")
#' p <- plot_cnv_spatial(nb, spots, title = "Sample1")
#' print(p)
#' }
#'
#' @export
plot_cnv_spatial <- function(
    nb,
    spots,
    title = "CNV Probability",
    color_low = "darkgreen",
    color_mid = "yellow",
    color_high = "red3"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("dplyr", quietly = TRUE)) {
    stop("dplyr package required")
  }
  if (!requireNamespace("scales", quietly = TRUE)) {
    stop("scales package required")
  }

  # Validate inputs
  if (is.null(nb$clone_post)) {
    stop("nb$clone_post is NULL. Run Numbat first.")
  }
  if (!("p_cnv" %in% colnames(nb$clone_post))) {
    stop("nb$clone_post missing 'p_cnv' column")
  }
  required_cols <- c("barcode", "in_tissue", "array_row", "array_col")
  missing_cols <- setdiff(required_cols, colnames(spots))
  if (length(missing_cols) > 0) {
    stop(sprintf("spots dataframe missing required columns: %s", paste(missing_cols, collapse = ", ")))
  }

  p <- spots %>%
    dplyr::left_join(nb$clone_post, by = c("barcode" = "cell")) %>%
    dplyr::filter(in_tissue == 1) %>%
    ggplot2::ggplot(ggplot2::aes(x = array_row, y = array_col)) +
    ggplot2::geom_point(
      ggplot2::aes(color = p_cnv),
      size = 1,
      alpha = 0.8,
      pch = 16
    ) +
    ggplot2::scale_color_gradient2(
      low = color_low,
      high = color_high,
      mid = color_mid,
      midpoint = 0.5,
      limits = c(0, 1),
      oob = scales::oob_squish,
      name = "P(CNV)"
    ) +
    ggplot2::theme_bw() +
    ggplot2::coord_fixed() +
    ggplot2::labs(
      title = title,
      x = "Array Row",
      y = "Array Col"
    ) +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"),
      axis.text = ggplot2::element_blank(),
      axis.ticks = ggplot2::element_blank()
    )

  return(p)
}


#' Plot Clones on Spatial Tissue
#'
#' Visualize clonal assignments on tissue coordinates.
#'
#' @param nb Numbat object
#' @param spots Spatial coordinates dataframe
#' @param pal Clone color palette (named vector)
#' @param title Plot title
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' pal <- c(`1` = "gray", `2` = "#9E0142", `3` = "#F67D4A")
#' p <- plot_clone_spatial(nb, spots, pal = pal)
#' }
#'
#' @export
plot_clone_spatial <- function(
    nb,
    spots,
    pal = NULL,
    title = "Clonal Architecture"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("dplyr", quietly = TRUE)) {
    stop("dplyr package required")
  }

  # Validate inputs
  if (is.null(nb$clone_post)) {
    stop("nb$clone_post is NULL. Run Numbat first.")
  }
  if (!("clone_opt" %in% colnames(nb$clone_post))) {
    stop("nb$clone_post missing 'clone_opt' column")
  }
  required_cols <- c("barcode", "in_tissue", "array_row", "array_col")
  missing_cols <- setdiff(required_cols, colnames(spots))
  if (length(missing_cols) > 0) {
    stop(sprintf("spots dataframe missing required columns: %s", paste(missing_cols, collapse = ", ")))
  }

  # Build palette if not provided
  if (is.null(pal)) {
    clone_levels <- sort(unique(nb$clone_post$clone_opt))
    n_clones <- length(clone_levels)
    default_pal <- c(
      `1` = "gray", `2` = "#9E0142", `3` = "#F67D4A",
      `4` = "#F2EA91", `5` = "#77C8A4", `6` = "#5E4FA2"
    )
    if (n_clones <= length(default_pal)) {
      pal <- default_pal[as.character(clone_levels)]
    } else {
      # Generate colors dynamically for large clone counts
      extra_colors <- grDevices::rainbow(n_clones)
      names(extra_colors) <- as.character(clone_levels)
      pal <- extra_colors
    }
  }

  p <- spots %>%
    dplyr::left_join(nb$clone_post, by = c("barcode" = "cell")) %>%
    dplyr::filter(in_tissue == 1) %>%
    dplyr::mutate(clone_opt = factor(clone_opt)) %>%
    ggplot2::ggplot(ggplot2::aes(x = array_row, y = array_col)) +
    ggplot2::geom_point(
      ggplot2::aes(color = clone_opt),
      size = 0.5,
      alpha = 0.8
    ) +
    ggplot2::scale_color_manual(
      values = pal,
      limits = force,
      name = "Clone"
    ) +
    ggplot2::theme_bw() +
    ggplot2::coord_fixed() +
    ggplot2::labs(
      title = title,
      x = "Array Row",
      y = "Array Col"
    ) +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, face = "bold"),
      axis.text = ggplot2::element_blank(),
      axis.ticks = ggplot2::element_blank()
    )

  return(p)
}


#' Aggregate Counts by Cluster
#'
#' Build reference expression profile by aggregating cells by cluster.
#'
#' @param count_mat Gene x cell raw count matrix
#' @param cell_annot Dataframe with columns "cell" and "group"
#' @param normalize Whether to normalize counts (default: TRUE)
#'
#' @return Gene x group normalized expression matrix
#'
#' @examples
#' \dontrun{
#' cell_annot <- data.frame(
#'   cell = colnames(counts),
#'   group = cluster_labels
#' )
#' ref <- aggregate_counts(counts, cell_annot)
#' }
#'
#' @export
aggregate_counts <- function(
    count_mat,
    cell_annot,
    normalize = TRUE
) {
  if (!requireNamespace("Matrix", quietly = TRUE)) {
    stop("Matrix package required")
  }

  # Ensure cell_annot is dataframe
  cell_annot <- as.data.frame(cell_annot)

  # Match cells
  common_cells <- intersect(colnames(count_mat), cell_annot$cell)
  if (length(common_cells) == 0) {
    stop("No matching cells between count_mat and cell_annot")
  }

  count_mat <- count_mat[, common_cells, drop = FALSE]
  cell_annot <- cell_annot[match(common_cells, cell_annot$cell), ]

  # Get unique groups
  groups <- unique(cell_annot$group)

  # Aggregate counts per group
  ref_list <- lapply(groups, function(g) {
    cells_g <- cell_annot$cell[cell_annot$group == g]
    counts_g <- count_mat[, cells_g, drop = FALSE]

    # Sum counts
    sum_counts <- Matrix::rowSums(counts_g)

    # Normalize
    if (normalize) {
      total <- sum(sum_counts)
      if (total > 0) {
        sum_counts <- sum_counts / total * 1e6
      }
    }

    return(sum_counts)
  })

  # Combine into matrix
  ref_matrix <- do.call(cbind, ref_list)
  colnames(ref_matrix) <- groups
  rownames(ref_matrix) <- rownames(count_mat)

  return(ref_matrix)
}


#' Load Numbat Results
#'
#' Load existing Numbat results from output directory.
#'
#' @param out_dir Numbat output directory
#' @param i iteration number (default: 2 for final results)
#'
#' @return Numbat object
#'
#' @export
load_numbat_results <- function(out_dir, i = 2) {
  if (!requireNamespace("numbat", quietly = TRUE)) {
    stop("numbat package required")
  }

  # NOTE: numbat::Numbat is an internal R6 class (not exported).
  # Load results directly from output files instead.
  results <- list()

  clone_post_file <- file.path(out_dir, sprintf("clone_post_%d.tsv", i))
  if (file.exists(clone_post_file)) {
    results$clone_post <- data.table::fread(clone_post_file)
  }

  joint_post_file <- file.path(out_dir, sprintf("joint_post_%d.tsv", i))
  if (file.exists(joint_post_file)) {
    results$joint_post <- data.table::fread(joint_post_file)
  }

  segs_file <- file.path(out_dir, sprintf("segs_consensus_%d.tsv", i))
  if (file.exists(segs_file)) {
    results$segs_consensus <- data.table::fread(segs_file)
  }

  tree_file <- file.path(out_dir, sprintf("tree_final_%d.rds", i))
  if (file.exists(tree_file)) {
    results$gtree <- readRDS(tree_file)
  }

  if (length(results) == 0) {
    warning(sprintf("No Numbat result files found in %s (iteration %d)", out_dir, i))
  }

  message(sprintf("Loaded Numbat results from: %s (iteration %d)", out_dir, i))

  return(results)
}
