# Visualization Functions for PROGENy
# ===================================
#
# This script provides visualization functions for PROGENy pathway activity results.

#' Plot pathway scores on embedding
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param pathways Character vector of pathway names to plot
#' @param reduction Embedding to use (default: "umap")
#' @param ncol Number of columns for facet (default: 3)
#' @param pt.size Point size (default: 0.5)
#' @return Combined ggplot object
#' @export
plot_pathway_embedding <- function(
    seurat_obj,
    pathways = NULL,
    reduction = "umap",
    ncol = 3,
    pt.size = 0.5
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("patchwork", quietly = TRUE)) {
    stop("patchwork package required. Install with: install.packages('patchwork')")
  }

  if (!("progeny" %in% names(seurat_obj@assays))) {
    stop("No progeny assay found. Run run_progeny() first.")
  }

  if (is.null(pathways)) {
    pathways <- rownames(seurat_obj[["progeny"]])
  }

  # Check which pathways exist
  available_pathways <- rownames(seurat_obj[["progeny"]])
  missing <- setdiff(pathways, available_pathways)
  if (length(missing) > 0) {
    warning("Pathways not found: ", paste(missing, collapse = ", "))
    pathways <- intersect(pathways, available_pathways)
  }

  if (length(pathways) == 0) {
    stop("No valid pathways to plot")
  }

  plots <- Seurat::FeaturePlot(
    seurat_obj,
    features = pathways,
    reduction = reduction,
    ncol = ncol,
    pt.size = pt.size,
    combine = FALSE,
    assay = "progeny"
  )

  # Add titles
  for (i in seq_along(plots)) {
    plots[[i]] <- plots[[i]] + ggtitle(pathways[i])
  }

  return(patchwork::wrap_plots(plots, ncol = ncol))
}

#' Create heatmap of pathway activities by cluster
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param group.by Grouping variable (default: active.ident)
#' @param assay Assay to use (default: "progeny")
#' @param scale Scale rows (default: "row")
#' @param cluster_cols Cluster columns (default: TRUE)
#' @param show_rownames Show row names (default: TRUE)
#' @param show_colnames Show column names (default: TRUE)
#' @return pheatmap object
#' @export
plot_pathway_heatmap <- function(
    seurat_obj,
    group.by = NULL,
    assay = "progeny",
    scale = "row",
    cluster_cols = TRUE,
    show_rownames = TRUE,
    show_colnames = TRUE,
    ...
) {
  if (!requireNamespace("pheatmap", quietly = TRUE)) {
    stop("pheatmap package required")
  }

  if (!(assay %in% names(seurat_obj@assays))) {
    stop("Assay '", assay, "' not found")
  }

  # Get scores matrix (pathways x cells)
  scores <- as.matrix(get_assay_data_compat(seurat_obj, assay = assay))

  # Get grouping
  if (is.null(group.by)) {
    groups <- Seurat::Idents(seurat_obj)
  } else {
    groups <- seurat_obj[[group.by, drop = TRUE]]
  }

  # Calculate average per group manually for cross-version compatibility
  group_names <- unique(as.character(groups))
  avg_scores <- sapply(group_names, function(g) {
    cells <- names(groups)[groups == g]
    if (length(cells) == 0) return(rep(0, nrow(scores)))
    rowMeans(scores[, cells, drop = FALSE], na.rm = TRUE)
  })
  colnames(avg_scores) <- group_names

  # Create heatmap
  pheatmap::pheatmap(
    avg_scores,
    scale = scale,
    cluster_cols = cluster_cols,
    show_rownames = show_rownames,
    show_colnames = show_colnames,
    main = "Pathway Activity by Group",
    ...
  )
}

#' Create violin plot of pathway activities
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param pathways Character vector of pathway names
#' @param group.by Grouping variable (default: active.ident)
#' @param ncol Number of columns (default: 3)
#' @param pt.size Point size (default: 0)
#' @return ggplot object
#' @export
plot_pathway_violin <- function(
    seurat_obj,
    pathways = NULL,
    group.by = NULL,
    ncol = 3,
    pt.size = 0
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (is.null(pathways)) {
    pathways <- rownames(seurat_obj[["progeny"]])
  }

  Seurat::VlnPlot(
    seurat_obj,
    features = pathways,
    group.by = group.by,
    ncol = ncol,
    pt.size = pt.size,
    assay = "progeny"
  )
}

#' Create dot plot of pathway activities
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param pathways Character vector of pathway names
#' @param group.by Grouping variable (default: active.ident)
#' @return ggplot object
#' @export
plot_pathway_dotplot <- function(
    seurat_obj,
    pathways = NULL,
    group.by = NULL
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (is.null(pathways)) {
    pathways <- rownames(seurat_obj[["progeny"]])
  }

  Seurat::DotPlot(
    seurat_obj,
    features = pathways,
    group.by = group.by,
    assay = "progeny"
  ) + Seurat::RotatedAxis()
}

#' Plot correlation between pathways
#'
#' @param seurat_obj Seurat object with progeny assay or scores matrix
#' @param method Correlation method (default: "pearson")
#' @param title Plot title
#' @param ... Additional arguments for pheatmap
#' @return pheatmap object
#' @export
plot_pathway_correlation <- function(
    seurat_obj,
    method = "pearson",
    title = "Pathway Correlation",
    ...
) {
  if (!requireNamespace("pheatmap", quietly = TRUE)) {
    stop("pheatmap package required")
  }

  # Extract scores
  if (inherits(seurat_obj, "Seurat")) {
    if (!"progeny" %in% names(seurat_obj@assays)) {
      stop("No progeny assay found")
    }
    scores <- t(as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny")))
  } else if (is.matrix(seurat_obj) || is.data.frame(seurat_obj)) {
    scores <- as.matrix(seurat_obj)
  } else {
    stop("Input must be Seurat object or matrix")
  }

  # Calculate correlation
  cor_matrix <- cor(scores, method = method)

  # Plot
  pheatmap::pheatmap(
    cor_matrix,
    main = title,
    display_numbers = TRUE,
    number_format = "%.2f",
    ...
  )
}

#' Create scatter plot of two pathways
#'
#' @param seurat_obj Seurat object
#' @param pathway_x Pathway for x-axis
#' @param pathway_y Pathway for y-axis
#' @param group.by Color by this metadata column (optional)
#' @param reduction Use embedding coordinates (optional)
#' @return ggplot object
#' @export
plot_pathway_scatter <- function(
    seurat_obj,
    pathway_x,
    pathway_y,
    group.by = NULL,
    reduction = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!"progeny" %in% names(seurat_obj@assays)) {
    stop("No progeny assay found")
  }

  # Get pathway scores
  scores <- t(as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny")))

  plot_data <- data.frame(
    x = scores[, pathway_x],
    y = scores[, pathway_y]
  )

  if (!is.null(group.by)) {
    plot_data$group <- seurat_obj[[group.by, drop = TRUE]]
  }

  if (!is.null(reduction)) {
    emb <- Seurat::Embeddings(seurat_obj, reduction = reduction)
    plot_data$umap_1 <- emb[, 1]
    plot_data$umap_2 <- emb[, 2]
  }

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = x, y = y))
  if (!is.null(group.by)) {
    p <- p + ggplot2::geom_point(ggplot2::aes(color = group), alpha = 0.5, size = 0.5)
  } else {
    p <- p + ggplot2::geom_point(alpha = 0.5, size = 0.5)
  }
  p <- p + ggplot2::xlab(pathway_x) + ggplot2::ylab(pathway_y) +
    ggplot2::ggtitle(paste(pathway_x, "vs", pathway_y)) +
    ggplot2::theme_minimal()

  return(p)
}

#' Create ridge plot of pathway distributions
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param pathways Character vector of pathway names
#' @param group.by Grouping variable (default: active.ident)
#' @param ncol Number of columns (default: 3)
#' @return ggplot object
#' @export
plot_pathway_ridge <- function(
    seurat_obj,
    pathways = NULL,
    group.by = NULL,
    ncol = 3
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("ggridges", quietly = TRUE)) {
    stop("ggridges package required. Install with: install.packages('ggridges')")
  }

  if (is.null(pathways)) {
    pathways <- rownames(seurat_obj[["progeny"]])
  }

  # Get scores
  scores <- t(as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny")))

  if (is.null(group.by)) {
    group.by <- "ident"
    group_vals <- Seurat::Idents(seurat_obj)
  } else {
    group_vals <- seurat_obj[[group.by, drop = TRUE]]
  }

  # Reshape to long format using base R
  n_cells <- nrow(scores)
  n_pathways <- length(pathways)
  plot_data_long <- data.frame(
    group = rep(group_vals, times = n_pathways),
    pathway = rep(pathways, each = n_cells),
    score = as.vector(scores[, pathways, drop = FALSE])
  )

  ggplot2::ggplot(plot_data_long, ggplot2::aes(x = score, y = pathway, fill = group)) +
    ggridges::geom_density_ridges(alpha = 0.5) +
    ggplot2::theme_minimal() +
    ggplot2::xlab("Pathway Activity Score") +
    ggplot2::ylab("Pathway") +
    ggplot2::ggtitle("Pathway Activity Distributions")
}

#' Create comprehensive pathway summary plot
#'
#' @param seurat_obj Seurat object with progeny assay
#' @param group.by Grouping variable
#' @param reduction Embedding for feature plot
#' @param top_n Number of top pathways to show (default: 6)
#' @param output_file Optional file to save plot
#' @return Combined ggplot object
#' @export
plot_pathway_summary <- function(
    seurat_obj,
    group.by = NULL,
    reduction = "umap",
    top_n = 6,
    output_file = NULL
) {
  # Select top variable pathways
  scores <- t(as.matrix(get_assay_data_compat(seurat_obj, assay = "progeny")))
  var_pathways <- names(sort(apply(scores, 2, var), decreasing = TRUE))[1:min(top_n, ncol(scores))]

  # Create individual plots
  p1 <- plot_pathway_embedding(seurat_obj, pathways = var_pathways[1:min(3, length(var_pathways))],
                                reduction = reduction, ncol = 3)

  p2 <- plot_pathway_violin(seurat_obj, pathways = var_pathways, group.by = group.by, ncol = 3)

  # Combine
  combined <- p1 / p2 + patchwork::plot_annotation(title = "PROGENy Pathway Activity Summary")

  if (!is.null(output_file)) {
    ggplot2::ggsave(output_file, combined, width = 12, height = 10, dpi = 300)
    message("Saved summary plot to ", output_file)
  }

  return(combined)
}

#' Plot pathway activities as bar plot by group
#'
#' @param avg_scores Data frame of average pathway activities (from average_pathway_activity)
#' @param group_col Column name for groups
#' @param title Plot title
#' @return ggplot object
#' @export
plot_pathway_bar <- function(
    avg_scores,
    group_col = NULL,
    title = "Average Pathway Activity by Group"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (is.null(group_col)) {
    group_col <- colnames(avg_scores)[1]
  }

  # Reshape to long format using base R
  pathways <- setdiff(colnames(avg_scores), group_col)
  n_groups <- nrow(avg_scores)
  n_pathways <- length(pathways)

  plot_data <- data.frame(
    group = rep(avg_scores[[group_col]], each = n_pathways),
    pathway = rep(pathways, times = n_groups),
    activity = as.vector(t(avg_scores[, pathways]))
  )

  ggplot2::ggplot(plot_data, ggplot2::aes(x = pathway, y = activity, fill = group)) +
    ggplot2::geom_bar(stat = "identity", position = "dodge") +
    ggplot2::theme_minimal() +
    ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1)) +
    ggplot2::xlab("Pathway") +
    ggplot2::ylab("Average Activity") +
    ggplot2::ggtitle(title)
}

#' Create PROGENy scatter plot showing gene contributions
#'
#' This wraps the progeny::progenyScatter function for easier use
#'
#' @param gene_expression Gene expression data frame
#' @param organism Organism (default: "Human")
#' @param top Number of top genes (default: 100)
#' @param sample_idx Sample/column index to plot (default: 1)
#' @return List of ggplot objects
#' @export
plot_gene_contributions <- function(
    gene_expression,
    organism = "Human",
    top = 100,
    sample_idx = 1
) {
  if (!requireNamespace("progeny", quietly = TRUE)) {
    stop("progeny package required")
  }

  # Get weight matrix
  weight_matrix <- progeny::getModel(organism = organism, top = top)
  weight_matrix <- data.frame(
    names = rownames(weight_matrix),
    row.names = NULL,
    weight_matrix
  )

  # Prepare expression data
  if (is.data.frame(gene_expression)) {
    expr_df <- gene_expression
  } else {
    expr_df <- data.frame(
      gene = rownames(gene_expression),
      gene_expression
    )
  }

  # Validate sample index
  if (sample_idx < 1 || sample_idx >= ncol(expr_df)) {
    stop(sprintf("sample_idx must be between 1 and %d", ncol(expr_df) - 1))
  }

  # Generate plots for specified sample
  plots <- progeny::progenyScatter(
    expr_df[, c(1, sample_idx + 1)],
    weight_matrix,
    statName = "Expression"
  )

  return(plots)
}
