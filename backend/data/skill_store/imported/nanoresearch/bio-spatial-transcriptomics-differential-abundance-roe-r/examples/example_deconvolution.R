# Deconvolution-Based Spatial Ro/e Example
# Demonstrates Ro/e analysis using deconvolution proportions

library(ggplot2)
library(dplyr)
library(reshape2)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source functions
source(file.path(base_dir, "scripts", "r", "spatial_roe_analysis.R"))
source(file.path(base_dir, "scripts", "r", "spatial_roe_visualization.R"))

# ============================================
# Create Synthetic Deconvolution Data
# ============================================

message("=== Creating Synthetic Deconvolution Data ===")

set.seed(123)

# Create a 15x15 grid
grid_size <- 15
n_spots <- grid_size * grid_size

# Coordinates
x <- rep(1:grid_size, each = grid_size) * 55  # 55 micron spacing (Visium)
y <- rep(1:grid_size, grid_size) * 55

coords <- data.frame(x = x, y = y)

# Define cell types
cell_types <- c(
  "Schwann_Myelinating",
  "Schwann_Non_myelinating",
  "Cancer_Classical",
  "Cancer_EMT",
  "Macrophage_NLRP3",
  "Macrophage_M2",
  "T_cell_CD8",
  "Fibroblast"
)

n_cell_types <- length(cell_types)

# Create deconvolution proportions with spatial patterns
# Simulating a tumor with neural invasion

props <- matrix(0, nrow = n_spots, ncol = n_cell_types)
colnames(props) <- cell_types

center_x <- mean(x)
center_y <- mean(y)
dist_from_center <- sqrt((x - center_x)^2 + (y - center_y)^2)
dist_norm <- dist_from_center / max(dist_from_center)

for (i in 1:n_spots) {
  d <- dist_norm[i]

  # Base proportions (sum to 1)
  if (d < 0.25) {
    # Tumor core: EMT cancer + NLRP3 macrophages
    props[i, ] <- c(0.02, 0.02, 0.20, 0.40, 0.20, 0.08, 0.05, 0.03)
  } else if (d < 0.4) {
    # Neural invasion zone: Schwann + EMT cancer + NLRP3
    props[i, ] <- c(0.15, 0.10, 0.15, 0.25, 0.15, 0.08, 0.07, 0.05)
  } else if (d < 0.6) {
    # Tumor margin: Classical cancer + M2 macrophages
    props[i, ] <- c(0.05, 0.03, 0.40, 0.15, 0.05, 0.15, 0.10, 0.07)
  } else {
    # Stroma: Fibroblasts + CD8 T cells
    props[i, ] <- c(0.02, 0.02, 0.05, 0.05, 0.02, 0.08, 0.30, 0.46)
  }

  # Add noise
  noise <- runif(n_cell_types, -0.05, 0.05)
  props[i, ] <- pmax(props[i, ] + noise, 0)
  props[i, ] <- props[i, ] / sum(props[i, ])  # Renormalize
}

cat("Deconvolution data created:\n")
cat("  Spots:", n_spots, "\n")
cat("  Cell types:", n_cell_types, "\n")
cat("\nMean proportions:\n")
print(round(colMeans(props), 3))

# ============================================
# Spatial Ro/e Analysis
# ============================================

message("\n=== Running Spatial Ro/e Analysis ===")

result <- calculate_spatial_roe(
  cell_types = props,
  coords = coords,
  method = "radius",
  radius = 120,  # ~2 Visium spots
  min_neighbors = 3
)

print(result)

# ============================================
# Analyze Neural Invasion Patterns
# ============================================

message("\n=== Neural Invasion Pattern Analysis ===")

roe_df <- spatial_roe_to_dataframe(result)

# Focus on Schwann cell interactions
schwann_interactions <- roe_df %>%
  filter(
    grepl("Schwann", cell_type_a) | grepl("Schwann", cell_type_b)
  ) %>%
  filter(cell_type_a != cell_type_b) %>%
  arrange(desc(roe))

message("\nSchwann cell co-localization patterns:")
print(schwann_interactions[, c("cell_type_a", "cell_type_b", "roe", "significant")])

# Cancer EMT interactions
emt_interactions <- roe_df %>%
  filter(
    cell_type_a == "Cancer_EMT" | cell_type_b == "Cancer_EMT"
  ) %>%
  filter(cell_type_a != cell_type_b) %>%
  arrange(desc(roe))

message("\nCancer EMT co-localization patterns:")
print(emt_interactions[, c("cell_type_a", "cell_type_b", "roe", "significant")])

# ============================================
# Visualizations
# ============================================

message("\n=== Creating Visualizations ===")

# 1. Spatial map of key cell types
p_schwann <- ggplot(coords, aes(x = x, y = y, color = props[, "Schwann_Myelinating"])) +
  geom_point(size = 3) +
  scale_color_viridis_c(name = "Proportion", option = "plasma") +
  coord_fixed() +
  labs(
    title = "Myelinating Schwann Cell Distribution",
    x = "X (microns)",
    y = "Y (microns)"
  ) +
  theme_minimal()

print(p_schwann)
ggsave("deconv_schwann_map.png", p_schwann, width = 7, height = 7, dpi = 300)

p_emt <- ggplot(coords, aes(x = x, y = y, color = props[, "Cancer_EMT"])) +
  geom_point(size = 3) +
  scale_color_viridis_c(name = "Proportion", option = "magma") +
  coord_fixed() +
  labs(
    title = "EMT Cancer Cell Distribution",
    x = "X (microns)",
    y = "Y (microns)"
  ) +
  theme_minimal()

print(p_emt)
ggsave("deconv_emt_map.png", p_emt, width = 7, height = 7, dpi = 300)

# 2. Ro/e heatmap
p_heatmap <- plot_spatial_roe_heatmap(
  result,
  show_values = TRUE,
  title = "Ro/e: Neural Invasion Related Cell Types"
)
print(p_heatmap)
ggsave("deconv_roe_heatmap.png", p_heatmap, width = 8, height = 7, dpi = 300)

# 3. Network of significant interactions
p_network <- plot_spatial_roe_network(
  result,
  min_roe = 1.2,
  layout = "fr",
  title = "Spatial Co-localization Network\n(Neural Invasion Context)"
)
if (!is.null(p_network)) {
  print(p_network)
  ggsave("deconv_roe_network.png", p_network, width = 9, height = 9, dpi = 300)
}

# 4. Lollipop plot
p_lollipop <- plot_spatial_roe_lollipop(
  result,
  n_top = 15,
  title = "Top Spatial Co-localizations (Deconvolution-based)"
)
print(p_lollipop)
ggsave("deconv_roe_lollipop.png", p_lollipop, width = 10, height = 7, dpi = 300)

# ============================================
# Save Results
# ============================================

saveRDS(result, "spatial_roe_deconv_result.rds")
write.csv(roe_df, "spatial_roe_deconv_results.csv", row.names = FALSE)

message("\n=== Example Complete ===")
