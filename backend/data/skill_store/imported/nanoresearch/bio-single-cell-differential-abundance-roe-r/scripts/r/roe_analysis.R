# Ro/e (Ratio of Observed to Expected) Analysis for Differential Abundance
# For comparing cell type proportions across conditions/groups

#' @title Calculate Ro/e for Differential Abundance
#' @description Calculate Ratio of Observed to Expected cell type proportions
#' across biological groups (e.g., High NI vs Low NI)
#' @param cell_types Vector of cell type annotations
#' @param groups Vector of group assignments (e.g., "High_NI", "Low_NI")
#' @param samples Optional vector of sample IDs for paired analysis
#' @param method Calculation method: "group" (default) or "global"
#' @return List containing roe matrix, observed, expected, and statistics
#' @export
calculate_roe <- function(
    cell_types,
    groups,
    samples = NULL,
    method = "group"
) {
    # Create data frame
    df <- data.frame(
        cell_type = as.character(cell_types),
        group = as.character(groups),
        stringsAsFactors = FALSE
    )

    if (!is.null(samples)) {
        df$sample <- as.character(samples)
    }

    # Remove NAs
    df <- df[!is.na(df$cell_type) & !is.na(df$group), ]

    # Calculate observed proportions per group (column proportions within each group)
    obs_table <- table(df$cell_type, df$group)
    observed <- prop.table(obs_table, margin = 2)  # Column proportions

    # Calculate expected proportions
    cell_type_totals <- rowSums(obs_table)
    total_cells <- sum(obs_table)
    if (method == "global") {
        # Global: uniform distribution across cell types
        expected <- rep(1 / length(cell_type_totals), length(cell_type_totals))
        names(expected) <- names(cell_type_totals)
    } else {
        # Group: overall observed proportion across all groups
        expected <- cell_type_totals / total_cells
    }

    # Calculate Ro/e for each group
    roe_matrix <- matrix(0,
                         nrow = nrow(observed),
                         ncol = ncol(observed),
                         dimnames = dimnames(observed))

    for (i in 1:ncol(observed)) {
        roe_matrix[, i] <- observed[, i] / expected
    }

    # Handle infinite and NA values
    roe_matrix[is.infinite(roe_matrix)] <- NA
    roe_matrix[is.nan(roe_matrix)] <- 0

    # Calculate statistics
    stats <- calculate_roe_stats(obs_table, roe_matrix)

    result <- list(
        roe = roe_matrix,
        observed = as.matrix(observed),
        expected = expected,
        counts = obs_table,
        statistics = stats,
        method = method,
        n_cells = total_cells,
        n_groups = length(unique(df$group)),
        n_cell_types = length(unique(df$cell_type))
    )

    class(result) <- "roe_result"
    return(result)
}

#' @title Calculate Ro/e Statistics
#' @description Calculate statistical significance for Ro/e values
#' @param count_table Contingency table of cell types vs groups
#' @param roe_matrix Ro/e matrix
#' @return List of statistical test results
#' @keywords internal
calculate_roe_stats <- function(count_table, roe_matrix) {
    n_rows <- nrow(count_table)
    n_cols <- ncol(count_table)

    # Chi-square test for overall association (skip if degenerate)
    if (n_rows >= 2 && n_cols >= 2) {
        chi_test <- chisq.test(count_table)
    } else {
        chi_test <- list(
            statistic = NA,
            p.value = NA,
            method = "Skipped (single cell type or single group)"
        )
    }

    # Per-cell-type statistical tests
    fisher_results <- list()
    cell_types <- rownames(count_table)

    for (ct in cell_types) {
        # Create 2xk table for this cell type vs others
        ct_row <- count_table[ct, , drop = FALSE]
        other_row <- colSums(count_table[rownames(count_table) != ct, , drop = FALSE])
        ct_table <- rbind(ct_row, other = other_row)

        if (ncol(ct_table) < 2) {
            fisher_results[[ct]] <- list(
                test = list(p.value = NA),
                std_residuals = NA,
                p_value = NA
            )
            next
        }

        # Get standardized residuals from chi-square test (always available)
        chi_res <- chisq.test(ct_table)
        std_residuals <- chi_res$stdres[1, ]

        # Choose test for p-value: Fisher for 2-group tables, chi-square otherwise
        if (ncol(ct_table) == 2) {
            test <- fisher.test(ct_table)
            p_value <- test$p.value
        } else {
            test <- chi_res
            p_value <- chi_res$p.value
        }

        fisher_results[[ct]] <- list(
            test = test,
            std_residuals = std_residuals,
            p_value = p_value
        )
    }

    # Adjust p-values (Benjamini-Hochberg)
    p_values <- sapply(fisher_results, function(x) x$p_value)
    p_values[is.na(p_values)] <- 1
    adj_p_values <- p.adjust(p_values, method = "BH")

    for (i in seq_along(fisher_results)) {
        fisher_results[[i]]$p_value_adj <- adj_p_values[i]
        fisher_results[[i]]$significant <- adj_p_values[i] < 0.05
    }

    list(
        chi_square = chi_test,
        per_cell_type = fisher_results,
        overall_p = chi_test$p.value
    )
}

#' @title Calculate Ro/e with Confidence Intervals
#' @description Bootstrap-based Ro/e calculation with confidence intervals
#' @param cell_types Vector of cell type annotations
#' @param groups Vector of group assignments
#' @param n_bootstrap Number of bootstrap iterations (default: 1000)
#' @param conf_level Confidence level (default: 0.95)
#' @param seed Random seed for reproducibility (default: NULL, no seed set)
#' @return Ro/e result with confidence intervals
#' @export
calculate_roe_bootstrap <- function(
    cell_types,
    groups,
    n_bootstrap = 1000,
    conf_level = 0.95,
    seed = NULL
) {
    # Clean input data (match calculate_roe NA handling)
    valid_mask <- !is.na(cell_types) & !is.na(groups)
    cell_types_clean <- as.character(cell_types)[valid_mask]
    groups_clean <- as.character(groups)[valid_mask]

    # Calculate base Ro/e on cleaned data
    base_result <- calculate_roe(cell_types_clean, groups_clean)

    n_cells <- length(cell_types_clean)
    boot_roe <- array(0, dim = c(nrow(base_result$roe),
                                  ncol(base_result$roe),
                                  n_bootstrap),
                      dimnames = c(dimnames(base_result$roe), list(NULL)))

    # Bootstrap sampling
    if (!is.null(seed)) set.seed(seed)
    for (i in 1:n_bootstrap) {
        # Sample cells with replacement within each group
        boot_indices <- unlist(tapply(1:n_cells, groups_clean, function(idx) {
            sample(idx, length(idx), replace = TRUE)
        }))

        boot_result <- calculate_roe(
            cell_types_clean[boot_indices],
            groups_clean[boot_indices],
            method = base_result$method
        )

        boot_roe[, , i] <- boot_result$roe
    }

    # Calculate confidence intervals
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

#' @title Compare Ro/e Across Multiple Conditions
#' @description Calculate Ro/e for complex experimental designs
#' @param seurat_obj Seurat object with cell type and metadata
#' @param cell_type_col Column name for cell types
#' @param group_col Column name for primary grouping
#' @param subset_col Optional column for subsetting (e.g., tissue regions)
#' @param method Calculation method
#' @return List of roe_result objects or combined result
#' @export
run_roe_analysis <- function(
    seurat_obj,
    cell_type_col = "cell_type",
    group_col = "condition",
    subset_col = NULL,
    method = "group"
) {
    if (!inherits(seurat_obj, "Seurat")) {
        stop("Input must be a Seurat object")
    }

    # Extract metadata
    meta <- seurat_obj[[]]

    # Check columns exist
    if (!cell_type_col %in% colnames(meta)) {
        stop(paste("Cell type column not found:", cell_type_col))
    }
    if (!group_col %in% colnames(meta)) {
        stop(paste("Group column not found:", group_col))
    }

    cell_types <- meta[[cell_type_col]]
    groups <- meta[[group_col]]

    # Handle subsetting
    if (!is.null(subset_col)) {
        if (!subset_col %in% colnames(meta)) {
            stop(paste("Subset column not found:", subset_col))
        }

        subsets <- unique(meta[[subset_col]])
        results <- list()

        for (sub in subsets) {
            mask <- meta[[subset_col]] == sub
            result <- calculate_roe(
                cell_types[mask],
                groups[mask],
                method = method
            )
            results[[sub]] <- result
        }

        results$combined <- calculate_roe(cell_types, groups, method = method)
        results$cell_type_col <- cell_type_col
        results$group_col <- group_col
        results$subset_col <- subset_col

        class(results) <- "roe_multi_result"
        return(results)
    }

    # Single analysis
    result <- calculate_roe(cell_types, groups, method = method)
    result$cell_type_col <- cell_type_col
    result$group_col <- group_col

    return(result)
}

#' @title Print Ro/e Result
#' @description Print method for roe_result objects
#' @param x roe_result object
#' @param ... Additional arguments
#' @export
print.roe_result <- function(x, ...) {
    cat("Ro/e Differential Abundance Analysis\n")
    cat("=====================================\n")
    cat("Method:", x$method, "\n")
    cat("Total cells:", format(x$n_cells, big.mark = ","), "\n")
    cat("Groups:", x$n_groups, "\n")
    cat("Cell types:", x$n_cell_types, "\n\n")

    cat("Ro/e Matrix:\n")
    print(round(x$roe, 3))

    cat("\nStatistics:\n")
    cat("  Overall Chi-square p-value:", format.pval(x$statistics$overall_p), "\n")
    cat("  Significant cell types (FDR < 0.05):",
        sum(sapply(x$statistics$per_cell_type, function(y) y$significant)), "\n")

    if (!is.null(x$bootstrap)) {
        cat("\nBootstrap CI:", x$bootstrap$conf_level * 100, "%\n")
    }
}

#' @title Extract Ro/e as Data Frame
#' @description Convert Ro/e result to tidy data frame
#' @param roe_result Result from calculate_roe()
#' @return Tidy data frame
#' @export
roe_to_dataframe <- function(roe_result) {
    if (!inherits(roe_result, "roe_result")) {
        stop("Input must be a roe_result object")
    }

    # Melt Ro/e matrix
    roe_df <- as.data.frame(as.table(roe_result$roe))
    colnames(roe_df) <- c("cell_type", "group", "roe")

    # Add observed proportions
    obs_df <- as.data.frame(as.table(roe_result$observed))
    colnames(obs_df) <- c("cell_type", "group", "observed_prop")

    # Add expected proportions
    exp_df <- data.frame(
        cell_type = names(roe_result$expected),
        expected_prop = roe_result$expected,
        stringsAsFactors = FALSE
    )

    # Merge
    result <- merge(roe_df, obs_df, by = c("cell_type", "group"))
    result <- merge(result, exp_df, by = "cell_type")

    # Add p-values
    p_values <- sapply(roe_result$statistics$per_cell_type, function(x) x$p_value)
    p_adj_values <- sapply(roe_result$statistics$per_cell_type, function(x) x$p_value_adj)
    sig_values <- sapply(roe_result$statistics$per_cell_type, function(x) x$significant)

    sig_df <- data.frame(
        cell_type = names(p_values),
        p_value = p_values,
        p_value_adj = p_adj_values,
        significant = sig_values,
        stringsAsFactors = FALSE
    )

    result <- merge(result, sig_df, by = "cell_type")

    # Add bootstrap CI if available
    if (!is.null(roe_result$bootstrap)) {
        ci_lower <- as.data.frame(as.table(roe_result$bootstrap$ci_lower))
        ci_upper <- as.data.frame(as.table(roe_result$bootstrap$ci_upper))
        roe_sd <- as.data.frame(as.table(roe_result$bootstrap$roe_sd))

        colnames(ci_lower) <- c("cell_type", "group", "ci_lower")
        colnames(ci_upper) <- c("cell_type", "group", "ci_upper")
        colnames(roe_sd) <- c("cell_type", "group", "roe_sd")

        result <- merge(result, ci_lower, by = c("cell_type", "group"))
        result <- merge(result, ci_upper, by = c("cell_type", "group"))
        result <- merge(result, roe_sd, by = c("cell_type", "group"))
    }

    # Order by cell type and group
    result <- result[order(result$cell_type, result$group), ]
    rownames(result) <- NULL

    return(result)
}
