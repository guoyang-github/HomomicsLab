# Minimal Example: miloR Differential Abundance Analysis
# ========================================================
#
# Basic workflow for testing differential abundance with miloR

# Load required libraries
library(miloR)
library(SingleCellExperiment)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("miloR Minimal Example\n")
cat("=", rep("=", 70), "\n\n", sep = "")

# -----------------------------------------------------------------------------
# Step 1: Create or load test data
# -----------------------------------------------------------------------------
cat("[Step 1] Creating test data...\n")

# Option 1: Use built-in test data generator
sce <- create_milo_test_data(
  n_cells = 500,
  n_samples = 6,
  n_genes = 1000,
  da_effect = TRUE,
  seed = 42
)

# Option 2: Load your own data
# sce <- readRDS("your_data.rds")
# Or convert from Seurat:
# sce <- seurat_to_sce(seurat_obj)

cat(sprintf("  Created SCE with %d cells, %d genes\n", ncol(sce), nrow(sce)))

# -----------------------------------------------------------------------------
# Step 2: Create Milo object and run analysis pipeline
# -----------------------------------------------------------------------------
cat("\n[Step 2] Running miloR pipeline...\n")

# Define design formula and create design data frame
design_df <- unique(data.frame(
  sample_id = sce$sample_id,
  condition = sce$condition
))
rownames(design_df) <- design_df$sample_id

# Run complete pipeline
results <- run_milo_pipeline(
  x = sce,
  sample_col = "sample_id",
  condition_col = "condition",
  design = ~ condition,
  design.df = design_df,
  k = 30,
  d = 30,
  prop = 0.1,
  refined = TRUE,
  calc.distances = TRUE,
  seed = 42
)

milo_obj <- results$milo
da_results <- results$da_results

# -----------------------------------------------------------------------------
# Step 3: Summarize results
# -----------------------------------------------------------------------------
cat("\n[Step 3] Summarizing results...\n")

summary_stats <- summarize_milo_results(da_results, alpha = 0.1)

# Get top DA neighborhoods
top_da <- get_top_da_nhoods(da_results, n_top = 5)
cat("\nTop 5 DA neighborhoods:\n")
print(top_da[, c("logFC", "PValue", "SpatialFDR")])

# Get significant neighborhoods
sig_nhoods <- get_significant_nhoods(da_results, alpha = 0.1, min.logFC = 1)
cat(sprintf("\nSignificant neighborhoods: %d\n", length(sig_nhoods)))

# -----------------------------------------------------------------------------
# Step 4: Visualization
# -----------------------------------------------------------------------------
cat("\n[Step 4] Creating visualizations...\n")

# Beeswarm plot
p1 <- plot_milo_beeswarm(da_results, alpha = 0.1)
ggsave("minimal_beeswarm.pdf", p1, width = 6, height = 5)
cat("  Saved: minimal_beeswarm.pdf\n")

# Volcano plot
p2 <- plot_milo_volcano(da_results, alpha = 0.1)
ggsave("minimal_volcano.pdf", p2, width = 6, height = 5)
cat("  Saved: minimal_volcano.pdf\n")

# Neighborhood size distribution
p3 <- plot_milo_size_distribution(milo_obj)
ggsave("minimal_size_dist.pdf", p3, width = 6, height = 4)
cat("  Saved: minimal_size_dist.pdf\n")

# -----------------------------------------------------------------------------
# Step 5: Export results
# -----------------------------------------------------------------------------
cat("\n[Step 5] Exporting results...\n")

export_milo_results(da_results, "minimal_da_results.csv", significant_only = FALSE)
export_milo_results(da_results, "minimal_da_results_sig.csv", significant_only = TRUE, alpha = 0.1)

cat("  Exported: minimal_da_results.csv\n")
cat("  Exported: minimal_da_results_sig.csv\n")

cat("\n", rep("=", 70), "\n", sep = "")
cat("Minimal example complete!\n")
cat(rep("=", 70), "\n", sep = "")
