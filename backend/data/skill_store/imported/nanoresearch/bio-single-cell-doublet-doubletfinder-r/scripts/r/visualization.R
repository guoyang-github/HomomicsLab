# Visualization Functions for DoubletFinder
# ==========================================
#
# This script provides visualization functions for DoubletFinder results.

#' Plot pK optimization results
#'
#' @param bcmvn Data frame from find.pK() with BCmetric values
#' @param mark_optimal Whether to mark the optimal pK (default: TRUE)
#' @return ggplot object
#' @export
plot_pk_optimization <- function(bcmvn, mark_optimal = TRUE) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required for plotting")
  }

  # Convert pK to numeric if factor
  if (is.factor(bcmvn$pK)) {
    bcmvn$pK_numeric <- as.numeric(as.character(bcmvn$pK))
  } else {
    bcmvn$pK_numeric <- bcmvn$pK
  }

  # Find optimal pK
  optimal_idx <- which.max(bcmvn$BCmetric)
  optimal_pk <- bcmvn$pK_numeric[optimal_idx]
  optimal_bc <- bcmvn$BCmetric[optimal_idx]

  p <- ggplot2::ggplot(bcmvn, ggplot2::aes(x = pK_numeric, y = BCmetric)) +
    ggplot2::geom_line(color = "#41b6c4", linewidth = 1) +
    ggplot2::geom_point(color = "#41b6c4", size = 2) +
    ggplot2::labs(
      title = "pK Optimization (BCmvn)",
      x = "pK (neighborhood size proportion)",
      y = "Mean-Variance Normalized Bimodality Coefficient"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, size = 14, face = "bold"),
      axis.title = ggplot2::element_text(size = 12)
    )

  if (mark_optimal) {
    p <- p +
      ggplot2::geom_point(
        data = bcmvn[optimal_idx, , drop = FALSE],
        ggplot2::aes(x = pK_numeric, y = BCmetric),
        color = "red", size = 4, shape = 18
      ) +
      ggplot2::annotate(
        "text",
        x = optimal_pk,
        y = optimal_bc,
        label = paste("Optimal pK:", optimal_pk),
        vjust = -1,
        color = "red",
        fontface = "bold"
      )
  }

  return(p)
}

#' Visualize doublet predictions on embedding
#'
#' @param seu Seurat object with doublet predictions
#' @param reduction Embedding to use (default: "umap")
#' @param pt.size Point size (default: 0.5)
#' @param label Whether to label clusters (default: TRUE)
#' @return ggplot object
#' @export
plot_doublet_embedding <- function(
    seu,
    reduction = "umap",
    pt.size = 0.5,
    label = TRUE
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat required")
  }

  if (!"doublet" %in% colnames(seu@meta.data)) {
    stop("No doublet predictions found. Run run_doubletfinder() first.")
  }

  # Set colors
  colors <- c("Singlet" = "#2ca02c", "Doublet" = "#d62728")

  p <- Seurat::DimPlot(
    seu,
    group.by = "doublet",
    reduction = reduction,
    pt.size = pt.size,
    label = label,
    cols = colors
  ) +
    ggplot2::ggtitle("DoubletFinder Predictions") +
    ggplot2::theme(plot.title = ggplot2::element_text(hjust = 0.5))

  return(p)
}

#' Plot pANN distribution by doublet status
#'
#' @param seu Seurat object with doublet predictions
#' @return ggplot object
#' @export
plot_pann_distribution <- function(seu) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  # Get pANN column
  pann_col <- grep("^pANN", colnames(seu@meta.data), value = TRUE)[1]

  if (is.na(pann_col)) {
    stop("No pANN scores found. Run run_doubletfinder() first.")
  }

  # Prepare data
  plot_data <- data.frame(
    pANN = seu@meta.data[[pann_col]],
    doublet = seu$doublet
  )

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = pANN, fill = doublet)) +
    ggplot2::geom_density(alpha = 0.6) +
    ggplot2::scale_fill_manual(values = c("Singlet" = "#2ca02c", "Doublet" = "#d62728")) +
    ggplot2::labs(
      title = "pANN Score Distribution",
      x = "Proportion of Artificial Nearest Neighbors (pANN)",
      y = "Density",
      fill = "Prediction"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, size = 14, face = "bold")
    )

  return(p)
}

#' Plot pANN distribution as violin plot
#'
#' @param seu Seurat object with doublet predictions
#' @param group_by Group by this metadata column (optional)
#' @return ggplot object
#' @export
plot_pann_violin <- function(seu, group_by = NULL) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  pann_col <- grep("^pANN", colnames(seu@meta.data), value = TRUE)[1]

  if (is.na(pann_col)) {
    stop("No pANN scores found")
  }

  # Prepare data
  plot_data <- data.frame(
    pANN = seu@meta.data[[pann_col]],
    doublet = seu$doublet
  )

  if (!is.null(group_by)) {
    if (!group_by %in% colnames(seu@meta.data)) {
      stop("Group column '", group_by, "' not found")
    }
    plot_data$group <- seu@meta.data[[group_by]]

    p <- ggplot2::ggplot(
      plot_data,
      ggplot2::aes(x = group, y = pANN, fill = doublet)
    ) +
      ggplot2::geom_violin(position = "dodge") +
      ggplot2::facet_wrap(~doublet, ncol = 1)
  } else {
    p <- ggplot2::ggplot(
      plot_data,
      ggplot2::aes(x = doublet, y = pANN, fill = doublet)
    ) +
      ggplot2::geom_violin()
  }

  p <- p +
    ggplot2::scale_fill_manual(values = c("Singlet" = "#2ca02c", "Doublet" = "#d62728")) +
    ggplot2::labs(
      title = "pANN Scores by Doublet Status",
      x = ifelse(is.null(group_by), "Prediction", group_by),
      y = "pANN Score"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, size = 14, face = "bold")
    )

  return(p)
}

#' Plot doublet rate by cluster
#'
#' @param seu Seurat object with doublet predictions
#' @param cluster_col Cluster column name (default: "seurat_clusters")
#' @return ggplot object
#' @export
plot_doublet_rate_by_cluster <- function(
    seu,
    cluster_col = "seurat_clusters"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  if (!cluster_col %in% colnames(seu@meta.data)) {
    stop("Cluster column '", cluster_col, "' not found")
  }

  # Calculate doublet rate per cluster
  plot_data <- as.data.frame(table(
    seu@meta.data[[cluster_col]],
    seu$doublet
  ))
  colnames(plot_data) <- c("cluster", "doublet", "count")

  # Calculate percentage
  plot_data <- do.call(rbind, lapply(unique(plot_data$cluster), function(c) {
    sub <- plot_data[plot_data$cluster == c, ]
    sub$percent <- sub$count / sum(sub$count) * 100
    return(sub)
  }))

  # Plot doublets only
  plot_data_doublets <- plot_data[plot_data$doublet == "Doublet", ]

  # Preserve original cluster order
  cluster_levels <- as.character(sort(unique(as.numeric(as.character(plot_data_doublets$cluster)))))
  if (all(!is.na(suppressWarnings(as.numeric(cluster_levels))))) {
    plot_data_doublets$cluster <- factor(plot_data_doublets$cluster, levels = cluster_levels)
  }

  p <- ggplot2::ggplot(
    plot_data_doublets,
    ggplot2::aes(x = cluster, y = percent, fill = cluster)
  ) +
    ggplot2::geom_bar(stat = "identity") +
    ggplot2::geom_text(
      ggplot2::aes(label = sprintf("%.1f%%", percent)),
      vjust = -0.5
    ) +
    ggplot2::labs(
      title = "Doublet Rate by Cluster",
      x = "Cluster",
      y = "Doublet Rate (%)"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, size = 14, face = "bold"),
      legend.position = "none"
    )

  return(p)
}

#' Create comprehensive DoubletFinder summary plot
#'
#' @param seu Seurat object with doublet predictions
#' @param sweep_results Results from run_param_sweep (optional)
#' @param reduction Embedding to use (default: "umap")
#' @param output_file Optional file to save plot
#' @return Combined plot object
#' @export
plot_doublet_summary <- function(
    seu,
    sweep_results = NULL,
    reduction = "umap",
    output_file = NULL
) {
  if (!requireNamespace("patchwork", quietly = TRUE)) {
    stop("patchwork package required for combined plots. Install: install.packages('patchwork')")
  }

  # Create individual plots
  p1 <- plot_doublet_embedding(seu, reduction = reduction)
  p2 <- plot_pann_distribution(seu)

  if (!is.null(sweep_results)) {
    p3 <- plot_pk_optimization(sweep_results$bcmvn)
  } else {
    p3 <- NULL
  }

  # Combine plots
  if (is.null(p3)) {
    combined <- p1 / p2
  } else {
    combined <- (p1 + p3) / p2
  }

  combined <- combined +
    patchwork::plot_annotation(
      title = "DoubletFinder Analysis Summary",
      theme = ggplot2::theme(
        plot.title = ggplot2::element_text(hjust = 0.5, size = 16, face = "bold")
      )
    )

  if (!is.null(output_file)) {
    ggplot2::ggsave(output_file, combined, width = 14, height = 10, dpi = 300)
    message("Saved summary plot to ", output_file)
  }

  return(combined)
}

#' Compare doublet predictions with other methods
#'
#' @param seu Seurat object with multiple doublet predictions
#' @param methods Character vector of column names with predictions
#' @return ggplot object
#' @export
plot_method_comparison <- function(seu, methods) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  missing <- setdiff(methods, colnames(seu@meta.data))
  if (length(missing) > 0) {
    stop("Methods not found: ", paste(missing, collapse = ", "))
  }

  # Create comparison matrix
  comparison <- sapply(methods, function(m) {
    as.numeric(seu@meta.data[[m]] == "Doublet")
  })

  # Calculate agreement
  agreement <- rowSums(comparison)
  plot_data <- data.frame(
    n_methods = agreement
  )

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = factor(n_methods))) +
    ggplot2::geom_bar(fill = "steelblue") +
    ggplot2::labs(
      title = "Doublet Prediction Agreement",
      x = "Number of Methods Predicting Doublet",
      y = "Cell Count"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, size = 14, face = "bold")
    )

  return(p)
}
