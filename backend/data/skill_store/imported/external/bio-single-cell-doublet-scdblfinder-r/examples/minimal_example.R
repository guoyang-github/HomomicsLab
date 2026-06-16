# Minimal Example: scDblFinder Doublet Detection
# =================================================
#
# Basic workflow for doublet detection using scDblFinder

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("scDblFinder Minimal Example\n")
cat("=", rep("=", 70), "\n\n", sep = "")

# -----------------------------------------------------------------------------
# Step 1: Create test data
# -----------------------------------------------------------------------------
cat("[Step 1] Creating test data...\n")

test_data <- create_scdblfinder_test_data(
  n_cells = 200,
  n_genes = 1000,
  doublet_rate = 0.05,
  seed = 42
)

cat(sprintf("  Created: %d genes x %d cells\n",
            nrow(test_data$counts), ncol(test_data$counts)))
cat(sprintf("  Expected doublets: %d (%.1f%%)\n",
            test_data$n_doublets, 100 * test_data$doublet_rate))

# Create SingleCellExperiment
library(SingleCellExperiment)
sce <- SingleCellExperiment(assays = list(counts = test_data$counts))

# -----------------------------------------------------------------------------
# Step 2: Validate input
# -----------------------------------------------------------------------------
cat("\n[Step 2] Validating input...\n")

validation <- validate_scdblfinder_input(sce)
cat(sprintf("  Valid: %s\n", validation$valid))
cat(sprintf("  Cells: %d, Genes: %d\n",
            validation$stats$n_cells, validation$stats$n_genes))

# -----------------------------------------------------------------------------
# Step 3: Get parameter recommendations
# -----------------------------------------------------------------------------
cat("\n[Step 3] Getting parameter recommendations...\n")

params <- recommend_scdblfinder_params(
  n_cells = ncol(sce),
  n_samples = 1,
  is_10x = TRUE
)

cat(params$message)

# -----------------------------------------------------------------------------
# Step 4: Run scDblFinder (commented to avoid dependency requirement)
# -----------------------------------------------------------------------------
cat("\n[Step 4] Running scDblFinder...\n")
cat("  (Commented out in example - requires scDblFinder package)\n")

# Uncomment to run with actual scDblFinder package:
# sce <- run_scdblfinder(
#   sce,
#   clusters = FALSE,
#   nfeatures = params$nfeatures,
#   dims = params$dims,
#   dbr.per1k = params$dbr.per1k,
#   verbose = TRUE
# )

# -----------------------------------------------------------------------------
# Step 5: Mock results for demonstration
# -----------------------------------------------------------------------------
cat("\n[Step 5] Creating mock results for demonstration...\n")

# Create realistic mock results
set.seed(42)
n_cells <- ncol(sce)
doublet_rate <- 0.05

# Mock scores (higher for simulated doublets)
mock_scores <- c(
  runif(round(n_cells * (1 - doublet_rate)), 0, 0.5),  # Singlets
  runif(round(n_cells * doublet_rate), 0.3, 1)          # Doublets
)

# Mock classifications
mock_class <- ifelse(mock_scores > 0.5, "doublet", "singlet")

# Add to SCE
coldata(sce)$scDblFinder.score <- mock_scores
coldata(sce)$scDblFinder.class <- mock_class

# Summary
cat("\nPrediction summary:\n")
print(table(sce$scDblFinder.class))

# -----------------------------------------------------------------------------
# Step 6: Summarize results
# -----------------------------------------------------------------------------
cat("\n[Step 6] Summarizing results...\n")

summary <- summarize_scdblfinder_results(sce)
cat(sprintf("  Total cells: %d\n", summary$n_cells))
cat(sprintf("  Doublets: %d (%.1f%%)\n", summary$n_doublets, 100 * summary$doublet_rate))
cat(sprintf("  Singlets: %d\n", summary$n_singlets))
cat(sprintf("  Mean score: %.3f\n", summary$mean_score))

# -----------------------------------------------------------------------------
# Step 7: Filter doublets
# -----------------------------------------------------------------------------
cat("\n[Step 7] Filtering doublets...\n")

sce_filtered <- filter_scdblfinder(sce, remove_doublets = TRUE)
cat(sprintf("  Cells after filtering: %d\n", ncol(sce_filtered)))

# -----------------------------------------------------------------------------
# Step 8: Export example
# -----------------------------------------------------------------------------
cat("\n[Step 8] Export example...\n")

results_df <- data.frame(
  cell = colnames(sce),
  scDblFinder.score = sce$scDblFinder.score,
  scDblFinder.class = sce$scDblFinder.class,
  stringsAsFactors = FALSE
)

write.csv(results_df, "minimal_scdblfinder_results.csv", row.names = FALSE)
cat("  Exported: minimal_scdblfinder_results.csv\n")

cat("\n", rep("=", 70), "\n", sep = "")
cat("Minimal example complete!\n")
cat(rep("=", 70), "\n", sep = "")
