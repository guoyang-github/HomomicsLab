#' scMetabolism Visualization Functions
#'
#' Comprehensive visualization functions for scMetabolism analysis results.
#' Includes dimensionality reduction plots, dot plots, box plots, and heatmaps.
#'
#' @author Yang Guo
#' @date 2026-04-03
#' @version 1.1.0

#' Safely get assay data with Seurat v4/v5 compatibility
#'
#' @param seurat_obj Seurat object
#' @param assay Assay name
#' @param layer Layer/slot name (default: "data")
#' @return Expression matrix
#' @noRd
.get_assay_data_safe <- function(seurat_obj, assay = NULL, layer = "data") {
  if (is.null(assay)) {
    assay <- DefaultAssay(seurat_obj)
  }
  if (packageVersion("SeuratObject") >= package_version("5.0.0")) {
    Seurat::GetAssayData(seurat_obj, assay = assay, layer = layer)
  } else {
    Seurat::GetAssayData(seurat_obj, assay = assay, slot = layer)
  }
}

#' DimPlot for Metabolism Pathways
#'
#' Visualize metabolic pathway scores on dimensionality reduction (UMAP/tSNE).
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param pathway Metabolic pathway name to visualize
#' @param reduction Dimensionality reduction to use: "umap", "tsne", or "pca" (default: "umap")
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param size Point size (default: 1)
#' @param palette Color palette: "Zissou1", "viridis", "plasma", "magma" (default: "Zissou1")
#' @param pt.shape Point shape (default: 16)
#'
#' @return ggplot object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Basic UMAP plot
#' p <- dimplot_metabolism(seurat_obj, pathway = "Glycolysis / Gluconeogenesis")
#' print(p)
#'
#' # tSNE with custom size
#' p <- dimplot_metabolism(
#'   seurat_obj,
#'   pathway = "Oxidative phosphorylation",
#'   reduction = "tsne",
#'   size = 0.5
#' )
#' }
dimplot_metabolism <- function(
    seurat_obj,
    pathway,
    reduction = "umap",
    assay = "METABOLISM",
    size = 1,
    palette = "Zissou1",
    pt.shape = 16
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Please install ggplot2: install.packages('ggplot2')")
  }

  # Check reduction exists
  reduction <- tolower(reduction)
  if (!reduction %in% names(seurat_obj@reductions)) {
    stop(sprintf("Reduction '%s' not found. Available: %s",
                 reduction, paste(names(seurat_obj@reductions), collapse = ", ")))
  }

  # Check assay exists
  if (!assay %in% names(seurat_obj@assays)) {
    stop(sprintf("Assay '%s' not found", assay))
  }

  # Get coordinates
  coord <- as.data.frame(seurat_obj@reductions[[reduction]]@cell.embeddings)
  coord_names <- colnames(coord)

  # Extract pathway scores (auto-detects Seurat v4/v5)
  scores <- .get_assay_data_safe(seurat_obj, assay = assay, layer = "data")

  if (!pathway %in% rownames(scores)) {
    # Try partial matching
    matches <- grep(pathway, rownames(scores), value = TRUE, ignore.case = TRUE)
    if (length(matches) == 0) {
      stop(sprintf("Pathway '%s' not found in metabolism assay", pathway))
    } else if (length(matches) == 1) {
      message(sprintf("Using matched pathway: %s", matches))
      pathway <- matches
    } else {
      stop(sprintf("Multiple matches found for '%s': %s",
                   pathway, paste(matches, collapse = ", ")))
    }
  }

  # Get pathway scores
  pathway_scores <- as.numeric(scores[pathway, rownames(coord)])
  coord$score <- pathway_scores

  # Create plot
  library(ggplot2)

  # Get color palette
  if (palette == "Zissou1") {
    if (!requireNamespace("wesanderson", quietly = TRUE)) {
      message("wesanderson not installed, using viridis")
      pal <- viridis::viridis(100)
    } else {
      pal <- wesanderson::wes_palette("Zissou1", 100, type = "continuous")
    }
  } else if (palette %in% c("viridis", "plasma", "magma")) {
    pal <- viridis::viridis(100, option = palette)
  } else {
    pal <- viridis::viridis(100)
  }

  # Build plot
  p <- ggplot(coord, aes_string(x = coord_names[1], y = coord_names[2], color = "score")) +
    geom_point(size = size, shape = pt.shape) +
    scale_color_gradientn(colours = pal, name = pathway) +
    theme_bw() +
    theme(
      panel.grid.major = element_blank(),
      panel.grid.minor = element_blank(),
      panel.background = element_blank(),
      axis.line = element_line(colour = "black"),
      aspect.ratio = 1
    ) +
    labs(title = pathway)

  return(p)
}


#' Dot Plot for Metabolism Pathways
#'
#' Create a dot plot showing metabolic pathway activity across cell groups.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param pathways Vector of pathway names to plot (default: top 10 variable)
#' @param group.by Column in metadata for grouping (default: "ident")
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param norm Normalization method: "y" (by pathway), "x" (by group), or "na" (none) (default: "y")
#' @param size_range Size range for dots (default: c(1, 8))
#' @param palette Color palette (default: "Zissou1")
#'
#' @return ggplot object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Plot specific pathways
#' p <- dotplot_metabolism(
#'   seurat_obj,
#'   pathways = c("Glycolysis / Gluconeogenesis", "Oxidative phosphorylation"),
#'   group.by = "cell_type"
#' )
#'
#' # Top 20 pathways by cell type
#' p <- dotplot_metabolism(
#'   seurat_obj,
#'   pathways = get_top_variable_pathways(seurat_obj, 20),
#'   group.by = "cell_type"
#' )
#' }
dotplot_metabolism <- function(
    seurat_obj,
    pathways = NULL,
    group.by = "ident",
    assay = "METABOLISM",
    norm = "y",
    size_range = c(1, 8),
    palette = "Zissou1"
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Please install ggplot2")
  }

  # Get grouping variable
  if (group.by == "ident") {
    groups <- as.character(seurat_obj@active.ident)
  } else {
    if (!group.by %in% colnames(seurat_obj@meta.data)) {
      stop(sprintf("Column '%s' not found in metadata", group.by))
    }
    groups <- as.character(seurat_obj@meta.data[[group.by]])
  }

  # Extract scores (auto-detects Seurat v4/v5)
  scores <- .get_assay_data_safe(seurat_obj, assay = assay, layer = "data")

  # Use top variable pathways if not specified
  if (is.null(pathways)) {
    source(file.path(dirname(sys.frame(1)$ofile), "run_scmetabolism.R"))
    pathways <- get_top_variable_pathways(seurat_obj, n_top = 10, assay = assay)
  }

  # Check pathways exist
  missing <- setdiff(pathways, rownames(scores))
  if (length(missing) > 0) {
    warning(sprintf("Pathways not found: %s", paste(missing, collapse = ", ")))
    pathways <- intersect(pathways, rownames(scores))
    if (length(pathways) == 0) {
      stop("No valid pathways found")
    }
  }

  # Calculate median scores per group
  scores_subset <- scores[pathways, , drop = FALSE]

  plot_data <- do.call(rbind, lapply(pathways, function(p) {
    pathway_scores <- as.numeric(scores_subset[p, ])
    group_stats <- sapply(unique(groups), function(g) {
      idx <- groups == g
      median(pathway_scores[idx], na.rm = TRUE)
    })
    data.frame(
      pathway = p,
      group = names(group_stats),
      score = as.numeric(group_stats),
      stringsAsFactors = FALSE
    )
  }))

  # Normalize
  range01 <- function(x) {
    rng <- range(x, na.rm = TRUE)
    if (rng[2] == rng[1]) return(rep(0.5, length(x)))
    (x - rng[1]) / (rng[2] - rng[1])
  }

  if (norm == "y") {
    # Normalize by pathway (row)
    plot_data <- do.call(rbind, lapply(unique(plot_data$pathway), function(p) {
      sub <- plot_data[plot_data$pathway == p, ]
      sub$score_norm <- range01(sub$score)
      sub
    }))
  } else if (norm == "x") {
    # Normalize by group (column)
    plot_data <- do.call(rbind, lapply(unique(plot_data$group), function(g) {
      sub <- plot_data[plot_data$group == g, ]
      sub$score_norm <- range01(sub$score)
      sub
    }))
  } else {
    plot_data$score_norm <- plot_data$score
  }

  # Create plot
  library(ggplot2)

  # Get color palette
  if (palette == "Zissou1" && requireNamespace("wesanderson", quietly = TRUE)) {
    pal <- wesanderson::wes_palette("Zissou1", 100, type = "continuous")
  } else {
    pal <- viridis::viridis(100)
  }

  p <- ggplot(plot_data, aes(x = group, y = pathway, color = score_norm, size = score_norm)) +
    geom_point() +
    scale_color_gradientn(colours = pal, name = "Score") +
    scale_size(range = size_range, name = "Score") +
    theme_bw() +
    theme(
      axis.text.x = element_text(angle = 45, hjust = 1),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_blank()
    ) +
    labs(x = group.by, y = "Metabolic Pathway")

  return(p)
}


#' Box Plot for Metabolism Pathways
#'
#' Create box plots comparing metabolic pathway activities across groups.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param pathways Vector of pathway names to plot
#' @param group.by Column in metadata for grouping (default: "ident")
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param ncol Number of columns in facet (default: 1)
#' @param fill_color Fill color for boxes (default: "steelblue")
#' @param compare_groups Whether to add statistical comparison (default: FALSE)
#'
#' @return ggplot object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Boxplot by condition
#' p <- boxplot_metabolism(
#'   seurat_obj,
#'   pathways = c("Glycolysis / Gluconeogenesis", "Citrate cycle (TCA cycle)"),
#'   group.by = "condition"
#' )
#'
#' # Multiple pathways, 2 columns
#' p <- boxplot_metabolism(
#'   seurat_obj,
#'   pathways = get_top_variable_pathways(seurat_obj, 6),
#'   ncol = 2
#' )
#' }
boxplot_metabolism <- function(
    seurat_obj,
    pathways,
    group.by = "ident",
    assay = "METABOLISM",
    ncol = 1,
    fill_color = NULL,
    compare_groups = FALSE
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Please install ggplot2")
  }

  # Get grouping variable
  if (group.by == "ident") {
    groups <- as.character(seurat_obj@active.ident)
  } else {
    if (!group.by %in% colnames(seurat_obj@meta.data)) {
      stop(sprintf("Column '%s' not found in metadata", group.by))
    }
    groups <- as.character(seurat_obj@meta.data[[group.by]])
  }

  # Extract scores (auto-detects Seurat v4/v5)
  scores <- .get_assay_data_safe(seurat_obj, assay = assay, layer = "data")

  # Check pathways exist
  missing <- setdiff(pathways, rownames(scores))
  if (length(missing) > 0) {
    warning(sprintf("Pathways not found: %s", paste(missing, collapse = ", ")))
    pathways <- intersect(pathways, rownames(scores))
    if (length(pathways) == 0) {
      stop("No valid pathways found")
    }
  }

  # Prepare data
  plot_data <- do.call(rbind, lapply(pathways, function(p) {
    data.frame(
      pathway = p,
      group = groups,
      score = as.numeric(scores[p, ]),
      stringsAsFactors = FALSE
    )
  }))

  # Create plot
  library(ggplot2)

  if (is.null(fill_color)) {
    p <- ggplot(plot_data, aes(x = group, y = score, fill = group)) +
      geom_boxplot(outlier.shape = NA) +
      geom_jitter(width = 0.2, alpha = 0.3, size = 0.5)
  } else {
    p <- ggplot(plot_data, aes(x = group, y = score)) +
      geom_boxplot(fill = fill_color, outlier.shape = NA) +
      geom_jitter(width = 0.2, alpha = 0.3, size = 0.5)
  }

  p <- p +
    facet_wrap(~pathway, ncol = ncol, scales = "free_y") +
    theme_bw() +
    theme(
      axis.text.x = element_text(angle = 45, hjust = 1),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_blank(),
      legend.position = "right"
    ) +
    labs(x = group.by, y = "Metabolism Score", fill = group.by)

  # Add statistical comparison if requested
  if (compare_groups && length(unique(groups)) == 2) {
    p <- p + ggpubr::stat_compare_means(method = "wilcox.test")
  }

  return(p)
}


#' Heatmap of Metabolism Scores
#'
#' Create a heatmap of metabolic pathway activities.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param pathways Vector of pathway names (default: top 20 variable)
#' @param group.by Column in metadata for annotation (default: "ident")
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param scale Scale data: "row", "column", or "none" (default: "row")
#' @param clustering_method Clustering method (default: "ward.D2")
#' @param show_rownames Whether to show row names (default: TRUE)
#' @param show_colnames Whether to show column names (default: FALSE)
#' @param cellwidth Cell width in points (default: NULL, auto)
#' @param cellheight Cell height in points (default: NULL, auto)
#'
#' @return pheatmap object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' # Basic heatmap
#' heatmap_metabolism(seurat_obj, group.by = "cell_type")
#'
#' # Custom pathways
#' heatmap_metabolism(
#'   seurat_obj,
#'   pathways = c("Glycolysis", "Oxidative phosphorylation", "TCA cycle"),
#'   group.by = "condition"
#' )
#' }
heatmap_metabolism <- function(
    seurat_obj,
    pathways = NULL,
    group.by = "ident",
    assay = "METABOLISM",
    scale = "row",
    clustering_method = "ward.D2",
    show_rownames = TRUE,
    show_colnames = FALSE,
    cellwidth = NULL,
    cellheight = NULL
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("pheatmap", quietly = TRUE)) {
    stop("Please install pheatmap: install.packages('pheatmap')")
  }

  # Get grouping variable
  if (group.by == "ident") {
    groups <- as.character(seurat_obj@active.ident)
  } else {
    if (!group.by %in% colnames(seurat_obj@meta.data)) {
      stop(sprintf("Column '%s' not found in metadata", group.by))
    }
    groups <- as.character(seurat_obj@meta.data[[group.by]])
  }

  # Extract scores (auto-detects Seurat v4/v5)
  scores <- .get_assay_data_safe(seurat_obj, assay = assay, layer = "data")

  # Use top pathways if not specified
  if (is.null(pathways)) {
    source(file.path(dirname(sys.frame(1)$ofile), "run_scmetabolism.R"))
    pathways <- get_top_variable_pathways(seurat_obj, n_top = 20, assay = assay)
  }

  # Check pathways exist
  missing <- setdiff(pathways, rownames(scores))
  if (length(missing) > 0) {
    warning(sprintf("Pathways not found: %s", paste(missing, collapse = ", ")))
    pathways <- intersect(pathways, rownames(scores))
  }

  # Subset and prepare matrix
  mat <- as.matrix(scores[pathways, , drop = FALSE])

  # Create annotation
  annotation_col <- data.frame(
    Group = groups,
    row.names = colnames(mat)
  )

  # For large datasets, sample cells for visualization
  max_cells <- 500
  if (ncol(mat) > max_cells) {
    message(sprintf("Sampling %d cells for heatmap visualization", max_cells))
    set.seed(42)
    sampled_cells <- sample(colnames(mat), max_cells)
    mat <- mat[, sampled_cells, drop = FALSE]
    annotation_col <- annotation_col[sampled_cells, , drop = FALSE]
  }

  # Generate heatmap
  p <- pheatmap::pheatmap(
    mat,
    annotation_col = annotation_col,
    scale = scale,
    clustering_method = clustering_method,
    show_rownames = show_rownames,
    show_colnames = show_colnames,
    cellwidth = cellwidth,
    cellheight = cellheight,
    main = "Metabolic Pathway Activity",
    color = viridis::viridis(100)
  )

  return(p)
}


#' Ridge Plot for Metabolism Pathways
#'
#' Create ridge plots (joy plots) showing distribution of metabolism scores.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param pathways Vector of pathway names to plot
#' @param group.by Column in metadata for grouping (default: "ident")
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param ncol Number of columns (default: 1)
#'
#' @return ggplot object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' ridgeplot_metabolism(
#'   seurat_obj,
#'   pathways = c("Glycolysis / Gluconeogenesis", "Oxidative phosphorylation"),
#'   group.by = "cell_type"
#' )
#' }
ridgeplot_metabolism <- function(
    seurat_obj,
    pathways,
    group.by = "ident",
    assay = "METABOLISM",
    ncol = 1
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("ggridges", quietly = TRUE)) {
    stop("Please install ggridges: install.packages('ggridges')")
  }

  # Get grouping variable
  if (group.by == "ident") {
    groups <- as.character(seurat_obj@active.ident)
  } else {
    if (!group.by %in% colnames(seurat_obj@meta.data)) {
      stop(sprintf("Column '%s' not found in metadata", group.by))
    }
    groups <- as.character(seurat_obj@meta.data[[group.by]])
  }

  # Extract scores (auto-detects Seurat v4/v5)
  scores <- .get_assay_data_safe(seurat_obj, assay = assay, layer = "data")

  # Check pathways exist
  missing <- setdiff(pathways, rownames(scores))
  if (length(missing) > 0) {
    warning(sprintf("Pathways not found: %s", paste(missing, collapse = ", ")))
    pathways <- intersect(pathways, rownames(scores))
    if (length(pathways) == 0) {
      stop("No valid pathways found")
    }
  }

  # Prepare data
  plot_data <- do.call(rbind, lapply(pathways, function(p) {
    data.frame(
      pathway = p,
      group = groups,
      score = as.numeric(scores[p, ]),
      stringsAsFactors = FALSE
    )
  }))

  # Create plot
  library(ggplot2)
  library(ggridges)

  p <- ggplot(plot_data, aes(x = score, y = group, fill = group)) +
    geom_density_ridges(alpha = 0.7) +
    facet_wrap(~pathway, ncol = ncol) +
    theme_bw() +
    theme(
      panel.grid.minor = element_blank(),
      legend.position = "none"
    ) +
    labs(x = "Metabolism Score", y = group.by)

  return(p)
}


#' Violin Plot for Metabolism Pathways
#'
#' Create violin plots comparing metabolic pathway activities.
#'
#' @param seurat_obj Seurat object with scMetabolism results
#' @param pathways Vector of pathway names to plot
#' @param group.by Column in metadata for grouping (default: "ident")
#' @param assay Assay name containing metabolism scores (default: "METABOLISM")
#' @param ncol Number of columns in facet (default: 1)
#' @param pt.size Point size for jitter (default: 0)
#'
#' @return ggplot object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' violinplot_metabolism(
#'   seurat_obj,
#'   pathways = c("Glycolysis / Gluconeogenesis"),
#'   group.by = "cell_type"
#' )
#' }
violinplot_metabolism <- function(
    seurat_obj,
    pathways,
    group.by = "ident",
    assay = "METABOLISM",
    ncol = 1,
    pt.size = 0
) {
  if (!inherits(seurat_obj, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("Please install ggplot2")
  }

  # Get grouping variable
  if (group.by == "ident") {
    groups <- as.character(seurat_obj@active.ident)
  } else {
    if (!group.by %in% colnames(seurat_obj@meta.data)) {
      stop(sprintf("Column '%s' not found in metadata", group.by))
    }
    groups <- as.character(seurat_obj@meta.data[[group.by]])
  }

  # Extract scores (auto-detects Seurat v4/v5)
  scores <- .get_assay_data_safe(seurat_obj, assay = assay, layer = "data")

  # Check pathways exist
  missing <- setdiff(pathways, rownames(scores))
  if (length(missing) > 0) {
    warning(sprintf("Pathways not found: %s", paste(missing, collapse = ", ")))
    pathways <- intersect(pathways, rownames(scores))
    if (length(pathways) == 0) {
      stop("No valid pathways found")
    }
  }

  # Prepare data
  plot_data <- do.call(rbind, lapply(pathways, function(p) {
    data.frame(
      pathway = p,
      group = groups,
      score = as.numeric(scores[p, ]),
      stringsAsFactors = FALSE
    )
  }))

  # Create plot
  library(ggplot2)

  p <- ggplot(plot_data, aes(x = group, y = score, fill = group)) +
    geom_violin(scale = "width") +
    geom_boxplot(width = 0.1, fill = "white", outlier.shape = NA)

  if (pt.size > 0) {
    p <- p + geom_jitter(width = 0.2, size = pt.size, alpha = 0.3)
  }

  p <- p +
    facet_wrap(~pathway, ncol = ncol, scales = "free_y") +
    theme_bw() +
    theme(
      axis.text.x = element_text(angle = 45, hjust = 1),
      panel.grid.minor = element_blank(),
      legend.position = "none"
    ) +
    labs(x = group.by, y = "Metabolism Score")

  return(p)
}
