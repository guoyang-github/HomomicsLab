#' Test Case 6: R path full pipeline (auto mode)
#'
#' Validates the R ecosystem path on PA08 data.
#' Note: Python h5ad must be converted to Seurat RDS first, or loaded via SeuratDisk.
#'
#' Usage:
#'   Rscript tests/test_r_path.R

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

script_dir <- dirname(sys.frame(1)$ofile)
if (is.null(script_dir) || script_dir == ".") {
  script_dir <- getwd()
}

# Source pipeline
source(file.path(script_dir, "..", "scripts", "r", "run_pipeline.R"))

# Check for required packages
required_pkgs <- c("Seurat", "SeuratDisk", "ggplot2", "dplyr")
missing <- required_pkgs[!sapply(required_pkgs, requireNamespace, quietly = TRUE)]
if (length(missing) > 0) {
  stop("Missing R packages: ", paste(missing, collapse = ", "),
       "\nInstall with: install.packages(c('Seurat', 'SeuratDisk', 'ggplot2', 'dplyr'))")
}

# ---------------------------------------------------------------------------
# Helper: Convert h5ad to Seurat RDS (one-time)
# ---------------------------------------------------------------------------

convert_h5ad_to_rds <- function(h5ad_path, rds_path) {
  if (file.exists(rds_path)) {
    message("RDS already exists, skipping conversion: ", rds_path)
    return(rds_path)
  }

  message("Converting h5ad to Seurat RDS...")
  library(SeuratDisk)

  # Convert h5ad to h5Seurat
  h5seurat_path <- sub("\\.h5ad$", ".h5Seurat", h5ad_path)
  Convert(h5ad_path, dest = "h5seurat", overwrite = TRUE)

  # Load h5Seurat as Seurat object
  obj <- LoadH5Seurat(h5seurat_path)

  # Rename mito_percent -> percent.mt for QC compatibility
  if ("mito_percent" %in% colnames(obj@meta.data)) {
    obj$percent.mt <- as.numeric(obj$mito_percent)
  }

  # Ensure counts assay is set
  if ("counts" %in% Layers(obj)) {
    DefaultAssay(obj) <- "RNA"
  }

  saveRDS(obj, rds_path)
  message("Saved RDS: ", rds_path)
  return(rds_path)
}

# ---------------------------------------------------------------------------
# Test: Full R pipeline
# ---------------------------------------------------------------------------

test_r_pipeline <- function() {
  message("\n", paste(rep("=", 60), collapse = ""))
  message("TEST 6: R path full pipeline (auto mode)")
  message(paste(rep("=", 60), collapse = ""), "\n")

  # Paths
  h5ad_path <- file.path(script_dir, "PA08_sc_renamed.h5ad")
  rds_path <- file.path(script_dir, "PA08_sc.rds")
  out_dir <- file.path(script_dir, "output_test_r")

  if (!file.exists(h5ad_path)) {
    stop("Test data not found: ", h5ad_path, "\nRun prepare_test_data.py first.")
  }

  # Convert if needed
  rds_path <- convert_h5ad_to_rds(h5ad_path, rds_path)

  # Run pipeline
  result <- run_pipeline(
    data_path = rds_path,
    project = "PA08",
    output_dir = out_dir,
    mode = "auto",
    batch_col = "patients",
    tissue = "Pancreas",
    use_llm = TRUE
  )

  obj <- result$obj
  reports <- result$reports
  llm_reports <- result$llm_reports

  # --- Assertions ---

  # 1. Final state
  stopifnot(obj@misc$pipeline_state == "Annotated")
  stopifnot(ncol(obj) > 0)
  stopifnot(nrow(obj) > 0)

  # 2. Reports
  expected_steps <- c("qc", "doublet", "normalization", "integration", "clustering", "markers", "annotation")
  for (step in expected_steps) {
    stopifnot(step %in% names(reports))
    stopifnot("status" %in% names(reports[[step]]))
    message("  ", step, ": ", reports[[step]]$status)
  }

  # 3. QC specifics
  qc <- reports$qc
  stopifnot(qc$cells_before == 25524)
  stopifnot(qc$pct_removed < 50)

  # 4. Single sample -> integration skipped
  stopifnot(reports$integration$status == "SKIPPED")

  # 5. Clustering
  clust <- reports$clustering
  stopifnot(clust$n_clusters >= 5 && clust$n_clusters <= 50)

  # 6. Markers
  stopifnot(reports$markers$n_markers > 0)

  # 7. Annotation
  annot <- reports$annotation
  stopifnot(annot$pct_assigned > 50)
  stopifnot("cell_type" %in% colnames(obj@meta.data))

  # 8. LLM reports
  stopifnot(length(llm_reports) > 0)
  llm_dir <- file.path(out_dir, "llm_reports")
  stopifnot(dir.exists(llm_dir))
  stopifnot(file.exists(file.path(llm_dir, "combined_report.md")))

  # 9. Output files
  stopifnot(file.exists(file.path(out_dir, "seurat_annotated.rds")))
  stopifnot(file.exists(file.path(out_dir, "all_markers.csv")))
  stopifnot(file.exists(file.path(out_dir, "plots", "umap_annotated.pdf")))

  message("\n", paste(rep("=", 60), collapse = ""))
  message("TEST 6: PASSED")
  message("Final cells: ", ncol(obj))
  message("Clusters: ", clust$n_clusters)
  message("Cell types: ", annot$n_cell_types)
  message(paste(rep("=", 60), collapse = ""), "\n")

  invisible(result)
}

# Run test
test_r_pipeline()
