# Advanced Example: miloR Comprehensive Analysis
# ==============================================
#
# Advanced workflow demonstrating:
# - Custom graph building
# - Neighborhood grouping
# - Marker gene identification
# - Complex experimental designs
# - Batch effect handling
# - Comprehensive visualization

# Load required libraries
library(miloR)
library(SingleCellExperiment)
library(ggplot2)
library(ComplexHeatmap)

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=", rep("=", 70), "\n", sep = "")
cat("miloR Advanced Example\n")
cat("=", rep("=", 70), "\n\n", sep = "")

# -----------------------------------------------------------------------------
# Step 1: Create or load data with batch structure
# -----------------------------------------------------------------------------
cat("[Step 1] Setting up data with batch structure...\n")

# Create test data with batch effect
set.seed(42)
n_cells_per_sample <- 1000
n_samples <- 8
n_genes <- 2000

# Sample structure with batch and condition
samples <- paste0("Sample", 1:n_samples)
conditions <- rep(c("Control", "Treatment"), each = n_samples/2)
batches <- rep(c("Batch1", "Batch2"), n_samples/2)
replicates <- rep(1:2, 4)

# Generate expression matrix
expr_matrix <- matrix(rpois(n_genes * n_cells_per_sample * n_samples, lambda = 5),
                      nrow = n_genes)
rownames(expr_matrix) <- paste0("Gene", 1:n_genes)
colnames(expr_matrix) <- paste0("Cell", 1:(n_cells_per_sample * n_samples))

# Add treatment effect to specific cell populations
treatment_cells <- 1:floor(n_cells_per_sample * 0.25)
for (s in 5:n_samples) {  # Treatment samples
  cell_idx <- ((s-1) * n_cells_per_sample + 1):(s * n_cells_per_sample)
  expr_matrix[, cell_idx[treatment_cells]] <- expr_matrix[, cell_idx[treatment_cells]] * 2
}

# Log normalize
logcounts <- log2(expr_matrix + 1)

# Compute PCA
pca <- prcomp(t(logcounts), center = TRUE, scale. = TRUE)
pca_dims <- pca$x[, 1:30]

# Compute UMAP (simplified)
set.seed(42)
umap_dims <- pca$x[, 1:2] + rnorm(length(pca$x[, 1:2]), 0, 0.1)

# Create cell metadata
cell_metadata <- data.frame(
  sample_id = factor(rep(samples, each = n_cells_per_sample)),
  condition = factor(rep(conditions, each = n_cells_per_sample)),
  batch = factor(rep(batches, each = n_cells_per_sample)),
  replicate = factor(rep(replicates, each = n_cells_per_sample)),
  row.names = colnames(expr_matrix)
)

# Create cell type labels (simulate 5 cell types)
cell_types <- sample(c("T_cell", "B_cell", "Monocyte", "NK_cell", "DC"),
                     n_cells_per_sample * n_samples, replace = TRUE,
                     prob = c(0.3, 0.2, 0.25, 0.15, 0.1))
cell_metadata$cell_type <- factor(cell_types)

# Create SCE
sce <- SingleCellExperiment(
  assays = list(counts = expr_matrix, logcounts = logcounts),
  colData = cell_metadata,
  reducedDims = SimpleList(PCA = pca_dims, UMAP = umap_dims)
)

cat(sprintf("  Created SCE with %d cells, %d genes\n", ncol(sce), nrow(sce)))
cat(sprintf("  Conditions: %s\n", paste(unique(sce$condition), collapse = ", ")))
cat(sprintf("  Batches: %s\n", paste(unique(sce$batch), collapse = ", ")))
cat(sprintf("  Cell types: %s\n", paste(unique(sce$cell_type), collapse = ", ")))

# -----------------------------------------------------------------------------
# Step 2: Build Milo object step by step (custom parameters)
# -----------------------------------------------------------------------------
cat("\n[Step 2] Building Milo object with custom parameters...\n")

# Recommend parameters based on dataset size
rec_k <- recommend_milo_k(ncol(sce))
rec_prop <- recommend_milo_prop(ncol(sce))

# Create Milo object
milo_obj <- create_milo_object(sce)

# Build graph with custom k
milo_obj <- build_milo_graph(milo_obj, k = rec_k, d = 30, reduced.dim = "PCA")

# Make neighborhoods with custom prop
milo_obj <- make_milo_neighborhoods(milo_obj, prop = rec_prop, k = rec_k,
                                    d = 30, refined = TRUE, seed = 42)

# Calculate distances for spatial FDR
milo_obj <- calc_milo_distances(milo_obj, d = 30, reduced.dim = "PCA")

# Count cells
milo_obj <- count_milo_cells(milo_obj, sample_col = "sample_id")

cat(sprintf("  Created %d neighborhoods\n", ncol(nhoods(milo_obj))))

# -----------------------------------------------------------------------------
# Step 3: Create design matrix with batch covariate
# -----------------------------------------------------------------------------
cat("\n[Step 3] Creating design matrix with batch covariate...\n")

design_df <- unique(data.frame(
  sample_id = colData(milo_obj)$sample_id,
  condition = colData(milo_obj)$condition,
  batch = colData(milo_obj)$batch,
  stringsAsFactors = FALSE
))
rownames(design_df) <- design_df$sample_id

cat("  Design matrix:\n")
print(design_df)

# -----------------------------------------------------------------------------
# Step 4: Test DA with batch correction
# -----------------------------------------------------------------------------
cat("\n[Step 4] Testing DA with batch correction...\n")

# Design formula including batch
da_results <- test_milo_da(
  milo_obj,
  design = ~ batch + condition,
  design.df = design_df,
  fdr.weighting = "k-distance",
  norm.method = "TMM"
)

# Summarize results
summary_stats <- summarize_milo_results(da_results, alpha = 0.1)

# -----------------------------------------------------------------------------
# Step 5: Annotate neighborhoods with cell types
# -----------------------------------------------------------------------------
cat("\n[Step 5] Annotating neighborhoods with cell types...\n")

da_results <- annotate_milo_neighborhoods(milo_obj, da_results,
                                          colData_col = "cell_type",
                                          nlargest = 1)

# View cell type composition of DA neighborhoods
cat("\n  Cell type composition of significant neighborhoods:\n")
sig_results <- da_results[da_results$SpatialFDR < 0.1, ]
if (nrow(sig_results) > 0) {
  print(table(sig_results$cell_type))
}

# -----------------------------------------------------------------------------
# Step 6: Group DA neighborhoods
# -----------------------------------------------------------------------------
cat("\n[Step 6] Grouping DA neighborhoods...\n")

da_results <- group_milo_neighborhoods(
  milo_obj,
  da.res = da_results,
  da.fdr = 0.1,
  overlap = 5,
  merge.discord = FALSE
)

# View group sizes
if ("NhoodGroup" %in% colnames(da_results)) {
  group_sizes <- table(da_results$NhoodGroup)
  cat(sprintf("  Created %d neighborhood groups\n", length(group_sizes)))
  cat("  Group sizes:\n")
  print(group_sizes)
}

# -----------------------------------------------------------------------------
# Step 7: Find marker genes for DA neighborhood groups
# -----------------------------------------------------------------------------
cat("\n[Step 7] Finding marker genes for DA groups...\n")

marker_results <- find_milo_markers(
  milo_obj,
  da.res = da_results,
  da.fdr = 0.1,
  assay = "logcounts",
  gene.offset = TRUE,
  return.groups = FALSE
)

cat(sprintf("  Found markers for %d genes\n", nrow(marker_results)))

# -----------------------------------------------------------------------------
# Step 8: Comprehensive visualization
# -----------------------------------------------------------------------------
cat("\n[Step 8] Creating comprehensive visualizations...\n")

# 8.1 DA beeswarm by cell type
p1 <- plot_milo_beeswarm(da_results, group.by = "cell_type", alpha = 0.1)
ggsave("advanced_beeswarm_celltype.pdf", p1, width = 8, height = 6)
cat("  Saved: advanced_beeswarm_celltype.pdf\n")

# 8.2 DA beeswarm by neighborhood group
if ("NhoodGroup" %in% colnames(da_results)) {
  p2 <- plot_milo_groups(milo_obj, da_results, alpha = 0.1)
  ggsave("advanced_groups.pdf", p2, width = 8, height = 6)
  cat("  Saved: advanced_groups.pdf\n")
}

# 8.3 Volcano plot
p3 <- plot_milo_volcano(da_results, alpha = 0.1, logfc.threshold = 1)
ggsave("advanced_volcano.pdf", p3, width = 6, height = 5)
cat("  Saved: advanced_volcano.pdf\n")

# 8.4 UMAP with DA coloring
p4 <- plot_milo_umap_da(milo_obj, da_results, dimred = "UMAP", alpha = 0.1)
ggsave("advanced_umap_da.pdf", p4, width = 7, height = 6)
cat("  Saved: advanced_umap_da.pdf\n")

# 8.5 Neighborhood counts
p5 <- plot_milo_counts(milo_obj, n.top = 50)
ggsave("advanced_nhood_counts.pdf", p5, width = 10, height = 5)
cat("  Saved: advanced_nhood_counts.pdf\n")

# 8.6 Size distribution
p6 <- plot_milo_size_distribution(milo_obj)
ggsave("advanced_size_dist.pdf", p6, width = 6, height = 4)
cat("  Saved: advanced_size_dist.pdf\n")

# 8.7 Sample counts per neighborhood
p7 <- plot_milo_sample_counts(milo_obj, n.top = 30)
ggsave("advanced_sample_counts.pdf", p7, width = 10, height = 5)
cat("  Saved: advanced_sample_counts.pdf\n")

# -----------------------------------------------------------------------------
# Step 9: Alternative analysis with different parameters
# -----------------------------------------------------------------------------
cat("\n[Step 9] Running alternative analysis with different k...\n")

# Test with larger k for denser neighborhoods
milo_obj_k50 <- build_milo_graph(milo_obj, k = 50, d = 30, reduced.dim = "PCA")
milo_obj_k50 <- make_milo_neighborhoods(milo_obj_k50, prop = 0.05, k = 50,
                                        d = 30, refined = TRUE, seed = 42)
milo_obj_k50 <- count_milo_cells(milo_obj_k50, sample_col = "sample_id")

da_results_k50 <- test_milo_da(
  milo_obj_k50,
  design = ~ batch + condition,
  design.df = design_df,
  fdr.weighting = "k-distance"
)

summary_k50 <- summarize_milo_results(da_results_k50, alpha = 0.1)

# Compare k values
cat("\n  Comparison of k values:\n")
cat(sprintf("    k=30: %d significant neighborhoods\n", summary_stats$n_significant))
cat(sprintf("    k=50: %d significant neighborhoods\n", summary_k50$n_significant))

# -----------------------------------------------------------------------------
# Step 10: Export results
# -----------------------------------------------------------------------------
cat("\n[Step 10] Exporting results...\n")

export_milo_results(da_results, "advanced_da_results.csv", significant_only = FALSE)
export_milo_results(da_results, "advanced_da_results_sig.csv", significant_only = TRUE)
write.csv(marker_results, "advanced_marker_genes.csv", row.names = FALSE)

# Save R objects
saveRDS(milo_obj, "advanced_milo_object.rds")
saveRDS(da_results, "advanced_da_results.rds")
saveRDS(results, "advanced_pipeline_results.rds")

cat("  Exported: CSV and RDS files\n")

# -----------------------------------------------------------------------------
# Step 11: Generate report
# -----------------------------------------------------------------------------
cat("\n[Step 11] Generating analysis report...\n")

# Create a comprehensive report
sink("advanced_milo_report.txt")

cat("=== miloR Advanced Analysis Report ===\n\n")
cat("Date:", format(Sys.time()), "\n\n")

cat("Dataset Summary:\n")
cat(sprintf("  Total cells: %d\n", ncol(sce)))
cat(sprintf("  Total genes: %d\n", nrow(sce)))
cat(sprintf("  Samples: %d\n", length(unique(sce$sample_id))))
cat(sprintf("  Conditions: %s\n", paste(unique(sce$condition), collapse = ", ")))
cat(sprintf("  Batches: %s\n", paste(unique(sce$batch), collapse = ", ")))
cat(sprintf("  Cell types: %s\n\n", paste(unique(sce$cell_type), collapse = ", ")))

cat("Analysis Parameters:\n")
cat(sprintf("  k (kNN): %d\n", rec_k))
cat(sprintf("  d (dimensions): 30\n"))
cat(sprintf("  prop (sampling): %.2f\n", rec_prop))
cat(sprintf("  Refined sampling: TRUE\n"))
cat(sprintf("  Spatial FDR: k-distance\n"))
cat(sprintf("  Normalization: TMM\n\n"))

cat("Neighborhood Summary:\n")
cat(sprintf("  Total neighborhoods: %d\n", ncol(nhoods(milo_obj))))
cat(sprintf("  Mean neighborhood size: %.1f cells\n",
            mean(colSums(nhoods(milo_obj) > 0))))

cat("\nDA Results (k=30):\n")
cat(sprintf("  Significant neighborhoods (FDR < 0.1): %d\n", summary_stats$n_significant))
cat(sprintf("  Up-regulated in Treatment: %d\n", summary_stats$n_upregulated))
cat(sprintf("  Down-regulated in Treatment: %d\n", summary_stats$n_downregulated))

if ("NhoodGroup" %in% colnames(da_results)) {
  cat(sprintf("  Neighborhood groups: %d\n", length(unique(na.omit(da_results$NhoodGroup)))))
}

cat("\nDA Results (k=50):\n")
cat(sprintf("  Significant neighborhoods (FDR < 0.1): %d\n", summary_k50$n_significant))

cat("\nTop 10 Significant Neighborhoods:\n")
top10 <- get_top_da_nhoods(da_results, n_top = 10)
print(top10[, c("logFC", "PValue", "SpatialFDR", "cell_type")])

sink()
cat("  Saved: advanced_milo_report.txt\n")

cat("\n", rep("=", 70), "\n", sep = "")
cat("Advanced example complete!\n")
cat(rep("=", 70), "\n", sep = "")
