#' Step 6: Dimensionality Reduction + Clustering — Single-Cell RNA-seq Pipeline (R)
#'
#' Reference: Seurat 5.0+
#'
#' Input State:  [Normalized] or [Integrated]
#' Output State: [Clustered] + [UMAP]

library(Seurat)


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend PCs and resolution
# ---------------------------------------------------------------------------

propose_clustering_params <- function(obj) {
  #' Propose PCA dimensions and clustering resolutions.
  #'
  #' @param obj Seurat object [Normalized/Integrated]
  #' @return Recommendation list

  n_cells <- ncol(obj)
  n_pcs <- 50

  # Elbow-based PC selection (simplified)
  if ("pca" %in% names(obj@reductions)) {
    stdev <- obj@reductions$pca@stdev
    # Find elbow: point where marginal gain drops below 5% of first PC
    threshold <- stdev[1] * 0.05
    eligible <- which(stdev < threshold)
    if (length(eligible) == 0) {
      elbow_pc <- length(stdev)
    } else {
      elbow_pc <- min(eligible)
    }
    n_pcs_use <- min(elbow_pc, 50)
  } else {
    n_pcs_use <- 30
  }

  # Resolution recommendation based on cell count
  if (n_cells < 3000) {
    resolutions <- c(0.3, 0.5, 0.8)
    default_res <- 0.5
    res_reason <- "Small dataset (<3k cells). Lower resolutions to avoid over-clustering."
  } else if (n_cells < 20000) {
    resolutions <- c(0.3, 0.5, 0.8, 1.2)
    default_res <- 0.8
    res_reason <- "Medium dataset. Standard resolution range."
  } else {
    resolutions <- c(0.3, 0.5, 0.8, 1.2, 1.6)
    default_res <- 1.2
    res_reason <- "Large dataset (>20k cells). Higher resolutions may reveal subtypes."
  }

  list(
    recommendation = list(
      npcs = n_pcs,
      npcs_use = n_pcs_use,
      resolutions = resolutions,
      default_resolution = default_res,
      reduction = obj@misc$integration_reduction %||% "pca"
    ),
    diagnostics = list(
      n_cells = n_cells,
      n_genes = nrow(obj)
    ),
    justification = res_reason,
    alternatives = list(
      lower_res = "Use 0.2-0.4 for broad cell-type-level clustering.",
      higher_res = "Use 1.5-2.0 for subtype discovery."
    )
  )
}


# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_clustering_proposal <- function(proposal, obj) {
  #' Evaluate clustering proposal before execution.
  #'
  #' Guardrails:
  #'   - Any resolution outside [0.1, 2.0] → BLOCK + clamp
  #'   - n_pcs_use < 5 → CAUTION (too few PCs)

  resolutions <- proposal$recommendation$resolutions

  clamped <- resolutions
  clamped[clamped < 0.1] <- 0.1
  clamped[clamped > 2.0] <- 2.0

  if (any(clamped != resolutions)) {
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf(
        "Resolutions %s outside valid range [0.1, 2.0]. Clamped to %s.",
        paste(resolutions[resolutions != clamped], collapse = ", "),
        paste(unique(clamped), collapse = ", ")
      ),
      adjusted_params = list(resolutions = unique(clamped))
    ))
  }

  npcs_use <- proposal$recommendation$npcs_use
  if (!is.null(npcs_use) && npcs_use < 5) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Only %d PCs recommended (<5). Clustering may be unreliable.", npcs_use)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — PCA, UMAP, multi-resolution clustering
# ---------------------------------------------------------------------------

execute_clustering <- function(obj, npcs = 50, resolutions = c(0.3, 0.5, 0.8),
                                default_res = NULL, reduction = "pca", ...) {
  #' Run full clustering workflow.
  #'
  #' @param obj Seurat object
  #' @param npcs Number of PCs to compute
  #' @param resolutions Vector of clustering resolutions
  #' @param default_res Default resolution to set as active identity
  #' @param reduction Reduction to use ("pca" or "harmony")
  #' @param ... Additional args
  #' @return Seurat object with PCA, UMAP, and multiple cluster resolutions

  # PCA (if not already done)
  if (!("pca" %in% names(obj@reductions))) {
    obj <- RunPCA(obj, features = VariableFeatures(obj), npcs = npcs, verbose = FALSE)
  }

  # Determine dims to use (elbow-based)
  stdev <- obj@reductions$pca@stdev
  threshold <- stdev[1] * 0.05
  eligible <- which(stdev < threshold)
  if (length(eligible) == 0) {
    dims_use <- 1:min(length(stdev), 50)
  } else {
    dims_use <- 1:min(min(eligible), 50)
  }
  if (length(dims_use) < 10) dims_use <- 1:min(20, length(stdev))

  # Neighbors + UMAP
  obj <- FindNeighbors(obj, reduction = reduction, dims = dims_use, verbose = FALSE)
  obj <- RunUMAP(obj, reduction = reduction, dims = dims_use, verbose = FALSE)

  # Multi-resolution clustering (Seurat v5 safe: loop)
  for (res in resolutions) {
    obj <- FindClusters(obj, resolution = res, verbose = FALSE)
  }

  # Restore active identity to default resolution
  if (!is.null(default_res)) {
    res_col <- grep(paste0(DefaultAssay(obj), "_snn_res.", default_res),
                    colnames(obj@meta.data), value = TRUE, fixed = TRUE)[1]
    if (!is.na(res_col)) {
      Idents(obj) <- res_col
    }
  }

  obj@misc$pipeline_state <- "Clustered"
  obj@misc$clustering_resolutions <- resolutions
  obj@misc$clustering_dims <- dims_use
  obj@misc$clustering_reduction <- reduction

  message(sprintf("Clustering complete. PCs used: %d, Resolutions: %s",
                  length(dims_use), paste(resolutions, collapse = ", ")))

  return(obj)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_clustering <- function(obj, proposal) {
  #' Report clustering results.
  #'
  #' @param obj Seurat object [Clustered]
  #' @param proposal Proposal list
  #' @return Report list

  resolutions <- proposal$recommendation$resolutions
  res_cols <- grep("snn_res\\.", colnames(obj@meta.data), value = TRUE)

  cluster_counts <- sapply(res_cols, function(col) {
    length(unique(obj@meta.data[[col]]))
  })

  default_res <- proposal$recommendation$default_resolution
  default_col <- grep(paste0(DefaultAssay(obj), "_snn_res.", default_res),
                      colnames(obj@meta.data), value = TRUE, fixed = TRUE)[1]

  if (is.na(default_col)) {
    default_col <- res_cols[min(2, length(res_cols))]
  }

  n_clusters <- length(unique(obj@meta.data[[default_col]]))

  status <- if (n_clusters < 5) {
    "CAUTION"
  } else if (n_clusters > 50) {
    "CAUTION"
  } else {
    "PASS"
  }

  list(
    step = "Clustering",
    status = status,
    n_clusters = n_clusters,
    default_resolution = default_res,
    default_column = default_col,
    all_resolutions = setNames(cluster_counts, res_cols),
    recommendation = if (status == "CAUTION" && n_clusters < 5) {
      "Too few clusters. Consider higher resolution or check HVG count."
    } else if (status == "CAUTION" && n_clusters > 50) {
      "Many clusters. May indicate over-clustering; try lower resolution for broad types."
    } else {
      sprintf("Clustering looks reasonable (%d clusters at res=%.1f). Proceed to marker detection.",
              n_clusters, default_res)
    },
    next_step = "Step 7: Marker Detection"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_clustering_step <- function(obj, npcs = NULL, resolutions = NULL,
                                 reduction = NULL, auto = FALSE, use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete clustering step.
  #'
  #' @param obj Seurat object [Normalized/Integrated]
  #' @param npcs Number of PCs (NULL = auto)
  #' @param resolutions Clustering resolutions (NULL = auto)
  #' @param reduction Reduction name (NULL = auto)
  #' @param auto Skip proposal display
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @param ... Passed to execute_clustering
  #' @return List(obj, report, proposal, llm_report)

  # State validation
  expected_states <- c("Normalized", "Integrated")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for clustering step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_clustering_params(obj)

  # Evaluate phase: guardrail on resolution bounds
  evaluation <- evaluate_clustering_proposal(proposal, obj)
  if (evaluation$adjusted) {
    message("GUARDRAIL: ", evaluation$reason)
    proposal$recommendation$resolutions <- evaluation$adjusted_params$resolutions
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(npcs)) npcs <- proposal$recommendation$npcs
  if (is.null(resolutions)) resolutions <- proposal$recommendation$resolutions
  if (is.null(reduction)) reduction <- proposal$recommendation$reduction

  if (!auto) {
    message("\n=== Clustering Proposal ===")
    message(sprintf("PCs to compute: %d", npcs))
    message(sprintf("PCs to use (estimated): %d", proposal$recommendation$npcs_use))
    message(sprintf("Resolutions: %s", paste(resolutions, collapse = ", ")))
    message(sprintf("Default resolution: %.1f", proposal$recommendation$default_resolution))
    message(sprintf("Reduction: %s", reduction))
    message(sprintf("Justification: %s", proposal$justification))
  }

  obj <- execute_clustering(obj, npcs = npcs, resolutions = resolutions,
                            default_res = proposal$recommendation$default_resolution,
                            reduction = reduction, ...)
  report <- report_clustering(obj, proposal)

  # LLM enhancement
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("cluster", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
