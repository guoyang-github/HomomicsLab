#!/usr/bin/env Rscript
#' Seurat Integration Example
#'
#' Demonstrates NicheNet analysis on Seurat objects with cell type annotations.
#'
#' @author Yang Guo
#' @date 2026-04-01

library(Seurat)
library(dplyr)

# Source NicheNet scripts
source("../scripts/r/nichenet_database.R")
source("../scripts/r/nichenet_analysis.R")
source("../scripts/r/nichenet_seurat.R")
source("../scripts/r/nichenet_visualization.R")

message("=== NicheNet Seurat Integration Example ===")

# ============================================================================
# Step 1: Load or Create Example Data
# ============================================================================

message("\n1. Preparing example data...")

# For this example, we'll use pbmc3k or create synthetic data
# In practice, replace with your own Seurat object

if (requireNamespace("SeuratData", quietly = TRUE)) {
  # Try to load pbmc3k
  tryCatch({
    data("pbmc3k")
    seurat_obj <- pbmc3k
  }, error = function(e) {
    message("Creating synthetic data instead...")
    seurat_obj <- NULL
  })
} else {
  message("Creating synthetic data...")
  seurat_obj <- NULL
}

# Create synthetic data if needed
if (is.null(seurat_obj)) {
  set.seed(42)

  # Create synthetic counts
  n_cells <- 500
  n_genes <- 2000

  counts <- matrix(
    rpois(n_cells * n_genes, lambda = 0.5),
    nrow = n_genes,
    ncol = n_cells
  )
  rownames(counts) <- paste0("GENE", 1:n_genes)
  colnames(counts) <- paste0("CELL", 1:n_cells)

  # Add some marker genes
  marker_genes <- list(
    Macrophage = c("CD14", "CD68", "CSF1R"),
    T_cell = c("CD3D", "CD3E", "CD4", "CD8A"),
    B_cell = c("CD19", "MS4A1", "CD79A"),
    NK = c("NCAM1", "NKG7", "KLRD1")
  )

  # Overwrite some genes with known names
  for (i in seq_along(marker_genes)) {
    for (gene in marker_genes[[i]]) {
      if (gene %in% rownames(counts)) {
        counts[gene, ] <- counts[gene, ] + rpois(n_cells, 5)
      }
    }
  }

  # Create Seurat object
  seurat_obj <- CreateSeuratObject(counts = counts)

  # Add cell type annotations
  cell_types <- sample(c("Macrophage", "T_cell", "B_cell", "NK"), n_cells, replace = TRUE)
  seurat_obj$cell_type <- cell_types

  # Add condition annotation
  seurat_obj$condition <- sample(c("control", "stimulated"), n_cells, replace = TRUE)

  # Normalize
  seurat_obj <- NormalizeData(seurat_obj)
  seurat_obj <- FindVariableFeatures(seurat_obj)

  message(sprintf("Created synthetic Seurat object: %d cells x %d genes",
                 ncol(seurat_obj), nrow(seurat_obj)))
}

# ============================================================================
# Step 2: Check Database
# ============================================================================

message("\n2. Checking NicheNet database...")

check_nichenet_database("human")

# ============================================================================
# Step 3: Get Expressed Genes
# ============================================================================

message("\n3. Calculating expressed genes...")

# Get expressed genes for each cell type
sender_genes <- get_expressed_genes(seurat_obj, "Macrophage", pct = 0.10)
receiver_genes <- get_expressed_genes(seurat_obj, "T_cell", pct = 0.10)

message(sprintf("Macrophage expressed genes: %d", length(sender_genes)))
message(sprintf("T_cell expressed genes: %d", length(receiver_genes)))

# ============================================================================
# Step 4: Run NicheNet Analysis
# ============================================================================

message("\n4. Running NicheNet analysis...")

# Option A: Full analysis with condition comparison
if ("condition" %in% colnames(seurat_obj@meta.data)) {
  message("\n--- Mode: Aggregate (condition comparison) ---")

  results <- run_nichenet_aggregate(
    seurat_obj = seurat_obj,
    sender = "Macrophage",
    receiver = "T_cell",
    condition_colname = "condition",
    condition_oi = "stimulated",
    condition_reference = "control",
    organism = "human"
  )

} else {
  # Option B: Basic analysis with marker genes
  message("\n--- Mode: Cell Type Pair (with marker genes) ---")

  # Define marker genes of interest
  marker_genes <- c("IL2RA", "IFNG", "TNF", "GZMB", "PRF1")

  results <- run_nichenet_celltype_pair(
    seurat_obj = seurat_obj,
    sender_celltype = "Macrophage",
    receiver_celltype = "T_cell",
    genes_of_interest = marker_genes,
    organism = "human"
  )
}

# ============================================================================
# Step 5: Explore Results
# ============================================================================

message("\n5. Results summary:")

cat(summarize_nichenet_results(results))

# Top ligands
message("\n\nTop 10 Ligands:")
print(head(results$ligand_activities[, c("test_ligand", "pearson")], 10))

# ============================================================================
# Step 6: Visualize
# ============================================================================

message("\n6. Creating visualizations...")

dir.create("output", showWarnings = FALSE)

# Dot plot of ligand activities
p1 <- plot_ligand_activity_dotplot(results$ligand_activities, top_n = 15)
ggsave("output/seurat_ligand_dotplot.png", p1, width = 8, height = 6, dpi = 150)
message("Saved: output/seurat_ligand_dotplot.png")

# Bar plot
p2 <- plot_top_ligand_barplot(results$ligand_activities, top_n = 10)
ggsave("output/seurat_ligand_barplot.png", p2, width = 8, height = 5, dpi = 150)
message("Saved: output/seurat_ligand_barplot.png")

# Ligand-receptor heatmap (if enough data)
tryCatch({
  ligand_target_matrix <- get_ligand_target_matrix("human")
  png("output/seurat_lt_heatmap.png", width = 10, height = 8, units = "in", res = 150)
  plot_ligand_target_heatmap(
    ligand_target_matrix,
    ligands = results$top_ligands[1:5],
    n_targets = 30
  )
  dev.off()
  message("Saved: output/seurat_lt_heatmap.png")
}, error = function(e) {
  message("Could not create heatmap: ", e$message)
})

# ============================================================================
# Step 7: Export
# ============================================================================

message("\n7. Exporting results...")

export_nichenet_results(results, "output", prefix = "seurat_analysis")

# ============================================================================
# Step 8: Advanced - Batch Analysis
# ============================================================================

message("\n8. Optional: Batch analysis example...")

# Define multiple cell type pairs
pairs <- data.frame(
  sender = c("Macrophage", "Macrophage", "B_cell"),
  receiver = c("T_cell", "B_cell", "T_cell")
)

message("Would analyze these pairs:")
print(pairs)

# Uncomment to run batch analysis:
# batch_results <- run_nichenet_batch(
#   seurat_obj,
#   pairs,
#   condition_col = "condition",
#   condition_oi = "stimulated",
#   condition_ref = "control"
# )

# ============================================================================
# Summary
# ============================================================================

message("\n=== Analysis Complete ===")
message("Results saved to output/ directory")
message("\nKey files:")
message("  - seurat_ligand_dotplot.png")
message("  - seurat_ligand_barplot.png")
message("  - seurat_analysis_ligand_activities.csv")
message("  - seurat_analysis_ligand_targets.csv")
