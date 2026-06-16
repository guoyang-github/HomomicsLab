# Ro/e Visualization Functions
# Including heatmap, lollipop, and dot plots

#' @title Plot Ro/e Heatmap
#' @description Create a heatmap visualization of Ro/e values
#' @param roe_result Result from calculate_roe()
#' @param cluster_rows Whether to cluster rows (default: TRUE)
#' @param cluster_cols Whether to cluster columns (default: FALSE)
#' @param color_scale Color scale: "diverging" (default) or "sequential"
#' @param value_text_size Size of value text (0 to hide)
#' @param title Plot title
#' @return ggplot object or pheatmap object
#' @export
plot_roe_heatmap <- function(
    roe_result,
    cluster_rows = TRUE,
    cluster_cols = FALSE,
    color_scale = "diverging",
    value_text_size = 3,
    title = "Ro/e Differential Abundance"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    # Convert to data frame
    roe_df <- roe_to_dataframe(roe_result)

    # Create base heatmap with ggplot2
    p <- ggplot2::ggplot(roe_df, ggplot2::aes(x = group, y = cell_type, fill = roe)) +
        ggplot2::geom_tile(color = "white", linewidth = 0.5) +
        ggplot2::scale_fill_gradient2(
            low = "#2166ac",      # Blue for depleted
            mid = "white",        # White for neutral
            high = "#b2182b",     # Red for enriched
            midpoint = 1,
            limits = {
                roe_max <- max(roe_df$roe, na.rm = TRUE)
                c(0, if (roe_max < 1) 1.5 else max(3, roe_max))
            },
            na.value = "grey80",
            name = "Ro/e"
        ) +
        ggplot2::labs(
            title = title,
            x = "Group",
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

    # Add value text if requested
    if (value_text_size > 0) {
        p <- p + ggplot2::geom_text(
            ggplot2::aes(label = sprintf("%.2f", roe)),
            size = value_text_size,
            color = ifelse(roe_df$roe > 1.5, "white", "black")
        )
    }

    return(p)
}

#' @title Plot Ro/e Lollipop Chart
#' @description Create a lollipop chart for Ro/e visualization
#' Best for comparing a single group vs reference or showing fold changes
#' @param roe_result Result from calculate_roe()
#' @param compare_group Which group to highlight (if NULL, plots all)
#' @param reference_group Reference group name (for calculating fold change)
#' @param highlight_sig Whether to highlight significant results (default: TRUE)
#' @param sig_threshold FDR threshold for significance (default: 0.05)
#' @param min_roe Minimum Ro/e to display (default: 0)
#' @param title Plot title
#' @param color_by_depletion Color depleted cell types differently (default: TRUE)
#' @return ggplot object
#' @export
plot_roe_lollipop <- function(
    roe_result,
    compare_group = NULL,
    reference_group = NULL,
    highlight_sig = TRUE,
    sig_threshold = 0.05,
    min_roe = 0,
    title = "Ro/e Cell Type Enrichment",
    color_by_depletion = TRUE
) {
    if (!requireNamespace("ggplot2", quietly = TRUE) ||
        !requireNamespace("dplyr", quietly = TRUE)) {
        stop("Please install ggplot2 and dplyr")
    }

    # Convert to data frame
    roe_df <- roe_to_dataframe(roe_result)

    # Filter if specific group requested
    if (!is.null(compare_group)) {
        roe_df <- roe_df[roe_df$group == compare_group, ]
    }

    # Filter by min Ro/e
    roe_df <- roe_df[roe_df$roe >= min_roe, ]

    # Sort by Ro/e value
    roe_df <- roe_df[order(roe_df$roe), ]
    roe_df$cell_type <- factor(roe_df$cell_type, levels = unique(roe_df$cell_type))

    # Create color scheme
    if (color_by_depletion) {
        roe_df$category <- dplyr::case_when(
            roe_df$roe > 1 ~ "Enriched",
            roe_df$roe < 1 ~ "Depleted",
            TRUE ~ "Neutral"
        )
        fill_colors <- c("Enriched" = "#b2182b", "Depleted" = "#2166ac", "Neutral" = "grey60")
    } else {
        roe_df$category <- "All"
        fill_colors <- c("All" = "#d6604d")
    }

    # Add significance indicator
    if (highlight_sig) {
        roe_df$shape <- ifelse(roe_df$significant, 21, 4)  # Filled circle vs X
    } else {
        roe_df$shape <- 21
    }

    # Base plot
    p <- ggplot2::ggplot(roe_df, ggplot2::aes(x = cell_type, y = roe)) +
        # Reference line at Ro/e = 1 (no enrichment)
        ggplot2::geom_hline(yintercept = 1, linetype = "dashed",
                           color = "grey50", linewidth = 0.5) +
        # Lollipops
        ggplot2::geom_segment(
            ggplot2::aes(x = cell_type, xend = cell_type,
                        y = 1, yend = roe),
            color = "grey70", linewidth = 0.5
        ) +
        ggplot2::geom_point(
            ggplot2::aes(fill = category, shape = shape, size = observed_prop),
            color = "black"
        ) +
        # Scale shapes
        ggplot2::scale_shape_identity() +
        # Colors
        ggplot2::scale_fill_manual(values = fill_colors, name = "Category") +
        ggplot2::scale_size_continuous(name = "Proportion", range = c(2, 8)) +
        # Labels
        ggplot2::labs(
            title = title,
            subtitle = if (!is.null(compare_group)) paste("Group:", compare_group) else NULL,
            x = "Cell Type",
            y = "Ro/e (Observed/Expected)",
            caption = if (highlight_sig) "● = FDR < 0.05, ✕ = not significant" else NULL
        ) +
        # Theme
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text.x = ggplot2::element_text(angle = 45, hjust = 1, size = 10),
            axis.text.y = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5),
            plot.subtitle = ggplot2::element_text(size = 11, hjust = 0.5),
            panel.grid.major.x = ggplot2::element_blank(),
            panel.grid.minor = ggplot2::element_blank(),
            legend.position = "right"
        ) +
        # Y-axis starts at 0
        ggplot2::coord_flip() +
        ggplot2::scale_y_continuous(
            breaks = c(0, 0.5, 1, 1.5, 2, 2.5, 3),
            limits = c(0, max(3, max(roe_df$roe, na.rm = TRUE)))
        )

    return(p)
}

#' @title Plot Ro/e Dot Plot
#' @description Create a dot plot showing Ro/e and significance
#' @param roe_result Result from calculate_roe()
#' @param size_by Size dots by "proportion" or "counts" (default: "proportion")
#' @param color_scale Color by Ro/e value or significance
#' @param title Plot title
#' @return ggplot object
#' @export
plot_roe_dotplot <- function(
    roe_result,
    size_by = "proportion",
    color_scale = "roe",
    title = "Ro/e Cell Type Enrichment"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    roe_df <- roe_to_dataframe(roe_result)

    # Determine size aesthetic
    if (size_by == "proportion") {
        size_aes <- ggplot2::aes(size = observed_prop)
        size_name <- "Observed\nProportion"
    } else {
        # Get counts from original table
        counts <- as.data.frame(as.table(roe_result$counts))
        colnames(counts) <- c("cell_type", "group", "count")
        roe_df <- merge(roe_df, counts, by = c("cell_type", "group"))
        size_aes <- ggplot2::aes(size = count)
        size_name <- "Cell Count"
    }

    # Determine color aesthetic
    if (color_scale == "roe") {
        color_aes <- ggplot2::aes(color = roe)
        color_scale_obj <- ggplot2::scale_color_gradient2(
            low = "#2166ac",
            mid = "white",
            high = "#b2182b",
            midpoint = 1,
            name = "Ro/e"
        )
    } else {
        roe_df$sig_label <- ifelse(roe_df$significant,
                                    paste0("FDR < ", 0.05),
                                    "n.s.")
        color_aes <- ggplot2::aes(color = sig_label)
        color_scale_obj <- ggplot2::scale_color_manual(
            values = c(`FDR < 0.05` = "#b2182b", `n.s.` = "grey60"),
            name = "Significance"
        )
    }

    p <- ggplot2::ggplot(roe_df, ggplot2::aes(x = group, y = cell_type)) +
        ggplot2::geom_point(mapping = modifyList(size_aes, color_aes)) +
        color_scale_obj +
        ggplot2::scale_size_continuous(name = size_name, range = c(2, 10)) +
        ggplot2::labs(
            title = title,
            x = "Group",
            y = "Cell Type"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text.x = ggplot2::element_text(angle = 45, hjust = 1, size = 11),
            axis.text.y = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5),
            panel.grid.major = ggplot2::element_line(color = "grey90"),
            panel.grid.minor = ggplot2::element_blank()
        )

    return(p)
}

#' @title Plot Ro/e Bar Chart
#' @description Create a grouped bar chart of observed vs expected proportions
#' @param roe_result Result from calculate_roe()
#' @param show_expected Whether to show expected proportion line
#' @param title Plot title
#' @return ggplot object
#' @export
plot_roe_bar <- function(
    roe_result,
    show_expected = TRUE,
    title = "Observed vs Expected Cell Type Proportions"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    roe_df <- roe_to_dataframe(roe_result)

    # Create expected reference line data
    if (show_expected) {
        exp_lines <- unique(roe_df[, c("cell_type", "expected_prop")])
    }

    p <- ggplot2::ggplot(roe_df, ggplot2::aes(x = cell_type, y = observed_prop, fill = group)) +
        ggplot2::geom_bar(stat = "identity", position = "dodge", width = 0.7) +
        ggplot2::scale_fill_brewer(palette = "Set1", name = "Group") +
        ggplot2::labs(
            title = title,
            x = "Cell Type",
            y = "Proportion"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text.x = ggplot2::element_text(angle = 45, hjust = 1, size = 10),
            axis.text.y = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5),
            legend.position = "right"
        )

    # Add expected reference segment per cell type
    if (show_expected) {
        exp_lines$cell_type <- factor(exp_lines$cell_type, levels = unique(roe_df$cell_type))
        p <- p + ggplot2::geom_segment(
            data = exp_lines,
            ggplot2::aes(
                x = as.numeric(cell_type) - 0.35,
                xend = as.numeric(cell_type) + 0.35,
                y = expected_prop,
                yend = expected_prop
            ),
            linetype = "dashed",
            color = "grey40",
            alpha = 0.7
        )
    }

    return(p)
}

#' @title Plot Multi-Group Comparison
#' @description Create a faceted plot for complex designs
#' @param roe_multi_result Result from run_roe_analysis with subsets
#' @param plot_type Type of plot: "lollipop", "heatmap", or "dot"
#' @param title Plot title
#' @return ggplot object or list of plots
#' @export
plot_roe_multi <- function(
    roe_multi_result,
    plot_type = "lollipop",
    title = "Ro/e by Subset"
) {
    if (!inherits(roe_multi_result, "roe_multi_result")) {
        stop("Input must be a roe_multi_result object from run_roe_analysis with subset_col")
    }

    plots <- list()
    subsets <- setdiff(names(roe_multi_result),
                       c("combined", "cell_type_col", "group_col", "subset_col"))

    for (sub in subsets) {
        sub_title <- paste(title, "-", sub)

        p <- switch(plot_type,
            "lollipop" = plot_roe_lollipop(roe_multi_result[[sub]], title = sub_title),
            "heatmap" = plot_roe_heatmap(roe_multi_result[[sub]], title = sub_title),
            "dot" = plot_roe_dotplot(roe_multi_result[[sub]], title = sub_title),
            stop("Unknown plot type")
        )

        plots[[sub]] <- p
    }

    # Return combined plot if possible
    if (length(plots) > 1 && requireNamespace("patchwork", quietly = TRUE)) {
        combined <- patchwork::wrap_plots(plots, ncol = min(2, length(plots))) +
            patchwork::plot_annotation(title = title)
        return(combined)
    }

    return(plots)
}

#' @title Save Ro/e Plot
#' @description Save Ro/e visualization to file
#' @param plot ggplot object
#' @param filename Output filename
#' @param width Width in inches (default: 8)
#' @param height Height in inches (default: 6)
#' @param dpi DPI for raster formats (default: 300)
#' @export
save_roe_plot <- function(plot, filename, width = 8, height = 6, dpi = 300) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    ext <- tolower(tools::file_ext(filename))

    if (ext %in% c("png", "jpg", "jpeg", "tiff")) {
        ggplot2::ggsave(filename, plot, width = width, height = height, dpi = dpi)
    } else {
        ggplot2::ggsave(filename, plot, width = width, height = height)
    }

    message(paste("Plot saved to:", filename))
}
