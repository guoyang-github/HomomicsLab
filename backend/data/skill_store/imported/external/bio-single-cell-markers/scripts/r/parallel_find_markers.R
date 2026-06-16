# Parallel Marker Finding with Seurat FindAllMarkers
# Provides multi-core parallel execution for faster marker detection
#
# @author Yang Guo
# @date 2026-04-02
# @version 1.0.0

#' Find All Markers with Parallel Support
#'
#' Run FindAllMarkers with automatic parallelization using future framework.
#' Automatically detects available cores and distributes cluster comparisons.
#'
#' @param seurat_obj Seurat object
#' @param only.pos Only return positive markers (default: TRUE)
#' @param min.pct Minimum percentage of cells expressing gene (default: 0.25)
#' @param logfc.threshold Log fold change threshold (default: 0.25)
#' @param test.use Test to use: 'wilcox', 'MAST', 'DESeq2', etc. (default: 'wilcox')
#' @param n_workers Number of parallel workers. NULL = auto-detect (default: NULL)
#' @param future.plan Parallel strategy: 'multisession', 'multicore', 'sequential' (default: 'multisession')
#' @param verbose Print progress messages (default: TRUE)
#' @param ... Additional arguments passed to FindAllMarkers
#'
#' @return DataFrame with marker genes
#' @export
#'
#' @examples
#' \dontrun{
#' # Basic usage - auto-detect cores
#' markers <- FindAllMarkersParallel(seurat_obj)
#'
#' # Specify number of workers
#' markers <- FindAllMarkersParallel(seurat_obj, n_workers = 4)
#'
#' # Use multicore (faster on Linux/Mac)
#' markers <- FindAllMarkersParallel(seurat_obj, future.plan = 'multicore')
#'
#' # With custom parameters
#' markers <- FindAllMarkersParallel(
#'   seurat_obj,
#'   only.pos = TRUE,
#'   min.pct = 0.5,
#'   logfc.threshold = 0.5,
#'   test.use = 'MAST',
#'   n_workers = 8
#' )
#' }
FindAllMarkersParallel <- function(
    seurat_obj,
    only.pos = TRUE,
    min.pct = 0.25,
    logfc.threshold = 0.25,
    test.use = 'wilcox',
    n_workers = NULL,
    future.plan = 'multisession',
    verbose = TRUE,
    ...
) {
  if (!requireNamespace('Seurat', quietly = TRUE)) {
    stop('Seurat package required')
  }

  if (!inherits(seurat_obj, 'Seurat')) {
    stop('Input must be a Seurat object')
  }

  if (!requireNamespace('future', quietly = TRUE)) {
    warning('future package not installed. Running sequentially.\n',
            'Install with: install.packages("future")')
    return(FindAllMarkers(
      seurat_obj,
      only.pos = only.pos,
      min.pct = min.pct,
      logfc.threshold = logfc.threshold,
      test.use = test.use,
      ...
    ))
  }

  library(future)

  # Auto-detect cores if not specified
  if (is.null(n_workers)) {
    n_workers <- parallel::detectCores() - 1
    n_workers <- max(1, min(n_workers, length(unique(Idents(seurat_obj)))))
  }

  # Set up parallel plan
  if (verbose) {
    message(sprintf('Setting up %d %s workers...', n_workers, future.plan))
  }

  # Store original plan to restore later
  original_plan <- plan()

  tryCatch({
    # Set parallel plan
    plan(future.plan, workers = n_workers)

    # Enable progress reporting if future.apply is available
    if (requireNamespace('future.apply', quietly = TRUE) && verbose) {
      library(future.apply)
      options(future.apply.scheduling = 2.0)
    }

    if (verbose) {
      message('Running FindAllMarkers in parallel mode...')
      start_time <- Sys.time()
    }

    # Run parallel FindAllMarkers
    markers <- FindAllMarkers(
      seurat_obj,
      only.pos = only.pos,
      min.pct = min.pct,
      logfc.threshold = logfc.threshold,
      test.use = test.use,
      ...
    )

    if (verbose) {
      end_time <- Sys.time()
      elapsed <- difftime(end_time, start_time, units = 'secs')
      message(sprintf('Completed in %.1f seconds', as.numeric(elapsed)))
      message(sprintf('Found %d marker genes', nrow(markers)))
    }

    return(markers)

  }, finally = {
    # Always restore original plan
    plan(original_plan)
    if (verbose) {
      message('Parallel plan restored')
    }
  })
}


#' Find Markers for Multiple Clusters in Parallel
#'
#' Run FindMarkers for specific clusters in parallel.
#'
#' @param seurat_obj Seurat object
#' @param clusters Vector of cluster IDs to analyze (default: all clusters)
#' @param ident.2 Reference cluster(s) for comparison (default: NULL = all others)
#' @param n_workers Number of parallel workers (default: NULL = auto)
#' @param future.plan Parallel strategy (default: 'multisession')
#' @param verbose Print progress (default: TRUE)
#' @param ... Additional arguments for FindMarkers
#'
#' @return Named list of marker dataframes, one per cluster
#' @export
#'
#' @examples
#' \dontrun{
#' # Find markers for clusters 0-3 in parallel
#' markers_list <- FindMarkersParallel(
#'   seurat_obj,
#'   clusters = c(0, 1, 2, 3),
#'   only.pos = TRUE
#' )
#'
#' # Access results
#' markers_cluster0 <- markers_list[['0']]
#' }
FindMarkersParallel <- function(
    seurat_obj,
    clusters = NULL,
    ident.2 = NULL,
    n_workers = NULL,
    future.plan = 'multisession',
    verbose = TRUE,
    ...
) {
  if (!requireNamespace('future', quietly = TRUE)) {
    warning('future package not installed. Running sequentially.')
    # Use lapply instead of future_lapply
    apply_fn <- lapply
  } else {
    library(future)
    library(future.apply)

    # Set up parallel plan
    if (is.null(n_workers)) {
      n_workers <- parallel::detectCores() - 1
    }

    original_plan <- future::plan()
    on.exit(future::plan(original_plan))

    future::plan(future.plan, workers = n_workers)
    apply_fn <- future_lapply
  }

  # Determine clusters to analyze
  if (is.null(clusters)) {
    clusters <- levels(Idents(seurat_obj))
  }

  if (verbose) {
    backend <- ifelse(exists('future.plan', inherits = FALSE), future.plan, 'sequential')
    message(sprintf('Finding markers for %d clusters using %s...',
                    length(clusters), backend))
  }

  # Run marker finding
  results <- apply_fn(clusters, function(cl) {
    if (verbose) {
      message(sprintf('Processing cluster %s...', cl))
    }

    tryCatch({
      FindMarkers(
        seurat_obj,
        ident.1 = cl,
        ident.2 = ident.2,
        verbose = FALSE,
        ...
      )
    }, error = function(e) {
      warning(sprintf('Error processing cluster %s: %s', cl, e$message))
      return(NULL)
    })
  }, future.seed = TRUE)

  names(results) <- as.character(clusters)

  # Remove NULL results
  results <- results[!sapply(results, is.null)]

  if (verbose) {
    message(sprintf('Completed analysis for %d clusters', length(results)))
  }

  return(results)
}


#' Batch Find Markers Across Multiple Conditions
#'
#' Run marker detection for multiple conditions/samples in parallel.
#'
#' @param seurat_list Named list of Seurat objects
#' @param n_workers Number of workers (default: NULL = auto)
#' @param future.plan Parallel strategy (default: 'multisession')
#' @param verbose Print progress (default: TRUE)
#' @param ... Arguments passed to FindAllMarkers
#'
#' @return Named list of marker results
#' @export
#'
#' @examples
#' \dontrun{
#' # Analyze multiple samples in parallel
#' seurat_list <- list(
#'   sample1 = seurat1,
#'   sample2 = seurat2,
#'   sample3 = seurat3
#' )
#'
#' all_markers <- FindAllMarkersBatch(seurat_list, n_workers = 3)
#' }
FindAllMarkersBatch <- function(
    seurat_list,
    n_workers = NULL,
    future.plan = 'multisession',
    verbose = TRUE,
    ...
) {
  if (!requireNamespace('future', quietly = TRUE)) {
    warning('future package not installed. Running sequentially.')
    results <- lapply(names(seurat_list), function(name) {
      if (verbose) message(sprintf('Processing %s...', name))
      FindAllMarkers(seurat_list[[name]], verbose = FALSE, ...)
    })
    names(results) <- names(seurat_list)
    return(results)
  }

  library(future)
  library(future.apply)

  # Set up parallel plan
  if (is.null(n_workers)) {
    n_workers <- min(length(seurat_list), parallel::detectCores() - 1)
  }

  original_plan <- plan()
  on.exit(plan(original_plan))

  plan(future.plan, workers = n_workers)

  if (verbose) {
    message(sprintf('Processing %d samples with %d workers...',
                    length(seurat_list), n_workers))
  }

  # Process samples in parallel
  results <- future_lapply(names(seurat_list), function(name) {
    if (verbose) {
      message(sprintf('Finding markers for %s...', name))
    }

    tryCatch({
      markers <- FindAllMarkers(
        seurat_list[[name]],
        verbose = FALSE,
        ...
      )
      markers$sample <- name
      return(markers)
    }, error = function(e) {
      warning(sprintf('Error processing %s: %s', name, e$message))
      return(NULL)
    })
  }, future.seed = TRUE)

  names(results) <- names(seurat_list)
  results <- results[!sapply(results, is.null)]

  return(results)
}


#' Benchmark Parallel vs Sequential Performance
#'
#' Compare execution time of parallel and sequential marker finding.
#'
#' @param seurat_obj Seurat object
#' @param n_workers Number of workers to test (default: c(1, 2, 4))
#' @param iterations Number of iterations per configuration (default: 1)
#' @param ... Arguments for FindAllMarkers
#'
#' @return DataFrame with benchmark results
#' @export
#'
#' @examples
#' \dontrun{
#' # Benchmark different worker configurations
#' results <- BenchmarkParallelMarkers(seurat_obj, n_workers = c(1, 2, 4, 8))
#' print(results)
#' }
BenchmarkParallelMarkers <- function(
    seurat_obj,
    n_workers = c(1, 2, 4),
    iterations = 1,
    ...
) {
  if (!requireNamespace('future', quietly = TRUE)) {
    stop('future package required for benchmarking')
  }

  results <- data.frame()

  for (n in n_workers) {
    times <- numeric(iterations)

    for (i in 1:iterations) {
      gc()  # Clean up memory

      start <- Sys.time()

      tryCatch({
        FindAllMarkersParallel(
          seurat_obj,
          n_workers = n,
          verbose = FALSE,
          ...
        )
      }, error = function(e) {
        warning(sprintf('Error with %d workers: %s', n, e$message))
      })

      end <- Sys.time()
      times[i] <- as.numeric(difftime(end, start, units = 'secs'))
    }

    results <- rbind(results, data.frame(
      workers = n,
      mean_time = mean(times),
      sd_time = if (iterations > 1) sd(times) else 0,
      min_time = min(times),
      max_time = max(times)
    ))
  }

  # Calculate speedup
  if (nrow(results) > 0 && results$mean_time[1] > 0) {
    results$speedup <- results$mean_time[1] / results$mean_time
    results$efficiency <- results$speedup / results$workers
  }

  return(results)
}


#' Get Parallel Computing Recommendations
#'
#' Provides recommendations for optimal parallel settings based on system.
#'
#' @return List with recommendations
#' @export
#'
#' @examples
#' \dontrun{
#' recommendations <- GetParallelRecommendations()
#' print(recommendations)
#' }
GetParallelRecommendations <- function() {
  sys_info <- list(
    os = Sys.info()[['sysname']],
    n_cores = parallel::detectCores(),
    n_clusters = NA
  )

  # Recommendations
  if (sys_info$os == 'Linux' || sys_info$os == 'Darwin') {
    recommended_plan <- 'multicore'
    reason <- 'Shared memory, lower overhead on Unix systems'
  } else {
    recommended_plan <- 'multisession'
    reason <- 'Windows requires separate R sessions'
  }

  recommended_workers <- max(1, sys_info$n_cores - 1)

  list(
    system = sys_info,
    recommendations = list(
      plan = recommended_plan,
      reason = reason,
      max_workers = sys_info$n_cores,
      recommended_workers = recommended_workers,
      memory_warning = 'Each worker uses additional memory. Monitor RAM usage.'
    ),
    packages = c('future', 'future.apply', 'parallel')
  )
}
