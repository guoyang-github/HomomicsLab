#' Utility Functions for Monocle3 Analysis
#'
#' Helper functions that add logic beyond official monocle3 accessors.
#'
#' Author: Yang Guo
#' Date: 2026-05-21

#==============================================================================
# Trajectory Graph Utilities
#==============================================================================

#' Get Root Nodes
#'
#' @param cds A cell_data_set object
#' @param reduction_method Dimensionality reduction method (default: "UMAP")
#' @return Integer indices of root nodes in the igraph object
#' @export
get_root_nodes <- function(cds, reduction_method = "UMAP") {
  g <- principal_graph(cds)[[reduction_method]]
  root_pr_nodes <- cds@principal_graph_aux[[reduction_method]]$root_pr_nodes
  root_nodes <- which(names(igraph::V(g)) %in% root_pr_nodes)
  return(root_nodes)
}

#' Get Branch Nodes
#'
#' Returns graph vertices with degree > 2, excluding root nodes.
#'
#' @param cds A cell_data_set object
#' @param reduction_method Dimensionality reduction method (default: "UMAP")
#' @return Integer indices of branch nodes
#' @export
get_branch_nodes <- function(cds, reduction_method = "UMAP") {
  g <- principal_graph(cds)[[reduction_method]]
  branch_points <- which(igraph::degree(g) > 2)
  root_nodes <- get_root_nodes(cds, reduction_method)
  branch_points <- branch_points[branch_points %in% root_nodes == FALSE]
  return(branch_points)
}

#' Get Leaf Nodes
#'
#' Returns graph vertices with degree == 1, excluding root nodes.
#'
#' @param cds A cell_data_set object
#' @param reduction_method Dimensionality reduction method (default: "UMAP")
#' @return Integer indices of leaf nodes
#' @export
get_leaf_nodes <- function(cds, reduction_method = "UMAP") {
  g <- principal_graph(cds)[[reduction_method]]
  leaves <- which(igraph::degree(g) == 1)
  root_nodes <- get_root_nodes(cds, reduction_method)
  leaves <- leaves[leaves %in% root_nodes == FALSE]
  return(leaves)
}

#==============================================================================
# Cluster and Partition Utilities
#==============================================================================

#' Get Cluster Assignments
#'
#' Extracts cluster vector from internal S4 structure.
#'
#' @param cds A cell_data_set object
#' @param reduction_method Dimensionality reduction method (default: "UMAP")
#' @return Named vector of cluster assignments
#' @export
get_clusters <- function(cds, reduction_method = "UMAP") {
  clusters <- cds@clusters[[reduction_method]]$clusters
  return(clusters)
}

#' Get Partition Assignments
#'
#' @param cds A cell_data_set object
#' @param reduction_method Dimensionality reduction method (default: "UMAP")
#' @return Named vector of partition assignments
#' @export
get_partitions <- function(cds, reduction_method = "UMAP") {
  partitions <- cds@clusters[[reduction_method]]$partitions
  return(partitions)
}

#==============================================================================
# Gene and Marker Utilities
#==============================================================================

#' Get Top Marker Genes
#'
#' Runs top_markers() and filters by fraction_expressing >= 0.10,
#' then selects top N per group by pseudo_R2.
#'
#' @param cds A cell_data_set object
#' @param group_cells_by Column to group cells by (default: "cluster")
#' @param n_markers Number of markers per group (default: 3)
#' @param reference_cells Number of reference cells (default: 100)
#' @param cores Number of cores
#' @return Data frame with top marker genes
#' @export
get_top_markers <- function(cds,
                           group_cells_by = "cluster",
                           n_markers = 3,
                           reference_cells = 100,
                           cores = 1) {
  marker_test_res <- top_markers(
    cds,
    group_cells_by = group_cells_by,
    reference_cells = reference_cells,
    cores = cores
  )

  required_cols <- c("fraction_expressing", "pseudo_R2", "cell_group")
  missing_cols <- setdiff(required_cols, colnames(marker_test_res))
  if (length(missing_cols) > 0) {
    stop("top_markers() output missing required columns: ", paste(missing_cols, collapse = ", "))
  }

  top_markers_df <- marker_test_res %>%
    dplyr::filter(fraction_expressing >= 0.10) %>%
    dplyr::group_by(cell_group) %>%
    dplyr::slice_max(order_by = pseudo_R2, n = n_markers, with_ties = FALSE)

  return(top_markers_df)
}

#==============================================================================
# Cell Metadata Utilities
#==============================================================================

#' Annotate Clusters
#'
#' Maps cluster IDs to annotations via a named vector.
#'
#' @param cds A cell_data_set object
#' @param cluster_annotations Named vector: names = cluster IDs, values = annotations
#' @param annotation_col Name for the new annotation column (default: "cell_type")
#' @return Updated CDS
#' @export
annotate_clusters <- function(cds,
                             cluster_annotations,
                             annotation_col = "cell_type") {
  clusters <- get_clusters(cds)

  annotations <- cluster_annotations[as.character(clusters)]
  names(annotations) <- names(clusters)

  # Warn about unmatched clusters to prevent silent NA propagation
  unmatched <- unique(clusters[is.na(annotations)])
  if (length(unmatched) > 0) {
    warning("No annotation found for clusters: ", paste(unmatched, collapse = ", "))
  }

  colData(cds)[[annotation_col]] <- annotations

  return(cds)
}

#==============================================================================
# Data Export Utilities
#==============================================================================

#' Export Pseudotime Data
#'
#' Exports pseudotime values combined with all cell metadata to CSV.
#'
#' @param cds A cell_data_set object
#' @param output_file Output CSV file path
#' @export
export_pseudotime_data <- function(cds, output_file) {
  pt <- pseudotime(cds)
  df <- data.frame(
    cell_id = names(pt),
    pseudotime = pt
  )

  cell_meta <- as.data.frame(colData(cds))

  # Avoid duplicate column names (e.g., if colData already has "cell_id" or "pseudotime")
  overlap <- intersect(colnames(df), colnames(cell_meta))
  if (length(overlap) > 0) {
    cell_meta <- cell_meta[, setdiff(colnames(cell_meta), overlap), drop = FALSE]
    message("Removed duplicate columns from metadata: ", paste(overlap, collapse = ", "))
  }

  df <- cbind(df, cell_meta)

  write.csv(df, output_file, row.names = FALSE)
  message("Pseudotime data exported to ", output_file)
}

#==============================================================================
# Quality Control Utilities
#==============================================================================

#' Check CDS Completeness
#'
#' Checks which analysis steps have been run on the CDS.
#'
#' @param cds A cell_data_set object
#' @param reduction_method Dimensionality reduction method to check (default: "UMAP")
#' @return Named list with boolean flags:
#'   preprocessed, reduced_dims, clustered, graph_learned, pseudotime_ordered
#' @export
check_cds_completeness <- function(cds, reduction_method = "UMAP") {
  results <- list()

  results$preprocessed <- !is.null(cds@reduce_dim_aux[["PCA"]])

  reduced_dims_names <- names(SingleCellExperiment::reducedDims(cds))
  results$reduced_dims <- reduction_method %in% reduced_dims_names

  results$clustered <- !is.null(cds@clusters[[reduction_method]])
  results$graph_learned <- !is.null(principal_graph(cds)[[reduction_method]])
  results$pseudotime_ordered <- !is.null(pseudotime(cds))

  return(results)
}

#' Print CDS Summary
#'
#' Prints dimensions and analysis step completion status.
#'
#' @param cds A cell_data_set object
#' @export
print_cds_summary <- function(cds) {
  message("CDS Summary:")
  message("  Genes: ", nrow(cds))
  message("  Cells: ", ncol(cds))

  checks <- check_cds_completeness(cds)

  message("\nAnalysis Status:")
  message("  Preprocessed: ", ifelse(checks$preprocessed, "Yes", "No"))
  message("  Reduced Dims: ", ifelse(checks$reduced_dims, "Yes", "No"))
  message("  Clustered: ", ifelse(checks$clustered, "Yes", "No"))
  message("  Graph Learned: ", ifelse(checks$graph_learned, "Yes", "No"))
  message("  Pseudotime: ", ifelse(checks$pseudotime_ordered, "Yes", "No"))
}
