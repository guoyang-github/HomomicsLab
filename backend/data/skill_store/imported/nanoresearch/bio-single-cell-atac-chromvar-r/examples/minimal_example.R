# Minimal chromVAR Example
# ========================
# This example demonstrates the basic chromVAR workflow with simulated data.

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# Check dependencies
cat("Checking dependencies...\n")
if (!check_chromvar_dependencies()) {
  stop("Missing required packages. Run install_chromvar_deps()")
}

# Step 1: Create simulated data
cat("Creating simulated data...\n")
set.seed(42)

# Simulate peak counts (peaks x cells)
n_peaks <- 5000
n_cells <- 200
counts <- Matrix::Matrix(
  rpois(n_peaks * n_cells, lambda = 3),
  nrow = n_peaks,
  ncol = n_cells,
  sparse = TRUE
)

# Create peak coordinates
peaks <- GenomicRanges::GRanges(
  seqnames = sample(paste0("chr", 1:22), n_peaks, replace = TRUE),
  ranges = IRanges::IRanges(
    start = sample(1:1e8, n_peaks),
    width = 500
  )
)

# Sort peaks
peaks <- sort(GenomeInfoDb::sortSeqlevels(peaks))

# Set names
rownames(counts) <- paste0("peak_", 1:n_peaks)
colnames(counts) <- paste0("cell_", 1:n_cells)

# Create cell metadata
cell_metadata <- data.frame(
  cell_id = colnames(counts),
  sample = sample(c("Sample1", "Sample2"), n_cells, replace = TRUE),
  stringsAsFactors = FALSE
)

cat(sprintf("Created: %d peaks x %d cells\n", n_peaks, n_cells))

# Step 2: Create chromVAR object
cat("Creating chromVAR object...\n")
rse <- create_chromvar_object(
  counts = counts,
  peaks = peaks,
  cell_metadata = cell_metadata
)

# Validate input
validation <- validate_chromvar_input(rse)
cat("Validation:", ifelse(validation$valid, "PASSED", "FAILED"), "\n")
if (length(validation$warnings) > 0) {
  cat("Warnings:\n")
  for (w in validation$warnings) cat("  -", w, "\n")
}

# Step 3: Filter peaks
cat("Filtering peaks...\n")
rse_filtered <- filter_peaks_chromvar(
  rse,
  min_fragments_per_peak = 1,
  non_overlapping = TRUE
)

# Step 4: Add GC bias (using a mock genome for this example)
# NOTE: In real analysis, use actual BSgenome package
cat("NOTE: Skipping GC bias addition in this minimal example\n")
cat("      In real analysis, run: add_gc_bias(rse, genome = BSgenome.Hsapiens.UCSC.hg38)\n")

# Step 5: Get background peaks
cat("Computing background peaks...\n")
# For this minimal example, we'll create a simple bias vector
# In real analysis, this comes from add_gc_bias()
SummarizedExperiment::rowData(rse_filtered)$bias <- runif(nrow(rse_filtered))
bg_peaks <- get_background_peaks(rse_filtered, niterations = 20)

# Step 6: Create simple motif annotations
cat("Creating motif annotations...\n")
# In real analysis, use match_motifs_chromvar() with JASPAR motifs
# Here we create random motif matches for demonstration
n_motifs <- 50
motif_matches <- Matrix::sparseMatrix(
  i = sample(nrow(rse_filtered), n_motifs * 100, replace = TRUE),
  j = rep(1:n_motifs, each = 100),
  x = TRUE,
  dims = c(nrow(rse_filtered), n_motifs)
)
motif_ix <- SummarizedExperiment::SummarizedExperiment(
  assays = list(matches = motif_matches)
)
SummarizedExperiment::colData(motif_ix)$name <- paste0("Motif_", 1:n_motifs)

# Step 7: Compute deviations
cat("Computing deviations...\n")
dev <- compute_deviations_chromvar(
  rse = rse_filtered,
  annotations = motif_ix,
  background_peaks = bg_peaks,
  validate = FALSE  # Skip validation for simulated data
)

# Step 8: Compute variability
cat("Computing variability...\n")
var <- compute_variability_chromvar(dev, bootstrap_error = FALSE)

# Step 9: View results
cat("\n=== Results ===\n")
cat(sprintf("Peaks analyzed: %d\n", nrow(rse_filtered)))
cat(sprintf("Cells analyzed: %d\n", ncol(rse_filtered)))
cat(sprintf("Motifs tested: %d\n", nrow(dev)))

cat("\nTop 5 Variable Motifs:\n")
print(head(var[order(var$variability, decreasing = TRUE), ], 5))

# Step 10: Simple visualization
cat("\nCreating visualizations...\n")
p1 <- plot_variability_chromvar(var, n_label = 3, use_plotly = FALSE)
ggsave("minimal_variability.pdf", p1, width = 8, height = 5)
cat("Saved: minimal_variability.pdf\n")

cat("\n=== Minimal Example Complete ===\n")
cat("For a real analysis with JASPAR motifs and proper genome, see advanced_example.R\n")
