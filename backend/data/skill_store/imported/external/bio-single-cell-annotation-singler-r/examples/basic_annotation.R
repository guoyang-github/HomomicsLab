# Basic SingleR annotation example using skill helpers

library(Seurat)
library(SingleR)
library(celldex)

# Source skill helpers
source("../scripts/r/singler_annotation.R")

# Example: Use pbmc_small from Seurat
data("pbmc_small", package = "Seurat")
seurat_obj <- pbmc_small

cat("SingleR Annotation Example\n")
cat(strrep("=", 40), "\n")

# Step 1: Load reference using skill helper
cat("\n1. Loading Monaco Immune reference...\n")
ref <- load_singler_reference("monaco")

# Step 2: Run SingleR annotation using skill wrapper
cat("\n2. Running SingleR annotation...\n")
seurat_obj <- run_singler_annotation(
  seurat_obj,
  ref = ref,
  label_col = "label.main",
  de.method = "wilcox",
  prune = TRUE
)

# View results
cat("\n3. Cell type counts:\n")
print(table(seurat_obj$SingleR_label))

# Step 4: Quality check
cat("\n4. Plotting quality metrics...\n")
plot_singler_quality(seurat_obj)

# Step 5: Filter low-confidence annotations
cat("\n5. Filtering by confidence...\n")
seurat_obj <- filter_singler_by_confidence(seurat_obj)

cat("\nHigh-confidence annotations:\n")
print(table(seurat_obj$SingleR_filtered))

cat("\nDone!\n")
