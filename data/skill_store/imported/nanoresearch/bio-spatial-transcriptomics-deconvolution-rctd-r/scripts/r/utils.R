#' RCTD Utility Functions
#'
#' Helper functions for RCTD analysis workflow.
#'
#' @author Yang Guo
#' @date 2026-04-07
#' @version 2.0.0

#' Create RCTD Test Data
#'
#' Generate synthetic spatial and reference data for testing RCTD.
#'
#' @param n_spots Number of spatial spots (default: 100)
#' @param n_genes Number of genes (default: 200)
#' @param n_cell_types Number of cell types (default: 4)
#' @param n_cells_per_type Number of cells per type in reference (default: 30)
#' @param seed Random seed (default: 42)
#'
#' @return List with spatial_counts, spatial_coords, reference_counts, cell_types
#' @export
create_rctd_test_data <- function(
    n_spots = 100,
    n_genes = 200,
    n_cell_types = 4,
    n_cells_per_type = 30,
    seed = 42
) {
  set.seed(seed)

  # Create gene names
  gene_names <- paste0("GENE_", 1:n_genes)

  # Create cell type names
  cell_type_names <- paste0("CellType", 1:n_cell_types)

  # Create reference data
  n_ref_cells <- n_cell_types * n_cells_per_type
  ref_counts <- matrix(
    rpois(n_genes * n_ref_cells, lambda = 10),
    nrow = n_genes,
    ncol = n_ref_cells
  )

  # Assign cell types
  cell_types <- factor(rep(cell_type_names, each = n_cells_per_type))

  # Set names
  rownames(ref_counts) <- gene_names
  colnames(ref_counts) <- paste0("cell_", 1:n_ref_cells)
  names(cell_types) <- colnames(ref_counts)

  # Create spatial coordinates (simulate a grid)
  grid_dim <- ceiling(sqrt(n_spots))
  spatial_coords <- data.frame(
    x = rep(1:grid_dim, length.out = n_spots),
    y = rep(1:grid_dim, each = grid_dim)[1:n_spots],
    row.names = paste0("spot_", 1:n_spots)
  )

  # Create spatial data by mixing reference cells
  spatial_counts <- matrix(0, nrow = n_genes, ncol = n_spots)
  rownames(spatial_counts) <- gene_names
  colnames(spatial_counts) <- rownames(spatial_coords)

  # Assign proportions for each spot
  for (i in 1:n_spots) {
    # Random proportions that sum to 1
    props <- runif(n_cell_types)
    props <- props / sum(props)

    # Sample cells according to proportions
    for (ct in 1:n_cell_types) {
      ct_cells <- which(cell_types == cell_type_names[ct])
      n_sample <- max(1, round(props[ct] * 8))
      selected <- sample(ct_cells, n_sample, replace = TRUE)
      spatial_counts[, i] <- spatial_counts[, i] + rowSums(ref_counts[, selected, drop = FALSE])
    }
  }

  list(
    spatial_counts = spatial_counts,
    spatial_coords = spatial_coords,
    reference_counts = ref_counts,
    cell_types = cell_types,
    cell_type_names = cell_type_names
  )
}

#' Recommend RCTD Parameters
#'
#' Get parameter recommendations based on data size.
#'
#' @param n_spots Number of spatial spots
#' @param n_cell_types Number of cell types
#' @param available_cores Number of available CPU cores (default: auto-detect)
#'
#' @return List with recommended parameters
#' @export
recommend_rctd_params <- function(
    n_spots,
    n_cell_types,
    available_cores = NULL
) {
  if (is.null(available_cores)) {
    available_cores <- parallel::detectCores()
  }

  # Recommend cores based on data size
  if (n_spots < 500) {
    recommended_cores <- min(2, available_cores)
  } else if (n_spots < 5000) {
    recommended_cores <- min(4, available_cores)
  } else {
    recommended_cores <- min(8, available_cores)
  }

  # Recommend mode based on cell types and spots
  if (n_cell_types <= 3) {
    recommended_mode <- "doublet"
  } else if (n_cell_types <= 8) {
    recommended_mode <- "doublet"
  } else {
    recommended_mode <- "full"
  }

  # Gene cutoff recommendation
  if (n_spots < 1000) {
    gene_cutoff <- 0.000125
  } else {
    gene_cutoff <- 0.0001
  }

  list(
    max_cores = recommended_cores,
    doublet_mode = recommended_mode,
    gene_cutoff = gene_cutoff,
    fc_cutoff = 0.5,
    UMI_min = 100,
    message = sprintf(
      "Recommended for %d spots, %d cell types: mode='%s', cores=%d",
      n_spots, n_cell_types, recommended_mode, recommended_cores
    )
  )
}

#' Filter RCTD Spots
#'
#' Filter spots based on UMI count or other criteria.
#'
#' @param rctd_results RCTD object
#' @param min_umi Minimum UMI threshold (default: 100)
#' @param max_umi Maximum UMI threshold (optional)
#' @param spots_to_keep Character vector: specific spots to keep (optional)
#'
#' @return Filtered RCTD object
#' @export
filter_rctd_spots <- function(
    rctd_results,
    min_umi = 100,
    max_umi = NULL,
    spots_to_keep = NULL
) {
  # Get current spots
  current_spots <- colnames(rctd_results@spatialRNA@counts)

  # Determine spots to keep
  if (!is.null(spots_to_keep)) {
    keep <- current_spots[current_spots %in% spots_to_keep]
  } else {
    nUMI <- rctd_results@spatialRNA@nUMI
    keep <- names(nUMI)[nUMI >= min_umi]

    if (!is.null(max_umi)) {
      keep <- keep[nUMI[keep] <= max_umi]
    }
  }

  # Filter the RCTD object
  rctd_results@spatialRNA <- restrict_puck(
    rctd_results@spatialRNA,
    keep
  )

  # Filter results if they exist
  if ('weights' %in% names(rctd_results@results)) {
    rctd_results@results$weights <- rctd_results@results$weights[keep, , drop = FALSE]
  }
  if ('weights_doublet' %in% names(rctd_results@results)) {
    rctd_results@results$weights_doublet <- rctd_results@results$weights_doublet[keep, , drop = FALSE]
  }
  if ('results_df' %in% names(rctd_results@results)) {
    rctd_results@results$results_df <- rctd_results@results$results_df[keep, , drop = FALSE]
  }

  message(sprintf("Filtered to %d spots", length(keep)))
  return(rctd_results)
}

#' Compare RCTD Results
#'
#' Compare deconvolution results across multiple samples or conditions.
#'
#' @param rctd_list Named list of RCTD objects
#' @param metric Metric to compare: 'mean', 'max', 'entropy' (default: 'mean')
#'
#' @return DataFrame with comparison results
#' @export
compare_rctd_results <- function(
    rctd_list,
    metric = 'mean'
) {
  results <- lapply(names(rctd_list), function(name) {
    rctd <- rctd_list[[name]]
    props <- extract_proportions_rctd(rctd)

    if (metric == 'mean') {
      vals <- colMeans(props)
    } else if (metric == 'max') {
      vals <- apply(props, 2, max)
    } else if (metric == 'entropy') {
      vals <- apply(props, 2, function(x) {
        p <- x[x > 0]
        -sum(p * log(p))
      })
    } else {
      stop(sprintf("Unknown metric: %s", metric))
    }

    data.frame(
      sample = name,
      cell_type = names(vals),
      value = vals,
      stringsAsFactors = FALSE
    )
  })

  do.call(rbind, results)
}

#' Merge Cell Types in RCTD Results
#'
#' Merge similar cell types after deconvolution.
#'
#' @param rctd_results RCTD object
#' @param merge_map Named list: names are new cell types, values are vectors of old types
#'
#' @return RCTD object with merged cell types
#' @export
merge_rctd_cell_types <- function(
    rctd_results,
    merge_map
) {
  # Extract current proportions
  props <- extract_proportions_rctd(rctd_results)

  # Create new proportion matrix
  new_props <- matrix(
    0,
    nrow = nrow(props),
    ncol = length(merge_map)
  )
  rownames(new_props) <- rownames(props)
  colnames(new_props) <- names(merge_map)

  # Merge proportions
  for (new_type in names(merge_map)) {
    old_types <- merge_map[[new_type]]
    new_props[, new_type] <- rowSums(props[, old_types, drop = FALSE])
  }

  # Update RCTD results
  rctd_results@results$weights <- as(new_props, "dgCMatrix")

  # Update cell type info
  rctd_results@cell_type_info$renorm[[2]] <- names(merge_map)
  rctd_results@cell_type_info$renorm[[3]] <- length(merge_map)

  message(sprintf("Merged %d cell types into %d types",
                  ncol(props), length(merge_map)))
  return(rctd_results)
}

#' Prepare Seurat Object for RCTD
#'
#' Convert Seurat object to RCTD-compatible format.
#'
#' @param seurat_obj Seurat object
#' @param cell_type_column Column containing cell type labels (for reference)
#' @param assay Assay to use (default: "RNA")
#' @param slot Slot to extract (default: "counts")
#'
#' @return List with counts and cell_types (if reference)
#' @export
prepare_rctd_seurat <- function(
    seurat_obj,
    cell_type_column = NULL,
    assay = "RNA",
    slot = "counts"
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract counts
  if (packageVersion("SeuratObject") >= "5.0.0") {
    counts <- Seurat::GetAssayData(seurat_obj, assay = assay, layer = slot)
  } else {
    counts <- Seurat::GetAssayData(seurat_obj, assay = assay, slot = slot)
  }

  result <- list(
    counts = counts
  )

  # Extract cell types if column provided
  if (!is.null(cell_type_column)) {
    if (cell_type_column %in% colnames(seurat_obj@meta.data)) {
      cell_types <- setNames(
        as.character(seurat_obj@meta.data[[cell_type_column]]),
        colnames(seurat_obj)
      )
      result$cell_types <- factor(cell_types)
    } else {
      warning(sprintf("Column '%s' not found in metadata", cell_type_column))
    }
  }

  return(result)
}

#' Calculate Proportion Entropy
#'
#' Calculate entropy of cell type proportions per spot (measure of mixing).
#'
#' @param rctd_results RCTD object
#' @param normalized Logical: return normalized entropy (0-1) (default: TRUE)
#'
#' @return Named vector of entropy values per spot
#' @export
calculate_proportion_entropy <- function(
    rctd_results,
    normalized = TRUE
) {
  props <- extract_proportions_rctd(rctd_results)

  entropy <- apply(props, 1, function(p) {
    p <- p[p > 0]
    if (length(p) == 1) return(0)
    -sum(p * log(p))
  })

  if (normalized) {
    n_types <- ncol(props)
    max_entropy <- log(n_types)
    entropy <- entropy / max_entropy
  }

  return(entropy)
}

#' Get High Purity Spots
#'
#' Identify spots dominated by a single cell type.
#'
#' @param rctd_results RCTD object
#' @param purity_threshold Minimum proportion for dominant type (default: 0.8)
#'
#' @return Character vector of spot IDs
#' @export
get_high_purity_spots <- function(
    rctd_results,
    purity_threshold = 0.8
) {
  props <- extract_proportions_rctd(rctd_results)
  max_props <- apply(props, 1, max)
  names(max_props)[max_props >= purity_threshold]
}

#' Get Mixed Spots
#'
#' Identify spots with multiple cell types.
#'
#' @param rctd_results RCTD object
#' @param max_dominant_prop Maximum proportion for dominant type (default: 0.6)
#' @param min_secondary_prop Minimum proportion for secondary type (default: 0.2)
#'
#' @return Character vector of spot IDs
#' @export
get_mixed_spots <- function(
    rctd_results,
    max_dominant_prop = 0.6,
    min_secondary_prop = 0.2
) {
  props <- extract_proportions_rctd(rctd_results)

  # Get sorted proportions
  sorted_props <- t(apply(props, 1, sort, decreasing = TRUE))

  spots <- rownames(props)[
    sorted_props[, 1] <= max_dominant_prop &
    sorted_props[, 2] >= min_secondary_prop
  ]

  return(spots)
}

#' Export Proportions to Seurat
#'
#' Add RCTD proportions to Seurat object as a new assay.
#'
#' @param seurat_obj Seurat object
#' @param rctd_results RCTD object
#' @param assay_name Name for new assay (default: "RCTD")
#'
#' @return Seurat object with added proportions
#' @export
export_rctd_to_seurat <- function(
    seurat_obj,
    rctd_results,
    assay_name = "RCTD"
) {
  if (!requireNamespace("Seurat", quietly = TRUE)) {
    stop("Seurat package required")
  }

  # Extract proportions
  props <- extract_proportions_rctd(rctd_results)

  # Ensure spot IDs match
  common_cells <- intersect(colnames(seurat_obj), rownames(props))

  if (length(common_cells) == 0) {
    stop("No matching cell IDs between Seurat object and RCTD results")
  }

  # Subset proportions
  props <- props[common_cells, , drop = FALSE]

  # Create assay
  rctd_assay <- Seurat::CreateAssayObject(
    data = t(as.matrix(props))
  )

  # Add to Seurat object
  seurat_obj[[assay_name]] <- rctd_assay

  message(sprintf("Added RCTD proportions as assay '%s' for %d cells", assay_name, length(common_cells)))
  return(seurat_obj)
}

#' Create RCTD Input from 10x Visium
#'
#' Load 10x Visium data and create RCTD input objects.
#'
#' @param data_dir Path to 10x Visium outs/ directory
#' @param reference_counts Reference counts matrix
#' @param cell_types Named vector of cell type labels
#'
#' @return List with spatial_rna and reference objects
#' @export
create_rctd_from_visium <- function(
    data_dir,
    reference_counts,
    cell_types
) {
  if (!requireNamespace("spacexr", quietly = TRUE)) {
    stop("spacexr package required")
  }

  library(spacexr)

  # Read Visium data
  spatial_rna <- read.VisiumSpatialRNA(data_dir)

  # Create reference
  nUMI_ref <- colSums(reference_counts)
  reference <- Reference(
    counts = reference_counts,
    cell_types = cell_types,
    nUMI = nUMI_ref
  )

  list(
    spatial_rna = spatial_rna,
    reference = reference
  )
}

# Helper function for NULL default
`%||%` <- function(x, y) if (is.null(x)) y else x
