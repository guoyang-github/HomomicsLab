#!/usr/bin/env Rscript
#' SpatialCellChat Spatial Analysis Example - 10X Visium
#'
#' Demonstrates spatial cell-cell communication analysis on 10X Visium data
#' using SpatialCellChat (CellChat v3).

# =============================================================================
# Setup
# =============================================================================

# Load required packages
if (!requireNamespace("Seurat", quietly = TRUE)) {
  install.packages("Seurat")
}
if (!requireNamespace("SpatialCellChat", quietly = TRUE)) {
  remotes::install_github("jinworks/SpatialCellChat")
}

library(Seurat)
library(SpatialCellChat)

# Source the SpatialCellChat spatial module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "cellchat_spatial.R"))

message("=== SpatialCellChat Visium Analysis Example ===\n")

# =============================================================================
# Step 1: Load Visium Data
# =============================================================================

message("Step 1: Loading 10X Visium data...")
message("  Note: Replace with your actual Visium data path")

# Example loading code (replace with your data)
# visium_data <- Load10X_Spatial(
#   data.dir = "path/to/spaceranger/outs",
#   filename = "filtered_feature_bc_matrix.h5"
# )

# For this example, we create simulated data
set.seed(42)
n_spots <- 200
n_genes <- 500

counts <- matrix(
  rpois(n_spots * n_genes, lambda = 5),
  nrow = n_genes,
  ncol = n_spots
)
rownames(counts) <- paste0("GENE_", 1:n_genes)
colnames(counts) <- paste0("spot_", 1:n_spots)

# Create Seurat object
visium_data <- CreateSeuratObject(counts = counts)

# Add cell type annotations (from deconvolution or clustering)
cell_types <- sample(
  c("Tumor", "T_cell", "B_cell", "Macrophage", "Endothelial"),
  n_spots,
  replace = TRUE,
  prob = c(0.3, 0.2, 0.15, 0.2, 0.15)
)
visium_data$cell_type <- cell_types

# Add mock spatial coordinates
visium_data@images <- list(
  slice1 = list(
    coordinates = data.frame(
      imagerow = sample(1:1000, n_spots),
      imagecol = sample(1:1000, n_spots),
      row.names = colnames(visium_data)
    )
  )
)

message(sprintf("  Loaded: %d spots, %d genes", n_spots, n_genes))
message(sprintf("  Cell types: %s", paste(table(cell_types), collapse = ", ")))

# =============================================================================
# Step 2: Prepare Scalefactors (for real data)
# =============================================================================

message("\nStep 2: Preparing spatial scalefactors...")
message("  For real Visium data, load from: spatial/scalefactors_json.json")

# Example scalefactors structure for Visium:
# {
#   "regist_target_img_scalef": 0.5,
#   "tissue_hires_scalef": 0.5,
#   "tissue_lowres_scalef": 0.1,
#   "spot_diameter_fullres": 100
# }

# Create mock scalefactors for example
mock_scalefactors <- list(
  spot_diameter_fullres = 100,
  tissue_hires_scalef = 0.5
)

# Save to temp file for demonstration
scalefactors_file <- tempfile("scalefactors_", fileext = ".json")
jsonlite::write_json(mock_scalefactors, scalefactors_file, auto_unbox = TRUE)

message(sprintf("  Spot diameter: %.1f pixels", mock_scalefactors$spot_diameter_fullres))

# =============================================================================
# Step 3: Run SpatialCellChat Visium Analysis
# =============================================================================

message("\nStep 3: Running SpatialCellChat Visium analysis...")
message("  This may take a few minutes for large datasets...")

# For demonstration, we'll show the code structure
# In practice, you would run:
# cellchat <- run_cellchat_visium(
#   seurat_obj = visium_data,
#   group_by = "cell_type",
#   sample_name = "Visium_Example",
#   scalefactors_json = scalefactors_file,
#   assay = "Spatial",
#   interaction_range = 250,
#   contact_range = 100,
#   signaling_type = c("Secreted Signaling", "ECM-Receptor", "Cell-Cell Contact"),
#   min_cells = 10,
#   min_links = 10
# )

message("  Note: Full analysis skipped in example (requires SpatialCellChat)")
message("  Code structure demonstrated above")

# =============================================================================
# Step 3b: Visium with Deconvolution (Advanced)
# =============================================================================

message("\nStep 3b: Visium with cell type decomposition...")
message("  For deconvoluted Visium, provide cell type proportions:")

# Create mock deconvolution proportions (spots x cell_types)
# In practice, use output from RCTD, SPOTlight, or cell2location
cell_types_unique <- unique(cell_types)
deconv_proportions <- matrix(0, nrow = n_spots, ncol = length(cell_types_unique))
rownames(deconv_proportions) <- colnames(visium_data)
colnames(deconv_proportions) <- cell_types_unique

# Assign each spot to one cell type (simplified)
for (i in seq_len(n_spots)) {
  deconv_proportions[i, cell_types[i]] <- 1
}

message("\n  With deconvolution proportions:")
message("    cellchat <- run_cellchat_visium(")
message("      seurat_obj = visium_data,")
message("      group_by = 'cell_type',")
message("      scalefactors_json = scalefactors_file,")
message("      assay = 'Spatial',")
message("      cell_type_decomposition = deconv_proportions,")
message("      avg_type = 'avg',")
message("      nboot = 100")
message("    )")

# =============================================================================
# Step 4: Advanced Analysis Options
# =============================================================================

message("\nStep 4: Advanced analysis options...")

message("\n  4.1 Contact-dependent signaling only:")
message("    cellchat_contact <- run_cellchat_visium(")
message("      seurat_obj = visium_data,")
message("      group_by = 'cell_type',")
message("      scalefactors_json = scalefactors_file,")
message("      assay = 'Spatial',")
message("      signaling_type = 'Cell-Cell Contact',")
message("      contact_dependent = TRUE,")
message("      contact_range = 100")
message("    )")

message("\n  4.2 Multiple signaling categories:")
message("    cellchat_multi_signal <- run_cellchat_visium(")
message("      seurat_obj = visium_data,")
message("      group_by = 'cell_type',")
message("      scalefactors_json = scalefactors_file,")
message("      assay = 'Spatial',")
message("      signaling_type = c('Secreted Signaling', 'ECM-Receptor')")
message("    )")

message("\n  4.3 Analyze only selected cell types:")
message("    cellchat_subset <- run_cellchat_visium(")
message("      seurat_obj = visium_data,")
message("      group_by = 'cell_type',")
message("      cell_types = c('Tumor', 'T_cell', 'Macrophage'),")
message("      scalefactors_json = scalefactors_file,")
message("      assay = 'Spatial'")
message("    )")

message("\n  4.4 Filter results by source and target:")
message("    df_filtered <- extract_communication_df(")
message("      cellchat_subset,")
message("      sources.use = c('Macrophage'),")
message("      targets.use = c('T_cell')")
message("    )")

# =============================================================================
# Step 5: Visualization Examples
# =============================================================================

message("\nStep 5: Visualization examples...")

message("\n  5.1 Spatial communication network:")
message("    SpatialCellChat::netVisual_aggregate(")
message("      cellchat,")
message("      signaling = 'CXCL',")
message("      layout = 'spatial'")
message("    )")

message("\n  5.2 Cell type spatial distribution:")
message("    SpatialCellChat::spatialDimPlot(cellchat, point.size = 1.5)")

message("\n  5.3 Gene expression on tissue:")
message("    SpatialCellChat::spatialFeaturePlot(")
message("      cellchat,")
message("      features = c('CXCL12', 'CXCR4')")
message("    )")

message("\n  5.4 Ligand-receptor pair expression:")
message("    SpatialCellChat::spatialFeaturePlot(")
message("      cellchat,")
message("      pairLR.use = 'CXCL12_CXCR4',")
message("      do.binary = FALSE")
message("    )")

message("\n  5.5 Communication distance distribution:")
message("    SpatialCellChat::communicationDistPlot2(cellchat, signaling.type = 'All')")

message("\n  5.6 Communication hot spots:")
message("    SpatialCellChat::spatialGiPlot(")
message("      cellchat,")
message("      slot.name = 'netP',")
message("      signaling.name = 'CXCL',")
message("      measure = 'indeg'")
message("    )")

message("\n  5.7 Communication scoring on tissue:")
message("    plot_spatial_scoring(")
message("      cellchat,")
message("      signaling = 'CXCL',")
message("      slot_name = 'netP',")
message("      measure = c('outdeg', 'indeg')")
message("    )")

message("\n  5.8 Circle plot (aggregated network):")
message("    cellchat <- aggregateNet(cellchat)")
message("    groupSize <- as.numeric(table(cellchat@idents))")
message("    netVisual_circle(")
message("      cellchat@net$count,")
message("      vertex.weight = groupSize,")
message("      weight.scale = TRUE")
message("    )")

# =============================================================================
# Step 6: Extract and Export Results
# =============================================================================

message("\nStep 6: Extracting and exporting results...")

message("\n  Extract all LR communications:")
message("    df_net <- extract_communication_df(cellchat)")
message("    head(df_net)")

message("\n  Extract enriched LR pairs for a pathway:")
message("    enriched_lr <- extract_enriched_lr(cellchat, signaling = 'CXCL')")

message("\n  Summarize by cell group:")
message("    summary <- summarize_communication(cellchat)")
message("    print(summary)")

message("\n  Export all results:")
message("    export_cellchat_results(")
message("      cellchat,")
message("      output_dir = './cellchat_results',")
message("      prefix = 'visium_example',")
message("      export_centrality = TRUE")
message("    )")

# =============================================================================
# Multi-Sample Analysis Example
# =============================================================================

message("\n=== Multi-Sample Analysis Example ===")

message("\n  For multiple Visium samples:")
message("")
message("  # Step 1: Process each sample")
message("  chat_list <- run_cellchat_multi(")
message("    seurat_list = list(sample1, sample2, sample3),")
message("    group_by = 'cell_type',")
message("    sample_names = c('S1', 'S2', 'S3'),")
message("    scalefactors_list = list(sf1, sf2, sf3),")
message("    spatial_tech = 'visium',")
message("    interaction_range = 250")
message("  )")
message("")
message("  # Step 2: Verify non-zero results")
message("  for (name in names(chat_list)) {")
message("    if (sum(chat_list[[name]]@net$count) == 0) {")
message("      warning(paste('Sample', name, 'has zero communications'))")
message("    }")
message("  }")
message("")
message("  # Step 3: Unify labels if needed, then merge")
message("  chat_merged <- mergeSpatialCellChat(")
message("    chat_list,")
message("    add.names = c('S1', 'S2', 'S3')")
message("  )")
message("")
message("  # Step 4: Differential analysis")
message("  netVisual_diffInteraction(chat_merged, comparison = c('S1', 'S2'))")

# =============================================================================
# Summary
# =============================================================================

message("\n=== Analysis Summary ===")
message("\nKey steps for Visium SpatialCellChat analysis:")
message("  1. Load Visium data with Load10X_Spatial()")
message("  2. Ensure cell type annotations are present")
message("  3. (Optional) Prepare cell type decomposition from deconvolution")
message("  4. Locate scalefactors_json.json from Space Ranger")
message("  5. Run run_cellchat_visium() with spatial parameters")
message("  6. Optional: provide cell_type_decomposition for group-level inference")
message("  7. Optional: subset to specific cell_types or signaling_type")
message("  8. Visualize with native SpatialCellChat functions")
message("  9. Extract and export communication data")

message("\nKey parameters:")
message("  - interaction_range: Maximum communication distance (default: 250 um)")
message("  - contact_range: Contact-dependent signaling range (default: 100 um for Visium)")
message("  - scalefactors_json: Required for pixel-to-micrometer conversion")
message("  - cell_type_decomposition: Cell type proportions for accurate Visium inference")
message("  - cell_types: Subset analysis to specific cell types before inference")
message("  - signaling_type: Secreted Signaling, Cell-Cell Contact, ECM-Receptor, or all")
message("  - assay: Seurat assay to use (default 'Spatial' for Visium)")

message("\nFor more examples, see:")
message("  - example_xenium.R: Single-cell resolution analysis")
message("  - usage-guide.md: Complete parameter reference and troubleshooting")

# Cleanup
unlink(scalefactors_file)
