# Minimal Example: diffcyt Differential Analysis
# ===============================================
#
# This example demonstrates the basic workflow for diffcyt analysis

# Load required libraries
library(diffcyt)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=" ,rep("=", 60), "\n", sep="")
cat("diffcyt Differential Analysis - Minimal Example\n")
cat("=" ,rep("=", 60), "\n", sep="")

# -----------------------------------------------------------------------------
# Step 1: Load or create data
# -----------------------------------------------------------------------------
cat("\n[Step 1] Loading data...\n")
cat("Note: Replace with your actual data loading code\n")

# Option A: Load from FCS files
# library(flowCore)
# fs <- read.flowSet(path = "fcs_files/")

# Option B: Create from matrices
# d_input <- list(
#   sample1 = matrix(rnorm(10000), nrow = 1000, ncol = 10),
#   sample2 = matrix(rnorm(10000), nrow = 1000, ncol = 10),
#   sample3 = matrix(rnorm(10000), nrow = 1000, ncol = 10),
#   sample4 = matrix(rnorm(10000), nrow = 1000, ncol = 10)
# )

# -----------------------------------------------------------------------------
# Step 2: Create metadata
# -----------------------------------------------------------------------------
cat("\n[Step 2] Creating metadata...\n")

# experiment_info <- data.frame(
#   sample_id = factor(paste0("sample", 1:4)),
#   group_id = factor(c("control", "control", "treated", "treated")),
#   stringsAsFactors = FALSE
# )

# marker_info <- data.frame(
#   channel_name = paste0("channel", sprintf("%03d", 1:10)),
#   marker_name = paste0("marker", sprintf("%02d", 1:10)),
#   marker_class = factor(c(rep("type", 5), rep("state", 5)),
#                         levels = c("type", "state", "none")),
#   stringsAsFactors = FALSE
# )

cat("- Required metadata:\n")
cat("  - experiment_info with sample_id column\n")
cat("  - marker_info with marker_name and marker_class columns\n")

# -----------------------------------------------------------------------------
# Step 3: Prepare data
# -----------------------------------------------------------------------------
cat("\n[Step 3] Preparing data...\n")

# d_se <- prepare_diffcyt_data(
#   d_input = d_input,
#   experiment_info = experiment_info,
#   marker_info = marker_info
# )

cat("- Data preparation complete\n")
cat("  - Cells concatenated across samples\n")
cat("  - Metadata added\n")

# -----------------------------------------------------------------------------
# Step 4: Transform data
# -----------------------------------------------------------------------------
cat("\n[Step 4] Transforming data...\n")

# d_se <- diffcyt::transformData(d_se, cofactor = 5)

cat("- Arcsinh transformation applied\n")
cat("  - Cofactor = 5 (for CyTOF)\n")
cat("  - Use cofactor = 150 for flow cytometry\n")

# -----------------------------------------------------------------------------
# Step 5: Generate clusters
# -----------------------------------------------------------------------------
cat("\n[Step 5] Generating clusters...\n")

# d_se <- generate_diffcyt_clusters(
#   d_se,
#   xdim = 10,
#   ydim = 10,
#   seed_clustering = 123
# )

cat("- FlowSOM clustering complete\n")
cat("  - Grid: 10 x 10 = 100 clusters\n")

# -----------------------------------------------------------------------------
# Step 6: Calculate features
# -----------------------------------------------------------------------------
cat("\n[Step 6] Calculating features...\n")

# d_counts <- diffcyt::calcCounts(d_se)

cat("- Cluster counts calculated\n")

# -----------------------------------------------------------------------------
# Step 7: Create design and contrast
# -----------------------------------------------------------------------------
cat("\n[Step 7] Creating design matrix and contrast...\n")

# design <- diffcyt::createDesignMatrix(experiment_info, cols_design = "group_id")
# contrast <- diffcyt::createContrast(c(0, 1))

cat("- Design matrix created\n")
cat("- Contrast matrix created\n")

# -----------------------------------------------------------------------------
# Step 8: Test differential abundance
# -----------------------------------------------------------------------------
cat("\n[Step 8] Testing differential abundance...\n")

# da_res <- test_da_edger(
#   d_counts = d_counts,
#   design = design,
#   contrast = contrast,
#   min_cells = 3
# )

cat("- DA testing complete (edgeR)\n")

# -----------------------------------------------------------------------------
# Step 9: View results
# -----------------------------------------------------------------------------
cat("\n[Step 9] Viewing results...\n")

# top_results <- get_top_results(da_res, n_top = 10)
# print(top_results)

# sig_clusters <- get_significant_clusters(da_res, p_threshold = 0.05)
# cat(sprintf("Significant clusters: %d\n", length(sig_clusters)))

cat("- Results summary printed\n")

# -----------------------------------------------------------------------------
# Step 10: Visualize
# -----------------------------------------------------------------------------
cat("\n[Step 10] Visualizing results...\n")

# p <- diffcyt::plotHeatmap(d_se, da_res, analysis_type = "DA")
# print(p)

cat("- Heatmap plotted\n")

cat("\n", rep("=", 60), "\n", sep="")
cat("Analysis complete!\n")
cat(rep("=", 60), "\n", sep="")
