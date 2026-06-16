# scDblFinder Doublet Detection Example
# ======================================
#
# Example workflow using scDblFinder wrapper functions

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

library(Seurat)
library(scDblFinder)
library(SingleCellExperiment)

print("scDblFinder Doublet Detection Example")
print("======================================")

# Load example data (or your own)
data("pbmc_small", package = "Seurat")
seurat_obj <- pbmc_small

print(paste("Input cells:", ncol(seurat_obj)))

# Method 1: Run directly with Seurat object
print("\nMethod 1: Using wrapper function with Seurat...")
seurat_obj <- run_scdblfinder_seurat(
  seurat_obj,
  clusters = "seurat_clusters",  # Use Seurat clusters
  nfeatures = 1000,
  verbose = TRUE
)

print("\nResults:")
print(table(seurat_obj$scDblFinder_class))

# Method 2: Manual workflow with SingleCellExperiment
print("\nMethod 2: Manual workflow...")
sce <- as.SingleCellExperiment(seurat_obj)

# Validate
validation <- validate_scdblfinder_input(sce)
print(paste("Valid input:", validation$valid))

# Run scDblFinder
sce <- scDblFinder(
  sce,
  clusters = TRUE,
  nfeatures = 1000,
  verbose = TRUE
)

# Add back to Seurat
seurat_obj$scDblFinder_class2 <- sce$scDblFinder.class

# Filter doublets
print("\nFiltering doublets...")
seurat_filtered <- subset(seurat_obj, subset = scDblFinder_class == "singlet")
print(paste("Cells before:", ncol(seurat_obj)))
print(paste("Cells after:", ncol(seurat_filtered)))

# Visualize
print("\nVisualizing...")
DimPlot(seurat_obj, group.by = "scDblFinder_class")
FeaturePlot(seurat_obj, features = "scDblFinder_score")

print("\nDone!")
