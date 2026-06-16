#' NicheNet Visualization Functions
#'
#' Create publication-ready visualizations for NicheNet results.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

#' Plot Ligand Activity Dot Plot
#'
#' Create a dot plot of ligand activities.
#'
#' @param ligand_activities Data frame from predict_ligand_activities
#' @param top_n Number of top ligands to show (default: 20)
#' @param color_by Column to use for color (default: "pearson")
#' @param title Plot title
#'
#' @return ggplot object
#' @export
#'
#' @examples
#' \dontrun{
#' p <- plot_ligand_activity_dotplot(results$ligand_activities, top_n = 15)
#' }
plot_ligand_activity_dotplot <- function(ligand_activities,
                                          top_n = 20,
                                          color_by = "pearson",
                                          title = "Ligand Activities") {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  # Get top ligands
  plot_data <- head(ligand_activities, top_n)
  plot_data$test_ligand <- factor(plot_data$test_ligand,
                                   levels = rev(plot_data$test_ligand))

  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = .data[[color_by]],
                                                y = test_ligand)) +
    ggplot2::geom_point(ggplot2::aes(size = pearson),
                        color = "darkblue", alpha = 0.7) +
    ggplot2::scale_size_continuous(range = c(2, 8)) +
    ggplot2::labs(
      title = title,
      x = ifelse(color_by == "pearson", "Pearson Correlation", color_by),
      y = "Ligand",
      size = "Pearson"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      axis.text.y = ggplot2::element_text(size = 10),
      plot.title = ggplot2::element_text(hjust = 0.5, size = 12, face = "bold")
    )

  return(p)
}


#' Plot Ligand-Target Heatmap
#'
#' Create a heatmap of ligand-target regulatory potential.
#'
#' @param ligand_target_matrix Ligand-target matrix
#' @param ligands Vector of ligands to include
#' @param targets Vector of targets to include (or NULL for top targets)
#' @param n_targets Number of top targets per ligand (default: 50)
#' @param cluster_rows Cluster rows (default: TRUE)
#' @param cluster_cols Cluster columns (default: TRUE)
#' @param title Plot title
#'
#' @return ComplexHeatmap object
#' @export
#'
#' @examples
#' \dontrun{
#' plot_ligand_target_heatmap(ligand_target_matrix,
#'                            ligands = c("TGFB1", "IL1B", "TNF"))
#' }
plot_ligand_target_heatmap <- function(ligand_target_matrix,
                                        ligands,
                                        targets = NULL,
                                        n_targets = 50,
                                        cluster_rows = TRUE,
                                        cluster_cols = TRUE,
                                        title = "Ligand-Target Regulatory Potential") {
  if (!requireNamespace("ComplexHeatmap", quietly = TRUE)) {
    stop("ComplexHeatmap required. Install with: BiocManager::install('ComplexHeatmap')")
  }

  # Filter ligands
  available_ligands <- intersect(ligands, colnames(ligand_target_matrix))
  if (length(available_ligands) == 0) {
    stop("No ligands found in matrix")
  }

  # Get targets
  if (is.null(targets)) {
    targets <- unique(unlist(lapply(available_ligands, function(l) {
      scores <- ligand_target_matrix[, l]
      names(sort(scores, decreasing = TRUE))[1:n_targets]
    })))
  }

  # Extract submatrix
  submat <- ligand_target_matrix[targets, available_ligands, drop = FALSE]
  submat <- t(submat)  # Ligands as rows

  # Plot
  ComplexHeatmap::Heatmap(
    submat,
    name = "Regulatory\nPotential",
    col = viridis::viridis(100),
    cluster_rows = cluster_rows,
    cluster_columns = cluster_cols,
    show_column_names = ncol(submat) <= 50,
    row_title = "Ligands",
    column_title = "Target Genes",
    heatmap_legend_param = list(direction = "horizontal"),
    row_names_gp = grid::gpar(fontsize = 10),
    column_names_gp = grid::gpar(fontsize = 8)
  )
}


#' Plot Ligand-Receptor Heatmap
#'
#' Create a heatmap of ligand-receptor expression.
#'
#' @param lr_network Ligand-receptor network (filtered)
#' @param seurat_obj Seurat object
#' @param sender_celltype Sender cell type
#' @param receiver_celltype Receiver cell type
#' @param group_by Column to group cells by
#' @param title Plot title
#'
#' @return ComplexHeatmap object
#' @export
#'
#' @examples
#' \dontrun{
#' plot_ligand_receptor_heatmap(results$lr_network, seurat_obj,
#'                              sender = "Macrophage", receiver = "T_cell")
#' }
plot_ligand_receptor_heatmap <- function(lr_network,
                                          seurat_obj,
                                          sender_celltype,
                                          receiver_celltype,
                                          group_by = "cell_type",
                                          title = "Ligand-Receptor Expression") {
  if (!requireNamespace("ComplexHeatmap", quietly = TRUE) ||
      !requireNamespace("Seurat", quietly = TRUE)) {
    stop("ComplexHeatmap and Seurat required")
  }

  # Get expression data (safe meta.data subsetting avoids WhichCells NSE edge cases)
  cells <- colnames(seurat_obj)[seurat_obj@meta.data[[group_by]] %in% c(sender_celltype, receiver_celltype)]
  seurat_subset <- subset(seurat_obj, cells = cells)

  # Calculate average expression
  avg_expr <- AverageExpression(seurat_subset, group.by = group_by)[["RNA"]]

  # Get ligands and receptors
  ligands <- unique(lr_network$from)
  receptors <- unique(lr_network$to)

  # Filter to available genes
  ligands <- intersect(ligands, rownames(avg_expr))
  receptors <- intersect(receptors, rownames(avg_expr))

  if (length(ligands) == 0 || length(receptors) == 0) {
    stop("No matching ligands or receptors in expression data")
  }

  # Create expression matrix
  expr_mat <- rbind(
    avg_expr[ligands, sender_celltype, drop = FALSE],
    avg_expr[receptors, receiver_celltype, drop = FALSE]
  )

  # Annotations
  gene_type <- c(rep("Ligand", length(ligands)), rep("Receptor", length(receptors)))
  row_anno <- ComplexHeatmap::rowAnnotation(
    Type = gene_type,
    col = list(Type = c("Ligand" = "darkred", "Receptor" = "darkblue"))
  )

  ComplexHeatmap::Heatmap(
    expr_mat,
    name = "Expression",
    left_annotation = row_anno,
    cluster_rows = FALSE,
    cluster_columns = FALSE,
    row_title = "Genes",
    column_title = "Cell Types",
    heatmap_legend_param = list(direction = "horizontal"),
    row_names_gp = grid::gpar(fontsize = 9)
  )
}


#' Plot Top Ligand Bar Plot
#'
#' Create a bar plot of top ligand activities.
#'
#' @param ligand_activities Data frame from predict_ligand_activities
#' @param top_n Number of top ligands (default: 10)
#' @param title Plot title
#' @param fill_color Bar color (default: "steelblue")
#'
#' @return ggplot object
#' @export
#'
#' @examples
#' \dontrun{
#' plot_top_ligand_barplot(results$ligand_activities, top_n = 15)
#' }
plot_top_ligand_barplot <- function(ligand_activities,
                                     top_n = 10,
                                     title = "Top Ligands by Activity",
                                     fill_color = "steelblue") {
  if (!requireNamespace("ggplot2", quietly = TRUE)) {
    stop("ggplot2 required")
  }

  plot_data <- head(ligand_activities, top_n)
  plot_data$test_ligand <- factor(plot_data$test_ligand,
                                   levels = plot_data$test_ligand)

  p <- ggplot2::ggplot(plot_data,
                       ggplot2::aes(x = test_ligand, y = pearson)) +
    ggplot2::geom_col(fill = fill_color, alpha = 0.8) +
    ggplot2::coord_flip() +
    ggplot2::labs(
      title = title,
      x = "Ligand",
      y = "Pearson Correlation"
    ) +
    ggplot2::theme_minimal() +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, size = 12, face = "bold")
    )

  return(p)
}


#' Plot Target Expression in Receiver
#'
#' Show expression of predicted target genes in receiver cells.
#'
#' @param seurat_obj Seurat object
#' @param targets Vector of target genes
#' @param receiver_celltype Receiver cell type
#' @param cell_type_col Column in meta.data containing cell type labels (default: "cell_type")
#' @param group_by Column to group by (e.g., condition)
#' @param ncol Number of columns for faceting
#' @param title Plot title
#'
#' @return ggplot object
#' @export
#'
#' @examples
#' \dontrun{
#' plot_target_expression(seurat_obj, targets = c("IL2", "IFNG"),
#'                        receiver_celltype = "T_cell")
#' }
plot_target_expression <- function(seurat_obj,
                                    targets,
                                    receiver_celltype,
                                    cell_type_col = "cell_type",
                                    group_by = NULL,
                                    ncol = 3,
                                    title = "Target Gene Expression") {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat required")
  }

  # Subset to receiver cells (safe meta.data subsetting avoids WhichCells NSE edge cases)
  cells <- colnames(seurat_obj)[seurat_obj@meta.data[[cell_type_col]] %in% receiver_celltype]
  seurat_subset <- subset(seurat_obj, cells = cells)

  # Filter to available targets
  targets <- intersect(targets, rownames(seurat_subset))
  if (length(targets) == 0) {
    stop("No target genes found in Seurat object")
  }

  # Create violin plot
  p <- Seurat::VlnPlot(
    seurat_subset,
    features = targets,
    group.by = group_by,
    ncol = ncol,
    pt.size = 0
  ) +
    ggplot2::theme_minimal() +
    ggplot2::labs(title = title) +
    ggplot2::theme(
      plot.title = ggplot2::element_text(hjust = 0.5, size = 12, face = "bold"),
      axis.text.x = ggplot2::element_text(angle = 45, hjust = 1)
    )

  return(p)
}


#' Export Results to CSV
#'
#' Export NicheNet results to CSV files.
#'
#' @param results NicheNet results list
#' @param output_dir Output directory
#' @param prefix File prefix (default: "nichenet")
#'
#' @return Invisible NULL
#' @export
#'
#' @examples
#' \dontrun{
#' export_nichenet_results(results, "./nichenet_output")
#' }
export_nichenet_results <- function(results, output_dir, prefix = "nichenet") {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  # Export ligand activities
  write.csv(results$ligand_activities,
            file.path(output_dir, paste0(prefix, "_ligand_activities.csv")),
            row.names = FALSE)

  # Export ligand-target pairs
  if (!is.null(results$ligand_targets)) {
    lt_pairs <- data.frame(
      ligand = rep(names(results$ligand_targets),
                   sapply(results$ligand_targets, length)),
      target = unlist(results$ligand_targets)
    )
    write.csv(lt_pairs,
              file.path(output_dir, paste0(prefix, "_ligand_targets.csv")),
              row.names = FALSE)
  }

  # Export LR network
  if (!is.null(results$lr_network)) {
    write.csv(results$lr_network,
              file.path(output_dir, paste0(prefix, "_lr_network.csv")),
              row.names = FALSE)
  }

  message(sprintf("Results exported to %s", output_dir))
  invisible(NULL)
}
