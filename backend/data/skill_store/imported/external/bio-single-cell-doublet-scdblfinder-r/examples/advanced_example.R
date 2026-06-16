# Advanced Example: scDblFinder Comprehensive Analysis
# =====================================================
#
# Advanced workflow demonstrating:
# - Multi-sample processing
# - Cluster-aware detection
# - Multiple visualization types
# - Comprehensive reporting

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("scDblFinder Advanced Example\n")
cat("=", rep("=", 70), "\n\n", sep = "")

# -----------------------------------------------------------------------------
# Step 1: Create comprehensive test data
# -----------------------------------------------------------------------------
cat("[Step 1] Creating test data with multiple samples...\n")

set.seed(42)
n_cells <- 400
n_genes <- 2000
n_samples <- 2

# Create sample info
sample_ids <- rep(c("Sample1", "Sample2"), each = n_cells / 2)

# Create test data with known doublets
test_data <- create_scdblfinder_test_data(
  n_cells = n_cells,
  n_genes = n_genes,
  doublet_rate = 0.08,  # 8% doublets
  seed = 42
)

# Add sample information
test_data$sample_info <- sample_ids

# Create cluster-like groups
test_data$cluster_info <- rep(paste0("Cluster_", 1:4), each = n_cells / 4)

cat(sprintf("  Created: %d genes x %d cells (%d samples)\n",
            n_genes, n_cells, n_samples))
cat(sprintf("  Expected doublets: %d (%.1f%%)\n",
            test_data$n_doublets, 100 * test_data$doublet_rate))

# Create SingleCellExperiment
library(SingleCellExperiment)
sce <- SingleCellExperiment(assays = list(counts = test_data$counts))
sce$sample_id <- sample_ids
sce$cluster <- test_data$cluster_info

# -----------------------------------------------------------------------------
# Step 2: Validate and check
# -----------------------------------------------------------------------------
cat("\n[Step 2] Validating input and checking parameters...\n")

validation <- validate_scdblfinder_input(sce)
cat(sprintf("  Valid: %s\n", validation$valid))

params <- recommend_scdblfinder_params(
  n_cells = ncol(sce),
  n_samples = length(unique(sce$sample_id)),
  is_10x = TRUE
)

cat(sprintf("  Recommended nfeatures: %d\n", params$nfeatures))
cat(sprintf("  Recommended dims: %d\n", params$dims))

# -----------------------------------------------------------------------------
# Step 3: Run scDblFinder (commented)
# -----------------------------------------------------------------------------
cat("\n[Step 3] Running scDblFinder...\n")
cat("  (Commented out - requires scDblFinder package)\n")

# Uncomment for actual run:
# sce <- run_scdblfinder(
#   sce,
#   samples = sce$sample_id,
#   clusters = sce$cluster,
#   multiSampleMode = "split",
#   nfeatures = params$nfeatures,
#   dims = params$dims,
#   k = params$k,
#   dbr.per1k = params$dbr.per1k,
#   iter = 1,
#   verbose = TRUE
# )

# -----------------------------------------------------------------------------
# Step 4: Create mock results
# -----------------------------------------------------------------------------
cat("\n[Step 4] Creating mock results for demonstration...\n")

set.seed(42)

# Mock scores with some sample effect
mock_scores <- c(
  runif(180, 0, 0.4),      # Sample1 singlets
  runif(20, 0.3, 0.9),     # Sample1 doublets
  runif(180, 0, 0.4),      # Sample2 singlets
  runif(20, 0.3, 0.9)      # Sample2 doublets
)

mock_class <- ifelse(mock_scores > 0.5, "doublet", "singlet")
mock_origin <- ifelse(mock_class == "doublet",
                       paste(sample(c("Cluster_1", "Cluster_2", "Cluster_3", "Cluster_4"), n_cells, replace = TRUE),
                             sample(c("Cluster_1", "Cluster_2", "Cluster_3", "Cluster_4"), n_cells, replace = TRUE),
                             sep = "+"),
                       NA)

# Add to SCE
coldata(sce)$scDblFinder.score <- mock_scores
coldata(sce)$scDblFinder.class <- mock_class
coldata(sce)$scDblFinder.mostLikelyOrigin <- mock_origin
coldata(sce)$scDblFinder.sample <- sce$sample_id

# -----------------------------------------------------------------------------
# Step 5: Summarize results
# -----------------------------------------------------------------------------
cat("\n[Step 5] Summarizing results...\n")

summary <- summarize_scdblfinder_results(sce)
cat(sprintf("  Total cells: %d\n", summary$n_cells))
cat(sprintf("  Doublets: %d (%.1f%%)\n", summary$n_doublets, 100 * summary$doublet_rate))
cat(sprintf("  Singlets: %d\n", summary$n_singlets))
cat(sprintf("  Mean score: %.3f\n", summary$mean_score))

# By sample
cat("\n  By sample:\n")
sample_summary <- aggregate(
  sce$scDblFinder.class == "doublet",
  by = list(sample = sce$sample_id),
  FUN = function(x) c(sum(x), length(x), sum(x) / length(x))
)
print(sample_summary)

# -----------------------------------------------------------------------------
# Step 6: Check cluster enrichment
# -----------------------------------------------------------------------------
cat("\n[Step 6] Checking cluster enrichment...\n")

enrichment <- check_doublet_enrichment(sce, cluster_col = "cluster")
print(enrichment)

# -----------------------------------------------------------------------------
# Step 7: Extract specific doublet types
# -----------------------------------------------------------------------------
cat("\n[Step 7] Extracting specific doublet origins...\n")

# Get doublets involving Cluster_1
cluster1_doublets <- sce$scDblFinder.mostLikelyOrigin[
  grepl("Cluster_1", sce$scDblFinder.mostLikelyOrigin)
]
cat(sprintf("  Doublets involving Cluster_1: %d\n", length(cluster1_doublets)))

# Get inter-cluster doublets
inter_cluster <- sce$scDblFinder.mostLikelyOrigin[
  sce$scDblFinder.class == "doublet" &
    !is.na(sce$scDblFinder.mostLikelyOrigin) &
    !grepl("(\\w+)\\+\\1", sce$scDblFinder.mostLikelyOrigin)
]
cat(sprintf("  Inter-cluster doublets: %d\n", length(inter_cluster)))

# -----------------------------------------------------------------------------
# Step 8: Visualizations
# -----------------------------------------------------------------------------
cat("\n[Step 8] Creating visualizations...\n")

# These would be saved if graphics devices were opened:
# plot_doublet_score_distribution(sce, color_by = "sample_id")
# plot_doublet_scores_by_class(sce)
# plot_doublet_rate_by_sample(sce)

output_dir <- "./scdblfinder_plots"
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

cat(sprintf("  (Plots would be saved to: %s)\n", output_dir))

# -----------------------------------------------------------------------------
# Step 9: Filter and export
# -----------------------------------------------------------------------------
cat("\n[Step 9] Filtering and exporting results...\n")

# Filter doublets
sce_filtered <- filter_scdblfinder(sce, remove_doublets = TRUE)
cat(sprintf("  Cells after filtering: %d (%.1f%% retained)\n",
            ncol(sce_filtered), 100 * ncol(sce_filtered) / ncol(sce)))

# Export results
export_scdblfinder_results(
  sce,
  output_dir = "./scdblfinder_output",
  prefix = "advanced_example"
)

# -----------------------------------------------------------------------------
# Step 10: Generate comprehensive report
# -----------------------------------------------------------------------------
cat("\n[Step 10] Generating comprehensive report...\n")

report <- sprintf("
scDblFinder Advanced Analysis Report
====================================
Date: %s

Dataset Information
-------------------
Total cells: %d
Genes: %d
Samples: %d
Expected doublet rate: %.1f%%

Analysis Parameters
-------------------
nfeatures: %d
dims: %d
k: %d
dbr.per1k: %.3f
multiSampleMode: split
clusters: cluster-based

Results Summary
---------------
Detected doublets: %d (%.1f%%)
Detected singlets: %d
Mean doublet score: %.3f

Per-Sample Breakdown
--------------------
%s

Cluster Enrichment
------------------
%s

Recommendations
---------------
1. Doublet rate is %s
2. Filter doublets before downstream analysis
3. Check cluster enrichment for biological interpretation
4. Visualize on UMAP before final filtering

Output Files
------------
- Classifications: scdblfinder_output/advanced_example_classifications.csv
- Summary: scdblfinder_output/advanced_example_summary.txt
",
  format(Sys.time(), "%Y-%m-%d %H:%M"),
  n_cells, n_genes, n_samples, 100 * test_data$doublet_rate,
  params$nfeatures, params$dims, params$k, params$dbr.per1k,
  summary$n_doublets, 100 * summary$doublet_rate, summary$n_singlets,
  summary$mean_score,
  paste(capture.output(print(sample_summary)), collapse = "\n"),
  paste(capture.output(print(enrichment)), collapse = "\n"),
  ifelse(summary$doublet_rate > 0.02 && summary$doublet_rate < 0.15,
         "within expected range", "please review")
)

writeLines(report, "advanced_scdblfinder_report.txt")
cat("  Report saved: advanced_scdblfinder_report.txt\n")

cat("\n", rep("=", 70), "\n", sep = "")
cat("Advanced example complete!\n")
cat(rep("=", 70), "\n", sep = "")
