# Spatial Ro/e (Ratio of Observed to Expected) Analysis
# For analyzing cell type co-occurrence patterns in spatial transcriptomics

#' @title Calculate Spatial Ro/e
#' @description Calculate Ro/e for cell type co-occurrence in spatial neighborhoods.
#' Assesses whether cell types co-occur more or less frequently than expected by chance.
#' @param cell_types Matrix of cell type proportions (spots x cell_types) or character vector
#' @param coords Data frame with x, y coordinates (rows matching cell_types)
#' @param method Neighborhood method: "radius" (default) or "knn"
#' @param radius Radius for neighborhood (in same units as coords) if method="radius"
#' @param k Number of nearest neighbors if method="knn"
#' @param spot_names Optional vector of spot IDs
#' @param min_neighbors Minimum neighbors required for a spot to be included (default: 3)
#' @return List containing roe matrix, observed co-occurrence, expected, and statistics
#' @export
calculate_spatial_roe <- function(
    cell_types,
    coords,
    method = "radius",
    radius = NULL,
    k = 10,
    spot_names = NULL,
    min_neighbors = 3
) {
    if (!requireNamespace("dplyr", quietly = TRUE)) {
        stop("Please install dplyr: install.packages('dplyr')")
    }
    if (!requireNamespace("stats", quietly = TRUE)) {
        stop("stats package required")
    }

    # Validate inputs
    if (is.null(dim(cell_types))) {
        # Convert vector to matrix (one-hot)
        cell_types <- as.character(cell_types)
        type_names <- unique(cell_types)
        type_matrix <- matrix(0, nrow = length(cell_types), ncol = length(type_names))
        colnames(type_matrix) <- type_names
        for (i in seq_along(type_names)) {
            type_matrix[, i] <- as.numeric(cell_types == type_names[i])
        }
        cell_types <- type_matrix
    }

    n_spots <- nrow(cell_types)
    n_cell_types <- ncol(cell_types)

    if (nrow(coords) != n_spots) {
        stop("Number of spots in cell_types and coords must match")
    }

    if (is.null(spot_names)) {
        spot_names <- paste0("Spot_", 1:n_spots)
    }

    # Set default radius if not provided
    if (method == "radius" && is.null(radius)) {
        # Auto-calculate based on coordinate range
        x_range <- diff(range(coords[, 1]))
        y_range <- diff(range(coords[, 2]))
        radius <- min(x_range, y_range) / 20
        message(paste("Auto-calculated radius:", round(radius, 2)))
    }

    # Build neighborhood graph
    message(paste("Building", method, "neighborhoods..."))

    if (method == "radius") {
        neighbors <- build_radius_neighbors(coords, radius, min_neighbors)
    } else if (method == "knn") {
        neighbors <- build_knn_neighbors(coords, k, min_neighbors)
    } else {
        stop("Method must be 'radius' or 'knn'")
    }

    message(paste("Calculated neighborhoods for", length(neighbors), "spots"))

    # Calculate observed co-occurrence
    observed <- calculate_cooccurrence(cell_types, neighbors, method = "mean")

    # Calculate expected co-occurrence (random distribution)
    expected <- calculate_expected_cooccurrence(cell_types, neighbors)

    # Calculate Ro/e
    roe_matrix <- observed / expected
    roe_matrix[is.infinite(roe_matrix)] <- NA
    roe_matrix[is.nan(roe_matrix)] <- 0

    # Calculate statistics
    stats <- calculate_spatial_stats(observed, expected, roe_matrix, cell_types, neighbors)

    result <- list(
        roe = roe_matrix,
        observed = observed,
        expected = expected,
        neighbors = neighbors,
        statistics = stats,
        method = method,
        radius = if(method == "radius") radius else NULL,
        k = if(method == "knn") k else NULL,
        n_spots = n_spots,
        n_cell_types = n_cell_types,
        cell_type_names = colnames(cell_types)
    )

    class(result) <- "spatial_roe_result"
    return(result)
}

#' @title Build Radius-based Neighborhoods
#' @description Find all spots within a given radius for each spot
#' @param coords Data frame with x, y coordinates
#' @param radius Search radius
#' @param min_neighbors Minimum neighbors required
#' @return List of neighbor indices for each spot
#' @keywords internal
build_radius_neighbors <- function(coords, radius, min_neighbors) {
    n <- nrow(coords)
    neighbors <- list()

    # Convert to matrix if needed
    coords_mat <- as.matrix(coords[, 1:2])

    for (i in 1:n) {
        # Calculate distances
        dists <- sqrt(rowSums((coords_mat - coords_mat[i, ])^2))

        # Find neighbors within radius (excluding self)
        neighbor_idx <- which(dists <= radius & dists > 0)

        if (length(neighbor_idx) >= min_neighbors) {
            neighbors[[i]] <- neighbor_idx
        } else {
            neighbors[[i]] <- integer(0)
        }
    }

    names(neighbors) <- rownames(coords)
    return(neighbors)
}

#' @title Build k-NN Neighborhoods
#' @description Find k nearest neighbors for each spot
#' @param coords Data frame with x, y coordinates
#' @param k Number of neighbors
#' @param min_neighbors Minimum neighbors required
#' @return List of neighbor indices for each spot
#' @keywords internal
build_knn_neighbors <- function(coords, k, min_neighbors) {
    n <- nrow(coords)
    neighbors <- list()

    coords_mat <- as.matrix(coords[, 1:2])

    for (i in 1:n) {
        # Calculate distances
        dists <- sqrt(rowSums((coords_mat - coords_mat[i, ])^2))

        # Find k nearest (excluding self)
        dists[i] <- Inf
        neighbor_idx <- order(dists)[1:min(k, n-1)]

        if (length(neighbor_idx) >= min_neighbors) {
            neighbors[[i]] <- neighbor_idx
        } else {
            neighbors[[i]] <- integer(0)
        }
    }

    names(neighbors) <- rownames(coords)
    return(neighbors)
}

#' @title Calculate Co-occurrence Matrix
#' @description Calculate observed cell type co-occurrence in neighborhoods
#' @param cell_types Matrix of cell type proportions
#' @param neighbors List of neighbor indices
#' @param method Aggregation method: "mean", "sum", or "jaccard"
#' @return Co-occurrence matrix
#' @keywords internal
calculate_cooccurrence <- function(cell_types, neighbors, method = "mean") {
    n_types <- ncol(cell_types)
    type_names <- colnames(cell_types)

    cooccur <- matrix(0, nrow = n_types, ncol = n_types)
    rownames(cooccur) <- type_names
    colnames(cooccur) <- type_names

    valid_spots <- which(sapply(neighbors, length) > 0)

    for (i in valid_spots) {
        neighbor_idx <- neighbors[[i]]

        if (length(neighbor_idx) == 0) next

        # Get cell types for center spot and neighbors
        center_props <- cell_types[i, ]
        neighbor_props <- colMeans(cell_types[neighbor_idx, , drop = FALSE])

        # Update co-occurrence based on method
        if (method == "mean") {
            # Average proportion of each cell type in neighborhood
            for (a in 1:n_types) {
                for (b in 1:n_types) {
                    cooccur[a, b] <- cooccur[a, b] + center_props[a] * neighbor_props[b]
                }
            }
        } else if (method == "sum") {
            for (a in 1:n_types) {
                for (b in 1:n_types) {
                    cooccur[a, b] <- cooccur[a, b] + sum(cell_types[neighbor_idx, a] * cell_types[neighbor_idx, b])
                }
            }
        }
    }

    # Normalize by number of valid spots
    if (method == "mean") {
        cooccur <- cooccur / length(valid_spots)
    }

    return(cooccur)
}

#' @title Calculate Expected Co-occurrence
#' @description Calculate expected co-occurrence under random distribution
#' @param cell_types Matrix of cell type proportions
#' @param neighbors List of neighbor indices
#' @return Expected co-occurrence matrix
#' @keywords internal
calculate_expected_cooccurrence <- function(cell_types, neighbors) {
    # Expected = global frequencies (independent distribution)
    global_freq <- colMeans(cell_types)

    n_types <- ncol(cell_types)
    expected <- matrix(0, nrow = n_types, ncol = n_types)

    for (i in 1:n_types) {
        for (j in 1:n_types) {
            expected[i, j] <- global_freq[i] * global_freq[j]
        }
    }

    rownames(expected) <- colnames(cell_types)
    colnames(expected) <- colnames(cell_types)

    return(expected)
}

#' @title Calculate Spatial Statistics
#' @description Calculate statistical significance for spatial Ro/e
#' @param observed Observed co-occurrence matrix
#' @param expected Expected co-occurrence matrix
#' @param roe_matrix Ro/e matrix
#' @param cell_types Cell type matrix
#' @param neighbors Neighborhood list
#' @return List of statistics
#' @keywords internal
calculate_spatial_stats <- function(observed, expected, roe_matrix, cell_types, neighbors) {
    # Permutation test for significance
    n_perm <- 100
    roe_perm <- array(0, dim = c(nrow(roe_matrix), ncol(roe_matrix), n_perm))

    set.seed(42)
    for (p in 1:n_perm) {
        # Permute spot labels
        perm_idx <- sample(nrow(cell_types))
        cell_types_perm <- cell_types[perm_idx, ]

        obs_perm <- calculate_cooccurrence(cell_types_perm, neighbors, method = "mean")
        roe_perm[, , p] <- obs_perm / expected
    }

    # Calculate p-values
    p_values <- matrix(1, nrow = nrow(roe_matrix), ncol = ncol(roe_matrix))
    rownames(p_values) <- rownames(roe_matrix)
    colnames(p_values) <- colnames(roe_matrix)

    for (i in 1:nrow(roe_matrix)) {
        for (j in 1:ncol(roe_matrix)) {
            if (!is.na(roe_matrix[i, j])) {
                # Two-sided test
                p_values[i, j] <- mean(abs(roe_perm[i, j, ] - 1) >= abs(roe_matrix[i, j] - 1), na.rm = TRUE)
            }
        }
    }

    # Adjust p-values
    p_adj <- matrix(p.adjust(p_values, method = "BH"), nrow = nrow(p_values))
    rownames(p_adj) <- rownames(p_values)
    colnames(p_adj) <- colnames(p_values)

    list(
        p_values = p_values,
        p_values_adj = p_adj,
        significant = p_adj < 0.05,
        n_permutations = n_perm
    )
}

#' @title Run Spatial Ro/e on Seurat Object
#' @description Wrapper for Seurat spatial objects
#' @param seurat_obj Seurat object with spatial coordinates
#' @param cell_type_col Column containing cell type annotations or deconvolution results
#' @param assay Assay to use if cell_type_col points to a matrix
#' @param coord_slot Slot containing spatial coordinates (default: "spatial")
#' @param ... Additional parameters passed to calculate_spatial_roe
#' @return spatial_roe_result object
#' @export
run_spatial_roe <- function(
    seurat_obj,
    cell_type_col = "predicted.celltype",
    assay = "predictions",
    coord_slot = "spatial",
    ...
) {
    if (!inherits(seurat_obj, "Seurat")) {
        stop("Input must be a Seurat object")
    }

    # Extract coordinates
    if (coord_slot %in% names(seurat_obj@images)) {
        coords <- GetTissueCoordinates(seurat_obj[[coord_slot]])
    } else if ("coord" %in% colnames(seurat_obj@meta.data)) {
        coords <- seurat_obj@meta.data[, c("x", "y")]
    } else {
        stop("Could not find spatial coordinates")
    }

    # Extract cell type information
    if (cell_type_col %in% colnames(seurat_obj@meta.data)) {
        # Discrete cell type assignments
        cell_types <- seurat_obj@meta.data[[cell_type_col]]
    } else if (cell_type_col %in% rownames(seurat_obj)) {
        # Deconvolution proportions from assay layer
        if (packageVersion("SeuratObject") >= "5.0.0") {
            cell_types <- as.matrix(t(Seurat::LayerData(seurat_obj, assay = assay, layer = "data")))
        } else {
            cell_types <- as.matrix(t(Seurat::GetAssayData(seurat_obj, assay = assay, slot = "data")))
        }
    } else {
        stop(paste("Cell type column not found:", cell_type_col))
    }

    # Run analysis
    result <- calculate_spatial_roe(
        cell_types = cell_types,
        coords = coords,
        spot_names = colnames(seurat_obj),
        ...
    )

    result$seurat_obj <- seurat_obj
    return(result)
}

#' @title Print Spatial Ro/e Result
#' @description Print method for spatial_roe_result objects
#' @param x spatial_roe_result object
#' @param ... Additional arguments
#' @export
print.spatial_roe_result <- function(x, ...) {
    cat("Spatial Ro/e Co-occurrence Analysis\n")
    cat("====================================\n")
    cat("Method:", x$method, "\n")
    if (!is.null(x$radius)) {
        cat("Radius:", round(x$radius, 2), "\n")
    }
    if (!is.null(x$k)) {
        cat("k:", x$k, "\n")
    }
    cat("Spots analyzed:", x$n_spots, "\n")
    cat("Cell types:", x$n_cell_types, "\n\n")

    cat("Ro/e Matrix (top interactions):\n")

    # Get top enriched pairs
    roe_df <- as.data.frame(as.table(x$roe))
    colnames(roe_df) <- c("Cell_Type_A", "Cell_Type_B", "RoE")
    roe_df <- roe_df[order(-roe_df$RoE), ]
    roe_df <- roe_df[roe_df$Cell_Type_A != roe_df$Cell_Type_B, ]  # Exclude self

    print(head(roe_df, 10))

    cat("\nStrongest co-localizations (Ro/e > 2):\n")
    strong <- roe_df[roe_df$RoE > 2 & !is.na(roe_df$RoE), ]
    cat("  Number of pairs:", nrow(strong), "\n")
}

#' @title Convert Spatial Ro/e to Data Frame
#' @description Convert spatial_roe_result to tidy data frame
#' @param spatial_roe_result Result from calculate_spatial_roe()
#' @return Tidy data frame with co-occurrence information
#' @export
spatial_roe_to_dataframe <- function(spatial_roe_result) {
    if (!inherits(spatial_roe_result, "spatial_roe_result")) {
        stop("Input must be a spatial_roe_result object")
    }

    # Melt Ro/e matrix
    roe_df <- as.data.frame(as.table(spatial_roe_result$roe))
    colnames(roe_df) <- c("cell_type_a", "cell_type_b", "roe")

    # Add observed
    obs_df <- as.data.frame(as.table(spatial_roe_result$observed))
    colnames(obs_df) <- c("cell_type_a", "cell_type_b", "observed")

    # Add expected
    exp_df <- as.data.frame(as.table(spatial_roe_result$expected))
    colnames(exp_df) <- c("cell_type_a", "cell_type_b", "expected")

    # Add p-values
    p_df <- as.data.frame(as.table(spatial_roe_result$statistics$p_values_adj))
    colnames(p_df) <- c("cell_type_a", "cell_type_b", "p_value_adj")

    # Merge
    result <- roe_df
    result$observed <- obs_df$observed
    result$expected <- exp_df$expected
    result$p_value_adj <- p_df$p_value_adj
    result$significant <- result$p_value_adj < 0.05

    # Add interpretation
    result$interaction <- ifelse(
        result$roe > 1.5, "Co-localization",
        ifelse(result$roe < 0.67, "Exclusion", "Random")
    )

    # Order by Ro/e
    result <- result[order(-result$roe), ]
    rownames(result) <- NULL

    return(result)
}
