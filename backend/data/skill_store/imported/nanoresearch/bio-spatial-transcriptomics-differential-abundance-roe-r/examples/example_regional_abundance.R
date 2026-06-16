# Regional Cell Type Abundance Ro/e Analysis Example
# Demonstrates analysis of cell type enrichment within anatomical regions
# using deconvolution results

library(ggplot2)
library(dplyr)
library(reshape2)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source functions
source(file.path(base_dir, "scripts", "r", "regional_roe_analysis.R"))
source(file.path(base_dir, "scripts", "r", "regional_roe_visualization.R"))

# ============================================
# Create Synthetic Spatial Data with Regions
# ============================================

message("=== Creating Synthetic PDAC Data with Regions ===")

set.seed(42)

# Create spatial coordinates (simulating a tissue slice)
n_spots <- 400
x <- runif(n_spots, 0, 2000)  # 2000 microns
y <- runif(n_spots, 0, 1500)  # 1500 microns

coords <- data.frame(x = x, y = y)

# Define anatomical regions based on spatial position
center_x <- 1000
center_y <- 750
dist_from_center <- sqrt((x - center_x)^2 + (y - center_y)^2)

# Create regions
regions <- ifelse(
  dist_from_center < 300, "Tumor_Core",
  ifelse(
    dist_from_center < 500, "Tumor_Margin",
    ifelse(
      x < 500, "Normal_Duct",
      ifelse(
        dist_from_center > 700 & y > 1000, "Neural_Invasion_Zone",
        "Stroma"
      )
    )
  )
)

# Ensure minimum spots per region
region_table <- table(regions)
print("Region distribution:")
print(region_table)

# Define cell types
cell_types <- c(
  "Cancer_Classical",
  "Cancer_EMT",
  "Schwann_Myelinating",
  "Schwann_Non_myelinating",
  "Macrophage_NLRP3",
  "Macrophage_M2",
  "T_cell_CD8",
  "T_cell_CD4",
  "Fibroblast_iCAF",
  "Fibroblast_myCAF",
  "Endothelial",
  "Dendritic"
)

n_cell_types <- length(cell_types)

# Create deconvolution proportions with region-specific patterns
props <- matrix(0, nrow = n_spots, ncol = n_cell_types)
colnames(props) <- cell_types

for (i in 1:n_spots) {
  region <- regions[i]

  # Define base proportions for each region
  base_props <- switch(region,
    "Tumor_Core" = c(
      Cancer_Classical = 0.25, Cancer_EMT = 0.20,
      Schwann_Myelinating = 0.02, Schwann_Non_myelinating = 0.02,
      Macrophage_NLRP3 = 0.15, Macrophage_M2 = 0.08,
      T_cell_CD8 = 0.05, T_cell_CD4 = 0.05,
      Fibroblast_iCAF = 0.05, Fibroblast_myCAF = 0.05,
      Endothelial = 0.05, Dendritic = 0.03
    ),
    "Tumor_Margin" = c(
      Cancer_Classical = 0.30, Cancer_EMT = 0.10,
      Schwann_Myelinating = 0.03, Schwann_Non_myelinating = 0.03,
      Macrophage_NLRP3 = 0.08, Macrophage_M2 = 0.12,
      T_cell_CD8 = 0.10, T_cell_CD4 = 0.08,
      Fibroblast_iCAF = 0.08, Fibroblast_myCAF = 0.04,
      Endothelial = 0.03, Dendritic = 0.01
    ),
    "Neural_Invasion_Zone" = c(
      Cancer_Classical = 0.10, Cancer_EMT = 0.25,
      Schwann_Myelinating = 0.20, Schwann_Non_myelinating = 0.15,
      Macrophage_NLRP3 = 0.10, Macrophage_M2 = 0.05,
      T_cell_CD8 = 0.03, T_cell_CD4 = 0.02,
      Fibroblast_iCAF = 0.05, Fibroblast_myCAF = 0.03,
      Endothelial = 0.01, Dendritic = 0.01
    ),
    "Normal_Duct" = c(
      Cancer_Classical = 0.05, Cancer_EMT = 0.02,
      Schwann_Myelinating = 0.02, Schwann_Non_myelinating = 0.02,
      Macrophage_NLRP3 = 0.02, Macrophage_M2 = 0.05,
      T_cell_CD8 = 0.10, T_cell_CD4 = 0.15,
      Fibroblast_iCAF = 0.25, Fibroblast_myCAF = 0.15,
      Endothelial = 0.10, Dendritic = 0.07
    ),
    "Stroma" = c(
      Cancer_Classical = 0.02, Cancer_EMT = 0.03,
      Schwann_Myelinating = 0.02, Schwann_Non_myelinating = 0.02,
      Macrophage_NLRP3 = 0.03, Macrophage_M2 = 0.08,
      T_cell_CD8 = 0.12, T_cell_CD4 = 0.10,
      Fibroblast_iCAF = 0.30, Fibroblast_myCAF = 0.20,
      Endothelial = 0.06, Dendritic = 0.02
    )
  )

  # Add noise
  noise <- runif(n_cell_types, -0.03, 0.03)
  props[i, ] <- pmax(base_props + noise, 0)
  props[i, ] <- props[i, ] / sum(props[i, ])
}

cat("\nData created:")
cat("\n  Spots:", n_spots)
cat("\n  Cell types:", n_cell_types)
cat("\n  Regions:", length(unique(regions)))
cat("\n\nMean proportions by region:\n")
for (region in unique(regions)) {
  cat("\n", region, ":\n")
  region_props <- colMeans(props[regions == region, ])
  print(round(region_props[region_props > 0.05], 3))
}

# ============================================
# Regional Ro/e Analysis
# ============================================

message("\n=== Running Regional Ro/e Analysis ===")

result <- calculate_regional_roe(
  proportions = props,
  regions = regions,
  aggr_method = "mean",
  min_spots = 5,
  min_proportion = 0.01
)

print(result)

# ============================================
# View Results
# ============================================

message("\n=== Regional Ro/e Results ===")

roe_df <- regional_roe_to_dataframe(result)

# Top enrichments per region
for (region in unique(roe_df$region)) {
  cat("\n", region, "- Top enriched cell types:\n")
  top <- roe_df %>%
    filter(region == !!region) %>%
    arrange(desc(roe)) %>%
    head(3)
  print(top[, c("cell_type", "roe", "observed", "expected")])
}

# ============================================
# Regional Specificity Analysis
# ============================================

message("\n=== Regional Specificity Scores ===")

specificity <- calculate_regional_specificity(result)
print(specificity)

# ============================================
# Visualizations
# ============================================

message("\n=== Creating Visualizations ===")

# 1. Spatial map of regions
p_regions <- plot_spatial_regions(coords, regions, title = "Tissue Regions")
print(p_regions)
ggsave("regional_spatial_map.png", p_regions, width = 10, height = 8, dpi = 300)

# 2. Regional Ro/e Heatmap
p_heatmap <- plot_regional_roe_heatmap(
  result,
  cluster_rows = TRUE,
  cluster_cols = FALSE,
  show_values = TRUE,
  title = "Cell Type Enrichment by Region (Ro/e)"
)
print(p_heatmap)
ggsave("regional_roe_heatmap.png", p_heatmap, width = 10, height = 8, dpi = 300)

# 3. Lollipop plots for key regions
for (region in c("Neural_Invasion_Zone", "Tumor_Core")) {
  p_lolli <- plot_regional_roe_lollipop(
    result,
    region = region,
    title = paste("Cell Type Enrichment in", gsub("_", " ", region))
  )
  print(p_lolli)
  ggsave(paste0("regional_lollipop_", tolower(region), ".png"),
         p_lolli, width = 8, height = 6)
}

# 4. Regional composition stacked bar
p_comp <- plot_regional_composition(
  result,
  normalize = TRUE,
  n_highlight = 8,
  title = "Cell Type Composition by Region"
)
print(p_comp)
ggsave("regional_composition.png", p_comp, width = 10, height = 6, dpi = 300)

# 5. Regional specificity plot
p_spec <- plot_regional_specificity(specificity, title = "Cell Type Regional Specificity")
print(p_spec)
ggsave("regional_specificity.png", p_spec, width = 8, height = 6, dpi = 300)

# 6. Multi-region comparison
p_multi <- plot_regional_comparison(result, n_top = 8)
print(p_multi)
ggsave("regional_comparison.png", p_multi, width = 12, height = 10, dpi = 300)

# ============================================
# Key Findings
# ============================================

message("\n=== Key Findings ===")

# Neural invasion zone specific
ni_zone <- roe_df %>%
  filter(region == "Neural_Invasion_Zone", roe > 1.5) %>%
  arrange(desc(roe))

message("\nCell types enriched in Neural Invasion Zone:")
print(ni_zone[, c("cell_type", "roe", "significant")])

# Compare Neural Invasion Zone vs Tumor Core
message("\nComparing Neural Invasion Zone vs Tumor Core:")
comparison <- roe_df %>%
  filter(region %in% c("Neural_Invasion_Zone", "Tumor_Core")) %>%
  select(cell_type, region, roe) %>%
  pivot_wider(names_from = region, values_from = roe) %>%
  mutate(
    ni_vs_core = Neural_Invasion_Zone / Tumor_Core,
    pattern = ifelse(ni_vs_core > 2, "NI-specific",
              ifelse(ni_vs_core < 0.5, "Core-specific", "Both"))
  ) %>%
  arrange(desc(ni_vs_core))

print(comparison[, c("cell_type", "Neural_Invasion_Zone", "Tumor_Core", "ni_vs_core", "pattern")])

# ============================================
# Save Results
# ============================================

saveRDS(result, "regional_roe_result.rds")
write.csv(roe_df, "regional_roe_results.csv", row.names = FALSE)
write.csv(specificity, "regional_specificity_scores.csv", row.names = FALSE)

message("\n=== Example Complete ===")
message("Files saved:")
message("- regional_spatial_map.png")
message("- regional_roe_heatmap.png")
message("- regional_lollipop_neural_invasion_zone.png")
message("- regional_lollipop_tumor_core.png")
message("- regional_composition.png")
message("- regional_specificity.png")
message("- regional_comparison.png")
message("- regional_roe_result.rds")
message("- regional_roe_results.csv")
message("- regional_specificity_scores.csv")
