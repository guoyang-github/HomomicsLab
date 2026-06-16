# Bootstrap Confidence Intervals Example
# Demonstrates Ro/e analysis with statistical confidence intervals

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
# Create Dataset with Uncertainty
# ============================================

message("=== Creating Test Data with Sample Variation ===")

set.seed(123)

# Simulate multiple samples per group
n_samples_per_group <- 8
cells_per_sample <- 50

# Sample-level proportions (with variation)
# Treatment samples: generally higher immune cells
# Control samples: generally higher structural cells

create_sample_data <- function(sample_id, group) {
  if (group == "Treatment") {
    # Treatment: variable but generally enriched for immune
    props <- c(
      CD4_T = runif(1, 0.25, 0.35),      # 25-35%
      CD8_T = runif(1, 0.15, 0.25),      # 15-25%
      B_cell = runif(1, 0.10, 0.20),     # 10-20%
      Macrophage = runif(1, 0.15, 0.25), # 15-25%
      Fibroblast = runif(1, 0.10, 0.20)  # 10-20%
    )
  } else {
    # Control: different pattern
    props <- c(
      CD4_T = runif(1, 0.15, 0.25),
      CD8_T = runif(1, 0.10, 0.20),
      B_cell = runif(1, 0.10, 0.20),
      Macrophage = runif(1, 0.05, 0.15),
      Fibroblast = runif(1, 0.25, 0.35)  # More fibroblasts
    )
  }

  # Normalize to sum to 1
  props <- props / sum(props)

  # Generate cell types
  cell_counts <- rmultinom(1, cells_per_sample, props)[, 1]
  cell_types <- rep(names(props), cell_counts)
  groups <- rep(group, length(cell_types))
  samples <- rep(paste0(group, "_", sample_id), length(cell_types))

  data.frame(
    cell_type = cell_types,
    group = groups,
    sample = samples,
    stringsAsFactors = FALSE
  )
}

# Generate all samples
df_list <- list()
for (i in 1:n_samples_per_group) {
  df_list[[length(df_list) + 1]] <- create_sample_data(i, "Treatment")
  df_list[[length(df_list) + 1]] <- create_sample_data(i, "Control")
}
full_data <- bind_rows(df_list)

cat("Total cells:", nrow(full_data), "\n")
cat("Samples:", length(unique(full_data$sample)), "\n")
cat("\nCell counts by group:\n")
print(table(full_data$cell_type, full_data$group))

# ============================================
# Bootstrap Ro/e Analysis
# ============================================

message("\n=== Running Bootstrap Ro/e Analysis ===")
message("This may take a minute (1000 bootstrap iterations)...")

# Use fewer iterations for faster example
roe_result <- calculate_roe_bootstrap(
  cell_types = full_data$cell_type,
  groups = full_data$group,
  n_bootstrap = 500,  # Use 1000 for production
  conf_level = 0.95
)

# Print results
print(roe_result)

# ============================================
# View Results with Confidence Intervals
# ============================================

message("\n=== Results with 95% Confidence Intervals ===")

roe_df <- roe_to_dataframe(roe_result)
print(roe_df)

# Identify robust enrichments (CI doesn't cross 1)
robust_enrichments <- roe_df %>%
  filter(ci_lower > 1) %>%
  arrange(desc(roe))

message("\nRobust enrichments (95% CI entirely above 1):")
print(robust_enrichments[, c("cell_type", "group", "roe", "ci_lower", "ci_upper")])

robust_depletions <- roe_df %>%
  filter(ci_upper < 1) %>%
  arrange(roe)

message("\nRobust depletions (95% CI entirely below 1):")
print(robust_depletions[, c("cell_type", "group", "roe", "ci_lower", "ci_upper")])

# ============================================
# Visualization: CI Plot
# ============================================

message("\n=== Creating Confidence Interval Plot ===")

# Custom CI plot
p_ci <- ggplot(roe_df, aes(x = cell_type, y = roe, color = group)) +
  geom_hline(yintercept = 1, linetype = "dashed", color = "grey50") +
  geom_pointrange(
    aes(ymin = ci_lower, ymax = ci_upper),
    position = position_dodge(width = 0.5),
    size = 0.8
  ) +
  coord_flip() +
  scale_color_brewer(palette = "Set1") +
  labs(
    title = "Ro/e with 95% Bootstrap Confidence Intervals",
    subtitle = "Error bars show bootstrap CI; Points without crossing the line = robust finding",
    x = "Cell Type",
    y = "Ro/e (Observed/Expected)",
    color = "Group"
  ) +
  theme_minimal() +
  theme(
    axis.text = element_text(size = 11),
    axis.title = element_text(size = 12, face = "bold"),
    plot.title = element_text(size = 14, face = "bold"),
    legend.position = "right"
  )

print(p_ci)
ggsave("roe_bootstrap_ci.png", p_ci, width = 10, height = 6, dpi = 300)

# ============================================
# Compare with and without bootstrap
# ============================================

message("\n=== Comparing Point Estimate vs Bootstrap CI ===")

# Standard calculation (fast)
roe_standard <- calculate_roe(full_data$cell_type, full_data$group)

# Create comparison plot
comparison_df <- data.frame(
  cell_type = rep(roe_df$cell_type, 2),
  group = rep(roe_df$group, 2),
  roe = c(roe_df$roe,
          as.vector(roe_standard$roe)),
  method = rep(c("Bootstrap", "Standard"), each = nrow(roe_df))
)

p_compare <- ggplot(comparison_df, aes(x = cell_type, y = roe, fill = method)) +
  geom_bar(stat = "identity", position = "dodge", width = 0.7) +
  geom_hline(yintercept = 1, linetype = "dashed") +
  facet_wrap(~group) +
  coord_flip() +
  scale_fill_manual(values = c("Bootstrap" = "steelblue", "Standard" = "coral")) +
  labs(
    title = "Ro/e: Bootstrap vs Standard Calculation",
    x = "Cell Type",
    y = "Ro/e"
  ) +
  theme_minimal()

print(p_compare)
ggsave("roe_comparison.png", p_compare, width = 10, height = 6)

# ============================================
# Sample-Level Analysis
# ============================================

message("\n=== Sample-Level Proportion Analysis ===")

sample_props <- full_data %>%
  group_by(sample, group, cell_type) %>%
  summarise(count = n(), .groups = "drop") %>%
  group_by(sample) %>%
  mutate(prop = count / sum(count))

# Boxplot of proportions by group
p_box <- ggplot(sample_props, aes(x = cell_type, y = prop, fill = group)) +
  geom_boxplot() +
  coord_flip() +
  scale_fill_brewer(palette = "Set1") +
  labs(
    title = "Cell Type Proportion Distribution by Sample",
    x = "Cell Type",
    y = "Proportion",
    fill = "Group"
  ) +
  theme_minimal()

print(p_box)
ggsave("roe_sample_boxplot.png", p_box, width = 10, height = 6)

# ============================================
# Save Results
# ============================================

saveRDS(roe_result, "roe_bootstrap_result.rds")
write.csv(roe_df, "roe_bootstrap_results.csv", row.names = FALSE)

message("\n=== Example Complete ===")
message("Files saved:")
message("- roe_bootstrap_ci.png")
message("- roe_comparison.png")
message("- roe_sample_boxplot.png")
message("- roe_bootstrap_result.rds")
message("- roe_bootstrap_results.csv")
