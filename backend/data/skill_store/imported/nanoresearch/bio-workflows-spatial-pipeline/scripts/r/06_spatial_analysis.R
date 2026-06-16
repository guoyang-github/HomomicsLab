#' Step 6: Spatial Analysis — Spatial Transcriptomics Pipeline (R)
#'
#' Reference: Seurat 5.0+, SPARK-X (optional)
#'
#' Input State:  [Clustered] + [UMAP]
#' Output State: [Spatial-Analyzed]
#'
#' Computes:
#' - Spatially Variable Genes (SVGs) via FindSpatiallyVariableFeatures
#' - Neighborhood enrichment (cluster co-localization)

library(Seurat)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

propose_spatial_analysis <- function(obj) {
  #' Propose spatial analysis parameters.

  n_spots <- ncol(obj)

  # Detect platform from image names
  img_names <- names(obj@images)
  if (length(img_names) > 0 && any(grepl("^slice", img_names))) {
    platform_guess <- "Visium (regular grid)"
    neigh_method <- "grid"
    neigh_reason <- "Visium hexagonal spot array detected."
  } else if (length(img_names) > 0 && any(grepl("fov", img_names, ignore.case = TRUE))) {
    platform_guess <- "Xenium (dense irregular)"
    neigh_method <- "KNN"
    neigh_reason <- "Xenium FOV detected; dense irregular platform."
  } else {
    platform_guess <- "Unknown (no recognized image)"
    neigh_method <- "KNN"
    neigh_reason <- "No spatial images found. Falling back to KNN."
  }

  list(
    recommendation = list(
      neighbor_method = neigh_method,
      svg_method = "markvariogram",
      n_svg_test = 2000
    ),
    diagnostics = list(
      n_spots = n_spots,
      platform_guess = platform_guess,
      has_spatial_images = length(img_names) > 0
    ),
    justification = neigh_reason,
    alternatives = list(
      moransi = "Moran's I (moransi) — alternative spatial autocorrelation metric.",
      sparkx = "SPARK-X — model-based SVG detection, more sensitive but slower.",
      rank = "Rank-based test — fastest, less sensitive."
    )
  )
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_spatial_proposal <- function(proposal, obj) {
  #' Evaluate spatial analysis proposal before execution.
  #'
  #' Guardrails:
  #'   - No spatial images/coords → BLOCK
  #'   - n_spots < 100 → CAUTION (too few for reliable spatial stats)

  has_coords <- !is.null(obj@images) && length(obj@images) > 0
  has_spatial <- "spatial" %in% names(obj@reductions) ||
                 any(grepl("^spatial", names(obj@reductions), ignore.case = TRUE))

  if (!has_coords && !has_spatial) {
    return(list(
      verdict = "BLOCK",
      adjusted = FALSE,
      reason = "No spatial images or coordinates found. Cannot perform spatial analysis."
    ))
  }

  n_spots <- proposal$diagnostics$n_spots
  if (n_spots < 100) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Only %d spots. Spatial statistics may be unreliable.", n_spots)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

execute_spatial_analysis <- function(obj,
                                     svg_method = "markvariogram",
                                     n_svg_test = 2000,
                                     cluster_col = "seurat_clusters",
                                     ...) {
  #' Run spatial analysis: SVGs and neighborhood enrichment.
  #'
  #' @param obj Seurat object [Clustered]
  #' @param svg_method Method for SVG detection (markvariogram, moransi)
  #' @param n_svg_test Number of HVGs to test
  #' @param cluster_col Column with cluster labels
  #' @param ... Additional args
  #' @return Seurat object with spatial analysis results

  # Resolve cluster column dynamically if default doesn't exist
  if (!(cluster_col %in% colnames(obj@meta.data))) {
    cluster_cols <- grep("snn_res\\.", colnames(obj@meta.data), value = TRUE)
    if (length(cluster_cols) > 0) {
      cluster_col <- cluster_cols[1]
    } else {
      warning("No cluster column found. Spatial analysis may be limited.")
      cluster_col <- NULL
    }
  }

  if (length(obj@images) == 0) {
    warning("No spatial images found. Spatial analysis may be limited.")
  }

  # SVG detection using Seurat's built-in method
  hvg <- VariableFeatures(obj)
  if (length(hvg) == 0) {
    warning("No HVGs found. Running FindVariableFeatures first.")
    obj <- FindVariableFeatures(obj, verbose = FALSE)
    hvg <- VariableFeatures(obj)
  }

  genes_to_test <- head(hvg, min(n_svg_test, length(hvg)))

  if (length(obj@images) > 0) {
    tryCatch({
      obj <- FindSpatiallyVariableFeatures(
        obj,
        features = genes_to_test,
        selection.method = svg_method,
        ...
      )
      message(sprintf("SVG detection complete (%s on %d genes)", svg_method, length(genes_to_test)))
    }, error = function(e) {
      message(sprintf("SVG detection skipped: %s", conditionMessage(e)))
    })
  }

  # Neighborhood enrichment: use SPARK-X or manual cluster co-localization
  # Seurat doesn't have built-in nhood enrichment; we compute a simple version
  if (cluster_col %in% colnames(obj@meta.data)) {
    tryCatch({
      nhood_result <- .compute_nhood_enrichment(obj, cluster_col = cluster_col)
      obj@misc$nhood_enrichment <- nhood_result
      message("Neighborhood enrichment computed.")
    }, error = function(e) {
      message(sprintf("Neighborhood enrichment skipped: %s", conditionMessage(e)))
    })
  }

  obj@misc$pipeline_state <- "Spatial-Analyzed"
  obj@misc$spatial_svg_method <- svg_method

  return(obj)
}


.compute_nhood_enrichment <- function(obj, cluster_col = "seurat_clusters", k = 6) {
  #' Simple neighborhood enrichment: compute cluster co-occurrence
  #' in transcriptomic KNN graph.

  assay <- DefaultAssay(obj)
  snn_name <- sprintf("%s_snn", assay)
  if (!(snn_name %in% names(obj@graphs))) {
    warning(sprintf("No SNN graph '%s' found. Skipping neighborhood enrichment.", snn_name))
    return(NULL)
  }

  snn <- as.matrix(obj@graphs[[snn_name]])
  clusters <- obj@meta.data[[cluster_col]]
  cluster_levels <- sort(unique(clusters))
  n_clust <- length(cluster_levels)

  # Count edges between clusters
  enrichment <- matrix(0, nrow = n_clust, ncol = n_clust)
  rownames(enrichment) <- cluster_levels
  colnames(enrichment) <- cluster_levels

  for (i in seq_along(cluster_levels)) {
    for (j in seq_along(cluster_levels)) {
      cells_i <- which(clusters == cluster_levels[i])
      cells_j <- which(clusters == cluster_levels[j])
      enrichment[i, j] <- mean(snn[cells_i, cells_j] > 0)
    }
  }

  list(
    enrichment_matrix = enrichment,
    cluster_levels = cluster_levels
  )
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_spatial_analysis <- function(obj, proposal) {
  #' Report spatial analysis results.

  # SVG results from assay meta.features (FindSpatiallyVariableFeatures stores here)
  assay <- DefaultAssay(obj)
  meta_features <- obj@assays[[assay]]@meta.features
  if ("spatially_variable" %in% colnames(meta_features)) {
    svg_mask <- meta_features$spatially_variable == TRUE
    n_svgs <- sum(svg_mask, na.rm = TRUE)
    top_gene <- if (n_svgs > 0) {
      svg_genes <- rownames(meta_features)[svg_mask]
      svg_genes[1]
    } else {
      "N/A"
    }
  } else {
    n_svgs <- 0
    top_gene <- "N/A"
  }

  has_nhood <- !is.null(obj@misc$nhood_enrichment)

  status <- if (n_svgs >= 10) "PASS" else "CAUTION"

  list(
    step = "Spatial Analysis",
    status = status,
    n_svgs = n_svgs,
    top_svg = top_gene,
    nhood_enrichment = has_nhood,
    svg_method = obj@misc$spatial_svg_method %||% "N/A",
    recommendation = if (status == "PASS") {
      sprintf("%d spatially variable genes detected.", n_svgs)
    } else {
      "Few significant SVGs. Check tissue quality or platform settings."
    },
    next_step = "Step 7: Domain Detection"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_spatial_analysis_step <- function(obj,
                                      svg_method = NULL,
                                      n_svg_test = NULL,
                                      auto = FALSE,
                                      use_llm = TRUE,
                                      prev_reports = list(),
                                      ...) {
  #' Complete spatial analysis step.

  # State validation
  expected_states <- c("Clustered")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for spatial analysis step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_spatial_analysis(obj)

  # Evaluate phase: guardrail on spatial data availability
  evaluation <- evaluate_spatial_proposal(proposal, obj)
  if (evaluation$verdict == "BLOCK") {
    stop(evaluation$reason)
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(svg_method)) svg_method <- proposal$recommendation$svg_method
  if (is.null(n_svg_test)) n_svg_test <- proposal$recommendation$n_svg_test

  if (!auto) {
    message("\n=== Spatial Analysis Proposal ===")
    message(sprintf("Platform guess: %s", proposal$diagnostics$platform_guess))
    message(sprintf("SVG method: %s", svg_method))
    message(sprintf("SVG test genes: %d", n_svg_test))
    message(sprintf("Justification: %s", proposal$justification))
  }

  obj <- execute_spatial_analysis(
    obj,
    svg_method = svg_method,
    n_svg_test = n_svg_test,
    ...
  )
  report <- report_spatial_analysis(obj, proposal)

  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("spatial", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
