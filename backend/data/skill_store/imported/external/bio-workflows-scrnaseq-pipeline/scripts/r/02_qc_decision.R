#' Step 2: QC Decision — Propose / Execute / Report
#'
#' Reference: Seurat 5.0+
#'
#' Input State:  [Raw]
#' Output State: [Filtered]
#'
#' Philosophy: Diagnose first, propose thresholds with justification,
#'             then execute after user confirmation (or auto-run).

library(Seurat)
library(ggplot2)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Diagnose and recommend thresholds
# ---------------------------------------------------------------------------

propose_qc_thresholds <- function(obj) {
  #' Analyze QC distributions and propose data-driven thresholds.
  #'
  #' @param obj Seurat object [Raw]
  #' @return List with proposed thresholds and diagnostic summary

  # Compute QC metrics if not present
  if (!("percent.mt" %in% colnames(obj@meta.data))) {
    obj[["percent.mt"]] <- PercentageFeatureSet(obj, pattern = "^MT-")
  }
  if (!("percent.ribo" %in% colnames(obj@meta.data))) {
    obj[["percent.ribo"]] <- PercentageFeatureSet(obj, pattern = "^RP[SL]")
  }

  nfeature <- obj$nFeature_RNA
  ncount <- obj$nCount_RNA
  mt <- obj$percent.mt

  # Dynamic thresholds based on data characteristics
  nfeature_q99 <- quantile(nfeature, 0.99)
  nfeature_q01 <- quantile(nfeature, 0.01)  # available for custom threshold tuning

  # MT%: if median > 10%, likely tissue with stress; be conservative
  mt_median <- median(mt, na.rm = TRUE)
  if (mt_median > 10) {
    mt_threshold <- min(25, mt_median + 2 * sd(mt, na.rm = TRUE))
    mt_reason <- sprintf(
      "MT%% median = %.1f%% (high, suggesting tissue dissociation stress). Conservative threshold recommended.",
      mt_median
    )
  } else if (mt_median > 5) {
    mt_threshold <- 15
    mt_reason <- sprintf(
      "MT%% median = %.1f%% (moderate). Standard threshold applies.",
      mt_median
    )
  } else {
    mt_threshold <- 10
    mt_reason <- sprintf(
      "MT%% median = %.1f%% (low, likely nuclei or clean sample). Stringent threshold OK.",
      mt_median
    )
  }

  # nFeature: upper bound based on 99th percentile to catch doublets
  nfeature_max <- max(5000, nfeature_q99 * 1.2)
  nfeature_min <- 200

  # nCount: lower bound based on 1st percentile of total counts
  ncount_min <- max(500, quantile(ncount, 0.01))

  proposal <- list(
    thresholds = list(
      nFeature_RNA_min = round(nfeature_min, 0),
      nFeature_RNA_max = round(nfeature_max, 0),
      nCount_RNA_min = round(ncount_min, 0),
      percent_mt_max = round(mt_threshold, 1)
    ),
    diagnostics = list(
      n_cells = ncol(obj),
      nfeature_median = round(median(nfeature)),
      nfeature_q99 = round(nfeature_q99, 0),
      ncount_median = round(median(ncount)),
      mt_median = round(mt_median, 2),
      mt_q95 = round(quantile(mt, 0.95), 2)
    ),
    justification = list(
      nFeature = sprintf(
        "Range %d-%d captures >95%% of cells while removing low-quality / doublet outliers.",
        round(nfeature_min, 0), round(nfeature_max, 0)
      ),
      nCount = sprintf(
        "Minimum %d total counts ensures sufficient sequencing depth.",
        round(ncount_min, 0)
      ),
      MT = mt_reason
    )
  )

  return(proposal)
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_qc_proposal <- function(proposal, obj) {
  #' Evaluate QC proposal before execution. Auto-relax if too aggressive.
  #'
  #' Guardrails:
  #'   - Removal > 80% → BLOCK + auto-relax thresholds
  #'   - Removal > 50% → CAUTION
  #'
  #' @param proposal List from propose_qc_thresholds()
  #' @param obj Pre-filter Seurat object
  #' @return List(verdict, adjusted, reason, adjusted_thresholds)

  t <- proposal$thresholds
  n_before <- ncol(obj)

  # Check required columns exist
  required_cols <- c("nFeature_RNA", "nCount_RNA", "percent.mt")
  missing_cols <- required_cols[!required_cols %in% colnames(obj@meta.data)]
  if (length(missing_cols) > 0) {
    return(list(
      verdict = "PROCEED",
      adjusted = FALSE,
      reason = sprintf("Missing QC columns: %s. Skipping guardrail.", paste(missing_cols, collapse = ", "))
    ))
  }

  keep <- obj$nFeature_RNA > t$nFeature_RNA_min &
          obj$nFeature_RNA < t$nFeature_RNA_max &
          obj$nCount_RNA > t$nCount_RNA_min &
          obj$percent.mt < t$percent_mt_max

  n_after <- sum(keep, na.rm = TRUE)
  pct_removed <- (1 - n_after / n_before) * 100

  if (pct_removed > 80) {
    adjusted_t <- t
    adjusted_t$nFeature_RNA_min <- max(100, round(adjusted_t$nFeature_RNA_min * 0.5))
    adjusted_t$percent_mt_max <- min(50, round(adjusted_t$percent_mt_max * 1.5, 1))

    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf(
        "Proposed thresholds would remove %.1f%% of cells (>80%%). Auto-relaxing: nFeature_RNA_min=%d, percent_mt_max=%.1f%%.",
        pct_removed, adjusted_t$nFeature_RNA_min, adjusted_t$percent_mt_max
      ),
      adjusted_thresholds = adjusted_t
    ))
  } else if (pct_removed > 50) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Proposed thresholds would remove %.1f%% of cells (>50%%). Review carefully.", pct_removed)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Apply thresholds
# ---------------------------------------------------------------------------

execute_qc_filter <- function(obj, thresholds) {
  #' Apply QC thresholds and return filtered object.
  #'
  #' @param obj Seurat object [Raw]
  #' @param thresholds List from propose_qc_thresholds()
  #' @return Seurat object [Filtered]

  t <- thresholds$thresholds

  obj_filtered <- subset(obj,
    nFeature_RNA > t$nFeature_RNA_min &
    nFeature_RNA < t$nFeature_RNA_max &
    nCount_RNA > t$nCount_RNA_min &
    percent.mt < t$percent_mt_max
  )

  obj_filtered@misc$pipeline_state <- "Filtered"
  obj_filtered@misc$qc_thresholds <- t

  return(obj_filtered)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT — Summarize results
# ---------------------------------------------------------------------------

report_qc <- function(obj_before, obj_after, thresholds) {
  #' Generate QC report with pass/fail assessment.
  #'
  #' @param obj_before Pre-filter object
  #' @param obj_after Post-filter object
  #' @param thresholds Applied thresholds
  #' @return Report list

  n_before <- ncol(obj_before)
  n_after <- ncol(obj_after)
  pct_removed <- (1 - n_after / n_before) * 100

  status <- if (pct_removed > 60) {
    "WARNING"
  } else if (pct_removed > 30) {
    "CAUTION"
  } else {
    "PASS"
  }

  list(
    step = "QC Filtering",
    status = status,
    cells_before = n_before,
    cells_after = n_after,
    pct_removed = round(pct_removed, 1),
    thresholds_applied = thresholds$thresholds,
    recommendation = if (status == "WARNING") {
      ">60% cells removed. Consider relaxing thresholds, especially nFeature_RNA_min or percent_mt_max."
    } else if (status == "CAUTION") {
      "30-60% cells removed. Review QC plots; may be acceptable for low-quality samples."
    } else {
      "Cell retention looks good. Proceed to Doublet Detection."
    },
    next_step = "Step 3: Doublet Detection"
  )
}


# ---------------------------------------------------------------------------
# Convenience: full step wrapper
# ---------------------------------------------------------------------------

run_qc_step <- function(obj, thresholds = NULL, auto = FALSE, use_llm = TRUE, prev_reports = list()) {
  #' Run complete QC step: propose, optionally confirm, execute, report.
  #'
  #' @param obj Seurat object [Raw]
  #' @param thresholds If NULL, auto-propose. If provided, use directly.
  #' @param auto If TRUE, skip proposal display.
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @return List(obj = [Filtered], report = report, proposal, llm_report)

  # State validation
  expected_states <- c("Raw")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for QC step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_qc_thresholds(obj)

  # Evaluate phase: guardrail on removal percentage
  evaluation <- evaluate_qc_proposal(proposal, obj)
  if (evaluation$adjusted) {
    message("GUARDRAIL: ", evaluation$reason)
    proposal$thresholds <- evaluation$adjusted_thresholds
    # Re-evaluate after adjustment
    evaluation2 <- evaluate_qc_proposal(proposal, obj)
    if (evaluation2$verdict == "BLOCK") {
      stop("Even after auto-relaxation, QC thresholds would remove >80% of cells. Manual intervention required.")
    }
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(thresholds)) {
    thresholds <- proposal
  }

  obj_filtered <- execute_qc_filter(obj, thresholds)
  qc_report <- report_qc(obj, obj_filtered, thresholds)

  # Print proposal for user review
  if (!auto) {
    message("\n=== QC Proposal ===")
    message(sprintf("nFeature_RNA: %d - %d",
                    thresholds$thresholds$nFeature_RNA_min,
                    thresholds$thresholds$nFeature_RNA_max))
    message(sprintf("nCount_RNA_min: %d", thresholds$thresholds$nCount_RNA_min))
    message(sprintf("percent.mt_max: %.1f%%", thresholds$thresholds$percent_mt_max))
    message(sprintf("\nJustification: %s", thresholds$justification$MT))
    message(sprintf("\nEstimated removal: ~%.1f%% cells", qc_report$pct_removed))
  }

  # LLM enhancement
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("qc", obj, proposal, qc_report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj_filtered, report = qc_report, proposal = proposal, llm_report = llm_report)
}
