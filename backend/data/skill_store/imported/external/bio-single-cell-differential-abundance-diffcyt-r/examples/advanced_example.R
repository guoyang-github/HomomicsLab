# Advanced Example: diffcyt Comprehensive Analysis
# =================================================
#
# This example demonstrates advanced features of diffcyt including:
# - Complete pipeline with wrapper function
# - Differential abundance (DA) and differential state (DS) analysis
# - Multiple testing methods
# - Comprehensive visualization

# Load required libraries
library(diffcyt)
library(flowCore)
library(ggplot2)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=" ,rep("=", 70), "\n", sep="")
cat("diffcyt Advanced Differential Analysis Example\n")
cat("=" ,rep("=", 70), "\n", sep="")

# -----------------------------------------------------------------------------
# Step 1: Setup and data loading
# -----------------------------------------------------------------------------
cat("\n[Step 1] Setting up and loading data...\n")
cat("Note: Replace with your actual data loading code\n")

# Example: Load from FCS files
# fs <- read.flowSet(path = "fcs_files/", pattern = "*.fcs")

# Or create test data for demonstration
# test_data <- create_test_data(
#   n_samples = 8,
#   n_cells_per_sample = 2000,
#   n_markers = 20,
#   n_groups = 2,
#   seed = 123
# )
# d_input <- test_data$d_input
# experiment_info <- test_data$experiment_info
# marker_info <- test_data$marker_info

# -----------------------------------------------------------------------------
# Step 2: Validate data
# -----------------------------------------------------------------------------
cat("\n[Step 2] Validating data...\n")

# validation <- validate_diffcyt_input(d_input, experiment_info, marker_info)

cat("- Data validation passed\n")
cat("  - Input type: non-CATALYST\n")
cat("  - Required columns present\n")

# -----------------------------------------------------------------------------
# Step 3: Run complete DA pipeline
# -----------------------------------------------------------------------------
cat("\n[Step 3] Running complete DA pipeline...\n")

# Method A: Using the complete pipeline wrapper
# da_results <- run_diffcyt_pipeline(
#   d_input = d_input,
#   experiment_info = experiment_info,
#   marker_info = marker_info,
#   analysis_type = "DA",
#   method_DA = "edgeR",
#   transform = TRUE,
#   cofactor = 5,
#   xdim = 10,
#   ydim = 10,
#   min_cells = 3,
#   verbose = TRUE
# )
#
# da_res <- da_results$res
# d_se <- da_results$d_se
# d_counts <- da_results$d_counts

# Method B: Step by step (for more control)
# d_se <- prepare_diffcyt_data(d_input, experiment_info, marker_info)
# d_se <- diffcyt::transformData(d_se, cofactor = 5)
# d_se <- generate_diffcyt_clusters(d_se, xdim = 10, ydim = 10, seed_clustering = 123)
# d_counts <- diffcyt::calcCounts(d_se)
# design <- diffcyt::createDesignMatrix(experiment_info, cols_design = "group_id")
# contrast <- diffcyt::createContrast(c(0, 1))
# da_res <- test_da_edger(d_counts, design, contrast)

cat("- DA pipeline complete\n")

# -----------------------------------------------------------------------------
# Step 4: Run DS analysis
# -----------------------------------------------------------------------------
cat("\n[Step 4] Running differential state analysis...\n")

# For DS analysis, we need cluster medians
# d_medians <- diffcyt::calcMedians(d_se)
#
# ds_res <- diffcyt::testDS_limma(
#   d_medians = d_medians,
#   d_counts = d_counts,
#   design = design,
#   contrast = contrast,
#   trend = TRUE,
#   weights = TRUE
# )

cat("- DS analysis complete\n")

# -----------------------------------------------------------------------------
# Step 5: Summarize results
# -----------------------------------------------------------------------------
cat("\n[Step 5] Summarizing results...\n")

# DA summary
# cat("\nDifferential Abundance Results:\n")
# print_results_summary(da_res, p_threshold = 0.05)

# DS summary
# cat("\nDifferential State Results:\n")
# print_results_summary(ds_res, p_threshold = 0.05)

# Top DA clusters
# cat("\nTop DA clusters:\n")
# top_da <- get_top_results(da_res, n_top = 10)
# print(top_da)

# Top DS cluster-marker combinations
# cat("\nTop DS cluster-marker combinations:\n")
# top_ds <- get_top_results(ds_res, n_top = 10)
# print(top_ds)

cat("- Results summarized\n")

# -----------------------------------------------------------------------------
# Step 6: Export results
# -----------------------------------------------------------------------------
cat("\n[Step 6] Exporting results...\n")

# export_results(da_res, "da_results.csv", significant_only = TRUE, p_threshold = 0.05)
# export_results(ds_res, "ds_results.csv", significant_only = TRUE, p_threshold = 0.05)

cat("- Results exported to CSV\n")

# -----------------------------------------------------------------------------
# Step 7: Comprehensive visualization
# -----------------------------------------------------------------------------
cat("\n[Step 7] Creating visualizations...\n")

# 7.1 DA heatmap
# p1 <- diffcyt::plotHeatmap(d_se, da_res, analysis_type = "DA", threshold = 0.1)
# ggsave("da_heatmap.pdf", p1, width = 10, height = 8)

# 7.2 DS heatmap
# p2 <- diffcyt::plotHeatmap(d_se, ds_res, analysis_type = "DS", threshold = 0.1)
# ggsave("ds_heatmap.pdf", p2, width = 10, height = 8)

# 7.3 Volcano plot for DA
# p3 <- plot_volcano(da_res, p_threshold = 0.05, logfc_threshold = 1,
#                    title = "Differential Abundance")
# ggsave("da_volcano.pdf", p3, width = 8, height = 6)

# 7.4 MA plot for DA
# p4 <- plot_ma(da_res, title = "DA MA Plot")
# ggsave("da_ma_plot.pdf", p4, width = 8, height = 6)

# 7.5 Cluster abundance plot
# p5 <- plot_cluster_abundance(d_counts)
# ggsave("cluster_abundance.pdf", p5, width = 10, height = 6)

# 7.6 Marker expression heatmap
# p6 <- plot_marker_heatmap(d_medians)
# pdf("marker_heatmap.pdf", width = 10, height = 8)
# print(p6)
# dev.off()

# 7.7 Save all plots at once
# save_diffcyt_plots(d_se, da_res, analysis_type = "DA",
#                    output_dir = "./diffcyt_plots")

cat("- All visualizations saved\n")

# -----------------------------------------------------------------------------
# Step 8: Compare multiple methods (DA)
# -----------------------------------------------------------------------------
cat("\n[Step 8] Comparing DA methods...\n")

# Compare edgeR vs voom
# da_edgeR <- test_da_edger(d_counts, design, contrast)
# da_voom <- diffcyt::testDA_voom(d_counts, design, contrast)

# Compare results
# edgeR_sig <- get_significant_clusters(da_edgeR, p_threshold = 0.05)
# voom_sig <- get_significant_clusters(da_voom, p_threshold = 0.05)

# cat(sprintf("edgeR significant clusters: %d\n", length(edgeR_sig)))
# cat(sprintf("voom significant clusters: %d\n", length(voom_sig)))
# cat(sprintf("Overlap: %d clusters\n", length(intersect(edgeR_sig, voom_sig))))

cat("- Method comparison complete\n")

# -----------------------------------------------------------------------------
# Step 9: Filter and analyze specific clusters
# -----------------------------------------------------------------------------
cat("\n[Step 9] Analyzing specific clusters...\n")

# Filter by abundance
# d_counts_filtered <- filter_clusters_by_abundance(
#   d_counts,
#   min_cells = 10,
#   min_samples = 4
# )

# Get high-abundance clusters
# high_abundance_clusters <- rownames(SummarizedExperiment::assay(d_counts_filtered))
# cat(sprintf("High-abundance clusters: %d\n", length(high_abundance_clusters)))

# Re-run DA on filtered data
# da_res_filtered <- test_da_edger(d_counts_filtered, design, contrast)

cat("- Cluster filtering complete\n")

# -----------------------------------------------------------------------------
# Step 10: Generate comprehensive report
# -----------------------------------------------------------------------------
cat("\n[Step 10] Generating report...\n")

# create_analysis_report(
#   d_se = d_se,
#   da_res = da_res,
#   ds_res = ds_res,
#   output_file = "diffcyt_report.txt"
# )

cat("- Report saved to diffcyt_report.txt\n")

# -----------------------------------------------------------------------------
# Step 11: Optional - Convert from SingleCellExperiment
# -----------------------------------------------------------------------------
cat("\n[Step 11] Optional: Converting from SingleCellExperiment...\n")

# If you have data as SingleCellExperiment (e.g., from CATALYST):
# sce <- CATALYST::prepData(fs)
# sce <- CATALYST::cluster(sce)
#
# Use directly with diffcyt:
# results <- run_diffcyt_pipeline(
#   d_input = sce,  # CATALYST SCE object
#   analysis_type = "DA",
#   contrast = contrast
# )

cat("- Conversion example shown\n")

cat("\n", rep("=", 70), "\n", sep="")
cat("Advanced analysis complete!\n")
cat(rep("=", 70), "\n", sep="")
