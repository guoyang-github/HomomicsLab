# Advanced Example: DoubletFinder Doublet Detection
# ==================================================
#
# This example demonstrates advanced features of DoubletFinder including:
# - SCTransform workflow
# - Homotypic doublet adjustment
# - Parallel processing
# - Comprehensive visualization
# - Cross-sample analysis

library(Seurat)
library(dplyr)
library(ggplot2)

# Source functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

main <- function() {
  cat("=" ,rep("=", 60), "\n", sep="")
  cat("DoubletFinder Advanced Analysis Example\n")
  cat("=" ,rep("=", 60), "\n\n", sep="")

  # -------------------------------------------------------------------------
  # Step 1: Load and preprocess data
  # -------------------------------------------------------------------------
  cat("[Step 1] Loading data...\n")
  cat("Note: Replace with your actual data loading code\n\n")

  # seurat_obj <- readRDS("your_data.rds")

  # -------------------------------------------------------------------------
  # Step 2: Choose preprocessing workflow
  # -------------------------------------------------------------------------
  cat("[Step 2] Preprocessing...\n")

  # Option A: Standard workflow
  # seurat_obj <- NormalizeData(seurat_obj)
  # seurat_obj <- FindVariableFeatures(seurat_obj, selection.method = "vst", nfeatures = 2000)
  # seurat_obj <- ScaleData(seurat_obj)
  # seurat_obj <- RunPCA(seurat_obj)

  # Option B: SCTransform workflow (recommended for better normalization)
  # seurat_obj <- SCTransform(seurat_obj, vst.flavor = "v2")
  # seurat_obj <- RunPCA(seurat_obj)

  # Common downstream steps
  # seurat_obj <- RunUMAP(seurat_obj, dims = 1:30)
  # seurat_obj <- FindNeighbors(seurat_obj, dims = 1:30)
  # seurat_obj <- FindClusters(seurat_obj, resolution = 0.5)

  cat("- Standard workflow: NormalizeData -> ScaleData -> PCA\n")
  cat("- SCTransform workflow: SCTransform -> PCA (set sct=TRUE)\n")
  cat("- Both workflows require clustering for homotypic adjustment\n\n")

  # -------------------------------------------------------------------------
  # Step 3: Run parameter sweep (parallel)
  # -------------------------------------------------------------------------
  cat("[Step 3] Parameter sweep with parallel processing...\n")

  # sweep_results <- run_param_sweep(
  #   seurat_obj,
  #   PCs = 1:30,
  #   sct = FALSE,           # Set TRUE if using SCTransform
  #   num.cores = 4,         # Parallel processing
  #   subsample = TRUE       # Subsample to 10000 cells for speed
  # )

  # optimal_pk <- sweep_results$optimal_pk

  cat("- Parallel processing with 4 cores\n")
  cat("- Automatic subsampling for large datasets (>10000 cells)\n")
  cat("- Computes BCmvn for optimal pK selection\n\n")

  # -------------------------------------------------------------------------
  # Step 4: Estimate doublets with platform-specific rates
  # -------------------------------------------------------------------------
  cat("[Step 4] Estimating doublet rate...\n")

  # Option 1: Platform-specific estimate
  # nExp_poi <- estimate_expected_doublets(ncol(seurat_obj), platform = "10x_v3")

  # Option 2: Based on actual loading
  # n_loaded <- 10000  # Number of cells loaded
  # recovery_rate <- 0.6  # 60% recovery
  # n_recovered <- round(n_loaded * recovery_rate)
  # doublet_rate <- get_10x_doublet_rate(n_loaded)
  # nExp_poi <- round(doublet_rate * n_recovered)

  # Option 3: Conservative estimate
  # nExp_poi <- round(0.06 * ncol(seurat_obj))  # 6% default

  cat("- 10x v3: ~0.8% per 1000 cells loaded\n")
  cat("- 10x v3.1: ~0.4% per 1000 cells (lower doublet rate)\n")
  cat("- Adjust based on actual loading density\n\n")

  # -------------------------------------------------------------------------
  # Step 5: Run DoubletFinder with homotypic adjustment
  # -------------------------------------------------------------------------
  cat("[Step 5] Running DoubletFinder with homotypic adjustment...\n")

  # Standard run (no adjustment)
  # seurat_obj <- run_doubletfinder(
  #   seurat_obj,
  #   PCs = 1:30,
  #   pN = 0.25,
  #   pK = optimal_pk,
  #   nExp = nExp_poi,
  #   sct = FALSE
  # )

  # With homotypic adjustment (requires clustering)
  # seurat_obj <- run_doubletfinder_adjusted(
  #   seurat_obj,
  #   PCs = 1:30,
  #   cluster_col = "seurat_clusters",  # Cell type annotations
  #   pK = optimal_pk,
  #   sct = FALSE
  # )

  cat("- Standard run: Assumes all doublets are detectable\n")
  cat("- Homotypic adjustment: Accounts for transcriptionally-similar doublets\n")
  cat("- Adjustment reduces nExp by predicted homotypic proportion\n\n")

  # -------------------------------------------------------------------------
  # Step 6: Multiple classification stringencies
  # -------------------------------------------------------------------------
  cat("[Step 6] Running with multiple stringencies...\n")

  # First run (unadjusted - more doublets)
  # seurat_obj <- run_doubletfinder(
  #   seurat_obj,
  #   PCs = 1:30,
  #   pN = 0.25,
  #   pK = optimal_pk,
  #   nExp = nExp_poi,
  #   reuse.pANN = NULL,
  #   sct = FALSE
  # )

  # Second run (adjusted - fewer doublets, reuses pANN)
  # annotations <- seurat_obj$seurat_clusters
  # homotypic.prop <- modelHomotypic(annotations)
  # nExp_poi.adj <- round(nExp_poi * (1 - homotypic.prop))
  #
  # pann_col <- grep("^pANN", colnames(seurat_obj@meta.data), value = TRUE)[1]
  # seurat_obj <- run_doubletfinder(
  #   seurat_obj,
  #   PCs = 1:30,
  #   pN = 0.25,
  #   pK = optimal_pk,
  #   nExp = nExp_poi.adj,
  #   reuse.pANN = pann_col,  # Reuse pANN for speed
  #   sct = FALSE
  # )

  cat("- First run: Higher stringency (nExp_poi)\n")
  cat("- Second run: Lower stringency with same pANN\n")
  cat("- reuse.pANN saves computation time\n\n")

  # -------------------------------------------------------------------------
  # Step 7: Comprehensive visualization
  # -------------------------------------------------------------------------
  cat("[Step 7] Creating comprehensive visualizations...\n")

  # Complete workflow with visualization
  # seurat_obj <- run_doubletfinder_workflow(
  #   seurat_obj,
  #   PCs = 1:30,
  #   sct = FALSE,
  #   adjust_homotypic = TRUE,
  #   cluster_col = "seurat_clusters",
  #   filter = FALSE  # Set TRUE to auto-filter
  # )

  # Individual plots
  # p1 <- plot_doublet_embedding(seurat_obj, reduction = "umap")
  # p2 <- plot_pk_optimization(sweep_results$bcmvn)
  # p3 <- plot_pann_distribution(seurat_obj)
  # p4 <- plot_pann_violin(seurat_obj, group_by = "seurat_clusters")
  # p5 <- plot_doublet_rate_by_cluster(seurat_obj, cluster_col = "seurat_clusters")

  # Combined summary plot
  # summary_plot <- plot_doublet_summary(
  #   seurat_obj,
  #   sweep_results = sweep_results,
  #   reduction = "umap",
  #   output_file = "doubletfinder_summary.png"
  # )

  cat("- Doublet predictions on UMAP\n")
  cat("- pK optimization curve\n")
  cat("- pANN distributions\n")
  cat("- Doublet rate by cluster\n")
  cat("- Combined summary figure\n\n")

  # -------------------------------------------------------------------------
  # Step 8: Summary statistics
  # -------------------------------------------------------------------------
  cat("[Step 8] Generating summary statistics...\n")

  # Overall summary
  # summary <- get_doublet_summary(seurat_obj)
  # print(summary)

  # By cluster
  # cluster_summary <- get_doublet_summary(seurat_obj, group_by = "seurat_clusters")
  # print(cluster_summary)

  # By sample (if multi-sample)
  # sample_summary <- summarize_by_sample(seurat_obj, sample_col = "sample")
  # print(sample_summary)

  cat("- Overall doublet rate\n")
  cat("- Per-cluster doublet rates\n")
  cat("- Per-sample statistics (multi-sample)\n\n")

  # -------------------------------------------------------------------------
  # Step 9: High-confidence doublets
  # -------------------------------------------------------------------------
  cat("[Step 9] Identifying high-confidence doublets...\n")

  # Get high-confidence doublets based on pANN threshold
  # high_conf <- get_high_confidence_doublets(seurat_obj, pann_threshold = 0.5)
  # cat("High-confidence doublets:", length(high_conf), "\n")

  # Create threshold-dependent classification
  # pann_col <- grep("^pANN", colnames(seurat_obj@meta.data), value = TRUE)[1]
  # pann_scores <- seurat_obj@meta.data[[pann_col]]
  # seurat_obj$doublet_confidence <- ifelse(
  #   pann_scores > 0.5, "High",
  #   ifelse(pann_scores > 0.2, "Medium", "Low")
  # )

  cat("- High-confidence: pANN >= 0.5\n")
  cat("- Medium-confidence: pANN 0.2-0.5\n")
  cat("- Low-confidence: pANN < 0.2\n\n")

  # -------------------------------------------------------------------------
  # Step 10: Filter and save
  # -------------------------------------------------------------------------
  cat("[Step 10] Filtering and exporting...\n")

  # Filter doublets
  # seurat_filtered <- filter_doublets(seurat_obj, keep = "Singlet")

  # Export predictions
  # export_doublet_predictions(
  #   seurat_obj,
  #   output_file = "doublet_predictions.csv",
  #   include_pANN = TRUE
  # )

  # Generate report
  # generate_df_report(seurat_obj, output_file = "doubletfinder_report.txt")

  # Save objects
  # saveRDS(seurat_obj, "seurat_with_doublets.rds")
  # saveRDS(seurat_filtered, "seurat_filtered.rds")

  cat("- Filtered Seurat object\n")
  cat("- Exported doublet predictions (CSV)\n")
  cat("- Generated analysis report\n")
  cat("- Saved RDS files\n\n")

  cat("=" ,rep("=", 60), "\n", sep="")
  cat("Advanced analysis complete!\n")
  cat("=" ,rep("=", 60), "\n", sep="")
}

# Run main function
main()
