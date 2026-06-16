# PDAC Neural Invasion Analysis Example
# Reproduces Ro/e analysis from PDAC NI paper

library(Seurat)
library(ggplot2)
library(dplyr)
library(tidyr)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source functions
source(file.path(base_dir, "scripts", "r", "roe_analysis.R"))
source(file.path(base_dir, "scripts", "r", "roe_visualization.R"))

# ============================================
# Create Synthetic PDAC Data
# ============================================

message("=== Creating Synthetic PDAC Dataset ===")

set.seed(42)

# Define cell subtypes relevant to PDAC NI
cell_subtypes <- c(
  "Schwann_Cycling",        # Neural-related
  "Schwann_Myelinating",
  "Schwann_Non_myelinating",
  "Neurons",
  "Cancer_Cells_Classical",
  "Cancer_Cells_EMT",       # EMT-related (linked to NI)
  "Cancer_Cells_Basal",
  "Macrophages_NLRP3",      # NLRP3+ macrophages
  "Macrophages_M1",
  "Macrophages_M2",
  "T_Cells_CD4",
  "T_Cells_CD8",
  "Fibroblasts_iCAF",
  "Fibroblasts_myCAF",
  "Endothelial",
  "DCs"
)

# Create cell counts for each NI group
# Based on literature: High NI has more Schwann cells, EMT cancer, NLRP3+ macrophages

# High NI sample proportions
high_ni_props <- c(
  Schwann_Cycling = 0.08,
  Schwann_Myelinating = 0.06,
  Schwann_Non_myelinating = 0.05,
  Neurons = 0.04,
  Cancer_Cells_Classical = 0.20,
  Cancer_Cells_EMT = 0.15,        # Enriched
  Cancer_Cells_Basal = 0.05,
  Macrophages_NLRP3 = 0.08,       # Enriched
  Macrophages_M1 = 0.05,
  Macrophages_M2 = 0.05,
  T_Cells_CD4 = 0.06,
  T_Cells_CD8 = 0.05,
  Fibroblasts_iCAF = 0.03,
  Fibroblasts_myCAF = 0.03,
  Endothelial = 0.02,
  DCs = 0.02
)

# Low NI sample proportions
low_ni_props <- c(
  Schwann_Cycling = 0.02,         # Depleted
  Schwann_Myelinating = 0.02,     # Depleted
  Schwann_Non_myelinating = 0.02, # Depleted
  Neurons = 0.01,
  Cancer_Cells_Classical = 0.25,
  Cancer_Cells_EMT = 0.05,        # Depleted
  Cancer_Cells_Basal = 0.08,
  Macrophages_NLRP3 = 0.02,       # Depleted
  Macrophages_M1 = 0.08,
  Macrophages_M2 = 0.08,
  T_Cells_CD4 = 0.10,
  T_Cells_CD8 = 0.08,
  Fibroblasts_iCAF = 0.08,
  Fibroblasts_myCAF = 0.06,
  Endothelial = 0.05,
  DCs = 0.03
)

# Normalize proportions
high_ni_props <- high_ni_props / sum(high_ni_props)
low_ni_props <- low_ni_props / sum(low_ni_props)

# Generate cells for each sample
n_cells_per_sample <- 200
n_high_ni_samples <- 6
n_low_ni_samples <- 6

# Create data for each sample
create_sample <- function(sample_id, ni_status, props) {
  cell_counts <- rmultinom(1, n_cells_per_sample, props)[, 1]
  cell_types <- rep(names(props), cell_counts)

  data.frame(
    cell_subtype = cell_types,
    NI_status = ni_status,
    sample_id = paste0(ni_status, "_", sample_id),
    stringsAsFactors = FALSE
  )
}

# Generate all samples
df_list <- list()

# High NI samples
for (i in 1:n_high_ni_samples) {
  df_list[[length(df_list) + 1]] <- create_sample(i, "High_NI", high_ni_props)
}

# Low NI samples
for (i in 1:n_low_ni_samples) {
  df_list[[length(df_list) + 1]] <- create_sample(i, "Low_NI", low_ni_props)
}

pdac_data <- bind_rows(df_list)

# Add broader cell type categories
pdac_data <- pdac_data %>%
  mutate(
    cell_type = case_when(
      grepl("Schwann", cell_subtype) ~ "Schwann",
      grepl("Neurons", cell_subtype) ~ "Neuronal",
      grepl("Cancer", cell_subtype) ~ "Cancer",
      grepl("Macrophage", cell_subtype) ~ "Macrophage",
      grepl("T_Cells", cell_subtype) ~ "T_Cell",
      grepl("Fibroblast", cell_subtype) ~ "Fibroblast",
      grepl("Endothelial", cell_subtype) ~ "Endothelial",
      grepl("DCs", cell_subtype) ~ "DC",
      TRUE ~ "Other"
    )
  )

cat("PDAC Dataset Created:\n")
cat("  Total cells:", nrow(pdac_data), "\n")
cat("  High NI samples:", n_high_ni_samples, "\n")
cat("  Low NI samples:", n_low_ni_samples, "\n\n")

cat("Cell subtype distribution by NI status:\n")
print(table(pdac_data$cell_subtype, pdac_data$NI_status))

# ============================================
# Ro/e Analysis: Fine-grained Subtypes
# ============================================

message("\n=== Ro/e Analysis: Cell Subtypes ===")

roe_subtype <- calculate_roe(
  cell_types = pdac_data$cell_subtype,
  groups = pdac_data$NI_status,
  method = "group"
)

print(roe_subtype)

# ============================================
# Visualization: Fine-grained Lollipop
# ============================================

message("\n=== Creating Fine-grained Lollipop Plot ===")

# Lollipop for High NI
p_high_ni <- plot_roe_lollipop(
  roe_subtype,
  compare_group = "High_NI",
  highlight_sig = TRUE,
  color_by_depletion = TRUE,
  title = "Cell Subtype Enrichment in High Neural Invasion"
)
print(p_high_ni)
ggsave("pdac_roe_subtype_high_ni.png", p_high_ni, width = 10, height = 8, dpi = 300)

# Lollipop for Low NI
p_low_ni <- plot_roe_lollipop(
  roe_subtype,
  compare_group = "Low_NI",
  highlight_sig = TRUE,
  color_by_depletion = TRUE,
  title = "Cell Subtype Enrichment in Low Neural Invasion"
)
print(p_low_ni)
ggsave("pdac_roe_subtype_low_ni.png", p_low_ni, width = 10, height = 8, dpi = 300)

# ============================================
# Side-by-Side Comparison Plot
# ============================================

message("\n=== Creating Comparison Plot ===")

roe_df_subtype <- roe_to_dataframe(roe_subtype)

# Create a side-by-side comparison
p_comparison <- ggplot(roe_df_subtype, aes(x = roe, y = cell_type)) +
  geom_vline(xintercept = 1, linetype = "dashed", color = "grey50") +
  geom_segment(aes(x = 1, xend = roe, y = cell_type, yend = cell_type),
               color = "grey70", linewidth = 0.5) +
  geom_point(aes(size = observed_prop, color = group), alpha = 0.8) +
  facet_wrap(~group, ncol = 2) +
  scale_color_manual(values = c("High_NI" = "#b2182b", "Low_NI" = "#2166ac")) +
  scale_size_continuous(name = "Proportion", range = c(2, 8)) +
  labs(
    title = "PDAC Cell Subtype Enrichment: High vs Low Neural Invasion",
    x = "Ro/e (Observed/Expected)",
    y = "Cell Subtype"
  ) +
  theme_minimal() +
  theme(
    axis.text = element_text(size = 10),
    axis.title = element_text(size = 12, face = "bold"),
    plot.title = element_text(size = 14, face = "bold", hjust = 0.5),
    strip.text = element_text(size = 12, face = "bold"),
    legend.position = "right"
  )

print(p_comparison)
ggsave("pdac_roe_subtype_comparison.png", p_comparison, width = 12, height = 10, dpi = 300)

# ============================================
# Ro/e Analysis: Broad Cell Types
# ============================================

message("\n=== Ro/e Analysis: Broad Cell Types ===")

roe_broad <- calculate_roe(
  cell_types = pdac_data$cell_type,
  groups = pdac_data$NI_status,
  method = "group"
)

print(roe_broad)

# Heatmap
p_heatmap <- plot_roe_heatmap(
  roe_broad,
  cluster_rows = TRUE,
  value_text_size = 5,
  title = "PDAC Cell Type Enrichment: High vs Low NI"
)
print(p_heatmap)
ggsave("pdac_roe_broad_heatmap.png", p_heatmap, width = 8, height = 6, dpi = 300)

# ============================================
# Key Findings Summary
# ============================================

message("\n=== Key Findings Summary ===")

roe_df <- roe_to_dataframe(roe_subtype)

# High NI enrichments
cat("\nCell subtypes ENRICHED in High NI:\n")
enriched_high <- roe_df %>%
  filter(group == "High_NI", roe > 1.5, significant) %>%
  arrange(desc(roe))
print(enriched_high[, c("cell_type", "roe", "observed_prop", "p_value_adj")])

# High NI depletions
cat("\nCell subtypes DEPLETED in High NI:\n")
depleted_high <- roe_df %>%
  filter(group == "High_NI", roe < 0.67, significant) %>%
  arrange(roe)
print(depleted_high[, c("cell_type", "roe", "observed_prop", "p_value_adj")])

# Create summary table
summary_df <- roe_df %>%
  filter(significant) %>%
  mutate(
    pattern = case_when(
      roe > 1.5 ~ "Strongly Enriched",
      roe > 1.2 ~ "Moderately Enriched",
      roe < 0.67 ~ "Strongly Depleted",
      roe < 0.83 ~ "Moderately Depleted",
      TRUE ~ "Neutral"
    )
  ) %>%
  select(cell_type, group, roe, pattern, p_value_adj) %>%
  arrange(group, desc(roe))

cat("\n=== Complete Summary Table ===\n")
print(summary_df)

# ============================================
# Focus on Neural Invasion Related Cells
# ============================================

message("\n=== Neural Invasion Related Cells ===")

neural_related <- c("Schwann_Cycling", "Schwann_Myelinating",
                   "Schwann_Non_myelinating", "Neurons",
                   "Cancer_Cells_EMT", "Macrophages_NLRP3")

neural_df <- roe_df %>%
  filter(cell_type %in% neural_related) %>%
  arrange(desc(roe))

cat("\nNeural invasion-related cell subtypes:\n")
print(neural_df[, c("cell_type", "group", "roe", "significant")])

# Neural focus plot
p_neural <- ggplot(neural_df, aes(x = cell_type, y = roe, fill = group)) +
  geom_bar(stat = "identity", position = "dodge", width = 0.7) +
  geom_hline(yintercept = 1, linetype = "dashed", color = "black") +
  scale_fill_manual(values = c("High_NI" = "#b2182b", "Low_NI" = "#2166ac")) +
  labs(
    title = "Neural Invasion Related Cell Subtypes",
    subtitle = "Ro/e values for cells implicated in PDAC neural invasion",
    x = "Cell Subtype",
    y = "Ro/e (Observed/Expected)",
    fill = "NI Status"
  ) +
  theme_minimal() +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1),
    axis.title = element_text(face = "bold"),
    plot.title = element_text(face = "bold", hjust = 0.5)
  )

print(p_neural)
ggsave("pdac_roe_neural_focus.png", p_neural, width = 10, height = 6, dpi = 300)

# ============================================
# Export Results
# ============================================

message("\n=== Exporting Results ===")

# Save all results
saveRDS(roe_subtype, "pdac_roe_subtype.rds")
saveRDS(roe_broad, "pdac_roe_broad.rds")

write.csv(roe_df, "pdac_roe_subtype_results.csv", row.names = FALSE)
write.csv(summary_df, "pdac_roe_summary.csv", row.names = FALSE)

# Create publication-ready table
pub_table <- roe_df %>%
  mutate(
    RoE_formatted = sprintf("%.2f", roe),
    p_formatted = ifelse(p_value_adj < 0.001, "<0.001", sprintf("%.3f", p_value_adj))
  ) %>%
  select(Cell_Type = cell_type, Group = group,
         RoE = RoE_formatted, FDR = p_formatted,
         Proportion = observed_prop)

write.csv(pub_table, "pdac_roe_publication_table.csv", row.names = FALSE)

message("\n=== Example Complete ===")
message("Files saved:")
message("- pdac_roe_subtype_high_ni.png")
message("- pdac_roe_subtype_low_ni.png")
message("- pdac_roe_subtype_comparison.png")
message("- pdac_roe_broad_heatmap.png")
message("- pdac_roe_neural_focus.png")
message("- pdac_roe_subtype.rds")
message("- pdac_roe_broad.rds")
message("- pdac_roe_subtype_results.csv")
message("- pdac_roe_summary.csv")
message("- pdac_roe_publication_table.csv")
