#!/usr/bin/env Rscript
#' Single-Cell Cell-Cell Communication Analysis with CellChat
#'
#' R wrapper functions for CellChat analysis on single-cell RNA-seq data.
#'
#' @author Yang Guo
#' @date 2026-04-03
#' @version 1.0.0

#' Run CellChat Analysis on Single-Cell Data
#'
#' Main wrapper function for complete CellChat analysis pipeline.
#'
#' @param seurat_obj Seurat object
#' @param group_by Metadata column for cell groups (default: "cell_type")
#' @param sample_name Sample name identifier
#' @param db_use Database: "CellChatDB.human" or "CellChatDB.mouse" (default: "CellChatDB.human")
#' @param signaling_type Signaling type(s): "Secreted Signaling", "Cell-Cell Contact", "ECM-Receptor", or "all". Can be a single string or a character vector to select multiple types. (default: "Secreted Signaling")
#' @param type Average method: "triMean" or "truncatedMean" (default: "triMean")
#' @param trim Trim value for truncatedMean (default: NULL)
#' @param population.size Consider cell population size (default: FALSE)
#' @param min_cells Minimum cells per group (default: 10)
#' @param cell_types Character vector of cell types to include. If NULL, all cell types are used (default: NULL)
#' @param n_workers Number of parallel workers (default: 4)
#' @param verbose Print progress (default: TRUE)
#'
#' @return CellChat object with complete analysis
#'
#' @examples
#' \dontrun{
#' # Basic usage
#' cellchat <- run_cellchat(seurat_obj, group_by = "cell_type")
#'
#' # With parameters
#' cellchat <- run_cellchat(
#'   seurat_obj,
#'   group_by = "cell_type",
#'   db_use = "CellChatDB.human",
#'   signaling_type = "Secreted Signaling",
#'   type = "triMean",
#'   min_cells = 10
#' )
#' }
#'
#' @export
run_cellchat <- function(
    seurat_obj,
    group_by = "cell_type",
    sample_name = "Sample",
    db_use = "CellChatDB.human",
    signaling_type = "Secreted Signaling",
    type = "triMean",
    trim = NULL,
    population.size = FALSE,
    cell_types = NULL,
    min_cells = 10,
    n_workers = 4,
    verbose = TRUE
) {
  if (!requireNamespace("CellChat", quietly = TRUE)) {
    stop("CellChat package required. Install with: remotes::install_github('jinworks/CellChat')")
  }

  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(CellChat)
  library(Seurat)

  if (verbose) {
    message(sprintf("Running CellChat analysis on: %s", sample_name))
    message(sprintf("  Cells: %d, Groups: %d", ncol(seurat_obj),
                    length(unique(seurat_obj@meta.data[[group_by]]))))
  }

  # Create CellChat object
  cellchat <- create_cellchat_object(
    seurat_obj = seurat_obj,
    group_by = group_by,
    verbose = verbose
  )

  # Set database
  cellchat <- set_cellchat_database(
    cellchat = cellchat,
    db_use = db_use,
    signaling_type = signaling_type,
    verbose = verbose
  )

  # Subset to specific cell types if requested
  if (!is.null(cell_types)) {
    if (verbose) message(sprintf("Subsetting to cell types: %s", paste(cell_types, collapse = ", ")))
    cellchat <- subsetCellChat(cellchat, idents.use = cell_types)
  }

  # Preprocessing
  if (verbose) message("Preprocessing expression data...")
  cellchat <- subsetData(cellchat)

  future::plan("multisession", workers = n_workers)
  cellchat <- identifyOverExpressedGenes(cellchat)
  cellchat <- identifyOverExpressedInteractions(cellchat)

  # Compute communication probability
  if (verbose) message("Computing communication probability...")

  compute_args <- list(
    object = cellchat,
    type = type,
    population.size = population.size
  )

  if (type == "truncatedMean" && !is.null(trim)) {
    compute_args$trim <- trim
  }

  cellchat <- do.call(computeCommunProb, compute_args)

  # Filter
  cellchat <- filterCommunication(cellchat, min.cells = min_cells)

  # Pathway-level analysis
  if (verbose) message("Computing pathway-level communication...")
  cellchat <- computeCommunProbPathway(cellchat)
  cellchat <- aggregateNet(cellchat)

  if (verbose) message("CellChat analysis complete!")

  return(cellchat)
}


#' Create CellChat Object from Seurat
#'
#' Helper function to create CellChat object from Seurat object.
#'
#' @param seurat_obj Seurat object
#' @param group_by Metadata column for cell groups
#' @param verbose Print progress
#'
#' @return CellChat object
#'
#' @keywords internal
#' @export
create_cellchat_object <- function(
    seurat_obj,
    group_by = "cell_type",
    verbose = TRUE
) {
  if (!group_by %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("'%s' not found in metadata", group_by))
  }

  # Create CellChat object
  cellchat <- CellChat::createCellChat(
    object = seurat_obj,
    group.by = group_by
  )

  if (verbose) {
    message(sprintf("Created CellChat object: %d cells, %d groups",
                    length(cellchat@idents), length(levels(cellchat@idents))))
  }

  return(cellchat)
}


#' Set CellChat Database
#'
#' Configure CellChat database and subset signaling types.
#'
#' @param cellchat CellChat object
#' @param db_use Database name
#' @param signaling_type Signaling type(s) to subset. Single string or character vector (e.g. c("Secreted Signaling", "ECM-Receptor")). Use "all" to keep all interactions.
#' @param verbose Print progress
#'
#' @return CellChat object with database set
#'
#' @keywords internal
#' @export
set_cellchat_database <- function(
    cellchat,
    db_use = "CellChatDB.human",
    signaling_type = "Secreted Signaling",
    verbose = TRUE
) {
  # Load database
  CellChatDB <- switch(db_use,
                       "CellChatDB.human" = CellChat::CellChatDB.human,
                       "CellChatDB.mouse" = CellChat::CellChatDB.mouse,
                       CellChat::CellChatDB.human
  )

  # Subset database
  if (length(signaling_type) == 1 && signaling_type == "all") {
    # When signaling_type is "all", use the full database directly
    # subsetDB() without search parameter may return an empty database
    CellChatDB.use <- CellChatDB
  } else {
    # Support multiple signaling types
    # CellChatDB is a list object, must use subsetDB() for correct filtering
    CellChatDB.use <- CellChat::subsetDB(
      CellChatDB,
      search = signaling_type,
      key = "annotation"
    )
    if (is.null(CellChatDB.use$interaction) || nrow(CellChatDB.use$interaction) == 0) {
      stop(sprintf("No interactions found for signaling_type: %s", paste(signaling_type, collapse = ", ")))
    }
  }

  cellchat@DB <- CellChatDB.use

  if (verbose) {
    message(sprintf("Database: %d interactions", nrow(CellChatDB.use$interaction)))
  }

  return(cellchat)
}


#' Plot CellChat Circle Visualization
#'
#' Create circle plot of cell-cell communication network.
#'
#' @param cellchat CellChat object
#' @param slot_name Slot to visualize: "net$count" or "net$weight" (default: "net$count")
#' @param title_name Plot title (optional)
#' @param ... Additional arguments
#'
#' @return None (generates plot)
#'
#' @examples
#' \dontrun{
#' plot_cellchat_circle(cellchat)
#' plot_cellchat_circle(cellchat, slot_name = "net$weight")
#' }
#'
#' @export
plot_cellchat_circle <- function(
    cellchat,
    slot_name = "net$count",
    title_name = NULL,
    ...
) {
  if (!requireNamespace("CellChat", quietly = TRUE)) {
    stop("CellChat required")
  }

  # Get data matrix
  if (slot_name == "net$count") {
    mat <- cellchat@net$count
  } else if (slot_name == "net$weight") {
    mat <- cellchat@net$weight
  } else {
    stop("Invalid slot_name")
  }

  groupSize <- as.numeric(table(cellchat@idents))

  if (is.null(title_name)) {
    title_name <- ifelse(slot_name == "net$count",
                         "Number of interactions",
                         "Interaction weights/strength")
  }

  CellChat::netVisual_circle(
    mat,
    vertex.weight = groupSize,
    weight.scale = TRUE,
    label.edge = FALSE,
    title.name = title_name,
    ...
  )
}


#' Plot CellChat Bubble Visualization
#'
#' Create bubble plot of ligand-receptor pairs.
#'
#' @param cellchat CellChat object
#' @param sources.use Source cell groups (optional)
#' @param targets.use Target cell groups (optional)
#' @param signaling Signaling pathways to show (optional)
#' @param pairLR.use Specific LR pairs (optional)
#' @param remove.isolate Remove isolated interactions (default: TRUE)
#' @param ... Additional arguments
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' # All interactions
#' plot_cellchat_bubble(cellchat)
#'
#' # Specific source-target
#' plot_cellchat_bubble(cellchat, sources.use = c(1,2), targets.use = c(3,4))
#'
#' # Specific pathways
#' plot_cellchat_bubble(cellchat, signaling = c("CXCL", "CCL"))
#' }
#'
#' @export
plot_cellchat_bubble <- function(
    cellchat,
    sources.use = NULL,
    targets.use = NULL,
    signaling = NULL,
    pairLR.use = NULL,
    remove.isolate = TRUE,
    ...
) {
  args <- list(
    object = cellchat,
    remove.isolate = remove.isolate,
    ...
  )

  if (!is.null(sources.use)) args$sources.use <- sources.use
  if (!is.null(targets.use)) args$targets.use <- targets.use
  if (!is.null(signaling)) args$signaling <- signaling
  if (!is.null(pairLR.use)) args$pairLR.use <- pairLR.use

  do.call(CellChat::netVisual_bubble, args)
}


#' Plot CellChat Pathway Visualization
#'
#' Visualize specific signaling pathway.
#'
#' @param cellchat CellChat object
#' @param signaling Signaling pathway name
#' @param layout Layout type: "circle", "hierarchy", "chord", "heatmap" (default: "circle")
#' @param vertex.receiver Target cells for hierarchy plot (optional)
#' @param ... Additional arguments
#'
#' @return None (generates plot)
#'
#' @examples
#' \dontrun{
#' plot_cellchat_pathway(cellchat, signaling = "CXCL", layout = "circle")
#' plot_cellchat_pathway(cellchat, signaling = "CXCL", layout = "hierarchy", vertex.receiver = 1:4)
#' }
#'
#' @export
plot_cellchat_pathway <- function(
    cellchat,
    signaling,
    layout = "circle",
    vertex.receiver = NULL,
    ...
) {
  args <- list(
    object = cellchat,
    signaling = signaling,
    layout = layout,
    ...
  )

  if (layout == "hierarchy" && !is.null(vertex.receiver)) {
    args$vertex.receiver <- vertex.receiver
  }

  do.call(CellChat::netVisual_aggregate, args)
}


#' Compute CellChat Network Centrality
#'
#' Compute network centrality scores for signaling roles.
#'
#' @param cellchat CellChat object
#' @param slot_name Slot name: "netP" or "net" (default: "netP")
#'
#' @return CellChat object with centrality computed
#'
#' @examples
#' \dontrun{
#' cellchat <- compute_cellchat_centrality(cellchat)
#' }
#'
#' @export
compute_cellchat_centrality <- function(
    cellchat,
    slot_name = "netP"
) {
  cellchat <- CellChat::netAnalysis_computeCentrality(cellchat, slot.name = slot_name)
  return(cellchat)
}


#' Plot CellChat Signaling Roles
#'
#' Visualize signaling roles of cell groups.
#'
#' @param cellchat CellChat object (with centrality computed)
#' @param signaling Signaling pathways (optional, all if NULL)
#' @param width Plot width (default: 8)
#' @param height Plot height (default: 2.5)
#' @param font.size Font size (default: 10)
#'
#' @return None (generates plot)
#'
#' @examples
#' \dontrun{
#' cellchat <- compute_cellchat_centrality(cellchat)
#' plot_cellchat_signaling_roles(cellchat, signaling = "CXCL")
#' }
#'
#' @export
plot_cellchat_signaling_roles <- function(
    cellchat,
    signaling = NULL,
    width = 8,
    height = 2.5,
    font.size = 10
) {
  args <- list(
    object = cellchat,
    width = width,
    height = height,
    font.size = font.size
  )

  if (!is.null(signaling)) args$signaling <- signaling

  do.call(CellChat::netAnalysis_signalingRole_network, args)
}


#' Identify CellChat Communication Patterns
#'
#' Identify global communication patterns using NMF.
#'
#' @param cellchat CellChat object
#' @param pattern Pattern type: "outgoing" or "incoming" (default: "outgoing")
#' @param k Number of patterns (default: 5)
#' @param ... Additional arguments
#'
#' @return CellChat object with patterns identified
#'
#' @examples
#' \dontrun{
#' cellchat <- identify_cellchat_patterns(cellchat, pattern = "outgoing", k = 5)
#' netAnalysis_river(cellchat, pattern = "outgoing")
#' }
#'
#' @export
identify_cellchat_patterns <- function(
    cellchat,
    pattern = "outgoing",
    k = 5,
    ...
) {
  if (!requireNamespace("NMF", quietly = TRUE)) {
    stop("NMF package required for pattern analysis")
  }

  cellchat <- CellChat::identifyCommunicationPatterns(
    cellchat,
    pattern = pattern,
    k = k,
    ...
  )

  return(cellchat)
}


#' Compare CellChat Conditions
#'
#' Merge and compare multiple CellChat objects.
#'
#' @param object.list Named list of CellChat objects
#' @param add.names Names for each condition
#' @param ... Additional arguments
#'
#' @return Merged CellChat comparison object
#'
#' @examples
#' \dontrun{
#' comparison <- compare_cellchat_conditions(
#'   list(Control = control, Treatment = treatment),
#'   add.names = c("Control", "Treatment")
#' )
#' }
#'
#' @export
compare_cellchat_conditions <- function(
    object.list,
    add.names = NULL,
    ...
) {
  if (is.null(add.names)) {
    add.names <- names(object.list)
  }

  if (is.null(add.names)) {
    add.names <- paste0("Condition", seq_along(object.list))
  }

  message(sprintf("Comparing %d conditions: %s",
                  length(object.list), paste(add.names, collapse = ", ")))

  cellchat <- CellChat::mergeCellChat(
    object.list,
    add.names = add.names,
    ...
  )

  return(cellchat)
}


#' Plot CellChat Comparison
#'
#' Visualize comparison between conditions.
#'
#' @param comparison Merged CellChat comparison object
#' @param measure Metric: "count" or "weight" (default: "count")
#' @param ... Additional arguments
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' comparison <- compare_cellchat_conditions(list(Ctrl = ctrl, Treat = treat))
#' plot_cellchat_comparison(comparison)
#' }
#'
#' @export
plot_cellchat_comparison <- function(
    comparison,
    measure = "count",
    ...
) {
  CellChat::compareInteractions(comparison, measure = measure, ...)
}


#' Extract CellChat Communications
#'
#' Extract inferred communications as data frame.
#'
#' @param cellchat CellChat object
#' @param slot_name Slot to extract: "net" or "netP" (default: "net")
#' @param signaling Filter by signaling pathway (optional)
#' @param sources.use Filter by sources (optional)
#' @param targets.use Filter by targets (optional)
#'
#' @return Data frame with communication data
#'
#' @examples
#' \dontrun{
#' # All LR pairs
#' df_net <- extract_cellchat_communications(cellchat)
#'
#' # Specific pathway
#' df_cxcl <- extract_cellchat_communications(cellchat, signaling = "CXCL")
#' }
#'
#' @export
extract_cellchat_communications <- function(
    cellchat,
    slot_name = "net",
    signaling = NULL,
    sources.use = NULL,
    targets.use = NULL
) {
  df <- subsetCommunication(
    cellchat,
    slot.name = slot_name,
    signaling = signaling,
    sources.use = sources.use,
    targets.use = targets.use
  )

  return(df)
}


#' Summarize CellChat Results
#'
#' Summarize cell-cell communication by group.
#'
#' @param cellchat CellChat object
#' @param measure Metric: "count" or "weight" (default: "count")
#'
#' @return Data frame with summary
#'
#' @examples
#' \dontrun{
#' summary <- summarize_cellchat(cellchat)
#' print(summary)
#' }
#'
#' @export
summarize_cellchat <- function(
    cellchat,
    measure = "count"
) {
  if (measure == "count") {
    mat <- cellchat@net$count
  } else {
    mat <- cellchat@net$weight
  }

  summary <- data.frame(
    cell_group = rownames(mat),
    outgoing = rowSums(mat),
    incoming = colSums(mat),
    total = rowSums(mat) + colSums(mat)
  )

  summary <- summary[order(-summary$total), ]

  return(summary)
}


#' Export CellChat Results
#'
#' Export CellChat analysis to files.
#'
#' @param cellchat CellChat object
#' @param output_dir Output directory (default: "cellchat_results")
#' @param prefix File prefix (default: "cellchat")
#' @param export_object Whether to save RDS (default: TRUE)
#'
#' @return None (saves files)
#'
#' @examples
#' \dontrun{
#' export_cellchat_results(cellchat, output_dir = "./results", prefix = "sample1")
#' }
#'
#' @export
export_cellchat_results <- function(
    cellchat,
    output_dir = "cellchat_results",
    prefix = "cellchat",
    export_object = TRUE
) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Extract and save communications
  df_net <- extract_cellchat_communications(cellchat)
  write.csv(df_net, file.path(output_dir, paste0(prefix, "_lr_pairs.csv")), row.names = FALSE)

  # Pathway-level
  df_pathway <- extract_cellchat_communications(cellchat, slot_name = "netP")
  write.csv(df_pathway, file.path(output_dir, paste0(prefix, "_pathways.csv")), row.names = FALSE)

  # Summary
  summary <- summarize_cellchat(cellchat)
  write.csv(summary, file.path(output_dir, paste0(prefix, "_summary.csv")), row.names = FALSE)

  # Save object
  if (export_object) {
    saveRDS(cellchat, file.path(output_dir, paste0(prefix, ".rds")))
  }

  message(sprintf("Results exported to: %s", output_dir))
}
