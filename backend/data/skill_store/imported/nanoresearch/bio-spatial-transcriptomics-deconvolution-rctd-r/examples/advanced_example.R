# Advanced Example: RCTD Comprehensive Analysis
# ==============================================
#
# Advanced workflow demonstrating:
# - Seurat integration
# - Multiple visualization types
# - Result filtering and comparison
# - Comprehensive reporting

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("RCTD Advanced Example\n")
cat("=", rep("=", 70), "\n\n", sep = "")

# -----------------------------------------------------------------------------
# Step 1: Create comprehensive test data
# -----------------------------------------------------------------------------
cat("[Step 1] Creating test data...\n")

set.seed(42)
n_spots <- 400
n_genes <- 1000
n_cell_types <- 6
n_cells_per_type <- 50

# Create spatial coordinates (simulate tissue structure)
coords <- data.frame(
  x = c(rep(1:20, 20), rep(21:40, 20)),
  y = rep(rep(1:20, each = 20), 2)
)[1:n_spots, ]

# Create reference data
n_ref_cells <- n_cell_types * n_cells_per_type
ref_counts <- matrix(
  rpois(n_genes * n_ref_cells, lambda = 10),
  nrow = n_genes,
  ncol = n_ref_cells
)

cell_type_names <- c("T_cell", "B_cell", "Macrophage", "Fibroblast", "Endothelial", "Epithelial")
cell_types <- factor(rep(cell_type_names, each = n_cells_per_type))

gene_names <- paste0("GENE_", 1:n_genes)
rownames(ref_counts) <- gene_names
colnames(ref_counts) <- paste0("cell_", 1:n_ref_cells)
names(cell_types) <- colnames(ref_counts)

# Create spatial data with tissue-specific patterns
spatial_counts <- matrix(0, nrow = n_genes, ncol = n_spots)
rownames(spatial_counts) <- gene_names
colnames(spatial_counts) <- paste0("spot_", 1:n_spots)

# Region 1 (spots 1-200): T_cells, B_cells, Macrophages
# Region 2 (spots 201-400): Fibroblasts, Endothelial, Epithelial

for (i in 1:200) {
  props <- c(0.4, 0.3, 0.2, 0.05, 0.03, 0.02)
  for (ct in 1:n_cell_types) {
    ct_cells <- which(cell_types == cell_type_names[ct])
    n_sample <- max(1, round(props[ct] * 8))
    selected <- sample(ct_cells, n_sample, replace = TRUE)
    spatial_counts[, i] <- spatial_counts[, i] + rowSums(ref_counts[, selected, drop = FALSE])
  }
}

for (i in 201:400) {
  props <- c(0.05, 0.05, 0.1, 0.4, 0.25, 0.15)
  for (ct in 1:n_cell_types) {
    ct_cells <- which(cell_types == cell_type_names[ct])
    n_sample <- max(1, round(props[ct] * 8))
    selected <- sample(ct_cells, n_sample, replace = TRUE)
    spatial_counts[, i] <- spatial_counts[, i] + rowSums(ref_counts[, selected, drop = FALSE])
  }
}

# Add region annotation
coords$region <- c(rep("Immune", 200), rep("Stromal", 200))

cat(sprintf("  Created: %d spots x %d genes\n", n_spots, n_genes))
cat(sprintf("  Reference: %d cells (%d types)\n", n_ref_cells, n_cell_types))

# -----------------------------------------------------------------------------
# Step 2: Get parameter recommendations
# -----------------------------------------------------------------------------
cat("\n[Step 2] Getting parameter recommendations...\n")

params <- recommend_rctd_params(n_spots, n_cell_types)
cat(sprintf("  Recommended mode: %s\n", params$doublet_mode))
cat(sprintf("  Recommended cores: %d\n", params$max_cores))

# -----------------------------------------------------------------------------
# Step 3: Run RCTD (commented)
# -----------------------------------------------------------------------------
cat("\n[Step 3] Running RCTD...\n")
cat("  (Commented out - requires spacexr package)\n")

# Uncomment to run:
# results <- run_rctd(
#   spatial_counts = spatial_counts,
#   spatial_coords = coords[, c("x", "y")],
#   reference_counts = ref_counts,
#   cell_types = cell_types,
#   doublet_mode = params$doublet_mode,
#   max_cores = 2
# )

# -----------------------------------------------------------------------------
# Step 4: Mock results for demonstration
# -----------------------------------------------------------------------------
cat("\n[Step 4] Creating mock results...\n")

# Create realistic mock proportions
mock_props <- matrix(0, nrow = n_spots, ncol = n_cell_types)
colnames(mock_props) <- cell_type_names
rownames(mock_props) <- colnames(spatial_counts)

for (i in 1:200) {
  props <- c(0.4, 0.3, 0.2, 0.05, 0.03, 0.02)
  props <- props + rnorm(6, 0, 0.02)
  props <- pmax(props, 0)
  props <- props / sum(props)
  mock_props[i, ] <- props
}

for (i in 201:400) {
  props <- c(0.05, 0.05, 0.1, 0.4, 0.25, 0.15)
  props <- props + rnorm(6, 0, 0.02)
  props <- pmax(props, 0)
  props <- props / sum(props)
  mock_props[i, ] <- props
}

# Mock spot classification for doublet mode
spot_class <- sample(c("singlet", "doublet_certain", "doublet_uncertain", "reject"),
                     n_spots, replace = TRUE, prob = c(0.5, 0.3, 0.15, 0.05))

# -----------------------------------------------------------------------------
# Step 5: Summarize results
# -----------------------------------------------------------------------------
cat("\n[Step 5] Summarizing results...\n")

cat("\nMean proportions:\n")
print(round(colMeans(mock_props), 3))

cat("\nDominant cell types:\n")
dominant <- cell_type_names[apply(mock_props, 1, which.max)]
print(table(dominant))

# By region
cat("\nMean proportions by region:\n")
for (region in c("Immune", "Stromal")) {
  cat(sprintf("\n%s:\n", region))
  region_props <- mock_props[coords$region == region, ]
  print(round(colMeans(region_props), 3))
}

# Spot classification
cat("\nSpot classification:\n")
print(table(spot_class))

# -----------------------------------------------------------------------------
# Step 6: Visualizations
# -----------------------------------------------------------------------------
cat("\n[Step 6] Creating visualizations...\n")

output_dir <- "./rctd_plots"
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

# 1. Spatial proportion plots
cat("  1. Spatial proportion plots...\n")
# Would create: plot_rctd_proportions(results, cell_types = cell_type_names[1:3])

# 2. Dominant cell types
cat("  2. Dominant cell types map...\n")
# Would create: plot_rctd_dominant(results)

# 3. Distribution plots
cat("  3. Distribution plots...\n")
# Would create: plot_rctd_distribution(results)

# 4. Mean proportions bar chart
cat("  4. Mean proportions bar chart...\n")
# Would create: plot_rctd_mean_props(results)

# 5. Proportion heatmap
cat("  5. Proportion heatmap...\n")
# Would create: plot_rctd_heatmap(results, n_spots = 100)

# 6. Doublet classification (if in doublet mode)
cat("  6. Doublet classification map...\n")
# Would create: plot_rctd_doublets(results)

# -----------------------------------------------------------------------------
# Step 7: Export results
# -----------------------------------------------------------------------------
cat("\n[Step 7] Exporting results...\n")

# Full results
export_df <- cbind(
  spot = rownames(mock_props),
  coords,
  mock_props
)
write.csv(export_df, "advanced_rctd_results.csv", row.names = FALSE)

# Summary by region
summary_df <- aggregate(mock_props, by = list(region = coords$region), mean)
write.csv(summary_df, "advanced_rctd_summary_by_region.csv", row.names = FALSE)

# Spot classification
class_df <- data.frame(
  spot = rownames(mock_props),
  spot_class = spot_class,
  dominant = dominant,
  stringsAsFactors = FALSE
)
write.csv(class_df, "advanced_rctd_spot_classification.csv", row.names = FALSE)

cat("  Exported: advanced_rctd_results.csv\n")
cat("  Exported: advanced_rctd_summary_by_region.csv\n")
cat("  Exported: advanced_rctd_spot_classification.csv\n")

# -----------------------------------------------------------------------------
# Step 8: Generate report
# -----------------------------------------------------------------------------
cat("\n[Step 8] Generating report...\n")

report <- sprintf("
RCTD Advanced Analysis Report
=============================
Date: %s

Dataset Information
-------------------
Number of spots: %d
Number of genes: %d
Number of cell types: %d
Reference cells: %d

Analysis Parameters
-------------------
Mode: %s
Cores: %d
Gene cutoff: %.6f
FC cutoff: 0.5

Results Summary
---------------
Mean cell type proportions:
%s

Regional Analysis
-----------------
Immune region (spots 1-200): T cells, B cells, Macrophages dominant
Stromal region (spots 201-400): Fibroblasts, Endothelial, Epithelial dominant

Spot Classification
-------------------
%s

Visualization Files
-------------------
- Spatial proportion plots: rctd_plots/prop_*.pdf
- Dominant cell types: rctd_plots/dominant.pdf
- Distribution plots: rctd_plots/distribution.pdf
- Heatmap: rctd_plots/heatmap.pdf
- Doublet map: rctd_plots/doublets.pdf
",
  format(Sys.time(), "%Y-%m-%d %H:%M"),
  n_spots, n_genes, n_cell_types, n_ref_cells,
  params$doublet_mode,
  params$max_cores,
  params$gene_cutoff,
  paste(sprintf("  %s: %.3f", cell_type_names, colMeans(mock_props)), collapse = "\n"),
  paste(sprintf("  %s: %d", names(table(spot_class)), table(spot_class)), collapse = "\n")
)

writeLines(report, "advanced_rctd_report.txt")
cat("  Report saved: advanced_rctd_report.txt\n")

cat("\n", rep("=", 70), "\n", sep = "")
cat("Advanced example complete!\n")
cat(rep("=", 70), "\n", sep = "")
