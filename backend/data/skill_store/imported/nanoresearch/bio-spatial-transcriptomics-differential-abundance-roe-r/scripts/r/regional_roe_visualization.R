# Regional Ro/e Visualization Functions
# Specialized visualizations for cell type regional enrichment

#' @title Plot Regional Ro/e Heatmap
#' @description Create a heatmap of regional cell type enrichment
#' @param regional_roe_result Result from calculate_regional_roe()
#' @param cluster_rows Whether to cluster rows (default: TRUE)
#' @param cluster_cols Whether to cluster columns (default: FALSE)
#' @param show_values Whether to show Ro/e values (default: TRUE)
#' @param value_size Text size for values (default: 3)
#' @param title Plot title
#' @param highlight_sig Whether to highlight significant cells (default: TRUE)
#' @return ggplot object
#' @export
plot_regional_roe_heatmap <- function(
    regional_roe_result,
    cluster_rows = TRUE,
    cluster_cols = FALSE,
    show_values = TRUE,
    value_size = 3,
    title = "Regional Cell Type Enrichment (Ro/e)",
    highlight_sig = TRUE
) {
    if (!requireNamespace("ggplot2", quietly = TRUE) ||
        !requireNamespace("reshape2", quietly = TRUE)) {
        stop("Please install ggplot2 and reshape2")
    }

    # Extract data
    roe_mat <- regional_roe_result$roe
    sig_mat <- regional_roe_result$statistics$significant

    # Clustering
    if (cluster_rows && nrow(roe_mat) > 1) {
        row_order <- order.dendrogram(as.dendrogram(hclust(dist(roe_mat))))
        roe_mat <- roe_mat[row_order, , drop = FALSE]
        sig_mat <- sig_mat[row_order, , drop = FALSE]
    }

    if (cluster_cols && ncol(roe_mat) > 1) {
        col_order <- order.dendrogram(as.dendrogram(hclust(dist(t(roe_mat)))))
        roe_mat <- roe_mat[, col_order, drop = FALSE]
        sig_mat <- sig_mat[, col_order, drop = FALSE]
    }

    # Melt
    roe_df <- reshape2::melt(roe_mat)
    colnames(roe_df) <- c("cell_type", "region", "roe")

    sig_df <- reshape2::melt(sig_mat)
    roe_df$significant <- sig_df$value

    # Text color
    roe_df$text_color <- ifelse(roe_df$roe > 1.5, "white", "black")

    # Create plot
    p <- ggplot2::ggplot(roe_df, ggplot2::aes(x = region, y = cell_type, fill = roe)) +
        ggplot2::geom_tile(color = "white", size = 0.5) +
        ggplot2::scale_fill_gradient2(
            low = "#2166ac",
            mid = "white",
            high = "#b2182b",
            midpoint = 1,
            limits = c(0, max(3, max(roe_df$roe, na.rm = TRUE))),
            na.value = "grey80",
            name = "Ro/e"
        ) +
        ggplot2::labs(
            title = title,
            x = "Anatomical Region",
            y = "Cell Type"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text.x = ggplot2::element_text(angle = 45, hjust = 1, size = 11),
            axis.text.y = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5),
            panel.grid = ggplot2::element_blank(),
            legend.position = "right"
        )

    # Add significance indicators
    if (highlight_sig && any(roe_df$significant, na.rm = TRUE)) {
        sig_points <- roe_df[roe_df$significant & !is.na(roe_df$significant), ]
        if (nrow(sig_points) > 0) {
            p <- p + ggplot2::geom_point(
                data = sig_points,
                ggplot2::aes(x = region, y = cell_type),
                shape = "*", size = 6, color = "black"
            )
        }
    }

    # Add value text
    if (show_values) {
        p <- p + ggplot2::geom_text(
            ggplot2::aes(label = sprintf("%.2f", roe)),
            color = roe_df$text_color,
            size = value_size
        )
    }

    return(p)
}

#' @title Plot Regional Ro/e Lollipop
#' @description Create lollipop plot for a specific region
#' @param regional_roe_result Result from calculate_regional_roe()
#' @param region Which region to plot (if NULL, plots all as facets)
#' @param n_top Number of top cell types to show (default: all)
#' @param highlight_sig Whether to highlight significant results (default: TRUE)
#' @param title Plot title
#' @return ggplot object
#' @export
plot_regional_roe_lollipop <- function(
    regional_roe_result,
    region = NULL,
    n_top = NULL,
    highlight_sig = TRUE,
    title = "Cell Type Enrichment"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    # Convert to data frame
    roe_df <- regional_roe_to_dataframe(regional_roe_result)

    # Filter by region if specified
    if (!is.null(region)) {
        roe_df <- roe_df[roe_df$region == region, ]
        subtitle <- paste("Region:", region)
    } else {
        subtitle <- NULL
    }

    # Sort and filter
    roe_df <- roe_df[order(roe_df$roe), ]
    if (!is.null(n_top)) {
        roe_df <- tail(roe_df, n_top)
    }

    roe_df$cell_type <- factor(roe_df$cell_type, levels = roe_df$cell_type)

    # Colors
    roe_df$color <- ifelse(roe_df$roe > 1, "#b2182b",
                          ifelse(roe_df$roe < 1, "#2166ac", "grey60"))

    # Create plot
    p <- ggplot2::ggplot(roe_df, ggplot2::aes(x = cell_type, y = roe)) +
        ggplot2::geom_hline(yintercept = 1, linetype = "dashed", color = "grey50") +
        ggplot2::geom_segment(
            ggplot2::aes(x = cell_type, xend = cell_type, y = 1, yend = roe),
            color = "grey70", linewidth = 0.5
        ) +
        ggplot2::geom_point(
            ggplot2::aes(size = observed, color = color),
            alpha = 0.8
        ) +
        ggplot2::scale_color_identity() +
        ggplot2::scale_size_continuous(name = "Observed\nProportion", range = c(3, 10)) +
        ggplot2::coord_flip() +
        ggplot2::labs(
            title = title,
            subtitle = subtitle,
            x = "Cell Type",
            y = "Ro/e (Observed/Expected)"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5),
            panel.grid.major.y = ggplot2::element_blank()
        )

    return(p)
}

#' @title Plot Stacked Regional Composition
#' @description Create stacked bar chart showing cell type composition per region
#' @param regional_roe_result Result from calculate_regional_roe()
#' @param normalize Whether to normalize to 100% per region (default: TRUE)
#' @param n_highlight Number of top cell types to highlight (default: 8)
#' @param title Plot title
#' @return ggplot object
#' @export
plot_regional_composition <- function(
    regional_roe_result,
    normalize = TRUE,
    n_highlight = 8,
    title = "Cell Type Composition by Region"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE) ||
        !requireNamespace("reshape2", quietly = TRUE)) {
        stop("Please install ggplot2 and reshape2")
    }

    # Get observed proportions
    obs <- regional_roe_result$observed

    if (normalize) {
        obs <- prop.table(obs, margin = 2) * 100
    }

    # Melt
    comp_df <- reshape2::melt(obs)
    colnames(comp_df) <- c("cell_type", "region", "proportion")

    # Select top cell types by mean proportion
    mean_props <- rowMeans(regional_roe_result$observed)
    top_types <- names(sort(mean_props, decreasing = TRUE))[1:min(n_highlight, length(mean_props))]

    # Group others
    comp_df$cell_type_grouped <- ifelse(
        comp_df$cell_type %in% top_types,
        as.character(comp_df$cell_type),
        "Other"
    )

    # Aggregate
    comp_agg <- aggregate(proportion ~ cell_type_grouped + region, data = comp_df, sum)

    # Order cell types
    type_order <- c(top_types, "Other")
    comp_agg$cell_type_grouped <- factor(comp_agg$cell_type_grouped, levels = type_order)

    # Colors
    n_types <- length(type_order)
    colors <- c(RColorBrewer::brewer.pal(min(n_types - 1, 8), "Set3"), "grey80")

    # Create plot
    p <- ggplot2::ggplot(comp_agg, ggplot2::aes(x = region, y = proportion, fill = cell_type_grouped)) +
        ggplot2::geom_bar(stat = "identity", position = "stack", width = 0.7) +
        ggplot2::scale_fill_manual(name = "Cell Type", values = colors) +
        ggplot2::labs(
            title = title,
            x = "Region",
            y = ifelse(normalize, "Percentage (%)", "Proportion")
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text.x = ggplot2::element_text(angle = 45, hjust = 1, size = 11),
            axis.text.y = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5),
            legend.position = "right"
        )

    return(p)
}

#' @title Plot Regional Specificity
#' @description Plot cell type regional specificity scores
#' @param specificity_df Result from calculate_regional_specificity()
#' @param title Plot title
#' @return ggplot object
#' @export
plot_regional_specificity <- function(
    specificity_df,
    title = "Cell Type Regional Specificity"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    # Sort by specificity score
    specificity_df <- specificity_df[order(specificity_df$specificity_score), ]
    specificity_df$cell_type <- factor(specificity_df$cell_type,
                                       levels = specificity_df$cell_type)

    # Colors for patterns
    pattern_colors <- c(
        "Highly Regional" = "#b2182b",
        "Moderately Regional" = "#ef8a62",
        "Variable" = "#999999",
        "Ubiquitous" = "#2166ac"
    )

    p <- ggplot2::ggplot(specificity_df, ggplot2::aes(x = cell_type, y = specificity_score)) +
        ggplot2::geom_bar(stat = "identity",
                          ggplot2::aes(fill = pattern),
                          width = 0.7) +
        ggplot2::scale_fill_manual(name = "Pattern", values = pattern_colors) +
        ggplot2::coord_flip() +
        ggplot2::labs(
            title = title,
            x = "Cell Type",
            y = "Specificity Score"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5)
        )

    return(p)
}

#' @title Plot Multi-Region Comparison
#' @description Create faceted lollipop plots for all regions
#' @param regional_roe_result Result from calculate_regional_roe()
#' @param n_top Number of top cell types per region (default: 10)
#' @param title Plot title
#' @return ggplot object or list
#' @export
plot_regional_comparison <- function(
    regional_roe_result,
    n_top = 10,
    title = "Cell Type Enrichment Across Regions"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE) ||
        !requireNamespace("dplyr", quietly = TRUE)) {
        stop("Please install ggplot2 and dplyr")
    }

    roe_df <- regional_roe_to_dataframe(regional_roe_result)

    # Get top cell types per region
    top_df <- roe_df %>%
        dplyr::group_by(region) %>%
        dplyr::top_n(n_top, roe) %>%
        dplyr::ungroup()

    # Create faceted plot
    p <- ggplot2::ggplot(top_df, ggplot2::aes(x = reorder(cell_type, roe), y = roe)) +
        ggplot2::geom_hline(yintercept = 1, linetype = "dashed", color = "grey50") +
        ggplot2::geom_segment(
            ggplot2::aes(x = cell_type, xend = cell_type, y = 1, yend = roe),
            color = "grey70"
        ) +
        ggplot2::geom_point(
            ggplot2::aes(color = roe > 1, size = observed),
            alpha = 0.8
        ) +
        ggplot2::scale_color_manual(values = c("TRUE" = "#b2182b", "FALSE" = "#2166ac"),
                                    guide = "none") +
        ggplot2::scale_size_continuous(name = "Observed\nProportion") +
        ggplot2::coord_flip() +
        ggplot2::facet_wrap(~region, ncol = 2, scales = "free_y") +
        ggplot2::labs(
            title = title,
            x = "Cell Type",
            y = "Ro/e"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            strip.text = ggplot2::element_text(size = 11, face = "bold"),
            axis.text = ggplot2::element_text(size = 9),
            panel.spacing = ggplot2::unit(1, "lines")
        )

    return(p)
}

#' @title Plot Condition Comparison (for differential analysis)
#' @description Compare regional Ro/e between two conditions
#' @param comparison_result Result from compare_regional_roe()
#' @param plot_type Type of plot: "heatmap", "scatter", or "bar"
#' @param title Plot title
#' @return ggplot object
#' @export
plot_regional_condition_comparison <- function(
    comparison_result,
    plot_type = "heatmap",
    title = "Condition Comparison: Regional Enrichment"
) {
    if (!inherits(comparison_result, "regional_roe_comparison") ||
        is.null(comparison_result$differential)) {
        stop("Input must be a comparison result with differential data")
    }

    diff_roe <- comparison_result$differential$diff_roe
    cond1 <- comparison_result$differential$condition_1
    cond2 <- comparison_result$differential$condition_2

    if (plot_type == "heatmap") {
        # Melt difference matrix
        diff_df <- reshape2::melt(diff_roe)
        colnames(diff_df) <- c("cell_type", "region", "diff")

        p <- ggplot2::ggplot(diff_df, ggplot2::aes(x = region, y = cell_type, fill = diff)) +
            ggplot2::geom_tile(color = "white") +
            ggplot2::scale_fill_gradient2(
                low = "#2166ac",
                mid = "white",
                high = "#b2182b",
                midpoint = 0,
                name = paste("Ro/e\nDifference\n", cond1, "-", cond2)
            ) +
            ggplot2::labs(
                title = title,
                subtitle = paste("Positive (red): Higher in", cond1,
                                "| Negative (blue): Higher in", cond2),
                x = "Region",
                y = "Cell Type"
            ) +
            ggplot2::theme_minimal() +
            ggplot2::theme(
                axis.text.x = ggplot2::element_text(angle = 45, hjust = 1),
                plot.title = ggplot2::element_text(face = "bold", hjust = 0.5)
            )

    } else if (plot_type == "scatter") {
        # Get Ro/e values for each condition
        roe1 <- comparison_result[[cond1]]$roe[rownames(diff_roe), colnames(diff_roe)]
        roe2 <- comparison_result[[cond2]]$roe[rownames(diff_roe), colnames(diff_roe)]

        scatter_df <- data.frame(
            roe1 = as.vector(roe1),
            roe2 = as.vector(roe2),
            cell_type = rep(rownames(roe1), ncol(roe1)),
            region = rep(colnames(roe1), each = nrow(roe1))
        )

        p <- ggplot2::ggplot(scatter_df, ggplot2::aes(x = roe2, y = roe1)) +
            ggplot2::geom_point(ggplot2::aes(color = region), alpha = 0.6, size = 3) +
            ggplot2::geom_abline(slope = 1, intercept = 0, linetype = "dashed") +
            ggplot2::labs(
                title = title,
                x = paste(cond2, "Ro/e"),
                y = paste(cond1, "Ro/e")
            ) +
            ggplot2::theme_minimal() +
            ggplot2::theme(plot.title = ggplot2::element_text(face = "bold", hjust = 0.5))

    } else {
        stop("Unknown plot_type: ", plot_type)
    }

    return(p)
}

#' @title Annotate Spatial Plot with Regions
#' @description Add region boundaries to spatial coordinate plot
#' @param coords Data frame with x, y coordinates
#' @param regions Vector of region labels
#' @param title Plot title
#' @param alpha Point transparency (default: 0.6)
#' @return ggplot object
#' @export
plot_spatial_regions <- function(
    coords,
    regions,
    title = "Spatial Regions",
    alpha = 0.6
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    plot_df <- data.frame(
        x = coords[, 1],
        y = coords[, 2],
        region = regions,
        stringsAsFactors = FALSE
    )

    # Get region colors
    n_regions <- length(unique(regions))
    if (n_regions <= 8) {
        colors <- RColorBrewer::brewer.pal(n_regions, "Set2")
    } else {
        colors <- rainbow(n_regions)
    }

    p <- ggplot2::ggplot(plot_df, ggplot2::aes(x = x, y = y, color = region)) +
        ggplot2::geom_point(size = 2, alpha = alpha) +
        ggplot2::scale_color_manual(name = "Region", values = colors) +
        ggplot2::coord_fixed() +
        ggplot2::labs(
            title = title,
            x = "X",
            y = "Y"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            plot.title = ggplot2::element_text(face = "bold", hjust = 0.5),
            legend.position = "right"
        )

    return(p)
}
