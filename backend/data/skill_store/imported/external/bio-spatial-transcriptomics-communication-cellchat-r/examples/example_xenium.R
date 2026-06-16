#!/usr/bin/env Rscript
#' SpatialCellChat Spatial Analysis Example - Xenium/Visium HD
#'
#' Demonstrates spatial cell-cell communication analysis on single-cell
#' resolution spatial data (Xenium, Visium HD, CosMx, etc.) using SpatialCellChat.

# =============================================================================
# Setup
# =============================================================================

library(Seurat)

# Source the SpatialCellChat spatial module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "cellchat_spatial.R"))

message("=== SpatialCellChat Analysis Example (Xenium/Visium HD) ===\n")

# =============================================================================
# Step 1: Load Single-Cell Resolution Spatial Data
# =============================================================================

message("Step 1: Loading Xenium/Visium HD data...")
message("  Note: Replace with your actual data loading code")

# Example for Xenium data loading:
# xenium_data <- LoadXenium(
#   data.dir = "path/to/xenium/outs",
#   fov = "fov"
# )

# Example for Visium HD:
# visium_hd <- Load10X_Spatial(
#   data.dir = "path/to/visium_hd/outs",
#   filename = "filtered_feature_bc_matrix.h5"
# )

# For this example, create simulated single-cell resolution data
set.seed(42)
n_cells <- 500
n_genes <- 1000

counts <- matrix(
  rpois(n_cells * n_genes, lambda = 3),
  nrow = n_genes,
  ncol = n_cells
)
rownames(counts) <- paste0("GENE_", 1:n_genes)
colnames(counts) <- paste0("cell_", 1:n_cells)

# Create Seurat object
xenium_data <- CreateSeuratObject(counts = counts)

# Add cell type annotations
cell_types <- sample(
  c("Tumor", "T_cell", "B_cell", "Macrophage", "Fibroblast", "Endothelial"),
  n_cells,
  replace = TRUE,
  prob = c(0.25, 0.15, 0.1, 0.15, 0.2, 0.15)
)
xenium_data$cell_type <- cell_types

# Add spatial coordinates (already in micrometers for Xenium)
xenium_data@images <- list(
  fov <- list(
    coordinates <- data.frame(
      x <- runif(n_cells, min = 0, max = 5000),  # um
      y <- runif(n_cells, min = 0, max = 5000),  # um
      row.names = colnames(xenium_data)
    )
  )
)

message(sprintf("  Loaded: %d cells, %d genes", n_cells, n_genes))
message(sprintf("  Cell types: %s", paste(table(cell_types), collapse = ", ")))

# =============================================================================
# Step 2: Run SpatialCellChat on Single-Cell Resolution Data
# =============================================================================

message("\nStep 2: Running SpatialCellChat on single-cell resolution data...")

message("\n  For Xenium data:")
message("    cellchat <- run_cellchat_sc_resolution(")
message("      seurat_obj = xenium_data,")
message("      group_by = 'cell_type',")
message("      spatial_tech = 'xenium',")
message("      spot_size = 10,           # Typical cell diameter in um")
message("      interaction_range = 250,  # Max communication distance")
message("      contact_range = 10        # Contact-dependent range")
message("    )")

message("\n  For Visium HD data:")
message("    cellchat <- run_cellchat_sc_resolution(")
message("      seurat_obj = visium_hd,")
message("      group_by = 'cell_type',")
message("      spatial_tech = 'visium_hd',")
message("      spot_size = 10,")
message("      interaction_range = 250,")
message("      contact_range = 10")
message("    )")

message("\n  For CosMx data:")
message("    cellchat <- run_cellchat_sc_resolution(")
message("      seurat_obj = cosmx_data,")
message("      group_by = 'cell_type',")
message("      spatial_tech = 'cosmx',")
message("      spot_size = 10,")
message("      interaction_range = 250")
message("    )")

# Note: CosMx requires pixel-to-um conversion (ratio = 0.12028)

# =============================================================================
# Step 3: Key Differences from Visium
# =============================================================================

message("\n=== Key Differences from Visium Analysis ===")

message("\n1. Spatial Coordinates:")
message("   - Visium: In pixels, require conversion via scalefactors")
message("   - Xenium/Visium HD: Already in micrometers (ratio = 1)")

message("\n2. Contact Range:")
message("   - Visium: ~100 um (spot center-to-center)")
message("   - Xenium: ~10 um (typical cell diameter)")

message("\n3. Cell Types:")
message("   - Visium: Cell types from deconvolution (RCTD, SPOTlight)")
message("   - Xenium: Direct cell type annotation from segmentation")

message("\n4. Analysis Focus:")
message("   - Visium: Spot-level communication with group-level aggregation")
message("   - Xenium: Cell-level communication (single-cell resolution)")

message("\n5. Group-Level Computation:")
message("   - Visium: Use computeAvgCommunProb_Visium() with deconvolution")
message("   - Xenium: Direct cell-level inference, no aggregation needed")

# =============================================================================
# Step 4: Visualization Examples
# =============================================================================

message("\n=== Visualization Examples ===")

message("\n  Spatial network with incoming signaling weights:")
message("    SpatialCellChat::netVisual_aggregate(")
message("      cellchat,")
message("      signaling = 'CXCL',")
message("      layout = 'spatial',")
message("      vertex.weight = 'incoming',")
message("      vertex.size.max = 4,")
message("      alpha.image = 0.2")
message("    )")

message("\n  Communication hot spots:")
message("    SpatialCellChat::spatialGiPlot(")
message("      cellchat,")
message("      slot.name = 'netP',")
message("      signaling.name = 'CXCL',")
message("      measure = 'indeg'")
message("    )")

message("\n  Centrality scores heatmap:")
message("    netAnalysis_signalingRole_network(")
message("      cellchat,")
message("      signaling = 'CXCL',")
message("      slot.name = 'netP',")
message("      measure = c('outdeg', 'indeg'),")
message("      width = 8,")
message("      height = 2.5")
message("    )")

message("\n  Communication scoring on tissue:")
message("    plot_spatial_scoring(")
message("      cellchat,")
message("      signaling = 'CXCL',")
message("      slot_name = 'netP',")
message("      merge = TRUE")
message("    )")

message("\n  Gene expression on tissue:")
message("    SpatialCellChat::spatialFeaturePlot(")
message("      cellchat,")
message("      features = c('CXCL12', 'CXCR4')")
message("    )")

# =============================================================================
# Summary
# =============================================================================

message("\n=== Analysis Summary ===")
message("\nFor single-cell resolution spatial data:")
message("  - Coordinates are already in micrometers (no conversion needed)")
message("  - Contact range is typically cell diameter (~10 um)")
message("  - Higher resolution enables true cell-level communication analysis")
message("  - No deconvolution or group-level aggregation needed")
message("  - Consider computational cost for large cell numbers (>10K cells)")

message("\nRecommended parameters:")
message("  Technology     | ratio | tol | contact.range")
message("  ---------------|-------|-----|---------------")
message("  Xenium         | 1.0   | 5   | 10")
message("  Visium HD      | 1.0   | 5   | 10")
message("  CosMx          | 0.12  | auto| 10")
message("  Slide-seq      | 0.73  | 5   | 10")
message("  seqFISH/merFISH| 1.0   | 5   | 10")
