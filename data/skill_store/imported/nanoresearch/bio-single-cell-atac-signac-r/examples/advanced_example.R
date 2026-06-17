# Advanced Signac Example
# =======================
# This example demonstrates advanced Signac workflows including:
# - Gene activity analysis
# - Peak calling with MACS2
# - Integration with scRNA-seq
# - Coverage tracks and visualization
# - Peak-gene links

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=== Advanced Signac Analysis Example ===\n\n")

# =============================================================================
# Part 1: Basic Setup and Analysis
# =============================================================================

cat("=== Part 1: Setup ===\n")

# Check dependencies
check_signac_dependencies()

# Check MACS2
has_macs2 <- check_macs2()
cat(sprintf("MACS2 available: %s\n\n", has_macs2))

# =============================================================================
# Part 2: Load Data and Basic QC
# =============================================================================

cat("=== Part 2: Load Data ===\n")

cat("In real analysis:\n")
cat("
seurat_obj <- create_signac_object(
  counts_file = 'filtered_peak_bc_matrix.h5',
  fragments_file = 'fragments.tsv.gz',
  metadata_file = 'singlecell.csv',
  genome = 'hg38'
)

# Compute QC
seurat_obj <- compute_qc_metrics(seurat_obj)
seurat_obj <- add_blacklist_ratio(seurat_obj)

# Filter
seurat_obj <- filter_cells_signac(
  seurat_obj,
  min_counts = 3000,
  max_counts = 20000,
  min_tss = 3,
  max_ns = 4
)
")
cat("\n")

# =============================================================================
# Part 3: Complete Workflow
# =============================================================================

cat("=== Part 3: Standard Workflow ===\n")

cat("
# Run complete workflow
seurat_obj <- run_signac_workflow(
  seurat_obj = seurat_obj,
  dims = 2:30,
  resolution = 0.8,
  run_umap = TRUE,
  run_clustering = TRUE
)

# View clusters
DimPlot(seurat_obj, reduction = 'umap', label = TRUE)
")
cat("\n")

# =============================================================================
# Part 4: Gene Activity Analysis
# =============================================================================

cat("=== Part 4: Gene Activity Analysis ===\n")

cat("
# Create gene activity matrix
seurat_obj <- create_gene_activity(
  seurat_obj,
  extend_upstream = 2000,
  extend_downstream = 0,
  biotypes = 'protein_coding'
)

# Get marker genes
markers <- create_marker_list(
  cell_types = c('CD4_T', 'CD8_T', 'B_cell', 'Monocyte', 'NK'),
  tissue = 'pbmc'
)

# Plot marker genes on UMAP
plot_gene_activity_umap(
  seurat_obj,
  genes = unlist(markers),
  ncol = 3
)
")
cat("\n")

# =============================================================================
# Part 5: Peak Calling (requires MACS2)
# =============================================================================

cat("=== Part 5: Peak Calling ===\n")

if (has_macs2) {
  cat("
# Call peaks per cluster
seurat_obj <- call_peaks_signac(
  seurat_obj,
  group_by = 'seurat_clusters',
  macs2_path = 'macs2',
  effective_genome_size = 2.7e9,
  pvalue = 0.01
)

# View peak counts per cluster
print(table(seurat_obj$seurat_clusters))
")
} else {
  cat("NOTE: MACS2 not available. Install with: pip install MACS2\n")
}
cat("\n")

# =============================================================================
# Part 6: scRNA-seq Integration
# =============================================================================

cat("=== Part 6: scRNA-seq Integration ===\n")

cat("
# Load scRNA-seq data
seRNA <- readRDS('scRNA_data.rds')

# Ensure gene activity exists
seurat_obj <- create_gene_activity(seurat_obj)

# Find transfer anchors
transfer_anchors <- FindTransferAnchors(
  reference = seRNA,
  query = seurat_obj,
  reference.assay = 'RNA',
  query.assay = 'RNA',
  reduction = 'cca'
)

# Transfer cell type labels
predicted_id <- TransferData(
  anchorset = transfer_anchors,
  refdata = seRNA$cell_type
)

# Add to metadata
seurat_obj$predicted.id <- predicted_id$predicted.id
seurat_obj$prediction.score.max <- predicted_id$prediction.score.max

# Visualize predictions
DimPlot(seurat_obj, reduction = 'umap', group.by = 'predicted.id', label = TRUE)
")
cat("\n")

# =============================================================================
# Part 7: Coverage Tracks
# =============================================================================

cat("=== Part 7: Coverage Tracks ===\n")

cat("
# Plot coverage for a gene
plot_coverage_track(
  seurat_obj,
  region = 'MS4A1',           # B cell marker
  group_by = 'seurat_clusters',
  extend = 5000
)

# Plot specific genomic region
plot_coverage_track(
  seurat_obj,
  region = 'chr14:106772282-106827066',  # IGH locus
  group_by = 'seurat_clusters'
)
")
cat("\n")

# =============================================================================
# Part 8: Advanced Visualization
# =============================================================================

cat("=== Part 8: Advanced Visualization ===\n")

cat("
# Create comprehensive QC report
create_qc_report(
  seurat_obj,
  output_dir = './signac_qc',
  prefix = 'sample',
  group_by = 'seurat_clusters'
)

# Plot marker genes
marker_plots <- plot_marker_genes(
  seurat_obj,
  markers = markers,
  ncol = 3
)

# Display plots
marker_plots$umap
marker_plots$violin
")
cat("\n")

# =============================================================================
# Part 9: Peak-Gene Links (if Cicero or similar run)
# =============================================================================

cat("=== Part 9: Peak-Gene Links ===\n")

cat("
# Note: Requires running LinkPeaks first
# seurat_obj <- LinkPeaks(
#   object = seurat_obj,
#   peak.assay = 'peaks',
#   expression.assay = 'RNA',
#   genes.use = unlist(markers)
# )

# Plot peak-gene links
# plot_peak_gene_links(
#   seurat_obj,
#   region = 'MS4A1',
#   group_by = 'seurat_clusters'
# )
")
cat("\n")

# =============================================================================
# Part 10: Export Results
# =============================================================================

cat("=== Part 10: Export ===\n")

cat("
# Export all results
export_signac_results(
  seurat_obj,
  output_dir = './signac_output',
  prefix = 'sample'
)

# Create comprehensive report
report <- create_signac_report(seurat_obj)
writeLines(report, 'signac_report.txt')
")
cat("\n")

# =============================================================================
# Summary
# =============================================================================

cat("=== Analysis Complete ===\n")
cat("
This example covered:
1. Basic Signac workflow (QC, filtering, LSI, clustering, UMAP)
2. Gene activity matrix creation
3. Peak calling with MACS2
4. scRNA-seq integration for label transfer
5. Coverage tracks and browser-style plots
6. Advanced visualization
7. Export and reporting

Key outputs:
- Seurat object with ATAC assays
- Gene activity scores (approximates expression)
- Peak calls (if MACS2 available)
- UMAP and LSI embeddings
- Cell type predictions
- Visualization plots
- Analysis report
")
