# decoupleR Minimal Example
# ==========================
#
# Basic usage of decoupleR for pathway activity inference
# This example demonstrates the simplest workflow for running decoupleR

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

library(decoupleR)
library(Seurat)

print("decoupleR Minimal Example")
print("=========================")

# ============================================================================
# Step 1: Load Example Data
# ============================================================================

print("\n1. Loading example data...")
data("pbmc_small", package = "Seurat")
seurat_obj <- pbmc_small

print(paste("  Cells:", ncol(seurat_obj)))
print(paste("  Genes:", nrow(seurat_obj)))

# ============================================================================
# Step 2: Load Pathway Network (PROGENy)
# ============================================================================

print("\n2. Loading PROGENy pathway network...")

# Get PROGENy network with top 500 genes per pathway
net <- get_progeny_network(organism = "human", top = 500)

# Show network summary
net_summary <- show_network_summary(net)
print(paste("  Pathways:", net_summary$n_sources))
print(paste("  Interactions:", net_summary$n_interactions))
print(paste("  Targets per pathway (median):", round(net_summary$median_targets_per_source, 1)))

# ============================================================================
# Step 3: Check Gene Overlap
# ============================================================================

print("\n3. Checking gene overlap...")

# Extract expression matrix
if (packageVersion("SeuratObject") >= "5.0.0") {
  mat <- Seurat::GetAssayData(seurat_obj, layer = "data")
} else {
  mat <- Seurat::GetAssayData(seurat_obj, slot = "data")
}

# Check overlap between matrix and network
overlap <- check_gene_overlap(mat, net)
print(paste("  Matrix genes:", overlap$n_mat_genes))
print(paste("  Network targets:", overlap$n_net_genes))
print(paste("  Overlap:", overlap$n_overlap,
            sprintf("(%.1f%%)", overlap$overlap_fraction * 100)))

if (overlap$overlap_fraction < 0.5) {
  print("  Warning: Low gene overlap may affect results")
}

# ============================================================================
# Step 4: Run ULM Analysis
# ============================================================================

print("\n4. Running ULM (Univariate Linear Model) analysis...")

# Run single-method analysis using ULM
acts <- run_decoupler_seurat(
  seurat_obj,
  net = net,
  method = "ulm",
  minsize = 5,
  center = TRUE  # Center data for linear models
)

print(paste("  Results:", nrow(acts), "pathway-cell combinations"))
print(paste("  Pathways analyzed:", length(unique(acts$source))))

# Show top results
print("\n  Top 5 pathway activities:")
print(head(acts %>% dplyr::arrange(dplyr::desc(abs(score))), 5))

# ============================================================================
# Step 5: Add Results to Seurat
# ============================================================================

print("\n5. Adding results to Seurat object...")
seurat_obj <- add_decoupler_to_seurat(seurat_obj, acts)

# Check added metadata
pathway_cols <- grep("^decoupleR_", colnames(seurat_obj@meta.data), value = TRUE)
print(paste("  Added", length(pathway_cols), "pathway scores to metadata"))
print(paste("  Pathways:", paste(gsub("decoupleR_", "", head(pathway_cols, 5)), collapse = ", ")))

# ============================================================================
# Step 6: Visualize Results
# ============================================================================

print("\n6. Creating visualizations...")

# 1. Heatmap of top pathways
print("  - Creating activity heatmap...")
tryCatch({
  ht <- plot_activity_heatmap(
    acts,
    n_top = 10,
    scale = TRUE,
    title = "PROGENy Pathway Activities"
  )
  print("    Heatmap created successfully")
}, error = function(e) {
  print(paste("    Could not create heatmap:", conditionMessage(e)))
})

# 2. Top activities for first sample
print("  - Creating top activities bar plot...")
tryCatch({
  first_cond <- unique(acts$condition)[1]
  p <- plot_top_activities(
    acts,
    condition = first_cond,
    n_top = 10,
    color_by_sign = TRUE
  )
  print(paste("    Top activities plot created for", first_cond))
}, error = function(e) {
  print(paste("    Could not create bar plot:", conditionMessage(e)))
})

# 3. Activity distribution
print("  - Creating activity distribution plot...")
tryCatch({
  p_dist <- plot_activity_distribution(acts, top_n = 10)
  print("    Distribution plot created")
}, error = function(e) {
  print(paste("    Could not create distribution plot:", conditionMessage(e)))
})

# ============================================================================
# Step 7: Summary Statistics
# ============================================================================

print("\n7. Summary statistics:")
summary <- summarize_decoupler_results(acts)
print(paste("  Sources analyzed:", summary$n_sources))
print(paste("  Conditions (cells):", summary$n_conditions))
print(paste("  Score range:", round(summary$score_range[1], 3),
            "to", round(summary$score_range[2], 3)))
print(paste("  Mean score:", round(summary$score_mean, 3)))

if ("statistic" %in% names(summary)) {
  print(paste("  Methods used:", paste(names(summary$by_statistic), collapse = ", ")))
}

# ============================================================================
# Completion
# ============================================================================

print("\n========================================")
print("Example completed successfully!")
print("========================================")
print("Key takeaways:")
print("- decoupleR infers pathway activities from gene expression")
print("- ULM is a fast, robust method for most use cases")
print("- Results are stored as cell-level pathway scores")
print("- Use heatmaps and bar plots to visualize activities")
print("========================================")
