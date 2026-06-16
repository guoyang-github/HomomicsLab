#!/usr/bin/env Rscript
#' Basic NicheNet Analysis Example
#'
#' Demonstrates core NicheNet analysis with manual gene lists.
#'
#' @author Yang Guo
#' @date 2026-04-01

library(Seurat)
library(dplyr)

# Source NicheNet scripts
source("../scripts/r/nichenet_database.R")
source("../scripts/r/nichenet_analysis.R")
source("../scripts/r/nichenet_visualization.R")

message("=== Basic NicheNet Analysis Example ===")

# ============================================================================
# Step 1: Check/Prepare Database
# ============================================================================

message("\n1. Checking NicheNet database...")

if (!check_nichenet_database("human", verbose = FALSE)) {
  message("Downloading database (this may take a few minutes)...")
  download_nichenet_database("human")
}

# Load databases
ligand_target_matrix <- get_ligand_target_matrix("human")
lr_network <- get_lr_network("human")

message(sprintf("Loaded matrix: %d targets x %d ligands",
               nrow(ligand_target_matrix), ncol(ligand_target_matrix)))

# ============================================================================
# Step 2: Define Input Data
# ============================================================================

message("\n2. Setting up input data...")

# Example: T cells responding to IL2 treatment
# Genes upregulated in T cells after IL2 stimulation
genes_of_interest <- c(
  "IL2RA", "IL2RB", "FOXP3", "CTLA4", "ICOS",   # IL2 response
  "IFNG", "TNF", "GZMB", "PRF1",                # Effector
  "BCL2", "MCL1",                               # Survival
  "CCND1", "CCND2", "CDK4"                      # Cell cycle
)

# All genes expressed in T cells
background_expressed_genes <- c(
  genes_of_interest,
  "ACTB", "GAPDH", "B2M",                       # Housekeeping
  "CD3D", "CD3E", "CD4", "CD8A",                # T cell markers
  "IL7R", "CD28", "CD69"                        # Activation markers
)

# Potential ligands from sender cells (e.g., APCs)
expressed_ligands_sender <- c(
  "IL2", "IL7", "IL15",                         # Cytokines
  "CD80", "CD86",                               # Co-stimulatory
  "ICOSL",                                      # ICOS ligand
  "TNFSF4", "TNFSF9", "TNFSF18",                # TNF family
  "TGFB1", "IL10"                               # Regulatory
)

# Filter to ligands in database
available_ligands <- colnames(ligand_target_matrix)
potential_ligands <- intersect(expressed_ligands_sender, available_ligands)

message(sprintf("Genes of interest: %d", length(genes_of_interest)))
message(sprintf("Background genes: %d", length(background_expressed_genes)))
message(sprintf("Potential ligands: %d", length(potential_ligands)))

# ============================================================================
# Step 3: Run NicheNet Analysis
# ============================================================================

message("\n3. Running NicheNet prediction...")

results <- predict_ligand_activities(
  geneset = genes_of_interest,
  background_expressed_genes = background_expressed_genes,
  ligand_target_matrix = ligand_target_matrix,
  potential_ligands = potential_ligands
)

# ============================================================================
# Step 4: Explore Results
# ============================================================================

message("\n4. Results:")
message("\nTop 10 Predicted Ligands:")
print(head(results, 10))

# Get top ligand and its targets
top_ligand <- results$test_ligand[1]
message(sprintf("\nTop Ligand: %s (Pearson: %.3f)",
               top_ligand, results$pearson[1]))

# Get target genes for top ligand
top_targets <- get_top_targets(
  ligand = top_ligand,
  ligand_target_matrix = ligand_target_matrix,
  n = 50,
  return_scores = TRUE
)

message(sprintf("\nTop 10 targets of %s:", top_ligand))
print(head(top_targets, 10))

# Check overlap with genes of interest
overlap <- intersect(names(top_targets), genes_of_interest)
message(sprintf("\nTarget overlap with genes of interest: %d/%d",
               length(overlap), length(genes_of_interest)))
if (length(overlap) > 0) {
  message("Overlapping genes: ", paste(overlap, collapse = ", "))
}

# ============================================================================
# Step 5: Visualize
# ============================================================================

message("\n5. Creating visualizations...")

# Dot plot
p1 <- plot_ligand_activity_dotplot(results, top_n = 15)
ggsave("01_ligand_activity_dotplot.png", p1, width = 8, height = 6, dpi = 150)
message("Saved: 01_ligand_activity_dotplot.png")

# Bar plot
p2 <- plot_top_ligand_barplot(results, top_n = 10)
ggsave("02_top_ligands_barplot.png", p2, width = 8, height = 5, dpi = 150)
message("Saved: 02_top_ligands_barplot.png")

# Heatmap (top 5 ligands)
png("03_ligand_target_heatmap.png", width = 10, height = 8, units = "in", res = 150)
plot_ligand_target_heatmap(
  ligand_target_matrix,
  ligands = results$test_ligand[1:5],
  n_targets = 30
)
dev.off()
message("Saved: 03_ligand_target_heatmap.png")

# ============================================================================
# Step 6: Export
# ============================================================================

message("\n6. Exporting results...")

dir.create("output", showWarnings = FALSE)

# Export ligand activities
write.csv(results, "output/ligand_activities.csv", row.names = FALSE)

# Export ligand-target pairs for top ligands
top_ligands <- results$test_ligand[1:5]
lt_pairs <- data.frame()
for (lig in top_ligands) {
  targets <- get_top_targets(lig, ligand_target_matrix, n = 50)
  lt_pairs <- rbind(lt_pairs, data.frame(
    ligand = lig,
    target = targets,
    stringsAsFactors = FALSE
  ))
}
write.csv(lt_pairs, "output/ligand_target_pairs.csv", row.names = FALSE)

message("Results exported to output/")

# ============================================================================
# Summary
# ============================================================================

message("\n=== Analysis Complete ===")
message(sprintf("Top 3 ligands: %s", paste(head(results$test_ligand, 3), collapse = ", ")))
message("Expected: IL2 should be top-ranked (ground truth in this example)")
if (results$test_ligand[1] == "IL2") {
  message("✓ IL2 correctly identified as top ligand!")
} else {
  message("Note: IL2 not top-ranked (may need more specific gene set)")
}
