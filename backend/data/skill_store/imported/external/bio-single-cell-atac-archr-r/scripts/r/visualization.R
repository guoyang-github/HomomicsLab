# ArchR Visualization Functions
# =============================
#
# Plotting and visualization functions for ArchR analysis

#' Plot embedding
#'
#' Visualize cells in a 2D embedding (UMAP, t-SNE, etc.)
#'
#' @param proj ArchRProject object
#' @param embedding Name of embedding (default: "UMAP")
#' @param color_by What to color by: "cellColData" or matrix name (default: "cellColData")
#' @param name Column name or feature name to color by (default: "Clusters")
#' @param log2_norm Log2 normalize (default: NULL, auto)
#' @param impute_weights Imputation weights for smoothing (default: NULL)
#' @param pal Color palette (default: NULL)
#' @param size Point size (default: 0.1)
#' @param sample_cells Number of cells to sample (default: NULL)
#' @param highlight_cells Cells to highlight (default: NULL)
#' @param rastr Rasterize plot (default: TRUE)
#' @param quant_cut Quantile cutoffs for color scale (default: c(0.01, 0.99))
#' @param discrete_palette Palette for discrete colors (default: "brewer")
#' @param continuous_palette Palette for continuous colors (default: "blueyellow")
#' @param randomize_random Randomize point order (default: TRUE)
#' @param base_size Base font size (default: 10)
#' @param plot_as Output format: "ggplot" or "plotly" (default: "ggplot")
#' @param width Plot width (default: NULL)
#' @param height Plot height (default: NULL)
#' @return ggplot or plotly object
#' @export
plot_embedding <- function(
    proj,
    embedding = "UMAP",
    color_by = "cellColData",
    name = "Clusters",
    log2_norm = NULL,
    impute_weights = NULL,
    pal = NULL,
    size = 0.1,
    sample_cells = NULL,
    highlight_cells = NULL,
    rastr = TRUE,
    quant_cut = c(0.01, 0.99),
    discrete_palette = "brewer",
    continuous_palette = "blueyellow",
    randomize_random = TRUE,
    base_size = 10,
    plot_as = "ggplot",
    width = NULL,
    height = NULL
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  p <- ArchR::plotEmbedding(
    ArchRProj = proj,
    embedding = embedding,
    colorBy = color_by,
    name = name,
    log2Norm = log2_norm,
    imputeWeights = impute_weights,
    pal = pal,
    size = size,
    sampleCells = sample_cells,
    highlightCells = highlight_cells,
    rastr = rastr,
    quantCut = quant_cut,
    discretePalette = discrete_palette,
    continuousPalette = continuous_palette,
    randomize = randomize_random,
    baseSize = base_size,
    plotAs = plot_as
  )

  return(p)
}

#' Plot gene scores
#'
#' Visualize gene scores on embedding
#'
#' @param proj ArchRProject object
#' @param genes Character vector of gene names
#' @param embedding Name of embedding (default: "UMAP")
#' @param impute Use imputation (default: TRUE)
#' @param log2_norm Log2 normalize (default: TRUE)
#' @param quant_cut Quantile cutoffs (default: c(0, 0.99))
#' @param size Point size (default: 0.1)
#' @param pal Color palette (default: NULL)
#' @param threads Number of threads for imputation (default: 1)
#' @return List of ggplot objects
#' @export
plot_gene_scores <- function(
    proj,
    genes,
    embedding = "UMAP",
    impute = TRUE,
    log2_norm = TRUE,
    quant_cut = c(0, 0.99),
    size = 0.1,
    pal = NULL,
    threads = 1
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Add imputation weights if needed
  if (impute && is.null(ArchR::getImputeWeights(proj))) {
    message("Adding imputation weights...")
    proj <- ArchR::addImputeWeights(proj, threads = threads)
  }

  # Plot each gene
  plots <- lapply(genes, function(gene) {
    tryCatch({
      p <- ArchR::plotEmbedding(
        ArchRProj = proj,
        embedding = embedding,
        colorBy = "GeneScoreMatrix",
        name = gene,
        imputeWeights = if (impute) ArchR::getImputeWeights(proj) else NULL,
        log2Norm = log2_norm,
        quantCut = quant_cut,
        size = size,
        pal = pal
      )
      p[[1]]  # Extract plot from list
    }, error = function(e) {
      message(sprintf("Could not plot gene %s: %s", gene, conditionMessage(e)))
      NULL
    })
  })

  names(plots) <- genes
  plots <- plots[!sapply(plots, is.null)]

  return(plots)
}

#' Plot marker genes heatmap
#'
#' Create heatmap of marker gene scores
#'
#' @param proj ArchRProject object
#' @param marker_genes List of marker genes per cell type
#' @param group_by Grouping column (default: "Clusters")
#' @param use_matrix Matrix to use (default: "GeneScoreMatrix")
#' @param scale_rows Scale rows (default: TRUE)
#' @param cut_off Cutoff for marker detection (default: "FDR <= 0.01")
#' @param return_matrix Return matrix instead of plot (default: FALSE)
#' @return ComplexHeatmap object or matrix
#' @export
plot_marker_heatmap <- function(
    proj,
    marker_genes = NULL,
    group_by = "Clusters",
    use_matrix = "GeneScoreMatrix",
    scale_rows = TRUE,
    cut_off = "FDR <= 0.01",
    return_matrix = FALSE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Get marker features if not provided
  if (is.null(marker_genes)) {
    markers <- ArchR::getMarkerFeatures(
      ArchRProj = proj,
      groupBy = group_by,
      useMatrix = use_matrix
    )

    marker_list <- ArchR::getMarkers(
      markers,
      cutOff = cut_off,
      returnGR = TRUE
    )

    # Extract top markers per group
    marker_genes <- lapply(marker_list, function(x) {
      if (length(x) > 0) {
        head(x$name, 5)
      } else {
        character(0)
      }
    })
  }

  # Flatten marker list
  all_markers <- unique(unlist(marker_genes))
  all_markers <- all_markers[all_markers %in% ArchR::getFeatures(proj, useMatrix = use_matrix)]

  if (length(all_markers) == 0) {
    stop("No valid marker genes found")
  }

  # Get matrix
  mat <- ArchR::getMatrixFromProject(
    proj,
    useMatrix = use_matrix,
    features = all_markers
  )

  # Aggregate by group
  group_vec <- SummarizedExperiment::colData(mat)[[group_by]]
  expr_mat <- assays(mat)[[1]]

  # Calculate mean per group
  group_means <- do.call(cbind, tapply(seq_along(group_vec), group_vec, function(idx) {
    Matrix::rowMeans(expr_mat[, idx, drop = FALSE])
  }))

  if (scale_rows) {
    group_means <- t(scale(t(group_means)))
  }

  if (return_matrix) {
    return(group_means)
  }

  # Create heatmap
  if (!requireNamespace("ComplexHeatmap", quietly = TRUE)) {
    stop("ComplexHeatmap required for heatmap plotting")
  }

  hm <- ComplexHeatmap::Heatmap(
    group_means,
    name = "Expression",
    cluster_columns = TRUE,
    cluster_rows = TRUE,
    show_row_names = nrow(group_means) <= 50,
    column_title = group_by
  )

  return(hm)
}

#' Plot browser track
#'
#' Plot genome browser track for a region
#'
#' @param proj ArchRProject object
#' @param region Genomic region (GRanges or string like "chr1:1000-2000")
#' @param group_by Grouping column (default: "Clusters")
#' @param use_groups Groups to include (default: NULL)
#' @param tile_size Tile size (default: 100)
#' @param annotation Annotation to include (default: "gene")
#' @param pal Color palette (default: NULL)
#' @param base_size Base font size (default: 7)
#' @param sc_atac Whether to plot scATAC signal (default: TRUE)
#' @param sc_rna Whether to plot scRNA signal (default: FALSE)
#' @param gene_symbol Gene symbol for annotation (default: NULL)
#' @param upstream Upstream extension (default: 50000)
#' @param downstream Downstream extension (default: 50000)
#' @return ggplot object
#' @export
plot_browser_track <- function(
    proj,
    region,
    group_by = "Clusters",
    use_groups = NULL,
    tile_size = 100,
    annotation = "gene",
    pal = NULL,
    base_size = 7,
    sc_atac = TRUE,
    sc_rna = FALSE,
    gene_symbol = NULL,
    upstream = 50000,
    downstream = 50000
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Handle gene symbol input
  if (!is.null(gene_symbol)) {
    region <- ArchR::geneAnnotation(proj)$genes
    region <- region[tolower(region$symbol) == tolower(gene_symbol)]
    if (length(region) == 0) {
      stop(sprintf("Gene %s not found", gene_symbol))
    }
  }

  p <- ArchR::plotBrowserTrack(
    ArchRProj = proj,
    region = region,
    groupBy = group_by,
    useGroups = use_groups,
    tileSize = tile_size,
    annotation = annotation,
    pal = pal,
    baseSize = base_size,
    scATAC = sc_atac,
    scRNA = sc_rna,
    upstream = upstream,
    downstream = downstream
  )

  return(p)
}

#' Plot peak2gene heatmap
#'
#' Visualize peak-to-gene links
#'
#' @param proj ArchRProject object
#' @param peak_to_gene_links Peak2GeneLinks object (default: NULL, will retrieve)
#' @param group_by Grouping column (default: "Clusters")
#' @param k_clusters Number of clusters for rows (default: 4)
#' @param pal Color palette (default: NULL)
#' @param limit Maximum value for color scale (default: 0.5)
#' @param return_matrix Return matrix instead of plot (default: FALSE)
#' @return ComplexHeatmap object or matrix
#' @export
plot_peak2gene_heatmap <- function(
    proj,
    peak_to_gene_links = NULL,
    group_by = "Clusters",
    k_clusters = 4,
    pal = NULL,
    limit = 0.5,
    return_matrix = FALSE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Get peak2gene links if not provided
  if (is.null(peak_to_gene_links)) {
    if (is.null(proj@peakSet$Peak2GeneLinks)) {
      stop("Peak2GeneLinks not found. Run addPeak2GeneLinks first.")
    }
    peak_to_gene_links <- proj@peakSet$Peak2GeneLinks
  }

  # Create heatmap
  p <- ArchR::plotPeak2GeneHeatmap(
    ArchRProj = proj,
    groupBy = group_by,
    k = k_clusters,
    pal = pal,
    limit = limit
  )

  return(p)
}

#' Plot enrichment heatmap
#'
#' Visualize motif or feature enrichment
#'
#' @param enrichments Data frame with enrichment results
#' @param cut_off P-value cutoff (default: 0.05)
#' @param n_features Number of top features to show (default: 10)
#' @param pal Color palette (default: NULL)
#' @param name Name for color scale (default: "Enrichment")
#' @return ggplot object
#' @export
plot_enrichment_heatmap <- function(
    enrichments,
    cut_off = 0.05,
    n_features = 10,
    pal = NULL,
    name = "Enrichment"
) {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  # Filter by cutoff
  enrichments <- enrichments[enrichments$FDR <= cut_off, ]

  if (nrow(enrichments) == 0) {
    stop("No significant enrichments found")
  }

  # Get top features per group
  if ("group" %in% colnames(enrichments)) {
    top_features <- do.call(rbind, by(enrichments, enrichments$group, function(x) {
      head(x[order(x$FDR), ], n_features)
    }))
  } else {
    top_features <- head(enrichments[order(enrichments$FDR), ], n_features)
  }

  # Create plot
  p <- ggplot2::ggplot(
    top_features,
    ggplot2::aes(
      x = group,
      y = name,
      fill = -log10(FDR),
      size = mlog10Padj
    )
  ) +
    ggplot2::geom_point(shape = 21) +
    ggplot2::scale_fill_gradient(low = "white", high = "red") +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      x = "Group",
      y = "Feature",
      fill = "-log10(FDR)",
      title = name
    )

  return(p)
}

#' Plot fragment size distribution
#'
#' Plot the distribution of fragment sizes
#'
#' @param proj ArchRProject object
#' @param group_by Grouping column (default: "Sample")
#' @param n_samples Number of samples to plot (default: NULL, all)
#' @param pal Color palette (default: NULL)
#' @param return_data Return data instead of plot (default: FALSE)
#' @return ggplot object or data frame
#' @export
plot_fragment_sizes <- function(
    proj,
    group_by = "Sample",
    n_samples = NULL,
    pal = NULL,
    return_data = FALSE
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  # Get fragment sizes
  frag_sizes <- ArchR::getFragmentSizes(proj)
  group_vec <- ArchR::getCellColData(proj)[[group_by]]

  # Create data frame
  plot_data <- data.frame(
    size = rep(seq_along(frag_sizes), frag_sizes),
    group = rep(group_vec, frag_sizes)
  )

  # Sample if needed
  if (!is.null(n_samples) && n_samples < nrow(plot_data)) {
    plot_data <- plot_data[sample(nrow(plot_data), n_samples), ]
  }

  if (return_data) {
    return(plot_data)
  }

  # Create plot
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = size, fill = group)) +
    ggplot2::geom_density(alpha = 0.5) +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      x = "Fragment Size (bp)",
      y = "Density",
      title = "Fragment Size Distribution"
    )

  return(p)
}

#' Plot TSS enrichment
#'
#' Plot TSS enrichment scores
#'
#' @param proj ArchRProject object
#' @param group_by Grouping column (default: "Sample")
#' @param quantiles Quantiles for lines (default: c(0.05, 0.5, 0.95))
#' @param pal Color palette (default: NULL)
#' @return ggplot object
#' @export
plot_tss_enrichment <- function(
    proj,
    group_by = "Sample",
    quantiles = c(0.05, 0.5, 0.95),
    pal = NULL
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  p <- ArchR::plotTSSEnrichment(
    ArchRProj = proj,
    groupBy = group_by,
    quantiles = quantiles,
    pal = pal
  )

  return(p)
}

#' Plot sample statistics
#'
#' Create a summary plot of sample statistics
#'
#' @param proj ArchRProject object
#' @param metric Metric to plot: "nFrags", "TSSEnrichment", "ReadsInTSS" (default: "nFrags")
#' @param group_by Grouping column (default: "Sample")
#' @param plot_type Type: "violin", "box", "bar" (default: "violin")
#' @return ggplot object
#' @export
plot_sample_stats <- function(
    proj,
    metric = "nFrags",
    group_by = "Sample",
    plot_type = "violin"
) {
  if (!requireNamespace("ArchR", quietly = TRUE)) {
    stop("ArchR package required")
  }

  cell_data <- ArchR::getCellColData(proj)

  if (!metric %in% colnames(cell_data)) {
    stop(sprintf("Metric '%s' not found in cell data", metric))
  }

  plot_data <- data.frame(
    value = cell_data[[metric]],
    group = cell_data[[group_by]]
  )

  # Create plot
  if (plot_type == "violin") {
    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = group, y = value, fill = group)) +
      ggplot2::geom_violin(trim = FALSE, alpha = 0.7) +
      ggplot2::geom_boxplot(width = 0.1, outlier.shape = NA)
  } else if (plot_type == "box") {
    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = group, y = value, fill = group)) +
      ggplot2::geom_boxplot(outlier.shape = NA)
  } else if (plot_type == "bar") {
    summary_data <- aggregate(value ~ group, plot_data, median)
    p <- ggplot2::ggplot(summary_data, ggplot2::aes(x = group, y = value, fill = group)) +
      ggplot2::geom_bar(stat = "identity")
  } else {
    stop("plot_type must be 'violin', 'box', or 'bar'")
  }

  p <- p +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      x = group_by,
      y = metric,
      title = sprintf("%s by %s", metric, group_by)
    ) +
    ggplot2::theme(
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
      legend.position = "none"
    )

  if (metric %in% c("nFrags", "ReadsInTSS")) {
    p <- p + ggplot2::scale_y_log10()
  }

  return(p)
}

#' Create comprehensive QC plots
#'
#' Generate multiple QC plots for ArchR project
#'
#' @param proj ArchRProject object
#' @param output_dir Output directory for plots
#' @param prefix File prefix
#' @return Invisible NULL
#' @export
create_qc_plots <- function(
    proj,
    output_dir = "./archr_qc_plots",
    prefix = "sample"
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  message("Creating QC plots...")

  # Plot 1: Sample stats - nFrags
  p1 <- plot_sample_stats(proj, metric = "nFrags")
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_nfrags.pdf")),
    p1, width = 8, height = 6
  )

  # Plot 2: Sample stats - TSS enrichment
  p2 <- plot_sample_stats(proj, metric = "TSSEnrichment")
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_tss_enrichment.pdf")),
    p2, width = 8, height = 6
  )

  # Plot 3: Fragment size distribution
  p3 <- plot_fragment_sizes(proj, n_samples = 10000)
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_fragment_sizes.pdf")),
    p3, width = 8, height = 6
  )

  # Plot 4: TSS enrichment profile
  p4 <- plot_tss_enrichment(proj)
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_tss_profile.pdf")),
    p4, width = 8, height = 6
  )

  # Plot 5: UMAP if available
  if ("UMAP" %in% names(ArchR::getEmbeddings(proj))) {
    p5 <- plot_embedding(proj, color_by = "cellColData", name = "Sample")
    ggplot2::ggsave(
      file.path(output_dir, paste0(prefix, "_umap_sample.pdf")),
      p5[[1]], width = 8, height = 6
    )

    if ("Clusters" %in% colnames(ArchR::getCellColData(proj))) {
      p6 <- plot_embedding(proj, color_by = "cellColData", name = "Clusters")
      ggplot2::ggsave(
        file.path(output_dir, paste0(prefix, "_umap_clusters.pdf")),
        p6[[1]], width = 8, height = 6
      )
    }
  }

  message(sprintf("QC plots saved to: %s", output_dir))
  invisible(NULL)
}

#' Create comprehensive visualization report
#'
#' Generate all standard plots for ArchR project
#'
#' @param proj ArchRProject object
#' @param marker_genes List of marker genes per cell type
#' @param output_dir Output directory
#' @param prefix File prefix
#' @return Invisible NULL
#' @export
create_archr_plots <- function(
    proj,
    marker_genes = NULL,
    output_dir = "./archr_plots",
    prefix = "sample"
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  message("Creating ArchR visualization report...")

  # QC plots
  create_qc_plots(proj, output_dir, prefix)

  # Marker gene plots if provided
  if (!is.null(marker_genes)) {
    all_genes <- unique(unlist(marker_genes))
    gene_plots <- plot_gene_scores(proj, genes = all_genes)

    for (gene in names(gene_plots)) {
      if (!is.null(gene_plots[[gene]])) {
        ggplot2::ggsave(
          file.path(output_dir, paste0(prefix, "_gene_", gene, ".pdf")),
          gene_plots[[gene]], width = 6, height = 6
        )
      }
    }
  }

  # Marker heatmap if clusters exist
  if ("Clusters" %in% colnames(ArchR::getCellColData(proj))) {
    tryCatch({
      pdf(file.path(output_dir, paste0(prefix, "_marker_heatmap.pdf")),
          width = 10, height = 12)
      plot_marker_heatmap(proj)
      dev.off()
    }, error = function(e) {
      message("Could not create marker heatmap: ", conditionMessage(e))
    })
  }

  message(sprintf("Plots saved to: %s", output_dir))
  invisible(NULL)
}
