# Minimal Example: DoubletFinder Doublet Detection
# =================================================
#
# This example demonstrates the basic workflow for detecting doublets
# using DoubletFinder.

library(Seurat)

# Source the core analysis functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# -------------------------------------------------------------------------
# Step 1: Load and preprocess data
# -------------------------------------------------------------------------
cat("[Step 1] Loading and preprocessing data...\n")

# Load your Seurat object
# seurat_obj <- readRDS("your_data.rds")

# Preprocess (if not already done)
# seurat_obj <- NormalizeData(seurat_obj)
# seurat_obj <- FindVariableFeatures(seurat_obj)
# seurat_obj <- ScaleData(seurat_obj)
# seurat_obj <- RunPCA(seurat_obj)
# seurat_obj <- RunUMAP(seurat_obj, dims = 1:20)
# seurat_obj <- FindNeighbors(seurat_obj, dims = 1:20)
# seurat_obj <- FindClusters(seurat_obj, resolution = 0.5)

cat("Note: Replace with your actual data loading\n")
cat("Required preprocessing: NormalizeData, FindVariableFeatures,\n")
cat("  ScaleData, RunPCA (or SCTransform alternative)\n\n")

# -------------------------------------------------------------------------
# Step 2: Run parameter sweep for optimal pK
# -------------------------------------------------------------------------
cat("[Step 2] Running parameter sweep...\n")

# Run parameter sweep to find optimal pK
# sweep_results <- run_param_sweep(
#   seurat_obj,
#   PCs = 1:20,
#   sct = FALSE,
#   num.cores = 1
# )

# Optimal pK is automatically identified
# optimal_pk <- sweep_results$optimal_pk
# cat("Optimal pK:", optimal_pk, "\n")

cat("- Testing pK values from 0.0005 to 0.3\n")
cat("- Using mean-variance normalized bimodality coefficient\n")
cat("- Optimal pK identified from maximum BCmvn\n\n")

# -------------------------------------------------------------------------
# Step 3: Estimate expected doublets
# -------------------------------------------------------------------------
cat("[Step 3] Estimating expected doublets...\n")

# Option 1: Based on 10x doublet rate
# nExp_poi <- estimate_doublet_rate(ncol(seurat_obj), method = "10x")

# Option 2: Based on platform-specific rate
# nExp_poi <- estimate_expected_doublets(ncol(seurat_obj), platform = "10x_v3")

# Option 3: Manual specification
# nExp_poi <- round(0.075 * ncol(seurat_obj))  # 7.5% for standard loading

cat("- 10x v3: ~0.8% per 1000 cells\n")
cat("- Adjust based on your loading density\n\n")

# -------------------------------------------------------------------------
# Step 4: Run DoubletFinder
# -------------------------------------------------------------------------
cat("[Step 4] Running DoubletFinder...\n")

# Run DoubletFinder with optimal pK
# seurat_obj <- run_doubletfinder(
#   seurat_obj,
#   PCs = 1:20,
#   pN = 0.25,
#   pK = optimal_pk,
#   nExp = nExp_poi,
#   sct = FALSE
# )

cat("- Created artificial doublets (pN=0.25)\n")
cat("- Computed pANN scores\n")
cat("- Classified cells as Singlet or Doublet\n\n")

# -------------------------------------------------------------------------
# Step 5: Visualize results
# -------------------------------------------------------------------------
cat("[Step 5] Visualizing results...\n")

# Plot doublets on embedding
# p1 <- plot_doublet_embedding(seurat_obj, reduction = "umap")
# print(p1)

# Plot pK optimization
# p2 <- plot_pk_optimization(sweep_results$bcmvn)
# print(p2)

# Plot pANN distribution
# p3 <- plot_pann_distribution(seurat_obj)
# print(p3)

cat("- Doublet predictions on UMAP\n")
cat("- pK optimization plot\n")
cat("- pANN score distribution\n\n")

# -------------------------------------------------------------------------
# Step 6: Filter doublets (optional)
# -------------------------------------------------------------------------
cat("[Step 6] Filtering doublets...\n")

# Get summary before filtering
# summary <- get_doublet_summary(seurat_obj)
# print(summary)

# Filter doublets
# seurat_filtered <- filter_doublets(seurat_obj, keep = "Singlet")

cat("- Original cells: [number]\n")
cat("- After filtering: [number]\n")
cat("- Removed: [number] predicted doublets\n\n")

# -------------------------------------------------------------------------
# Step 7: Export results
# -------------------------------------------------------------------------
cat("[Step 7] Exporting results...\n")

# Export doublet predictions
# export_doublet_predictions(
#   seurat_obj,
#   output_file = "doublet_predictions.csv",
#   include_pANN = TRUE
# )

# Save filtered object
# saveRDS(seurat_filtered, "seurat_filtered.rds")

cat("- Doublet predictions exported\n")
cat("- Filtered Seurat object saved\n\n")

cat("Analysis complete!\n")
