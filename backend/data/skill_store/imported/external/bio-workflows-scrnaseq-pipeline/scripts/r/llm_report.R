#' LLM Diagnostic Report Generator — Single-Cell RNA-seq Pipeline (R)
#'
#' Generates structured markdown "diagnostic cards" that the LLM agent consumes
#' to provide deep, contextual advice at each pipeline step.
#'
#' Design: Deterministic rule engine proposes + executes; LLM layer interprets
#' and contextualizes. No external API calls — the agent itself is the LLM.
#'
#' Usage:
#'   llm_report <- generate_llm_report("qc", obj, proposal, report, prev_reports)
#'   message(llm_report)  # Agent reads this and generates analysis

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x

# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

generate_llm_report <- function(step_name, obj, proposal, report, prev_reports = list()) {
  #' Generate a markdown diagnostic card for a pipeline step.
  #'
  #' @param step_name One of: qc, doublet, normalize, integration, cluster, markers, annotation
  #' @param obj Seurat object (current state)
  #' @param proposal Proposal list from propose_*()
  #' @param report Report list from report_*()
  #' @param prev_reports Named list of previous step reports (for cross-step analysis)
  #' @return Character string containing markdown diagnostic card

  card <- switch(step_name,
    "qc"           = .llm_report_qc(obj, proposal, report, prev_reports),
    "doublet"      = .llm_report_doublet(obj, proposal, report, prev_reports),
    "normalize"    = .llm_report_normalize(obj, proposal, report, prev_reports),
    "integration"  = .llm_report_integration(obj, proposal, report, prev_reports),
    "cluster"      = .llm_report_cluster(obj, proposal, report, prev_reports),
    "markers"      = .llm_report_markers(obj, proposal, report, prev_reports),
    "annotation"   = .llm_report_annotation(obj, proposal, report, prev_reports),
    sprintf("## Unknown Step: %s\n\nNo LLM diagnostic template available.", step_name)
  )

  return(card)
}


# ---------------------------------------------------------------------------
# Helpers: cross-step linkage and formatting
# ---------------------------------------------------------------------------

.llm_cross_step <- function(prev_reports, step_names) {
  #' Extract relevant context from previous step reports.
  lines <- c()
  for (sn in step_names) {
    if (sn %in% names(prev_reports)) {
      r <- prev_reports[[sn]]
      status <- r$status %||% "N/A"
      lines <- c(lines, sprintf("- **%s**: status=%s", sn, status))
      if (!is.null(r$pct_removed)) {
        lines <- c(lines, sprintf("  - Cell removal: %.1f%%", r$pct_removed))
      }
      if (!is.null(r$doublet_rate)) {
        lines <- c(lines, sprintf("  - Doublet rate: %.1f%%", r$doublet_rate))
      }
      if (!is.null(r$n_hvg)) {
        lines <- c(lines, sprintf("  - HVG count: %d", r$n_hvg))
      }
    }
  }
  if (length(lines) == 0) return("No previous step data available.")
  paste(lines, collapse = "\n")
}


.llm_fmt_list <- function(lst, indent = "") {
  #' Format a named list as markdown bullet points.
  lines <- c()
  for (nm in names(lst)) {
    val <- lst[[nm]]
    if (is.list(val) && length(val) > 0) {
      lines <- c(lines, sprintf("%s- **%s**:", indent, nm))
      lines <- c(lines, .llm_fmt_list(val, paste0(indent, "  ")))
    } else if (length(val) == 1) {
      lines <- c(lines, sprintf("%s- **%s**: %s", indent, nm, as.character(val)))
    }
  }
  paste(lines, collapse = "\n")
}


# ---------------------------------------------------------------------------
# D2: QC
# ---------------------------------------------------------------------------

.llm_report_qc <- function(obj, proposal, report, prev_reports) {
  t <- proposal$thresholds
  d <- proposal$diagnostics
  j <- proposal$justification

  card <- sprintf("
## [LLM Diagnostic Card] Step 2: QC Filtering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Initial cells | %d |
| nFeature_RNA median | %d |
| nFeature_RNA 99th pct | %d |
| nCount_RNA median | %d |
| MT%% median | %.2f%% |
| MT%% 95th pct | %.2f%% |

### Rule Proposal
| Threshold | Value | Rationale |
|-----------|-------|-----------|
| nFeature_RNA min | %d | %s |
| nFeature_RNA max | %d | Captures >95%% of cells |
| nCount_RNA min | %d | %s |
| MT%% max | %.1f%% | %s |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Cells after filter | %d |
| Cells removed | %.1f%% |

### Cross-Step Context
%s

### LLM Analysis Task
> Analyze this QC profile and assess whether the proposed thresholds are
> appropriate for downstream analysis. Consider:
> 1. Is the MT%% distribution consistent with the expected tissue type?
> 2. Is the removal rate (%s) reasonable, or does it suggest over/under-filtering?
> 3. Are there any red flags (e.g., bimodal nFeature distribution, extreme MT%% outliers)
>    that warrant special attention?
> 4. Should any thresholds be adjusted before proceeding?
",
    d$n_cells,
    d$nfeature_median, d$nfeature_q99,
    d$ncount_median, d$mt_median, d$mt_q95,
    t$nFeature_RNA_min, j$nFeature,
    t$nFeature_RNA_max,
    t$nCount_RNA_min, j$nCount,
    t$percent_mt_max, j$MT,
    report$status, report$cells_after, report$pct_removed,
    .llm_cross_step(prev_reports, c("load")),
    report$pct_removed
  )

  return(trimws(card))
}


# ---------------------------------------------------------------------------
# D3: Doublet
# ---------------------------------------------------------------------------

.llm_report_doublet <- function(obj, proposal, report, prev_reports) {
  card <- sprintf("
## [LLM Diagnostic Card] Step 3: Doublet Detection

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells input | %d |
| Expected doublet rate | ~%.1f%% |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Doublets detected | %d (%.1f%%) |
| Cells after removal | %d |

### Cross-Step Context
%s

### LLM Analysis Task
> Evaluate the doublet detection results:
> 1. Is the detected doublet rate (%.1f%%) consistent with the expected rate (%.1f%%)?
> 2. If the rate is abnormally high (>15%%) or low (<1%%), what could explain this?
>    Consider whether QC filtering in the previous step may have pre-removed doublets.
> 3. For multi-sample data: should doublet detection have been run per-sample?
> 4. Is it safe to proceed to normalization?
",
    proposal$params$n_cells,
    proposal$params$expected_doublet_rate,
    report$status, report$doublets_detected, report$doublet_rate,
    report$cells_after,
    .llm_cross_step(prev_reports, c("qc")),
    report$doublet_rate, proposal$params$expected_doublet_rate
  )

  return(trimws(card))
}


# ---------------------------------------------------------------------------
# D4: Normalization
# ---------------------------------------------------------------------------

.llm_report_normalize <- function(obj, proposal, report, prev_reports) {
  card <- sprintf("
## [LLM Diagnostic Card] Step 4: Normalization + HVG

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells | %d |
| Genes | %d |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | %s | %s |
| Vars to regress | %s | Remove technical variance |
| Target HVGs | %d | Standard range |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| HVGs selected | %d |

### Cross-Step Context
%s

### LLM Analysis Task
> Assess the normalization setup:
> 1. Is %s appropriate for this dataset size (%d cells)?
> 2. Is the HVG count (%d) within the optimal range (1500-3000)?
> 3. Should additional variables be regressed (e.g., cell cycle, ribosomal %%)?
> 4. For SCTransform: is vst.flavor='v2' being used (recommended for UMI data)?
",
    proposal$diagnostics$n_cells,
    proposal$diagnostics$n_genes,
    proposal$recommendation$method,
    proposal$justification,
    paste(proposal$recommendation$vars_to_regress, collapse = ", "),
    proposal$recommendation$n_hvg_target,
    report$status, report$n_hvg,
    .llm_cross_step(prev_reports, c("qc", "doublet")),
    proposal$recommendation$method, proposal$diagnostics$n_cells,
    report$n_hvg
  )

  return(trimws(card))
}


# ---------------------------------------------------------------------------
# D5: Integration (Critical)
# ---------------------------------------------------------------------------

.llm_report_integration <- function(obj, proposal, report, prev_reports) {
  d <- proposal$diagnostics

  card <- sprintf("
## [LLM Diagnostic Card] Step 5: Batch Integration Decision [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Batches detected | %d |
| Total cells | %d |
| Batch mixing score | %s |

### Rule Proposal
| Parameter | Value |
|-----------|-------|
| Integrate? | %s |
| Method | %s |
| Reason | %s |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Method applied | %s |

### Cross-Step Context
%s

### LLM Analysis Task [DECISION POINT]
> This is a critical decision that affects all downstream analysis.
> Evaluate the integration recommendation:
> 1. Is the batch mixing score (%s) interpreted correctly?
>    - <0.3: batches well-mixed, skip integration
>    - 0.3-0.6: moderate effect, integrate
>    - >0.6: strong effect, integrate aggressively
> 2. Is the recommended method (%s) appropriate for %d batches and %d cells?
>    - Harmony: best for 2-5 batches, <50k cells
>    - RPCA: better for >5 batches or large datasets
>    - CCA: for reference-based mapping
> 3. If integration is SKIPPED: are we confident batches are truly well-mixed,
>    or could biological variation be confounded with batch?
> 4. After integration (if applied): should we verify biological signals are
>    preserved by checking known marker expression?
",
    d$n_batches, d$n_cells,
    if (!is.null(d$batch_mixing_score)) sprintf("%.3f", d$batch_mixing_score) else "N/A (single batch)",
    if (proposal$recommendation$integrate) "YES" else "NO",
    proposal$recommendation$method %||% "N/A",
    proposal$justification,
    report$status, report$method %||% "None",
    .llm_cross_step(prev_reports, c("qc", "doublet", "normalize")),
    if (!is.null(d$batch_mixing_score)) sprintf("%.3f", d$batch_mixing_score) else "N/A",
    proposal$recommendation$method %||% "N/A", d$n_batches, d$n_cells
  )

  return(trimws(card))
}


# ---------------------------------------------------------------------------
# D6: Clustering
# ---------------------------------------------------------------------------

.llm_report_cluster <- function(obj, proposal, report, prev_reports) {
  card <- sprintf("
## [LLM Diagnostic Card] Step 6: Clustering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells | %d |
| PCs computed | %d |
| PCs used | %d |
| Reduction | %s |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Resolutions | %s | %s |
| Default resolution | %.1f | Based on dataset size |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Clusters (default) | %d |

### LLM Analysis Task
> Evaluate the clustering results:
> 1. Is %d clusters at resolution %.1f reasonable for %d cells?
>    - <5 clusters: may need higher resolution
>    - >50 clusters: likely over-clustering
> 2. Are the tested resolutions (%s) sufficient to capture both broad and fine structure?
> 3. Should we consider running additional resolutions (e.g., 0.1 for very broad types, 1.5-2.0 for subtypes)?
> 4. If batch integration was applied: are clusters driven by biology or residual batch effects?
",
    proposal$diagnostics$n_cells,
    proposal$recommendation$npcs,
    proposal$recommendation$npcs_use,
    proposal$recommendation$reduction %||% "pca",
    paste(proposal$recommendation$resolutions, collapse = ", "),
    proposal$justification,
    proposal$recommendation$default_resolution,
    report$status, report$n_clusters,
    report$n_clusters, report$default_resolution, proposal$diagnostics$n_cells,
    paste(proposal$recommendation$resolutions, collapse = ", ")
  )

  return(trimws(card))
}


# ---------------------------------------------------------------------------
# D7: Markers
# ---------------------------------------------------------------------------

.llm_report_markers <- function(obj, proposal, report, prev_reports) {
  card <- sprintf("
## [LLM Diagnostic Card] Step 7: Marker Detection

### Data Snapshot
| Metric | Value |
|--------|-------|
| Clusters | %d |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Test | %s | Robust for most data |
| min.pct | %.2f | Marker expressed in >=25%% of cluster |
| logFC threshold | %.2f | Biologically meaningful difference |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Total markers | %d |
| Avg per cluster | %.1f |

### Cross-Step Context
%s

### LLM Analysis Task
> Evaluate marker quality:
> 1. Is %.1f markers per cluster sufficient for annotation?
>    - <5: likely insufficient, may need lower thresholds
>    - 5-20: good range
>    - >50: may include noisy genes
> 2. Are the top markers per cluster showing expected cell-type-specific patterns?
> 3. Should conserved markers be computed if multi-sample?
> 4. Any clusters with very few or no markers? These may be low-quality or doublet clusters.
",
    proposal$diagnostics$n_clusters,
    proposal$recommendation$test.use,
    proposal$recommendation$min.pct,
    proposal$recommendation$logfc.threshold,
    report$status, report$n_markers, report$avg_markers_per_cluster,
    .llm_cross_step(prev_reports, c("qc", "doublet", "cluster")),
    report$avg_markers_per_cluster
  )

  return(trimws(card))
}


# ---------------------------------------------------------------------------
# D8: Annotation
# ---------------------------------------------------------------------------

.llm_report_annotation <- function(obj, proposal, report, prev_reports) {
  cell_type_summary <- if ("cell_type" %in% colnames(obj@meta.data)) {
    tbl <- sort(table(obj$cell_type), decreasing = TRUE)
    paste(sprintf("- %s: %d (%.1f%%)", names(tbl), tbl, 100 * tbl / sum(tbl)), collapse = "\n")
  } else {
    "No cell type assignments available."
  }

  card <- sprintf("
## [LLM Diagnostic Card] Step 8: Cell Type Annotation [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Cells | %d |
| Clusters | %d |
| Tissue hint | %s |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | %s | %s |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Cell types assigned | %d |
| Assignment rate | %.1f%% |

### Cell Type Distribution
%s

### Cross-Step Context
%s

### LLM Analysis Task [DECISION POINT]
> Evaluate the annotation quality:
> 1. Is %.1f%% assignment rate acceptable?
>    - >90%%: excellent
>    - 70-90%%: review unassigned clusters
>    - <70%%: method may be inappropriate for this tissue
> 2. Do the assigned cell types match the expected tissue composition (%s)?
> 3. Are there any suspicious annotations (e.g., all cells labeled as one type,
>    or obviously wrong assignments like neurons in blood)?
> 4. Should manual curation be performed for any clusters?
> 5. If annotation confidence is low: should we re-run with a different method
>    (e.g., SingleR instead of ScType, or manual with known markers)?
",
    proposal$diagnostics$n_cells,
    proposal$diagnostics$n_clusters,
    proposal$recommendation$tissue %||% "Not provided",
    proposal$recommendation$method,
    proposal$justification,
    report$status, report$n_cell_types, report$pct_assigned,
    cell_type_summary,
    .llm_cross_step(prev_reports, c("qc", "doublet", "cluster", "markers")),
    report$pct_assigned,
    proposal$recommendation$tissue %||% "unknown tissue"
  )

  return(trimws(card))
}


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

save_llm_reports <- function(llm_reports, output_dir) {
  #' Save all LLM diagnostic cards to markdown files.
  #'
  #' @param llm_reports Named list of markdown strings
  #' @param output_dir Directory to save reports

  llm_dir <- file.path(output_dir, "llm_reports")
  dir.create(llm_dir, showWarnings = FALSE, recursive = TRUE)

  for (step_name in names(llm_reports)) {
    if (!is.null(llm_reports[[step_name]])) {
      writeLines(llm_reports[[step_name]],
                 file.path(llm_dir, sprintf("%s_diagnostic.md", step_name)))
    }
  }

  # Also write a combined report
  combined <- paste(
    c("# LLM Diagnostic Reports — scRNA-seq Pipeline", "",
      sapply(names(llm_reports), function(sn) {
        if (!is.null(llm_reports[[sn]])) {
          c(paste0("---\n\n"), llm_reports[[sn]], "\n")
        }
      })),
    collapse = "\n"
  )
  writeLines(combined, file.path(llm_dir, "combined_report.md"))

  message(sprintf("LLM reports saved to: %s", llm_dir))
}
