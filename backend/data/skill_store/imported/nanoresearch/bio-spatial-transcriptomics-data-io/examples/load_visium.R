#' Load 10X Visium Spatial Data in R
#' Reference: Seurat 5.0+ | Verify API if version differs

library(Seurat)

# Source the spatial data I/O module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "spatial_data_io.R"))

message("=== Loading 10X Visium Data (R) ===\n")

# =============================================================================
# Step 1: Load Visium Data from Space Ranger Output
# =============================================================================

message("Step 1: Loading Visium data...")
message("  Note: Replace with your actual Space Ranger output path")

# Example loading code:
# seurat_obj <- load_visium(
#   data.dir = "spaceranger_output/",
#   filename = "filtered_feature_bc_matrix.h5",
#   assay = "Spatial",
#   slice = "slice1"
# )

# For demonstration, create a minimal simulated object
set.seed(42)
n_spots <- 100
n_genes <- 500
counts <- Matrix::Matrix(
  rpois(n_spots * n_genes, lambda = 5),
  nrow = n_genes,
  ncol = n_spots,
  sparse = TRUE
)
rownames(counts) <- paste0("GENE_", 1:n_genes)
colnames(counts) <- paste0("spot_", 1:n_spots)

seurat_obj <- CreateSeuratObject(counts = counts, assay = "Spatial")

# Add mock spatial coordinates and image for demonstration
seurat_obj@images[["slice1"]] <- new(
  Class = "SlideSeq",
  assay = "Spatial",
  key = "slice1_",
  coordinates = data.frame(
    x = runif(n_spots, 0, 2000),
    y = runif(n_spots, 0, 2000),
    row.names = colnames(seurat_obj)
  ),
  scale.factors = new(
    Class = "scalefactors",
    spot = 100,
    fiducial = 100,
    hires = 0.5,
    lowres = 0.1
  )
)

message(sprintf("  Loaded: %d spots x %d genes", ncol(seurat_obj), nrow(seurat_obj)))

# =============================================================================
# Step 2: Access Spatial Coordinates and Scale Factors
# =============================================================================

message("\nStep 2: Accessing spatial information...")

# Extract spatial coordinates
coords <- get_spatial_coords(seurat_obj)
message(sprintf("  Coordinate range: x=[%.0f, %.0f], y=[%.0f, %.0f]",
                min(coords[, 1]), max(coords[, 1]),
                min(coords[, 2]), max(coords[, 2])))

# Extract scale factors
sf <- get_scalefactors(seurat_obj)
message(sprintf("  Spot diameter (fullres): %.1f pixels", sf@spot))
message(sprintf("  Hires scale factor: %.4f", sf@hires))

# Load from JSON (for real data)
# sf_json <- load_scalefactors_json("spaceranger_output/spatial/scalefactors_json.json")
# conversion_factor <- 65 / sf_json$spot_diameter_fullres

# =============================================================================
# Step 3: Add Metadata and Subset
# =============================================================================

message("\nStep 3: Working with metadata...")

# Add sample annotation
seurat_obj$sample <- "Visium_S1"

# Add cell type annotations (e.g., from deconvolution)
seurat_obj$cell_type <- sample(
  c("Tumor", "T_cell", "Macrophage", "Fibroblast", "Endothelial"),
  n_spots,
  replace = TRUE
)

message(sprintf("  Cell types: %s", paste(table(seurat_obj$cell_type), collapse = ", ")))

# Subset by spatial region (example: central region)
x_range <- range(coords[, 1])
y_range <- range(coords[, 2])
center_spots <- rownames(coords)[
  coords[, 1] > x_range[1] + 0.3 * diff(x_range) &
  coords[, 1] < x_range[2] - 0.3 * diff(x_range) &
  coords[, 2] > y_range[1] + 0.3 * diff(y_range) &
  coords[, 2] < y_range[2] - 0.3 * diff(y_range)
]
seurat_subset <- subset(seurat_obj, cells = center_spots)
message(sprintf("  Subset to %d spots in central region", ncol(seurat_subset)))

# =============================================================================
# Step 4: Save Results
# =============================================================================

message("\nStep 4: Saving Seurat object...")
saveRDS(seurat_obj, file = "visium_loaded.rds")
message("  Saved to: visium_loaded.rds")

message("\n=== Done ===")
