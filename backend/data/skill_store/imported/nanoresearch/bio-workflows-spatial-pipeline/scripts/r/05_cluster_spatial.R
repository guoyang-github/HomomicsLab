#' Step 5: Clustering + UMAP — Spatial Transcriptomics Pipeline (R)
#'
#' Reference: Seurat 5.0+
#'
#' Input State:  [Normalized] or [Integrated]
#' Output State: [Clustered] + [UMAP]
#'
#' Pure transcriptomic clustering. Spatial domain detection is Step 7.

library(Seurat)


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

propose_clustering_params <- function(obj) {
  #' Propose PCA dimensions and clustering resolutions for spatial data.

  n_spots <- ncol(obj)
  npcs <- 50

  # Resolution based on spot count
  if (n_spots < 3000) {
    resolutions <- c(0.3, 0.5, 0.8)
    default_res <- 0.5
    res_reason <- "Small tissue section (<3k spots). Lower resolutions avoid over-segmentation."
  } else if (n_spots < 20000) {
    resolutions <- c(0.3, 0.5, 0.8, 1.2)
    default_res <- 0.8
    res_reason <- "Medium tissue. Standard resolution range."
  } else {
    resolutions <- c(0.3, 0.5, 0.8, 1.2, 1.6)
    default_res <- 1.2
    res_reason <- "Large tissue section (>20k spots). Higher resolutions may reveal fine domains."
  }

  list(
    recommendation = list(
      npcs = npcs,
      npcs_use = 30,
      resolutions = resolutions,
      default_resolution = default_res,
      reduction = obj@misc$integration_reduction %||% "pca"
    ),
    diagnostics = list(
      n_spots = n_spots,
      n_genes = nrow(obj)
    ),
    justification = res_reason,
    alternatives = list(
      lower_res = "Use 0.2-0.4 for broad tissue domains.",
      higher_res = "Use 1.5-2.0 for fine-grained subdomains."
    )
  )
}


`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_clustering_proposal <- function(proposal, obj) {
  #' Evaluate spatial clustering proposal before execution.
  #'
  #' Guardrails:
  #'   - Any resolution outside [0.1, 2.0] → BLOCK + clamp
  #'   - n_pcs_use < 5 → CAUTION

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
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

execute_clustering <- function(obj, npcs = 50, resolutions = c(0.3, 0.5, 0.8),
                                default_res = NULL, reduction = "pca", ...) {
  #' Run transcriptomic clustering + UMAP.

  # PCA
  if (!("pca" %in% names(obj@reductions))) {
    obj <- RunPCA(obj, features = VariableFeatures(obj), npcs = npcs, verbose = FALSE)
  }

  # Elbow-based dim selection
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

  # Multi-resolution clustering
  for (res in resolutions) {
    obj <- FindClusters(obj, resolution = res, verbose = FALSE)
  }

  # Set default identity
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

  resolutions <- proposal$recommendation$resolutions
  res_cols <- grep("snn_res\\.", colnames(obj@meta.data), value = TRUE)
  cluster_counts <- sapply(res_cols, function(col) length(unique(obj@meta.data[[col]])))

  default_res <- proposal$recommendation$default_resolution
  default_col <- grep(paste0(DefaultAssay(obj), "_snn_res.", default_res),
                      colnames(obj@meta.data), value = TRUE, fixed = TRUE)[1]
  if (is.na(default_col)) {
    default_col <- res_cols[min(2, length(res_cols))]
  }

  n_clusters <- length(unique(obj@meta.data[[default_col]]))

  status <- if (n_clusters < 3 || n_clusters > 50) "CAUTION" else "PASS"

  list(
    step = "Clustering",
    status = status,
    n_clusters = n_clusters,
    resolution = default_res,
    default_column = default_col,
    all_resolutions = setNames(cluster_counts, res_cols),
    n_pcs_used = length(obj@misc$clustering_dims),
    recommendation = if (n_clusters < 3) {
      "Too few clusters. Consider higher resolution or check tissue coverage."
    } else if (n_clusters > 50) {
      "Many clusters. May indicate over-clustering; try lower resolution for broad domains."
    } else {
      sprintf("Clustering looks reasonable (%d clusters at res=%.1f). Proceed to spatial analysis.",
              n_clusters, default_res)
    },
    next_step = "Step 6: Spatial Analysis"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_clustering_step <- function(obj, npcs = NULL, resolutions = NULL,
                                 reduction = NULL, auto = FALSE,
                                 use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete clustering step for spatial data.

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
    message(sprintf("Resolutions: %s", paste(resolutions, collapse = ", ")))
    message(sprintf("Default resolution: %.1f", proposal$recommendation$default_resolution))
    message(sprintf("Justification: %s", proposal$justification))
  }

  obj <- execute_clustering(
    obj, npcs = npcs, resolutions = resolutions,
    default_res = proposal$recommendation$default_resolution,
    reduction = reduction,
    ...
  )
  report <- report_clustering(obj, proposal)

  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("cluster", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
