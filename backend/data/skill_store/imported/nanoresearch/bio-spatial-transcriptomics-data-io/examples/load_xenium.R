#' Load 10X Xenium Spatial Data in R
#' Reference: Seurat 5.0+ | Verify API if version differs

library(Seurat)

# Source the spatial data I/O module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "spatial_data_io.R"))

message("=== Loading 10X Xenium Data (R) ===\n")

# =============================================================================
# Step 1: Load Xenium Data
# =============================================================================

message("Step 1: Loading Xenium data...")
message("  Note: Replace with your actual Xenium output path")

# Example loading code:
# seurat_obj <- load_xenium(
#   data.dir = "xenium_output/",
#   fov = "fov",
#   assay = "Xenium"
# )

# For demonstration, create a minimal simulated object
set.seed(42)
n_cells <- 500
n_genes <- 1000
counts <- Matrix::Matrix(
  rpois(n_cells * n_genes, lambda = 3),
  nrow = n_genes,
  ncol = n_cells,
  sparse = TRUE
)
rownames(counts) <- paste0("GENE_", 1:n_genes)
colnames(counts) <- paste0("cell_", 1:n_cells)

seurat_obj <- CreateSeuratObject(counts = counts, assay = "Xenium")

# Add mock spatial coordinates (in micrometers for Xenium)
seurat_obj@images[["fov"]] <- new(
  Class = "SlideSeq",
  assay = "Xenium",
  key = "fov_",
  coordinates = data.frame(
    x = runif(n_cells, 0, 5000),
    y = runif(n_cells, 0, 5000),
    row.names = colnames(seurat_obj)
  ),
  scale.factors = new(
    Class = "scalefactors",
    spot = 10,
    fiducial = 10,
    hires = 1.0,
    lowres = 1.0
  )
)

message(sprintf("  Loaded: %d cells x %d genes", ncol(seurat_obj), nrow(seurat_obj)))

# =============================================================================
# Step 2: Access Spatial Information
# =============================================================================

message("\nStep 2: Accessing spatial information...")

coords <- get_spatial_coords(seurat_obj, image = "fov")
message(sprintf("  Coordinate range: x=[%.0f, %.0f], y=[%.0f, %.0f]",
                min(coords[, 1]), max(coords[, 1]),
                min(coords[, 2]), max(coords[, 2])))

# =============================================================================
# Step 3: Add Cell Type Annotations
# =============================================================================

message("\nStep 3: Adding annotations...")

seurat_obj$sample <- "Xenium_S1"
seurat_obj$cell_type <- sample(
  c("Tumor", "T_cell", "B_cell", "Macrophage", "Fibroblast", "Endothelial"),
  n_cells,
  replace = TRUE,
  prob = c(0.25, 0.15, 0.1, 0.15, 0.2, 0.15)
)

message(sprintf("  Cell types: %s", paste(table(seurat_obj$cell_type), collapse = ", ")))

# =============================================================================
# Step 4: QC Summary
# =============================================================================

message("\nStep 4: QC summary...")
message(sprintf("  Mean counts per cell: %.0f", mean(seurat_obj$nCount_Xenium)))
message(sprintf("  Mean genes per cell: %.0f", mean(seurat_obj$nFeature_Xenium)))

# =============================================================================
# Step 5: Save
# =============================================================================

message("\nStep 5: Saving...")
saveRDS(seurat_obj, file = "xenium_loaded.rds")
message("  Saved to: xenium_loaded.rds")

message("\n=== Done ===")
