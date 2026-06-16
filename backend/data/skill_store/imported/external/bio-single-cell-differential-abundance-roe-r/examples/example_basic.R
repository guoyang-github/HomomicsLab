# Basic Ro/e Analysis Example
# Demonstrates standard workflow for differential abundance analysis

library(Seurat)
library(ggplot2)
library(dplyr)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source functions
source(file.path(base_dir, "scripts", "r", "roe_analysis.R"))
source(file.path(base_dir, "scripts", "r", "roe_visualization.R"))

# ============================================
# Create Synthetic Data
# ============================================

message("=== Creating Synthetic Test Data ===")

set.seed(42)

# Simulate a dataset with 500 cells across 5 cell types
n_cells <- 500
cell_types <- c(
  rep("CD4_T_cell", 120),
  rep("CD8_T_cell", 100),
  rep("B_cell", 80),
  rep("Macrophage", 100),
  rep("Fibroblast", 100)
)

# Create two groups with differential abundance patterns:
# - Group A (Treatment): More immune cells (T cells, Macrophages)
# - Group B (Control): More structural cells (Fibroblasts)

# Proportions designed to create Ro/e patterns
groups <- c(
  # CD4 T cells: 70% in Treatment, 30% in Control
  rep("Treatment", 84),  rep("Control", 36),
  # CD8 T cells: 65% in Treatment, 35% in Control
  rep("Treatment", 65),  rep("Control", 35),
  # B cells: balanced
  rep("Treatment", 40),  rep("Control", 40),
  # Macrophages: 75% in Treatment, 25% in Control (strong enrichment)
  rep("Treatment", 75),  rep("Control", 25),
  # Fibroblasts: 30% in Treatment, 70% in Control (depletion)
  rep("Treatment", 30),  rep("Control", 70)
)

# Create sample IDs for paired analysis
samples <- paste0("Sample_", rep(1:10, each = 50))

cat("Total cells:", length(cell_types), "\n")
cat("Cell type distribution:\n")
print(table(cell_types))
cat("\nGroup distribution:\n")
print(table(groups))

# ============================================
# Run Ro/e Analysis
# ============================================

message("\n=== Running Ro/e Analysis ===")

# Basic Ro/e calculation
roe_result <- calculate_roe(
  cell_types = cell_types,
  groups = groups,
  method = "group"
)

# Print summary
print(roe_result)

# ============================================
# View Results as Data Frame
# ============================================

message("\n=== Ro/e Results Table ===")

roe_df <- roe_to_dataframe(roe_result)
print(roe_df)

# ============================================
# Visualization: Heatmap
# ============================================

message("\n=== Creating Heatmap ===")

p_heatmap <- plot_roe_heatmap(
  roe_result,
  cluster_rows = TRUE,
  cluster_cols = FALSE,
  value_text_size = 4,
  title = "Ro/e: Treatment vs Control"
)
print(p_heatmap)

# Save plot
ggsave("roe_heatmap_basic.png", p_heatmap, width = 8, height = 6, dpi = 300)
message("Saved: roe_heatmap_basic.png")

# ============================================
# Visualization: Lollipop Chart
# ============================================

message("\n=== Creating Lollipop Charts ===")

# Lollipop for Treatment group
p_lollipop_treat <- plot_roe_lollipop(
  roe_result,
  compare_group = "Treatment",
  highlight_sig = TRUE,
  color_by_depletion = TRUE,
  title = "Cell Type Enrichment in Treatment Group"
)
print(p_lollipop_treat)
ggsave("roe_lollipop_treatment.png", p_lollipop_treat, width = 8, height = 6)

# Lollipop for Control group
p_lollipop_ctrl <- plot_roe_lollipop(
  roe_result,
  compare_group = "Control",
  highlight_sig = TRUE,
  color_by_depletion = TRUE,
  title = "Cell Type Enrichment in Control Group"
)
print(p_lollipop_ctrl)
ggsave("roe_lollipop_control.png", p_lollipop_ctrl, width = 8, height = 6)

# ============================================
# Visualization: Dot Plot
# ============================================

message("\n=== Creating Dot Plot ===")

p_dot <- plot_roe_dotplot(
  roe_result,
  size_by = "proportion",
  color_scale = "roe",
  title = "Ro/e and Cell Proportions"
)
print(p_dot)
ggsave("roe_dotplot.png", p_dot, width = 8, height = 6)

# ============================================
# Visualization: Bar Chart
# ============================================

message("\n=== Creating Bar Chart ===")

p_bar <- plot_roe_bar(
  roe_result,
  show_expected = TRUE,
  title = "Observed vs Expected Proportions"
)
print(p_bar)
ggsave("roe_barchart.png", p_bar, width = 10, height = 6)

# ============================================
# Interpret Results
# ============================================

message("\n=== Result Interpretation ===")

# Identify enriched cell types
enriched_treatment <- roe_df %>%
  filter(group == "Treatment", roe > 1.5, significant) %>%
  arrange(desc(roe))

message("Cell types enriched in Treatment (Ro/e > 1.5, FDR < 0.05):")
print(enriched_treatment[, c("cell_type", "roe", "p_value_adj")])

# Identify depleted cell types
depleted_treatment <- roe_df %>%
  filter(group == "Treatment", roe < 0.67, significant) %>%
  arrange(roe)

message("\nCell types depleted in Treatment (Ro/e < 0.67, FDR < 0.05):")
print(depleted_treatment[, c("cell_type", "roe", "p_value_adj")])

# ============================================
# Save Results
# ============================================

# Save Ro/e results
saveRDS(roe_result, "roe_result_basic.rds")
write.csv(roe_df, "roe_results_table.csv", row.names = FALSE)

message("\n=== Example Complete ===")
message("Files saved:")
message("- roe_heatmap_basic.png")
message("- roe_lollipop_treatment.png")
message("- roe_lollipop_control.png")
message("- roe_dotplot.png")
message("- roe_barchart.png")
message("- roe_result_basic.rds")
message("- roe_results_table.csv")
