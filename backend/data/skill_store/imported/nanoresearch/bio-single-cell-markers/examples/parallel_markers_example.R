# Parallel Marker Finding Example
# Demonstrates FindAllMarkers with parallel execution

library(Seurat)
library(dplyr)

# Source parallel functions
source("../scripts/r/parallel_find_markers.R")

# ============================================================================
# Example 1: Basic Parallel Execution
# ============================================================================

# Load your clustered Seurat object
# seurat_obj <- readRDS('clustered.rds')

# Basic usage - auto-detects available cores
# all_markers <- FindAllMarkersParallel(seurat_obj)

# With custom parameters
# all_markers <- FindAllMarkersParallel(
#   seurat_obj,
#   only.pos = TRUE,
#   min.pct = 0.25,
#   logfc.threshold = 0.25,
#   test.use = 'wilcox'
# )

# ============================================================================
# Example 2: Specify Workers and Plan
# ============================================================================

# Linux/Mac: Use multicore for better performance
# all_markers <- FindAllMarkersParallel(
#   seurat_obj,
#   n_workers = 8,
#   future.plan = 'multicore'
# )

# Windows: Use multisession (default)
# all_markers <- FindAllMarkersParallel(
#   seurat_obj,
#   n_workers = 4,
#   future.plan = 'multisession'
# )

# ============================================================================
# Example 3: Parallel Markers for Specific Clusters
# ============================================================================

# Find markers for specific clusters in parallel
# markers_list <- FindMarkersParallel(
#   seurat_obj,
#   clusters = c(0, 1, 2, 3, 4, 5),
#   ident.2 = NULL,  # Compare to all other cells
#   n_workers = 6,
#   only.pos = TRUE,
#   min.pct = 0.25
# )

# Access results
# markers_cluster0 <- markers_list[['0']]
# markers_cluster1 <- markers_list[['1']]

# Combine results
# all_markers <- bind_rows(markers_list, .id = 'cluster')

# ============================================================================
# Example 4: Batch Processing Multiple Samples
# ============================================================================

# Process multiple samples in parallel
# seurat_list <- list(
#   sample1 = seurat1,
#   sample2 = seurat2,
#   sample3 = seurat3
# )
#
# all_markers_list <- FindAllMarkersBatch(
#   seurat_list,
#   n_workers = 3,
#   only.pos = TRUE
# )

# Access results
# markers_sample1 <- all_markers_list[['sample1']]

# ============================================================================
# Example 5: Benchmarking Performance
# ============================================================================

# Compare sequential vs parallel performance
# benchmark_results <- BenchmarkParallelMarkers(
#   seurat_obj,
#   n_workers = c(1, 2, 4, 8),
#   iterations = 1
# )
# print(benchmark_results)

# Expected output format:
#   workers mean_time sd_time min_time max_time   speedup efficiency
# 1       1     120.5    0.00    120.5    120.5  1.000000   1.000000
# 2       2      65.3    0.00     65.3     65.3  1.845329   0.922665
# 3       4      38.2    0.00     38.2     38.2  3.154450   0.788613
# 4       8      25.1    0.00     25.1     25.1  4.800797   0.600100

# ============================================================================
# Example 6: Get System Recommendations
# ============================================================================

# Get recommendations for your system
recommendations <- GetParallelRecommendations()
print(recommendations)

# Output includes:
# - Recommended plan (multicore vs multisession)
# - Optimal number of workers
# - Memory warnings

# ============================================================================
# Example 7: Complete Workflow with Top Markers
# ============================================================================

# Complete workflow example
find_and_process_markers <- function(seurat_obj, n_workers = NULL) {

  # Get recommendations if not specified
  if (is.null(n_workers)) {
    rec <- GetParallelRecommendations()
    n_workers <- rec$recommendations$recommended_workers
    message(sprintf("Using %d workers (recommended)", n_workers))
  }

  # Find markers in parallel
  all_markers <- FindAllMarkersParallel(
    seurat_obj,
    n_workers = n_workers,
    only.pos = TRUE,
    min.pct = 0.25,
    logfc.threshold = 0.25
  )

  # Process results
  top_markers <- all_markers %>%
    group_by(cluster) %>%
    slice_max(n = 10, order_by = avg_log2FC) %>%
    ungroup()

  # Summary statistics
  marker_stats <- all_markers %>%
    group_by(cluster) %>%
    summarise(
      n_markers = n(),
      avg_logfc = mean(avg_log2FC, na.rm = TRUE),
      median_pval = median(p_val_adj, na.rm = TRUE),
      .groups = 'drop'
    )

  list(
    all_markers = all_markers,
    top_markers = top_markers,
    stats = marker_stats
  )
}

# Usage
# results <- find_and_process_markers(seurat_obj, n_workers = 4)
# print(results$top_markers)
# print(results$stats)

# ============================================================================
# Performance Tips
# ============================================================================

# 1. Choose the right plan for your OS:
#    - Linux/Mac: multicore (shared memory, faster)
#    - Windows: multisession (separate R sessions)
#
# 2. Memory considerations:
#    - Each worker loads a copy of the data
#    - Monitor memory: n_workers * object_size < available_RAM
#    - Reduce workers if memory is limited
#
# 3. Optimal worker count:
#    - Usually: detectCores() - 1
#    - Diminishing returns after 8-16 workers
#    - More workers = more memory usage
#
# 4. When to use parallel:
#    - Dataset has >10 clusters
#    - Large cell count (>10,000 cells)
#    - Using slower tests (MAST, DESeq2)
#    - Batch processing multiple samples
#
# 5. When NOT to use parallel:
#    - Small datasets (<5 clusters)
#    - Memory-constrained systems
#    - Quick exploratory analysis

# ============================================================================
# Troubleshooting
# ============================================================================

# Error: "Failed to retrieve result of future"
# Solution: Reduce n_workers or check memory usage

# Error: "cannot allocate vector of size"
# Solution: Reduce n_workers or process in batches

# Slow performance with multicore
# Solution: Try multisession instead (some systems work better)

# Results differ between runs
# Solution: Set seed for reproducibility (handled automatically)
