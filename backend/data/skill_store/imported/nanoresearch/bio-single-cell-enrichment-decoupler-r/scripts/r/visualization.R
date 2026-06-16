# decoupleR Visualization Functions
# ==================================
#
# Visualization functions for decoupleR activity inference results

#' Plot activity heatmap
#'
#' Create heatmap of pathway/TF activities
#'
#' @param acts Activity results from decoupleR
#' @param n_top Number of top sources to show (default: 20)
#' @param scale Scale rows (default: TRUE)
#' @param cluster_cols Cluster columns (default: TRUE)
#' @param cluster_rows Cluster rows (default: TRUE)
#' @param title Plot title
#' @param file Output file path (optional)
#' @return ggplot object or ComplexHeatmap object
#' @export
plot_activity_heatmap <- function(
    acts,
    n_top = 20,
    scale = TRUE,
    cluster_cols = TRUE,
    cluster_rows = TRUE,
    title = "Activity Scores",
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  # Get top sources by mean absolute score
  top_sources <- acts %>%
    dplyr::group_by(source) %>%
    dplyr::summarise(mean_abs = mean(abs(score), na.rm = TRUE)) %>%
    dplyr::arrange(dplyr::desc(mean_abs)) %>%
    head(n_top) %>%
    dplyr::pull(source)

  # Filter to top sources
  acts_filtered <- acts %>%
    dplyr::filter(source %in% top_sources)

  # Use decoupleR's built-in plot function if available
  if (requireNamespace("ComplexHeatmap", quietly = TRUE)) {
    # Reshape to matrix
    mat <- acts_filtered %>%
      dplyr::select(source, condition, score) %>%
      tidyr::pivot_wider(names_from = condition, values_from = score) %>%
      as.data.frame()

    rownames(mat) <- mat$source
    mat$source <- NULL
    mat <- as.matrix(mat)

    if (scale) {
      mat <- t(scale(t(mat)))
    }

    # Create heatmap
    ht <- ComplexHeatmap::Heatmap(
      mat,
      name = "Score",
      cluster_columns = cluster_cols,
      cluster_rows = cluster_rows,
      show_column_names = ncol(mat) < 50,
      row_title = "Source",
      column_title = title
    )

    if (!is.null(file)) {
      pdf(file, width = 12, height = 10)
      ComplexHeatmap::draw(ht)
      dev.off()
      message(sprintf("Heatmap saved to: %s", file))
    }

    return(ht)
  } else {
    # Use ggplot2
    p <- ggplot2::ggplot(acts_filtered, ggplot2::aes(x = condition, y = source, fill = score)) +
      ggplot2::geom_tile() +
      ggplot2::scale_fill_gradient2(low = "blue", mid = "white", high = "red") +
      ggplot2::labs(title = title, x = "Sample", y = "Source") +
      ggplot2::theme_minimal() +
      ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1))

    if (!is.null(file)) {
      ggplot2::ggsave(file, p, width = 12, height = 10)
      message(sprintf("Heatmap saved to: %s", file))
    }

    return(p)
  }
}

#' Plot activity scatter
#'
#' Scatter plot comparing two conditions or methods
#'
#' @param acts Activity results from decoupleR
#' @param x_condition Condition for x-axis
#' @param y_condition Condition for y-axis
#' @param highlight_sources Sources to highlight (optional)
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_activity_scatter <- function(
    acts,
    x_condition,
    y_condition,
    highlight_sources = NULL,
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("ggrepel", quietly = TRUE)) {
    stop("ggrepel package required for label repelling. Install with: install.packages('ggrepel')")
  }

  # Reshape to wide
  acts_wide <- acts %>%
    dplyr::filter(condition %in% c(x_condition, y_condition)) %>%
    dplyr::select(source, condition, score) %>%
    tidyr::pivot_wider(names_from = condition, values_from = score)

  # Create plot
  p <- ggplot2::ggplot(acts_wide, ggplot2::aes(x = .data[[x_condition]], y = .data[[y_condition]])) +
    ggplot2::geom_point(alpha = 0.6, size = 2) +
    ggplot2::geom_abline(intercept = 0, slope = 1, linetype = "dashed", color = "red") +
    ggplot2::labs(
      title = paste("Activity Comparison:", x_condition, "vs", y_condition),
      x = paste(x_condition, "Score"),
      y = paste(y_condition, "Score")
    ) +
    ggplot2::theme_minimal()

  # Add source labels
  if (!is.null(highlight_sources)) {
    acts_highlight <- acts_wide %>%
      dplyr::filter(source %in% highlight_sources)

    p <- p + ggplot2::geom_point(
      data = acts_highlight,
      color = "red",
      size = 3
    ) +
      ggrepel::geom_text_repel(
        data = acts_highlight,
        ggplot2::aes(label = source),
        color = "red"
      )
  } else {
    # Label top outliers
    acts_wide$diff <- abs(acts_wide[[x_condition]] - acts_wide[[y_condition]])
    top_diff <- acts_wide %>%
      dplyr::arrange(dplyr::desc(diff)) %>%
      head(10)

    p <- p + ggrepel::geom_text_repel(
      data = top_diff,
      ggplot2::aes(label = source),
      size = 3,
      max.overlaps = 20
    )
  }

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 8, height = 8)
    message(sprintf("Scatter plot saved to: %s", file))
  }

  return(p)
}

#' Plot top activities
#'
#' Bar plot of top activities for a specific condition
#'
#' @param acts Activity results from decoupleR
#' @param condition Condition to plot (NULL for overall average)
#' @param n_top Number of top activities to show
#' @param color_by_sign Color bars by sign (default: TRUE)
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_top_activities <- function(
    acts,
    condition = NULL,
    n_top = 20,
    color_by_sign = TRUE,
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  # Filter to condition or calculate average
  if (!is.null(condition)) {
    acts_cond <- acts %>%
      dplyr::filter(condition == !!condition)
    title_suffix <- condition
  } else {
    acts_cond <- acts %>%
      dplyr::group_by(source) %>%
      dplyr::summarise(score = mean(score, na.rm = TRUE))
    title_suffix <- "Average"
  }

  # Get top activities
  acts_top <- acts_cond %>%
    dplyr::arrange(dplyr::desc(abs(score))) %>%
    head(n_top) %>%
    dplyr::mutate(
      source = forcats::fct_reorder(source, score),
      sign = ifelse(score > 0, "Positive", "Negative")
    )

  # Create plot
  if (color_by_sign) {
    p <- ggplot2::ggplot(acts_top, ggplot2::aes(x = source, y = score, fill = sign)) +
      ggplot2::scale_fill_manual(values = c("Positive" = "red", "Negative" = "blue"))
  } else {
    p <- ggplot2::ggplot(acts_top, ggplot2::aes(x = source, y = score)) +
      ggplot2::geom_bar(stat = "identity", fill = "steelblue")
  }

  p <- p +
    ggplot2::geom_bar(stat = "identity") +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = paste("Top", n_top, "Activities -", title_suffix),
      x = "Source",
      y = "Activity Score"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "none")

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 8, height = 10)
    message(sprintf("Top activities plot saved to: %s", file))
  }

  return(p)
}

#' Plot activity distribution
#'
#' Distribution of activity scores
#'
#' @param acts Activity results from decoupleR
#' @param group_by Column to group by (default: "source")
#' @param top_n Show top N variable sources
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_activity_distribution <- function(
    acts,
    group_by = "source",
    top_n = 20,
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  # Get top sources by variance
  top_sources <- acts %>%
    dplyr::group_by(source) %>%
    dplyr::summarise(var = var(score, na.rm = TRUE)) %>%
    dplyr::arrange(dplyr::desc(var)) %>%
    head(top_n) %>%
    dplyr::pull(source)

  acts_filtered <- acts %>%
    dplyr::filter(source %in% top_sources)

  p <- ggplot2::ggplot(acts_filtered, ggplot2::aes(x = score, fill = source)) +
    ggplot2::geom_density(alpha = 0.5) +
    ggplot2::facet_wrap(~source, scales = "free_y") +
    ggplot2::labs(
      title = "Activity Score Distributions",
      x = "Score",
      y = "Density"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "none")

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 12, height = 10)
    message(sprintf("Distribution plot saved to: %s", file))
  }

  return(p)
}

#' Plot activity volcano
#'
#' Volcano plot for differential activities
#'
#' @param diff_results Differential results from get_differential_activities
#' @param logfc_col Column with log fold change
#' @param pval_col Column with p-values (if available)
#' @param fc_threshold Fold change threshold (default: 0.5)
#' @param pval_threshold P-value threshold (default: 0.05)
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_activity_volcano <- function(
    diff_results,
    logfc_col = "diff",
    pval_col = NULL,
    fc_threshold = 0.5,
    pval_threshold = 0.05,
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }
  if (!requireNamespace("ggrepel", quietly = TRUE)) {
    stop("ggrepel package required for label repelling. Install with: install.packages('ggrepel')")
  }

  # Prepare data
  plot_data <- diff_results %>%
    dplyr::mutate(
      logfc = .data[[logfc_col]],
      significant = abs(logfc) >= fc_threshold
    )

  if (!is.null(pval_col) && pval_col %in% colnames(diff_results)) {
    plot_data <- plot_data %>%
      dplyr::mutate(
        logpval = -log10(.data[[pval_col]]),
        significant = significant & (logpval >= -log10(pval_threshold))
      )
  } else {
    plot_data$logpval <- abs(plot_data$logfc)
  }

  # Create plot
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = logfc, y = logpval)) +
    ggplot2::geom_point(ggplot2::aes(color = significant), alpha = 0.6, size = 2) +
    ggplot2::scale_color_manual(values = c("TRUE" = "red", "FALSE" = "grey")) +
    ggplot2::geom_vline(xintercept = c(-fc_threshold, fc_threshold), linetype = "dashed") +
    ggplot2::labs(
      title = "Differential Activity Volcano Plot",
      x = "Activity Difference",
      y = ifelse(is.null(pval_col), "|Difference|", "-log10(p-value)")
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(legend.position = "none")

  # Add labels for significant points
  sig_points <- plot_data %>%
    dplyr::filter(significant) %>%
    head(10)

  if (nrow(sig_points) > 0) {
    p <- p + ggrepel::geom_text_repel(
      data = sig_points,
      ggplot2::aes(label = source),
      size = 3
    )
  }

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 10, height = 8)
    message(sprintf("Volcano plot saved to: %s", file))
  }

  return(p)
}

#' Plot activity on reduced dimensions
#'
#' Plot activity scores on UMAP, t-SNE, or PCA
#'
#' @param seurat_obj Seurat object with decoupleR results
#' @param source Source/pathway to plot
#' @param dimred Dimensionality reduction to use (default: "umap")
#' @param label Label cells (default: FALSE)
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_activity_reduced <- function(
    seurat_obj,
    source,
    dimred = "umap",
    label = FALSE,
    file = NULL
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Check if decoupleR results exist
  safe_name <- make.names(paste0("decoupleR_", source))

  if (!safe_name %in% names(seurat_obj@meta.data)) {
    stop(paste("Source", source, "not found in Seurat metadata"))
  }

  # Use Seurat's FeaturePlot
  p <- Seurat::FeaturePlot(
    seurat_obj,
    features = safe_name,
    reduction = dimred,
    label = label,
    cols = c("grey", "red")
  ) +
    ggplot2::labs(title = paste(source, "Activity"))

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 8, height = 8)
    message(sprintf("Reduced dim plot saved to: %s", file))
  }

  return(p)
}

#' Plot method comparison
#'
#' Compare results from multiple methods
#'
#' @param acts Activity results from multiple methods
#' @param source_specific Source to compare (if NULL, uses all)
#' @param method_x First method to compare
#' @param method_y Second method to compare
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_method_comparison <- function(
    acts,
    source_specific = NULL,
    method_x = NULL,
    method_y = NULL,
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  # Filter to specific source if provided
  if (!is.null(source_specific)) {
    acts <- acts %>%
      dplyr::filter(source == source_specific)

    title <- paste("Method Comparison -", source_specific)
  } else {
    title <- "Method Comparison (All Sources)"
  }

  # Check if multiple methods exist
  methods <- unique(acts$statistic)
  if (length(methods) < 2) {
    stop("Need results from multiple methods for comparison")
  }

  # Use specified methods or first two
  if (is.null(method_x)) method_x <- methods[1]
  if (is.null(method_y)) method_y <- methods[2]

  # Create comparison plot
  acts_wide <- acts %>%
    dplyr::filter(statistic %in% c(method_x, method_y)) %>%
    dplyr::select(statistic, source, condition, score) %>%
    tidyr::pivot_wider(names_from = statistic, values_from = score)

  # Plot correlation
  p <- ggplot2::ggplot(acts_wide, ggplot2::aes(x = .data[[method_x]], y = .data[[method_y]])) +
    ggplot2::geom_point(alpha = 0.5) +
    ggplot2::geom_abline(intercept = 0, slope = 1, linetype = "dashed", color = "red") +
    ggplot2::labs(
      title = title,
      x = paste(method_x, "Score"),
      y = paste(method_y, "Score")
    ) +
    ggplot2::theme_minimal()

  # Add correlation coefficient
  cor_val <- cor(acts_wide[[method_x]], acts_wide[[method_y]], use = "complete.obs")
  p <- p + ggplot2::annotate(
    "text",
    x = min(acts_wide[[method_x]], na.rm = TRUE),
    y = max(acts_wide[[method_y]], na.rm = TRUE),
    label = paste("r =", round(cor_val, 3)),
    hjust = 0,
    size = 5
  )

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 8, height = 8)
    message(sprintf("Method comparison plot saved to: %s", file))
  }

  return(p)
}

#' Plot network
#'
#' Visualize network connections for a specific source
#'
#' @param net Network data frame
#' @param source_name Source to visualize
#' @param n_targets Number of targets to show (default: 20)
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_network <- function(
    net,
    source_name,
    n_targets = 20,
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  # Filter to source
  net_source <- net %>%
    dplyr::filter(source == source_name) %>%
    dplyr::arrange(dplyr::desc(abs(weight))) %>%
    head(n_targets)

  if (nrow(net_source) == 0) {
    stop(paste("Source", source_name, "not found in network"))
  }

  # Create lollipop plot
  net_source <- net_source %>%
    dplyr::mutate(
      target = forcats::fct_reorder(target, weight),
      sign = ifelse(weight > 0, "Activation", "Inhibition")
    )

  p <- ggplot2::ggplot(net_source, ggplot2::aes(x = target, y = weight, color = sign)) +
    ggplot2::geom_segment(ggplot2::aes(xend = target, yend = 0), size = 1) +
    ggplot2::geom_point(size = 3) +
    ggplot2::scale_color_manual(values = c("Activation" = "red", "Inhibition" = "blue")) +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = paste(source_name, "Network"),
      x = "Target",
      y = "Weight",
      color = "Mode"
    ) +
    ggplot2::theme_minimal()

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 8, height = 10)
    message(sprintf("Network plot saved to: %s", file))
  }

  return(p)
}

#' Plot consensus score
#'
#' Plot consensus scores across methods
#'
#' @param acts Activity results with multiple methods
#' @param top_n Number of top sources to show
#' @param file Output file path (optional)
#' @return ggplot object
#' @export
plot_consensus_scores <- function(
    acts,
    top_n = 15,
    file = NULL
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 package required")
  }

  # Calculate consensus (mean across methods)
  consensus <- acts %>%
    dplyr::group_by(source, condition) %>%
    dplyr::summarise(
      consensus_score = mean(score, na.rm = TRUE),
      score_sd = sd(score, na.rm = TRUE),
      .groups = "drop"
    )

  # Get top sources
  top_sources <- consensus %>%
    dplyr::group_by(source) %>%
    dplyr::summarise(mean_cons = mean(abs(consensus_score))) %>%
    dplyr::arrange(dplyr::desc(mean_cons)) %>%
    head(top_n) %>%
    dplyr::pull(source)

  # Filter and prepare for plotting
  plot_data <- consensus %>%
    dplyr::filter(source %in% top_sources) %>%
    dplyr::mutate(
      source = forcats::fct_reorder(source, consensus_score, .fun = mean)
    )

  # Create plot
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = source, y = consensus_score)) +
    ggplot2::geom_bar(stat = "identity", fill = "steelblue", alpha = 0.7) +
    ggplot2::geom_errorbar(
      ggplot2::aes(ymin = consensus_score - score_sd, ymax = consensus_score + score_sd),
      width = 0.2
    ) +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = paste("Top", top_n, "Consensus Scores"),
      x = "Source",
      y = "Consensus Score (mean +/- SD)"
    ) +
    ggplot2::theme_minimal()

  if (!is.null(file)) {
    ggplot2::ggsave(file, p, width = 8, height = 10)
    message(sprintf("Consensus plot saved to: %s", file))
  }

  return(p)
}

#' Create comprehensive summary plots
#'
#' Generate multiple plots summarizing decoupleR results
#'
#' @param acts Activity results from decoupleR
#' @param net Network data frame (optional)
#' @param output_dir Output directory for plots
#' @param prefix File prefix
#' @return List of generated plot files
#' @export
plot_decoupler_summary <- function(
    acts,
    net = NULL,
    output_dir = "./decoupler_plots",
    prefix = "decoupler"
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  generated_files <- list()

  # 1. Activity heatmap
  tryCatch({
    file_path <- file.path(output_dir, paste0(prefix, "_heatmap.pdf"))
    plot_activity_heatmap(acts, file = file_path)
    generated_files$heatmap <- file_path
  }, error = function(e) {
    message("Could not create heatmap: ", conditionMessage(e))
  })

  # 2. Top activities for first few conditions
  conditions <- unique(acts$condition)
  generated_files$top_activities <- list()

  for (cond in head(conditions, 5)) {
    tryCatch({
      file_path <- file.path(output_dir, paste0(prefix, "_top_", make.names(cond), ".pdf"))
      plot_top_activities(acts, condition = cond, n_top = 15, file = file_path)
      generated_files$top_activities[[cond]] <- file_path
    }, error = function(e) {
      message("Could not create top activities plot for ", cond, ": ", conditionMessage(e))
    })
  }

  # 3. Activity distribution
  tryCatch({
    file_path <- file.path(output_dir, paste0(prefix, "_distribution.pdf"))
    plot_activity_distribution(acts, file = file_path)
    generated_files$distribution <- file_path
  }, error = function(e) {
    message("Could not create distribution plot: ", conditionMessage(e))
  })

  # 4. Method comparison (if multiple methods)
  if ("statistic" %in% colnames(acts) && length(unique(acts$statistic)) > 1) {
    tryCatch({
      methods <- unique(acts$statistic)
      file_path <- file.path(output_dir, paste0(prefix, "_method_comparison.pdf"))
      plot_method_comparison(acts, method_x = methods[1], method_y = methods[2], file = file_path)
      generated_files$method_comparison <- file_path
    }, error = function(e) {
      message("Could not create method comparison plot: ", conditionMessage(e))
    })
  }

  # 5. Network visualization for top source (if net provided)
  if (!is.null(net)) {
    tryCatch({
      top_source <- acts %>%
        dplyr::group_by(source) %>%
        dplyr::summarise(mean_abs = mean(abs(score))) %>%
        dplyr::arrange(dplyr::desc(mean_abs)) %>%
        dplyr::slice(1) %>%
        dplyr::pull(source)

      file_path <- file.path(output_dir, paste0(prefix, "_network_top.pdf"))
      plot_network(net, source_name = top_source, file = file_path)
      generated_files$network <- file_path
    }, error = function(e) {
      message("Could not create network plot: ", conditionMessage(e))
    })
  }

  message(sprintf("Summary plots saved to: %s", output_dir))
  return(generated_files)
}
