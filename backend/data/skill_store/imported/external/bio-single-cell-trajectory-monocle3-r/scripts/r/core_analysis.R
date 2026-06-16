#' Core Analysis Functions for Monocle3 Trajectory Analysis
#'
#' High-value functions that add logic beyond official monocle3:
#' - create_cds: handles NULL metadata gracefully
#' - cds_from_seurat: auto-detects Seurat v4 (slot=) vs v5 (layer=)
#' - cds_from_sce: converts SingleCellExperiment with gene_short_name fix
#' - run_trajectory_analysis: end-to-end pipeline combining all steps
#' - get_earliest_principal_node: programmatic root selection from metadata
#' - find_trajectory_variable_genes: filters graph_test by q-value + Moran's I
#'
#' Author: Yang Guo
#' Date: 2026-05-21

#==============================================================================
# Cell Data Set Creation
#==============================================================================

#' Create Cell Data Set from Various Sources
#'
#' Handles NULL metadata by creating default cell_id / gene_short_name columns.
#'
#' @param expression_matrix Gene expression matrix (genes x cells)
#' @param cell_metadata Data frame with cell metadata (optional)
#' @param gene_metadata Data frame with gene metadata (optional)
#' @return A cell_data_set object
#' @export
create_cds <- function(expression_matrix,
                       cell_metadata = NULL,
                       gene_metadata = NULL) {
  if (is.null(cell_metadata)) {
    cell_metadata <- data.frame(cell_id = colnames(expression_matrix))
    rownames(cell_metadata) <- colnames(expression_matrix)
  }

  if (is.null(gene_metadata)) {
    gene_metadata <- data.frame(gene_short_name = rownames(expression_matrix))
    rownames(gene_metadata) <- rownames(expression_matrix)
  }

  cds <- new_cell_data_set(
    expression_data = expression_matrix,
    cell_metadata = cell_metadata,
    gene_metadata = gene_metadata
  )

  return(cds)
}

#' Create CDS from Seurat Object (v4/v5 compatible)
#'
#' Automatically detects Seurat v5 (SeuratObject >= 5.0.0, uses `layer="counts"`)
#' vs v4 (uses `slot="counts"`).
#'
#' @param seurat_obj A Seurat object
#' @param assay Which assay to use (default: "RNA")
#' @return A cell_data_set object
#' @export
cds_from_seurat <- function(seurat_obj, assay = "RNA") {
  if (!requireNamespace("SeuratObject", quietly = TRUE)) {
    stop("SeuratObject package is required. Install with install.packages('SeuratObject')")
  }
  if (packageVersion("SeuratObject") >= "5.0.0") {
    counts <- Seurat::GetAssayData(seurat_obj, layer = "counts", assay = assay)
  } else {
    counts <- Seurat::GetAssayData(seurat_obj, slot = "counts", assay = assay)
  }

  cell_metadata <- seurat_obj@meta.data

  gene_metadata <- data.frame(
    gene_short_name = rownames(counts),
    row.names = rownames(counts)
  )

  cds <- new_cell_data_set(
    expression_data = counts,
    cell_metadata = cell_metadata,
    gene_metadata = gene_metadata
  )

  return(cds)
}

#' Create CDS from SingleCellExperiment
#'
#' Ensures gene_short_name column exists; creates it from rownames if missing.
#'
#' @param sce A SingleCellExperiment object
#' @return A cell_data_set object
#' @export
cds_from_sce <- function(sce) {
  counts <- SingleCellExperiment::counts(sce)
  cell_metadata <- as.data.frame(SingleCellExperiment::colData(sce))
  gene_metadata <- as.data.frame(SingleCellExperiment::rowData(sce))

  if (!("gene_short_name" %in% colnames(gene_metadata))) {
    gene_metadata$gene_short_name <- rownames(gene_metadata)
  }

  cds <- new_cell_data_set(
    expression_data = counts,
    cell_metadata = cell_metadata,
    gene_metadata = gene_metadata
  )

  return(cds)
}

#==============================================================================
# End-to-End Pipeline
#==============================================================================

#' Run Complete Trajectory Analysis
#'
#' Combines preprocess_cds -> reduce_dimension -> cluster_cells -> learn_graph -> order_cells.
#'
#' @param cds A cell_data_set object
#' @param num_dim Number of principal components (default: 50)
#' @param reduction_method "UMAP", "tSNE", or "PCA"
#' @param cluster_resolution Clustering resolution (default: 1e-5)
#' @param root_cells Root cell IDs (optional)
#' @param root_pr_nodes Root principal nodes (optional)
#' @return CDS with complete trajectory analysis
#' @export
run_trajectory_analysis <- function(cds,
                                    num_dim = 50,
                                    reduction_method = "UMAP",
                                    cluster_resolution = 1e-5,
                                    root_cells = NULL,
                                    root_pr_nodes = NULL) {
  message("Running complete trajectory analysis...")

  cds <- preprocess_cds(cds, num_dim = num_dim)
  cds <- reduce_dimension(cds, reduction_method = reduction_method)
  cds <- cluster_cells(cds, resolution = cluster_resolution)
  cds <- learn_graph(cds)

  if (!is.null(root_cells) || !is.null(root_pr_nodes)) {
    cds <- order_cells(cds, root_cells = root_cells, root_pr_nodes = root_pr_nodes)
  } else {
    message("Skipping order_cells - no root specified")
  }

  message("Trajectory analysis complete!")
  return(cds)
}

#==============================================================================
# Root Selection Helper
#==============================================================================

#' Get Earliest Principal Node from Metadata
#'
#' Identifies the principal graph node most enriched for a given time/stage value.
#' Use this to set root_pr_nodes for order_cells() programmatically.
#'
#' @param cds A cell_data_set object with learned graph
#' @param time_bin_col Column in colData indicating time/stage
#' @param time_bin_value Value indicating the earliest stage
#' @return Character vector of principal node name(s)
#' @export
get_earliest_principal_node <- function(cds,
                                        time_bin_col,
                                        time_bin_value) {
  cell_ids <- which(colData(cds)[[time_bin_col]] == time_bin_value)

  closest_vertex <- cds@principal_graph_aux[["UMAP"]]$pr_graph_cell_proj_closest_vertex
  closest_vertex <- as.matrix(closest_vertex[colnames(cds), ])

  root_pr_nodes <- igraph::V(principal_graph(cds)[["UMAP"]])$name[
    as.numeric(names(which.max(table(closest_vertex[cell_ids, ]))))
  ]

  return(root_pr_nodes)
}

#==============================================================================
# Gene Analysis Helpers
#==============================================================================

#' Find Trajectory-Variable Genes
#'
#' Runs graph_test() and filters by q-value and Moran's I.
#'
#' @param cds A cell_data_set object with pseudotime
#' @param q_value_threshold Q-value threshold (default: 0.05)
#' @param morans_I_threshold Minimum Moran's I (default: 0)
#' @param cores Number of cores for parallel processing
#' @return Data frame of significant genes
#' @export
find_trajectory_variable_genes <- function(cds,
                                           q_value_threshold = 0.05,
                                           morans_I_threshold = 0,
                                           cores = 1) {
  message("Finding trajectory-variable genes...")

  test_res <- graph_test(cds, neighbor_graph = "principal_graph", cores = cores)

  sig_genes <- subset(test_res,
                      q_value < q_value_threshold &
                        morans_I > morans_I_threshold)

  message("Found ", nrow(sig_genes), " trajectory-variable genes")
  return(sig_genes)
}
