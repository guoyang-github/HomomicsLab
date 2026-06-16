# Advanced chromVAR Example
# =========================
# This example demonstrates advanced chromVAR workflows including:
# - Loading real ATAC-seq data
# - Using JASPAR motifs
# - Integration with Seurat
# - Differential analysis
# - Comprehensive visualization

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# ============================================
# Part 1: Data Loading and Preparation
# ============================================

cat("=== Part 1: Data Loading ===\n")

# Example: Load from 10x Genomics output
# Uncomment and modify paths for your data:
#
# counts <- load_count_matrix("path/to/peak_counts.mtx")
# peaks <- load_peaks_from_bed("path/to/peaks.bed")
# metadata <- read.csv("path/to/metadata.csv")
#
# rse <- create_chromvar_object(counts, peaks, metadata)

# For demonstration, create simulated realistic data
set.seed(123)
n_peaks <- 50000
n_cells <- 1000

# Simulate counts with batch effect
counts <- Matrix::Matrix(0, nrow = n_peaks, ncol = n_cells, sparse = TRUE)
for (i in 1:n_cells) {
  # Variable accessibility per cell
  lambda <- runif(1, 1, 5)
  counts[, i] <- rpois(n_peaks, lambda)
}

# Create realistic peak coordinates
peaks <- GenomicRanges::GRanges(
  seqnames = sample(paste0("chr", 1:22), n_peaks, replace = TRUE,
                    prob = c(rep(0.08, 22))),  # Chr 1-22
  ranges = IRanges::IRanges(
    start = as.integer(runif(n_peaks, 1, 2.5e8)),
    width = 500
  )
)
peaks <- sort(GenomeInfoDb::sortSeqlevels(peaks))

# Set names
rownames(counts) <- paste0("peak_", 1:n_peaks)
colnames(counts) <- paste0("cell_", 1:n_cells)

# Create realistic metadata with cell types
cell_metadata <- data.frame(
  cell_id = colnames(counts),
  sample = sample(c("Sample_A", "Sample_B"), n_cells, replace = TRUE),
  cell_type = sample(c("CD4_T", "CD8_T", "B_cell", "Monocyte"), n_cells,
                     replace = TRUE, prob = c(0.3, 0.3, 0.2, 0.2)),
  stringsAsFactors = FALSE
)

# Create chromVAR object
rse <- create_chromvar_object(counts, peaks, cell_metadata)
cat(sprintf("Created object: %d peaks x %d cells\n", nrow(rse), ncol(rse)))

# ============================================
# Part 2: Quality Control
# ============================================

cat("\n=== Part 2: Quality Control ===\n")

# Validate input
validation <- validate_chromvar_input(rse)
print(validation$stats)

# Visualize before filtering
p_depth <- plot_sample_depth(rse)
ggsave("qc_depth_before.pdf", p_depth, width = 6, height = 4)

p_accessibility <- plot_peak_accessibility(rse)
ggsave("qc_accessibility.pdf", p_accessibility, width = 6, height = 4)

# Get parameter recommendations
params <- recommend_chromvar_params(ncol(rse), nrow(rse))

# Filter peaks
rse_filtered <- filter_peaks_chromvar(
  rse,
  min_fragments_per_peak = 5,
  non_overlapping = TRUE
)

cat(sprintf("Filtered: %d -> %d peaks\n", nrow(rse), nrow(rse_filtered)))

# ============================================
# Part 3: Complete chromVAR Workflow
# ============================================

cat("\n=== Part 3: chromVAR Analysis ===\n")

# NOTE: In real analysis, load actual BSgenome
# For this example, we simulate GC bias
cat("NOTE: Simulating GC bias for demonstration\n")
SummarizedExperiment::rowData(rse_filtered)$bias <- runif(nrow(rse_filtered), 0.3, 0.7)

# Create simulated motif annotations
# In real analysis:
#   motifs <- load_jaspar_motifs(species = 9606)
#   motif_ix <- match_motifs_chromvar(rse_filtered, motifs, genome)

cat("Creating simulated motif database...\n")
n_motifs <- 200
set.seed(456)

# Create sparse motif match matrix
motif_matches <- Matrix::sparseMatrix(
  i = sample(nrow(rse_filtered), n_motifs * 200, replace = TRUE),
  j = rep(1:n_motifs, each = 200),
  x = TRUE,
  dims = c(nrow(rse_filtered), n_motifs)
)

motif_ix <- SummarizedExperiment::SummarizedExperiment(
  assays = list(matches = motif_matches),
  colData = data.frame(
    name = paste0("MA", sprintf("%04d", 1:n_motifs), "_TF", 1:n_motifs),
    stringsAsFactors = FALSE
  )
)

# Get background peaks
bg_peaks <- get_background_peaks(rse_filtered, niterations = 50)

# Compute deviations
dev <- compute_deviations_chromvar(
  rse = rse_filtered,
  annotations = motif_ix,
  background_peaks = bg_peaks
)

# Compute variability
var <- compute_variability_chromvar(dev, bootstrap_error = TRUE)

cat(sprintf("Analyzed %d motifs\n", nrow(var)))

# ============================================
# Part 4: Results Extraction
# ============================================

cat("\n=== Part 4: Results ===\n")

# Summary
summary <- summarize_chromvar_results(list(
  rse = rse_filtered,
  deviations = dev,
  variability = var
))
print(summary)

# Top variable motifs
top_motifs <- get_top_variable_motifs(var, n = 10)
cat("\nTop 10 Variable Motifs:\n")
print(top_motifs[, c("name", "variability", "p_value_adj")])

# Get deviation scores for top motifs
z_scores <- get_motif_deviation_scores(dev, top_motifs$name)
cat(sprintf("\nZ-score matrix: %d motifs x %d cells\n", nrow(z_scores), ncol(z_scores)))

# ============================================
# Part 5: Visualization
# ============================================

cat("\n=== Part 5: Visualization ===\n")

# Variability plot
p_var <- plot_variability_chromvar(var, n_label = 5)
ggsave("advanced_variability.pdf", p_var, width = 10, height = 6)
cat("Saved: advanced_variability.pdf\n")

# Heatmap
pdf("advanced_heatmap.pdf", width = 10, height = 8)
plot_deviation_heatmap(dev, var, n_motifs = 20)
dev.off()
cat("Saved: advanced_heatmap.pdf\n")

# Group comparison
group_by <- SummarizedExperiment::colData(rse_filtered)$cell_type
p_group <- plot_motif_deviations(
  dev,
  motif_names = top_motifs$name[1:6],
  group_by = group_by,
  plot_type = "violin"
)
ggsave("advanced_group_comparison.pdf", p_group, width = 12, height = 8)
cat("Saved: advanced_group_comparison.pdf\n")

# Simulate dimensionality reduction coordinates
set.seed(789)
umap_coords <- data.frame(
  x = rnorm(ncol(rse_filtered)),
  y = rnorm(ncol(rse_filtered))
)

# Plot on dimensionality reduction
p_dimred <- plot_deviations_dimred(
  dev,
  dimred = umap_coords,
  motif_names = top_motifs$name[1:4]
)
ggsave("advanced_dimred.pdf", p_dimred, width = 10, height = 10)
cat("Saved: advanced_dimred.pdf\n")

# GC bias plot (simulated)
p_gc <- plot_gc_bias(rse_filtered)
ggsave("advanced_gc_bias.pdf", p_gc, width = 6, height = 4)
cat("Saved: advanced_gc_bias.pdf\n")

# ============================================
# Part 6: Differential Analysis
# ============================================

cat("\n=== Part 6: Differential Analysis ===\n")

# Compare cell types
# In real analysis with chromVAR installed:
# diff_dev <- chromVAR::differentialDeviations(dev, group_by)
# print(head(diff_dev[order(diff_dev$p_value), ]))

cat("NOTE: Differential analysis requires installed chromVAR package\n")
cat("      Run: chromVAR::differentialDeviations(dev, groups)\n")

# ============================================
# Part 7: Export and Report
# ============================================

cat("\n=== Part 7: Export ===\n")

# Export results
export_dir <- "./advanced_output"
dir.create(export_dir, showWarnings = FALSE)

# Export variability
write.table(
  var,
  file.path(export_dir, "variability.txt"),
  sep = "\t",
  row.names = FALSE,
  quote = FALSE
)

# Export z-scores
z_export <- as.data.frame(t(chromVAR::deviationScores(dev)))
write.table(
  z_export,
  file.path(export_dir, "deviation_scores.txt"),
  sep = "\t",
  row.names = TRUE,
  quote = FALSE
)

# Generate report
report <- create_chromvar_report(
  list(rse = rse_filtered, deviations = dev, variability = var)
)
writeLines(report, file.path(export_dir, "report.txt"))
cat(sprintf("Exported results to: %s\n", export_dir))

# ============================================
# Part 8: Integration Examples
# ============================================

cat("\n=== Part 8: Integration Examples ===\n")

# Example: Correlation with gene expression (simulated)
cat("Simulating gene expression correlation...\n")
gene_expression <- matrix(
  rnorm(nrow(z_scores) * ncol(z_scores)),
  nrow = nrow(z_scores),
  ncol = ncol(z_scores)
)
rownames(gene_expression) <- top_motifs$name
colnames(gene_expression) <- colnames(z_scores)

# Correlate
correlations <- data.frame(
  motif = top_motifs$name,
  correlation = sapply(1:nrow(z_scores), function(i) {
    cor(z_scores[i, ], gene_expression[i, ])
  })
)
print(head(correlations))

# Example: Seurat integration
cat("\nSeurat integration example:\n")
cat("
# Add to Seurat object:
seurat_obj[['chromvar']] <- CreateAssayObject(data = z_scores)

# Find variable motifs:
seurat_obj <- FindVariableFeatures(seurat_obj, assay = 'chromvar')

# Plot on UMAP:
FeaturePlot(seurat_obj, features = 'GATA1', assay = 'chromvar')
")

cat("\n=== Advanced Example Complete ===\n")
cat("Results saved to current directory\n")
