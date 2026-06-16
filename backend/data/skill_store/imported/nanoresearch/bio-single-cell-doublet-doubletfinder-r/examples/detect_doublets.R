# DoubletFinder Doublet Detection Example

library(Seurat)
library(DoubletFinder)

# Load example data (or your own)
data("pbmc_small", package = "Seurat")
seurat_obj <- pbmc_small

print("DoubletFinder Doublet Detection Example")
cat(strrep("=", 40), "\n")

# Step 1: Preprocess
print("\n1. Preprocessing...")
seurat_obj <- NormalizeData(seurat_obj)
seurat_obj <- FindVariableFeatures(seurat_obj)
seurat_obj <- ScaleData(seurat_obj)
seurat_obj <- RunPCA(seurat_obj, npcs = 20)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:20)

# Step 2: Determine optimal pK
print("\n2. Finding optimal pK value...")
sweep.res <- paramSweep(seurat_obj, PCs = 1:20, sct = FALSE)
sweep.stats <- summarizeSweep(sweep.res, GT = FALSE)
bcmvn <- find.pK(sweep.stats)

optimal_pK <- as.numeric(as.character(bcmvn$pK[which.max(bcmvn$BCmetric)]))
print(paste("   Optimal pK:", optimal_pK))

# Step 3: Estimate homotypic doublet proportion
print("\n3. Estimating homotypic doublets...")
annotations <- seurat_obj$RNA_snn_res.0.8  # Use existing clusters
homotypic.prop <- modelHomotypic(annotations)

# Estimate doublet formation rate (typically 7.5% for 10x)
nExp_poi <- round(0.075 * ncol(seurat_obj))
nExp_poi.adj <- round(nExp_poi * (1 - homotypic.prop))

# Step 4: Run DoubletFinder
print("\n4. Running DoubletFinder...")
seurat_obj <- doubletFinder(
  seurat_obj,
  PCs = 1:20,
  pN = 0.25,
  pK = optimal_pK,
  nExp = nExp_poi.adj,
  reuse.pANN = FALSE,
  sct = FALSE
)

# View results
print("\n5. Results:")
doublet_col <- grep("DF.classifications", colnames(seurat_obj@meta.data), value = TRUE)[1]
print(table(seurat_obj[[doublet_col]]))

# Step 5: Filter doublets
print("\n6. Filtering doublets...")
seurat_filtered <- subset(seurat_obj, subset = !!as.symbol(doublet_col) == "Singlet")
print(paste("   Cells before:", ncol(seurat_obj)))
print(paste("   Cells after:", ncol(seurat_filtered)))

# Step 6: Visualize
print("\n7. Visualizing doublets...")
DimPlot(seurat_obj, group.by = doublet_col, cols = c("red", "blue"))
