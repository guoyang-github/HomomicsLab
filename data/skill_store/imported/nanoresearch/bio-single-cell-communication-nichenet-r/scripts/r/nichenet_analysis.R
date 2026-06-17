#' NicheNet Core Analysis Functions
#'
#' Predict ligand activities and extract target genes.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

#' Predict Ligand Activities
#'
#' Predict which ligands can regulate a set of target genes.
#'
#' @param geneset Vector of target genes of interest
#' @param background_expressed_genes Vector of all expressed genes in receiver
#' @param ligand_target_matrix Ligand-target probability matrix
#' @param potential_ligands Vector of potential ligands to test
#' @param single Run single-sample analysis (default: TRUE)
#' @param ... Additional arguments passed to nichenetr::predict_ligand_activities
#'
#' @return Data frame with ligand activity scores
#' @export
#'
#' @examples
#' \dontrun{
#' results <- predict_ligand_activities(
#'   geneset = genes_of_interest,
#'   background_expressed_genes = expressed_genes_receiver,
#'   ligand_target_matrix = ligand_target_matrix,
#'   potential_ligands = expressed_genes_sender
#' )
#' }
predict_ligand_activities <- function(geneset,
                                       background_expressed_genes,
                                       ligand_target_matrix,
                                       potential_ligands,
                                       single = TRUE,
                                       ...) {
  if (!requireNamespace("nichenetr", quietly = TRUE)) {
    stop("nichenetr package required. Install with: devtools::install_github('saeyslab/nichenetr')")
  }

  library(nichenetr)

  # Validate inputs
  if (length(geneset) == 0) {
    stop("geneset cannot be empty")
  }

  if (length(background_expressed_genes) == 0) {
    stop("background_expressed_genes cannot be empty")
  }

  # Filter ligands present in matrix
  available_ligands <- colnames(ligand_target_matrix)
  potential_ligands <- intersect(potential_ligands, available_ligands)

  if (length(potential_ligands) == 0) {
    stop("No potential ligands found in ligand_target_matrix")
  }

  message(sprintf("Testing %d ligands against %d target genes...",
                 length(potential_ligands), length(geneset)))

  # Run prediction
  results <- nichenetr::predict_ligand_activities(
    geneset = geneset,
    background_expressed_genes = background_expressed_genes,
    ligand_target_matrix = ligand_target_matrix,
    potential_ligands = potential_ligands,
    single = single,
    ...
  )

  # Sort by aupr_corrected (NicheNet v2 recommended metric)
  results <- results[order(-results$aupr_corrected), ]

  message(sprintf("Top ligand: %s (aupr_corrected: %.3f)",
                 results$test_ligand[1], results$aupr_corrected[1]))

  return(results)
}


#' Get Expressed Genes
#'
#' Get genes expressed above a threshold in specific cell types.
#'
#' @param seurat_obj Seurat object
#' @param cell_types Cell type(s) to consider (or "all" for all cells)
#' @param pct Minimum percentage of cells expressing the gene (default: 0.10)
#' @param assay Assay to use (default: "RNA")
#'
#' @return Vector of expressed gene symbols
#' @export
#'
#' @examples
#' \dontrun{
#' expressed_genes <- get_expressed_genes(seurat_obj, "T_cell", pct = 0.10)
#' all_genes <- get_expressed_genes(seurat_obj, "all", pct = 0.05)
#' }
get_expressed_genes <- function(seurat_obj,
                                 cell_types,
                                 pct = 0.10,
                                 assay = "RNA") {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  DefaultAssay(seurat_obj) <- assay

  if (cell_types == "all") {
    # Get all cells
    cells <- colnames(seurat_obj)
  } else {
    # Get cells of specified type
    cells <- WhichCells(seurat_obj, idents = cell_types)
  }

  if (length(cells) == 0) {
    warning("No cells found for specified cell types")
    return(character(0))
  }

  # Calculate percentage expression
  if (packageVersion("SeuratObject") >= "5.0.0") {
    expr_pct <- rowMeans(Seurat::GetAssayData(seurat_obj, assay = assay, layer = "counts")[, cells, drop = FALSE] > 0)
  } else {
    expr_pct <- rowMeans(Seurat::GetAssayData(seurat_obj, assay = assay, slot = "counts")[, cells, drop = FALSE] > 0)
  }

  expressed_genes <- names(expr_pct)[expr_pct >= pct]

  message(sprintf("Found %d genes expressed in >= %.0f%% of %d cells",
                 length(expressed_genes), pct * 100, length(cells)))

  return(expressed_genes)
}


#' Get Differentially Expressed Genes
#'
#' Get DE genes between two conditions.
#'
#' @param seurat_obj Seurat object
#' @param condition_col Column with condition labels
#' @param condition_oi Condition of interest
#' @param condition_reference Reference condition
#' @param cell_type_col Optional column to subset specific cell type
#' @param cell_type Optional cell type to subset
#' @param logfc_threshold Log fold change threshold (default: 0.25)
#' @param pval_threshold P-value threshold (default: 0.05)
#' @param min_pct Minimum percentage expressing cells (default: 0.10)
#'
#' @return Vector of DE gene symbols
#' @export
#'
#' @examples
#' \dontrun{
#' # DE genes in stimulated vs control T cells
#' de_genes <- get_de_genes(
#'   seurat_obj,
#'   condition_col = "stimulation",
#'   condition_oi = "stimulated",
#'   condition_reference = "control",
#'   cell_type_col = "cell_type",
#'   cell_type = "T_cell"
#' )
#' }
get_de_genes <- function(seurat_obj,
                          condition_col,
                          condition_oi,
                          condition_reference,
                          cell_type_col = NULL,
                          cell_type = NULL,
                          logfc_threshold = 0.25,
                          pval_threshold = 0.05,
                          min_pct = 0.10) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Subset to cell type if specified
  if (!is.null(cell_type_col) && !is.null(cell_type)) {
    cells <- WhichCells(seurat_obj, idents = cell_type)
    seurat_obj <- subset(seurat_obj, cells = cells)
  }

  # Check conditions exist
  if (!condition_col %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("Condition column '%s' not found", condition_col))
  }

  conditions <- unique(seurat_obj@meta.data[[condition_col]])
  if (!condition_oi %in% conditions) {
    stop(sprintf("Condition '%s' not found", condition_oi))
  }
  if (!condition_reference %in% conditions) {
    stop(sprintf("Reference condition '%s' not found", condition_reference))
  }

  message(sprintf("Finding DE genes: %s vs %s", condition_oi, condition_reference))

  # Run DE analysis
  markers <- FindMarkers(
    seurat_obj,
    ident.1 = condition_oi,
    ident.2 = condition_reference,
    group.by = condition_col,
    logfc.threshold = logfc_threshold,
    min.pct = min_pct,
    only.pos = FALSE
  )

  # Filter by significance
  sig_genes <- rownames(markers)[markers$p_val_adj < pval_threshold]

  # Return upregulated genes
  up_genes <- rownames(markers)[markers$p_val_adj < pval_threshold & markers$avg_log2FC > 0]

  message(sprintf("Found %d DE genes (%d upregulated)", length(sig_genes), length(up_genes)))

  return(up_genes)
}


#' Get Top Targets
#'
#' Get top predicted target genes for a ligand.
#'
#' @param ligand Ligand name
#' @param ligand_target_matrix Ligand-target probability matrix
#' @param n Number of top targets (default: 200)
#' @param cutoff Minimum probability score (default: NULL)
#' @param return_scores Whether to return scores (default: FALSE)
#'
#' @return Vector of target gene names (or named vector if return_scores = TRUE)
#' @export
#'
#' @examples
#' \dontrun{
#' targets <- get_top_targets("TGFB1", ligand_target_matrix, n = 100)
#' targets_with_scores <- get_top_targets("TGFB1", ligand_target_matrix, return_scores = TRUE)
#' }
get_top_targets <- function(ligand,
                             ligand_target_matrix,
                             n = 200,
                             cutoff = NULL,
                             return_scores = FALSE) {
  if (!ligand %in% colnames(ligand_target_matrix)) {
    warning(sprintf("Ligand '%s' not found in matrix", ligand))
    return(character(0))
  }

  # Get targets
  scores <- ligand_target_matrix[, ligand]
  scores <- sort(scores, decreasing = TRUE)

  # Apply cutoff if specified
  if (!is.null(cutoff)) {
    scores <- scores[scores >= cutoff]
  }

  # Take top n
  scores <- head(scores, n)

  if (return_scores) {
    return(scores)
  } else {
    return(names(scores))
  }
}


#' Get Ligand Receptors
#'
#' Get receptors for a given ligand from the ligand-receptor network.
#'
#' @param ligand Ligand name
#' @param lr_network Ligand-receptor network
#' @param return_df Return full data frame (default: FALSE)
#'
#' @return Vector of receptor names (or data frame if return_df = TRUE)
#' @export
#'
#' @examples
#' \dontrun{
#' receptors <- get_ligand_receptors("TGFB1", lr_network)
#' }
get_ligand_receptors <- function(ligand, lr_network, return_df = FALSE) {
  ligand_data <- lr_network[lr_network$from == ligand, ]

  if (nrow(ligand_data) == 0) {
    warning(sprintf("No receptors found for ligand '%s'", ligand))
    return(if (return_df) data.frame() else character(0))
  }

  if (return_df) {
    return(ligand_data)
  } else {
    return(unique(ligand_data$to))
  }
}


#' Calculate Ligand-Receptor Expression
#'
#' Calculate average expression of ligand-receptor pairs.
#'
#' @param seurat_obj Seurat object
#' @param lr_pairs Data frame with ligand and receptor columns
#' @param group_by Column to group by (default: NULL)
#'
#' @return Data frame with expression values
#' @export
#'
#' @examples
#' \dontrun{
#' lr_expr <- calculate_lr_expression(seurat_obj, lr_pairs, group_by = "cell_type")
#' }
calculate_lr_expression <- function(seurat_obj,
                                     lr_pairs,
                                     group_by = NULL) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Validate columns
  if (!all(c("ligand", "receptor") %in% colnames(lr_pairs))) {
    stop("lr_pairs must have 'ligand' and 'receptor' columns")
  }

  # Get expression data
  if (packageVersion("SeuratObject") >= "5.0.0") {
    expr <- Seurat::GetAssayData(seurat_obj, layer = "data")
  } else {
    expr <- Seurat::GetAssayData(seurat_obj, slot = "data")
  }

  results <- data.frame(
    ligand = lr_pairs$ligand,
    receptor = lr_pairs$receptor,
    ligand_expr = NA,
    receptor_expr = NA,
    stringsAsFactors = FALSE
  )

  for (i in seq_len(nrow(lr_pairs))) {
    ligand <- lr_pairs$ligand[i]
    receptor <- lr_pairs$receptor[i]

    if (ligand %in% rownames(expr)) {
      results$ligand_expr[i] <- mean(expr[ligand, ])
    }
    if (receptor %in% rownames(expr)) {
      results$receptor_expr[i] <- mean(expr[receptor, ])
    }
  }

  return(results)
}
