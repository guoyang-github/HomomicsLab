# Signac Visualization Functions
# ==============================
#
# Plotting and visualization functions for Signac analysis

#' Plot QC metrics
#'
#' Create violin plots for QC metrics
#'
#' @param seurat_obj Seurat object
#' @param features Features to plot (default: auto-detect available QC metrics)
#' @param group_by Grouping variable (default: NULL)
#' @param pt.size Point size (default: 0.1)
#' @param ncol Number of columns (default: NULL)
#' @param log_scale Log transform count features (default: TRUE)
#' @return ggplot object
#' @export
plot_qc_metrics <- function(
    seurat_obj,
    features = NULL,
    group_by = NULL,
    pt.size = 0.1,
    ncol = NULL,
    log_scale = TRUE
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Auto-detect available QC features
  if (is.null(features)) {
    qc_features <- c("nCount_peaks", "nFeature_peaks", "TSS.enrichment",
                     "nucleosome_signal", "pct_reads_in_peaks", "blacklist_ratio")
    features <- qc_features[qc_features %in% colnames(seurat_obj@meta.data)]
  }

  if (length(features) == 0) {
    stop("No QC features found")
  }

  # Log transform count features if requested
  if (log_scale) {
    for (feat in features) {
      if (grepl("nCount|nFeature", feat)) {
        log_feat <- paste0("log10_", feat)
        seurat_obj@meta.data[[log_feat]] <- log10(seurat_obj@meta.data[[feat]] + 1)
        features[features == feat] <- log_feat
      }
    }
  }

  p <- Seurat::VlnPlot(
    object = seurat_obj,
    features = features,
    group.by = group_by,
    pt.size = pt.size,
    ncol = ncol %||% min(length(features), 3)
  )

  return(p)
}

#' Plot fragment length distribution
#'
#' Plot the distribution of fragment lengths
#'
#' @param seurat_obj Seurat object
#' @param assay Name of assay (default: "peaks")
#' @param n Number of fragments to sample (default: 100000)
#' @param group_by Grouping variable (default: NULL)
#' @param log_y Use log scale for y-axis (default: TRUE)
#' @return ggplot object
#' @export
plot_fragment_distribution <- function(
    seurat_obj,
    assay = "peaks",
    n = 100000,
    group_by = NULL,
    log_y = TRUE
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  # Extract fragment lengths
  fragments <- Signac::Fragments(seurat_obj[[assay]])[[1]]

  # Sample fragments
  if (length(fragments) > n) {
    fragments <- fragments[sample(length(fragments), n)]
  }

  # Get lengths
  lengths <- width(fragments)

  # Create plot data
  plot_data <- data.frame(length = lengths)

  if (!is.null(group_by) && group_by %in% colnames(seurat_obj@meta.data)) {
    # Add group information if available
    cells <- names(fragments)
    plot_data$group <- seurat_obj@meta.data[cells, group_by]
  }

  # Create plot
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = length)) +
    ggplot2::geom_histogram(bins = 100, fill = "steelblue", alpha = 0.7) +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      x = "Fragment Length (bp)",
      y = "Count",
      title = "Fragment Length Distribution"
    ) +
    ggplot2::geom_vline(xintercept = c(147, 294), linetype = "dashed", color = "red")

  if (log_y) {
    p <- p + ggplot2::scale_y_log10()
  }

  return(p)
}

#' Plot TSS enrichment profile
#'
#' Plot TSS enrichment profile across cells
#'
#' @param seurat_obj Seurat object
#' @param assay Name of assay (default: "peaks")
#' @param group_by Grouping variable (default: NULL)
#' @param window Window around TSS (default: 1000)
#' @return ggplot object
#' @export
plot_tss_profile <- function(
    seurat_obj,
    assay = "peaks",
    group_by = NULL,
    window = 1000
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  # Compute TSS enrichment if not present
  if (!"TSS.enrichment" %in% colnames(seurat_obj@meta.data)) {
    seurat_obj <- Signac::TSSEnrichment(seurat_obj, assay = assay)
  }

  # Get TSS enrichment matrix
  tss_matrix <- seurat_obj@assays[[assay]]@positionEnrichment[["TSS"]]

  if (is.null(tss_matrix)) {
    stop("TSS enrichment matrix not found")
  }

  # Aggregate by group
  if (!is.null(group_by) && group_by %in% colnames(seurat_obj@meta.data)) {
    groups <- seurat_obj@meta.data[[group_by]]
    plot_data <- do.call(rbind, lapply(unique(groups), function(g) {
      cells <- colnames(seurat_obj)[groups == g]
      data.frame(
        position = as.numeric(colnames(tss_matrix)),
        enrichment = colMeans(tss_matrix[cells, , drop = FALSE]),
        group = g,
        stringsAsFactors = FALSE
      )
    }))

    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = position, y = enrichment, color = group)) +
      ggplot2::geom_line(size = 1) +
      ggplot2::theme_minimal() +
      ggplot2::labs(
        x = "Distance from TSS (bp)",
        y = "Enrichment",
        title = "TSS Enrichment Profile",
        color = group_by
      )
  } else {
    plot_data <- data.frame(
      position = as.numeric(colnames(tss_matrix)),
      enrichment = colMeans(tss_matrix),
      stringsAsFactors = FALSE
    )

    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = position, y = enrichment)) +
      ggplot2::geom_line(color = "steelblue", size = 1) +
      ggplot2::theme_minimal() +
      ggplot2::labs(
        x = "Distance from TSS (bp)",
        y = "Enrichment",
        title = "TSS Enrichment Profile"
      )
  }

  return(p)
}

#' Plot nucleosome signal distribution
#'
#' Plot distribution of nucleosome signal scores
#'
#' @param seurat_obj Seurat object
#' @param group_by Grouping variable (default: NULL)
#' @param bins Number of histogram bins (default: 50)
#' @return ggplot object
#' @export
plot_nucleosome_signal <- function(
    seurat_obj,
    group_by = NULL,
    bins = 50
) {
  if (!"nucleosome_signal" %in% colnames(seurat_obj@meta.data)) {
    stop("Nucleosome signal not computed. Run compute_qc_metrics first.")
  }

  plot_data <- data.frame(
    signal = seurat_obj$nucleosome_signal
  )

  if (!is.null(group_by) && group_by %in% colnames(seurat_obj@meta.data)) {
    plot_data$group <- seurat_obj@meta.data[[group_by]]

    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = signal, fill = group)) +
      ggplot2::geom_histogram(bins = bins, alpha = 0.7, position = "identity")
  } else {
    p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = signal)) +
      ggplot2::geom_histogram(bins = bins, fill = "steelblue", alpha = 0.7)
  }

  p <- p +
    ggplot2::theme_minimal() +
    ggplot2::labs(
      x = "Nucleosome Signal",
      y = "Count",
      title = "Nucleosome Signal Distribution"
    ) +
    ggplot2::geom_vline(xintercept = 4, linetype = "dashed", color = "red")

  return(p)
}

#' Plot UMAP with gene activity
#'
#' Plot UMAP colored by gene activity scores
#'
#' @param seurat_obj Seurat object
#' @param genes Character vector of gene names
#' @param reduction Name of reduction (default: "umap")
#' @param ncol Number of columns (default: NULL)
#' @param pt.size Point size (default: 0.1)
#' @return ggplot object or list
#' @export
plot_gene_activity_umap <- function(
    seurat_obj,
    genes,
    reduction = "umap",
    ncol = NULL,
    pt.size = 0.1
) {
  if (!"RNA" %in% names(seurat_obj@assays)) {
    stop("Gene activity matrix not found. Run create_gene_activity first.")
  }

  # Check which genes are available
  available_genes <- genes[genes %in% rownames(seurat_obj[["RNA"]])]
  missing_genes <- genes[!genes %in% rownames(seurat_obj[["RNA"]])]

  if (length(missing_genes) > 0) {
    warning(sprintf("Genes not found: %s", paste(missing_genes, collapse = ", ")))
  }

  if (length(available_genes) == 0) {
    stop("No valid genes found")
  }

  # Plot
  p <- Seurat::FeaturePlot(
    object = seurat_obj,
    features = available_genes,
    reduction = reduction,
    ncol = ncol %||% min(length(available_genes), 3),
    pt.size = pt.size
  )

  return(p)
}

#' Plot coverage track
#'
#' Plot coverage for a genomic region
#'
#' @param seurat_obj Seurat object
#' @param region Genomic region (string like "chr1:1000-2000" or gene name)
#' @param group_by Grouping variable (default: "seurat_clusters")
#' @param assay Name of assay (default: "peaks")
#' @param features Gene features to show (default: NULL)
#' @param expression Assay for expression (default: "RNA")
#' @param extend Upstream/downstream extension (default: 5000)
#' @param window Window size (default: NULL)
#' @return ggplot object
#' @export
plot_coverage_track <- function(
    seurat_obj,
    region,
    group_by = "seurat_clusters",
    assay = "peaks",
    features = NULL,
    expression = "RNA",
    extend = 5000,
    window = NULL
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  # Try to get gene region if gene name provided
  if (!grepl(":", region)) {
    # Assume it's a gene name
    annotation <- Signac::Annotation(seurat_obj[[assay]])
    gene_idx <- which(annotation$gene_name == region)
    if (length(gene_idx) > 0) {
      gene_range <- annotation[gene_idx]
      region <- sprintf("%s:%d-%d",
                       seqnames(gene_range)[1],
                       start(gene_range)[1] - extend,
                       end(gene_range)[1] + extend)
      if (is.null(features)) {
        features <- region
      }
    }
  }

  p <- Signac::CoveragePlot(
    object = seurat_obj,
    region = region,
    group.by = group_by,
    assay = assay,
    features = features,
    expression.assay = expression,
    extend.upstream = extend,
    extend.downstream = extend,
    window = window
  )

  return(p)
}

#' Plot peak-gene links
#'
#' Visualize links between peaks and genes
#'
#' @param seurat_obj Seurat object with links
#' @param region Genomic region to plot
#' @param group_by Grouping variable (default: "seurat_clusters")
#' @param min_coaccess Minimum co-accessibility (default: 0.25)
#' @return ggplot object
#' @export
plot_peak_gene_links <- function(
    seurat_obj,
    region,
    group_by = "seurat_clusters",
    min_coaccess = 0.25
) {
  if (!requireNamespace("Signac", quietly = TRUE)) {
    stop("Signac package required")
  }

  if (is.null(seurat_obj@assays[["peaks"]]@links)) {
    stop("Peak-gene links not found. Run LinkPeaks first.")
  }

  p <- Signac::CoveragePlot(
    object = seurat_obj,
    region = region,
    group.by = group_by,
    features = Signac::LinkedGene(seurat_obj@assays[["peaks"]]@links),
    expression.assay = "RNA",
    min.cutoff = min_coaccess
  )

  return(p)
}

#' Plot integration results
#'
#' Plot scRNA-scATAC integration results
#'
#' @param seurat_obj Seurat object
#' @param reduction Name of reduction (default: "umap")
#' @param group_by Grouping variable (default: "predicted.id")
#' @param label Label clusters (default: TRUE)
#' @return ggplot object
#' @export
plot_integration_results <- function(
    seurat_obj,
    reduction = "umap",
    group_by = "predicted.id",
    label = TRUE
) {
  if (!group_by %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("Column '%s' not found in metadata", group_by))
  }

  p <- Seurat::DimPlot(
    object = seurat_obj,
    reduction = reduction,
    group.by = group_by,
    label = label,
    pt.size = 0.1
  )

  return(p)
}

#' Create comprehensive QC report
#'
#' Generate multiple QC plots
#'
#' @param seurat_obj Seurat object
#' @param output_dir Output directory
#' @param prefix File prefix
#' @param group_by Grouping variable (default: NULL)
#' @return Invisible NULL
#' @export
create_qc_report <- function(
    seurat_obj,
    output_dir = "./signac_qc",
    prefix = "sample",
    group_by = NULL
) {
  if (!dir.exists(output_dir)) {
    dir.create(output_dir, recursive = TRUE)
  }

  message("Creating QC report...")

  # Plot 1: QC metrics violin plots
  p1 <- plot_qc_metrics(seurat_obj, group_by = group_by)
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_qc_violins.pdf")),
    p1, width = 12, height = 8
  )

  # Plot 2: Scatter plots
  p2 <- Seurat::FeatureScatter(
    seurat_obj,
    feature1 = "nCount_peaks",
    feature2 = "TSS.enrichment",
    group.by = group_by
  )
  ggplot2::ggsave(
    file.path(output_dir, paste0(prefix, "_qc_scatter.pdf")),
    p2, width = 8, height = 6
  )

  # Plot 3: Nucleosome signal
  if ("nucleosome_signal" %in% colnames(seurat_obj@meta.data)) {
    p3 <- plot_nucleosome_signal(seurat_obj, group_by = group_by)
    ggplot2::ggsave(
      file.path(output_dir, paste0(prefix, "_nucleosome_signal.pdf")),
      p3, width = 8, height = 6
    )
  }

  # Plot 4: UMAP if available
  if ("umap" %in% names(seurat_obj@reductions)) {
    p4 <- Seurat::DimPlot(seurat_obj, reduction = "umap", group.by = group_by)
    ggplot2::ggsave(
      file.path(output_dir, paste0(prefix, "_umap.pdf")),
      p4, width = 8, height = 6
    )
  }

  message(sprintf("QC report saved to: %s", output_dir))
  invisible(NULL)
}

#' Create marker gene plot
#'
#' Plot marker genes on UMAP and violin plots
#'
#' @param seurat_obj Seurat object
#' @param markers Named list of marker genes
#' @param reduction Name of reduction (default: "umap")
#' @param ncol Number of columns (default: 3)
#' @return List of ggplot objects
#' @export
plot_marker_genes <- function(
    seurat_obj,
    markers,
    reduction = "umap",
    ncol = 3
) {
  all_markers <- unlist(markers)

  # Check availability
  if ("RNA" %in% names(seurat_obj@assays)) {
    available <- all_markers[all_markers %in% rownames(seurat_obj[["RNA"]])]
  } else {
    available <- character(0)
  }

  plots <- list()

  if (length(available) > 0) {
    # UMAP feature plots
    plots$umap <- Seurat::FeaturePlot(
      seurat_obj,
      features = available,
      reduction = reduction,
      ncol = ncol
    )

    # Violin plots
    plots$violin <- Seurat::VlnPlot(
      seurat_obj,
      features = available,
      ncol = ncol
    )
  }

  return(plots)
}
