#!/usr/bin/env Rscript
#' CellChat Single-Cell Basic Analysis Example
#'
#' Demonstrates complete cell-cell communication analysis workflow.

# =============================================================================
# Setup
# =============================================================================

# Load required packages
if (!requireNamespace("Seurat", quietly = TRUE)) {
  install.packages("Seurat")
}
if (!requireNamespace("CellChat", quietly = TRUE)) {
  remotes::install_github("jinworks/CellChat")
}

library(Seurat)
library(CellChat)

# Source the CellChat analysis module
script_dir <- dirname(sys.frame(1)$ofile)
source(file.path(script_dir, "..", "scripts", "r", "cellchat_analysis.R"))

message("=== CellChat Single-Cell Analysis Example ===\n")

# =============================================================================
# Step 1: Create/load Single-Cell Data
# =============================================================================

message("Step 1: Creating simulated single-cell dataset...")
message("  Note: Replace with your actual scRNA-seq data")

# For this example, create simulated data
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
seurat_obj <- CreateSeuratObject(counts = counts)

# Add cell type annotations
cell_types <- sample(
  c("Tumor", "T_cell", "B_cell", "Macrophage", "Fibroblast", "Endothelial"),
  n_cells,
  replace = TRUE,
  prob = c(0.25, 0.2, 0.1, 0.15, 0.2, 0.1)
)
seurat_obj$cell_type <- cell_types

# Add UMAP coordinates for visualization (optional)
# seurat_obj <- NormalizeData(seurat_obj)
# seurat_obj <- FindVariableFeatures(seurat_obj)
# seurat_obj <- ScaleData(seurat_obj)
# seurat_obj <- RunPCA(seurat_obj)
# seurat_obj <- RunUMAP(seurat_obj, dims = 1:10)

message(sprintf("  Created: %d cells, %d genes", n_cells, n_genes))
message(sprintf("  Cell types: %s", paste(table(cell_types), collapse = ", ")))

# =============================================================================
# Step 2: Run CellChat Analysis
# =============================================================================

message("\nStep 2: Running CellChat analysis...")
message("  Note: Full analysis skipped in example (requires CellChat)")
message("")
message("  # Run complete analysis")
message("  cellchat <- run_cellchat(")
message("    seurat_obj = seurat_obj,")
message("    group_by = 'cell_type',")
message("    sample_name = 'Example_Sample',")
message("    db_use = 'CellChatDB.human',")
message("    signaling_type = 'Secreted Signaling',")
message("    type = 'triMean',")
message("    min_cells = 10,")
message("    n_workers = 4")
message("  )")

# For demonstration, we create a mock cellchat object structure
# In practice, you would run the above code

# =============================================================================
# Step 3: Visualization Examples
# =============================================================================

message("\n=== Visualization Examples ===")

message("\n  3.1 Circle plot of aggregated network:")
message("    plot_cellchat_circle(cellchat)")
message("    plot_cellchat_circle(cellchat, slot_name = 'net$weight')")

message("\n  3.2 Signaling pathway visualization:")
message("    # Circle plot")
message("    plot_cellchat_pathway(cellchat, signaling = 'CXCL', layout = 'circle')")
message("")
message("    # Hierarchy plot")
message("    plot_cellchat_pathway(")
message("      cellchat,")
message("      signaling = 'CXCL',")
message("      layout = 'hierarchy',")
message("      vertex.receiver = 1:3  # Target cells on left")
message("    )")
message("")
message("    # Chord diagram")
message("    plot_cellchat_pathway(cellchat, signaling = 'CXCL', layout = 'chord')")
message("")
message("    # Heatmap")
message("    netVisual_heatmap(cellchat, signaling = 'CXCL')")

message("\n  3.3 Bubble plot of L-R pairs:")
message("    # All interactions from specific sources")
message("    plot_cellchat_bubble(cellchat, sources.use = c(1, 2))")
message("")
message("    # Specific source-target pairs")
message("    plot_cellchat_bubble(")
message("      cellchat,")
message("      sources.use = c('T_cell', 'B_cell'),")
message("      targets.use = c('Tumor', 'Macrophage')")
message("    )")
message("")
message("    # Specific signaling pathways")
message("    plot_cellchat_bubble(")
message("      cellchat,")
message("      signaling = c('CXCL', 'CCL', 'TNF')")
message("    )")

message("\n  3.4 Gene expression visualization:")
message("    # Violin plot")
message("    plotGeneExpression(cellchat, signaling = 'CXCL', type = 'violin')")
message("")
message("    # Dot plot")
message("    plotGeneExpression(cellchat, signaling = 'CXCL', type = 'dot')")

# =============================================================================
# Step 4: Systems Analysis Examples
# =============================================================================

message("\n=== Systems Analysis Examples ===")

message("\n  4.1 Network centrality analysis:")
message("    # Compute centrality")
message("    cellchat <- compute_cellchat_centrality(cellchat)")
message("")
message("    # Heatmap of signaling roles")
message("    netAnalysis_signalingRole_heatmap(cellchat, pattern = 'outgoing')")
message("    netAnalysis_signalingRole_heatmap(cellchat, pattern = 'incoming')")
message("")
message("    # Scatter plot")
message("    netAnalysis_signalingRole_scatter(cellchat)")

message("\n  4.2 Communication patterns:")
message("    # Identify optimal number of patterns")
message("    selectK(cellchat, pattern = 'outgoing')")
message("")
message("    # Identify patterns (e.g., k=5)")
message("    cellchat <- identify_cellchat_patterns(")
message("      cellchat,")
message("      pattern = 'outgoing',")
message("      k = 5")
message("    )")
message("")
message("    # River plot")
message("    netAnalysis_river(cellchat, pattern = 'outgoing')")
message("")
message("    # Dot plot")
message("    netAnalysis_dot(cellchat, pattern = 'outgoing')")

message("\n  4.3 Similarity analysis:")
message("    # Functional similarity")
message("    cellchat <- computeNetSimilarity(cellchat, type = 'functional')")
message("    cellchat <- netEmbedding(cellchat, type = 'functional')")
message("    cellchat <- netClustering(cellchat, type = 'functional')")
message("    netVisual_embedding(cellchat, type = 'functional')")
message("")
message("    # Structural similarity")
message("    cellchat <- computeNetSimilarity(cellchat, type = 'structural')")
message("    cellchat <- netEmbedding(cellchat, type = 'structural')")
message("    netVisual_embedding(cellchat, type = 'structural')")

# =============================================================================
# Step 5: Extract and Export Results
# =============================================================================

message("\n=== Extract and Export Results ===")

message("\n  5.1 Extract communications:")
message("    # All L-R pairs")
message("    df_net <- extract_cellchat_communications(cellchat)")
message("    head(df_net)")
message("")
message("    # Specific pathway")
message("    df_cxcl <- extract_cellchat_communications(")
message("      cellchat,")
message("      signaling = 'CXCL'")
message("    )")
message("")
message("    # Specific source-target pairs")
message("    df_specific <- extract_cellchat_communications(")
message("      cellchat,")
message("      sources.use = c(1, 2),")
message("      targets.use = c(3, 4)")
message("    )")

message("\n  5.2 Summarize results:")
message("    # Summary by cell group")
message("    summary <- summarize_cellchat(cellchat)")
message("    print(summary)")

message("\n  5.3 Export to files:")
message("    export_cellchat_results(")
message("      cellchat,")
message("      output_dir = './cellchat_results',")
message("      prefix = 'example'")
message("    )")

# =============================================================================
# Summary
# =============================================================================

message("\n=== Analysis Summary ===")
message("\nKey steps for CellChat analysis:")
message("  1. Prepare annotated scRNA-seq data (Seurat object)")
message("  2. Run run_cellchat() for complete analysis")
message("  3. Visualize with circle plots, bubble plots, heatmaps")
message("  4. Perform systems analysis (centrality, patterns, similarity)")
message("  5. Extract and export results")

message("\nKey parameters:")
message("  - db_use: 'CellChatDB.human' or 'CellChatDB.mouse'")
message("  - signaling_type: 'Secreted Signaling', 'Cell-Cell Contact', 'ECM-Receptor', 'all'")
message("  - type: 'triMean' (fewer, stronger) or 'truncatedMean' (more, weaker)")
message("  - min_cells: Minimum cells per group for analysis")

message("\nFor more examples, see:")
message("  - example_comparison.R: Multi-condition comparison")
message("  - example_advanced.R: Advanced visualization and analysis")
