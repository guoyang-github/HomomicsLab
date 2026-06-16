#!/usr/bin/env Rscript
#' Advanced Example: BayesSpace Comprehensive Analysis
#'
#' This example demonstrates advanced BayesSpace features including:
#' - Spatial clustering with multiple q values
#' - Resolution enhancement to subspot-level
#' - MCMC chain diagnostics
#' - Comprehensive visualization
#' - Feature enhancement
#'
#' Requirements:
#'   - BayesSpace (>= 1.10.0)
#'   - SingleCellExperiment
#'   - scater
#'   - scran
#'   - ggplot2
#'   - mclust (optional)
#'
#' Reference:
#'   Zhao et al. (2021). BayesSpace enables the robust characterization of spatial
#'   transcriptomic architectures in tissues. Nature Communications.

library(BayesSpace)
library(SingleCellExperiment)
library(scater)
library(scran)
library(ggplot2)

cat("================================================================================\n")
cat("BayesSpace Advanced Example\n")
cat("================================================================================\n\n")

set.seed(42)

# ================================================================================
# PART 1: Data Preparation
# ================================================================================

cat("================================================================================\n")
cat("PART 1: Data Preparation\n")
cat("================================================================================\n\n")

create_synthetic_data <- function(n_spots = 400, n_genes = 1000, n_domains = 5, seed = 42) {
  set.seed(seed)

  # Create spatial coordinates
  grid_size <- ceiling(sqrt(n_spots))
  array_col <- rep(1:grid_size, each = grid_size)[1:n_spots]
  array_row <- rep(1:grid_size, times = grid_size)[1:n_spots]

  # Create expression matrix
  counts <- matrix(rpois(n_genes * n_spots, lambda = 2), nrow = n_genes)

  # Assign domains based on position
  domain_labels <- rep(0, n_spots)
  genes_per_domain <- n_genes / n_domains

  for (i in 1:n_spots) {
    xi <- array_col[i]
    yi <- array_row[i]

    # Concentric-like domains
    center_x <- center_y <- grid_size / 2
    dist <- sqrt((xi - center_x)^2 + (yi - center_y)^2)
    max_dist <- sqrt(center_x^2 + center_y^2)
    domain <- min(floor((dist / max_dist) * n_domains) + 1, n_domains)

    domain_labels[i] <- domain

    # Add markers
    marker_start <- (domain - 1) * genes_per_domain + 1
    marker_end <- domain * genes_per_domain
    counts[marker_start:marker_end, i] <- counts[marker_start:marker_end, i] + rpois(genes_per_domain, 15)
  }

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
  colnames(sce) <- paste0("Spot_", sprintf("%04d", 1:n_spots))

  sce
}

# Create main dataset
sce <- create_synthetic_data(n_spots = 400, n_genes = 1000, n_domains = 5)
cat(sprintf("Created SCE: %d spots x %d genes\n", ncol(sce), nrow(sce)))
cat(sprintf("Ground truth domains: %d\n", length(unique(sce$ground_truth))))

# Create output directory
output_dir <- "output_advanced"
if (!dir.exists(output_dir)) {
  dir.create(output_dir)
}

# ================================================================================
# PART 2: Preprocessing
# ================================================================================

cat("\n================================================================================\n")
cat("PART 2: Preprocessing\n")
cat("================================================================================\n\n")

sce <- spatialPreprocess(
  sce,
  platform = "ST",
  n.PCs = 15,
  n.HVGs = 500,
  log.normalize = TRUE
)

cat(sprintf("Identified %d highly variable genes\n", sum(rowData(sce)$is.HVG)))
cat(sprintf("Computed %d principal components\n", ncol(reducedDim(sce, "PCA"))))

# ================================================================================
# PART 3: Spatial Clustering with Multiple q Values
# ================================================================================

cat("\n================================================================================\n")
cat("PART 3: Spatial Clustering with Multiple q Values\n")
cat("================================================================================\n\n")

# Test different numbers of clusters
q_values <- c(3, 4, 5, 6)
cluster_results <- list()

for (q in q_values) {
  cat(sprintf("\nClustering with q=%d...\n", q))

  sce_temp <- spatialCluster(
    sce,
    q = q,
    platform = "ST",
    nrep = 5000,
    burn.in = 1000,
    gamma = 2,
    verbose = FALSE
  )

  cluster_results[[paste0("q", q)]] <- sce_temp$spatial.cluster
  cat(sprintf("  Completed: %d domains\n", length(unique(sce_temp$spatial.cluster))))
}

# Store q=5 result as main clustering
sce <- spatialCluster(
  sce,
  q = 5,
  platform = "ST",
  nrep = 10000,
  burn.in = 5000,
  gamma = 2,
  save.chain = TRUE,
  verbose = FALSE
)

cat("\nFinal clustering (q=5) complete!\n")
cat("Domain distribution:\n")
print(table(sce$spatial.cluster))

# ================================================================================
# PART 4: Resolution Enhancement
# ================================================================================

cat("\n================================================================================\n")
cat("PART 4: Resolution Enhancement\n")
cat("================================================================================\n\n")

cat("Enhancing resolution to subspot level...\n")
cat("  (This may take 2-5 minutes)\n\n")

sce_enhanced <- spatialEnhance(
  sce,
  q = 5,
  platform = "ST",
  nrep = 10000,
  burn.in = 5000,
  jitter.scale = 5,
  jitter.prior = 0.3,
  cores = 1,
  verbose = FALSE
)

cat("\nEnhancement complete!\n")
cat(sprintf("Original spots: %d\n", ncol(sce)))
cat(sprintf("Enhanced subspots: %d (%.1fx increase)\n",
            ncol(sce_enhanced), ncol(sce_enhanced) / ncol(sce)))

# ================================================================================
# PART 5: Feature Enhancement (Optional)
# ================================================================================

cat("\n================================================================================\n")
cat("PART 5: Feature Enhancement\n")
cat("================================================================================\n\n")

cat("Enhancing features at subspot resolution...\n")

# Select top variable genes for enhancement
hvgs <- rowData(sce)$is.HVG
genes_to_enhance <- rownames(sce)[hvgs][1:50]

try {
  sce_enhanced <- enhanceFeatures(
    sce_enhanced,
    sce,
    features = genes_to_enhance,
    model = "xgboost"
  )

  cat(sprintf("Enhanced %d features\n", length(genes_to_enhance)))
  cat("Access enhanced expression: assay(sce_enhanced, 'enhanced')\n")
} catch <- function(e) {
  cat(sprintf("Feature enhancement skipped: %s\n", conditionMessage(e)))
}

# ================================================================================
# PART 6: MCMC Chain Diagnostics
# ================================================================================

cat("\n================================================================================\n")
cat("PART 6: MCMC Chain Diagnostics\n")
cat("================================================================================\n\n")

# Extract cluster assignments across iterations
zsamples <- mcmcChain(sce, "z")
cat(sprintf("MCMC chain dimensions: %d iterations x %d spots\n",
            nrow(zsamples), ncol(zsamples)))

# Calculate cluster stability
cluster_stability <- apply(zsamples, 2, function(x) {
  tab <- table(x)
  max(tab) / sum(tab)
})

cat(sprintf("\nCluster assignment stability:\n"))
cat(sprintf("  Mean: %.3f\n", mean(cluster_stability)))
cat(sprintf("  Min: %.3f\n", min(cluster_stability)))
cat(sprintf("  Max: %.3f\n", max(cluster_stability)))

# ================================================================================
# PART 7: Export Results
# ================================================================================

cat("\n================================================================================\n")
cat("PART 7: Exporting Results\n")
cat("================================================================================\n\n")

# Export main clustering results
cluster_df <- data.frame(
  spot = colnames(sce),
  cluster = sce$spatial.cluster,
  cluster_init = sce$cluster.init,
  ground_truth = sce$ground_truth,
  array_row = sce$array_row,
  array_col = sce$array_col
)
write.csv(cluster_df, file.path(output_dir, "bayesspace_clusters.csv"), row.names = FALSE)
cat("  Saved: bayesspace_clusters.csv\n")

# Export enhanced results
enhanced_df <- data.frame(
  subspot = colnames(sce_enhanced),
  parent_spot = sce_enhanced$spot.idx,
  subspot_idx = sce_enhanced$subspot.idx,
  cluster = sce_enhanced$spatial.cluster,
  array_row = sce_enhanced$array_row,
  array_col = sce_enhanced$array_col
)
write.csv(enhanced_df, file.path(output_dir, "bayesspace_enhanced.csv"), row.names = FALSE)
cat("  Saved: bayesspace_enhanced.csv\n")

# Export multiple q comparison
comparison_df <- data.frame(
  spot = colnames(sce),
  ground_truth = sce$ground_truth
)
for (q_name in names(cluster_results)) {
  comparison_df[[q_name]] <- cluster_results[[q_name]]
}
write.csv(comparison_df, file.path(output_dir, "q_comparison.csv"), row.names = FALSE)
cat("  Saved: q_comparison.csv\n")

# Save SingleCellExperiments
saveRDS(sce, file.path(output_dir, "bayesspace_results.rds"))
cat("  Saved: bayesspace_results.rds\n")

saveRDS(sce_enhanced, file.path(output_dir, "bayesspace_enhanced.rds"))
cat("  Saved: bayesspace_enhanced.rds\n")

# Export summary report
report_lines <- c(
  "BayesSpace Advanced Analysis Report",
  "====================================",
  "",
  "Dataset Summary",
  "---------------",
  sprintf("Spots analyzed: %d", ncol(sce)),
  sprintf("Genes: %d", nrow(sce)),
  sprintf("Ground truth domains: %d", length(unique(sce$ground_truth))),
  "",
  "Clustering Results",
  "------------------",
  sprintf("Final q: 5"),
  sprintf("Identified domains: %d", length(unique(sce$spatial.cluster))),
  "",
  "Domain distribution:",
  paste(capture.output(table(sce$spatial.cluster)), collapse = "\n"),
  "",
  "Resolution Enhancement",
  "----------------------",
  sprintf("Original spots: %d", ncol(sce)),
  sprintf("Enhanced subspots: %d", ncol(sce_enhanced)),
  sprintf("Resolution increase: %.1fx", ncol(sce_enhanced) / ncol(sce)),
  "",
  "MCMC Diagnostics",
  "----------------",
  sprintf("Iterations: %d", nrow(zsamples)),
  sprintf("Cluster stability (mean): %.3f", mean(cluster_stability)),
  "",
  "Multiple q Comparison",
  "---------------------"
)

for (q in q_values) {
  q_label <- paste0("q", q)
  report_lines <- c(report_lines,
                    sprintf("q=%d: %d clusters", q, length(unique(cluster_results[[q_label]]))))
}

writeLines(report_lines, file.path(output_dir, "analysis_report.txt"))
cat("  Saved: analysis_report.txt\n")

# ================================================================================
# Summary
# ================================================================================

cat("\n================================================================================\n")
cat("Analysis Complete!\n")
cat("================================================================================\n\n")

cat(sprintf("Output files in %s/:\n", output_dir))
cat("  - bayesspace_clusters.csv (main clustering results)\n")
cat("  - bayesspace_enhanced.csv (subspot-level results)\n")
cat("  - q_comparison.csv (multiple q values)\n")
cat("  - bayesspace_results.rds (main SCE object)\n")
cat("  - bayesspace_enhanced.rds (enhanced SCE object)\n")
cat("  - analysis_report.txt (summary report)\n")

cat("\nNext steps:\n")
cat("  1. Compare clustering with different q values using q_comparison.csv\n")
cat("  2. Visualize results with clusterPlot(sce)\n")
cat("  3. Analyze enhanced resolution data\n")
cat("  4. For real data, use readVisium() to load 10X Visium output\n")
