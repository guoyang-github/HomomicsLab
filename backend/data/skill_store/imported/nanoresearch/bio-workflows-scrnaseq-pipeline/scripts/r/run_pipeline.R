#' Main Pipeline Runner — Single-Cell RNA-seq (R)
#'
#' Linear auto-runner for the full pipeline. Does NOT pause for user input.
#' For interactive per-step execution, call steps individually (Agent model).
#'
#' Usage:
#'   source("scripts/r/run_pipeline.R")
#'   result <- run_pipeline(data_path = "filtered_feature_bc_matrix/",
#'                          project = "my_project",
#'                          mode = "auto")

# Helper for NULL defaulting
`%||%` <- function(x, y) if (is.null(x)) y else x

# Source all step scripts
script_dir <- dirname(sys.frame(1)$ofile)
if (is.null(script_dir) || script_dir == ".") {
  script_dir <- getwd()
}

source(file.path(script_dir, "llm_report.R"))
source(file.path(script_dir, "01_load.R"))
source(file.path(script_dir, "02_qc_decision.R"))
source(file.path(script_dir, "03_doublet.R"))
source(file.path(script_dir, "04_normalize.R"))
source(file.path(script_dir, "05_integration_decision.R"))
source(file.path(script_dir, "06_cluster.R"))
source(file.path(script_dir, "07_markers.R"))
source(file.path(script_dir, "08_annotation_decision.R"))


# ---------------------------------------------------------------------------
# Main pipeline runner
# ---------------------------------------------------------------------------

run_pipeline <- function(
  data_path,
  project = "scRNAseq",
  output_dir = "pipeline_results",
  mode = "auto",
  batch_col = "sample_id",
  tissue = NULL,
  resolution_col = NULL,
  use_llm = TRUE
) {
  #' Run the complete single-cell RNA-seq pipeline.
  #'
  #' Linear auto-runner. Does NOT pause for user input.
  #' For interactive execution, call steps individually.
  #'
  #' @param data_path Path to data (10X dir, .h5, .rds, or SampleSheet CSV)
  #' @param project Project name
  #' @param output_dir Output directory
  #' @param mode "auto" (silent) or "verbose" (print proposals)
  #' @param batch_col Column for batch integration
  #' @param tissue Tissue type hint for annotation
  #' @param resolution_col Cluster resolution column for markers
  #' @param use_llm If TRUE, generate LLM diagnostic cards at each step.
  #' @return List with final object and all step reports

  dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)
  dir.create(file.path(output_dir, "plots"), showWarnings = FALSE)

  reports <- list()
  prev_reports <- list()
  llm_reports <- list()

  # --- Step 1: Load ---
  message("\n========== STEP 1: Load Data ==========")
  obj <- load_data(data_path, project = project)

  # --- Step 2: QC ---
  message("\n========== STEP 2: QC Filtering ==========")
  qc_result <- run_qc_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- qc_result$obj
  reports$qc <- qc_result$report
  prev_reports$qc <- qc_result$report
  llm_reports$qc <- qc_result$llm_report
  message(sprintf("[REPORT] %s: %s (%d -> %d cells, %.1f%% removed)",
                  qc_result$report$step, qc_result$report$status,
                  qc_result$report$cells_before, qc_result$report$cells_after,
                  qc_result$report$pct_removed))

  # --- Step 3: Doublet ---
  message("\n========== STEP 3: Doublet Detection ==========")
  dbl_result <- run_doublet_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- dbl_result$obj
  reports$doublet <- dbl_result$report
  prev_reports$doublet <- dbl_result$report
  llm_reports$doublet <- dbl_result$llm_report
  message(sprintf("[REPORT] %s: %s (%.1f%% doublets)",
                  dbl_result$report$step, dbl_result$report$status,
                  dbl_result$report$doublet_rate))

  # --- Step 4: Normalize ---
  message("\n========== STEP 4: Normalization ==========")
  norm_result <- run_normalization_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- norm_result$obj
  reports$normalization <- norm_result$report
  prev_reports$normalization <- norm_result$report
  llm_reports$normalization <- norm_result$llm_report
  message(sprintf("[REPORT] %s: %s (method=%s, HVGs=%d)",
                  norm_result$report$step, norm_result$report$status,
                  norm_result$report$method, norm_result$report$n_hvg))

  # --- Step 5: Integration Decision ---
  message("\n========== STEP 5: Integration Decision ==========")
  int_result <- run_integration_step(obj, batch_col = batch_col, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- int_result$obj
  reports$integration <- int_result$report
  prev_reports$integration <- int_result$report
  llm_reports$integration <- int_result$llm_report
  message(sprintf("[REPORT] %s: %s (method=%s)",
                  int_result$report$step, int_result$report$status,
                  int_result$report$method %||% "N/A"))

  # --- Step 6: Clustering ---
  message("\n========== STEP 6: Clustering ==========")
  clust_result <- run_clustering_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- clust_result$obj
  reports$clustering <- clust_result$report
  prev_reports$clustering <- clust_result$report
  llm_reports$clustering <- clust_result$llm_report
  message(sprintf("[REPORT] %s: %s (%d clusters at res=%.1f)",
                  clust_result$report$step, clust_result$report$status,
                  clust_result$report$n_clusters,
                  clust_result$report$default_resolution))

  # --- Step 7: Markers ---
  message("\n========== STEP 7: Marker Detection ==========")
  if (is.null(resolution_col)) {
    resolution_col <- clust_result$report$default_column
    if (is.na(resolution_col) || length(resolution_col) == 0) {
      resolution_col <- NULL
    }
  }
  marker_result <- run_marker_step(obj, resolution_col = resolution_col, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- marker_result$obj
  reports$markers <- marker_result$report
  prev_reports$markers <- marker_result$report
  llm_reports$markers <- marker_result$llm_report

  # Export markers
  exported <- export_markers(obj, output_dir = output_dir)
  message(sprintf("[REPORT] %s: %s (%d markers, %.1f avg/cluster)",
                  marker_result$report$step, marker_result$report$status,
                  marker_result$report$n_markers,
                  marker_result$report$avg_markers_per_cluster))

  # --- Step 8: Annotation ---
  message("\n========== STEP 8: Cell Type Annotation ==========")
  annot_result <- run_annotation_step(obj, tissue = tissue, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
  obj <- annot_result$obj
  reports$annotation <- annot_result$report
  prev_reports$annotation <- annot_result$report
  llm_reports$annotation <- annot_result$llm_report
  message(sprintf("[REPORT] %s: %s (method=%s, %.1f%% assigned)",
                  annot_result$report$step, annot_result$report$status,
                  annot_result$report$method, annot_result$report$pct_assigned))

  # --- Save ---
  message("\n========== SAVING RESULTS ==========")
  saveRDS(obj, file.path(output_dir, "seurat_annotated.rds"))

  # Save LLM reports
  if (use_llm) {
    save_llm_reports(llm_reports, output_dir)
  }

  # Summary UMAP
  pdf(file.path(output_dir, "plots", "umap_annotated.pdf"), width = 10, height = 8)
  if ("cell_type" %in% colnames(obj@meta.data)) {
    DimPlot(obj, reduction = "umap", group.by = "cell_type", label = TRUE)
  } else {
    DimPlot(obj, reduction = "umap", label = TRUE)
  }
  dev.off()

  # --- Final Report ---
  message("\n========== PIPELINE COMPLETE ==========")
  message(sprintf("Final cells: %d", ncol(obj)))
  message(sprintf("Final clusters: %d", length(unique(Idents(obj)))))
  message(sprintf("Results saved to: %s", output_dir))

  invisible(list(
    obj = obj,
    reports = reports,
    llm_reports = llm_reports,
    output_dir = output_dir
  ))
}


# ---------------------------------------------------------------------------
# Resume from intermediate state
# ---------------------------------------------------------------------------

resume_pipeline <- function(
  obj,
  from_step = 5,
  output_dir = "pipeline_results",
  mode = "auto",
  use_llm = TRUE,
  prev_reports = list(),
  ...
) {
  #' Resume pipeline from a specific step.
  #' @param obj Seurat object with appropriate state
  #' @param from_step Step number to resume from (5-8)
  #' @param mode "auto" (silent) or "verbose" (print proposals)
  #' @param use_llm If TRUE, generate LLM diagnostic cards.
  #' @param prev_reports Previous step reports for cross-step context.
  #' @param ... Passed to run_pipeline parameters

  if (from_step <= 4) {
    stop("Cannot resume before Step 5. Use run_pipeline() for full run.")
  }

  reports <- list()
  llm_reports <- list()

  if (from_step <= 5) {
    message("\n========== STEP 5: Integration Decision ==========")
    int_result <- run_integration_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports, ...)
    obj <- int_result$obj
    reports$integration <- int_result$report
    prev_reports$integration <- int_result$report
    llm_reports$integration <- int_result$llm_report
  }

  if (from_step <= 6) {
    message("\n========== STEP 6: Clustering ==========")
    clust_result <- run_clustering_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
    obj <- clust_result$obj
    reports$clustering <- clust_result$report
    prev_reports$clustering <- clust_result$report
    llm_reports$clustering <- clust_result$llm_report
  }

  if (from_step <= 7) {
    message("\n========== STEP 7: Marker Detection ==========")
    res_col <- if (exists("clust_result", envir = environment())) clust_result$report$default_column %||% NULL else NULL
    marker_result <- run_marker_step(obj, resolution_col = res_col, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports)
    obj <- marker_result$obj
    reports$markers <- marker_result$report
    prev_reports$markers <- marker_result$report
    llm_reports$markers <- marker_result$llm_report
    export_markers(obj, output_dir = output_dir)
  }

  if (from_step <= 8) {
    message("\n========== STEP 8: Cell Type Annotation ==========")
    annot_result <- run_annotation_step(obj, auto = (mode == "auto"), use_llm = use_llm, prev_reports = prev_reports, ...)
    obj <- annot_result$obj
    reports$annotation <- annot_result$report
    prev_reports$annotation <- annot_result$report
    llm_reports$annotation <- annot_result$llm_report
  }

  saveRDS(obj, file.path(output_dir, "seurat_annotated.rds"))

  if (use_llm) {
    save_llm_reports(llm_reports, output_dir)
  }

  message("\n========== RESUME COMPLETE ==========")

  invisible(list(obj = obj, reports = reports, llm_reports = llm_reports, output_dir = output_dir))
}
