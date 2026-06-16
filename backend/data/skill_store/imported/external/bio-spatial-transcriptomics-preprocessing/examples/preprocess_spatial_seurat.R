# Preprocess 10x Visium spatial transcriptomics data with Seurat
# Reference: Seurat 5.x+ | Verify API if version differs

library(Seurat)

# Step 1: Load Visium data -----------------------------------------------------
spatial_obj <- Load10X_Spatial(
    data.dir = "spatial/",
    filename = "filtered_feature_bc_matrix.h5",
    assay = "Spatial",
    slice = "slice1"
)
cat("Raw:", ncol(spatial_obj), "spots,", nrow(spatial_obj), "genes\n")

# Step 2: QC visualization -----------------------------------------------------
# Violin plots
VlnPlot(spatial_obj, features = c("nCount_Spatial", "nFeature_Spatial"),
        ncol = 2, pt.size = 0)

# Spatial QC maps
SpatialFeaturePlot(spatial_obj, features = "nCount_Spatial")
SpatialFeaturePlot(spatial_obj, features = "nFeature_Spatial")

# Step 3: Filter spots ---------------------------------------------------------
# Spatial thresholds are more lenient than single-cell (spots contain multiple cells)
spatial_obj <- subset(
    spatial_obj,
    subset = nCount_Spatial > 200 &
             nFeature_Spatial > 100
)
cat("After filtering:", ncol(spatial_obj), "spots\n")

# Step 4: SCTransform normalization --------------------------------------------
# Recommended for spatial data; return.only.var.genes = FALSE retains all genes
spatial_obj <- SCTransform(
    spatial_obj,
    assay = "Spatial",
    vars.to.regress = "percent.mt",
    return.only.var.genes = FALSE,
    verbose = FALSE
)
cat("HVGs:", length(VariableFeatures(spatial_obj)), "\n")

# Step 5: Dimensionality reduction and clustering ------------------------------
spatial_obj <- RunPCA(spatial_obj, assay = "SCT")
spatial_obj <- FindNeighbors(spatial_obj, reduction = "pca", dims = 1:30)
spatial_obj <- FindClusters(spatial_obj, resolution = 0.8)
spatial_obj <- RunUMAP(spatial_obj, reduction = "pca", dims = 1:30)

# Step 6: Spatial visualization ------------------------------------------------
SpatialDimPlot(spatial_obj, label = TRUE, pt.size.factor = 1.6)
DimPlot(spatial_obj, reduction = "umap", label = TRUE)

# Step 7: Spatially variable features ------------------------------------------
spatial_obj <- FindSpatiallyVariableFeatures(
    spatial_obj,
    assay = "SCT",
    selection.method = "moransi",
    features = VariableFeatures(spatial_obj)[1:1000],
    nfeatures = 50
)
top_svgs <- SpatiallyVariableFeatures(spatial_obj, selection.method = "moransi")
cat("Top SVGs:", head(top_svgs, 6), "\n")

# Visualize top SVGs
SpatialFeaturePlot(spatial_obj, features = head(top_svgs, 6),
                   ncol = 3, pt.size.factor = 1.6)

# Step 8: Save -----------------------------------------------------------------
saveRDS(spatial_obj, file = "spatial_preprocessed.rds")
cat("Saved preprocessed spatial data\n")
