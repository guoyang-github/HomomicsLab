#' Main Pipeline Runner — Spatial Transcriptomics (R)
#'
#' Linear auto-runner for the full spatial pipeline. Does NOT pause for user input.
#' For interactive per-step execution, call steps individually (Agent model).
#'
#' Usage:
#'   source('scripts/r/run_pipeline.R')
#'   result <- run_pipeline(data_path = 'spaceranger_output/', mode = 'auto')

library(Seurat)

.this_file <- if (!is.null(sys.frame(1)$ofile)) sys.frame(1)$ofile else NULL
if (is.null(.this_file) || .this_file == ".") {
  this_dir <- getwd()
} else {
  this_dir <- dirname(.this_file)
}

source(file.path(this_dir, "01_load_spatial.R"))
source(file.path(this_dir, "02_qc_spatial.R"))
source(file.path(this_dir, "03_normalize_spatial.R"))
source(file.path(this_dir, "04_integration_spatial.R"))
source(file.path(this_dir, "05_cluster_spatial.R"))
source(file.path(this_dir, "06_spatial_analysis.R"))
source(file.path(this_dir, "07_domain_detection.R"))
source(file.path(this_dir, "llm_report.R"))


run_pipeline <- function(
    data_path,
    output_dir = "spatial_results",
    mode = "auto",
    sample_col = "sample_id",
    use_llm = TRUE
) {
  #' Run the complete spatial transcriptomics pipeline.
  #'
  #' Linear auto-runner. Does NOT pause for user input.
  #' For interactive execution, call steps individually.
  #'
  #' @param data_path Path to data (Visium dir, Xenium dir, .rds, or SampleSheet CSV)
  #' @param output_dir Output directory
  #' @param mode "auto" (silent) or "verbose" (print proposals)
  #' @param sample_col Column for batch integration
  #' @param use_llm If TRUE, generate LLM diagnostic cards
  #' @return List with obj, reports, llm_reports, output_dir

  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  dir.create(file.path(output_dir, "plots"), showWarnings = FALSE, recursive = TRUE)

  reports <- list()
  prev_reports <- list()
  llm_reports <- list()

  # --- Step 1: Load ---
  message("\n========== STEP 1: Load Spatial Data ==========")
  obj <- load_spatial_data(data_path)

  # --- Step 2: QC ---
  message("\n========== STEP 2: QC Filtering ==========")
  qc_result <- run_qc_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- qc_result$obj
  reports$qc <- qc_result$report
  prev_reports$qc <- qc_result$report
  llm_reports$qc <- qc_result$llm_report
  message(sprintf(
    "[REPORT] %s: %s (%d -> %d spots, %.1f%% removed)",
    qc_result$report$step, qc_result$report$status,
    qc_result$report$spots_before, qc_result$report$spots_after,
    qc_result$report$pct_removed
  ))

  # --- Step 3: Normalize ---
  message("\n========== STEP 3: Normalization + HVG ==========")
  norm_result <- run_normalization_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- norm_result$obj
  reports$normalization <- norm_result$report
  prev_reports$normalization <- norm_result$report
  llm_reports$normalization <- norm_result$llm_report
  message(sprintf(
    "[REPORT] %s: %s (method=%s, HVGs=%d)",
    norm_result$report$step, norm_result$report$status,
    norm_result$report$method, norm_result$report$n_hvg
  ))

  # --- Step 4: Integration ---
  message("\n========== STEP 4: Integration Decision ==========")
  int_result <- run_integration_step(obj, sample_col = sample_col, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- int_result$obj
  reports$integration <- int_result$report
  prev_reports$integration <- int_result$report
  llm_reports$integration <- int_result$llm_report
  message(sprintf(
    "[REPORT] %s: %s (method=%s)",
    int_result$report$step, int_result$report$status,
    int_result$report$method %||% "N/A"
  ))

  # --- Step 5: Clustering ---
  message("\n========== STEP 5: Clustering + UMAP ==========")
  clust_result <- run_clustering_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- clust_result$obj
  reports$clustering <- clust_result$report
  prev_reports$clustering <- clust_result$report
  llm_reports$clustering <- clust_result$llm_report
  message(sprintf(
    "[REPORT] %s: %s (%d clusters at res=%.1f)",
    clust_result$report$step, clust_result$report$status,
    clust_result$report$n_clusters, clust_result$report$resolution
  ))

  # --- Step 6: Spatial Analysis ---
  message("\n========== STEP 6: Spatial Analysis ==========")
  spat_result <- run_spatial_analysis_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- spat_result$obj
  reports$spatial <- spat_result$report
  prev_reports$spatial <- spat_result$report
  llm_reports$spatial <- spat_result$llm_report
  message(sprintf(
    "[REPORT] %s: %s (SVGs=%s, method=%s)",
    spat_result$report$step, spat_result$report$status,
    spat_result$report$n_svgs %||% "N/A",
    spat_result$report$svg_method %||% "N/A"
  ))

  # --- Step 7: Domain Detection ---
  message("\n========== STEP 7: Domain Detection ==========")
  dom_result <- run_domain_detection_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- dom_result$obj
  reports$domain <- dom_result$report
  prev_reports$domain <- dom_result$report
  llm_reports$domain <- dom_result$llm_report
  message(sprintf(
    "[REPORT] %s: %s (%d domains, method=%s)",
    dom_result$report$step, dom_result$report$status,
    dom_result$report$n_domains, dom_result$report$method
  ))

  # --- Save ---
  message("\n========== SAVING RESULTS ==========")
  saveRDS(obj, file.path(output_dir, "spatial_seurat.rds"))

  if (use_llm) {
    save_llm_reports(llm_reports, output_dir)
  }

  # Summary plots
  if (length(obj@images) > 0) {
    p1 <- SpatialDimPlot(obj, label = TRUE)
    pdf(file.path(output_dir, "plots", "spatial_clusters.pdf"), width = 10, height = 8)
    print(p1)
    dev.off()

    if ("spatial_domain" %in% colnames(obj@meta.data)) {
      p2 <- SpatialDimPlot(obj, group.by = "spatial_domain", label = TRUE)
      pdf(file.path(output_dir, "plots", "spatial_domains.pdf"), width = 10, height = 8)
      print(p2)
      dev.off()
    }
  }

  # --- Final Report ---
  message("\n========== PIPELINE COMPLETE ==========")
  message(sprintf("Final spots: %d", ncol(obj)))
  message(sprintf("Results saved to: %s", output_dir))

  list(
    obj = obj,
    reports = reports,
    llm_reports = llm_reports,
    output_dir = output_dir
  )
}


resume_pipeline <- function(
    obj,
    from_step = 5,
    output_dir = "spatial_results",
    mode = "auto",
    use_llm = TRUE,
    prev_reports = NULL,
    ...
) {
  #' Resume pipeline from a specific step.
  #'
  #' @param obj Seurat object
  #' @param from_step Step to resume from (5-7)
  #' @param output_dir Output directory
  #' @param mode "auto" (silent) or "verbose" (print proposals)
  #' @param use_llm Generate LLM diagnostic cards
  #' @param prev_reports Previous reports
  #' @param ... Passed to step functions
  #' @return List with obj, reports, llm_reports, output_dir

  if (from_step <= 4) {
    stop("Cannot resume before Step 5. Use run_pipeline() for full run.")
  }

  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  reports <- list()
  llm_reports <- list()
  if (is.null(prev_reports)) {
    prev_reports <- list()
  }

  if (from_step <= 5) {
    message("\n========== STEP 5: Clustering + UMAP ==========")
    clust_result <- run_clustering_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports, ...)
    obj <- clust_result$obj
    reports$clustering <- clust_result$report
    prev_reports$clustering <- clust_result$report
    llm_reports$clustering <- clust_result$llm_report
  }

  if (from_step <= 6) {
    message("\n========== STEP 6: Spatial Analysis ==========")
    spat_result <- run_spatial_analysis_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports, ...)
    obj <- spat_result$obj
    reports$spatial <- spat_result$report
    prev_reports$spatial <- spat_result$report
    llm_reports$spatial <- spat_result$llm_report
  }

  if (from_step <= 7) {
    message("\n========== STEP 7: Domain Detection ==========")
    dom_result <- run_domain_detection_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports, ...)
    obj <- dom_result$obj
    reports$domain <- dom_result$report
    prev_reports$domain <- dom_result$report
    llm_reports$domain <- dom_result$llm_report
  }

  saveRDS(obj, file.path(output_dir, "spatial_seurat.rds"))

  if (use_llm) {
    save_llm_reports(llm_reports, output_dir)
  }

  message("\n========== RESUME COMPLETE ==========")

  list(obj = obj, reports = reports, llm_reports = llm_reports, output_dir = output_dir)
}


`%||%` <- function(x, y) if (is.null(x)) y else x
