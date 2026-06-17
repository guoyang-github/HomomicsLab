# Basic Spatial Ro/e Analysis Example
# Demonstrates spatial co-occurrence analysis with synthetic data

library(ggplot2)
library(dplyr)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source functions
source(file.path(base_dir, "scripts", "r", "spatial_roe_analysis.R"))
source(file.path(base_dir, "scripts", "r", "spatial_roe_visualization.R"))

# ============================================
# Create Synthetic Spatial Data
# ============================================

message("=== Creating Synthetic Spatial Data ===")

set.seed(42)

# Create a 20x20 grid of spots (400 spots)
grid_size <- 20
n_spots <- grid_size * grid_size

# Coordinates
x <- rep(1:grid_size, each = grid_size) * 50  # 50 micron spacing
y <- rep(1:grid_size, grid_size) * 50

coords <- data.frame(x = x, y = y)
rownames(coords) <- paste0("Spot_", 1:n_spots)

# Create spatial patterns:
# - Cancer cells form a central cluster (tumor core)
# - T cells form a rim around the tumor (immune exclusion)
# - Macrophages infiltrate the tumor
# - Fibroblasts in the stroma (outer region)

cell_types <- character(n_spots)

# Define regions
center_x <- mean(x)
center_y <- mean(y)
dist_from_center <- sqrt((x - center_x)^2 + (y - center_y)^2)

# Normalize distance to 0-1
dist_norm <- dist_from_center / max(dist_from_center)

# Assign cell types based on spatial position
for (i in 1:n_spots) {
  d <- dist_norm[i]

  if (d < 0.3) {
    # Tumor core: mostly cancer, some macrophages
    cell_types[i] <- sample(c("Cancer", "Cancer", "Cancer", "Macrophage"), 1)
  } else if (d < 0.5) {
    # Tumor margin: mix of cancer, T cells, macrophages
    cell_types[i] <- sample(c("Cancer", "T_cell", "Macrophage", "Macrophage"), 1)
  } else if (d < 0.7) {
    # Stroma interface: T cells, fibroblasts
    cell_types[i] <- sample(c("T_cell", "Fibroblast", "Fibroblast"), 1)
  } else {
    # Outer stroma: mostly fibroblasts
    cell_types[i] <- sample(c("Fibroblast", "Fibroblast", "Fibroblast", "T_cell"), 1)
  }
}

cat("Spatial data created:\n")
cat("  Total spots:", n_spots, "\n")
cat("  Grid size:", grid_size, "x", grid_size, "\n")
cat("  Spot spacing: 50 microns\n\n")

cat("Cell type distribution:\n")
print(table(cell_types))

# ============================================
# Spatial Ro/e Analysis
# ============================================

message("\n=== Running Spatial Ro/e Analysis ===")

# Run with radius-based neighborhoods
result <- calculate_spatial_roe(
  cell_types = cell_types,
  coords = coords,
  method = "radius",
  radius = 100,        # 100 micron radius
  min_neighbors = 3
)

print(result)

# ============================================
# View Results
# ============================================

message("\n=== Co-occurrence Results ===")

# Convert to data frame
roe_df <- spatial_roe_to_dataframe(result)

# Show top co-localizations
top_coloc <- roe_df %>%
  filter(cell_type_a != cell_type_b, roe > 1) %>%
  arrange(desc(roe)) %>%
  head(10)

message("\nTop 10 co-localizations:")
print(top_coloc[, c("cell_type_a", "cell_type_b", "roe", "significant")])

# Show exclusions (Ro/e < 1)
exclusions <- roe_df %>%
  filter(cell_type_a != cell_type_b, roe < 1) %>%
  arrange(roe) %>%
  head(10)

message("\nTop 10 exclusions:")
print(exclusions[, c("cell_type_a", "cell_type_b", "roe", "significant")])

# ============================================
# Visualizations
# ============================================

message("\n=== Creating Visualizations ===")

# 1. Spatial distribution of cell types
p_spatial <- ggplot(coords, aes(x = x, y = y, color = cell_types)) +
  geom_point(size = 2) +
  coord_fixed() +
  scale_color_brewer(palette = "Set1") +
  labs(
    title = "Spatial Distribution of Cell Types",
    x = "X (microns)",
    y = "Y (microns)",
    color = "Cell Type"
  ) +
  theme_minimal() +
  theme(
    plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
    axis.title = element_text(size = 12, face = "bold")
  )

print(p_spatial)
ggsave("spatial_celltype_distribution.png", p_spatial, width = 8, height = 7, dpi = 300)

# 2. Ro/e Heatmap
p_heatmap <- plot_spatial_roe_heatmap(
  result,
  show_values = TRUE,
  title = "Spatial Co-occurrence (Ro/e)"
)
print(p_heatmap)
ggsave("spatial_roe_heatmap.png", p_heatmap, width = 8, height = 7, dpi = 300)

# 3. Network visualization
p_network <- plot_spatial_roe_network(
  result,
  min_roe = 1.3,
  layout = "circle",
  title = "Cell Type Co-localization Network"
)
if (!is.null(p_network)) {
  print(p_network)
  ggsave("spatial_roe_network.png", p_network, width = 8, height = 8, dpi = 300)
}

# 4. Lollipop plot of top interactions
p_lollipop <- plot_spatial_roe_lollipop(
  result,
  n_top = 12,
  exclude_self = TRUE,
  title = "Top Spatial Co-localizations"
)
print(p_lollipop)
ggsave("spatial_roe_lollipop.png", p_lollipop, width = 10, height = 6, dpi = 300)

# 5. Neighborhood map
p_map <- plot_neighborhood_map(result, coords, spot_size = 1.5)
print(p_map)
ggsave("spatial_neighborhood_map.png", p_map, width = 8, height = 7, dpi = 300)

# ============================================
# Key Findings
# ============================================

message("\n=== Key Findings ===")

# Cancer-Macrophage co-localization
cancer_macro <- roe_df %>%
  filter(
    (cell_type_a == "Cancer" & cell_type_b == "Macrophage") |
    (cell_type_a == "Macrophage" & cell_type_b == "Cancer")
  ) %>%
  slice(1)  # Get one direction

message("\nCancer-Macrophage interaction:")
message(sprintf("  Ro/e: %.2f (expected: %.3f, observed: %.3f)",
                cancer_macro$roe,
                cancer_macro$expected,
                cancer_macro$observed))

# T cell exclusion from cancer
tcell_cancer <- roe_df %>%
  filter(
    (cell_type_a == "T_cell" & cell_type_b == "Cancer") |
    (cell_type_a == "Cancer" & cell_type_b == "T_cell")
  ) %>%
  slice(1)

message("\nT_cell-Cancer interaction:")
message(sprintf("  Ro/e: %.2f (expected: %.3f, observed: %.3f)",
                tcell_cancer$roe,
                tcell_cancer$expected,
                tcell_cancer$observed))
if (tcell_cancer$roe < 1) {
  message("  -> T cells are EXCLUDED from cancer regions (immune exclusion)")
}

# ============================================
# Save Results
# ============================================

saveRDS(result, "spatial_roe_result.rds")
write.csv(roe_df, "spatial_roe_results.csv", row.names = FALSE)

message("\n=== Example Complete ===")
message("Files saved:")
message("- spatial_celltype_distribution.png")
message("- spatial_roe_heatmap.png")
message("- spatial_roe_network.png")
message("- spatial_roe_lollipop.png")
message("- spatial_neighborhood_map.png")
message("- spatial_roe_result.rds")
message("- spatial_roe_results.csv")
