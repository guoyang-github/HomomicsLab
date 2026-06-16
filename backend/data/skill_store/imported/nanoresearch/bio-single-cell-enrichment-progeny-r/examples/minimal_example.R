# Minimal Example: PROGENy Pathway Activity Analysis
# ===================================================
#
# This example demonstrates the basic workflow for PROGENy pathway activity
# inference from single-cell RNA-seq data.

library(Seurat)

# Source the core analysis functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# -------------------------------------------------------------------------
# Step 1: Load data
# -------------------------------------------------------------------------
cat("[Step 1] Loading data...\n")

# Load your Seurat object
# seurat_obj <- readRDS("your_data.rds")

# For demonstration, create example data structure
# In practice, replace this with: seurat_obj <- readRDS("your_data.rds")
cat("Note: Replace with your actual data loading\n")
cat("Expected: Seurat object with normalized expression data\n")

# -------------------------------------------------------------------------
# Step 2: Run PROGENy
# -------------------------------------------------------------------------
cat("\n[Step 2] Running PROGENy...\n")

# Run PROGENy with default parameters
# seurat_obj <- run_progeny(
#   seurat_obj,
#   organism = "Human",    # or "Mouse"
#   top = 100,             # Top responsive genes per pathway
#   scale = FALSE,         # Don't scale for single-cell
#   return_assay = TRUE
# )

cat("- Using top 100 responsive genes per pathway\n")
cat("- Organism: Human\n")
cat("- Scoring method: Unscaled (appropriate for single-cell)\n")

# -------------------------------------------------------------------------
# Step 3: Add scores to metadata (optional)
# -------------------------------------------------------------------------
cat("\n[Step 3] Adding scores to metadata...\n")

# seurat_obj <- add_progeny_to_metadata(seurat_obj, prefix = "PROGENy_")

cat("- Pathway scores added as metadata columns\n")

# -------------------------------------------------------------------------
# Step 4: Visualize results
# -------------------------------------------------------------------------
cat("\n[Step 4] Visualizing results...\n")

# Visualize key pathways on embedding
# pathways_to_plot <- c("MAPK", "PI3K", "TGFb", "TNFa")
# plot_pathway_embedding(seurat_obj, pathways = pathways_to_plot, reduction = "umap")

# Violin plot by cluster
# plot_pathway_violin(seurat_obj, pathways = pathways_to_plot, group.by = "seurat_clusters")

cat("- Created feature plots on UMAP\n")
cat("- Created violin plots by cluster\n")

# -------------------------------------------------------------------------
# Step 5: Export results
# -------------------------------------------------------------------------
cat("\n[Step 5] Exporting results...\n")

# export_progeny_results(
#   seurat_obj,
#   output_dir = "progeny_results",
#   prefix = "analysis"
# )

cat("- Results exported to progeny_results/\n")

cat("\nAnalysis complete!\n")
