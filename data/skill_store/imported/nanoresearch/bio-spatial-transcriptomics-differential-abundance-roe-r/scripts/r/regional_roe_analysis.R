# Regional Cell Type Abundance Ro/e Analysis
# Quantifies enrichment/depletion of cell types within anatomical regions

#' @title Calculate Regional Cell Type Abundance Ro/e
#' @description Calculate Ro/e for cell type proportions within anatomical regions
#' Assesses whether cell types are enriched or depleted in specific tissue regions
#' @param proportions Matrix of cell type proportions (spots x cell_types) from deconvolution
#' @param regions Vector of region labels for each spot (e.g., "tumor_core", "stroma")
#' @param aggr_method Method to aggregate proportions within regions: "mean" (default), "sum", or "median"
#' @param min_spots Minimum spots required for a region to be included (default: 5)
#' @param min_proportion Minimum mean proportion for a cell type to be analyzed (default: 0.01)
#' @return List containing roe matrix, observed proportions, expected, and statistics
#' @export
calculate_regional_roe <- function(
    proportions,
    regions,
    aggr_method = "mean",
    min_spots = 5,
    min_proportion = 0.01
) {
    if (!requireNamespace("dplyr", quietly = TRUE)) {
        stop("Please install dplyr: install.packages('dplyr')")
    }

    # Validate inputs
    if (nrow(proportions) != length(regions)) {
        stop("Number of rows in proportions must match length of regions")
    }

    if (is.null(colnames(proportions))) {
        colnames(proportions) <- paste0("CellType_", 1:ncol(proportions))
    }

    # Remove NA regions
    valid_idx <- !is.na(regions)
    proportions <- proportions[valid_idx, , drop = FALSE]
    regions <- regions[valid_idx]

    # Filter regions with sufficient spots
    region_counts <- table(regions)
    valid_regions <- names(region_counts)[region_counts >= min_spots]

    if (length(valid_regions) == 0) {
        stop("No regions with sufficient spots (min_spots = ", min_spots, ")")
    }

    if (length(valid_regions) < length(region_counts)) {
        message("Excluding regions with < ", min_spots, " spots: ",
                paste(setdiff(names(region_counts), valid_regions), collapse = ", "))
        proportions <- proportions[regions %in% valid_regions, , drop = FALSE]
        regions <- regions[regions %in% valid_regions]
    }

    # Filter cell types with sufficient overall proportion
    overall_mean <- colMeans(proportions)
    valid_celltypes <- names(overall_mean)[overall_mean >= min_proportion]

    if (length(valid_celltypes) == 0) {
        stop("No cell types with sufficient proportion (min_proportion = ", min_proportion, ")")
    }

    if (length(valid_celltypes) < ncol(proportions)) {
        message("Excluding rare cell types (< ", min_proportion, " mean proportion): ",
                paste(setdiff(colnames(proportions), valid_celltypes), collapse = ", "))
        proportions <- proportions[, valid_celltypes, drop = FALSE]
    }

    cell_types <- colnames(proportions)
    region_names <- valid_regions

    message("Analyzing ", length(cell_types), " cell types across ",
            length(region_names), " regions")

    # Calculate observed proportions per region
    observed <- matrix(0, nrow = length(cell_types), ncol = length(region_names))
    rownames(observed) <- cell_types
    colnames(observed) <- region_names

    spot_counts <- numeric(length(region_names))
    names(spot_counts) <- region_names

    for (i in seq_along(region_names)) {
        region <- region_names[i]
        region_mask <- regions == region
        region_props <- proportions[region_mask, , drop = FALSE]
        spot_counts[i] <- nrow(region_props)

        observed[, i] <- switch(aggr_method,
            "mean" = colMeans(region_props),
            "sum" = colSums(region_props),
            "median" = apply(region_props, 2, median),
            stop("Unknown aggregation method: ", aggr_method)
        )
    }

    # Calculate expected proportions (global mean across all spots)
    expected <- colMeans(proportions)

    # Calculate Ro/e
    roe_matrix <- matrix(0, nrow = length(cell_types), ncol = length(region_names))
    rownames(roe_matrix) <- cell_types
    colnames(roe_matrix) <- region_names

    for (i in 1:length(cell_types)) {
        for (j in 1:length(region_names)) {
            if (expected[i] > 0) {
                roe_matrix[i, j] <- observed[i, j] / expected[i]
            } else {
                roe_matrix[i, j] <- NA
            }
        }
    }

    # Handle extreme values
    roe_matrix[is.infinite(roe_matrix)] <- NA
    roe_matrix[is.nan(roe_matrix)] <- 0

    # Calculate statistics
    stats <- calculate_regional_stats(roe_matrix, observed, expected, proportions, regions)

    result <- list(
        roe = roe_matrix,
        observed = observed,
        expected = expected,
        region_spot_counts = spot_counts,
        statistics = stats,
        aggr_method = aggr_method,
        n_spots = nrow(proportions),
        n_cell_types = length(cell_types),
        n_regions = length(region_names),
        cell_types = cell_types,
        regions = region_names
    )

    class(result) <- "regional_roe_result"
    return(result)
}

#' @title Calculate Regional Statistics
#' @description Calculate statistical significance for regional Ro/e
#' @param roe_matrix Ro/e matrix
#' @param observed Observed proportions matrix
#' @param expected Expected proportions vector
#' @param proportions Original proportion matrix
#' @param regions Region labels
#' @return List of statistical results
#' @keywords internal
calculate_regional_stats <- function(roe_matrix, observed, expected, proportions, regions) {
    # Permutation test
    n_perm <- 100
    roe_perm <- array(0, dim = c(nrow(roe_matrix), ncol(roe_matrix), n_perm))

    set.seed(42)
    for (p in 1:n_perm) {
        # Permute region labels
        perm_regions <- sample(regions)

        # Recalculate observed with permuted labels
        perm_observed <- matrix(0, nrow = ncol(proportions), ncol = length(unique(regions)))

        for (j in seq_along(unique(regions))) {
            region <- unique(regions)[j]
            region_mask <- perm_regions == region
            if (sum(region_mask) > 0) {
                perm_observed[, j] <- colMeans(proportions[region_mask, , drop = FALSE])
            }
        }

        # Calculate Ro/e for permutation
        for (i in 1:nrow(perm_observed)) {
            for (j in 1:ncol(perm_observed)) {
                if (expected[i] > 0) {
                    roe_perm[i, j, p] <- perm_observed[i, j] / expected[i]
                }
            }
        }
    }

    # Calculate p-values
    p_values <- matrix(1, nrow = nrow(roe_matrix), ncol = ncol(roe_matrix))
    rownames(p_values) <- rownames(roe_matrix)
    colnames(p_values) <- colnames(roe_matrix)

    for (i in 1:nrow(roe_matrix)) {
        for (j in 1:ncol(roe_matrix)) {
            if (!is.na(roe_matrix[i, j])) {
                # Two-sided test
                p_values[i, j] <- mean(abs(roe_perm[i, j, ] - 1) >=
                                         abs(roe_matrix[i, j] - 1), na.rm = TRUE)
            }
        }
    }

    # Adjust p-values (Benjamini-Hochberg)
    p_adj <- matrix(p.adjust(p_values, method = "BH"),
                    nrow = nrow(p_values), ncol = ncol(p_values))
    rownames(p_adj) <- rownames(p_values)
    colnames(p_adj) <- colnames(p_values)

    list(
        p_values = p_values,
        p_values_adj = p_adj,
        significant = p_adj < 0.05,
        n_permutations = n_perm
    )
}

#' @title Calculate Regional Ro/e with Bootstrap CI
#' @description Calculate regional Ro/e with bootstrap confidence intervals
#' @param proportions Cell type proportion matrix
#' @param regions Region labels
#' @param n_bootstrap Number of bootstrap iterations (default: 500)
#' @param conf_level Confidence level (default: 0.95)
#' @param ... Additional parameters passed to calculate_regional_roe
#' @return regional_roe_result with bootstrap CI
#' @export
calculate_regional_roe_bootstrap <- function(
    proportions,
    regions,
    n_bootstrap = 500,
    conf_level = 0.95,
    ...
) {
    # Calculate base result
    base_result <- calculate_regional_roe(proportions, regions, ...)

    # Bootstrap
    n_spots <- nrow(proportions)
    boot_roe <- array(0, dim = c(nrow(base_result$roe), ncol(base_result$roe), n_bootstrap))

    set.seed(42)
    for (b in 1:n_bootstrap) {
        # Bootstrap sample spots within each region
        boot_idx <- unlist(tapply(1:n_spots, regions, function(idx) {
            sample(idx, length(idx), replace = TRUE)
        }))

        boot_result <- calculate_regional_roe(
            proportions[boot_idx, , drop = FALSE],
            regions[boot_idx],
            aggr_method = base_result$aggr_method,
            min_spots = 1  # Lower threshold for bootstrap
        )

        boot_roe[, , b] <- boot_result$roe
    }

    # Calculate CI
    alpha <- 1 - conf_level
    ci_lower <- apply(boot_roe, c(1, 2), quantile, probs = alpha / 2, na.rm = TRUE)
    ci_upper <- apply(boot_roe, c(1, 2), quantile, probs = 1 - alpha / 2, na.rm = TRUE)
    roe_sd <- apply(boot_roe, c(1, 2), sd, na.rm = TRUE)

    base_result$bootstrap <- list(
        n_bootstrap = n_bootstrap,
        conf_level = conf_level,
        ci_lower = ci_lower,
        ci_upper = ci_upper,
        roe_sd = roe_sd
    )

    return(base_result)
}

#' @title Compare Regional Ro/e Across Conditions
#' @description Compare cell type regional enrichment between conditions (e.g., High vs Low NI)
#' @param proportions_list Named list of proportion matrices for each condition
#' @param regions_list Named list of region label vectors for each condition
#' @param ... Additional parameters passed to calculate_regional_roe
#' @return List of regional_roe_result objects with comparison statistics
#' @export
compare_regional_roe <- function(
    proportions_list,
    regions_list,
    ...
) {
    if (length(proportions_list) != length(regions_list)) {
        stop("proportions_list and regions_list must have same length")
    }

    # Calculate Ro/e for each condition
    results <- list()
    for (name in names(proportions_list)) {
        message("Processing condition: ", name)
        results[[name]] <- calculate_regional_roe(
            proportions_list[[name]],
            regions_list[[name]],
            ...
        )
    }

    # Find common regions and cell types
    common_regions <- Reduce(intersect, lapply(results, function(r) r$regions))
    common_celltypes <- Reduce(intersect, lapply(results, function(r) r$cell_types))

    if (length(common_regions) == 0) {
        warning("No common regions found across conditions")
    }
    if (length(common_celltypes) == 0) {
        warning("No common cell types found across conditions")
    }

    # Calculate differential Ro/e
    if (length(results) == 2) {
        names_cond <- names(results)

        # Subset to common elements
        roe1 <- results[[1]]$roe[common_celltypes, common_regions, drop = FALSE]
        roe2 <- results[[2]]$roe[common_celltypes, common_regions, drop = FALSE]

        diff_roe <- roe1 - roe2
        fold_change <- roe1 / roe2

        results$differential <- list(
            diff_roe = diff_roe,
            fold_change = fold_change,
            condition_1 = names_cond[1],
            condition_2 = names_cond[2],
            common_regions = common_regions,
            common_celltypes = common_celltypes
        )
    }

    class(results) <- "regional_roe_comparison"
    return(results)
}

#' @title Run Regional Ro/e on Seurat Object
#' @description Wrapper for Seurat objects with deconvolution results
#' @param seurat_obj Seurat object
#' @param deconv_assay Assay containing deconvolution proportions (default: "predictions")
#' @param region_col Column in metadata containing region labels
#' @param ... Additional parameters passed to calculate_regional_roe
#' @return regional_roe_result object
#' @export
run_regional_roe <- function(
    seurat_obj,
    deconv_assay = "predictions",
    region_col = "region",
    ...
) {
    if (!inherits(seurat_obj, "Seurat")) {
        stop("Input must be a Seurat object")
    }

    # Extract deconvolution proportions
    if (deconv_assay %in% names(seurat_obj@assays)) {
        # Use GetAssayData for Seurat v4/v5 compatibility
        if (packageVersion("SeuratObject") >= "5.0.0") {
            proportions <- as.matrix(t(Seurat::LayerData(seurat_obj, assay = deconv_assay, layer = "data")))
        } else {
            proportions <- as.matrix(t(Seurat::GetAssayData(seurat_obj, assay = deconv_assay, slot = "data")))
        }
    } else if (deconv_assay %in% colnames(seurat_obj@meta.data)) {
        # Single cell type column
        props <- seurat_obj@meta.data[[deconv_assay]]
        proportions <- matrix(props, ncol = 1)
        colnames(proportions) <- deconv_assay
    } else {
        stop("Deconvolution assay not found: ", deconv_assay)
    }

    # Extract region labels
    if (!region_col %in% colnames(seurat_obj@meta.data)) {
        stop("Region column not found: ", region_col)
    }
    regions <- seurat_obj@meta.data[[region_col]]

    # Run analysis
    result <- calculate_regional_roe(proportions, regions, ...)
    result$seurat_obj <- seurat_obj

    return(result)
}

#' @title Print Regional Ro/e Result
#' @description Print method for regional_roe_result objects
#' @param x regional_roe_result object
#' @param ... Additional arguments
#' @export
print.regional_roe_result <- function(x, ...) {
    cat("Regional Cell Type Abundance Ro/e Analysis\n")
    cat("==========================================\n")
    cat("Aggregation method:", x$aggr_method, "\n")
    cat("Total spots:", format(x$n_spots, big.mark = ","), "\n")
    cat("Regions:", paste(x$regions, collapse = ", "), "\n")
    cat("Cell types:", length(x$cell_types), "\n")
    cat("Spots per region:\n")
    for (region in names(x$region_spot_counts)) {
        cat("  ", region, ": ", x$region_spot_counts[region], "\n")
    }
    cat("\n")

    cat("Ro/e Matrix:\n")
    print(round(x$roe, 2))

    cat("\nTop enriched cell types per region:\n")
    for (region in colnames(x$roe)) {
        top_idx <- order(-x$roe[, region])[1:3]
        cat("  ", region, ": ")
        cat(paste(rownames(x$roe)[top_idx], "(", round(x$roe[top_idx, region], 1), ")",
                  collapse = ", "), "\n")
    }
}

#' @title Convert Regional Ro/e to Data Frame
#' @description Convert regional_roe_result to tidy data frame
#' @param regional_roe_result Result from calculate_regional_roe()
#' @return Tidy data frame
#' @export
regional_roe_to_dataframe <- function(regional_roe_result) {
    if (!inherits(regional_roe_result, "regional_roe_result")) {
        stop("Input must be a regional_roe_result object")
    }

    # Melt Ro/e matrix
    roe_df <- as.data.frame(as.table(regional_roe_result$roe))
    colnames(roe_df) <- c("cell_type", "region", "roe")

    # Add observed
    obs_df <- as.data.frame(as.table(regional_roe_result$observed))
    roe_df$observed <- obs_df$Freq

    # Add expected
    exp_df <- data.frame(
        cell_type = names(regional_roe_result$expected),
        expected = regional_roe_result$expected,
        stringsAsFactors = FALSE
    )
    roe_df <- merge(roe_df, exp_df, by = "cell_type")

    # Add p-values
    p_df <- as.data.frame(as.table(regional_roe_result$statistics$p_values_adj))
    roe_df$p_value_adj <- p_df$Freq
    roe_df$significant <- roe_df$p_value_adj < 0.05

    # Add bootstrap CI if available
    if (!is.null(regional_roe_result$bootstrap)) {
        ci_lower_df <- as.data.frame(as.table(regional_roe_result$bootstrap$ci_lower))
        ci_upper_df <- as.data.frame(as.table(regional_roe_result$bootstrap$ci_upper))
        roe_df$ci_lower <- ci_lower_df$Freq
        roe_df$ci_upper <- ci_upper_df$Freq
    }

    # Add interpretation
    roe_df$pattern <- ifelse(
        roe_df$roe > 1.5, "Strongly Enriched",
        ifelse(roe_df$roe > 1.2, "Moderately Enriched",
               ifelse(roe_df$roe < 0.67, "Strongly Depleted",
                      ifelse(roe_df$roe < 0.83, "Moderately Depleted", "Neutral")))
    )

    # Order
    roe_df <- roe_df[order(roe_df$region, -roe_df$roe), ]
    rownames(roe_df) <- NULL

    return(roe_df)
}

#' @title Calculate Regional Specificity Index
#' @description Calculate how specific each cell type is to particular regions
#' @param regional_roe_result Result from calculate_regional_roe()
#' @return Data frame with specificity scores
#' @export
calculate_regional_specificity <- function(regional_roe_result) {
    roe <- regional_roe_result$roe

    # Calculate metrics per cell type
    specificity <- data.frame(
        cell_type = rownames(roe),
        max_roe = apply(roe, 1, max, na.rm = TRUE),
        max_region = colnames(roe)[apply(roe, 1, which.max)],
        min_roe = apply(roe, 1, min, na.rm = TRUE),
        sd_roe = apply(roe, 1, sd, na.rm = TRUE),
        stringsAsFactors = FALSE
    )

    # Specificity score: max Ro/e normalized by variation across regions
    specificity$specificity_score <- specificity$max_roe / (1 + specificity$sd_roe)

    # Classify specificity pattern
    specificity$pattern <- ifelse(
        specificity$max_roe > 2 & specificity$sd_roe > 0.5,
        "Highly Regional",
        ifelse(specificity$max_roe > 1.5, "Moderately Regional",
               ifelse(specificity$sd_roe < 0.3, "Ubiquitous", "Variable"))
    )

    return(specificity[order(-specificity$specificity_score), ])
}
