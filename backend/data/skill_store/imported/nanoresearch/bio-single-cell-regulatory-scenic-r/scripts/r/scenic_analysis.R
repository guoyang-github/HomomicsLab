# SCENIC Regulatory Network Analysis Functions
#
# Wrapper functions for SCENIC pipeline to infer gene regulatory networks
# and cell type specific regulons from single-cell RNA-seq data.
#
# Features based on SCENIC package best practices:
# - Resume capability for interrupted GENIE3 runs
# - TF validation with percentage checking
# - Correlation-based network as GENIE3 alternative
# - Flexible module creation with weight thresholds
# - Binarization support for regulon activity
#
# @author Yang Guo
# @date 2026-04-03
# @version 2.0.0

#' Initialize SCENIC Analysis
#'
#' Set up SCENIC options with automatic database detection.
#'
#' @param org Organism: "hgnc" (human) or "mmusculus" (mouse)
#' @param dbDir Directory for cisTarget databases (default: "cisTarget")
#' @param datasetTitle Dataset name
#' @param nCores Number of cores to use (default: 4)
#'
#' @return SCENIC options list
#' @export
#'
#' @examples
#' \dontrun{
#' scenicOptions <- init_scenic("hgnc", dbDir = "cisTarget")
#' }
init_scenic <- function(org = c("hgnc", "mmusculus"),
                        dbDir = "cisTarget",
                        datasetTitle = "SCENIC",
                        nCores = 4) {
  if (!requireNamespace("SCENIC", quietly = TRUE)) {
    stop("SCENIC package required. Install with: BiocManager::install('SCENIC')")
  }

  library(SCENIC)

  org <- match.arg(org)

  # Check if cisTarget database exists
  if (!dir.exists(dbDir)) {
    warning(sprintf("cisTarget database directory not found: %s", dbDir))
    message("Use init_scenic_auto() for automatic database download,")
    message("or download manually from: https://resources.aertslab.org/cistarget/")
    message("R function: download_cistarget_databases(org='%s', dbDir='%s')", org, dbDir)
  }

  # Get default database names
  dbs <- SCENIC::defaultDbNames[[org]]

  # Initialize SCENIC options
  scenicOptions <- SCENIC::initializeScenic(
    org = org,
    dbDir = dbDir,
    dbs = dbs,
    datasetTitle = datasetTitle,
    nCores = nCores
  )

  message(sprintf("SCENIC initialized for %s", org))
  message(sprintf("Using databases: %s", paste(names(dbs), collapse = ", ")))

  return(scenicOptions)
}


#' Validate TF List Against Expression Matrix
#'
#' Check overlap between database TF list and expression matrix genes.
#' Warns if overlap is insufficient for meaningful analysis.
#'
#' @param exprMat Expression matrix (genes x cells)
#' @param tfList Vector of transcription factor names from database
#' @param minOverlapPct Minimum required overlap percentage (default: 80)
#'
#' @return List with validation results: overlap count, percentage, missing TFs
#' @export
#'
#' @examples
#' \dontrun{
#' tfList <- getDbTfs(scenicOptions)
#' validation <- validate_tf_list(exprMat, tfList)
#' print(validation$overlapPct)
#' }
validate_tf_list <- function(exprMat, tfList, minOverlapPct = 80) {
  genesInExpr <- rownames(exprMat)

  # Check overlap
  overlapTFs <- intersect(tfList, genesInExpr)
  missingTFs <- setdiff(tfList, genesInExpr)

  overlapCount <- length(overlapTFs)
  totalTFs <- length(tfList)
  overlapPct <- (overlapCount / totalTFs) * 100

  # Create result
  result <- list(
    overlapCount = overlapCount,
    totalTFs = totalTFs,
    overlapPct = overlapPct,
    missingTFs = missingTFs,
    valid = overlapPct >= minOverlapPct
  )

  # Report
  message(sprintf("TF validation: %d/%d (%.1f%%) TFs found in expression matrix",
                  overlapCount, totalTFs, overlapPct))

  if (overlapPct < minOverlapPct) {
    warning(sprintf("Low TF overlap (%.1f%% < %d%%). Check gene ID format (should match database).",
                    overlapPct, minOverlapPct))
    if (length(missingTFs) > 0 && length(missingTFs) <= 20) {
      message("Missing TFs: ", paste(head(missingTFs, 10), collapse = ", "))
    }
  } else {
    message("TF validation passed.")
  }

  return(result)
}


#' Build Correlation-Based Network
#'
#' Alternative to GENIE3 for building co-expression network using
#' Spearman correlation. Much faster but may miss non-linear relationships.
#'
#' @param exprMat Expression matrix (genes x cells)
#' @param scenicOptions SCENIC options
#' @param corMethod Correlation method: "spearman" (default) or "pearson"
#' @param corThreshold Minimum absolute correlation to include edge (default: 0.03)
#' @param topNPerTF Number of top targets per TF to keep (default: 50)
#' @param verbose Print progress messages
#'
#' @return Invisible NULL. Saves correlation matrix to scenicOptions int directory.
#' @export
#'
#' @examples
#' \dontrun{
#' # Fast alternative to GENIE3
#' run_correlation_network(exprMat, scenicOptions, corThreshold = 0.05)
#' }
run_correlation_network <- function(exprMat,
                                    scenicOptions,
                                    corMethod = "spearman",
                                    corThreshold = 0.03,
                                    topNPerTF = 50,
                                    verbose = TRUE) {
  if (!requireNamespace("SCENIC", quietly = TRUE)) {
    stop("SCENIC package required")
  }

  library(SCENIC)

  if (verbose) message("\n[Alternative to GENIE3] Building correlation-based network...")

  # Get TF list
  allTFs <- getDbTfs(scenicOptions)
  allTFs <- intersect(allTFs, rownames(exprMat))

  if (verbose) message(sprintf("Calculating %s correlation for %d TFs...", corMethod, length(allTFs)))

  # Calculate correlation matrix
  corrMat <- cor(t(exprMat[allTFs, , drop = FALSE]),
                 t(exprMat),
                 method = corMethod)

  # Save correlation matrix
  saveRDS(corrMat, file = getIntName(scenicOptions, "corrMat"))

  if (verbose) message(sprintf("Correlation matrix saved: %d x %d", nrow(corrMat), ncol(corrMat)))

  # Convert to link list format (similar to GENIE3 output)
  if (verbose) message("Converting to link list format...")

  linkList <- data.frame(
    TF = character(),
    Target = character(),
    weight = numeric(),
    stringsAsFactors = FALSE
  )

  for (tf in allTFs) {
    corRow <- corrMat[tf, ]
    corRow <- corRow[names(corRow) != tf]  # Remove self-correlation

    # Filter by threshold and take top N
    corRow <- corRow[abs(corRow) >= corThreshold]
    corRow <- sort(corRow, decreasing = TRUE)

    if (length(corRow) > topNPerTF) {
      corRow <- corRow[1:topNPerTF]
    }

    if (length(corRow) > 0) {
      tfLinks <- data.frame(
        TF = tf,
        Target = names(corRow),
        weight = as.numeric(corRow),
        stringsAsFactors = FALSE
      )
      linkList <- rbind(linkList, tfLinks)
    }
  }

  # Save link list (compatible with SCENIC format)
  colnames(linkList) <- c("TF", "Target", "weight")
  saveRDS(linkList, file = getIntName(scenicOptions, "genie3ll"))

  if (verbose) {
    message(sprintf("Correlation network complete: %d edges", nrow(linkList)))
    message(sprintf("Average edges per TF: %.1f", nrow(linkList) / length(allTFs)))
  }

  invisible(NULL)
}


#' Run Complete SCENIC Pipeline
#'
#' Execute the full SCENIC pipeline from co-expression to regulon scoring.
#' Supports resume functionality for interrupted GENIE3 runs.
#'
#' @param exprMat Expression matrix (genes x cells)
#' @param scenicOptions SCENIC options from init_scenic()
#' @param runGenie3 Whether to run GENIE3 (default: TRUE)
#' @param nParts Number of parts for GENIE3 parallelization (default: 10)
#' @param resumePreviousRun If TRUE, resume interrupted GENIE3 run (default: FALSE)
#' @param useCorrelationNetwork If TRUE, use correlation instead of GENIE3 (default: FALSE)
#' @param weightThreshold Weight threshold for module creation (default: 0.001)
#' @param topThr Top quantile threshold for module creation (default: 0.005)
#' @param nTopTFs Number of top TFs to include in modules (default: c(5, 10, 50))
#' @param nTopTargets Number of top targets per TF (default: 50)
#' @param minGenes Minimum genes per module for RcisTarget (default: 20)
#'
#' @return SCENIC options with results
#' @export
#'
#' @examples
#' \dontrun{
#' exprMat <- GetAssayData(seurat_obj, slot = "counts")
#' scenicOptions <- run_scenic_pipeline(exprMat, scenicOptions)
#' }
run_scenic_pipeline <- function(exprMat,
                                 scenicOptions,
                                 runGenie3 = TRUE,
                                 nParts = 10,
                                 resumePreviousRun = FALSE,
                                 useCorrelationNetwork = FALSE,
                                 weightThreshold = 0.001,
                                 topThr = 0.005,
                                 nTopTFs = c(5, 10, 50),
                                 nTopTargets = 50,
                                 minGenes = 20) {
  if (!requireNamespace("SCENIC", quietly = TRUE)) {
    stop("SCENIC package required")
  }

  library(SCENIC)

  message("=== Starting SCENIC Pipeline ===")

  # Validate TF list
  message("\n[Validation] Checking TF list overlap...")
  tfList <- getDbTfs(scenicOptions)
  tfValidation <- validate_tf_list(exprMat, tfList)

  if (!tfValidation$valid) {
    warning("Low TF overlap may affect results quality. Consider checking gene ID format.")
  }

  # Step 1: Co-expression network
  message("\n[Step 1/5] Building co-expression network...")
  SCENIC::runCorrelation(exprMat, scenicOptions)

  # Step 2: GRN inference or correlation network
  if (useCorrelationNetwork) {
    message("\n[Step 2/5] Building correlation-based network (alternative to GENIE3)...")
    run_correlation_network(exprMat, scenicOptions)
  } else if (runGenie3) {
    if (resumePreviousRun && file.exists(getIntName(scenicOptions, "genie3ll"))) {
      message("\n[Step 2/5] Resuming previous GENIE3 run...")
      message("Using existing GENIE3 results from: ", getIntName(scenicOptions, "genie3ll"))
    } else {
      message("\n[Step 2/5] Running GENIE3 for GRN inference...")
      if (resumePreviousRun) {
        message("Note: resumePreviousRun=TRUE but no previous run found. Starting fresh.")
      }
      message("Note: This step may take several hours for large datasets")
      SCENIC::runGenie3(exprMat, scenicOptions, nParts = nParts)
    }
  } else {
    message("\n[Step 2/5] Skipping GRN inference (using correlation-based network only)")
  }

  # Step 3: Create modules with flexible parameters
  message("\n[Step 3/5] Creating co-expression modules...")
  message(sprintf("Parameters: weightThreshold=%.4f, topThr=%.4f, nTopTFs=%s, nTopTargets=%d",
                  weightThreshold, topThr, paste(nTopTFs, collapse = ","), nTopTargets))

  # SCENIC reads module-creation parameters from scenicOptions@settings,
  # not as direct function arguments.
  scenicOptions@settings$weightThreshold <- weightThreshold
  scenicOptions@settings$topThr <- topThr
  scenicOptions@settings$nTopTFs <- nTopTFs
  scenicOptions@settings$nTopTargets <- nTopTargets

  SCENIC::runSCENIC_1_coexNetwork2modules(scenicOptions, minGenes = minGenes)

  # Step 4: Create regulons
  message("\n[Step 4/5] Creating regulons with RcisTarget...")
  SCENIC::runSCENIC_2_createRegulons(scenicOptions, minGenes = minGenes)

  # Step 5: Score cells
  message("\n[Step 5/5] Scoring cells for regulon activity...")
  SCENIC::runSCENIC_3_scoreCells(exprMat, scenicOptions)

  message("\n=== SCENIC Pipeline Complete ===")
  return(scenicOptions)
}


#' Run AUCell Binarization
#'
#' Binarize regulon activity scores to identify cells with active regulons.
#' Uses automatic threshold detection based on bimodal distribution.
#'
#' @param scenicOptions SCENIC options
#' @param skipBoxplot Skip boxplot visualization (default: FALSE)
#' @param skipHeatmaps Skip binary heatmap (default: FALSE)
#' @param skipTsne Skip binary t-SNE (default: TRUE)
#' @param smallestPopPercent Minimum population percentage for threshold (default: 0.01)
#'
#' @return SCENIC options updated with binary activity
#' @export
#'
#' @examples
#' \dontrun{
#' # After run_scenic_pipeline()
#' scenicOptions <- run_aucell_binarization(scenicOptions)
#'
#' # Load binary activity
#' binaryActivity <- loadInt(scenicOptions, "aucell_binary_nonDupl")
#' }
run_aucell_binarization <- function(scenicOptions,
                                    skipBoxplot = FALSE,
                                    skipHeatmaps = FALSE,
                                    skipTsne = TRUE,
                                    smallestPopPercent = 0.01) {
  if (!requireNamespace("SCENIC", quietly = TRUE)) {
    stop("SCENIC package required")
  }
  if (!requireNamespace("AUCell", quietly = TRUE)) {
    stop("AUCell package required")
  }

  library(SCENIC)
  library(AUCell)

  message("\n[Step 6 - Optional] Binarizing regulon activity...")

  # Check if regulonAUC exists
  if (!file.exists(getIntName(scenicOptions, "aucell_regulonAUC"))) {
    stop("Regulon AUC not found. Please run run_scenic_pipeline() first.")
  }

  # Load regulon AUC
  regulonAUC <- loadInt(scenicOptions, "aucell_regulonAUC")

  # Explore thresholds
  message("Calculating optimal thresholds for each regulon...")
  cells_AUCellThresholds <- AUCell::AUCell_exploreThresholds(
    regulonAUC,
    smallestPopPercent = smallestPopPercent,
    assignCells = TRUE,
    plotHist = FALSE,
    verbose = FALSE,
    nCores = getSettings(scenicOptions, "nCores")
  )

  # Save thresholds
  saveRDS(cells_AUCellThresholds, file = getIntName(scenicOptions, "aucell_thresholds"))

  # Get selected thresholds
  thresholds <- AUCell::getThresholdSelected(cells_AUCellThresholds)

  # Assign cells
  regulonsCells <- setNames(lapply(names(thresholds), function(x) {
    trh <- thresholds[x]
    names(which(AUCell::getAUC(regulonAUC)[x, ] > trh))
  }), names(thresholds))

  # Convert to binary matrix
  regulonActivity <- reshape2::melt(regulonsCells)
  binaryRegulonActivity <- t(table(regulonActivity[, 1], regulonActivity[, 2]))
  class(binaryRegulonActivity) <- "matrix"

  saveRDS(binaryRegulonActivity, file = getIntName(scenicOptions, "aucell_binary_full"))

  # Create non-duplicated version (only best annotation per TF)
  onlyNonDuplicatedExtended <- function(rownames) {
    baseNames <- gsub("_extended", "", rownames)
    dupBase <- duplicated(baseNames) | duplicated(baseNames, fromLast = TRUE)
    extended <- grepl("_extended$", rownames)
    !extended | (!dupBase & extended)
  }

  binaryRegulonActivity_nonDupl <- binaryRegulonActivity[
    which(rownames(binaryRegulonActivity) %in%
            onlyNonDuplicatedExtended(rownames(binaryRegulonActivity))),
  ]

  saveRDS(binaryRegulonActivity_nonDupl, file = getIntName(scenicOptions, "aucell_binary_nonDupl"))

  # Report
  nRegulons <- nrow(binaryRegulonActivity_nonDupl)
  nCells <- ncol(binaryRegulonActivity)
  minCells <- ncol(binaryRegulonActivity) * smallestPopPercent
  activeRegulons <- sum(rowSums(binaryRegulonActivity_nonDupl) > minCells)

  message(sprintf("Binary regulon activity: %d TF regulons x %d cells", nRegulons, nCells))
  message(sprintf("(%d regulons including 'extended' versions)", nrow(binaryRegulonActivity)))
  message(sprintf("%d regulons are active in more than %.0f%% (%d) cells",
                  activeRegulons, smallestPopPercent * 100, minCells))

  # Update status
  scenicOptions@status$current <- 4

  message("\nBinarization complete!")
  invisible(scenicOptions)
}


#' Load Binary Regulon Activity
#'
#' Load binarized regulon activity matrix.
#'
#' @param scenicOptions SCENIC options
#' @param nonDuplicated If TRUE, return only non-duplicated regulons (default: TRUE)
#'
#' @return Binary activity matrix (regulons x cells)
#' @export
#'
#' @examples
#' \dontrun{
#' binaryMat <- load_binary_activity(scenicOptions)
#' # binaryMat[regulon, cell] == 1 if regulon is active in that cell
#' }
load_binary_activity <- function(scenicOptions, nonDuplicated = TRUE) {
  if (!requireNamespace("SCENIC", quietly = TRUE)) {
    stop("SCENIC package required")
  }

  library(SCENIC)

  fileName <- if (nonDuplicated) {
    getIntName(scenicOptions, "aucell_binary_nonDupl")
  } else {
    getIntName(scenicOptions, "aucell_binary_full")
  }

  if (!file.exists(fileName)) {
    stop("Binary activity not found. Please run run_aucell_binarization() first.")
  }

  binaryMat <- readRDS(fileName)
  message(sprintf("Loaded binary activity: %d regulons x %d cells",
                  nrow(binaryMat), ncol(binaryMat)))

  return(binaryMat)
}


#' Get Active Regulons Per Cell Type
#'
#' Identify regulons that are active in a significant fraction of cells
#' in each cell type based on binary activity.
#'
#' @param scenicOptions SCENIC options
#' @param cellInfo Data frame with cell annotations (row names = cell IDs)
#' @param cellTypeCol Column name containing cell type labels
#' @param minActiveFrac Minimum fraction of cells with active regulon (default: 0.25)
#' @param nonDuplicated Use non-duplicated regulon set (default: TRUE)
#'
#' @return Data frame with active regulons per cell type
#' @export
#'
#' @examples
#' \dontrun{
#' cellInfo <- data.frame(
#'   cellType = seurat_obj$cell_type,
#'   row.names = colnames(seurat_obj)
#' )
#' activeRegulons <- get_active_regulons_by_celltype(
#'   scenicOptions, cellInfo, "cellType"
#' )
#' }
get_active_regulons_by_celltype <- function(scenicOptions,
                                             cellInfo,
                                             cellTypeCol,
                                             minActiveFrac = 0.25,
                                             nonDuplicated = TRUE) {
  # Validate cellTypeCol exists
  if (!cellTypeCol %in% colnames(cellInfo)) {
    available_cols <- paste(colnames(cellInfo), collapse = "', '")
    stop(sprintf("Column '%s' not found in cellInfo. Available columns: '%s'",
                 cellTypeCol, available_cols))
  }

  # Load binary activity
  binaryMat <- load_binary_activity(scenicOptions, nonDuplicated)

  # Check cell overlap
  commonCells <- intersect(rownames(cellInfo), colnames(binaryMat))
  if (length(commonCells) == 0) {
    stop("No matching cells between cellInfo and binary activity matrix")
  }

  message(sprintf("Analyzing %d cells with binary activity...", length(commonCells)))

  binaryMat <- binaryMat[, commonCells, drop = FALSE]
  cellInfo <- cellInfo[commonCells, , drop = FALSE]

  # Calculate active fraction per cell type
  results <- data.frame()

  for (ct in unique(cellInfo[[cellTypeCol]])) {
    cellsInType <- rownames(cellInfo)[cellInfo[[cellTypeCol]] == ct]
    binarySub <- binaryMat[, cellsInType, drop = FALSE]

    activeFrac <- rowSums(binarySub) / length(cellsInType)
    activeRegulons <- names(activeFrac)[activeFrac >= minActiveFrac]

    if (length(activeRegulons) > 0) {
      ctResults <- data.frame(
        cell_type = ct,
        regulon = activeRegulons,
        active_fraction = activeFrac[activeRegulons],
        n_active_cells = rowSums(binarySub)[activeRegulons],
        n_total_cells = length(cellsInType),
        stringsAsFactors = FALSE
      )
      results <- rbind(results, ctResults)
    }
  }

  results <- results[order(results$cell_type, -results$active_fraction), ]
  message(sprintf("Found %d cell type - regulon pairs with >= %.0f%% activity",
                  nrow(results), minActiveFrac * 100))

  return(results)
}


#' Load SCENIC Results
#'
#' Load regulon AUC scores and other SCENIC outputs.
#'
#' @param scenicOptions SCENIC options
#' @param type Result type: "aucell", "regulons", "modules", "binary"
#'
#' @return Loaded SCENIC results
#' @export
#'
#' @examples
#' \dontrun{
#' regulonAUC <- load_scenic_results(scenicOptions, "aucell")
#' }
load_scenic_results <- function(scenicOptions,
                                 type = c("aucell", "regulons", "modules", "binary")) {
  if (!requireNamespace("SCENIC", quietly = TRUE)) {
    stop("SCENIC package required")
  }

  type <- match.arg(type)

  switch(type,
    "aucell" = {
      regulonAUC <- SCENIC::loadInt(scenicOptions, "aucell_regulonAUC")
      return(regulonAUC)
    },
    "regulons" = {
      regulons <- SCENIC::loadInt(scenicOptions, "regulons")
      return(regulons)
    },
    "modules" = {
      modules <- SCENIC::loadInt(scenicOptions, "modules")
      return(modules)
    },
    "binary" = {
      binary <- load_binary_activity(scenicOptions)
      return(binary)
    }
  )
}


#' Add SCENIC Results to Seurat Object
#'
#' Add regulon AUC scores as an assay to Seurat object.
#'
#' @param seurat_obj Seurat object
#' @param scenicOptions SCENIC options
#' @param assayName Name for the new assay (default: "SCENIC")
#' @param addBinary Add binary activity as well (default: FALSE)
#'
#' @return Seurat object with SCENIC assay added
#' @export
#'
#' @examples
#' \dontrun{
#' seurat_obj <- add_scenic_to_seurat(seurat_obj, scenicOptions, addBinary = TRUE)
#' }
add_scenic_to_seurat <- function(seurat_obj,
                                  scenicOptions,
                                  assayName = "SCENIC",
                                  addBinary = FALSE) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }
  if (!requireNamespace("AUCell", quietly = TRUE)) {
    stop("AUCell package required")
  }

  library(Seurat)
  library(AUCell)

  # Load regulon AUC
  regulonAUC <- load_scenic_results(scenicOptions, "aucell")
  auc_matrix <- AUCell::getAUC(regulonAUC)

  # Ensure cell order matches
  common_cells <- intersect(colnames(seurat_obj), colnames(auc_matrix))
  if (length(common_cells) == 0) {
    stop("No matching cells between Seurat object and SCENIC results")
  }

  auc_matrix <- auc_matrix[, common_cells, drop = FALSE]

  # Warn if assay already exists
  if (assayName %in% names(seurat_obj@assays)) {
    warning(sprintf("Assay '%s' already exists and will be overwritten.", assayName))
  }

  # Create assay
  scenic_assay <- Seurat::CreateAssayObject(data = auc_matrix)

  # Add to Seurat
  seurat_obj[[assayName]] <- scenic_assay

  message(sprintf("Added SCENIC assay with %d regulons", nrow(auc_matrix)))

  # Add binary activity if requested
  if (addBinary) {
    tryCatch({
      binaryMat <- load_binary_activity(scenicOptions)
      binaryMat <- binaryMat[, common_cells, drop = FALSE]

      # Store as another assay or in metadata
      binary_assay <- Seurat::CreateAssayObject(data = binaryMat)
      seurat_obj[[paste0(assayName, "_binary")]] <- binary_assay
      message(sprintf("Added binary SCENIC assay with %d regulons", nrow(binaryMat)))
    }, error = function(e) {
      warning("Could not add binary activity: ", e$message)
    })
  }

  return(seurat_obj)
}


#' Get Top Regulons
#'
#' Get top regulons by activity in specific cells or clusters.
#'
#' @param seurat_obj Seurat object with SCENIC assay
#' @param group_by Column to group by (e.g., "seurat_clusters")
#' @param top_n Number of top regulons per group (default: 10)
#' @param assayName SCENIC assay name (default: "SCENIC")
#'
#' @return Data frame with top regulons per group
#' @export
#'
#' @examples
#' \dontrun{
#' top_regulons <- get_top_regulons(seurat_obj, "seurat_clusters", top_n = 5)
#' }
get_top_regulons <- function(seurat_obj,
                              group_by = "seurat_clusters",
                              top_n = 10,
                              assayName = "SCENIC") {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(Seurat)

  # Check assay exists
  if (!assayName %in% names(seurat_obj@assays)) {
    stop(sprintf("Assay '%s' not found in Seurat object", assayName))
  }

  # Get AUC data
  DefaultAssay(seurat_obj) <- assayName
  # Handle both Seurat v4 and v5
  # SCENIC assay is created with CreateAssayObject(data = auc_matrix), so data layer/slot holds AUC values
  if (packageVersion("SeuratObject") >= "5.0.0") {
    auc_data <- GetAssayData(seurat_obj, layer = "data")
  } else {
    auc_data <- GetAssayData(seurat_obj, slot = "data")
  }

  # Check grouping column
  if (!group_by %in% colnames(seurat_obj@meta.data)) {
    stop(sprintf("Column '%s' not found in metadata", group_by))
  }

  groups <- unique(seurat_obj@meta.data[[group_by]])

  results <- data.frame()

  for (group in groups) {
    # Get cells in group
    cells <- colnames(seurat_obj)[seurat_obj@meta.data[[group_by]] == group]

    # Calculate average AUC for group
    avg_auc <- rowMeans(auc_data[, cells, drop = FALSE])

    # Get top regulons
    top_idx <- order(avg_auc, decreasing = TRUE)[1:min(top_n, length(avg_auc))]

    group_results <- data.frame(
      group = group,
      regulon = names(avg_auc)[top_idx],
      avg_auc = avg_auc[top_idx],
      stringsAsFactors = FALSE
    )

    results <- rbind(results, group_results)
  }

  return(results)
}


#' Plot Regulon Activity
#'
#' Create FeaturePlot for regulon activity.
#'
#' @param seurat_obj Seurat object with SCENIC assay
#' @param regulons Vector of regulon names to plot
#' @param reduction Dimensionality reduction to use (default: "umap")
#' @param assayName SCENIC assay name (default: "SCENIC")
#'
#' @return ggplot object or list of plots
#' @export
#'
#' @examples
#' \dontrun{
#' # Use full regulon names as output by SCENIC: "TF_NAME (n_targets)g"
#' plot_regulon_activity(seurat_obj, c("SOX10 (45g)", "MITF (32g)"))
#' }
plot_regulon_activity <- function(seurat_obj,
                                   regulons,
                                   reduction = "umap",
                                   assayName = "SCENIC") {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  library(Seurat)

  # Check assay
  if (!assayName %in% names(seurat_obj@assays)) {
    stop(sprintf("Assay '%s' not found", assayName))
  }

  DefaultAssay(seurat_obj) <- assayName

  # Check regulons exist
  available_regulons <- rownames(seurat_obj)
  missing_regulons <- setdiff(regulons, available_regulons)

  if (length(missing_regulons) > 0) {
    warning(sprintf("Regulons not found: %s", paste(missing_regulons, collapse = ", ")))
    regulons <- intersect(regulons, available_regulons)
  }

  if (length(regulons) == 0) {
    stop("No valid regulons to plot")
  }

  # Create plots
  plots <- Seurat::FeaturePlot(
    seurat_obj,
    features = regulons,
    reduction = reduction,
    ncol = min(3, length(regulons))
  )

  return(plots)
}


#' Find Cell-Type Specific Regulons
#'
#' Identify regulons that are specifically active in specific cell types.
#'
#' @param seurat_obj Seurat object with SCENIC assay
#' @param group_by Column defining cell types (default: "seurat_clusters")
#' @param min_auc Minimum AUC threshold (default: 0.05)
#' @param assayName SCENIC assay name (default: "SCENIC")
#'
#' @return List of specific regulons per cell type
#' @export
#'
#' @examples
#' \dontrun{
#' specific_regulons <- find_celltype_specific_regulons(seurat_obj, "cell_type")
#' }
find_celltype_specific_regulons <- function(seurat_obj,
                                             group_by = "seurat_clusters",
                                             min_auc = 0.05,
                                             assayName = "SCENIC") {
  if (!assayName %in% names(seurat_obj@assays)) {
    stop(sprintf("Assay '%s' not found", assayName))
  }

  # Get AUC data
  DefaultAssay(seurat_obj) <- assayName
  # Handle both Seurat v4 and v5
  # SCENIC assay is created with CreateAssayObject(data = auc_matrix), so data layer/slot holds AUC values
  if (packageVersion("SeuratObject") >= "5.0.0") {
    auc_data <- GetAssayData(seurat_obj, layer = "data")
  } else {
    auc_data <- GetAssayData(seurat_obj, slot = "data")
  }

  groups <- unique(seurat_obj@meta.data[[group_by]])

  specific_regulons <- list()

  for (group in groups) {
    # Get cells
    cells_in <- colnames(seurat_obj)[seurat_obj@meta.data[[group_by]] == group]
    cells_out <- setdiff(colnames(seurat_obj), cells_in)

    # Calculate mean AUC
    mean_in <- rowMeans(auc_data[, cells_in, drop = FALSE])
    mean_out <- rowMeans(auc_data[, cells_out, drop = FALSE])

    # Calculate specificity score
    specificity <- mean_in / (mean_out + 0.01)  # Add small value to avoid division by zero

    # Filter regulons
    specific <- names(specificity)[mean_in > min_auc & specificity > 2]

    specific_regulons[[as.character(group)]] <- specific
  }

  return(specific_regulons)
}


# ============================================================================
# Database Management
# ============================================================================

# cisTarget database configuration
CISTARGET_DB_CONFIG <- list(
  hgnc = list(
    name = "human",
    base_url = "https://resources.aertslab.org/cistarget/databases/homo_sapiens/hg38/refseq_r80/",
    rankings = list(
      "500bp" = "hg38__refseq-r80__500bp_up_and_100bp_down_tss.genes_vs_motifs.rankings.feather",
      "10kb" = "hg38__refseq-r80__10kb_up_and_down_tss.genes_vs_motifs.rankings.feather"
    ),
    motif_annotations = list(
      "v9" = "https://resources.aertslab.org/cistarget/motif2tf/motifs-v9-nr.hgnc-m0.001-o0.0.tbl",
      "v10" = "https://resources.aertslab.org/cistarget/motif2tf/motifs-v10nr_clust-nr.hgnc-m0.001-o0.0.tbl"
    ),
    tf_list = "https://resources.aertslab.org/cistarget/tf_lists/allTFs_hg38.txt"
  ),
  mmusculus = list(
    name = "mouse",
    base_url = "https://resources.aertslab.org/cistarget/databases/mus_musculus/mm10/",
    rankings = list(
      "500bp" = "mm10__refseq-r80__500bp_up_and_100bp_down_tss.genes_vs_motifs.rankings.feather",
      "10kb" = "mm10__refseq-r80__10kb_up_and_down_tss.genes_vs_motifs.rankings.feather"
    ),
    motif_annotations = list(
      "v9" = "https://resources.aertslab.org/cistarget/motif2tf/motifs-v9-nr.mgi-m0.001-o0.0.tbl",
      "v10" = "https://resources.aertslab.org/cistarget/motif2tf/motifs-v10nr_clust-nr.mgi-m0.001-o0.0.tbl"
    ),
    tf_list = "https://resources.aertslab.org/cistarget/tf_lists/allTFs_mm10.txt"
  ),
  dmel = list(
    name = "fly",
    base_url = "https://resources.aertslab.org/cistarget/databases/drosophila_melanogaster/dm6/",
    rankings = list(
      "500bp" = "dm6__refseq-r80__500bp_up_and_100bp_down_tss.genes_vs_motifs.rankings.feather",
      "10kb" = "dm6__refseq-r80__10kb_up_and_down_tss.genes_vs_motifs.rankings.feather"
    ),
    motif_annotations = list(
      "v9" = "https://resources.aertslab.org/cistarget/motif2tf/motifs-v9-nr.flybase-m0.001-o0.0.tbl"
    ),
    tf_list = "https://resources.aertslab.org/cistarget/tf_lists/allTFs_dmel.txt"
  )
)


#' Get Skill Root Directory
#'
#' Find the root directory of the bio-single-cell-regulatory-scenic-r skill.
#'
#' @return Path to skill root directory or NULL if not found
#' @keywords internal
#'
get_skill_root_dir <- function() {
  # Try multiple methods to find skill directory

  # Method 1: Check if running from within the skill directory structure
  tryCatch({
    # Get path of current script
    if (exists(".scenic_script_path", envir = .GlobalEnv)) {
      script_path <- get(".scenic_script_path", envir = .GlobalEnv)
    } else {
      # Try to determine from source info
      script_path <- sys.frame(1)$ofile
      if (is.null(script_path)) {
        script_path <- attr(sys.function(1), "srcref")
      }
    }

    if (!is.null(script_path)) {
      script_dir <- dirname(script_path)
      # scripts/r/ -> skill root
      if (basename(script_dir) == "r") {
        potential_root <- dirname(dirname(script_dir))
        if (file.exists(file.path(potential_root, "SKILL.md"))) {
          return(normalizePath(potential_root))
        }
      }
    }
  }, error = function(e) NULL)

  # Method 2: Check working directory
  wd <- getwd()
  if (file.exists(file.path(wd, "SKILL.md")) &&
      dir.exists(file.path(wd, "scripts", "r"))) {
    return(normalizePath(wd))
  }

  # Method 3: Check common parent directories
  tryCatch({
    current <- normalizePath(getwd())
    for (i in 1:5) {  # Check up to 5 levels up
      parent <- dirname(current)
      if (parent == current) break
      current <- parent

      if (file.exists(file.path(current, "SKILL.md")) &&
          dir.exists(file.path(current, "scripts", "r"))) {
        return(current)
      }
    }
  }, error = function(e) NULL)

  return(NULL)
}


#' Get cisTarget Database Directory
#'
#' Get or create the cisTarget database directory with hierarchical lookup.
#'
#' Lookup order:
#' 1. If prefer_skill_assets=TRUE: Check skill directory's assets/ folder first
#' 2. Fall back to specified dbDir (default: "~/cisTarget")
#'
#' The assets/ folder in the skill directory allows for project-specific
#' database storage without polluting the user's home directory.
#'
#' @param dbDir Directory path for fallback (default: "cisTarget" in home)
#' @param prefer_skill_assets If TRUE, prefer skill assets directory (default: TRUE)
#' @param create_if_missing Create directory if it doesn't exist (default: TRUE)
#'
#' @return Normalized path to database directory
#' @export
#'
#' @examples
#' \dontrun{
#' # Use hierarchical lookup (skill assets first, then home)
#' db_path <- get_cistarget_dir(prefer_skill_assets = TRUE)
#'
#' # Force use of home directory
#' db_path <- get_cistarget_dir("~/cisTarget", prefer_skill_assets = FALSE)
#' }
get_cistarget_dir <- function(dbDir = "cisTarget",
                              prefer_skill_assets = TRUE,
                              create_if_missing = TRUE) {
  # Try skill directory first if requested
  if (prefer_skill_assets) {
    skill_root <- get_skill_root_dir()
    if (!is.null(skill_root)) {
      skill_assets <- file.path(skill_root, "assets")

      # Create assets directory if needed
      if (create_if_missing && !dir.exists(skill_assets)) {
        dir.create(skill_assets, recursive = TRUE, showWarnings = FALSE)
        message(sprintf("Created skill assets directory: %s", skill_assets))
      }

      # Return skill assets path (it either exists or we just created it)
      if (dir.exists(skill_assets)) {
        message(sprintf("Using skill assets directory: %s", skill_assets))
        return(normalizePath(skill_assets))
      }
    }
  }

  # Fall back to specified dbDir
  dbDir <- path.expand(dbDir)

  if (create_if_missing && !dir.exists(dbDir)) {
    dir.create(dbDir, recursive = TRUE, showWarnings = FALSE)
    message(sprintf("Created cisTarget directory: %s", dbDir))
  }

  message(sprintf("Using fallback directory: %s", normalizePath(dbDir)))
  return(normalizePath(dbDir))
}


#' List cisTarget Cache Locations
#'
#' List all possible cache locations for cisTarget databases.
#'
#' @return List with 'skill_assets' and 'home_cache' paths
#' @export
#'
#' @examples
#' \dontrun{
#' locations <- list_cistarget_cache_locations()
#' print(locations$skill_assets)
#' print(locations$home_cache)
#' }
list_cistarget_cache_locations <- function() {
  locations <- list(
    home_cache = path.expand("~/cisTarget")
  )

  skill_root <- get_skill_root_dir()
  if (!is.null(skill_root)) {
    locations$skill_assets <- file.path(skill_root, "assets")
  } else {
    locations$skill_assets <- NULL
  }

  return(locations)
}


#' Migrate Databases to Skill Assets
#'
#' Migrate databases from home directory to skill assets/ directory.
#'
#' @param home_dir Source directory (default: "~/cisTarget")
#' @param dry_run If TRUE, only preview without moving (default: TRUE)
#'
#' @return List with migration results
#' @export
#'
#' @examples
#' \dontrun{
#' # Preview migration
#' result <- migrate_databases_to_skill_assets(dry_run = TRUE)
#'
#' # Actually migrate
#' result <- migrate_databases_to_skill_assets(dry_run = FALSE)
#' }
migrate_databases_to_skill_assets <- function(home_dir = "~/cisTarget",
                                               dry_run = TRUE) {
  home_dir <- path.expand(home_dir)
  skill_root <- get_skill_root_dir()

  if (is.null(skill_root)) {
    stop("Cannot determine skill root directory. Run from within the skill folder.")
  }

  skill_assets <- file.path(skill_root, "assets")

  result <- list(
    to_migrate = character(),
    already_present = character(),
    source_dir = home_dir,
    target_dir = skill_assets
  )

  if (!dir.exists(home_dir)) {
    message("No home cache directory found")
    return(result)
  }

  # Create skill assets if needed
  if (!dir.exists(skill_assets) && !dry_run) {
    dir.create(skill_assets, recursive = TRUE, showWarnings = FALSE)
  }

  # Check files
  files <- list.files(home_dir, full.names = FALSE)
  for (f in files) {
    home_file <- file.path(home_dir, f)
    skill_file <- file.path(skill_assets, f)

    if (file.exists(skill_file)) {
      result$already_present <- c(result$already_present, f)
    } else {
      result$to_migrate <- c(result$to_migrate, f)
    }
  }

  message(sprintf("Files to migrate: %d", length(result$to_migrate)))
  message(sprintf("Files already in skill assets: %d", length(result$already_present)))

  if (!dry_run && length(result$to_migrate) > 0) {
    for (f in result$to_migrate) {
      src <- file.path(home_dir, f)
      dst <- file.path(skill_assets, f)
      message(sprintf("Copying %s...", f))
      file.copy(src, dst, overwrite = FALSE)
    }
    message("Migration complete!")
  }

  return(result)
}


#' Check cisTarget Databases
#'
#' Check if required cisTarget databases are available.
#'
#' @param org Organism: "hgnc" (human), "mmusculus" (mouse), or "dmel" (fly)
#' @param dbDir Directory for cisTarget databases (default: "cisTarget")
#' @param db_types Vector of database types to check: "500bp", "10kb", or both
#' @param motif_version Motif annotation version: "v9" or "v10"
#'
#' @return List with database availability status
#' @export
#'
#' @examples
#' \dontrun{
#' status <- check_cistarget_databases("hgnc", dbDir = "cisTarget")
#' print(status$all_ready)
#' }
check_cistarget_databases <- function(org = c("hgnc", "mmusculus", "dmel"),
                                       dbDir = "cisTarget",
                                       db_types = c("500bp", "10kb"),
                                       motif_version = "v10",
                                       prefer_skill_assets = TRUE) {
  org <- match.arg(org)
  dbDir <- get_cistarget_dir(dbDir, prefer_skill_assets = prefer_skill_assets)

  config <- CISTARGET_DB_CONFIG[[org]]
  if (is.null(config)) {
    stop(sprintf("Unknown organism: %s", org))
  }

  results <- list(
    org = org,
    dbDir = dbDir,
    rankings = list(),
    motif_annotation = FALSE,
    tf_list = FALSE,
    all_ready = TRUE
  )

  # Check ranking databases
  for (db_type in db_types) {
    db_file <- config$rankings[[db_type]]
    if (!is.null(db_file)) {
      db_path <- file.path(dbDir, db_file)
      exists <- file.exists(db_path)
      size_mb <- if (exists) round(file.size(db_path) / 1024 / 1024, 1) else 0

      results$rankings[[db_type]] <- list(
        file = db_file,
        path = db_path,
        exists = exists,
        size_mb = size_mb
      )

      if (!exists) {
        results$all_ready <- FALSE
      }
    }
  }

  # Check motif annotation
  motif_url <- config$motif_annotations[[motif_version]]
  if (!is.null(motif_url)) {
    motif_file <- basename(motif_url)
    motif_path <- file.path(dbDir, motif_file)
    results$motif_annotation <- file.exists(motif_path)
    results$motif_file <- motif_file
    results$motif_path <- motif_path

    if (!results$motif_annotation) {
      results$all_ready <- FALSE
    }
  } else {
    results$all_ready <- FALSE
  }

  # Check TF list
  tf_file <- basename(config$tf_list)
  tf_path <- file.path(dbDir, tf_file)
  results$tf_list <- file.exists(tf_path)
  results$tf_file <- tf_file
  results$tf_path <- tf_path

  if (!results$tf_list) {
    results$all_ready <- FALSE
  }

  return(results)
}


#' Download File with Progress
#'
#' Download a file from URL with progress reporting.
#'
#' @param url URL to download from
#' @param dest_path Destination file path
#' @param timeout Download timeout in seconds (default: 600)
#'
#' @return Invisible NULL
#' @keywords internal
#'
#' @examples
#' \dontrun{
#' download_with_progress(url, dest_file)
#' }
download_with_progress <- function(url, dest_path, timeout = 600) {
  message(sprintf("Downloading: %s", basename(url)))
  message(sprintf("Destination: %s", dest_path))
  message("This may take several minutes for large files (~1GB)...")

  # Set timeout
  old_timeout <- getOption("timeout")
  options(timeout = timeout)
  on.exit(options(timeout = old_timeout))

  # Download
  tryCatch({
    download.file(url, dest_path, mode = "wb", quiet = FALSE)

    # Verify download
    if (!file.exists(dest_path)) {
      stop("Download failed: file not created")
    }

    size_mb <- round(file.size(dest_path) / 1024 / 1024, 1)
    message(sprintf("Download complete: %.1f MB", size_mb))

  }, error = function(e) {
    # Clean up partial download
    if (file.exists(dest_path)) {
      file.remove(dest_path)
    }
    stop(sprintf("Download failed: %s", e$message))
  })

  invisible(NULL)
}


#' Download cisTarget Databases
#'
#' Download cisTarget databases for SCENIC analysis.
#'
#' @param org Organism: "hgnc" (human), "mmusculus" (mouse), or "dmel" (fly)
#' @param dbDir Directory to save databases (default: "cisTarget")
#' @param db_types Database types to download: "500bp", "10kb", or both (default: c("500bp", "10kb"))
#' @param motif_version Motif annotation version: "v9" or "v10" (default: "v10")
#' @param force Force re-download even if files exist (default: FALSE)
#' @param timeout Download timeout in seconds (default: 600)
#'
#' @return List with paths to downloaded files
#' @export
#'
#' @examples
#' \dontrun{
#' # Download all databases for human
#' db_paths <- download_cistarget_databases("hgnc", dbDir = "cisTarget")
#'
#' # Download only 10kb database
#' db_paths <- download_cistarget_databases("hgnc", db_types = "10kb")
#'
#' # Force re-download
#' db_paths <- download_cistarget_databases("hgnc", force = TRUE)
#' }
download_cistarget_databases <- function(org = c("hgnc", "mmusculus", "dmel"),
                                          dbDir = "cisTarget",
                                          db_types = c("500bp", "10kb"),
                                          motif_version = "v10",
                                          force = FALSE,
                                          timeout = 600,
                                          prefer_skill_assets = TRUE) {
  org <- match.arg(org)
  dbDir <- get_cistarget_dir(dbDir, prefer_skill_assets = prefer_skill_assets)

  config <- CISTARGET_DB_CONFIG[[org]]
  if (is.null(config)) {
    stop(sprintf("Unknown organism: %s", org))
  }

  message(paste(rep("=", 60), collapse = ""))
  message(sprintf("Downloading cisTarget databases for %s", config$name))
  message(paste(rep("=", 60), collapse = ""))
  message(sprintf("Destination: %s", dbDir))
  message("")

  results <- list(
    org = org,
    dbDir = dbDir,
    rankings = list(),
    motif_annotation = NULL,
    tf_list = NULL
  )

  # Download ranking databases
  for (db_type in db_types) {
    db_file <- config$rankings[[db_type]]
    if (is.null(db_file)) {
      warning(sprintf("Database type '%s' not available for %s", db_type, org))
      next
    }

    db_path <- file.path(dbDir, db_file)
    db_url <- paste0(config$base_url, db_file)

    if (file.exists(db_path) && !force) {
      size_mb <- round(file.size(db_path) / 1024 / 1024, 1)
      message(sprintf("[%s] Already exists (%.1f MB): %s", db_type, size_mb, db_file))
    } else {
      if (file.exists(db_path) && force) {
        message(sprintf("[%s] Forcing re-download...", db_type))
      }
      download_with_progress(db_url, db_path, timeout)
    }

    results$rankings[[db_type]] <- db_path
  }

  message("")

  # Download motif annotation
  motif_url <- config$motif_annotations[[motif_version]]
  if (!is.null(motif_url)) {
    motif_file <- basename(motif_url)
    motif_path <- file.path(dbDir, motif_file)

    if (file.exists(motif_path) && !force) {
      message(sprintf("[motifs] Already exists: %s", motif_file))
    } else {
      download_with_progress(motif_url, motif_path, timeout)
    }

    results$motif_annotation <- motif_path
  }

  message("")

  # Download TF list
  tf_file <- basename(config$tf_list)
  tf_path <- file.path(dbDir, tf_file)

  if (file.exists(tf_path) && !force) {
    message(sprintf("[TF list] Already exists: %s", tf_file))
  } else {
    download_with_progress(config$tf_list, tf_path, timeout)
  }

  results$tf_list <- tf_path

  message("")
  message(paste(rep("=", 60), collapse = ""))
  message("Download complete!")
  message(paste(rep("=", 60), collapse = ""))

  return(results)
}


#' List Available cisTarget Databases
#'
#' List all available cisTarget databases and their local status.
#'
#' @param dbDir Directory for cisTarget databases (default: "cisTarget")
#'
#' @return Data frame with database availability status
#' @export
#'
#' @examples
#' \dontrun{
#' db_status <- list_cistarget_databases("cisTarget")
#' print(db_status)
#' }
list_cistarget_databases <- function(dbDir = "cisTarget", prefer_skill_assets = TRUE) {
  records <- list()

  for (org in names(CISTARGET_DB_CONFIG)) {
    for (db_type in c("500bp", "10kb")) {
      status <- check_cistarget_databases(org, dbDir, db_type, prefer_skill_assets = prefer_skill_assets)

      records[[length(records) + 1]] <- list(
        organism = org,
        type = db_type,
        ranking_exists = status$rankings[[db_type]]$exists %||% FALSE,
        motif_exists = status$motif_annotation,
        tf_list_exists = status$tf_list,
        all_ready = status$all_ready
      )
    }
  }

  do.call(rbind, lapply(records, as.data.frame))
}


#' Initialize SCENIC with Database Auto-Download
#'
#' Enhanced initialization that checks and optionally downloads databases.
#'
#' @param org Organism: "hgnc" (human), "mmusculus" (mouse), or "dmel" (fly)
#' @param dbDir Directory for cisTarget databases (default: "cisTarget")
#' @param datasetTitle Dataset name
#' @param nCores Number of cores to use (default: 4)
#' @param db_types Database types to use: "500bp", "10kb", or both (default: "10kb")
#' @param motif_version Motif annotation version: "v9" or "v10" (default: "v10")
#' @param download_if_missing Download databases if not found (default: TRUE)
#' @param force_download Force re-download even if files exist (default: FALSE)
#'
#' @return SCENIC options list
#' @export
#'
#' @examples
#' \dontrun{
#' # Auto-download if missing
#' scenicOptions <- init_scenic_auto("hgnc", dbDir = "cisTarget")
#'
#' # Use 500bp database only
#' scenicOptions <- init_scenic_auto("hgnc", db_types = "500bp")
#'
#' # Skip download (fail if missing)
#' scenicOptions <- init_scenic_auto("hgnc", download_if_missing = FALSE)
#' }
init_scenic_auto <- function(org = c("hgnc", "mmusculus", "dmel"),
                              dbDir = "cisTarget",
                              datasetTitle = "SCENIC",
                              nCores = 4,
                              db_types = "10kb",
                              motif_version = "v10",
                              download_if_missing = TRUE,
                              force_download = FALSE,
                              prefer_skill_assets = TRUE) {
  org <- match.arg(org)

  message("Checking cisTarget databases...")

  # Get effective dbDir (might be skill assets)
  effective_dbDir <- get_cistarget_dir(dbDir, prefer_skill_assets = prefer_skill_assets)

  # Check database status
  status <- check_cistarget_databases(org, effective_dbDir, db_types, motif_version)

  if (!status$all_ready) {
    if (download_if_missing) {
      message("Some databases are missing. Downloading now...")
      download_cistarget_databases(org, effective_dbDir, db_types, motif_version,
                                   force = force_download)
    } else {
      stop("Databases not found. Set download_if_missing=TRUE to auto-download, or run download_cistarget_databases() first.")
    }
  } else if (force_download) {
    message("Force download requested. Re-downloading databases...")
    download_cistarget_databases(org, effective_dbDir, db_types, motif_version,
                                 force = TRUE)
  }

  # Now proceed with normal initialization (pass the effective path)
  init_scenic(org, effective_dbDir, datasetTitle, nCores)
}


# Helper for NULL default
default <- function(x, y) if (is.null(x)) y else x
`%||%` <- default
