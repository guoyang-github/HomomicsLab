#' Step 4: Integration Decision — Spatial Transcriptomics Pipeline (R)
#'
#' Reference: Seurat 5.0+, harmony 1.0+
#'
#' Input State:  [Normalized] + [HVG]
#' Output State: [Integrated] (if needed) or [Normalized] (if skipped)
#'
#' Critical: For spatial data, integration should preserve spatial images
#' and coordinates per sample.

library(Seurat)
library(harmony)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

propose_integration <- function(obj, sample_col = "sample_id") {
  #' Diagnose batch effects and propose integration strategy.
  #'
  #' @param obj Seurat object [Normalized]
  #' @param sample_col Column name for sample identifier
  #' @return Recommendation list

  if (!(sample_col %in% colnames(obj@meta.data))) {
    return(list(
      recommendation = list(
        integrate = FALSE,
        method = NULL,
        reason = sprintf("No '%s' column found. Single-sample analysis.", sample_col)
      ),
      diagnostics = list(n_samples = 1),
      justification = "Single sample detected."
    ))
  }

  samples <- unique(obj@meta.data[[sample_col]])
  n_samples <- length(samples)

  if (n_samples <= 1) {
    return(list(
      recommendation = list(
        integrate = FALSE,
        method = NULL,
        reason = "Only one sample detected. Integration not needed."
      ),
      diagnostics = list(n_samples = n_samples),
      justification = "Single sample. Proceed directly to clustering."
    ))
  }

  # Quick PCA for diagnostic (use copy to avoid mutating original)
  obj_tmp <- obj
  if (!("pca" %in% names(obj_tmp@reductions))) {
    obj_tmp <- ScaleData(obj_tmp, verbose = FALSE)
    obj_tmp <- RunPCA(obj_tmp, npcs = 30, verbose = FALSE)
  }
  obj_tmp <- RunUMAP(obj_tmp, dims = 1:20, verbose = FALSE)

  # Batch mixing score
  embeddings <- Embeddings(obj_tmp, "umap")
  batch_labels <- as.factor(obj_tmp@meta.data[[sample_col]])
  knn_same_batch <- .compute_knn_batch_mix(embeddings, batch_labels, k = 15)
  batch_score <- mean(knn_same_batch)

  if (batch_score < 0.3) {
    integrate <- FALSE
    reason <- sprintf(
      "Batch mixing score = %.2f (<0.3). Samples well-mixed.", batch_score
    )
    method <- NULL
  } else if (batch_score < 0.6) {
    integrate <- TRUE
    reason <- sprintf(
      "Batch mixing score = %.2f (0.3-0.6). Moderate batch effect.", batch_score
    )
    method <- "Harmony"
  } else {
    integrate <- TRUE
    reason <- sprintf(
      "Batch mixing score = %.2f (>0.6). Strong batch effect.", batch_score
    )
    method <- "Harmony"
  }

  list(
    recommendation = list(
      integrate = integrate,
      method = method,
      sample_col = sample_col,
      reason = reason
    ),
    diagnostics = list(
      n_samples = n_samples,
      n_spots = ncol(obj),
      batch_mixing_score = round(batch_score, 3)
    ),
    justification = reason,
    alternatives = list(
      Harmony = "Fast, works for most cases (2-5 samples).",
      RPCA = "More conservative, good for many samples."
    )
  )
}


.compute_knn_batch_mix <- function(embeddings, batch_labels, k = 15) {
  #' Helper: compute fraction of k-nearest neighbors from same batch.
  n_cells <- nrow(embeddings)

  if (requireNamespace("FNN", quietly = TRUE)) {
    knn <- FNN::get.knn(embeddings, k = k)
    knn_indices <- knn$nn.index
  } else {
    dist_mat <- as.matrix(dist(embeddings))
    knn_indices <- apply(dist_mat, 1, function(x) order(x)[2:(k + 1)])
    if (!is.matrix(knn_indices)) {
      knn_indices <- matrix(knn_indices, ncol = 1)
    }
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
  #' Evaluate spatial integration proposal before execution.
  #'
  #' Guardrails:
  #'   - Single sample / integrate=FALSE → PROCEED (skip)
  #'   - batch_mixing_score < 0.1 → BLOCK (force skip)
  #'   - batch_mixing_score > 0.9 → CAUTION

  rec <- proposal$recommendation

  if (!rec$integrate) {
    return(list(verdict = "PROCEED", adjusted = FALSE,
                reason = "Single sample or integration not recommended. Skipping execution."))
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
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

execute_integration <- function(obj, method = "Harmony",
                                 sample_col = "sample_id", npcs = 50, ...) {
  #' Run batch integration with specified method.
  #'
  #' For spatial data, preserves images and uses RunHarmony for metadata-based
  #' integration (safer for preserving spatial structure).
  #'
  #' @param obj Seurat object [Normalized]
  #' @param method "Harmony" or "RPCA"
  #' @param sample_col Column name for sample
  #' @param npcs PCs for PCA
  #' @param ... Additional args
  #' @return Seurat object [Integrated]

  if (method == "Harmony") {
    assay <- DefaultAssay(obj)
    if (length(Layers(obj[[assay]])) > 1) {
      obj[[assay]] <- JoinLayers(obj[[assay]])
    }

    if (!("pca" %in% names(obj@reductions))) {
      obj <- ScaleData(obj, verbose = FALSE)
      obj <- RunPCA(obj, npcs = npcs, verbose = FALSE)
    }

    obj <- harmony::RunHarmony(obj, group.by.vars = sample_col,
                                reduction = "pca", assay.use = assay, ...)
    obj@misc$integration_reduction <- "harmony"

  } else if (method == "RPCA") {
    if (!("pca" %in% names(obj@reductions))) {
      obj <- ScaleData(obj, verbose = FALSE)
      obj <- RunPCA(obj, npcs = npcs, verbose = FALSE)
    }
    obj <- IntegrateLayers(
      object = obj,
      method = RPCAIntegration,
      orig.reduction = "pca",
      new.reduction = "integrated.rpca",
      ...
    )
    assay <- DefaultAssay(obj)
    if (length(Layers(obj[[assay]])) > 1) {
      obj[[assay]] <- JoinLayers(obj[[assay]])
    }
    obj@misc$integration_reduction <- "integrated.rpca"

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

  method <- obj@misc$integration_method

  if (method == "None") {
    list(
      step = "Batch Integration",
      status = "SKIPPED",
      method = "None",
      reason = proposal$recommendation$reason,
      recommendation = "Integration not needed. Proceed to clustering using PCA embeddings.",
      next_step = "Step 5: Clustering + UMAP"
    )
  } else {
    list(
      step = "Batch Integration",
      status = "PASS",
      method = method,
      n_samples = proposal$diagnostics$n_samples,
      recommendation = sprintf(
        "Integration with %s complete. Use '%s' for downstream clustering.",
        method, obj@misc$integration_reduction
      ),
      next_step = "Step 5: Clustering + UMAP"
    )
  }
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_integration_step <- function(obj, sample_col = "sample_id", method = NULL,
                                   auto = FALSE, use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete integration decision step.

  # State validation
  expected_states <- c("Normalized")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for integration step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_integration(obj, sample_col = sample_col)

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
    message(sprintf("Samples detected: %d", proposal$diagnostics$n_samples))
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
    obj <- execute_integration(obj, method = method, sample_col = sample_col, ...)
  } else {
    obj <- skip_integration(obj)
  }

  report <- report_integration(obj, proposal)

  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("integration", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
