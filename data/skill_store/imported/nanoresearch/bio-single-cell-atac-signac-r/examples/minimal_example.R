# Minimal Signac Example
# ======================
# This example demonstrates the basic Signac workflow with minimal setup.

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# Step 1: Setup
cat("=== Step 1: Setup ===\n")

# Check dependencies
if (!check_signac_dependencies()) {
  cat("WARNING: Some dependencies are missing\n")
  cat("Install with: install_signac_deps()\n")
}

cat("NOTE: This example shows the workflow structure\n")
cat("      In real analysis, you need actual ATAC-seq data files\n\n")

# Step 2: Load Data
cat("=== Step 2: Load Data ===\n")

cat("In real analysis, provide paths to your 10x output:\n")
cat("
seurat_obj <- create_signac_object(
  counts_file = 'filtered_peak_bc_matrix.h5',
  fragments_file = 'fragments.tsv.gz',
  metadata_file = 'singlecell.csv',  # Optional
  genome = 'hg38',
  min_cells = 10,
  min_features = 200
)
")
cat("\n")

# For demonstration, show expected structure
cat("Expected input files:\n")
cat("  - filtered_peak_bc_matrix.h5 (or MatrixMarket directory)\n")
cat("  - fragments.tsv.gz (with tabix index)\n")
cat("  - singlecell.csv (optional, cell metadata)\n")
cat("\nFragment file format (tab-delimited, gzipped):\n")
cat("  chr1\t1000\t1050\tACGTACGT-1\t1\n")
cat("  chr1\t2000\t2050\tACGTACGT-1\t1\n")
cat("\n")

# Step 3: QC Metrics
cat("=== Step 3: Compute QC Metrics ===\n")

cat("
# Compute nucleosome signal and TSS enrichment
seurat_obj <- compute_qc_metrics(
  seurat_obj,
  compute_nucleosome = TRUE,
  compute_tss = TRUE,
  tss_fast = TRUE
)

# Add blacklist ratio
seurat_obj <- add_blacklist_ratio(seurat_obj)

# View QC summary
print(get_qc_summary(seurat_obj))
")
cat("\n")

# Step 4: Filter Cells
cat("=== Step 4: Filter Cells ===\n")

cat("
# Filter cells based on QC
seurat_obj <- filter_cells_signac(
  seurat_obj,
  min_counts = 1000,        # Minimum fragments
  max_counts = 20000,       # Maximum fragments (remove doublets)
  min_tss = 2,              # Minimum TSS enrichment
  max_ns = 4,               # Maximum nucleosome signal
  min_rip = 15,             # Minimum % reads in peaks
  max_bl = 0.05             # Maximum blacklist ratio
)
")
cat("\n")

# Step 5: Normalization
cat("=== Step 5: TF-IDF Normalization ===\n")

cat("
# Run TF-IDF normalization
seurat_obj <- run_tfidf(seurat_obj, method = 1)

# Find top features
seurat_obj <- find_top_features(seurat_obj, min_cutoff = 'q0')
")
cat("\n")

# Step 6: Dimensionality Reduction
cat("=== Step 6: Dimensionality Reduction ===\n")

cat("
# Run LSI (Latent Semantic Indexing)
seurat_obj <- run_lsi(seurat_obj, dims = 50)
")
cat("\n")

# Step 7: Clustering
cat("=== Step 7: Clustering and UMAP ===\n")

cat("
# Find neighbors
seurat_obj <- FindNeighbors(
  object = seurat_obj,
  reduction = 'lsi',
  dims = 2:30              # Skip first LSI component
)

# Find clusters
seurat_obj <- FindClusters(
  object = seurat_obj,
  resolution = 0.8
)

# Run UMAP
seurat_obj <- RunUMAP(
  object = seurat_obj,
  reduction = 'lsi',
  dims = 2:30
)
")
cat("\n")

# Step 8: Visualization
cat("=== Step 8: Visualization ===\n")

cat("
# Plot clusters
DimPlot(seurat_obj, reduction = 'umap', label = TRUE)

# Plot QC metrics
plot_qc_metrics(seurat_obj)

# Plot TSS profile
plot_tss_profile(seurat_obj)
")
cat("\n")

# Step 9: Export
cat("=== Step 9: Export Results ===\n")

cat("
# Export results
export_signac_results(
  seurat_obj,
  output_dir = './signac_output',
  prefix = 'sample'
)

# Generate report
report <- create_signac_report(seurat_obj)
cat(report)
")
cat("\n")

# Complete workflow shortcut
cat("=== Complete Workflow Shortcut ===\n")
cat("Alternatively, run everything at once:\n")
cat("
seurat_obj <- run_signac_workflow(
  seurat_obj = seurat_obj,
  dims = 2:30,
  resolution = 0.8,
  run_umap = TRUE,
  run_clustering = TRUE
)
")
cat("\n")

cat("=== Notes ===\n")
cat("1. This example shows the workflow structure\n")
cat("2. Run in an R session with Signac installed\n")
cat("3. Requires actual ATAC-seq data files\n")
cat("4. See advanced_example.R for gene activity and peak calling\n")
cat("\nFor more details, see:\n")
cat("  - SKILL.md for complete documentation\n")
cat("  - usage-guide.md for detailed workflows\n")
