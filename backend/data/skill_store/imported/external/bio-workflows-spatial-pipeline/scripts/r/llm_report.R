#' LLM Diagnostic Report Generator — Spatial Transcriptomics Pipeline (R)
#'
#' Generates structured markdown "diagnostic cards" that the LLM agent consumes
#' to provide deep, contextual advice at each pipeline step.
#'
#' Design: Deterministic rule engine proposes + executes; LLM layer interprets
#' and contextualizes. No external API calls — the agent itself is the LLM.

# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

`%||%` <- function(x, y) if (is.null(x)) y else x

# Simple pipe operator (no magrittr dependency)
`%>%` <- function(x, f) f(x)

generate_llm_report <- function(step_name, obj, proposal, report, prev_reports = list()) {
  card <- switch(step_name,
    "qc"          = .llm_report_qc(obj, proposal, report, prev_reports),
    "normalize"   = .llm_report_normalize(obj, proposal, report, prev_reports),
    "integration" = .llm_report_integration(obj, proposal, report, prev_reports),
    "cluster"     = .llm_report_cluster(obj, proposal, report, prev_reports),
    "spatial"     = .llm_report_spatial(obj, proposal, report, prev_reports),
    "domain"      = .llm_report_domain(obj, proposal, report, prev_reports),
    sprintf("## Unknown Step: %s\n\nNo LLM diagnostic template available.", step_name)
  )
  return(card)
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

.llm_cross_step <- function(prev_reports, step_names) {
  lines <- c()
  for (sn in step_names) {
    if (sn %in% names(prev_reports)) {
      r <- prev_reports[[sn]]
      status <- r$status %||% "N/A"
      lines <- c(lines, sprintf("- **%s**: status=%s", sn, status))
      if (!is.null(r$pct_removed)) {
        lines <- c(lines, sprintf("  - Spot removal: %.1f%%", r$pct_removed))
      }
      if (!is.null(r$n_hvg)) {
        lines <- c(lines, sprintf("  - HVG count: %d", r$n_hvg))
      }
    }
  }
  if (length(lines) == 0) return("No previous step data available.")
  paste(lines, collapse = "\n")
}


# ---------------------------------------------------------------------------
# D2: QC
# ---------------------------------------------------------------------------

.llm_report_qc <- function(obj, proposal, report, prev_reports) {
  t <- proposal$thresholds
  d <- proposal$diagnostics
  j <- proposal$justification

  sprintf("
## [LLM Diagnostic Card] Step 2: QC Filtering

### Data Snapshot
| Metric | Value |
|--------|-------|
| Initial spots | %d |
| nFeature median | %d |
| nCount median | %d |
| MT%% median | %.2f%% |

### Rule Proposal
| Threshold | Value | Rationale |
|-----------|-------|-----------|
| min_counts | %d | %s |
| min_genes | %d | %s |
| MT%% max | %.1f%% | %s |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Spots after filter | %d |
| Spots removed | %.1f%% |

### Cross-Step Context
%s

### LLM Analysis Task
> 1. Is the removal rate (%.1f%%) reasonable for spatial data?
>    - >40%%: check if tissue-edge spots were improperly removed
> 2. Do QC metrics show expected spatial patterns (center vs edge)?
> 3. Are image artifacts (folds, bubbles) driving low-quality spots?
",
    d$n_spots, d$n_genes_median, d$n_counts_median, d$mt_median,
    t$min_counts, j$counts,
    t$min_genes, j$genes,
    t$max_mt, j$mt,
    report$status, report$spots_after, report$pct_removed,
    .llm_cross_step(prev_reports, c("qc")),
    report$pct_removed
  ) %>% trimws()
}


# ---------------------------------------------------------------------------
# D3: Normalization
# ---------------------------------------------------------------------------

.llm_report_normalize <- function(obj, proposal, report, prev_reports) {
  sprintf("
## [LLM Diagnostic Card] Step 3: Normalization + HVG

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | %d |
| Genes | %d |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | %s | %s |
| Target HVGs | %d | Standard range |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| HVGs selected | %d |

### LLM Analysis Task
> 1. Is HVG count (%d) within optimal range (1500-3000)?
> 2. For spatial data: should spatially variable genes (SVGs) be prioritized over HVGs?
> 3. Are there obvious batch effects visible in UMAP (if multi-sample)?
",
    proposal$diagnostics$n_spots, proposal$diagnostics$n_genes,
    proposal$recommendation$method, proposal$justification,
    proposal$recommendation$n_hvg,
    report$status, report$n_hvg,
    report$n_hvg
  ) %>% trimws()
}


# ---------------------------------------------------------------------------
# D4: Integration
# ---------------------------------------------------------------------------

.llm_report_integration <- function(obj, proposal, report, prev_reports) {
  d <- proposal$diagnostics
  score_str <- if (!is.null(d$batch_mixing_score)) sprintf("%.3f", d$batch_mixing_score) else "N/A (single sample)"

  sprintf("
## [LLM Diagnostic Card] Step 4: Batch Integration [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Samples detected | %d |
| Total spots | %d |
| Batch mixing score | %s |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Method applied | %s |

### Cross-Step Context
%s

### LLM Analysis Task [DECISION POINT]
> 1. For spatial data: does integration preserve spatial coordinates and tissue structure?
> 2. If integration is SKIPPED: are samples truly comparable?
> 3. Should integration preserve spatial graphs per sample?
",
    d$n_samples, d$n_spots, score_str,
    report$status, report$method %||% "None",
    .llm_cross_step(prev_reports, c("qc", "normalize"))
  ) %>% trimws()
}


# ---------------------------------------------------------------------------
# D5: Clustering
# ---------------------------------------------------------------------------

.llm_report_cluster <- function(obj, proposal, report, prev_reports) {
  sprintf("
## [LLM Diagnostic Card] Step 5: Clustering

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Clusters | %d |
| Resolution | %.1f |

### LLM Analysis Task
> 1. Do clusters correspond to tissue regions (not image artifacts)?
> 2. Is %d clusters reasonable for this tissue type?
> 3. Are clusters driven by batch or biology?
> 4. Should spatially constrained clustering be used?
",
    report$status, report$n_clusters, report$resolution,
    report$n_clusters
  ) %>% trimws()
}


# ---------------------------------------------------------------------------
# D6: Spatial Analysis
# ---------------------------------------------------------------------------

.llm_report_spatial <- function(obj, proposal, report, prev_reports) {
  sprintf("
## [LLM Diagnostic Card] Step 6: Spatial Analysis [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | %d |
| Neighbor method | %s |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| SVGs detected | %s |
| Top SVG | %s |

### LLM Analysis Task [DECISION POINT]
> 1. Do top SVGs match expected tissue architecture markers?
> 2. Is %s appropriate for this platform?
> 3. Do neighborhood enrichment patterns match known tissue biology?
> 4. Any clusters with no spatial structure (possible artifacts)?
",
    proposal$diagnostics$n_spots, proposal$recommendation$neighbor_method,
    report$status, report$n_svgs %||% "N/A", report$top_svg %||% "N/A",
    proposal$recommendation$neighbor_method
  ) %>% trimws()
}


# ---------------------------------------------------------------------------
# D7: Domain Detection
# ---------------------------------------------------------------------------

.llm_report_domain <- function(obj, proposal, report, prev_reports) {
  sprintf("
## [LLM Diagnostic Card] Step 7: Domain Detection [CRITICAL]

### Data Snapshot
| Metric | Value |
|--------|-------|
| Spots | %d |
| Clusters | %d |

### Rule Proposal
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Method | %s | %s |

### Execution Report
| Outcome | Value |
|---------|-------|
| Status | **%s** |
| Domains detected | %d |

### LLM Analysis Task [DECISION POINT]
> 1. Do spatial domains correspond to known histological regions?
> 2. Are domain boundaries sharp and biologically meaningful?
> 3. For method=%s: is this the best choice?
>    - Spatial Leiden: fast, exploratory
>    - STAGATE: complex architecture
>    - BayesSpace: uncertainty quantification
> 4. Should domains replace transcriptomic clusters for downstream?
",
    proposal$diagnostics$n_spots, proposal$diagnostics$n_clusters,
    proposal$recommendation$method, proposal$justification,
    report$status, report$n_domains,
    proposal$recommendation$method
  ) %>% trimws()
}


# ---------------------------------------------------------------------------
# Save helper
# ---------------------------------------------------------------------------

save_llm_reports <- function(llm_reports, output_dir) {
  llm_dir <- file.path(output_dir, "llm_reports")
  dir.create(llm_dir, showWarnings = FALSE, recursive = TRUE)

  for (step_name in names(llm_reports)) {
    if (!is.null(llm_reports[[step_name]])) {
      writeLines(llm_reports[[step_name]],
                 file.path(llm_dir, sprintf("%s_diagnostic.md", step_name)))
    }
  }

  combined <- paste(
    c("# LLM Diagnostic Reports — Spatial Transcriptomics Pipeline", "",
      unlist(lapply(names(llm_reports), function(sn) {
        if (!is.null(llm_reports[[sn]])) {
          c("---\n\n", llm_reports[[sn]], "\n")
        }
      }))),
    collapse = "\n"
  )
  writeLines(combined, file.path(llm_dir, "combined_report.md"))
  message(sprintf("LLM reports saved to: %s", llm_dir))
}
