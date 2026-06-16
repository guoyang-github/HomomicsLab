# Basic ScType Annotation Example
# Demonstrates standard workflow using built-in marker database

library(Seurat)
library(dplyr)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source ScType functions
source(file.path(base_dir, "scripts", "r", "sctype_annotation.R"))

# Load example data (or use your own)
example_file <- file.path(base_dir, "assets", "markers", "example_data.RDS")

if (file.exists(example_file)) {
  message("Loading example data...")
  pbmc <- readRDS(example_file)
} else {
  message("Example data not found. Creating minimal test data...")
  # Create minimal test data if example not available
  set.seed(42)
  counts <- matrix(rpois(2000, 5), nrow = 100, ncol = 200)
  rownames(counts) <- paste0("GENE", 1:100)

  # Add some immune markers
  rownames(counts)[1:10] <- c("CD3D", "CD3E", "CD4", "CD8A", "CD8B",
                             "CD79A", "CD79B", "LYZ", "CD14", "IL7R")

  pbmc <- CreateSeuratObject(counts = counts)
  pbmc <- NormalizeData(pbmc)
  pbmc <- FindVariableFeatures(pbmc)
  pbmc <- ScaleData(pbmc)
  pbmc <- RunPCA(pbmc, features = rownames(pbmc))
  pbmc <- FindNeighbors(pbmc, dims = 1:10)
  pbmc <- FindClusters(pbmc, resolution = 0.8)
  pbmc <- RunUMAP(pbmc, dims = 1:10)
}

# Check available tissues
message("\n=== Available Tissues ===")
tissues <- get_available_tissues(db_source = "full")
print(tissues)

# Run ScType annotation with Immune system markers
message("\n=== Running ScType Annotation ===")
pbmc <- run_sctype_annotation(
  pbmc,
  tissue = "Immune system",
  slot = "data",
  cluster_col = "seurat_clusters",
  output_col = "sctype_cell_type",
  plot_results = TRUE
)

# View results
message("\n=== Cell Type Distribution ===")
print(table(pbmc$sctype_cell_type))

message("\n=== Cluster vs Cell Type ===")
celltype_table <- table(pbmc$seurat_clusters, pbmc$sctype_cell_type)
print(celltype_table)

# Visualize
if ("umap" %in% names(pbmc@reductions)) {
  p1 <- DimPlot(pbmc, reduction = "umap", group.by = "seurat_clusters",
                label = TRUE, repel = TRUE) + ggtitle("Clusters")
  p2 <- DimPlot(pbmc, reduction = "umap", group.by = "sctype_cell_type",
                label = TRUE, repel = TRUE) + ggtitle("ScType Annotation")

  print(p1 + p2)
}

# Save annotated object
output_file <- "pbmc_annotated.rds"
saveRDS(pbmc, output_file)
message(paste("\nAnnotated object saved to:", output_file))

message("\n=== Example Complete ===")
