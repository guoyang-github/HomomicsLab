#' Step 3: Normalization + HVG — Spatial Transcriptomics Pipeline (R)
#'
#' Reference: Seurat 5.0+
#'
#' Input State:  [Filtered]
#' Output State: [Normalized] + [HVG]
#'
#' Note: For spatial data, LogNormalize is standard. SCTransform can be used
#' but may overfit on spot-level counts. LogNormalize + ScaleData is the
#' conservative default.

library(Seurat)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

propose_normalization <- function(obj) {
  #' Propose normalization strategy for spatial data.
  #'
  #' @param obj Seurat object [Filtered]
  #' @return Recommendation list

  n_spots <- ncol(obj)
  method <- "LogNormalize"

  justification <- paste(
    "LogNormalize is standard for spatial transcriptomics:",
    "fast, well-tested, compatible with downstream spatial statistics.",
    "SCTransform may overfit at spot level (low UMI counts per spot)."
  )

  if (n_spots < 1000) {
    justification <- paste(justification, "Small dataset; results should be interpreted cautiously.")
  }

  list(
    recommendation = list(
      method = method,
      target_sum = 1e4,
      n_hvg = 2000
    ),
    diagnostics = list(
      n_spots = n_spots,
      n_genes = nrow(obj)
    ),
    justification = justification,
    alternatives = list(
      SCTransform = "Use if comparing with scRNA-seq SCT workflow; may overfit on spots.",
      shift_log = "Use for large datasets (>100k spots) where exact normalization is too slow."
    )
  )
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_normalization_proposal <- function(proposal, obj) {
  #' Evaluate spatial normalization proposal before execution.
  #'
  #' Guardrails:
  #'   - n_hvg < 500 or > 5000 → BLOCK + clamp
  #'   - n_spots < 100 → CAUTION (too few for reliable HVG selection)

  n_hvg <- proposal$recommendation$n_hvg

  if (n_hvg < 500 || n_hvg > 5000) {
    clamped <- max(500, min(5000, n_hvg))
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf("n_hvg = %d outside [500, 5000]. Clamped to %d.", n_hvg, clamped),
      adjusted_params = list(n_hvg = clamped)
    ))
  }

  n_spots <- proposal$diagnostics$n_spots
  if (n_spots < 100) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Only %d spots. HVG selection may be unreliable.", n_spots)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

execute_lognormalize <- function(obj, target_sum = 1e4, n_hvg = 2000, verbose = FALSE) {
  #' Run LogNormalize + HVG selection for spatial data.
  #'
  #' @param obj Seurat object [Filtered]
  #' @param target_sum Target sum for normalization
  #' @param n_hvg Number of highly variable genes
  #' @param verbose Print progress
  #' @return Seurat object [Normalized] + [HVG]

  obj <- NormalizeData(obj, normalization.method = "LogNormalize",
                        scale.factor = target_sum, verbose = verbose)
  obj <- FindVariableFeatures(obj, selection.method = "vst",
                               nfeatures = n_hvg, verbose = verbose)
  obj <- ScaleData(obj, verbose = verbose)

  obj@misc$pipeline_state <- "Normalized"
  obj@misc$normalization_method <- "LogNormalize"

  n_hvg_selected <- length(VariableFeatures(obj))
  message(sprintf("LogNormalize complete. HVGs selected: %d", n_hvg_selected))

  return(obj)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_normalization <- function(obj) {
  #' Report normalization results.
  #'
  #' @param obj Seurat object [Normalized]
  #' @return Report list

  method <- obj@misc$normalization_method
  n_hvg <- length(VariableFeatures(obj))

  status <- if (n_hvg >= 1500 && n_hvg <= 3000) {
    "PASS"
  } else {
    "CAUTION"
  }

  list(
    step = "Normalization + HVG",
    status = status,
    method = method,
    n_hvg = n_hvg,
    recommendation = if (status == "PASS") {
      "HVG count within optimal range (1500-3000). Proceed to clustering."
    } else {
      sprintf("HVG count = %d. Consider adjusting nfeatures if downstream domains are poor.", n_hvg)
    },
    next_step = "Step 4: Integration Decision"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_normalization_step <- function(obj, method = NULL, auto = FALSE,
                                      use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete normalization step for spatial data.
  #'
  #' @param obj Seurat object [Filtered]
  #' @param method "LogNormalize" or "SCTransform". NULL = auto-propose.
  #' @param auto Skip proposal display
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @param prev_reports Previous step reports for cross-step analysis.
  #' @param ... Passed to normalization function
  #' @return List(obj, report, proposal, llm_report)

  # State validation
  expected_states <- c("Filtered")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for normalization step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_normalization(obj)

  # Evaluate phase: guardrail on HVG target
  evaluation <- evaluate_normalization_proposal(proposal, obj)
  if (evaluation$adjusted) {
    message("GUARDRAIL: ", evaluation$reason)
    proposal$recommendation$n_hvg <- evaluation$adjusted_params$n_hvg
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(method)) {
    method <- proposal$recommendation$method
  }

  if (!auto) {
    message("\n=== Normalization Proposal ===")
    message(sprintf("Recommended: %s", method))
    message(sprintf("Justification: %s", proposal$justification))
  }

  if (method == "LogNormalize") {
    obj <- execute_lognormalize(
      obj,
      target_sum = proposal$recommendation$target_sum,
      n_hvg = proposal$recommendation$n_hvg,
      ...
    )
  } else if (method == "SCTransform") {
    obj <- SCTransform(obj, vst.flavor = "v2", verbose = FALSE, ...)
    obj@misc$pipeline_state <- "Normalized"
    obj@misc$normalization_method <- "SCTransform"
  } else {
    stop("Unknown normalization method: ", method)
  }

  report <- report_normalization(obj)

  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("normalize", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
