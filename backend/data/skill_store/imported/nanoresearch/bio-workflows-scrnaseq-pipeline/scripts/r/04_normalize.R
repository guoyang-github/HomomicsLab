#' Step 4: Normalization + HVG — Single-Cell RNA-seq Pipeline (R)
#'
#' Reference: Seurat 5.0+
#'
#' Input State:  [Clean]
#' Output State: [Normalized] + [HVG]
#'
#' Supports:
#' - SCTransform (recommended for most data, regression-aware)
#' - LogNormalize + ScaleData (legacy, for comparison or specific needs)

library(Seurat)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend normalization method
# ---------------------------------------------------------------------------

propose_normalization <- function(obj) {
  #' Propose normalization strategy based on data characteristics.
  #'
  #' @param obj Seurat object [Clean]
  #' @return Recommendation list

  n_cells <- ncol(obj)
  method <- "SCTransform"

  justification <- paste(
    "SCTransform is recommended for most analyses:",
    "(1) models technical variance directly,",
    "(2) selects HVGs automatically,",
    "(3) better for downstream integration."
  )

  # Only suggest LogNormalize for very simple datasets or specific comparisons
  if (n_cells < 1000) {
    justification <- paste(
      justification,
      "Small dataset (<1k cells); SCTransform may overfit. LogNormalize is acceptable alternative."
    )
  }

  vars_to_regress <- c("percent.mt")
  if ("percent.ribo" %in% colnames(obj@meta.data)) {
    # Ribosomal percentage rarely needs regression
  }

  list(
    recommendation = list(
      method = method,
      vars_to_regress = vars_to_regress,
      n_hvg_target = 2000
    ),
    diagnostics = list(
      n_cells = n_cells,
      n_genes = nrow(obj)
    ),
    justification = justification,
    alternatives = list(
      LogNormalize = "Use if comparing directly with published LogNormalize workflows.",
      SCTransform_v2 = "Use `vst.flavor = 'v2'` for UMI-based datasets (default in Seurat v5)."
    )
  )
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_normalization_proposal <- function(proposal, obj) {
  #' Evaluate normalization proposal before execution.
  #'
  #' Guardrails:
  #'   - n_hvg_target < 500 or > 5000 → BLOCK + clamp
  #'   - n_cells < 100 → CAUTION (too few for reliable HVG selection)

  n_hvg <- proposal$recommendation$n_hvg_target

  if (n_hvg < 500 || n_hvg > 5000) {
    clamped <- max(500, min(5000, n_hvg))
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf("n_hvg_target = %d outside [500, 5000]. Clamped to %d.", n_hvg, clamped),
      adjusted_params = list(n_hvg_target = clamped)
    ))
  }

  n_cells <- proposal$diagnostics$n_cells
  if (n_cells < 100) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Only %d cells. HVG selection may be unreliable.", n_cells)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

execute_sctransform <- function(obj, vars.to.regress = "percent.mt", verbose = FALSE) {
  #' Run SCTransform normalization.
  #'
  #' @param obj Seurat object [Clean]
  #' @param vars.to.regress Variables to regress out
  #' @param verbose Print progress
  #' @return Seurat object [Normalized] + [HVG]

  obj <- SCTransform(obj, vars.to.regress = vars.to.regress, vst.flavor = "v2", verbose = verbose)
  obj@misc$pipeline_state <- "Normalized"
  obj@misc$normalization_method <- "SCTransform"

  n_hvg <- length(VariableFeatures(obj))
  message(sprintf("SCTransform complete. HVGs selected: %d", n_hvg))

  return(obj)
}


execute_lognormalize <- function(obj, n_hvg = 2000, verbose = FALSE) {
  #' Run LogNormalize + FindVariableFeatures as alternative.
  #'
  #' @param obj Seurat object [Clean]
  #' @param n_hvg Number of highly variable genes
  #' @param verbose Print progress
  #' @return Seurat object [Normalized] + [HVG]

  obj <- NormalizeData(obj, verbose = verbose)
  obj <- FindVariableFeatures(obj, selection.method = "vst",
                               nfeatures = n_hvg, verbose = verbose)
  obj <- ScaleData(obj, verbose = verbose)
  obj@misc$pipeline_state <- "Normalized"
  obj@misc$normalization_method <- "LogNormalize"

  message(sprintf("LogNormalize complete. HVGs selected: %d", length(VariableFeatures(obj))))

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
      "HVG count within optimal range (1500-3000). Proceed to integration check."
    } else {
      sprintf("HVG count = %d. Consider adjusting nfeatures parameter if downstream clustering is poor.", n_hvg)
    },
    next_step = "Step 5: Integration Decision (check for batch effects)"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_normalization_step <- function(obj, method = NULL, auto = FALSE,
                                      use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete normalization step.
  #'
  #' @param obj Seurat object [Clean]
  #' @param method "SCTransform" or "LogNormalize". NULL = auto-propose.
  #' @param auto Skip proposal display
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @param prev_reports Previous step reports for cross-step analysis.
  #' @param ... Passed to normalization function
  #' @return List(obj = [Normalized], report = report, proposal, llm_report)

  # State validation
  expected_states <- c("Clean", "Filtered")
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
    proposal$recommendation$n_hvg_target <- evaluation$adjusted_params$n_hvg_target
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(method)) {
    method <- proposal$recommendation$method
  }

  if (!auto) {
    message("\n=== Normalization Proposal ===")
    message(sprintf("Recommended: %s", method))
    message(sprintf("Vars to regress: %s", paste(proposal$recommendation$vars_to_regress, collapse = ", ")))
    message(sprintf("Justification: %s", proposal$justification))
  }

  if (method == "SCTransform") {
    obj <- execute_sctransform(obj, vars.to.regress = proposal$recommendation$vars_to_regress, ...)
  } else if (method == "LogNormalize") {
    obj <- execute_lognormalize(obj, n_hvg = proposal$recommendation$n_hvg_target, ...)
  } else {
    stop("Unknown normalization method: ", method)
  }

  report <- report_normalization(obj)

  # LLM enhancement
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("normalize", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
