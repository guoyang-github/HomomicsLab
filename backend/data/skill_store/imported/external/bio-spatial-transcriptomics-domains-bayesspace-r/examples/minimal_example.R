#!/usr/bin/env Rscript
#' Minimal Example: BayesSpace Spatial Domain Identification
#'
#' This example demonstrates basic BayesSpace usage for identifying spatial domains
#' using Bayesian hierarchical modeling with spatial priors.
#'
#' Requirements:
#'   - BayesSpace (>= 1.10.0)
#'   - SingleCellExperiment
#'   - scater
#'   - scran
#'
#' Reference:
#'   Zhao et al. (2021). BayesSpace enables the robust characterization of spatial
#'   transcriptomic architectures in tissues. Nature Communications.

library(BayesSpace)
library(SingleCellExperiment)
library(scater)
library(scran)

cat("================================================================================\n")
cat("BayesSpace Minimal Example\n")
cat("================================================================================\n\n")

# ================================================================================
# Step 1: Create Synthetic Data
# ================================================================================

cat("Step 1: Creating synthetic spatial data...\n")

set.seed(42)

# Create synthetic gene expression data
n_spots <- 200
n_genes <- 500

# Create spatial coordinates (grid pattern)
grid_size <- ceiling(sqrt(n_spots))
array_col <- rep(1:grid_size, each = grid_size)[1:n_spots]
array_row <- rep(1:grid_size, times = grid_size)[1:n_spots]

# Create count matrix with spatial patterns
counts <- matrix(rpois(n_genes * n_spots, lambda = 2), nrow = n_genes)

# Add spatial domain patterns
n_domains <- 4
domain_labels <- rep(0, n_spots)
genes_per_domain <- n_genes / n_domains

for (i in 1:n_spots) {
  x <- array_col[i]
  y <- array_row[i]

  # Assign domain based on position
  if (x <= grid_size/2 && y <= grid_size/2) {
    domain <- 1
    counts[1:genes_per_domain, i] <- counts[1:genes_per_domain, i] + rpois(genes_per_domain, 10)
  } else if (x > grid_size/2 && y <= grid_size/2) {
    domain <- 2
    counts[(genes_per_domain+1):(2*genes_per_domain), i] <- counts[(genes_per_domain+1):(2*genes_per_domain), i] + rpois(genes_per_domain, 10)
  } else if (x <= grid_size/2 && y > grid_size/2) {
    domain <- 3
    counts[(2*genes_per_domain+1):(3*genes_per_domain), i] <- counts[(2*genes_per_domain+1):(3*genes_per_domain), i] + rpois(genes_per_domain, 10)
  } else {
    domain <- 4
    counts[(3*genes_per_domain+1):(4*genes_per_domain), i] <- counts[(3*genes_per_domain+1):(4*genes_per_domain), i] + rpois(genes_per_domain, 10)
  }

  domain_labels[i] <- domain
}

# Create SingleCellExperiment
sce <- SingleCellExperiment(
  assays = list(counts = counts),
  colData = DataFrame(
    array_row = array_row,
    array_col = array_col,
    in_tissue = 1,
    ground_truth = factor(domain_labels)
  )
)

rownames(sce) <- paste0("Gene_", 1:n_genes)
colnames(sce) <- paste0("Spot_", 1:n_spots)

cat(sprintf("  Created SCE: %d spots x %d genes\n", n_spots, n_genes))
cat(sprintf("  Ground truth domains: %d\n", n_domains))

# ================================================================================
# Step 2: Preprocess Data
# ================================================================================

cat("\nStep 2: Preprocessing data...\n")

sce <- spatialPreprocess(
  sce,
  platform = "ST",
  n.PCs = 10,
  n.HVGs = 200,
  log.normalize = TRUE
)

cat(sprintf("  Identified %d highly variable genes\n", sum(rowData(sce)$is.HVG)))
cat(sprintf("  Computed %d principal components\n", ncol(reducedDim(sce, "PCA"))))

# ================================================================================
# Step 3: Spatial Clustering
# ================================================================================

cat("\nStep 3: Running BayesSpace clustering...\n")
cat("  (This may take 1-2 minutes)\n")

set.seed(149)
sce <- spatialCluster(
  sce,
  q = 4,                    # Number of clusters
  platform = "ST",
  nrep = 5000,              # MCMC iterations
  burn.in = 1000,           # Burn-in
  gamma = 2,                # Spatial smoothing
  verbose = FALSE
)

cat("\n  Clustering complete!\n")
cat(sprintf("  Identified %d spatial domains\n", length(unique(sce$spatial.cluster))))

# Compare with ground truth
cat("\n  Domain distribution:\n")
print(table(Predicted = sce$spatial.cluster, GroundTruth = sce$ground_truth))

# ================================================================================
# Step 4: Export Results
# ================================================================================

cat("\nStep 4: Exporting results...\n")

output_dir <- "output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# Export cluster assignments
cluster_df <- data.frame(
  spot = colnames(sce),
  cluster = sce$spatial.cluster,
  ground_truth = sce$ground_truth,
  array_row = sce$array_row,
  array_col = sce$array_col
)
write.csv(cluster_df, file.path(output_dir, "bayesspace_clusters.csv"), row.names = FALSE)
cat(sprintf("  Saved: bayesspace_clusters.csv\n"))

# Export summary
summary_lines <- c(
  "BayesSpace Analysis Summary",
  "===========================",
  "",
  sprintf("Spots analyzed: %d", n_spots),
  sprintf("Genes: %d", n_genes),
  sprintf("Domains identified: %d", length(unique(sce$spatial.cluster))),
  "",
  "Domain distribution:",
  paste(capture.output(table(sce$spatial.cluster)), collapse = "\n")
)
writeLines(summary_lines, file.path(output_dir, "summary.txt"))
cat(sprintf("  Saved: summary.txt\n"))

# Save SingleCellExperiment
saveRDS(sce, file.path(output_dir, "bayesspace_results.rds"))
cat(sprintf("  Saved: bayesspace_results.rds\n"))

cat("\n================================================================================\n")
cat("Analysis complete!\n")
cat(sprintf("Results saved to: %s/\n", output_dir))
cat("================================================================================\n")

cat("\nNext steps:\n")
cat("  1. Review cluster assignments in output/bayesspace_clusters.csv\n")
cat("  2. Load results: sce <- readRDS('output/bayesspace_results.rds')\n")
cat("  3. For real data, use readVisium() to load 10X Visium data\n")
