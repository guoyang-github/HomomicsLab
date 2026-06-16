#' Step 3: Doublet Detection — Single-Cell RNA-seq Pipeline (R)
#'
#' Reference: scDblFinder 1.14+, SingleCellExperiment
#'
#' Input State:  [Filtered]
#' Output State: [Clean]
#'
#' Expected doublet rate: ~2-10% for 10X data.
#' If >15%, check for sample aggregation artifacts.

library(Seurat)
library(SingleCellExperiment)
library(scDblFinder)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Estimate expected doublet rate
# ---------------------------------------------------------------------------

propose_doublet_params <- function(obj) {
  #' Propose doublet detection parameters based on cell count.
  #'
  #' @param obj Seurat object [Filtered]
  #' @return List with parameters and expectations

  n_cells <- ncol(obj)

  # 10X expected doublet rate approximation
  # Based on 10X documentation: ~0.8% per 1,000 cells
  expected_rate <- min(0.15, 0.008 * (n_cells / 1000))

  list(
    params = list(
      n_cells = n_cells,
      expected_doublet_rate = round(expected_rate * 100, 1)
    ),
    diagnostics = list(
      n_cells = n_cells,
      note = if (n_cells > 20000) {
        "Large dataset (>20k cells). Consider running per-sample if multi-sample."
      } else {
        "Standard size. Single-pass doublet detection is appropriate."
      }
    ),
    justification = sprintf(
      "Expected doublet rate ~%.1f%% for %d cells (10X approximation). scDblFinder will adaptively estimate.",
      expected_rate * 100, n_cells
    )
  )
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_doublet_proposal <- function(proposal, obj) {
  #' Evaluate doublet proposal before execution.
  #'
  #' Guardrails:
  #'   - Expected doublet rate > 20% → CAUTION (possible sample aggregation)
  #'   - n_cells > 50000 → CAUTION (consider per-sample detection)

  expected_rate <- proposal$params$expected_doublet_rate
  n_cells <- proposal$params$n_cells

  if (expected_rate > 20) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf(
        "Expected doublet rate %.1f%% is very high (>20%%). Possible sample aggregation or barcoding issue. Consider per-sample detection.",
        expected_rate
      )
    ))
  }

  if (n_cells > 50000) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Large dataset (%d cells). Consider per-sample doublet detection.", n_cells)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — Run scDblFinder
# ---------------------------------------------------------------------------

execute_doublet_detection <- function(obj, sample_col = NULL) {
  #' Run scDblFinder and add labels to Seurat object.
  #'
  #' @param obj Seurat object [Filtered]
  #' @param sample_col Column name for sample ID (run per-sample if provided)
  #' @return Seurat object with doublet_class and doublet_score

  sce <- as.SingleCellExperiment(obj)

  if (!is.null(sample_col) && sample_col %in% colnames(obj@meta.data)) {
    sce$sample <- obj@meta.data[[sample_col]]
    sce <- scDblFinder(sce, samples = "sample")
  } else {
    sce <- scDblFinder(sce)
  }

  obj$doublet_class <- sce$scDblFinder.class
  obj$doublet_score <- sce$scDblFinder.score

  return(obj)
}


remove_doublets <- function(obj) {
  #' Remove predicted doublets and tag state.
  #'
  #' @param obj Seurat object with doublet_class column
  #' @return Seurat object [Clean]

  n_before <- ncol(obj)
  obj_clean <- subset(obj, doublet_class == "singlet")
  n_after <- ncol(obj_clean)

  obj_clean@misc$pipeline_state <- "Clean"
  obj_clean@misc$n_doublets_removed <- n_before - n_after

  message(sprintf("Removed %d doublets (%.1f%%)", n_before - n_after,
                  (n_before - n_after) / n_before * 100))
  message(sprintf("Cells after doublet removal: %d", n_after))

  return(obj_clean)
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_doublets <- function(obj_before, obj_after) {
  #' Generate doublet detection report.
  #'
  #' @param obj_before Object with doublet labels
  #' @param obj_after Clean object after removal
  #' @return Report list

  n_before <- ncol(obj_before)
  n_doublets <- sum(obj_before$doublet_class == "doublet", na.rm = TRUE)
  doublet_rate <- n_doublets / n_before * 100

  status <- if (doublet_rate > 15) {
    "WARNING"
  } else if (doublet_rate > 10) {
    "CAUTION"
  } else if (doublet_rate < 1) {
    "CAUTION"
  } else {
    "PASS"
  }

  list(
    step = "Doublet Detection",
    status = status,
    cells_before = n_before,
    doublets_detected = n_doublets,
    doublet_rate = round(doublet_rate, 1),
    cells_after = ncol(obj_after),
    recommendation = if (status == "WARNING") {
      "Doublet rate >15%. Possible sample aggregation. Consider per-sample detection or re-check data loading."
    } else if (status == "CAUTION" && doublet_rate > 10) {
      "Doublet rate elevated. Acceptable for high-density runs; review if unexpected."
    } else if (status == "CAUTION" && doublet_rate < 1) {
      "Doublet rate unusually low. May indicate over-filtering in QC step."
    } else {
      "Doublet rate within expected range. Proceed to Normalization."
    },
    next_step = "Step 4: Normalization + HVG"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_doublet_step <- function(obj, sample_col = NULL, auto = FALSE, use_llm = TRUE, prev_reports = list()) {
  #' Complete doublet detection step.
  #'
  #' @param obj Seurat object [Filtered]
  #' @param sample_col Sample column for per-sample detection
  #' @param auto Skip proposal display
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @return List(obj = [Clean], report = report, proposal, llm_report)

  # State validation
  expected_states <- c("Filtered")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for doublet step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  proposal <- propose_doublet_params(obj)

  # Evaluate phase: guardrail on expected doublet rate
  evaluation <- evaluate_doublet_proposal(proposal, obj)
  if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (!auto) {
    message("\n=== Doublet Detection Proposal ===")
    message(sprintf("Cells: %d", proposal$params$n_cells))
    message(sprintf("Expected doublet rate: ~%.1f%%", proposal$params$expected_doublet_rate))
    message(sprintf("Note: %s", proposal$diagnostics$note))
  }

  obj <- execute_doublet_detection(obj, sample_col = sample_col)
  obj_clean <- remove_doublets(obj)
  report <- report_doublets(obj, obj_clean)

  # LLM enhancement
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("doublet", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj_clean, report = report, proposal = proposal, llm_report = llm_report)
}
