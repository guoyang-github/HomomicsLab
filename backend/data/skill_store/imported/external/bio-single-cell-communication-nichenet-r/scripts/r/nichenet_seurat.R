#' NicheNet Seurat Integration
#'
#' Run NicheNet analysis on Seurat objects with different modes.
#'
#' @author Yang Guo
#' @date 2026-04-01
#' @version 2.0.0

#' Run NicheNet: Aggregate Mode
#'
#' Analyze cell-cell communication between aggregated sender and receiver populations
#' across conditions.
#'
#' @param seurat_obj Seurat object
#' @param sender Cell type(s) of sender cells (or "all")
#' @param receiver Cell type of receiver cells
#' @param condition_colname Column with condition labels
#' @param condition_oi Condition of interest
#' @param condition_reference Reference condition
#' @param ligand_target_matrix Ligand-target matrix (auto-load if NULL)
#' @param lr_network Ligand-receptor network (auto-load if NULL)
#' @param expressed_genes_sender Optional: pre-calculated expressed genes
#' @param expressed_genes_receiver Optional: pre-calculated expressed genes
#' @param genes_of_interest Optional: pre-calculated DE genes
#' @param organism "human" or "mouse"
#' @param ... Additional arguments
#'
#' @return List with results including ligand_activities, top_ligands, targets
#' @export
#'
#' @examples
#' \dontrun{
#' results <- run_nichenet_aggregate(
#'   seurat_obj,
#'   sender = "Macrophage",
#'   receiver = "T_cell",
#'   condition_colname = "stimulation",
#'   condition_oi = "stimulated",
#'   condition_reference = "control"
#' )
#' }
run_nichenet_aggregate <- function(seurat_obj,
                                    sender,
                                    receiver,
                                    condition_colname,
                                    condition_oi,
                                    condition_reference,
                                    ligand_target_matrix = NULL,
                                    lr_network = NULL,
                                    expressed_genes_sender = NULL,
                                    expressed_genes_receiver = NULL,
                                    genes_of_interest = NULL,
                                    organism = c("human", "mouse"),
                                    ...) {
  organism <- match.arg(organism)

  # Auto-load databases if not provided
  if (is.null(ligand_target_matrix)) {
    ligand_target_matrix <- get_ligand_target_matrix(organism)
  }
  if (is.null(lr_network)) {
    lr_network <- get_lr_network(organism)
  }

  # Get expressed genes if not provided
  if (is.null(expressed_genes_sender)) {
    expressed_genes_sender <- get_expressed_genes(seurat_obj, sender, pct = 0.10)
  }
  if (is.null(expressed_genes_receiver)) {
    expressed_genes_receiver <- get_expressed_genes(seurat_obj, receiver, pct = 0.10)
  }

  # Get DE genes if not provided
  if (is.null(genes_of_interest)) {
    genes_of_interest <- get_de_genes(
      seurat_obj,
      condition_col = condition_colname,
      condition_oi = condition_oi,
      condition_reference = condition_reference,
      cell_type_col = "cell_type",
      cell_type = receiver
    )
  }

  message(sprintf("\nRunning NicheNet: %s -> %s", paste(sender, collapse = ","), receiver))
  message(sprintf("Conditions: %s vs %s", condition_oi, condition_reference))

  # Get potential ligands
  ligands <- unique(lr_network$from)
  receptors <- unique(lr_network$to)

  potential_ligands <- intersect(ligands, expressed_genes_sender)
  potential_receptors <- intersect(receptors, expressed_genes_receiver)

  # Filter to ligands with receptors in receiver
  lr_network_filtered <- lr_network %>%
    filter(from %in% potential_ligands, to %in% potential_receptors)
  potential_ligands <- unique(lr_network_filtered$from)

  message(sprintf("Potential ligands: %d", length(potential_ligands)))

  # Run NicheNet
  ligand_activities <- predict_ligand_activities(
    geneset = genes_of_interest,
    background_expressed_genes = expressed_genes_receiver,
    ligand_target_matrix = ligand_target_matrix,
    potential_ligands = potential_ligands
  )

  # Get top ligands
  top_ligands <- ligand_activities$test_ligand[1:min(20, nrow(ligand_activities))]

  # Get targets for top ligands
  ligand_targets <- list()
  for (ligand in top_ligands[1:10]) {
    ligand_targets[[ligand]] <- get_top_targets(
      ligand, ligand_target_matrix, n = 200
    )
  }

  # Get active receptors
  lr_network_top <- lr_network_filtered %>%
    filter(from %in% top_ligands)

  # Compile results
  results <- list(
    ligand_activities = ligand_activities,
    top_ligands = top_ligands,
    ligand_targets = ligand_targets,
    lr_network = lr_network_top,
    sender = sender,
    receiver = receiver,
    condition_oi = condition_oi,
    condition_reference = condition_reference,
    parameters = list(
      organism = organism,
      n_geneset = length(genes_of_interest),
      n_sender_genes = length(expressed_genes_sender),
      n_receiver_genes = length(expressed_genes_receiver)
    )
  )

  message("\nNicheNet analysis complete!")
  message(sprintf("Top 3 ligands: %s", paste(top_ligands[1:3], collapse = ", ")))

  return(results)
}


#' Run NicheNet: Cluster Differential Expression Mode
#'
#' Compare two receiver cell clusters to find DE genes regulated by sender ligands.
#'
#' @param seurat_obj Seurat object
#' @param receiver_affected Affected receiver cluster
#' @param receiver_reference Reference receiver cluster
#' @param sender Cell type(s) of sender (or "all")
#' @param cell_type_col Column in meta.data containing cell type labels (default: "cell_type")
#' @param ligand_target_matrix Ligand-target matrix
#' @param lr_network Ligand-receptor network
#' @param organism "human" or "mouse"
#' @param ... Additional arguments
#'
#' @return List with results
#' @export
#'
#' @examples
#' \dontrun{
#' results <- run_nichenet_cluster_de(
#'   seurat_obj,
#'   receiver_affected = "T_cell_exhausted",
#'   receiver_reference = "T_cell_naive",
#'   sender = "Macrophage"
#' )
#' }
run_nichenet_cluster_de <- function(seurat_obj,
                                     receiver_affected,
                                     receiver_reference,
                                     sender = "all",
                                     cell_type_col = "cell_type",
                                     ligand_target_matrix = NULL,
                                     lr_network = NULL,
                                     organism = c("human", "mouse"),
                                     ...) {
  organism <- match.arg(organism)

  # Auto-load databases
  if (is.null(ligand_target_matrix)) {
    ligand_target_matrix <- get_ligand_target_matrix(organism)
  }
  if (is.null(lr_network)) {
    lr_network <- get_lr_network(organism)
  }

  # Get expressed genes
  expressed_genes_sender <- get_expressed_genes(seurat_obj, sender, pct = 0.10)
  expressed_genes_receiver <- unique(c(
    get_expressed_genes(seurat_obj, receiver_affected, pct = 0.10),
    get_expressed_genes(seurat_obj, receiver_reference, pct = 0.10)
  ))

  # Find DE genes between receiver clusters
  message(sprintf("\nComparing receiver clusters: %s vs %s", receiver_affected, receiver_reference))

  # Get cells safely using meta.data subsetting (avoids WhichCells NSE edge cases)
  cells_affected <- colnames(seurat_obj)[seurat_obj@meta.data[[cell_type_col]] %in% receiver_affected]
  cells_reference <- colnames(seurat_obj)[seurat_obj@meta.data[[cell_type_col]] %in% receiver_reference]

  markers <- FindMarkers(
    seurat_obj,
    cells.1 = cells_affected,
    cells.2 = cells_reference,
    logfc.threshold = 0.25,
    min.pct = 0.10
  )

  genes_of_interest <- rownames(markers)[markers$p_val_adj < 0.05 & markers$avg_log2FC > 0]

  message(sprintf("Found %d upregulated genes in %s", length(genes_of_interest), receiver_affected))

  # Run standard NicheNet analysis
  results <- run_nichenet_celltype_pair(
    seurat_obj = seurat_obj,
    sender_celltype = sender,
    receiver_celltype = receiver_affected,
    expressed_genes_sender = expressed_genes_sender,
    expressed_genes_receiver = expressed_genes_receiver,
    genes_of_interest = genes_of_interest,
    ligand_target_matrix = ligand_target_matrix,
    lr_network = lr_network,
    organism = organism,
    ...
  )

  results$receiver_affected <- receiver_affected
  results$receiver_reference <- receiver_reference
  results$de_genes <- genes_of_interest

  return(results)
}


#' Run NicheNet: Cell Type Pair Mode
#'
#' Basic NicheNet analysis between sender and receiver cell types.
#'
#' @param seurat_obj Seurat object
#' @param sender_celltype Sender cell type(s)
#' @param receiver_celltype Receiver cell type
#' @param expressed_genes_sender Optional: expressed genes in sender
#' @param expressed_genes_receiver Optional: expressed genes in receiver
#' @param genes_of_interest Optional: genes of interest in receiver
#' @param ligand_target_matrix Ligand-target matrix
#' @param lr_network Ligand-receptor network
#' @param organism "human" or "mouse"
#' @param ... Additional arguments
#'
#' @return List with results
#' @export
#'
#' @examples
#' \dontrun{
#' results <- run_nichenet_celltype_pair(
#'   seurat_obj,
#'   sender_celltype = "Macrophage",
#'   receiver_celltype = "T_cell",
#'   genes_of_interest = c("IL2", "IFNG", "TNF")
#' )
#' }
run_nichenet_celltype_pair <- function(seurat_obj,
                                        sender_celltype,
                                        receiver_celltype,
                                        expressed_genes_sender = NULL,
                                        expressed_genes_receiver = NULL,
                                        genes_of_interest,
                                        ligand_target_matrix = NULL,
                                        lr_network = NULL,
                                        organism = c("human", "mouse"),
                                        ...) {
  organism <- match.arg(organism)

  # Auto-load databases
  if (is.null(ligand_target_matrix)) {
    ligand_target_matrix <- get_ligand_target_matrix(organism)
  }
  if (is.null(lr_network)) {
    lr_network <- get_lr_network(organism)
  }

  # Get expressed genes
  if (is.null(expressed_genes_sender)) {
    expressed_genes_sender <- get_expressed_genes(seurat_obj, sender_celltype, pct = 0.10)
  }
  if (is.null(expressed_genes_receiver)) {
    expressed_genes_receiver <- get_expressed_genes(seurat_obj, receiver_celltype, pct = 0.10)
  }

  message(sprintf("\nAnalyzing: %s -> %s", paste(sender_celltype, collapse = ","), receiver_celltype))
  message(sprintf("Genes of interest: %d", length(genes_of_interest)))

  # Get potential ligands
  ligands <- unique(lr_network$from)
  receptors <- unique(lr_network$to)

  potential_ligands <- intersect(ligands, expressed_genes_sender)
  potential_receptors <- intersect(receptors, expressed_genes_receiver)

  lr_network_filtered <- lr_network %>%
    filter(from %in% potential_ligands, to %in% potential_receptors)
  potential_ligands <- unique(lr_network_filtered$from)

  # Run prediction
  ligand_activities <- predict_ligand_activities(
    geneset = genes_of_interest,
    background_expressed_genes = expressed_genes_receiver,
    ligand_target_matrix = ligand_target_matrix,
    potential_ligands = potential_ligands
  )

  # Get top ligands and targets
  top_ligands <- ligand_activities$test_ligand[1:min(20, nrow(ligand_activities))]

  ligand_targets <- list()
  for (ligand in top_ligands[1:10]) {
    ligand_targets[[ligand]] <- get_top_targets(
      ligand, ligand_target_matrix, n = 200
    )
  }

  # Results
  results <- list(
    ligand_activities = ligand_activities,
    top_ligands = top_ligands,
    ligand_targets = ligand_targets,
    lr_network = lr_network_filtered %>% filter(from %in% top_ligands),
    sender = sender_celltype,
    receiver = receiver_celltype,
    genes_of_interest = genes_of_interest,
    parameters = list(
      organism = organism,
      n_sender_genes = length(expressed_genes_sender),
      n_receiver_genes = length(expressed_genes_receiver),
      n_geneset = length(genes_of_interest)
    )
  )

  return(results)
}


#' Run NicheNet: Cell Type Specific
#'
#' Analyze communication with specific sender and receiver cell barcodes.
#'
#' @param seurat_obj Seurat object
#' @param sender_cells Vector of sender cell barcodes
#' @param receiver_cells Vector of receiver cell barcodes
#' @param genes_of_interest Genes of interest in receiver
#' @param ligand_target_matrix Ligand-target matrix
#' @param lr_network Ligand-receptor network
#' @param organism "human" or "mouse"
#'
#' @return List with results
#' @export
#'
#' @examples
#' \dontrun{
#' results <- run_nichenet_celltype_specific(
#'   seurat_obj,
#'   sender_cells = sender_barcodes,
#'   receiver_cells = receiver_barcodes,
#'   genes_of_interest = marker_genes
#' )
#' }
run_nichenet_celltype_specific <- function(seurat_obj,
                                            sender_cells,
                                            receiver_cells,
                                            genes_of_interest,
                                            ligand_target_matrix = NULL,
                                            lr_network = NULL,
                                            organism = c("human", "mouse")) {
  organism <- match.arg(organism)

  if (is.null(ligand_target_matrix)) {
    ligand_target_matrix <- get_ligand_target_matrix(organism)
  }
  if (is.null(lr_network)) {
    lr_network <- get_lr_network(organism)
  }

  # Get expressed genes from specific cells
  if (packageVersion("SeuratObject") >= "5.0.0") {
    expr <- Seurat::GetAssayData(seurat_obj, layer = "counts")
  } else {
    expr <- Seurat::GetAssayData(seurat_obj, slot = "counts")
  }

  sender_expr <- expr[, sender_cells, drop = FALSE]
  receiver_expr <- expr[, receiver_cells, drop = FALSE]

  expressed_genes_sender <- rownames(expr)[rowMeans(sender_expr > 0) >= 0.10]
  expressed_genes_receiver <- rownames(expr)[rowMeans(receiver_expr > 0) >= 0.10]

  message(sprintf("Sender cells: %d, Receiver cells: %d",
                 length(sender_cells), length(receiver_cells)))

  # Run analysis
  results <- run_nichenet_celltype_pair(
    seurat_obj = seurat_obj,
    sender_celltype = "custom_sender",
    receiver_celltype = "custom_receiver",
    expressed_genes_sender = expressed_genes_sender,
    expressed_genes_receiver = expressed_genes_receiver,
    genes_of_interest = genes_of_interest,
    ligand_target_matrix = ligand_target_matrix,
    lr_network = lr_network,
    organism = organism
  )

  results$sender_cells <- sender_cells
  results$receiver_cells <- receiver_cells

  return(results)
}
