#' Visualization Functions for scTenifoldKnk Results
#'
#' This module provides plotting functions for visualizing knockdown results,
#' including volcano plots, network plots, and comparison visualizations.
#'
#' @author Based on scTenifoldKnk manuscript analysis
#' @references Osorio et al. (2020). Systematic characterization of gene knockdown
#'   perturbations in single-cell data. bioRxiv.

#' Plot Volcano Plot of Differential Regulation
#'
#' Creates a volcano plot showing the distribution of differentially regulated
#' genes from scTenifoldKnk analysis.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param gKO Character. Name of the knocked-out gene (for title).
#' @param p_cutoff Numeric. P-value cutoff for significance (default: 0.05).
#' @param fc_cutoff Numeric. Fold change cutoff for labeling (default: 2).
#' @param label_top_n Integer. Number of top genes to label (default: 10).
#' @param label_genes Character vector. Specific genes to label (default: NULL).
#' @param save_path Character. Path to save plot (default: NULL).
#' @param width Numeric. Plot width (default: 10).
#' @param height Numeric. Plot height (default: 8).
#'
#' @return ggplot object (invisibly if save_path provided).
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#' plot_volcano(result, gKO = "POU5F1")
#' plot_volcano(result, gKO = "POU5F1", label_top_n = 20, save_path = "volcano.png")
#' }
#'
#' @export
plot_volcano <- function(
    result,
    gKO = NULL,
    p_cutoff = 0.05,
    fc_cutoff = 2,
    label_top_n = 10,
    label_genes = NULL,
    save_path = NULL,
    width = 10,
    height = 8
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Package 'ggplot2' is required for plotting")
  }

  # Extract differential regulation results
  dr <- result$diffRegulation

  # Prepare data for plotting
  df <- data.frame(
    gene = dr$gene,
    Z = dr$Z,
    FC = dr$FC,
    p.value = dr$p.value,
    p.adj = dr$p.adj,
    logP = -log10(dr$p.value),
    significant = dr$p.adj < p_cutoff
  )

  # Determine genes to label
  if (is.null(label_genes)) {
    # Label top genes by significance
    top_genes <- df$gene[order(df$p.adj)][seq_len(min(label_top_n, nrow(df)))]
    df$label <- ifelse(df$gene %in% top_genes, df$gene, "")
  } else {
    df$label <- ifelse(df$gene %in% label_genes, df$gene, "")
  }

  # Create color palette
  df$color <- ifelse(df$significant, "Significant", "Not significant")

  # Create plot
  p <- ggplot2::ggplot(df, ggplot2::aes(x = Z, y = logP)) +
    ggplot2::geom_point(ggplot2::aes(color = color), alpha = 0.6, size = 2) +
    ggplot2::scale_color_manual(
      values = c("Significant" = "red", "Not significant" = "grey50")
    ) +
    ggplot2::geom_hline(
      yintercept = -log10(p_cutoff),
      linetype = "dashed",
      color = "blue",
      alpha = 0.5
    ) +
    ggplot2::geom_vline(
      xintercept = 0,
      linetype = "dashed",
      color = "black",
      alpha = 0.3
    )

  # Add labels if ggrepel is available
  if (requireNamespace("ggrepel", quietly = TRUE)) {
    p <- p + ggrepel::geom_text_repel(
      data = df[df$label != "", ],
      ggplot2::aes(label = label),
      size = 3,
      segment.alpha = 0.3,
      force = 10,
      segment.size = 0.2
    )
  } else {
    p <- p + ggplot2::geom_text(
      data = df[df$label != "", ],
      ggplot2::aes(label = label),
      size = 3,
      check_overlap = TRUE
    )
  }

  # Add title and labels
  title <- if (is.null(gKO)) "Differential Regulation" else paste("In-silico Knockdown:", gKO)

  p <- p + ggplot2::labs(
    title = title,
    subtitle = sprintf("%d significant genes (FDR < %.2f)", sum(df$significant), p_cutoff),
    x = "Z-score",
    y = expression(-log[10](P-value)),
    color = "Significance"
  ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(face = "bold", size = 14),
      plot.subtitle = ggplot2::element_text(size = 11),
      legend.position = "top"
    )

  # Save if path provided
  if (!is.null(save_path)) {
    ggplot2::ggsave(save_path, p, width = width, height = height, dpi = 300)
    message("Plot saved to: ", save_path)
    invisible(p)
  } else {
    return(p)
  }
}

#' Plot Top Affected Genes
#'
#' Creates a bar plot of the top differentially regulated genes.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param n Integer. Number of top genes to show (default: 20).
#' @param direction Character. Which genes to show: "up", "down", or "both" (default: "both").
#' @param color_up Character. Color for upregulated genes (default: "red").
#' @param color_down Character. Color for downregulated genes (default: "blue").
#' @param save_path Character. Path to save plot (default: NULL).
#' @param width Numeric. Plot width (default: 10).
#' @param height Numeric. Plot height (default: 10).
#'
#' @return ggplot object (invisibly if save_path provided).
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "POU5F1")
#' plot_top_genes(result, n = 20)
#' plot_top_genes(result, n = 15, direction = "up", save_path = "top_up.png")
#' }
#'
#' @export
plot_top_genes <- function(
    result,
    n = 20,
    direction = "both",
    color_up = "red",
    color_down = "blue",
    save_path = NULL,
    width = 10,
    height = 10
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Package 'ggplot2' is required for plotting")
  }

  dr <- result$diffRegulation

  # Filter by direction
  if (direction == "up") {
    dr <- dr[dr$Z > 0, ]
    title_suffix <- "Upregulated"
  } else if (direction == "down") {
    dr <- dr[dr$Z < 0, ]
    title_suffix <- "Downregulated"
  } else {
    title_suffix <- "Affected"
  }

  # Get top n genes by significance
  dr <- dr[order(dr$p.adj), ]
  if (nrow(dr) > n) {
    dr <- dr[seq_len(n), ]
  }

  # Create direction factor for coloring
  dr$direction <- ifelse(dr$Z > 0, "Up", "Down")

  # Create plot
  p <- ggplot2::ggplot(dr, ggplot2::aes(
    x = reorder(gene, -log10(p.adj)),
    y = Z,
    fill = direction
  )) +
    ggplot2::geom_bar(stat = "identity") +
    ggplot2::scale_fill_manual(values = c("Up" = color_up, "Down" = color_down)) +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = paste("Top", n, title_suffix, "Genes"),
      x = "Gene",
      y = "Z-score",
      fill = "Direction"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(face = "bold"),
      axis.text.y = ggplot2::element_text(size = 9)
    )

  # Save if path provided
  if (!is.null(save_path)) {
    ggplot2::ggsave(save_path, p, width = width, height = height, dpi = 300)
    message("Plot saved to: ", save_path)
    invisible(p)
  } else {
    return(p)
  }
}

#' Plot KO Network
#'
#' Plots the egocentric network centered on the knocked-out gene.
#' This is a wrapper around the plotKO function from scTenifoldKnk.
#'
#' @param result List. Output from scTenifoldKnk analysis.
#' @param gKO Character. Gene symbol that was knocked out.
#' @param q Numeric. Edge weight quantile threshold (0-1, default: 0.99).
#' @param annotate Logical. Whether to annotate with enrichment (default: TRUE).
#' @param nCategories Integer. Max enrichment categories to show (default: 20).
#' @param fdrThreshold Numeric. FDR cutoff for enrichment (default: 0.05).
#' @param save_path Character. Path to save plot (default: NULL).
#' @param width Numeric. Plot width in inches (default: 12).
#' @param height Numeric. Plot height in inches (default: 10).
#'
#' @return Invisibly returns NULL. Plot is generated as side effect.
#'
#' @examples
#' \dontrun{
#' result <- scTenifoldKnk(counts, gKO = "TREM2")
#' plot_ko_network(result, gKO = "TREM2")
#' plot_ko_network(result, gKO = "TREM2", annotate = TRUE, save_path = "network.png")
#' }
#'
#' @export
plot_ko_network <- function(
    result,
    gKO,
    q = 0.99,
    annotate = TRUE,
    nCategories = 20,
    fdrThreshold = 0.05,
    save_path = NULL,
    width = 12,
    height = 10
) {
  # Check if required packages are available
  if (!requireNamespace("igraph", quietly = TRUE)) {
    stop("Package 'igraph' is required for network plotting")
  }

  # Set up plot device if saving
  if (!is.null(save_path)) {
    grDevices::png(save_path, width = width * 100, height = height * 100, res = 100)
    on.exit(grDevices::dev.off())
  }

  # NOTE: scTenifoldKnk does not export a plotKO function.
  # Use the built-in basic network plot instead.
  .plot_basic_network(result, gKO, q)

  if (!is.null(save_path)) {
    message("Network plot saved to: ", save_path)
  }

  invisible(NULL)
}

#' Basic Network Plot (Fallback)
#'
#' Internal function for basic network visualization when plotKO is not available.
#'
#' @keywords internal
.plot_basic_network <- function(result, gKO, q = 0.99) {
  # Extract network
  WT <- as.matrix(result$tensorNetworks$WT)

  # Get significant genes
  dr <- result$diffRegulation
  sig_genes <- dr$gene[dr$p.adj < 0.05]

  if (length(sig_genes) == 0) {
    sig_genes <- c(gKO)
  }

  # Add KO gene
  gList <- unique(c(gKO, sig_genes))

  # Subset network
  if (all(gList %in% rownames(WT))) {
    sCluster <- WT[gList, gList]
  } else {
    # Fallback: use available genes
    available <- gList[gList %in% rownames(WT)]
    if (length(available) < 2) {
      message("Insufficient genes for network plot")
      return(NULL)
    }
    sCluster <- WT[available, available]
  }

  # Threshold edges
  threshold <- quantile(abs(sCluster), q, na.rm = TRUE)
  sCluster[abs(sCluster) < threshold] <- 0
  diag(sCluster) <- 0

  # Create igraph object
  edges <- which(sCluster != 0, arr.ind = TRUE)
  if (nrow(edges) == 0) {
    message("No edges remaining after thresholding")
    return(NULL)
  }

  edge_list <- data.frame(
    from = rownames(sCluster)[edges[, 1]],
    to = colnames(sCluster)[edges[, 2]],
    weight = sCluster[edges]
  )

  g <- igraph::graph_from_data_frame(edge_list, directed = TRUE)

  # Plot
  set.seed(1)
  layout <- igraph::layout_with_fr(g)

  igraph::plot.igraph(
    g,
    layout = layout,
    vertex.size = ifelse(igraph::V(g)$name == gKO, 30, 15),
    vertex.color = ifelse(igraph::V(g)$name == gKO, "red", "lightblue"),
    vertex.label.color = "black",
    vertex.label.cex = 0.8,
    edge.arrow.size = 0.3,
    edge.color = ifelse(edge_list$weight > 0, "red", "blue"),
    edge.width = abs(edge_list$weight) * 2,
    main = paste("Network centered on", gKO)
  )
}

#' Plot Comparison Heatmap
#'
#' Creates a heatmap comparing Z-scores across multiple knockdown experiments.
#'
#' @param results_list Named list of scTenifoldKnk results.
#' @param genes Character vector. Genes to include in heatmap (default: top significant).
#' @param n_genes Integer. Number of top genes to include if genes not specified (default: 50).
#' @param cluster_genes Logical. Whether to cluster genes (default: TRUE).
#' @param cluster_knockdowns Logical. Whether to cluster knockdowns (default: TRUE).
#' @param save_path Character. Path to save plot (default: NULL).
#' @param width Numeric. Plot width (default: 10).
#' @param height Numeric. Plot height (default: 12).
#'
#' @return Invisibly returns the matrix used for plotting.
#'
#' @examples
#' \dontrun{
#' genes <- c("POU5F1", "SOX2", "NANOG")
#' results <- run_multiple_knockdowns(counts, genes)
#' plot_comparison_heatmap(results, save_path = "heatmap.png")
#' }
#'
#' @export
plot_comparison_heatmap <- function(
    results_list,
    genes = NULL,
    n_genes = 50,
    cluster_genes = TRUE,
    cluster_knockdowns = TRUE,
    save_path = NULL,
    width = 10,
    height = 12
) {
  # Extract Z-scores for all results
  all_genes <- unique(unlist(lapply(results_list, function(x) x$diffRegulation$gene)))

  # Determine genes to plot
  if (is.null(genes)) {
    # Get genes that are significant in at least one knockdown
    sig_genes_list <- lapply(results_list, function(x) {
      x$diffRegulation$gene[x$diffRegulation$p.adj < 0.05]
    })
    sig_genes <- unique(unlist(sig_genes_list))

    # If too many, take top by max |Z|
    if (length(sig_genes) > n_genes) {
      max_z <- sapply(sig_genes, function(g) {
        zs <- sapply(results_list, function(x) {
          idx <- which(x$diffRegulation$gene == g)
          if (length(idx) > 0) abs(x$diffRegulation$Z[idx]) else 0
        })
        max(zs)
      })
      sig_genes <- sig_genes[order(-max_z)][seq_len(n_genes)]
    }
    genes <- sig_genes
  }

  # Build matrix
  z_matrix <- sapply(results_list, function(x) {
    sapply(genes, function(g) {
      idx <- which(x$diffRegulation$gene == g)
      if (length(idx) > 0) x$diffRegulation$Z[idx] else NA
    })
  })

  rownames(z_matrix) <- genes

  # Create plot
  if (!is.null(save_path)) {
    grDevices::png(save_path, width = width * 100, height = height * 100, res = 100)
    on.exit(grDevices::dev.off())
  }

  # Use pheatmap if available
  if (requireNamespace("pheatmap", quietly = TRUE)) {
    pheatmap::pheatmap(
      z_matrix,
      cluster_rows = cluster_genes,
      cluster_cols = cluster_knockdowns,
      main = "Z-scores Across Knockdowns",
      color = grDevices::colorRampPalette(c("blue", "white", "red"))(100),
      breaks = seq(-max(abs(z_matrix), na.rm = TRUE), max(abs(z_matrix), na.rm = TRUE), length.out = 101),
      na_col = "grey50"
    )
  } else {
    # Fallback to base R heatmap
    stats::heatmap(
      z_matrix,
      Rowv = cluster_genes,
      Colv = cluster_knockdowns,
      main = "Z-scores Across Knockdowns",
      col = grDevices::colorRampPalette(c("blue", "white", "red"))(100),
      scale = "none",
      na.rm = TRUE
    )
  }

  if (!is.null(save_path)) {
    message("Heatmap saved to: ", save_path)
  }

  invisible(z_matrix)
}

#' Plot Prediction vs Experiment
#'
#' Compares scTenifoldKnk predictions with experimental data.
#'
#' @param comparison List. Output from compare_with_experiment().
#' @param save_path Character. Path to save plot (default: NULL).
#' @param width Numeric. Plot width (default: 10).
#' @param height Numeric. Plot height (default: 8).
#'
#' @return ggplot object (invisibly if save_path provided).
#'
#' @examples
#' \dontrun{
#' predicted <- scTenifoldKnk(counts, gKO = "TREM2")
#' comparison <- compare_with_experiment(predicted, experimental_de)
#' plot_prediction_validation(comparison, save_path = "validation.png")
#' }
#'
#' @export
plot_prediction_validation <- function(
    comparison,
    save_path = NULL,
    width = 10,
    height = 8
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Package 'ggplot2' is required for plotting")
  }

  # Prepare data
  df <- comparison$data

  # Create scatter plot
  p <- ggplot2::ggplot(df, ggplot2::aes(x = predicted, y = experimental)) +
    ggplot2::geom_point(alpha = 0.5, color = "steelblue") +
    ggplot2::geom_smooth(method = "lm", color = "red", se = TRUE) +
    ggplot2::labs(
      title = "Prediction vs Experiment",
      subtitle = sprintf(
        "Spearman rho = %.3f, p = %.3e",
        comparison$correlation$rho,
        comparison$correlation$p.value
      ),
      x = "Predicted (scTenifoldKnk Z-score)",
      y = "Experimental (Log2 Fold Change)"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(face = "bold"),
      plot.subtitle = ggplot2::element_text(size = 10)
    )

  # Save if path provided
  if (!is.null(save_path)) {
    ggplot2::ggsave(save_path, p, width = width, height = height, dpi = 300)
    message("Plot saved to: ", save_path)
    invisible(p)
  } else {
    return(p)
  }
}
