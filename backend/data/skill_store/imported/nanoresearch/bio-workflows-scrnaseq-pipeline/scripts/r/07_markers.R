#' Step 7: Marker Detection — Single-Cell RNA-seq Pipeline (R)
#'
#' Reference: Seurat 5.0+
#'
#' Input State:  [Clustered] + [UMAP]
#' Output State: [Clustered] + markers

library(Seurat)
library(dplyr)

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x


# ---------------------------------------------------------------------------
# PHASE 1: PROPOSE — Recommend marker detection parameters
# ---------------------------------------------------------------------------

propose_marker_params <- function(obj) {
  #' Propose marker detection parameters.

  n_clusters <- length(unique(Idents(obj)))

  list(
    recommendation = list(
      only.pos = TRUE,
      min.pct = 0.25,
      logfc.threshold = 0.25,
      test.use = "wilcox"
    ),
    diagnostics = list(
      n_clusters = n_clusters
    ),
    justification = paste(
      "Wilcoxon test (default) is robust for most datasets.",
      "min.pct=0.25 ensures markers are expressed in at least 25% of cells in the cluster.",
      "logfc.threshold=0.25 filters for biologically meaningful differences."
    ),
    alternatives = list(
      MAST = "Use for datasets with strong depth variation (e.g. Smart-seq2).",
      DESeq2 = "Use for pseudo-bulk differential expression.",
      LR = "Use for conserved markers across samples (requires 'sample' column)."
    )
  )
}


# ---------------------------------------------------------------------------
# PHASE 1.5: EVALUATE — Guardrail layer
# ---------------------------------------------------------------------------

evaluate_marker_proposal <- function(proposal, obj) {
  #' Evaluate marker detection proposal before execution.
  #'
  #' Guardrails:
  #'   - n_clusters < 2 → BLOCK (need at least 2 clusters)
  #'   - n_clusters > 100 → CAUTION (very high, may be slow)

  n_clusters <- proposal$diagnostics$n_clusters

  if (n_clusters < 2) {
    return(list(
      verdict = "BLOCK",
      adjusted = FALSE,
      reason = sprintf("Only %d cluster found. Marker detection requires at least 2 clusters.", n_clusters)
    ))
  }

  if (n_clusters > 100) {
    return(list(
      verdict = "CAUTION",
      adjusted = FALSE,
      reason = sprintf("Very high cluster count (%d). Marker detection may be slow.", n_clusters)
    ))
  }

  list(verdict = "PROCEED", adjusted = FALSE)
}


# ---------------------------------------------------------------------------
# PHASE 2: EXECUTE — FindAllMarkers
# ---------------------------------------------------------------------------

execute_marker_detection <- function(obj, only.pos = TRUE, min.pct = 0.25,
                                      logfc.threshold = 0.25, test.use = "wilcox",
                                      ...) {
  #' Run marker detection across all clusters.

  # SCT assay compatibility: switch to RNA for differential expression
  original_assay <- DefaultAssay(obj)
  if (original_assay == "SCT" && "RNA" %in% names(obj@assays)) {
    DefaultAssay(obj) <- "RNA"
    if (length(Layers(obj[["RNA"]])) > 1) {
      obj[["RNA"]] <- JoinLayers(obj[["RNA"]])
    }
    markers <- FindAllMarkers(obj,
                              only.pos = only.pos,
                              min.pct = min.pct,
                              logfc.threshold = logfc.threshold,
                              test.use = test.use,
                              verbose = FALSE,
                              ...)
    DefaultAssay(obj) <- original_assay
  } else {
    markers <- FindAllMarkers(obj,
                              only.pos = only.pos,
                              min.pct = min.pct,
                              logfc.threshold = logfc.threshold,
                              test.use = test.use,
                              verbose = FALSE,
                              ...)
  }

  obj@misc$markers <- markers
  obj@misc$pipeline_state <- "Clustered"

  message(sprintf("Marker detection complete: %d markers found", nrow(markers)))

  return(obj)
}


export_markers <- function(obj, output_dir = ".") {
  #' Export markers to CSV files.

  markers <- obj@misc$markers

  if (is.null(markers)) {
    warning("No markers found. Run execute_marker_detection first.")
    return(NULL)
  }

  # All markers
  write.csv(markers, file.path(output_dir, "all_markers.csv"), row.names = FALSE)

  # Top 10 per cluster
  top10 <- markers %>%
    group_by(cluster) %>%
    slice_max(n = 10, order_by = avg_log2FC)
  write.csv(top10, file.path(output_dir, "top10_markers.csv"), row.names = FALSE)

  # Top 3 per cluster (quick reference)
  top3 <- markers %>%
    group_by(cluster) %>%
    slice_max(n = 3, order_by = avg_log2FC)

  message(sprintf("Markers exported to %s/all_markers.csv", output_dir))

  return(list(all = markers, top10 = top10, top3 = top3))
}


# ---------------------------------------------------------------------------
# PHASE 3: REPORT
# ---------------------------------------------------------------------------

report_markers <- function(obj) {
  #' Report marker detection results.

  markers <- obj@misc$markers

  if (is.null(markers) || nrow(markers) == 0) {
    return(list(
      step = "Marker Detection",
      status = "FAIL",
      n_markers = 0,
      recommendation = "No markers found. Check clustering resolution or filtering thresholds.",
      next_step = "Revisit Step 6: Clustering"
    ))
  }

  n_markers <- nrow(markers)
  n_clusters <- length(unique(markers$cluster))
  avg_per_cluster <- n_markers / n_clusters

  status <- if (avg_per_cluster < 10) {
    "CAUTION"
  } else {
    "PASS"
  }

  list(
    step = "Marker Detection",
    status = status,
    n_markers = n_markers,
    n_clusters = n_clusters,
    avg_markers_per_cluster = round(avg_per_cluster, 1),
    recommendation = if (status == "CAUTION") {
      "Low marker count per cluster. Consider lower logfc.threshold or check cluster quality."
    } else {
      "Good marker yield. Proceed to cell type annotation."
    },
    next_step = "Step 8: Cell Type Annotation"
  )
}


# ---------------------------------------------------------------------------
# Full step wrapper
# ---------------------------------------------------------------------------

run_marker_step <- function(obj, resolution_col = NULL, auto = FALSE,
                             use_llm = TRUE, prev_reports = list(), ...) {
  #' Complete marker detection step.
  #'
  #' @param use_llm If TRUE, generate LLM diagnostic card.
  #' @param prev_reports Previous step reports for cross-step analysis.
  #' @return List(obj, report, proposal, llm_report)

  # State validation
  expected_states <- c("Clustered")
  current_state <- obj@misc$pipeline_state %||% "Raw"
  if (!current_state %in% expected_states) {
    warning(sprintf("Expected input state '%s' for marker step, got '%s'. Proceeding anyway.",
                    paste(expected_states, collapse = "/"), current_state))
  }

  if (!is.null(resolution_col)) {
    if (!(resolution_col %in% colnames(obj@meta.data))) {
      stop(sprintf("Resolution column '%s' not found in metadata. Available: %s",
                   resolution_col, paste(colnames(obj@meta.data), collapse = ", ")))
    }
    Idents(obj) <- resolution_col
  }

  proposal <- propose_marker_params(obj)

  # Evaluate phase: guardrail on cluster count
  evaluation <- evaluate_marker_proposal(proposal, obj)
  if (evaluation$verdict == "BLOCK") {
    stop(evaluation$reason)
  } else if (evaluation$verdict == "CAUTION") {
    message("CAUTION: ", evaluation$reason)
  }

  if (!auto) {
    message("\n=== Marker Detection Proposal ===")
    message(sprintf("Test: %s", proposal$recommendation$test.use))
    message(sprintf("min.pct: %.2f", proposal$recommendation$min.pct))
    message(sprintf("logfc.threshold: %.2f", proposal$recommendation$logfc.threshold))
  }

  obj <- execute_marker_detection(obj,
                                   only.pos = proposal$recommendation$only.pos,
                                   min.pct = proposal$recommendation$min.pct,
                                   logfc.threshold = proposal$recommendation$logfc.threshold,
                                   test.use = proposal$recommendation$test.use,
                                   ...)
  report <- report_markers(obj)

  # LLM enhancement
  llm_report <- NULL
  if (use_llm) {
    llm_report <- generate_llm_report("markers", obj, proposal, report, prev_reports)
    if (!auto) message(llm_report)
  }

  list(obj = obj, report = report, proposal = proposal, llm_report = llm_report)
}
