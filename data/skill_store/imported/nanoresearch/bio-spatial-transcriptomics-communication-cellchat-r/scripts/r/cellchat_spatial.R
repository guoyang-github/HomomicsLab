#' Spatial Cell-Cell Communication Analysis with SpatialCellChat (CellChat v3)
#'
#' R wrapper functions for SpatialCellChat analysis on spatial transcriptomics data.
#' Supports Visium, Visium HD, Xenium, Slide-seq, CosMx, and Stereo-seq.
#'
#' Based on SpatialCellChat best practices:
#' https://github.com/jinworks/SpatialCellChat
#'
#' @author Yang Guo
#' @date 2026-05-14
#' @version 2.0.0

#' Run CellChat on Spatial Transcriptomics Data
#'
#' Main wrapper function for spatial CellChat analysis with automatic
#' technology detection and parameter configuration.
#'
#' @param seurat_obj Seurat object with spatial data
#' @param group_by Metadata column for cell groups (default: "cell_type")
#' @param sample_name Sample name identifier
#' @param spatial_tech Spatial technology: "visium", "xenium", "slideseq", "cosmx", "stereoseq" (default: "visium")
#' @param assay Seurat assay to use. Defaults to "Spatial" for Visium, otherwise DefaultAssay (default: NULL)
#' @param db_use Database: "CellChatDB.human" or "CellChatDB.mouse" (default: "CellChatDB.human")
#' @param signaling_type Signaling type(s): "Secreted Signaling", "Cell-Cell Contact", "ECM-Receptor", or "all". Can be a single string or a character vector. (default: c("Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact"))
#' @param interaction_range Maximum communication distance in um (default: 250)
#' @param contact_range Contact-dependent range in um (default: NULL)
#' @param contact_dependent Whether to restrict to contact-dependent signaling (default: FALSE)
#' @param scale_distance Scale factor for distance (default: 0.01)
#' @param spatial_factors List with ratio and tol, or NULL for auto-detect (default: NULL)
#' @param cell_types Character vector of cell types to include. If NULL, all cell types are used (default: NULL)
#' @param min_cells Minimum cells per group at group-level filtering (default: 10)
#' @param min_links Minimum links for filtering after computeCommunProb (default: 10)
#' @param verbose Whether to print progress (default: TRUE)
#'
#' @return SpatialCellChat object with spatial communication analysis
#'
#' @examples
#' \dontrun{
#' # Visium with auto-detected factors
#' cellchat <- run_cellchat_spatial(
#'   seurat_obj = visium_data,
#'   group_by = "cell_type",
#'   sample_name = "Visium_Sample",
#'   spatial_tech = "visium"
#' )
#'
#' # Xenium (single-cell resolution)
#' cellchat <- run_cellchat_spatial(
#'   seurat_obj = xenium_data,
#'   group_by = "cell_type",
#'   spatial_tech = "xenium"
#' )
#' }
#'
#' @export
# Helper: get assay names compatible with Seurat v4 and v5
.get_assay_names <- function(seurat_obj) {
  tryCatch(
    SeuratObject::Assays(seurat_obj),
    error = function(e) names(seurat_obj@assays)
  )
}

# Helper: safely get tissue coordinates compatible with Seurat v4 and v5
.safe_get_coords <- function(seurat_obj) {
  coords <- Seurat::GetTissueCoordinates(seurat_obj)
  coords <- as.data.frame(coords)
  if (is.null(rownames(coords))) {
    rownames(coords) <- colnames(seurat_obj)
  }
  return(coords)
}

run_cellchat_spatial <- function(
    seurat_obj,
    group_by = "cell_type",
    sample_name = "Sample",
    spatial_tech = "visium",
    assay = NULL,
    db_use = "CellChatDB.human",
    signaling_type = c("Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact"),
    interaction_range = 250,
    contact_range = NULL,
    contact_dependent = FALSE,
    scale_distance = 0.01,
    spatial_factors = NULL,
    cell_types = NULL,
    min_cells = 10,
    min_links = 10,
    verbose = TRUE
) {
  if (!requireNamespace("SpatialCellChat", quietly = TRUE)) {
    stop("SpatialCellChat package required. Install with: remotes::install_github('jinworks/SpatialCellChat')")
  }

  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  if (verbose) {
    message(sprintf("Running SpatialCellChat analysis on: %s", sample_name))
    message(sprintf("  Technology: %s", spatial_tech))
    message(sprintf("  Cells: %d, Groups: %d", ncol(seurat_obj), length(unique(seurat_obj@meta.data[[group_by]]))))
  }

  # Create SpatialCellChat object with spatial information
  cellchat <- create_spatial_cellchat(
    seurat_obj = seurat_obj,
    group_by = group_by,
    spatial_tech = spatial_tech,
    assay = assay,
    spatial_factors = spatial_factors,
    verbose = verbose
  )

  # Subset to specific cell types if requested
  if (!is.null(cell_types)) {
    if (verbose) message(sprintf("Subsetting to cell types: %s", paste(cell_types, collapse = ", ")))
    cellchat <- subsetSpatialCellChat(cellchat, idents.use = cell_types)
  }

  # Set database
  cellchat <- set_cellchat_db(cellchat, db_use, signaling_type)

  # Preprocessing
  if (verbose) message("Preprocessing expression data...")
  cellchat <- subsetData(cellchat)
  cellchat <- preProcessing(cellchat)

  # Identify spatially variable genes for spatial data
  cellchat <- identifyOverExpressedGenes(
    cellchat,
    selection.method = "meringue",
    do.grid = FALSE
  )
  cellchat <- identifyOverExpressedInteractions(cellchat, variable.both = FALSE)

  # Compute communication probability with spatial constraint
  if (verbose) message("Computing communication probability...")

  # Determine contact range if not provided
  if (is.null(contact_range)) {
    contact_range <- switch(spatial_tech,
      "visium" = 100,
      10  # default for single-cell resolution
    )
  }

  cellchat <- computeCommunProb(
    cellchat,
    type = "truncatedMean",
    trim = 0.1,
    distance.use = TRUE,
    interaction.range = interaction_range,
    scale.distance = scale_distance,
    contact.dependent = contact_dependent,
    contact.range = contact_range
  )

  # Filter non-significant communications
  cellchat <- filterProbability(cellchat)

  # Filter by min links (before aggregation)
  cellchat <- filterCommunication(
    cellchat,
    min.cells = NULL,
    min.links = min_links,
    min.cells.sr = min_cells
  )

  # Pathway-level analysis
  if (verbose) message("Computing pathway-level communication...")
  cellchat <- computeCommunProbPathway(cellchat)
  cellchat <- aggregateNet(cellchat)

  # Compute centrality
  # Note: do.group is not a valid parameter for netAnalysis_computeCentrality in standard CellChat.
  # If group-level centrality is needed, use netAnalysis_computeCentrality with appropriate grouping.
  cellchat <- netAnalysis_computeCentrality(cellchat, slot.name = "netP", degree.only = TRUE)

  if (verbose) message("SpatialCellChat analysis complete!")

  return(cellchat)
}


#' Run CellChat on 10X Visium Data
#'
#' Specialized wrapper for 10X Visium spatial transcriptomics data.
#' For Visium (low-resolution), this wrapper also supports computing
#' group-level communication using cell type decomposition proportions.
#'
#' @param seurat_obj Seurat object with Visium data
#' @param group_by Metadata column for cell groups (default: "cell_type")
#' @param sample_name Sample name
#' @param scalefactors_json Path to scalefactors_json.json file
#' @param spot_size Theoretical spot size in um (default: 65)
#' @param assay Seurat assay to use (default: "Spatial")
#' @param db_use Database to use (default: "CellChatDB.human")
#' @param interaction_range Maximum communication distance (default: 250)
#' @param contact_range Contact range for juxtacrine (default: 100)
#' @param cell_type_decomposition Cell type proportion matrix (spots x cell_types) from deconvolution. If provided, computeAvgCommunProb_Visium is used. (default: NULL)
#' @param avg_type Averaging type for Visium: "avg" or "sum" (default: "avg")
#' @param nboot Number of bootstrap permutations for Visium group-level computation (default: 100)
#' @param ... Additional arguments passed to run_cellchat_spatial()
#'
#' @return SpatialCellChat object
#'
#' @examples
#' \dontrun{
#' cellchat <- run_cellchat_visium(
#'   seurat_obj = visium_data,
#'   group_by = "cell_type",
#'   sample_name = "Visium_Sample",
#'   scalefactors_json = "spatial/scalefactors_json.json"
#' )
#'
#' # With deconvolution proportions (e.g., from RCTD/SPOTlight)
#' cellchat <- run_cellchat_visium(
#'   seurat_obj = visium_data,
#'   group_by = "cell_type",
#'   scalefactors_json = "spatial/scalefactors_json.json",
#'   cell_type_decomposition = deconv_proportions
#' )
#' }
#'
#' @export
run_cellchat_visium <- function(
    seurat_obj,
    group_by = "cell_type",
    sample_name = "Visium_Sample",
    scalefactors_json = NULL,
    spot_size = 65,
    assay = "Spatial",
    db_use = "CellChatDB.human",
    interaction_range = 250,
    contact_range = 100,
    cell_type_decomposition = NULL,
    avg_type = "avg",
    nboot = 100,
    ...
) {
  if (is.null(scalefactors_json)) {
    warning(
      "scalefactors_json not provided. Using generic Visium defaults (ratio=0.5). ",
      "Results may be inaccurate. Provide 'spatial/scalefactors_json.json' from Space Ranger ",
      "for correct pixel-to-um conversion."
    )
    spatial_factors <- infer_spatial_factors(NULL, "visium")
  } else if (!file.exists(scalefactors_json)) {
    warning(
      sprintf("scalefactors_json '%s' not found. Using generic Visium defaults (ratio=0.5). ", scalefactors_json),
      "Results may be inaccurate. Ensure the path points to 'spatial/scalefactors_json.json' from Space Ranger."
    )
    spatial_factors <- infer_spatial_factors(NULL, "visium")
  } else {
    # Read scalefactors
    scalefactors <- jsonlite::fromJSON(txt = scalefactors_json)
    conversion_factor <- spot_size / scalefactors$spot_diameter_fullres

    # Spatial factors must be a list for SpatialCellChat
    spatial_factors <- list(
      ratio = conversion_factor,
      tol = spot_size / 2
    )

    message(sprintf("Visium conversion factor: %.4f", conversion_factor))
  }

  cellchat <- run_cellchat_spatial(
    seurat_obj = seurat_obj,
    group_by = group_by,
    sample_name = sample_name,
    spatial_tech = "visium",
    assay = assay,
    db_use = db_use,
    interaction_range = interaction_range,
    contact_range = contact_range,
    spatial_factors = spatial_factors,
    ...
  )

  # For Visium with deconvolution, compute group-level communication
  if (!is.null(cell_type_decomposition)) {
    message("Computing group-level communication for Visium with cell type decomposition...")
    cellchat <- computeAvgCommunProb_Visium(
      cellchat,
      cell.type.decomposition = as.matrix(cell_type_decomposition),
      avg.type = avg_type,
      nboot = nboot,
      do.permutation = TRUE
    )
    # Re-filter at group level
    cellchat <- filterCommunication(cellchat, min.cells = 10)
    # Re-compute pathway and aggregate after group-level computation
    cellchat <- computeCommunProbPathway(cellchat)
    cellchat <- aggregateNet(cellchat)
  }

  return(cellchat)
}


#' Run CellChat on Single-Cell Resolution Spatial Data
#'
#' Wrapper for Xenium, Visium HD, CosMx, and other single-cell resolution technologies.
#'
#' @param seurat_obj Seurat object
#' @param group_by Metadata column
#' @param sample_name Sample name
#' @param spatial_tech Technology: "xenium", "visium_hd", "cosmx", "slideseq" (default: "xenium")
#' @param spot_size Cell diameter in um (default: 10)
#' @param interaction_range Maximum distance (default: 250)
#' @param ... Additional arguments passed to run_cellchat_spatial()
#'
#' @return SpatialCellChat object
#'
#' @examples
#' \dontrun{
#' # Xenium
#' cellchat <- run_cellchat_sc_resolution(
#'   seurat_obj = xenium_data,
#'   group_by = "cell_type",
#'   spatial_tech = "xenium"
#' )
#'
#' # CosMx
#' cellchat <- run_cellchat_sc_resolution(
#'   seurat_obj = cosmx_data,
#'   group_by = "cell_type",
#'   spatial_tech = "cosmx"
#' )
#' }
#'
#' @export
run_cellchat_sc_resolution <- function(
    seurat_obj,
    group_by = "cell_type",
    sample_name = "SC_Sample",
    spatial_tech = "xenium",
    spot_size = 10,
    interaction_range = 250,
    ...
) {
  # Set conversion factor based on technology
  conversion_factor <- switch(spatial_tech,
    "xenium" = 1,
    "visium_hd" = 1,
    "cosmx" = 0.12028,
    "slideseq" = 0.73,
    1  # default
  )

  # For CosMx, compute tol from data
  tol <- spot_size / 2
  if (spatial_tech == "cosmx") {
    spatial_locs <- .safe_get_coords(seurat_obj)
    d <- SpatialCellChat::computeCellDistance(spatial_locs)
    tol <- min(d[d != 0]) * conversion_factor / 2
  }

  # Spatial factors must be a list
  spatial_factors <- list(
    ratio = conversion_factor,
    tol = tol
  )

  message(sprintf("%s: ratio=%.5f, tol=%.2f", spatial_tech, conversion_factor, tol))

  cellchat <- run_cellchat_spatial(
    seurat_obj = seurat_obj,
    group_by = group_by,
    sample_name = sample_name,
    spatial_tech = spatial_tech,
    interaction_range = interaction_range,
    contact_range = spot_size,
    spatial_factors = spatial_factors,
    ...
  )

  return(cellchat)
}


#' Run CellChat on Multiple Spatial Samples
#'
#' Analyze multiple spatial samples. For best results, run each sample
#' separately and then merge using mergeSpatialCellChat().
#'
#' @param seurat_list List of Seurat objects
#' @param group_by Metadata column
#' @param sample_names Character vector of sample names
#' @param scalefactors_list List of scalefactors objects or file paths (for Visium)
#' @param spot_size Spot size in um (default: 65)
#' @param spatial_tech Technology type for all samples (default: "visium")
#' @param ... Additional arguments passed to run_cellchat_spatial()
#'
#' @return List of SpatialCellChat objects (one per sample)
#'
#' @examples
#' \dontrun{
#' # Run each sample individually
#' chat_list <- run_cellchat_multi(
#'   seurat_list = list(s1, s2, s3),
#'   sample_names = c("S1", "S2", "S3"),
#'   scalefactors_list = list(sf1, sf2, sf3),
#'   spatial_tech = "visium"
#' )
#'
#' # Merge for comparison
#' chat_merged <- mergeSpatialCellChat(chat_list, add.names = c("S1", "S2", "S3"))
#' }
#'
#' @export
run_cellchat_multi <- function(
    seurat_list,
    group_by = "cell_type",
    sample_names = NULL,
    scalefactors_list = NULL,
    spot_size = 65,
    spatial_tech = "visium",
    ...
) {
  if (!is.list(seurat_list)) {
    stop("seurat_list must be a list of Seurat objects")
  }

  if (is.null(sample_names)) {
    sample_names <- paste0("Sample", seq_along(seurat_list))
  }

  if (length(seurat_list) != length(sample_names)) {
    stop("seurat_list and sample_names must have same length")
  }

  message(sprintf("Processing %d samples...", length(seurat_list)))

  chat_list <- list()

  for (i in seq_along(seurat_list)) {
    seu <- seurat_list[[i]]
    sname <- sample_names[i]

    message(sprintf("\n--- Processing sample: %s ---", sname))

    # Get spatial factors for this sample
    if (!is.null(scalefactors_list)) {
      sf <- scalefactors_list[[i]]
      if (is.character(sf)) {
        sf <- jsonlite::fromJSON(sf)
      }
      conversion_factor <- spot_size / sf$spot_diameter_fullres
      spatial_factors <- list(
        ratio = conversion_factor,
        tol = spot_size / 2
      )
    } else {
      spatial_factors <- NULL
    }

    # Run analysis for this sample
    cellchat <- run_cellchat_spatial(
      seurat_obj = seu,
      group_by = group_by,
      sample_name = sname,
      spatial_tech = spatial_tech,
      spatial_factors = spatial_factors,
      ...
    )

    chat_list[[i]] <- cellchat
  }

  names(chat_list) <- sample_names
  return(chat_list)
}


#' Create SpatialCellChat Object from Seurat
#'
#' Helper function to create SpatialCellChat object from spatial data.
#' Uses createSpatialCellChat from the SpatialCellChat package.
#'
#' @param seurat_obj Seurat object
#' @param group_by Metadata column
#' @param spatial_tech Spatial technology
#' @param assay Seurat assay to use (default: NULL, uses DefaultAssay)
#' @param spatial_factors Pre-computed spatial factors list with ratio and tol (optional)
#' @param verbose Print progress
#'
#' @return SpatialCellChat object
#'
#' @keywords internal
#' @export
create_spatial_cellchat <- function(
    seurat_obj,
    group_by = "cell_type",
    spatial_tech = "visium",
    assay = NULL,
    spatial_factors = NULL,
    verbose = TRUE
) {
  if (!requireNamespace("SpatialCellChat", quietly = TRUE)) {
    stop("SpatialCellChat package required")
  }

  # Auto-detect assay if not provided
  if (is.null(assay)) {
    if (spatial_tech == "visium" && "Spatial" %in% .get_assay_names(seurat_obj)) {
      assay <- "Spatial"
    } else {
      assay <- Seurat::DefaultAssay(seurat_obj)
    }
    if (verbose) message(sprintf("Using assay: %s", assay))
  }

  # Check that group_by exists
  meta_cols <- colnames(seurat_obj@meta.data)
  if (!group_by %in% meta_cols) {
    stop(sprintf("'%s' not found in metadata columns: %s",
                 group_by, paste(meta_cols, collapse = ", ")))
  }

  # Get spatial coordinates (v4/v5 compatible)
  coords <- .safe_get_coords(seurat_obj)

  # Auto-detect spatial factors if not provided
  if (is.null(spatial_factors)) {
    spatial_factors <- infer_spatial_factors(coords, spatial_tech)
  }

  # Ensure spatial_factors is a list
  if (is.data.frame(spatial_factors)) {
    spatial_factors <- list(
      ratio = spatial_factors$ratio[1],
      tol = spatial_factors$tol[1]
    )
  }

  if (verbose) {
    message(sprintf("Spatial factors: ratio=%.4f, tol=%.2f",
                    spatial_factors$ratio, spatial_factors$tol))
  }

  # Create SpatialCellChat object using the package function
  cellchat <- SpatialCellChat::createSpatialCellChat(
    object = seurat_obj,
    group.by = group_by,
    assay = assay,
    datatype = "spatial",
    coordinates = coords,
    spatial.factors = spatial_factors
  )

  return(cellchat)
}


#' Infer Spatial Factors from Data
#'
#' Automatically infer spatial factors based on technology type.
#' Returns a list with ratio and tol.
#'
#' @param coords Spatial coordinates data frame
#' @param spatial_tech Technology type
#'
#' @return List with ratio and tol
#'
#' @keywords internal
#' @export
infer_spatial_factors <- function(coords, spatial_tech = "visium") {
  switch(spatial_tech,
    "visium" = {
      message("Warning: Using default Visium factors. Provide scalefactors_json for accuracy.")
      list(ratio = 0.5, tol = 32.5)
    },
    "xenium" = , "visium_hd" = , "merfish" = , "seqfish" = {
      list(ratio = 1, tol = 5)
    },
    "slideseq" = {
      list(ratio = 0.73, tol = 5)
    },
    "cosmx" = {
      d <- SpatialCellChat::computeCellDistance(coords)
      min_dist <- min(d[d != 0])
      list(ratio = 0.12028, tol = min_dist * 0.12028 / 2)
    },
    {
      message("Unknown technology, using defaults")
      list(ratio = 1, tol = 5)
    }
  )
}


#' Set CellChat Database
#'
#' Configure CellChat database and signaling subset using subsetDB.
#'
#' @param cellchat SpatialCellChat object
#' @param db_use Database name: "CellChatDB.human" or "CellChatDB.mouse"
#' @param signaling_type Signaling type(s) to subset. Can be a single string, character vector, or "all". (default: c("Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact"))
#'
#' @return SpatialCellChat object with database set
#'
#' @keywords internal
#' @export
set_cellchat_db <- function(
    cellchat,
    db_use = "CellChatDB.human",
    signaling_type = c("Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact")
) {
  # Load database
  CellChatDB <- switch(db_use,
    "CellChatDB.human" = SpatialCellChat::CellChatDB.human,
    "CellChatDB.mouse" = SpatialCellChat::CellChatDB.mouse,
    SpatialCellChat::CellChatDB.human
  )

  # Subset database using subsetDB
  if (length(signaling_type) == 1 && signaling_type == "all") {
    CellChatDB.use <- subsetDB(CellChatDB)
  } else {
    CellChatDB.use <- subsetDB(CellChatDB, search = signaling_type, non_protein = FALSE)
  }

  cellchat@DB <- CellChatDB.use

  return(cellchat)
}


#' Plot Spatial Communication Scoring
#'
#' Visualize outgoing/incoming communication scores on spatial coordinates.
#' This wrapper merges outgoing and incoming plots side-by-side when merge=FALSE,
#' or overlays them in a single plot when merge=TRUE.
#'
#' @param cellchat SpatialCellChat object
#' @param signaling Signaling pathway or LR pair name
#' @param slot_name Slot name: "net" or "netP" (default: "netP")
#' @param measure Measure: "outdeg" or "indeg" (default: c("outdeg", "indeg"))
#' @param do_binary Binary expression (default: FALSE)
#' @param point_size Point size (default: 1)
#' @param merge Merge outgoing and incoming plots (default: FALSE)
#' @param ... Additional arguments
#'
#' @return Plot object or list of plots
#'
#' @export
plot_spatial_scoring <- function(
    cellchat,
    signaling,
    slot_name = "netP",
    measure = c("outdeg", "indeg"),
    do_binary = FALSE,
    point_size = 1,
    merge = FALSE,
    ...
) {
  args <- list(
    object = cellchat,
    signaling = signaling,
    slot.name = slot_name,
    do.binary = do_binary,
    point.size = point_size,
    merge = merge,
    ...
  )

  if (!merge && length(measure) == 2) {
    # Return side-by-side plots
    gg1 <- do.call(SpatialCellChat::spatialVisual_scoring, c(args, list(measure = measure[1], color.heatmap = "Blues")))
    gg2 <- do.call(SpatialCellChat::spatialVisual_scoring, c(args, list(measure = measure[2], color.heatmap = "Reds")))
    return(patchwork::wrap_plots(gg1, gg2, ncol = 2))
  } else {
    args$measure <- measure
    do.call(SpatialCellChat::spatialVisual_scoring, args)
  }
}


# =============================================================================
# Result Extraction and Export
# =============================================================================

#' Extract Communication Data Frame
#'
#' Extract inferred cell-cell communications as data frame.
#'
#' @param cellchat SpatialCellChat object
#' @param slot_name Slot to extract: "net" or "netP" (default: "net")
#' @param signaling Filter by signaling pathway (optional)
#' @param sources.use Source cell groups (optional)
#' @param targets.use Target cell groups (optional)
#'
#' @return Data frame with communication data
#'
#' @examples
#' \dontrun{
#' # All communications
#' df_net <- extract_communication_df(cellchat)
#'
#' # Specific pathway
#' df_cxcl <- extract_communication_df(cellchat, signaling = "CXCL")
#' }
#'
#' @export
extract_communication_df <- function(
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


#' Extract Enriched Ligand-Receptor Pairs
#'
#' Extract all significant interactions for a given signaling pathway.
#'
#' @param cellchat SpatialCellChat object
#' @param signaling Signaling pathway name
#' @param do.group Group-level extraction (default: FALSE)
#' @param geneLR.return Return gene list (default: FALSE)
#'
#' @return Data frame of enriched LR pairs, or list with geneLR
#'
#' @export
extract_enriched_lr <- function(
    cellchat,
    signaling,
    do.group = FALSE,
    geneLR.return = FALSE
) {
  SpatialCellChat::extractEnrichedLR(
    cellchat,
    signaling = signaling,
    do.group = do.group,
    geneLR.return = geneLR.return
  )
}


#' Summarize Communication by Group
#'
#' Summarize cell-cell communication by source/target groups.
#'
#' @param cellchat SpatialCellChat object
#' @param measure Metric: "count" or "weight" (default: "count")
#'
#' @return Data frame with summary
#'
#' @examples
#' \dontrun{
#' summary <- summarize_communication(cellchat)
#' print(summary)
#' }
#'
#' @export
summarize_communication <- function(
    cellchat,
    measure = "count"
) {
  net <- cellchat@net

  if (measure == "count") {
    mat <- net$count
  } else {
    mat <- net$weight
  }

  # Summarize by source
  source_sum <- data.frame(
    cell_group = rownames(mat),
    outgoing = rowSums(mat),
    incoming = colSums(mat),
    total = rowSums(mat) + colSums(mat)
  )

  source_sum <- source_sum[order(-source_sum$total), ]

  return(source_sum)
}


#' Export CellChat Results
#'
#' Export CellChat analysis results to files.
#'
#' @param cellchat SpatialCellChat object
#' @param output_dir Output directory (default: "cellchat_results")
#' @param prefix File prefix (default: "cellchat")
#' @param export_network Whether to export network matrices (default: TRUE)
#' @param export_centrality Whether to export centrality scores (default: TRUE)
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
    export_network = TRUE,
    export_centrality = TRUE
) {
  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

  # Export communication data
  df_net <- extract_communication_df(cellchat)
  write.csv(df_net, file.path(output_dir, paste0(prefix, "_lr_pairs.csv")), row.names = FALSE)

  # Export pathway-level
  df_pathway <- extract_communication_df(cellchat, slot_name = "netP")
  write.csv(df_pathway, file.path(output_dir, paste0(prefix, "_pathways.csv")), row.names = FALSE)

  # Export network matrices
  if (export_network) {
    write.csv(cellchat@net$count, file.path(output_dir, paste0(prefix, "_count.csv")))
    write.csv(cellchat@net$weight, file.path(output_dir, paste0(prefix, "_weight.csv")))
  }

  # Export centrality scores if available
  if (export_centrality && "centr" %in% names(cellchat@netP)) {
    centr <- cellchat@netP$centr
    # Save centrality as a list of matrices per signaling pathway
    for (sig_name in dimnames(centr)[[3]]) {
      centr_mat <- centr[, , sig_name]
      write.csv(centr_mat, file.path(output_dir, paste0(prefix, "_centrality_", sig_name, ".csv")))
    }
  }

  # Save CellChat object
  saveRDS(cellchat, file.path(output_dir, paste0(prefix, ".rds")))

  message(sprintf("Results exported to: %s", output_dir))
}
