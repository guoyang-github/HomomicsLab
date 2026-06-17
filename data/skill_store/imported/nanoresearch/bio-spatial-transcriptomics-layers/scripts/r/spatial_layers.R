# Spatial Layer Analysis for Seurat Objects
# Create concentric layers around ROI for gradient analysis

#' Create Spatial Layers Around ROI
#'
#' Divide tissue into concentric layers centered on a Region of Interest (ROI),
#' enabling analysis of microenvironment gradients (e.g., tumor infiltration zones,
#' perineural regions, perivascular niches).
#'
#' @param seurat_obj Seurat object with spatial coordinates
#' @param roi.definition Definition of center region
#' @param roi.type Type of ROI definition: "niche", "cell_type", "mask", "coordinates"
#' @param n.layers Number of layers to create (excluding center/ROI layer)
#' @param layer.method Method for layer creation: "distance", "knn", or "radius"
#' @param distance.threshold Distance thresholds for layer boundaries
#' @param layer.names Custom names for layers
#' @param buffer.zone Distance buffer between ROI and first layer
#' @param return.distance Whether to store distance to ROI
#' @param spatial.coord Slot containing spatial coordinates
#' @return Seurat object with spatial_layer metadata
#' @export
CreateSpatialLayers <- function(
    seurat_obj,
    roi.definition,
    roi.type = c("niche", "cell_type", "mask", "coordinates"),
    n.layers = 3,
    layer.method = c("distance", "knn", "radius"),
    distance.threshold = NULL,
    layer.names = NULL,
    buffer.zone = 0,
    return.distance = TRUE,
    spatial.coord = "spatial"
) {
    roi.type <- match.arg(roi.type)
    layer.method <- match.arg(layer.method)

    # Extract coordinates
    if (!spatial.coord %in% names(seurat_obj@images)) {
        stop(paste("Spatial coordinates not found:", spatial.coord))
    }

    coords <- GetTissueCoordinates(seurat_obj[[spatial.coord]])
    coords.2d <- as.matrix(coords[, c(1, 2)])

    # Parse ROI definition
    roi.mask <- .ParseROIDefinition(seurat_obj, roi.definition, roi.type)

    if (sum(roi.mask) == 0) {
        stop("No spots found matching ROI definition")
    }

    message(paste("Found", sum(roi.mask), "ROI spots"))

    # Calculate distances
    distances <- switch(layer.method,
        "distance" = .CalculateDistanceToROI(coords.2d, roi.mask),
        "knn" = .CalculateKNNDistance(seurat_obj, roi.mask),
        "radius" = .CalculateRadiusDistance(coords.2d, roi.mask)
    )

    # Determine layer boundaries
    if (is.null(distance.threshold)) {
        max.dist <- max(distances[!roi.mask])
        layer.boundaries <- seq(0, max.dist, length.out = n.layers + 1)[-1]
    } else if (length(distance.threshold) == 1) {
        layer.boundaries <- distance.threshold * (1:n.layers)
    } else {
        layer.boundaries <- distance.threshold
        n.layers <- length(layer.boundaries)
    }

    message(paste("Layer boundaries:", paste(round(layer.boundaries, 1), collapse = ", ")))

    # Assign layers
    layers <- .AssignLayers(distances, roi.mask, layer.boundaries, buffer.zone)

    # Generate layer names
    if (is.null(layer.names)) {
        layer.names <- c("center", paste0("layer_", 1:n.layers))
    }

    # Map layer indices to names
    layer.map <- setNames(layer.names, 0:n.layers)
    layer.labels <- layer.map[as.character(layers)]
    layer.labels[is.na(layer.labels)] <- "unassigned"

    # Add to metadata
    seurat_obj$spatial_layer <- factor(layer.labels, levels = layer.names)
    seurat_obj$roi_status <- roi.mask

    if (return.distance) {
        seurat_obj$distance_to_roi <- distances
    }

    # Calculate statistics
    layer.stats <- .CalculateLayerStats(seurat_obj, layers, layer.names, distances, roi.mask)

    # Store in misc
    seurat_obj@misc$spatial_layers <- list(
        params = list(
            roi_type = roi.type,
            roi_definition = ifelse(is.character(roi.definition),
                                    paste(roi.definition, collapse = ","),
                                    "custom_mask"),
            n_layers = n.layers,
            layer_method = layer.method,
            distance_threshold = distance.threshold,
            buffer_zone = buffer.zone,
            layer_names = layer.names
        ),
        layer_stats = layer.stats
    )

    # Print summary
    message(paste("\nCreated", n.layers + 1, "layers:"))
    for (name in layer.names) {
        count <- sum(layer.labels == name)
        message(paste(" ", name, ":", count, "spots"))
    }

    return(seurat_obj)
}


#' Parse ROI Definition
#' @keywords internal
.ParseROIDefinition <- function(seurat_obj, roi.definition, roi.type) {
    switch(roi.type,
        "mask" = {
            if (length(roi.definition) != ncol(seurat_obj)) {
                stop(paste("Mask length doesn't match n_cells:",
                          length(roi.definition), "!=", ncol(seurat_obj)))
            }
            return(as.logical(roi.definition))
        },

        "niche" = {
            niche.col <- ifelse("niche_annotated" %in% colnames(seurat_obj@meta.data),
                               "niche_annotated", "niche")
            if (!niche.col %in% colnames(seurat_obj@meta.data)) {
                stop("Niche column not found. Run niche clustering first.")
            }

            if (is.character(roi.definition)) {
                return(seurat_obj@meta.data[[niche.col]] %in% roi.definition)
            } else {
                return(seurat_obj@meta.data[[niche.col]] == roi.definition)
            }
        },

        "cell_type" = {
            # Try to find in metadata
            for (col in colnames(seurat_obj@meta.data)) {
                if (is.character(seurat_obj@meta.data[[col]]) ||
                    is.factor(seurat_obj@meta.data[[col]])) {
                    mask <- seurat_obj@meta.data[[col]] %in% roi.definition
                    if (any(mask)) return(mask)
                }
            }
            stop(paste("Cell type", paste(roi.definition, collapse = ", "), "not found"))
        },

        "coordinates" = {
            coords <- GetTissueCoordinates(seurat_obj)
            center <- matrix(as.numeric(roi.definition), ncol = 2)

            if (nrow(center) == 1) {
                # Single center point
                dists <- sqrt(rowSums((as.matrix(coords[, 1:2]) - center)^2))
                return(dists < 50)  # 50μm radius
            } else {
                # Multiple centers
                dists <- apply(center, 1, function(c) {
                    sqrt(rowSums((as.matrix(coords[, 1:2]) - c)^2))
                })
                if (is.matrix(dists)) {
                    dists <- apply(dists, 1, min)
                }
                return(dists < 50)
            }
        },

        stop(paste("Unknown roi_type:", roi.type))
    )
}


#' Calculate Euclidean Distance to ROI
#' @keywords internal
.CalculateDistanceToROI <- function(coords, roi.mask) {
    roi.coords <- coords[roi.mask, , drop = FALSE]

    if (nrow(roi.coords) == 0) {
        return(rep(Inf, nrow(coords)))
    }

    # Calculate distance to nearest ROI spot
    dists <- proxy::dist(coords, roi.coords)
    min.dists <- apply(as.matrix(dists), 1, min)

    # ROI spots have distance 0
    min.dists[roi.mask] <- 0

    return(min.dists)
}


#' Calculate KNN Distance
#' @keywords internal
.CalculateKNNDistance <- function(seurat_obj, roi.mask) {
    # Build neighbor graph
    seurat_obj <- FindNeighbors(seurat_obj, reduction = "spatial",
                                 dims = 1:2, k.param = 6)

    # BFS to find shortest path
    adj <- as.matrix(seurat_obj@graphs$RNA_nn)
    n <- length(roi.mask)
    distances <- rep(-1, n)
    distances[roi.mask] <- 0

    current.layer <- 0
    current.spots <- which(roi.mask)

    while (length(current.spots) > 0 && any(distances == -1)) {
        next.spots <- c()
        for (spot in current.spots) {
            neighbors <- which(adj[spot, ] > 0)
            for (neighbor in neighbors) {
                if (distances[neighbor] == -1) {
                    distances[neighbor] <- current.layer + 1
                    next.spots <- c(next.spots, neighbor)
                }
            }
        }
        current.spots <- next.spots
        current.layer <- current.layer + 1
    }

    return(distances)
}


#' Calculate Radius Distance from ROI Center
#' @keywords internal
.CalculateRadiusDistance <- function(coords, roi.mask) {
    roi.coords <- coords[roi.mask, , drop = FALSE]
    center <- colMeans(roi.coords)

    dists <- sqrt(rowSums((coords - center)^2))
    return(dists)
}


#' Assign Spots to Layers
#' @keywords internal
.AssignLayers <- function(distances, roi.mask, layer.boundaries, buffer.zone) {
    n <- length(distances)
    layers <- rep(-1, n)  # -1 = unassigned

    # ROI is layer 0
    layers[roi.mask] <- 0

    # Assign layers based on distance
    for (i in seq_along(layer.boundaries)) {
        boundary <- layer.boundaries[i]

        if (i == 1) {
            # First layer
            if (buffer.zone > 0) {
                mask <- !roi.mask & distances > buffer.zone & distances <= boundary
            } else {
                mask <- !roi.mask & distances <= boundary
            }
        } else {
            # Subsequent layers
            prev.boundary <- layer.boundaries[i - 1]
            mask <- !roi.mask & distances > prev.boundary & distances <= boundary
        }

        layers[mask] <- i
    }

    # Assign spots beyond last boundary
    if (length(layer.boundaries) > 0) {
        last.boundary <- layer.boundaries[length(layer.boundaries)]
        mask <- !roi.mask & distances > last.boundary
        layers[mask] <- length(layer.boundaries)
    }

    return(layers)
}


#' Calculate Layer Statistics
#' @keywords internal
.CalculateLayerStats <- function(seurat_obj, layers, layer.names, distances, roi.mask) {
    stats <- list()

    for (i in seq_along(layer.names)) {
        name <- layer.names[i]
        mask <- layers == (i - 1)

        if (any(mask)) {
            stats[[name]] <- list(
                n_spots = sum(mask),
                mean_distance = mean(distances[mask]),
                min_distance = min(distances[mask]),
                max_distance = max(distances[mask]),
                fraction = sum(mask) / length(layers)
            )
        }
    }

    return(stats)
}


#' Analyze Feature Gradients Across Layers
#'
#' @param seurat_obj Seurat object with layer annotations
#' @param layer.key Metadata column with layer info
#' @param features Features to analyze (gene names or metadata columns)
#' @param feature.type Type: "gene" or "metadata"
#' @param method Analysis method: "trend", "anova", "wilcox"
#' @return Data frame with gradient analysis results
#' @export
AnalyzeLayerGradients <- function(
    seurat_obj,
    layer.key = "spatial_layer",
    features = NULL,
    feature.type = c("gene", "metadata"),
    method = "trend"
) {
    feature.type <- match.arg(feature.type)

    # Get layer order
    if (is.factor(seurat_obj@meta.data[[layer.key]])) {
        layer.order <- levels(seurat_obj@meta.data[[layer.key]])
    } else {
        layer.order <- unique(seurat_obj@meta.data[[layer.key]])
    }

    # Get features
    if (is.null(features)) {
        if (feature.type == "gene") {
            features <- head(rownames(seurat_obj), 100)
        } else {
            features <- colnames(seurat_obj@meta.data)[
                sapply(seurat_obj@meta.data, is.numeric)
            ]
        }
    }

    results <- data.frame()

    for (feature in features) {
        # Extract values
        if (feature.type == "gene") {
            if (!feature %in% rownames(seurat_obj)) next
            if (packageVersion("SeuratObject") >= "5.0.0") {
                values <- Seurat::GetAssayData(seurat_obj, layer = "data")[feature, ]
            } else {
                values <- Seurat::GetAssayData(seurat_obj, slot = "data")[feature, ]
            }
        } else {
            if (!feature %in% colnames(seurat_obj@meta.data)) next
            values <- seurat_obj@meta.data[[feature]]
        }

        # Calculate per-layer statistics
        layer.means <- sapply(layer.order, function(layer) {
            mask <- seurat_obj@meta.data[[layer.key]] == layer
            if (sum(mask) == 0) return(NA)
            mean(values[mask], na.rm = TRUE)
        })

        # Determine trend
        trend <- .DetermineTrend(layer.means)

        # Statistical test
        if (method == "anova" && length(layer.order) > 2) {
            # One-way ANOVA
            formula <- as.formula(paste(feature, "~", layer.key))
            fit <- aov(formula, data = seurat_obj@meta.data)
            pval <- summary(fit)[[1]][["Pr(>F)"]][1]
        } else {
            pval <- NA
        }

        # Reference layer (first layer)
        ref.mean <- layer.means[1]

        for (i in seq_along(layer.order)) {
            layer <- layer.order[i]
            layer.mean <- layer.means[i]

            # Calculate log2 fold change
            if (!is.na(ref.mean) && !is.na(layer.mean) && ref.mean > 0 && layer.mean > 0) {
                log2fc <- log2(layer.mean / ref.mean)
            } else {
                log2fc <- NA
            }

            results <- rbind(results, data.frame(
                feature = feature,
                layer = layer,
                mean_value = layer.mean,
                log2fc = log2fc,
                trend = trend,
                pval = pval,
                stringsAsFactors = FALSE
            ))
        }
    }

    return(results)
}


#' Determine Trend Pattern
#' @keywords internal
.DetermineTrend <- function(means) {
    if (all(diff(means) >= 0, na.rm = TRUE)) {
        return("increasing")
    } else if (all(diff(means) <= 0, na.rm = TRUE)) {
        return("decreasing")
    } else if (means[1] < max(means) && tail(means, 1) < max(means)) {
        return("peaked")
    } else if (means[1] > min(means) && tail(means, 1) > min(means)) {
        return("valley")
    } else {
        return("variable")
    }
}


#' Visualize Spatial Layers
#'
#' @param seurat_obj Seurat object
#' @param layer.key Metadata column with layer info
#' @param group.by Additional grouping variable
#' @param ncol Number of columns for facet
#' @return ggplot object
#' @export
PlotSpatialLayers <- function(seurat_obj, layer.key = "spatial_layer",
                               group.by = NULL, ncol = NULL) {

    # Get coordinates
    coords <- as.data.frame(GetTissueCoordinates(seurat_obj))
    colnames(coords)[1:2] <- c("x", "y")

    # Add metadata
    coords$layer <- seurat_obj@meta.data[[layer.key]]

    if (!is.null(group.by)) {
        coords$group <- seurat_obj@meta.data[[group.by]]
    }

    # Create plot
    p <- ggplot2::ggplot(coords, ggplot2::aes(x = x, y = y, color = layer)) +
        ggplot2::geom_point(size = 1.5, alpha = 0.7) +
        ggplot2::coord_fixed() +
        ggplot2::labs(title = "Spatial Layers", color = "Layer") +
        ggplot2::theme_minimal()

    if (!is.null(group.by)) {
        p <- p + ggplot2::facet_wrap(~group, ncol = ncol)
    }

    return(p)
}


#' Plot Layer Composition
#'
#' @param seurat_obj Seurat object
#' @param layer.key Layer column
#' @param features Features to plot
#' @param plot.type "boxplot" or "heatmap"
#' @return ggplot object
#' @export
PlotLayerComposition <- function(seurat_obj, layer.key = "spatial_layer",
                                  features, plot.type = c("boxplot", "heatmap")) {
    plot.type <- match.arg(plot.type)

    # Extract data
    data <- FetchData(seurat_obj, vars = c(features, layer.key))

    if (plot.type == "boxplot") {
        # Melt for ggplot
        data.melt <- reshape2::melt(data, id.vars = layer.key)
        colnames(data.melt)[1] <- "layer"

        p <- ggplot2::ggplot(data.melt, ggplot2::aes(x = layer, y = value, fill = layer)) +
            ggplot2::geom_boxplot() +
            ggplot2::facet_wrap(~variable, scales = "free_y") +
            ggplot2::labs(x = "Layer", y = "Value") +
            ggplot2::theme_minimal() +
            ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1))

    } else {
        # Heatmap of mean values
        means <- aggregate(. ~ data[[layer.key]], data[, features], mean)
        rownames(means) <- means[, 1]
        means <- means[, -1]

        # Normalize
        means.scaled <- scale(t(means))

        p <- pheatmap::pheatmap(means.scaled,
                               main = "Feature Values Across Layers",
                               cluster_cols = FALSE)
    }

    return(p)
}


#' Plot Layer Heatmap
#'
#' Create a heatmap visualization of feature values across spatial layers.
#' Similar to Python plot_layer_heatmap function.
#'
#' @param gradient_results Data frame from AnalyzeLayerGradients
#' @param value_col Column containing values to plot (default: "mean_value")
#' @param normalize Whether to normalize values per feature (row)
#' @param cluster_rows Whether to cluster rows
#' @param cluster_cols Whether to cluster columns
#' @param color Color palette
#' @param main Plot title
#' @return pheatmap object
#' @export
PlotLayerHeatmap <- function(
    gradient_results,
    value_col = "mean_value",
    normalize = TRUE,
    cluster_rows = TRUE,
    cluster_cols = FALSE,
    color = NULL,
    main = "Feature Values Across Layers"
) {
    # Reshape to wide format
    wide_data <- reshape2::dcast(
        gradient_results,
        feature ~ layer,
        value.var = value_col
    )

    # Extract feature names
    features <- wide_data$feature
    wide_data <- wide_data[, -1]
    rownames(wide_data) <- features

    # Handle missing values
    wide_data[is.na(wide_data)] <- 0

    # Normalize if requested
    if (normalize && nrow(wide_data) > 1) {
        mat <- as.matrix(wide_data)
        mat_scaled <- t(scale(t(mat)))
        mat_scaled[is.nan(mat_scaled)] <- 0
        mat_scaled[is.infinite(mat_scaled)] <- 0
    } else {
        mat_scaled <- as.matrix(wide_data)
    }

    # Default color scheme
    if (is.null(color)) {
        color <- colorRampPalette(c("#2c7bb6", "#ffffbf", "#d7191c"))(100)
    }

    # Create heatmap
    p <- pheatmap::pheatmap(
        mat_scaled,
        main = main,
        cluster_rows = cluster_rows,
        cluster_cols = cluster_cols,
        color = color,
        show_rownames = TRUE,
        show_colnames = TRUE,
        fontsize_row = 8,
        fontsize_col = 10
    )

    return(p)
}
