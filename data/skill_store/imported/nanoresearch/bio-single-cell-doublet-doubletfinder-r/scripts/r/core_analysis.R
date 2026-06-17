# Core Analysis Functions for DoubletFinder
# ==========================================
#
# This script provides wrapper functions for DoubletFinder doublet detection
# in single-cell RNA sequencing data.

#' Check if Seurat object is properly preprocessed for DoubletFinder
#'
#' @param seu Seurat object
#' @return Logical indicating whether object is ready
#' @export
check_seurat_for_df <- function(seu) {
  if (!inherits(seu, "Seurat")) {
    stop("Input must be a Seurat object")
  }

  # Check for required reductions and commands
  if (length(seu@commands) == 0) {
    stop("Seurat object has no processing history. Run NormalizeData, FindVariableFeatures, ScaleData, and RunPCA first.")
  }

  if (!"pca" %in% names(seu@reductions)) {
    stop("PCA not found. Run RunPCA() before DoubletFinder.")
  }

  # Check normalization
  if (!"NormalizeData.RNA" %in% names(seu@commands)) {
    warning("NormalizeData not found in command history. Ensure data is normalized.")
  }

  message("Seurat object check passed")
  message("  Cells: ", ncol(seu))
  message("  Genes: ", nrow(seu))
  message("  PCA dimensions: ", ncol(seu@reductions$pca@cell.embeddings))

  return(TRUE)
}

#' Estimate expected number of doublets based on cell loading
#'
#' @param n_cells Number of cells loaded
#' @param method Estimation method: "10x" (default) or "poisson"
#' @return Expected number of doublets
#' @export
estimate_doublet_rate <- function(n_cells, method = "10x") {
  if (method == "10x") {
    # 10x Genomics doublet rate: rate scales with loading density.
    # Approximate formula: rate = (n_cells / 1000) * 0.008, then nExp = rate * n_cells.
    # This gives nExp proportional to n_cells^2 (Poisson loading model).
    rate <- n_cells / 1000 * 0.008
  } else if (method == "poisson") {
    # Poisson-based estimate (conservative)
    rate <- 0.075
  } else {
    stop("Unknown method. Use '10x' or 'poisson'.")
  }

  n_exp <- round(rate * n_cells)

  message("Estimated doublet rate: ", round(rate * 100, 2), "%")
  message("Expected doublets: ", n_exp, " out of ", n_cells, " cells")

  return(n_exp)
}

#' Run parameter sweep to find optimal pK
#'
#' @param seu Pre-processed Seurat object
#' @param PCs Principal components to use (e.g., 1:20)
#' @param sct Whether SCTransform was used (default: FALSE)
#' @param num.cores Number of cores for parallelization (default: 1)
#' @param subsample Subsample to 10000 cells for speed (default: TRUE)
#' @return List containing sweep results and statistics
#' @export
run_param_sweep <- function(
    seu,
    PCs = 1:20,
    sct = FALSE,
    num.cores = 1,
    subsample = TRUE
) {
  if (!requireNamespace("DoubletFinder", quietly = TRUE)) {
    stop("DoubletFinder not installed. Run: remotes::install_github('chris-mcginnis-ucsf/DoubletFinder')")
  }

  check_seurat_for_df(seu)

  message("Running parameter sweep...")
  message("  PCs: ", paste(range(PCs), collapse = "-"))
  message("  SCTransform: ", sct)
  message("  Cores: ", num.cores)

  # Subsample for speed if requested and dataset is large
  if (subsample && ncol(seu) > 10000) {
    message("  Subsampling to 10000 cells for parameter sweep...")
    set.seed(42)
    cells_keep <- sample(colnames(seu), 10000)
    seu_sweep <- subset(seu, cells = cells_keep)
  } else {
    seu_sweep <- seu
  }

  # Parameter sweep
  sweep.res <- DoubletFinder::paramSweep(
    seu_sweep,
    PCs = PCs,
    sct = sct,
    num.cores = num.cores
  )

  message("Summarizing sweep results...")

  # Summarize results
  sweep.stats <- DoubletFinder::summarizeSweep(
    sweep.res,
    GT = FALSE
  )

  # Find optimal pK
  bcmvn <- DoubletFinder::find.pK(sweep.stats)

  # Get optimal pK
  optimal_pk <- as.numeric(as.character(
    bcmvn$pK[which.max(bcmvn$BCmetric)]
  ))

  message("Optimal pK identified: ", optimal_pk)

  return(list(
    sweep.res = sweep.res,
    sweep.stats = sweep.stats,
    bcmvn = bcmvn,
    optimal_pk = optimal_pk
  ))
}

#' Run DoubletFinder doublet detection
#'
#' @param seu Pre-processed Seurat object
#' @param PCs Principal components to use
#' @param pN Proportion of artificial doublets (default: 0.25)
#' @param pK PC neighborhood size (if NULL, will run parameter sweep)
#' @param nExp Expected number of doublets (if NULL, will estimate)
#' @param reuse.pANN Column name to reuse pANN (default: NULL)
#' @param sct Whether SCTransform was used (default: FALSE)
#' @return Seurat object with doublet predictions
#' @export
run_doubletfinder <- function(
    seu,
    PCs = 1:20,
    pN = 0.25,
    pK = NULL,
    nExp = NULL,
    reuse.pANN = NULL,
    sct = FALSE
) {
  if (!requireNamespace("DoubletFinder", quietly = TRUE)) {
    stop("DoubletFinder not installed")
  }

  check_seurat_for_df(seu)

  # Determine pK if not provided
  if (is.null(pK)) {
    message("pK not provided, running parameter sweep...")
    sweep_results <- run_param_sweep(seu, PCs = PCs, sct = sct)
    pK <- sweep_results$optimal_pk
  }

  # Estimate nExp if not provided
  if (is.null(nExp)) {
    nExp <- estimate_doublet_rate(ncol(seu))
  }

  message("Running DoubletFinder...")
  message("  pN: ", pN)
  message("  pK: ", pK)
  message("  nExp: ", nExp)

  # Run DoubletFinder
  seu <- DoubletFinder::doubletFinder(
    seu,
    PCs = PCs,
    pN = pN,
    pK = pK,
    nExp = nExp,
    reuse.pANN = reuse.pANN,
    sct = sct
  )

  # Get classification column name (most recent run if multiple exist)
  df_col <- grep(
    "DF.classifications",
    colnames(seu@meta.data),
    value = TRUE
  )

  if (length(df_col) == 0) {
    stop("No DF.classifications column found after doubletFinder run")
  }

  # Use the last (most recent) classification column
  df_col_use <- tail(df_col, 1)

  # Add simplified doublet column
  seu$doublet <- seu@meta.data[[df_col_use]]

  # Count results
  n_doublets <- sum(seu$doublet == "Doublet")
  n_singlets <- sum(seu$doublet == "Singlet")

  message("Doublet detection complete")
  message("  Predicted doublets: ", n_doublets, " (", round(n_doublets/ncol(seu)*100, 1), "%)")
  message("  Predicted singlets: ", n_singlets)

  return(seu)
}

#' Run DoubletFinder with homotypic doublet adjustment
#'
#' @param seu Pre-processed Seurat object with clustering
#' @param PCs Principal components to use
#' @param cluster_col Metadata column with cluster annotations
#' @param pK PC neighborhood size (if NULL, will run parameter sweep)
#' @param sct Whether SCTransform was used (default: FALSE)
#' @return Seurat object with adjusted doublet predictions
#' @export
run_doubletfinder_adjusted <- function(
    seu,
    PCs = 1:20,
    cluster_col = "seurat_clusters",
    pK = NULL,
    sct = FALSE
) {
  if (!requireNamespace("DoubletFinder", quietly = TRUE)) {
    stop("DoubletFinder not installed")
  }

  # Check for clustering
  if (!cluster_col %in% colnames(seu@meta.data)) {
    stop("Cluster column '", cluster_col, "' not found in metadata")
  }

  annotations <- seu@meta.data[[cluster_col]]

  # Step 1: Run without adjustment to get pANN
  nExp_poi <- estimate_doublet_rate(ncol(seu))

  if (is.null(pK)) {
    sweep_results <- run_param_sweep(seu, PCs = PCs, sct = sct)
    pK <- sweep_results$optimal_pk
  }

  message("Running initial DoubletFinder (unadjusted)...")
  seu <- DoubletFinder::doubletFinder(
    seu,
    PCs = PCs,
    pN = 0.25,
    pK = pK,
    nExp = nExp_poi,
    reuse.pANN = NULL,
    sct = sct
  )

  # Get pANN column name
  pann_col <- grep("pANN", colnames(seu@meta.data), value = TRUE)[1]

  # Step 2: Model homotypic doublets
  message("Modeling homotypic doublets...")
  homotypic.prop <- DoubletFinder::modelHomotypic(annotations)
  nExp_poi.adj <- round(nExp_poi * (1 - homotypic.prop))

  message("  Homotypic proportion: ", round(homotypic.prop * 100, 1), "%")
  message("  Adjusted expected doublets: ", nExp_poi.adj)

  # Step 3: Run with adjusted nExp (reusing pANN)
  message("Running adjusted DoubletFinder...")
  seu <- DoubletFinder::doubletFinder(
    seu,
    PCs = PCs,
    pN = 0.25,
    pK = pK,
    nExp = nExp_poi.adj,
    reuse.pANN = pann_col,
    sct = sct
  )

  # Update doublet column to adjusted results
  df_col <- grep("DF.classifications", colnames(seu@meta.data), value = TRUE)
  seu$doublet_adjusted <- seu@meta.data[[tail(df_col, 1)]]
  seu$doublet <- seu$doublet_adjusted

  return(seu)
}

#' Filter doublets from Seurat object
#'
#' @param seu Seurat object with doublet predictions
#' @param classification_col Column with doublet classifications (default: "doublet")
#' @param keep Which cells to keep: "Singlet" (default) or "Doublet"
#' @return Filtered Seurat object
#' @export
filter_doublets <- function(
    seu,
    classification_col = "doublet",
    keep = "Singlet"
) {
  if (!classification_col %in% colnames(seu@meta.data)) {
    stop("Classification column '", classification_col, "' not found")
  }

  if (!requireNamespace("rlang", quietly = TRUE)) {
    stop("rlang package required for filter_doublets")
  }

  n_before <- ncol(seu)

  # Filter
  seu_filtered <- subset(seu, subset = !!rlang::sym(classification_col) == keep)

  n_after <- ncol(seu_filtered)
  n_removed <- n_before - n_after

  message("Filtered Seurat object")
  message("  Before: ", n_before, " cells")
  message("  After: ", n_after, " cells")
  message("  Removed: ", n_removed, " cells (", round(n_removed/n_before*100, 1), "%)")

  return(seu_filtered)
}

#' Complete DoubletFinder workflow
#'
#' @param seu Pre-processed Seurat object
#' @param PCs Principal components to use
#' @param sct Whether SCTransform was used
#' @param adjust_homotypic Whether to adjust for homotypic doublets
#' @param cluster_col Cluster column for homotypic adjustment
#' @param filter Whether to filter doublets (default: FALSE)
#' @return Seurat object with doublet predictions
#' @export
run_doubletfinder_workflow <- function(
    seu,
    PCs = 1:20,
    sct = FALSE,
    adjust_homotypic = FALSE,
    cluster_col = "seurat_clusters",
    filter = FALSE
) {
  message("=== DoubletFinder Workflow ===")
  message("")

  # Run parameter sweep
  message("[1/3] Parameter sweep for optimal pK...")
  sweep_results <- run_param_sweep(seu, PCs = PCs, sct = sct)

  # Run DoubletFinder
  message("")
  message("[2/3] Doublet detection...")

  if (adjust_homotypic) {
    seu <- run_doubletfinder_adjusted(
      seu,
      PCs = PCs,
      cluster_col = cluster_col,
      pK = sweep_results$optimal_pk,
      sct = sct
    )
  } else {
    seu <- run_doubletfinder(
      seu,
      PCs = PCs,
      pK = sweep_results$optimal_pk,
      sct = sct
    )
  }

  # Filter if requested
  if (filter) {
    message("")
    message("[3/3] Filtering doublets...")
    seu <- filter_doublets(seu)
  } else {
    message("")
    message("[3/3] Skipping filter (set filter=TRUE to remove doublets)")
  }

  message("")
  message("=== Workflow Complete ===")

  return(seu)
}

#' Get doublet prediction summary
#'
#' @param seu Seurat object with doublet predictions
#' @param group_by Grouping column (optional)
#' @return Data frame with summary statistics
#' @export
get_doublet_summary <- function(seu, group_by = NULL) {
  if (!"doublet" %in% colnames(seu@meta.data)) {
    stop("No doublet predictions found. Run run_doubletfinder() first.")
  }

  if (is.null(group_by)) {
    # Overall summary
    summary <- data.frame(
      total_cells = ncol(seu),
      n_doublets = sum(seu$doublet == "Doublet"),
      n_singlets = sum(seu$doublet == "Singlet"),
      doublet_rate = round(sum(seu$doublet == "Doublet") / ncol(seu) * 100, 2)
    )
  } else {
    # Summary by group
    if (!group_by %in% colnames(seu@meta.data)) {
      stop("Grouping column '", group_by, "' not found")
    }

    groups <- unique(seu@meta.data[[group_by]])
    summary <- lapply(groups, function(g) {
      cells <- seu@meta.data[[group_by]] == g
      data.frame(
        group = g,
        total_cells = sum(cells),
        n_doublets = sum(seu$doublet[cells] == "Doublet"),
        n_singlets = sum(seu$doublet[cells] == "Singlet"),
        doublet_rate = round(sum(seu$doublet[cells] == "Doublet") / sum(cells) * 100, 2)
      )
    })
    summary <- do.call(rbind, summary)
  }

  return(summary)
}

#' Export doublet predictions
#'
#' @param seu Seurat object with doublet predictions
#' @param output_file Output CSV file path
#' @param include_pANN Whether to include pANN scores
#' @return Invisible NULL
#' @export
export_doublet_predictions <- function(
    seu,
    output_file = "doublet_predictions.csv",
    include_pANN = TRUE
) {
  # Get doublet column
  df_col <- grep("DF.classifications", colnames(seu@meta.data), value = TRUE)

  # Prepare export data
  export <- data.frame(
    cell_id = colnames(seu),
    doublet = seu$doublet
  )

  # Add pANN if requested
  if (include_pANN) {
    pann_col <- grep("pANN", colnames(seu@meta.data), value = TRUE)
    if (length(pann_col) > 0) {
      export$pANN <- seu@meta.data[[pann_col[1]]]
    }
  }

  # Write to file
  write.csv(export, output_file, row.names = FALSE)
  message("Exported doublet predictions to ", output_file)

  return(invisible(NULL))
}
