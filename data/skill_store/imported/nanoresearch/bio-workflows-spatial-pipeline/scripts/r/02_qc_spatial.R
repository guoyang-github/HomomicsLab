#' Step 2: QC Decision — Spatial Transcriptomics Pipeline (R)
#'
#' Reference: Seurat 5.0+
#'
#' Input State:  [Raw]
#' Output State: [Filtered]
#'
#' Spatial-specific: estimates tissue coverage from spots with counts > 0.

library(Seurat)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE
# ---------------------------------------------------------------------------

propose_qc_thresholds <- function(obj) {
  #' Analyze QC distributions and propose data-driven thresholds.
  #'
  #' @param obj Seurat object [Raw]
  #' @return Recommendation list

  md <- obj@meta.data

  # Ensure MT% is computed
  if (!("percent.mt" %in% colnames(md))) {
    obj[["percent.mt"]] <- PercentageFeatureSet(obj, pattern = "^MT-")
    md <- obj@meta.data
  }

  # Dynamically resolve feature/count column names (e.g., nFeature_Spatial vs nFeature_Xenium)
  assay_name <- DefaultAssay(obj)
  feat_col <- sprintf("nFeature_%s", assay_name)
  count_col <- sprintf("nCount_%s", assay_name)
  if (!(feat_col %in% colnames(md))) {
    stop(sprintf("QC column '%s' not found in meta.data. Available: %s",
                 feat_col, paste(colnames(md), collapse = ", ")))
  }

  n_genes <- md[[feat_col]]
  n_counts <- md[[count_col]]
  mt <- md$percent.mt
  mt_median <- median(mt, na.rm = TRUE)

  # Dynamic MT% threshold
  if (mt_median > 10) {
    mt_threshold <- min(30, mt_median + 2 * sd(mt, na.rm = TRUE))
    mt_reason <- sprintf(
      "MT%% median = %.1f%% (high, suggesting FFPE or tissue stress). Conservative threshold.",
      mt_median
    )
  } else if (mt_median > 5) {
    mt_threshold <- 20.0
    mt_reason <- sprintf(
      "MT%% median = %.1f%% (moderate). Standard threshold applies.",
      mt_median
    )
  } else {
    mt_threshold <- 15.0
    mt_reason <- sprintf(
      "MT%% median = %.1f%% (low, likely fresh frozen). Stringent threshold OK.",
      mt_median
    )
  }

  # Tissue coverage: spots with counts > 0
  tissue_coverage <- sum(n_counts > 0) / length(n_counts) * 100

  list(
    thresholds = list(
      min_counts = max(500, floor(quantile(n_counts, 0.01, na.rm = TRUE))),
      min_genes = 200,
      max_mt = round(mt_threshold, 1)
    ),
    diagnostics = list(
      n_spots = ncol(obj),
      n_genes_median = median(n_genes, na.rm = TRUE),
      n_counts_median = median(n_counts, na.rm = TRUE),
      mt_median = round(mt_median, 2),
      tissue_coverage_pct = round(tissue_coverage, 1)
    ),
    justification = list(
      counts = sprintf("Minimum %d total counts ensures sufficient depth.", max(500, floor(quantile(n_counts, 0.01, na.rm = TRUE)))),
      genes = "Minimum 200 genes per spot captures tissue diversity.",
      mt = mt_reason
    )
  )
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_qc_proposal <- function(proposal, obj) {
  #' Evaluate spatial QC proposal before execution.
  #'
  #' Guardrails:
  #'   - Removal > 80% → BLOCK + auto-relax thresholds
  #'   - Removal > 50% → CAUTION
  #'   - Tissue coverage < 10% after filtering → BLOCK

  t <- proposal$thresholds
  n_before <- ncol(obj)

  assay_name <- DefaultAssay(obj)
  feat_col <- sprintf("nFeature_%s", assay_name)
  count_col <- sprintf("nCount_%s", assay_name)

  if (!(feat_col %in% colnames(obj@meta.data))) {
    return(list(verdict = "PROCEED", adjusted = FALSE,
                reason = sprintf("QC column '%s' not found. Skipping guardrail.", feat_col)))
  }

  keep <- obj@meta.data[[feat_col]] >= t$min_genes &
          obj@meta.data[[count_col]] >= t$min_counts &
          obj$percent.mt < t$max_mt

  n_after <- sum(keep, na.rm = TRUE)
  pct_removed <- (1 - n_after / n_before) * 100

  if (pct_removed > 80) {
    adjusted_t <- t
    adjusted_t$min_genes <- max(50, round(adjusted_t$min_genes * 0.5))
    adjusted_t$max_mt <- min(50, round(adjusted_t$max_mt * 1.5, 1))
    return(list(
      verdict = "BLOCK",
      adjusted = TRUE,
      reason = sprintf(
        "Proposed thresholds would remove %.1f%% of spots (>80%%). Auto-relaxing: min_genes=%d, max_mt=%.1f%%.",
        pct_removed, adjusted_t$min_genes, adjusted_t$max_mt
      ),
      adjusted_thresholds = adjusted_t
    ))
  } else if (pct_removed > 50) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Proposed thresholds would remove %.1f%% of spots (>50%%). Review carefully.", pct_removed)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE
# ---------------------------------------------------------------------------

execute_qc_filter <- function(obj, thresholds) {
  #' Apply QC thresholds and return filtered object.
  #'
  #' @param obj Seurat object [Raw]
  #' @param thresholds Threshold list from propose_qc_thresholds()
  #' @return Seurat object [Filtered]

  t <- thresholds$thresholds

  feat_col <- sprintf("nFeature_%s", DefaultAssay(obj))
  count_col <- sprintf("nCount_%s", DefaultAssay(obj))

  md <- obj@meta.data
  keep <- md[[feat_col]] >= t$min_genes &
          md[[count_col]] >= t$min_counts &
          md$percent.mt < t$max_mt

  obj_filtered <- obj[, which(keep)]

  obj_filtered@misc$pipeline_state <- "Filtered"
  obj_filtered@misc$qc_thresholds <- t

  return(obj_filtered)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_qc <- function(obj_before, obj_after, thresholds) {
  #' Generate QC report with pass/fail assessment.
  #'
  #' @param obj_before Seurat object before QC
  #' @param obj_after Seurat object after QC
  #' @param thresholds Threshold list
  #' @return Report list

  n_before <- ncol(obj_before)
  n_after <- ncol(obj_after)
  pct_removed <- (1 - n_after / n_before) * 100

  status <- if (pct_removed > 50) {
    "WARNING"
  } else if (pct_removed > 25) {
    "CAUTION"
  } else {
    "PASS"
  }

  list(
    step = "QC Filtering",
    status = status,
    spots_before = n_before,
    spots_after = n_after,
    pct_removed = round(pct_removed, 1),
    thresholds_applied = thresholds$thresholds,
    recommendation = if (status == "WARNING") {
      ">50% spots removed. Check if tissue-edge spots were over-filtered."
    } else if (status == "CAUTION") {
      "25-50% spots removed. Review spatial QC plots for artifacts."
    } else {
      "Spot retention looks good. Proceed to Normalization."
    },
    next_step = "Step 3: Normalization + HVG"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_qc_step <- function(obj, thresholds = NULL, auto = FALSE,
                          use_llm = TRUE, prev_reports = list()) {
  #' Run complete QC step: propose, optionally confirm, execute, report.
  #'
  #' @param obj Seurat object [Raw]
  #' @param thresholds Override thresholds (NULL = auto-propose)
  #' @param auto Skip proposal display
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @param prev_reports Previous step reports for cross-step analysis.
  #' @return List(obj, report, proposal, llm_report)

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
    evaluation2 <- evaluate_qc_proposal(proposal, obj)
    if (evaluation2$verdict == "BLOCK") {
      stop("Even after auto-relaxation, QC thresholds would remove >80% of spots. Manual intervention required.")
    }
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (is.null(thresholds)) {
    thresholds <- proposal
  }

  obj_filtered <- execute_qc_filter(obj, thresholds)
  qc_report <- report_qc(obj, obj_filtered, thresholds)

  if (!auto) {
    message("\n=== QC Proposal ===")
    message(sprintf("min_counts: %d", thresholds$thresholds$min_counts))
    message(sprintf("min_genes: %d", thresholds$thresholds$min_genes))
    message(sprintf("max_mt: %.1f%%", thresholds$thresholds$max_mt))
    message(sprintf("\nJustification: %s", thresholds$justification$mt))
    message(sprintf("\nEstimated removal: ~%.1f%% spots", qc_report$pct_removed))
  }

  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("qc", obj_filtered, proposal, qc_report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj_filtered, report = qc_report, proposal = proposal, llm_report = llm_report)
}
