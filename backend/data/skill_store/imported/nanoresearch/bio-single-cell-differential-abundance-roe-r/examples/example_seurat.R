# Seurat Integration Example
# Demonstrates Ro/e analysis with Seurat objects

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
# Create Synthetic Seurat Object
# ============================================

message("=== Creating Synthetic Seurat Object ===")

set.seed(42)

# Create count matrix
genes <- c(paste0("Gene", 1:100),
           "CD3D", "CD3E", "CD4", "CD8A", "CD8B",  # T cell markers
           "CD79A", "CD79B", "MS4A1",              # B cell markers
           "CD68", "CD14", "LYZ",                  # Macrophage markers
           "COL1A1", "COL1A2", "VIM",              # Fibroblast markers
           "PECAM1", "VWF")                        # Endothelial markers

n_cells <- 400
counts <- matrix(rpois(length(genes) * n_cells, lambda = 2),
                 nrow = length(genes), ncol = n_cells)
rownames(counts) <- genes
colnames(counts) <- paste0("Cell", 1:n_cells)

# Add expression patterns for cell types
# CD4 T cells
idx_cd4 <- 1:100
counts[c("CD3D", "CD3E", "CD4"), idx_cd4] <- counts[c("CD3D", "CD3E", "CD4"), idx_cd4] + rpois(300, 15)

# CD8 T cells
idx_cd8 <- 101:180
counts[c("CD3D", "CD3E", "CD8A", "CD8B"), idx_cd8] <- counts[c("CD3D", "CD3E", "CD8A", "CD8B"), idx_cd8] + rpois(320, 15)

# B cells
idx_b <- 181:250
counts[c("CD79A", "CD79B", "MS4A1"), idx_b] <- counts[c("CD79A", "CD79B", "MS4A1"), idx_b] + rpois(210, 15)

# Macrophages
idx_mac <- 251:320
counts[c("CD68", "CD14", "LYZ"), idx_mac] <- counts[c("CD68", "CD14", "LYZ"), idx_mac] + rpois(210, 15)

# Fibroblasts
idx_fibro <- 321:360
counts[c("COL1A1", "COL1A2", "VIM"), idx_fibro] <- counts[c("COL1A1", "COL1A2", "VIM"), idx_fibro] + rpois(120, 15)

# Endothelial
idx_endo <- 361:400
counts[c("PECAM1", "VWF"), idx_endo] <- counts[c("PECAM1", "VWF"), idx_endo] + rpois(80, 15)

# Create Seurat object
seurat_obj <- CreateSeuratObject(counts = counts, min.cells = 0, min.features = 0)
seurat_obj <- NormalizeData(seurat_obj)

# Add cell type annotations
seurat_obj$cell_type <- c(
  rep("CD4_T", 100),
  rep("CD8_T", 80),
  rep("B_cell", 70),
  rep("Macrophage", 70),
  rep("Fibroblast", 40),
  rep("Endothelial", 40)
)

# Add condition metadata with differential abundance pattern
# Tumor: More immune cells (T cells, Macrophages)
# Normal: More structural cells (Fibroblasts, Endothelial)
seurat_obj$condition <- c(
  rep("Tumor", 70), rep("Normal", 30),    # CD4_T: 70% Tumor
  rep("Tumor", 55), rep("Normal", 25),    # CD8_T: ~69% Tumor
  rep("Tumor", 35), rep("Normal", 35),    # B_cell: balanced
  rep("Tumor", 55), rep("Normal", 15),    # Macrophage: ~79% Tumor
  rep("Tumor", 10), rep("Normal", 30),    # Fibroblast: 25% Tumor
  rep("Tumor", 10), rep("Normal", 30)     # Endothelial: 25% Tumor
)

# Add tissue region metadata
seurat_obj$tissue_region <- sample(
  c("Tumor_core", "Tumor_margin", "Normal_stroma"),
  n_cells,
  replace = TRUE,
  prob = c(0.4, 0.3, 0.3)
)

# Add sample IDs
seurat_obj$sample_id <- paste0(
  seurat_obj$condition, "_",
  sample(1:5, n_cells, replace = TRUE)
)

cat("Seurat object created:\n")
cat("  Cells:", ncol(seurat_obj), "\n")
cat("  Genes:", nrow(seurat_obj), "\n")
cat("\nCell type distribution:\n")
print(table(seurat_obj$cell_type))
cat("\nCondition distribution:\n")
print(table(seurat_obj$condition))

# ============================================
# Basic Ro/e Analysis with Seurat
# ============================================

message("\n=== Running Ro/e Analysis on Seurat Object ===")

roe_result <- run_roe_analysis(
  seurat_obj,
  cell_type_col = "cell_type",
  group_col = "condition",
  method = "group"
)

print(roe_result)

# ============================================
# Visualization
# ============================================

message("\n=== Creating Visualizations ===")

# Lollipop plot for Tumor
p_tumor <- plot_roe_lollipop(
  roe_result,
  compare_group = "Tumor",
  highlight_sig = TRUE,
  title = "Cell Type Enrichment in Tumor"
)
print(p_tumor)
ggsave("roe_seurat_tumor.png", p_tumor, width = 8, height = 6)

# Heatmap
p_heatmap <- plot_roe_heatmap(roe_result, title = "Ro/e: Tumor vs Normal")
print(p_heatmap)
ggsave("roe_seurat_heatmap.png", p_heatmap, width = 8, height = 6)

# ============================================
# Subset Analysis by Tissue Region
# ============================================

message("\n=== Running Subset Analysis by Tissue Region ===")

roe_multi <- run_roe_analysis(
  seurat_obj,
  cell_type_col = "cell_type",
  group_col = "condition",
  subset_col = "tissue_region",
  method = "group"
)

# Access individual region results
cat("\nTumor Core Ro/e:\n")
print(roe_multi$Tumor_core$roe)

cat("\nTumor Margin Ro/e:\n")
print(roe_multi$Tumor_margin$roe)

cat("\nNormal Stroma Ro/e:\n")
print(roe_multi$Normal_stroma$roe)

# ============================================
# Multi-Region Visualization
# ============================================

message("\n=== Creating Multi-Region Visualizations ===")

# Individual lollipop plots for each region
regions <- c("Tumor_core", "Tumor_margin", "Normal_stroma")

for (region in regions) {
  if (region %in% names(roe_multi)) {
    p <- plot_roe_lollipop(
      roe_multi[[region]],
      compare_group = "Tumor",
      title = paste("Ro/e in", gsub("_", " ", region))
    )
    print(p)
    ggsave(paste0("roe_seurat_", tolower(region), ".png"), p, width = 8, height = 6)
  }
}

# Combined heatmap comparison
if (requireNamespace("patchwork", quietly = TRUE)) {
  library(patchwork)

  p1 <- plot_roe_heatmap(roe_multi$Tumor_core,
                         title = "Tumor Core") +
    theme(legend.position = "none")

  p2 <- plot_roe_heatmap(roe_multi$Tumor_margin,
                         title = "Tumor Margin") +
    theme(legend.position = "none")

  p3 <- plot_roe_heatmap(roe_multi$Normal_stroma,
                         title = "Normal Stroma")

  combined <- (p1 | p2 | p3) +
    plot_annotation(title = "Ro/e Across Tissue Regions")

  print(combined)
  ggsave("roe_seurat_combined.png", combined, width = 14, height = 5)
}

# ============================================
# Export Results
# ============================================

message("\n=== Exporting Results ===")

# Convert to data frames
roe_df_main <- roe_to_dataframe(roe_result)
roe_df_tumor_core <- roe_to_dataframe(roe_multi$Tumor_core)
roe_df_tumor_margin <- roe_to_dataframe(roe_multi$Tumor_margin)
roe_df_normal <- roe_to_dataframe(roe_multi$Normal_stroma)

# Add region info
roe_df_tumor_core$region <- "Tumor_core"
roe_df_tumor_margin$region <- "Tumor_margin"
roe_df_normal$region <- "Normal_stroma"

# Combine all
all_results <- bind_rows(
  roe_df_main %>% mutate(region = "Overall"),
  roe_df_tumor_core,
  roe_df_tumor_margin,
  roe_df_normal
)

# Save
saveRDS(roe_result, "roe_seurat_result.rds")
write.csv(all_results, "roe_seurat_all_results.csv", row.names = FALSE)

message("\nTop enrichments by region:")
print(
  all_results %>%
    filter(group == "Tumor", roe > 1.5) %>%
    select(region, cell_type, roe, p_value_adj) %>%
    arrange(region, desc(roe))
)

# ============================================
# Save Annotated Seurat Object
# ============================================

# Add Ro/e annotation to metadata
roe_annotations <- roe_df_main %>%
  select(cell_type, group, roe) %>%
  pivot_wider(names_from = group, values_from = roe, names_prefix = "roe_")

# Merge with Seurat metadata (using cell_type as key)
# This adds roe_Tumor and roe_Normal columns
meta <- seurat_obj@meta.data
meta <- left_join(meta, roe_annotations, by = c("cell_type" = "cell_type"))
seurat_obj@meta.data <- meta

cat("\nUpdated metadata columns:\n")
print(colnames(seurat_obj@meta.data))

# Save final object
saveRDS(seurat_obj, "seurat_with_roe.rds")

message("\n=== Example Complete ===")
message("Files saved:")
message("- roe_seurat_tumor.png")
message("- roe_seurat_heatmap.png")
message("- roe_seurat_tumor_core.png")
message("- roe_seurat_tumor_margin.png")
message("- roe_seurat_normal_stroma.png")
message("- roe_seurat_combined.png")
message("- roe_seurat_result.rds")
message("- roe_seurat_all_results.csv")
message("- seurat_with_roe.rds")
