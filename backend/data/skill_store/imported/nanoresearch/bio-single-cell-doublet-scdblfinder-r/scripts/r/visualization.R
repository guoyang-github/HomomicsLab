# scDblFinder Visualization Functions
# ====================================
#
# Visualization functions for scDblFinder doublet detection results

#' Plot doublet scores distribution
#'
#' Plot the distribution of doublet scores
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param color_by Column to color by (optional)
#' @param bins Number of bins for histogram
#' @return ggplot object
#' @export
plot_doublet_score_distribution <- function(
    sce,
    color_by = NULL,
    bins = 50
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  cd <- as.data.frame(SummarizedExperiment::colData(sce))

  if (!"scDblFinder.score" %in% colnames(cd)) {
    stop("No scDblFinder.score found. Run scDblFinder first.")
  }

  # Create base plot
  if (is.null(color_by) || !color_by %in% colnames(cd)) {
    p <- ggplot2::ggplot(cd, ggplot2::aes(x = scDblFinder.score)) +
      ggplot2::geom_histogram(bins = bins, fill = "steelblue", alpha = 0.7) +
      ggplot2::geom_vline(xintercept = mean(cd$scDblFinder.score, na.rm = TRUE),
                          linetype = "dashed", color = "red")
  } else {
    p <- ggplot2::ggplot(cd, ggplot2::aes(x = scDblFinder.score, fill = .data[[color_by]])) +
      ggplot2::geom_histogram(bins = bins, alpha = 0.7, position = "identity")
  }

  p <- p + ggplot2::labs(
    title = "scDblFinder Score Distribution",
    x = "Doublet Score",
    y = "Count"
  ) +
    ggplot2::theme_minimal()

  return(p)
}

#' Plot doublet scores by classification
#'
#' Boxplot/violin plot of scores by doublet/singlet classification
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param plot_type Type of plot: "boxplot" or "violin"
#' @return ggplot object
#' @export
plot_doublet_scores_by_class <- function(
    sce,
    plot_type = c("violin", "boxplot")
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  plot_type <- match.arg(plot_type)

  cd <- as.data.frame(SummarizedExperiment::colData(sce))

  if (!all(c("scDblFinder.score", "scDblFinder.class") %in% colnames(cd))) {
    stop("scDblFinder results not found. Run scDblFinder first.")
  }

  # Create plot
  if (plot_type == "violin") {
    p <- ggplot2::ggplot(cd, ggplot2::aes(x = scDblFinder.class, y = scDblFinder.score, fill = scDblFinder.class)) +
      ggplot2::geom_violin(alpha = 0.7) +
      ggplot2::geom_boxplot(width = 0.1, fill = "white", alpha = 0.5)
  } else {
    p <- ggplot2::ggplot(cd, ggplot2::aes(x = scDblFinder.class, y = scDblFinder.score, fill = scDblFinder.class)) +
      ggplot2::geom_boxplot(alpha = 0.7)
  }

  p <- p + ggplot2::scale_fill_manual(values = c(
    "singlet" = "#1B9E77",
    "doublet" = "#D95F02"
  )) +
    ggplot2::labs(
      title = "Doublet Scores by Classification",
      x = "Classification",
      y = "Doublet Score"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "none")

  return(p)
}

#' Plot doublet map
#'
#' Plot heatmap of observed vs expected doublets
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param colorBy Column for color mapping ("enrichment" or other)
#' @param labelBy Column for cell labels ("observed" or other)
#' @param addSizes Add cluster sizes to labels
#' @return ComplexHeatmap object
#' @export
plot_doublet_map <- function(
    sce,
    colorBy = "enrichment",
    labelBy = "observed",
    addSizes = TRUE,
    ...
) {
  if (!requireNamespace("scDblFinder", quietly = TRUE)) {
    stop("scDblFinder package required")
  }

  # Use scDblFinder's built-in function
  ht <- scDblFinder::plotDoubletMap(sce, colorBy = colorBy, labelBy = labelBy,
                                     addSizes = addSizes, ...)

  return(ht)
}

#' Plot doublet thresholds
#'
#' Plot the threshold optimization for doublet classification
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param ths Thresholds to plot
#' @param return_data Return data instead of plot
#' @return ggplot object or data.frame
#' @export
plot_doublet_thresholds <- function(
    sce,
    ths = (0:100) / 100,
    return_data = FALSE
) {
  if (!requireNamespace("scDblFinder", quietly = TRUE)) {
    stop("scDblFinder package required")
  }

  if (!requireNamespace("SummarizedExperiment", quietly = TRUE)) {
    stop("SummarizedExperiment package required")
  }

  # Extract existing thresholds from SCE metadata instead of re-running scDblFinder
  d <- SummarizedExperiment::metadata(sce)$scDblFinder$thresholds
  if (is.null(d)) {
    stop("scDblFinder thresholds not found in SCE metadata. Ensure scDblFinder was run on this object first.")
  }

  p <- scDblFinder::plotThresholds(d, ths = ths, do.plot = !return_data)

  if (return_data) {
    return(p)
  }

  return(p)
}

#' Plot doublets on dimensionality reduction
#'
#' Plot doublet classifications on UMAP, t-SNE, or PCA
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param dimred Dimensionality reduction to use ("UMAP", "TSNE", "PCA")
#' @param color_by Column to color by (default: scDblFinder.class)
#' @param size Point size
#' @param alpha Point alpha
#' @return ggplot object
#' @export
plot_doublets_reduced <- function(
    sce,
    dimred = "UMAP",
    color_by = "scDblFinder.class",
    size = 0.5,
    alpha = 0.6
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  if (!requireNamespace("SingleCellExperiment", quietly = TRUE)) {
    stop("SingleCellExperiment package required")
  }

  # Get reduced dimensions
  rd <- SingleCellExperiment::reducedDim(sce, dimred)

  if (is.null(rd)) {
    stop(paste("Reduced dimension", dimred, "not found in object"))
  }

  # Create data frame
  df <- as.data.frame(rd)
  colnames(df) <- paste0(dimred, c("_1", "_2"))

  # Add colData
  cd <- as.data.frame(SummarizedExperiment::colData(sce))
  df <- cbind(df, cd)

  # Get column names for plotting
  x_col <- colnames(df)[1]
  y_col <- colnames(df)[2]

  # Create plot
  if (color_by %in% colnames(df)) {
    p <- ggplot2::ggplot(df, ggplot2::aes(x = .data[[x_col]], y = .data[[y_col]], color = .data[[color_by]])) +
      ggplot2::geom_point(size = size, alpha = alpha)

    if (color_by == "scDblFinder.class") {
      p <- p + ggplot2::scale_color_manual(values = c(
        "singlet" = "#1B9E77",
        "doublet" = "#D95F02"
      ))
    }
  } else {
    p <- ggplot2::ggplot(df, ggplot2::aes(x = .data[[x_col]], y = .data[[y_col]])) +
      ggplot2::geom_point(size = size, alpha = alpha, color = "gray")
  }

  p <- p + ggplot2::labs(
    title = paste("Doublets on", dimred),
    x = paste(dimred, "1"),
    y = paste(dimred, "2")
  ) +
    ggplot2::theme_minimal()

  return(p)
}

#' Plot doublet rate by sample
#'
#' Plot doublet rates across multiple samples
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @return ggplot object
#' @export
plot_doublet_rate_by_sample <- function(sce) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  cd <- as.data.frame(SummarizedExperiment::colData(sce))

  if (!"scDblFinder.class" %in% colnames(cd)) {
    stop("scDblFinder results not found")
  }

  # Check for sample info
  sample_col <- NULL
  if ("scDblFinder.sample" %in% colnames(cd)) {
    sample_col <- "scDblFinder.sample"
  } else if ("sample" %in% colnames(cd)) {
    sample_col <- "sample"
  }

  if (is.null(sample_col)) {
    stop("No sample information found in object")
  }

  # Calculate doublet rates by sample
  summary_df <- aggregate(
    cd$scDblFinder.class == "doublet",
    by = list(sample = cd[[sample_col]]),
    FUN = function(x) c(sum(x), length(x), sum(x) / length(x))
  )

  summary_df <- do.call(data.frame, summary_df)
  colnames(summary_df) <- c("sample", "n_doublets", "n_cells", "doublet_rate")

  # Plot
  p <- ggplot2::ggplot(summary_df, ggplot2::aes(x = sample, y = doublet_rate, fill = sample)) +
    ggplot2::geom_bar(stat = "identity") +
    ggplot2::geom_text(ggplot2::aes(label = sprintf("%d/%d", n_doublets, n_cells)),
                       vjust = -0.5, size = 3) +
    ggplot2::labs(
      title = "Doublet Rate by Sample",
      x = "Sample",
      y = "Doublet Rate"
    ) +
    ggplot2::ylim(0, max(summary_df$doublet_rate) * 1.2) +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "none",
                   axis.text.x = ggplot2::element_text(angle = 45, hjust = 1))

  return(p)
}

#' Plot score vs library size
#'
#' Plot relationship between doublet score and library size
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @return ggplot object
#' @export
plot_score_vs_libsize <- function(sce) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  cd <- as.data.frame(SummarizedExperiment::colData(sce))

  if (!"scDblFinder.score" %in% colnames(cd)) {
    stop("scDblFinder.score not found")
  }

  # Calculate library size if not present
  if (!"total_counts" %in% colnames(cd) && !"nCount_RNA" %in% colnames(cd)) {
    cd$total_counts <- colSums(SummarizedExperiment::assay(sce, "counts"))
  } else if ("nCount_RNA" %in% colnames(cd)) {
    cd$total_counts <- cd$nCount_RNA
  }

  p <- ggplot2::ggplot(cd, ggplot2::aes(x = total_counts, y = scDblFinder.score,
                                         color = scDblFinder.class)) +
    ggplot2::geom_point(size = 0.5, alpha = 0.5) +
    ggplot2::scale_color_manual(values = c(
      "singlet" = "#1B9E77",
      "doublet" = "#D95F02"
    )) +
    ggplot2::labs(
      title = "Doublet Score vs Library Size",
      x = "Total Counts",
      y = "Doublet Score"
    ) +
    ggplot2::theme_minimal()

  return(p)
}

#' Create comprehensive summary plots
#'
#' Generate multiple plots summarizing scDblFinder results
#'
#' @param sce SingleCellExperiment with scDblFinder results
#' @param output_dir Output directory for plots
#' @param prefix File prefix
#' @return NULL
#' @export
plot_scdblfinder_summary <- function(
    sce,
    output_dir = "./scdblfinder_plots",
    prefix = "scdblfinder"
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  # 1. Score distribution
  p1 <- plot_doublet_score_distribution(sce)
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_score_distribution.pdf")),
    p1, width = 8, height = 6
  )

  # 2. Scores by class
  p2 <- plot_doublet_scores_by_class(sce)
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_scores_by_class.pdf")),
    p2, width = 6, height = 6
  )

  # 3. Score vs library size
  tryCatch({
    p3 <- plot_score_vs_libsize(sce)
    ggplot2::ggsave(
      file.path(output_dir, paste0(prefix, "_score_vs_libsize.pdf")),
      p3, width = 8, height = 6
    )
  }, error = function(e) {
    cat("Could not create library size plot:", conditionMessage(e), "\n")
  })

  # 4. Doublet rate by sample (if multi-sample)
  if ("scDblFinder.sample" %in% colnames(SummarizedExperiment::colData(sce))) {
    p4 <- plot_doublet_rate_by_sample(sce)
    ggplot2::ggsave(
      file.path(output_dir, paste0(prefix, "_rate_by_sample.pdf")),
      p4, width = 8, height = 6
    )
  }

  # 5. Doublet map (if clusters used)
  if (!is.null(S4Vectors::metadata(sce)$scDblFinder.stats)) {
    tryCatch({
      pdf(file.path(output_dir, paste0(prefix, "_doublet_map.pdf")),
          width = 10, height = 8)
      plot_doublet_map(sce)
      dev.off()
    }, error = function(e) {
      cat("Could not create doublet map:", conditionMessage(e), "\n")
    })
  }

  cat(sprintf("Summary plots saved to: %s\n", output_dir))
}
