# Advanced ArchR Example
# ======================
# This example demonstrates advanced ArchR workflows including:
# - Peak calling with MACS2
# - Motif enrichment analysis
# - Integration with scRNA-seq
# - Trajectory analysis
# - Comprehensive visualization

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

cat("=== Advanced ArchR Analysis Example ===\n\n")

# =============================================================================
# Part 1: Setup and Basic Analysis
# =============================================================================

cat("=== Part 1: Setup ===\n")

# In real analysis:
# setup_archr(threads = 16, genome = "hg38")
cat("Setup: configure threads and genome\n")
cat("  setup_archr(threads = 16, genome = 'hg38')\n\n")

# Check MACS2 for peak calling
has_macs2 <- check_macs2()
cat(sprintf("MACS2 available: %s\n\n", has_macs2))

# =============================================================================
# Part 2: Create Arrow Files and Project
# =============================================================================

cat("=== Part 2: Create Project ===\n")

cat("In real analysis:\n")
cat("
input_files <- c('sample1_fragments.tsv.gz', 'sample2_fragments.tsv.gz')
sample_names <- c('Sample1', 'Sample2')

# Create Arrow files
arrow_files <- create_arrow_files(
  input_files = input_files,
  sample_names = sample_names,
  filter_tss = 4,
  filter_frags = 1000,
  add_tile_mat = TRUE,
  add_gene_score_mat = TRUE
)

# Create project
proj <- create_archr_project(
  arrow_files = arrow_files,
  output_directory = 'Save-ArchR',
  copy_arrows = TRUE
)
")
cat("\n")

# =============================================================================
# Part 3: Doublet Detection and Filtering
# =============================================================================

cat("=== Part 3: Doublet Detection ===\n")

cat("
# Add doublet scores
proj <- add_doublet_scores(
  proj,
  use_matrix = 'TileMatrix',
  k = 10,
  n_trials = 5
)

# Plot doublet scores (optional QC)
# plot_embedding(proj, color_by = 'cellColData', name = 'DoubletScore')

# Filter doublets
proj <- filter_doublets(proj)

# Check remaining cells
cat('Cells after filtering:', length(getCellNames(proj)), '\n')
")
cat("\n")

# =============================================================================
# Part 4: Dimensionality Reduction and Clustering
# =============================================================================

cat("=== Part 4: Dimensionality Reduction ===\n")

cat("
# Add iterative LSI
proj <- add_iterative_lsi(
  proj,
  name = 'IterativeLSI',
  iterations = 2,
  cluster_params = list(resolution = 2, sampleCells = 10000),
  var_features = 25000,
  dims_to_use = 1:30
)

# Add clusters
proj <- add_clusters(
  proj,
  reduced_dims = 'IterativeLSI',
  name = 'Clusters',
  resolution = 0.8,
  method = 'Seurat'
)

# Add UMAP
proj <- add_umap(
  proj,
  reduced_dims = 'IterativeLSI',
  n_neighbors = 40,
  min_dist = 0.4
)

# Visualize
plot_embedding(proj, color_by = 'cellColData', name = 'Clusters')
plot_embedding(proj, color_by = 'cellColData', name = 'Sample')
")
cat("\n")

# =============================================================================
# Part 5: Gene Score Visualization
# =============================================================================

cat("=== Part 5: Gene Score Visualization ===\n")

cat("
# Create marker gene list
markers <- create_marker_list(
  cell_types = c('CD4_T', 'CD8_T', 'B_cell', 'Monocyte', 'NK'),
  tissue = 'pbmc'
)

# Add imputation weights for smooth visualization
proj <- ArchR::addImputeWeights(proj)

# Plot gene scores
gene_plots <- plot_gene_scores(
  proj,
  genes = unlist(markers),
  embedding = 'UMAP',
  impute = TRUE
)

# Display plots
cowplot::plot_grid(plotlist = gene_plots[1:6], ncol = 3)
")
cat("\n")

# =============================================================================
# Part 6: Peak Calling (requires MACS2)
# =============================================================================

cat("=== Part 6: Peak Calling ===\n")

if (has_macs2) {
  cat("
# Add reproducible peak set
proj <- add_reproducible_peak_set(
  proj,
  group_by = 'Clusters',
  peak_method = 'Macs2',
  reproducibility = '2',
  peaks_per_cell = 500,
  max_peaks = 250000,
  path_to_macs2 = 'macs2'
)

# Add peak matrix
proj <- add_peak_matrix(proj)

# View peaks
peaks <- ArchR::getPeakSet(proj)
cat('Number of peaks:', length(peaks), '\n')
")
} else {
  cat("NOTE: MACS2 not available. Install with: pip install MACS2\n")
  cat("Peak calling skipped in this example.\n")
}
cat("\n")

# =============================================================================
# Part 7: Motif Enrichment and Deviations
# =============================================================================

cat("=== Part 7: Motif Analysis ===\n")

cat("
# Add motif annotations
proj <- add_motif_annotations(
  proj,
  motif_set = 'cisbp',     # Options: 'cisbp', 'encode', 'homer', 'jasparkellis'
  anno_name = 'Motif'
)

# Add deviations matrix (chromVAR)
proj <- add_deviations_matrix(
  proj,
  peak_annotation = 'Motif',
  out = 'z'                # Output z-scores
)

# Visualize TF deviations
plot_embedding(
  proj,
  color_by = 'MotifMatrix',
  name = 'GATA1',
  embedding = 'UMAP'
)
")
cat("\n")

# =============================================================================
# Part 8: scRNA-seq Integration
# =============================================================================

cat("=== Part 8: scRNA-seq Integration ===\n")

cat("
# Load scRNA-seq data (Seurat object)
seRNA <- readRDS('scRNA_data.rds')

# Add gene integration matrix
proj <- ArchR::addGeneIntegrationMatrix(
  ArchRProj = proj,
  seRNA = seRNA,
  useMatrix = 'GeneScoreMatrix',
  matrixName = 'GeneIntegrationMatrix',
  reducedDims = 'IterativeLSI',
  groupATAC = 'Clusters',
  groupRNA = 'seurat_clusters'
)

# Transfer labels
proj$predictedCellType <- proj$predictedGroup_Un

# Plot predictions
plot_embedding(
  proj,
  color_by = 'cellColData',
  name = 'predictedCellType'
)
")
cat("\n")

# =============================================================================
# Part 9: Marker Features
# =============================================================================

cat("=== Part 9: Marker Features ===\n")

cat("
# Get marker features
markers <- ArchR::getMarkerFeatures(
  ArchRProj = proj,
  groupBy = 'Clusters',
  useMatrix = 'GeneScoreMatrix',
  bias = c('TSSEnrichment', 'log10(nFrags)'),
  testMethod = 'wilcoxon'
)

# Get marker genes
marker_list <- ArchR::getMarkers(
  markers,
  cutOff = 'FDR <= 0.01 & Log2FC >= 0.5',
  returnGR = TRUE
)

# View top markers per cluster
for (cluster in names(marker_list)) {
  cat('Cluster', cluster, 'markers:', head(marker_list[[cluster]]$name, 5), '\n')
}
")
cat("\n")

# =============================================================================
# Part 10: Trajectory Analysis
# =============================================================================

cat("=== Part 10: Trajectory Analysis ===\n")

cat("
# Define trajectory (example: myeloid differentiation)
proj <- ArchR::addTrajectory(
  ArchRProj = proj,
  trajectory = 'Myeloid',
  groupBy = 'Clusters',
  reducedDims = 'IterativeLSI',
  trajectoryParams = list(
    groupPerTrajectory = c('C1', 'C2', 'C3'),
    clustersToExclude = NULL
  )
)

# Plot trajectory
ArchR::plotTrajectory(proj, trajectory = 'Myeloid')

# Plot genes along trajectory
ArchR::plotTrajectory(
  proj,
  trajectory = 'Myeloid',
  colorBy = 'GeneScoreMatrix',
  name = c('CD34', 'MPO', 'CD14'),
  continuousSet = 'blueYellow'
)
")
cat("\n")

# =============================================================================
# Part 11: Footprinting (requires peaks)
# =============================================================================

cat("=== Part 11: Footprinting ===\n")

if (has_macs2) {
  cat("
# Add footprints for TF of interest
proj <- ArchR::addFootprints(
  ArchRProj = proj,
  motifName = c('GATA1', 'CEBPA'),
  genome = 'hg38'
)

# Plot footprints
ArchR::plotFootprints(
  proj,
  motifName = c('GATA1', 'CEBPA'),
  plotName = 'Footprints',
  quantileCut = c(0.05, 0.95)
)
")
} else {
  cat("NOTE: Footprinting requires peaks (MACS2).\n")
}
cat("\n")

# =============================================================================
# Part 12: Browser Tracks
# =============================================================================

cat("=== Part 12: Browser Tracks ===\n")

cat("
# Plot browser track for a gene
plot_browser_track(
  proj,
  gene_symbol = 'GATA1',
  group_by = 'Clusters',
  upstream = 50000,
  downstream = 50000
)

# Plot specific region
plot_browser_track(
  proj,
  region = 'chrX:48644962-48652758',
  group_by = 'Clusters'
)
")
cat("\n")

# =============================================================================
# Part 13: Comprehensive Visualization
# =============================================================================

cat("=== Part 13: Comprehensive Visualization ===\n")

cat("
# Create all QC plots
create_qc_plots(
  proj,
  output_dir = './archr_qc',
  prefix = 'sample'
)

# Create comprehensive plots
create_archr_plots(
  proj,
  marker_genes = markers,
  output_dir = './archr_plots',
  prefix = 'sample'
)
")
cat("\n")

# =============================================================================
# Part 14: Export and Save
# =============================================================================

cat("=== Part 14: Export and Save ===\n")

cat("
# Save project
proj <- save_archr_project(proj)

# Export metadata
export_cell_metadata(proj, 'cell_metadata.tsv')

# Convert to Seurat for further analysis
seurat_obj <- convert_to_seurat(
  proj,
  assay_name = 'ATAC',
  use_matrix = 'GeneScoreMatrix'
)

# Create report
report <- create_archr_report(proj)
writeLines(report, 'archr_report.txt')
")
cat("\n")

# =============================================================================
# Summary
# =============================================================================

cat("=== Analysis Complete ===\n")
cat("
This example covered:
1. Basic ArchR workflow (doublets, LSI, clustering, UMAP)
2. Peak calling with MACS2
3. Motif enrichment and chromVAR deviations
4. scRNA-seq integration
5. Marker feature identification
6. Trajectory analysis
7. Footprinting
8. Browser tracks
9. Comprehensive visualization
10. Export and reporting

Key outputs:
- Arrow files (raw data)
- ArchR project (analysis results)
- Peak set (BED format)
- Cell metadata (TSV)
- Visualization plots (PDF)
- Analysis report (TXT)
")
