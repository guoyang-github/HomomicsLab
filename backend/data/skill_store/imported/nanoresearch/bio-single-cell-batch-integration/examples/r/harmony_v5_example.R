# Example: Harmony integration with Seurat V5
# Reference: Seurat 5.0+, harmony 1.0+
#
# Demonstrates loading multiple RDS files and running Harmony
# via IntegrateLayers (official V5 method).

library(Seurat)

# Source the integration function
source("../../scripts/r/seurat-v5/integrate.R")

# Load individual samples
sample_files <- c("sample1.rds", "sample2.rds", "sample3.rds")
samples <- lapply(sample_files, readRDS)
names(samples) <- gsub("\\.rds$", "", basename(sample_files))

# QC per sample
samples <- lapply(samples, function(x) {
  x[["percent.mt"]] <- PercentageFeatureSet(x, pattern = "^MT-")
  subset(x, nFeature_RNA > 200 & nFeature_RNA < 8000 & percent.mt < 15)
})

# Merge (V5 auto-creates layers)
obj <- merge(samples[[1]], y = samples[-1],
             add.cell.ids = names(samples))

# Run Harmony integration
obj <- integrate_v5_standard(obj, method = "harmony", npcs = 50)

# Visualize
pdf("harmony_umap.pdf", width = 10, height = 5)
DimPlot(obj, reduction = "umap", group.by = "sample")
dev.off()

# Differential expression
markers <- FindAllMarkers(obj, only.pos = TRUE, min.pct = 0.25,
                         logfc.threshold = 0.25)
write.csv(markers, "harmony_markers.csv", row.names = FALSE)

# Save
saveRDS(obj, "harmony_integrated.rds")
cat("Integration complete.\n")
