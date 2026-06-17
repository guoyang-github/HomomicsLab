# Minimal ArchR Example
# =====================
# This example demonstrates the basic ArchR workflow with minimal setup.

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# Step 1: Setup ArchR environment
cat("=== Step 1: Setup ===\n")

# Check dependencies
if (!check_archr_dependencies()) {
  cat("WARNING: Some dependencies are missing\n")
  cat("Install with: install_archr_deps()\n")
}

# Setup ArchR (in real analysis, use actual genome)
cat("NOTE: This example shows the workflow structure\n")
cat("      In real analysis, run:\n")
cat("      setup_archr(threads = 16, genome = 'hg38')\n")
cat("\n")

# Step 2: Create sample fragment files list
cat("=== Step 2: Prepare Input Files ===\n")

# In real analysis, these would be actual fragment files
# Format: tab-delimited, gzipped, with columns:
#   chr, start, end, cell_barcode, count
example_files <- c(
  "sample1_fragments.tsv.gz",
  "sample2_fragments.tsv.gz"
)

cat("Example fragment files:\n")
for (f in example_files) {
  cat(sprintf("  - %s\n", f))
}

cat("\nFragment file format (5 columns, tab-delimited, gzipped):\n")
cat("  chr1\t1000\t1050\tACGTACGT-1\t1\n")
cat("  chr1\t2000\t2050\tACGTACGT-1\t1\n")
cat("\n")

# Step 3: Validate fragment files
cat("=== Step 3: Validate Files ===\n")
cat("In real analysis:\n")
cat("  validation <- validate_fragment_files(example_files)\n")
cat("  print(validation)\n")
cat("\n")

# Step 4: Create Arrow files
cat("=== Step 4: Create Arrow Files ===\n")
cat("In real analysis:\n")
cat("
arrow_files <- create_arrow_files(
  input_files = c('sample1_fragments.tsv.gz', 'sample2_fragments.tsv.gz'),
  sample_names = c('Sample1', 'Sample2'),
  filter_tss = 4,        # TSS enrichment cutoff
  filter_frags = 1000,   # Minimum fragments per cell
  add_tile_mat = TRUE,   # Add genome tile matrix
  add_gene_score_mat = TRUE  # Add gene activity scores
)
")
cat("\n")

# Step 5: Create ArchR Project
cat("=== Step 5: Create ArchR Project ===\n")
cat("In real analysis:\n")
cat("
proj <- create_archr_project(
  arrow_files = arrow_files,
  output_directory = 'Save-ArchR',
  copy_arrows = TRUE
)
")
cat("\n")

# Step 6: Add Doublet Scores
cat("=== Step 6: Doublet Detection ===\n")
cat("In real analysis:\n")
cat("
# Add doublet scores
proj <- add_doublet_scores(
  proj,
  k = 10,           # Nearest neighbors
  n_trials = 5      # Simulation trials
)

# Filter doublets
proj <- filter_doublets(proj)
")
cat("\n")

# Step 7: Dimensionality Reduction
cat("=== Step 7: Dimensionality Reduction ===\n")
cat("In real analysis:\n")
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
")
cat("\n")

# Step 8: Clustering
cat("=== Step 8: Clustering ===\n")
cat("In real analysis:\n")
cat("
# Add clusters
proj <- add_clusters(
  proj,
  reduced_dims = 'IterativeLSI',
  name = 'Clusters',
  resolution = 0.8,
  method = 'Seurat'
)

# View clusters
table(proj$Clusters)
")
cat("\n")

# Step 9: UMAP
cat("=== Step 9: UMAP ===\n")
cat("In real analysis:\n")
cat("
# Add UMAP
proj <- add_umap(
  proj,
  reduced_dims = 'IterativeLSI',
  n_neighbors = 40,
  min_dist = 0.4
)
")
cat("\n")

# Step 10: Visualization
cat("=== Step 10: Visualization ===\n")
cat("In real analysis:\n")
cat("
# Plot clusters
plot_embedding(
  proj,
  embedding = 'UMAP',
  color_by = 'cellColData',
  name = 'Clusters'
)

# Plot by sample
plot_embedding(
  proj,
  color_by = 'cellColData',
  name = 'Sample'
)
")
cat("\n")

# Step 11: Save Project
cat("=== Step 11: Save Project ===\n")
cat("In real analysis:\n")
cat("
# Save project
proj <- save_archr_project(proj)

# Export metadata
export_cell_metadata(proj, 'cell_metadata.tsv')
")
cat("\n")

# Complete workflow shortcut
cat("=== Complete Workflow Shortcut ===\n")
cat("Alternatively, run everything at once:\n")
cat("
proj <- run_archr_workflow(
  input_files = c('sample1_fragments.tsv.gz', 'sample2_fragments.tsv.gz'),
  sample_names = c('Sample1', 'Sample2'),
  output_directory = 'ArchR-Project',
  genome = 'hg38',
  threads = 16,
  filter_tss = 4,
  filter_frags = 1000,
  run_umap = TRUE,
  run_doublet_filter = TRUE
)
")
cat("\n")

cat("=== Notes ===\n")
cat("1. This example shows the workflow structure\n")
cat("2. Run in an R session with ArchR installed\n")
cat("3. Requires actual fragment files as input\n")
cat("4. See advanced_example.R for peak calling and motif analysis\n")
cat("\nFor more details, see:\n")
cat("  - SKILL.md for complete documentation\n")
cat("  - usage-guide.md for detailed workflows\n")
