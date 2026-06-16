#' Step 5: Integration Decision — Propose / Execute / Report
#'
#' Reference: Seurat 5.0+, harmony 1.0+
#'
#' Input State:  [Normalized] + [HVG]
#' Output State: [Integrated] (if needed) or [Normalized] (if skipped)
#'
#' Critical decision point: diagnose batch effects BEFORE integration.
#' Strategy: quick PCA+UMAP without integration → assess → recommend.

library(Seurat)
library(harmony)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Diagnose batch effects and recommend
# ---------------------------------------------------------------------------

propose_integration <- function(obj, batch_col = "sample_id") {
  #' Diagnose batch effects and propose integration strategy.
  #'
  #' @param obj Seurat object [Normalized]
  #' @param batch_col Column name for batch/sample identifier
  #' @return Recommendation list

  if (!(batch_col %in% colnames(obj@meta.data))) {
    return(list(
      recommendation = list(
        integrate = FALSE,
        method = NULL,
        reason = sprintf("No '%s' column found. Single-sample analysis — integration not needed.", batch_col)
      ),
      diagnostics = list(n_batches = 1),
      justification = "Single sample detected."
    ))
  }

  n_batches <- length(unique(obj@meta.data[[batch_col]]))

  if (n_batches <= 1) {
    return(list(
      recommendation = list(
        integrate = FALSE,
        method = NULL,
        reason = "Only one batch detected. Integration not needed."
      ),
      diagnostics = list(n_batches = n_batches),
      justification = "Single batch. Proceed directly to clustering."
    ))
  }

  # Quick PCA for diagnostic UMAP
  obj_tmp <- obj
  if (!("pca" %in% names(obj_tmp@reductions))) {
    if (!("SCT" %in% names(obj_tmp@assays) && DefaultAssay(obj_tmp) == "SCT")) {
      obj_tmp <- ScaleData(obj_tmp, verbose = FALSE)
    }
    obj_tmp <- RunPCA(obj_tmp, npcs = 30, verbose = FALSE)
  }
  obj_tmp <- RunUMAP(obj_tmp, dims = 1:20, verbose = FALSE)

  # Compute batch mixing metric (approximate silhouette-based)
  # Lower score = better mixing
  embeddings <- Embeddings(obj_tmp, "umap")
  batch_labels <- as.factor(obj_tmp@meta.data[[batch_col]])

  # Simple metric: proportion of nearest neighbors from same batch
  knn_same_batch <- .compute_knn_batch_mix(embeddings, batch_labels, k = 15)
  batch_score <- mean(knn_same_batch)

  # Score interpretation
  if (batch_score < 0.3) {
    integrate <- FALSE
    reason <- sprintf(
      "Batch mixing score = %.2f (<0.3). Batches are already well-mixed. Integration may over-correct biological variation.",
      batch_score
    )
    method <- NULL
  } else if (batch_score < 0.6) {
    integrate <- TRUE
    reason <- sprintf(
      "Batch mixing score = %.2f (0.3-0.6). Moderate batch effect detected. Integration recommended to improve clustering.",
      batch_score
    )
    method <- "Harmony"
  } else {
    integrate <- TRUE
    reason <- sprintf(
      "Batch mixing score = %.2f (>0.6). Strong batch effect detected. Integration strongly recommended.",
      batch_score
    )
    method <- if (n_batches > 5 || ncol(obj) > 50000) "RPCA" else "Harmony"
  }

  list(
    recommendation = list(
      integrate = integrate,
      method = method,
      batch_col = batch_col,
      reason = reason,
      n_batches = n_batches
    ),
    diagnostics = list(
      n_batches = n_batches,
      n_cells = ncol(obj),
      batch_mixing_score = round(batch_score, 3)
    ),
    justification = reason,
    alternatives = list(
      Harmony = "Fast, works for most cases (2-5 batches, <50k cells).",
      RPCA = "More conservative, better for >5 batches or large datasets.",
      CCA = "Best for reference-mapping with known anchors.",
      fastMNN = "Preserves rare populations well."
    )
  )
}


.compute_knn_batch_mix <- function(embeddings, batch_labels, k = 15) {
  #' Helper: compute fraction of k-nearest neighbors from same batch.
  #' Lower values indicate better mixing.
  #' @return Vector of same-batch fractions per cell

  n_cells <- nrow(embeddings)

  # Use FNN for fast nearest neighbor search
  if (!requireNamespace("FNN", quietly = TRUE)) {
    # Fallback: simple Euclidean distance (slower)
    dist_mat <- as.matrix(dist(embeddings))
    knn_indices <- apply(dist_mat, 1, function(x) order(x)[2:(k+1)])
    # Ensure matrix format even when k=1
    if (!is.matrix(knn_indices)) {
      knn_indices <- matrix(knn_indices, ncol = 1)
    }
  } else {
    knn <- FNN::get.knn(embeddings, k = k)
    knn_indices <- knn$nn.index
  }

  same_batch <- sapply(1:nrow(knn_indices), function(i) {
    neighbors <- knn_indices[i, , drop = FALSE]
    mean(batch_labels[as.vector(neighbors)] == batch_labels[i])
  })

  return(same_batch)
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_integration_proposal <- function(proposal, obj) {
  #' Evaluate integration proposal before execution.
  #'
  #' Guardrails:
  #'   - Single batch / integrate=FALSE → PROCEED (skip)
  #'   - batch_mixing_score < 0.1 → BLOCK (already well-mixed, integration harmful)
  #'   - batch_mixing_score > 0.9 → CAUTION (very strong batch, may need manual review)

  rec <- proposal$recommendation

  if (!rec$integrate) {
    return(list(verdict = "PROCEED", adjusted = FALSE,
                reason = "Single batch or integration not recommended. Skipping execution."))
  }

  score <- proposal$diagnostics$batch_mixing_score

  if (!is.null(score) && score < 0.1) {
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf("Batch mixing score = %.3f (<0.1). Already perfectly mixed. Integration may remove biological signal. Forcing skip.", score),
      adjusted_recommendation = list(integrate = FALSE, method = NULL)
    ))
  }

  if (!is.null(score) && score > 0.9) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Batch mixing score = %.3f (>0.9). Extremely strong batch effect. Verify samples are comparable.", score)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Run integration if recommended
# ---------------------------------------------------------------------------

.is_sct_assay <- function(obj) {
  #' Detect whether the default assay was SCTransformed.
  default <- DefaultAssay(obj)
  "SCT" %in% names(obj@assays) && default == "SCT"
}


.METHOD_MAP_V5 <- list(
  Harmony = list(method = "HarmonyIntegration", reduction = "harmony"),
  RPCA    = list(method = "RPCAIntegration",    reduction = "integrated.rpca"),
  CCA     = list(method = "CCAIntegration",     reduction = "integrated.cca"),
  fastMNN = list(method = "FastMNNIntegration", reduction = "integrated.mnn")
)


execute_integration <- function(obj, method = "Harmony", batch_col = "sample_id", npcs = 50, ...) {
  #' Run batch integration with specified method (Seurat v5).
  #'
  #' Uses IntegrateLayers for all methods except legacy RunHarmony fallback.
  #' Auto-detects SCT vs LogNormalize workflow.
  #'
  #' @param obj Seurat object [Normalized]
  #' @param method "Harmony", "RPCA", "CCA", or "fastMNN"
  #' @param batch_col Column name for batch (used by RunHarmony fallback)
  #' @param npcs PCs for PCA
  #' @param ... Additional args passed to IntegrateLayers or RunHarmony
  #' @return Seurat object [Integrated]

  use_sct <- .is_sct_assay(obj)

  # ------------------------------------------------------------------
  # Harmony via RunHarmony (metadata-based, supports multi-var)
  # ------------------------------------------------------------------
  if (method == "Harmony") {
    assay <- DefaultAssay(obj)

    # RunHarmony needs a unified (joined) matrix, not split layers
    obj[[assay]] <- JoinLayers(obj[[assay]])

    if (!("pca" %in% names(obj@reductions))) {
      if (use_sct) {
        obj <- RunPCA(obj, npcs = npcs, verbose = FALSE)
      } else {
        obj <- NormalizeData(obj, verbose = FALSE)
        obj <- FindVariableFeatures(obj, verbose = FALSE)
        obj <- ScaleData(obj, verbose = FALSE)
        obj <- RunPCA(obj, npcs = npcs, verbose = FALSE)
      }
    }

    obj <- harmony::RunHarmony(obj, group.by.vars = batch_col,
                                reduction = "pca", assay.use = assay, ...)
    obj@misc$integration_reduction <- "harmony"

  # ------------------------------------------------------------------
  # CCA / RPCA / fastMNN via IntegrateLayers (layer-based)
  # ------------------------------------------------------------------
  } else if (method %in% names(.METHOD_MAP_V5)) {
    cfg <- .METHOD_MAP_V5[[method]]

    if (use_sct) {
      # SCT workflow: SCTransform already done; just PCA + IntegrateLayers
      if (!("pca" %in% names(obj@reductions))) {
        obj <- RunPCA(obj, npcs = npcs, verbose = FALSE)
      }
      obj <- IntegrateLayers(
        object = obj,
        method = cfg$method,
        normalization.method = "SCT",
        orig.reduction = "pca",
        new.reduction = cfg$reduction,
        ...
      )
    } else {
      # Standard workflow
      if (!("pca" %in% names(obj@reductions))) {
        obj <- NormalizeData(obj, verbose = FALSE)
        obj <- FindVariableFeatures(obj, verbose = FALSE)
        obj <- ScaleData(obj, verbose = FALSE)
        obj <- RunPCA(obj, npcs = npcs, verbose = FALSE)
      }
      obj <- IntegrateLayers(
        object = obj,
        method = cfg$method,
        orig.reduction = "pca",
        new.reduction = cfg$reduction,
        ...
      )
      # Join layers before downstream DE
      assay <- DefaultAssay(obj)
      obj[[assay]] <- JoinLayers(obj[[assay]])
    }

    obj@misc$integration_reduction <- cfg$reduction

  } else {
    stop("Unknown integration method: ", method)
  }

  obj@misc$pipeline_state <- "Integrated"
  obj@misc$integration_method <- method
  message(sprintf("Integration complete: %s", method))

  return(obj)
}


skip_integration <- function(obj) {
  #' Tag object as proceeding without integration.
  obj@misc$pipeline_state <- "Normalized"
  obj@misc$integration_method <- "None"
  obj@misc$integration_reduction <- "pca"
  return(obj)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_integration <- function(obj, proposal) {
  #' Report integration results.
  #'
  #' @param obj Seurat object
  #' @param proposal Proposal list from propose_integration()
  #' @return Report list

  method <- obj@misc$integration_method

  if (method == "None") {
    list(
      step = "Batch Integration",
      status = "SKIPPED",
      method = "None",
      reason = proposal$recommendation$reason,
      recommendation = "Integration not needed. Proceed to clustering using PCA embeddings.",
      next_step = "Step 6: Dimensionality Reduction + Clustering"
    )
  } else {
    list(
      step = "Batch Integration",
      status = "PASS",
      method = method,
      n_batches = proposal$diagnostics$n_batches,
      recommendation = sprintf(
        "Integration with %s complete. Use '%s' reduction for downstream clustering.",
        method, obj@misc$integration_reduction
      ),
      next_step = "Step 6: Dimensionality Reduction + Clustering"
    )
  }
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_integration_step <- function(obj, batch_col = "sample_id", method = NULL,
                                   auto = FALSE, use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete integration decision step.
  #'
  #' @param obj Seurat object [Normalized]
  #' @param batch_col Batch column name
  #' @param method Override proposed method (NULL = auto)
  #' @param auto Skip proposal display
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @param ... Passed to execute_integration
  #' @return List(obj, report, proposal, llm_report)

  # State validation
  expected_states <- c("Normalized")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for integration step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_integration(obj, batch_col = batch_col)

  # Evaluate phase: guardrail on batch mixing score
  evaluation <- evaluate_integration_proposal(proposal, obj)
  if (evaluation$adjusted) {
    message("GUARDRAIL: ", evaluation$reason)
    proposal$recommendation <- evaluation$adjusted_recommendation
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (!auto) {
    message("\n=== Integration Proposal ===")
    message(sprintf("Batches detected: %d", proposal$diagnostics$n_batches))
    if (!is.null(proposal$diagnostics$batch_mixing_score)) {
      message(sprintf("Batch mixing score: %.3f", proposal$diagnostics$batch_mixing_score))
    }
    message(sprintf("Recommendation: %s", proposal$justification))
    if (proposal$recommendation$integrate) {
      message(sprintf("Suggested method: %s", proposal$recommendation$method))
    }
  }

  if (is.null(method)) {
    integrate <- proposal$recommendation$integrate
    method <- proposal$recommendation$method
  } else {
    integrate <- (method != "None")
  }

  if (integrate) {
    obj <- execute_integration(obj, method = method, batch_col = batch_col, ...)
  } else {
    obj <- skip_integration(obj)
  }

  report <- report_integration(obj, proposal)

  # LLM enhancement
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("integration", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
