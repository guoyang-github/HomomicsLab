#' STARTRAC Visualization Functions
#'
#' This file contains visualization functions for STARTRAC analysis results.
#' Includes bar plots, heatmaps, and network visualizations.
#'
#' @author Based on STARTRAC package
#' @references https://github.com/Japrin/STARTRAC

#' Plot Complete STARTRAC Results
#'
#' Generate a comprehensive set of plots for STARTRAC analysis results.
#'
#' @param result A StartracOut object
#' @param output_prefix Prefix for output file names (default: "startrac")
#' @param plot_types Vector of plot types to generate
#'   Options: "expansion", "migration", "transition", "all" (default: "all")
#' @param byPatient Logical; plot by patient if available (default: FALSE)
#' @param width Plot width in inches (default: 10)
#' @param height Plot height in inches (default: 8)
#'
#' @return Invisible list of ggplot objects
#'
#' @examples
#' \dontrun{
#' plot_startrac_results(result, output_prefix = "analysis/startrac")
#' }
plot_startrac_results <- function(result,
                                   output_prefix = "startrac",
                                   plot_types = "all",
                                   byPatient = FALSE,
                                   width = 10,
                                   height = 8) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    # Check required packages
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("ggplot2 package is required")
    }

    plots <- list()

    # Determine which plots to generate
    if ("all" %in% plot_types) {
        plot_types <- c("expansion", "migration", "transition")
    }

    # Cluster-level indices (expansion)
    if ("expansion" %in% plot_types) {
        message("Generating expansion plots...")
        plots$expansion <- plot_expansion_bar(result, byPatient = byPatient)
        if (!is.null(plots$expansion)) {
            ggsave(paste0(output_prefix, "_expansion.pdf"),
                   plots$expansion, width = width, height = height)
        }
    }

    # Migration heatmap
    if ("migration" %in% plot_types) {
        message("Generating migration plots...")
        plots$migration <- plot_migration_heatmap(result)
        if (!is.null(plots$migration)) {
            ggsave(paste0(output_prefix, "_migration.pdf"),
                   plots$migration, width = width, height = height)
        }
    }

    # Transition heatmap
    if ("transition" %in% plot_types) {
        message("Generating transition plots...")
        plots$transition <- plot_transition_heatmap(result)
        if (!is.null(plots$transition)) {
            ggsave(paste0(output_prefix, "_transition.pdf"),
                   plots$transition, width = width, height = height)
        }
    }

    message(sprintf("Plots saved with prefix: %s", output_prefix))
    invisible(plots)
}


#' Plot Expansion Index Bar Chart
#'
#' Create a bar plot of STARTRAC expansion index by cluster.
#'
#' @param result A StartracOut object
#' @param byPatient Logical; create boxplot by patient (default: FALSE)
#' @param color_palette Color palette for bars (default: "Set2")
#'
#' @return A ggplot object
#'
#' @examples
#' \dontrun{
#' p <- plot_expansion_bar(result)
#' print(p)
#' }
plot_expansion_bar <- function(result, byPatient = FALSE, color_palette = "Set2") {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    require(ggplot2)

    # Get cluster data
    dat <- result@cluster.data

    if (byPatient && nrow(result@cluster.sig.data) > 0) {
        # Use significance data which has per-patient info
        dat_plot <- result@cluster.sig.data %>%
            dplyr::filter(index == "expa", aid != result@proj)

        if (nrow(dat_plot) == 0) {
            message("No per-patient data available")
            return(NULL)
        }

        p <- ggplot(dat_plot, aes(x = majorCluster, y = value, fill = aid)) +
            geom_boxplot(outlier.shape = NA) +
            geom_jitter(position = position_dodge(width = 0.75), size = 1) +
            labs(x = "Cell Cluster", y = "Expansion Index",
                 title = "STARTRAC Expansion Index by Patient") +
            theme_bw() +
            theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
            scale_fill_brewer(palette = color_palette, name = "Patient")

    } else {
        # Simple bar plot of overall indices
        dat <- dat %>%
            dplyr::arrange(dplyr::desc(expa))

        p <- ggplot(dat, aes(x = reorder(majorCluster, expa), y = expa, fill = majorCluster)) +
            geom_bar(stat = "identity") +
            coord_flip() +
            labs(x = "Cell Cluster", y = "Expansion Index",
                 title = "STARTRAC Expansion Index by Cluster") +
            theme_bw() +
            theme(legend.position = "none") +
            scale_fill_brewer(palette = color_palette)
    }

    return(p)
}


#' Plot Migration Heatmap
#'
#' Create a heatmap of pairwise migration indices.
#'
#' @param result A StartracOut object
#' @param cluster_order Optional order of clusters for rows
#' @param color_low Color for low values (default: "white")
#' @param color_high Color for high values (default: "steelblue")
#'
#' @return A ggplot object or ComplexHeatmap object
#'
#' @examples
#' \dontrun{
#' p <- plot_migration_heatmap(result)
#' }
plot_migration_heatmap <- function(result,
                                   cluster_order = NULL,
                                   color_low = "white",
                                   color_high = "steelblue") {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    require(ggplot2)
    require(tidyr)
    require(dplyr)

    # Get migration data
    migr_data <- result@pIndex.migr

    if (nrow(migr_data) == 0) {
        message("No migration data available")
        return(NULL)
    }

    # Reshape for plotting
    migr_long <- migr_data %>%
        dplyr::select(-aid, -NCells) %>%
        tidyr::pivot_longer(cols = -majorCluster,
                            names_to = "tissue_pair",
                            values_to = "migr_index")

    # Order clusters if specified
    if (!is.null(cluster_order)) {
        migr_long$majorCluster <- factor(migr_long$majorCluster,
                                         levels = cluster_order)
    }

    p <- ggplot(migr_long, aes(x = tissue_pair, y = majorCluster, fill = migr_index)) +
        geom_tile() +
        scale_fill_gradient(low = color_low, high = color_high,
                            name = "Migration\nIndex") +
        labs(x = "Tissue Pair", y = "Cell Cluster",
             title = "STARTRAC Migration Index") +
        theme_bw() +
        theme(axis.text.x = element_text(angle = 45, hjust = 1))

    return(p)
}


#' Plot Transition Heatmap
#'
#' Create a heatmap of pairwise transition indices between clusters.
#'
#' @param result A StartracOut object
#' @param color_scale Color scale function (default: circlize::colorRamp2)
#' @param cluster_order Optional order of clusters
#'
#' @return A ComplexHeatmap object or ggplot object
#'
#' @examples
#' \dontrun{
#' p <- plot_transition_heatmap(result)
#' }
plot_transition_heatmap <- function(result,
                                    color_scale = NULL,
                                    cluster_order = NULL) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    if (!requireNamespace("ComplexHeatmap", quietly = TRUE)) {
        stop("ComplexHeatmap is required for plot_transition_heatmap(). Install with: BiocManager::install('ComplexHeatmap')")
    }
    if (!requireNamespace("circlize", quietly = TRUE)) {
        stop("circlize is required for plot_transition_heatmap(). Install with: install.packages('circlize')")
    }

    require(ComplexHeatmap)
    require(circlize)

    # Get transition data
    tran_data <- result@pIndex.tran

    if (nrow(tran_data) == 0) {
        message("No transition data available")
        return(NULL)
    }

    # Convert to matrix
    tran_matrix <- as.matrix(tran_data[, -c(1:3)])  # Remove aid, NCells, majorCluster
    rownames(tran_matrix) <- tran_data$majorCluster

    # Handle NA values
    tran_matrix[is.na(tran_matrix)] <- 0

    # Order if specified
    if (!is.null(cluster_order)) {
        tran_matrix <- tran_matrix[cluster_order, cluster_order, drop = FALSE]
    }

    # Default color scale
    if (is.null(color_scale)) {
        color_scale <- colorRamp2(
            c(0, max(tran_matrix, na.rm = TRUE) / 2, max(tran_matrix, na.rm = TRUE)),
            c("white", "yellow", "red")
        )
    }

    # Create heatmap
    ht <- Heatmap(
        tran_matrix,
        name = "Transition\nIndex",
        col = color_scale,
        cluster_rows = is.null(cluster_order),
        cluster_columns = is.null(cluster_order),
        row_title = "To Cluster",
        column_title = "From Cluster",
        heatmap_legend_param = list(title = "Transition Index")
    )

    return(ht)
}


#' Plot Migration Network
#'
#' Create a network visualization of migration patterns.
#'
#' @param result A StartracOut object
#' @param min_threshold Minimum index value to include edge (default: 0.1)
#' @param node_size Size of nodes (default: 20)
#'
#' @return A ggplot object
#'
#' @examples
#' \dontrun{
#' p <- plot_migration_network(result)
#' }
plot_migration_network <- function(result, min_threshold = 0.1, node_size = 20) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    if (!requireNamespace("igraph", quietly = TRUE)) {
        stop("igraph is required for plot_migration_network(). Install with: install.packages('igraph')")
    }
    if (!requireNamespace("ggraph", quietly = TRUE)) {
        stop("ggraph is required for plot_migration_network(). Install with: install.packages('ggraph')")
    }

    require(ggplot2)
    require(igraph)
    require(ggraph)

    # Get migration data
    migr_data <- result@pIndex.migr

    if (nrow(migr_data) == 0) {
        message("No migration data available")
        return(NULL)
    }

    # This is a simplified network plot
    # For a full implementation, would need tissue locations as nodes

    # Average migration index per cluster
    cluster_migr <- migr_data %>%
        dplyr::select(-aid, -NCells) %>%
        dplyr::rowwise() %>%
        dplyr::mutate(avg_migr = mean(dplyr::c_across(-majorCluster), na.rm = TRUE)) %>%
        dplyr::ungroup()

    p <- ggplot(cluster_migr, aes(x = reorder(majorCluster, avg_migr), y = avg_migr)) +
        geom_point(size = node_size / 2, color = "steelblue") +
        geom_segment(aes(x = majorCluster, xend = majorCluster, y = 0, yend = avg_migr),
                     color = "steelblue", alpha = 0.5) +
        coord_flip() +
        labs(x = "Cell Cluster", y = "Average Migration Index",
             title = "T Cell Migration Potential by Cluster") +
        theme_bw()

    return(p)
}


#' Plot Indices Comparison
#'
#' Compare expansion, migration, and transition indices in a multi-panel plot.
#'
#' @param result A StartracOut object
#' @param output_file Optional output file path
#'
#' @return A ggplot object (cowplot grid)
#'
#' @examples
#' \dontrun{
#' p <- plot_indices_comparison(result)
#' }
plot_indices_comparison <- function(result, output_file = NULL) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    if (!requireNamespace("cowplot", quietly = TRUE)) {
        stop("cowplot is required for plot_indices_comparison(). Install with: install.packages('cowplot')")
    }

    require(ggplot2)
    require(cowplot)
    require(tidyr)
    require(dplyr)

    # Get cluster data
    dat <- result@cluster.data %>%
        dplyr::select(majorCluster, expa, migr, tran, NCells) %>%
        tidyr::pivot_longer(cols = c(expa, migr, tran),
                            names_to = "index_type",
                            values_to = "value")

    # Create individual plots
    p_expa <- ggplot(dat %>% dplyr::filter(index_type == "expa"),
                     aes(x = reorder(majorCluster, value), y = value, fill = majorCluster)) +
        geom_bar(stat = "identity") +
        coord_flip() +
        labs(x = NULL, y = "Expansion", title = "Expansion Index") +
        theme_bw() +
        theme(legend.position = "none")

    p_migr <- ggplot(dat %>% dplyr::filter(index_type == "migr"),
                     aes(x = reorder(majorCluster, value), y = value, fill = majorCluster)) +
        geom_bar(stat = "identity") +
        coord_flip() +
        labs(x = NULL, y = "Migration", title = "Migration Index") +
        theme_bw() +
        theme(legend.position = "none")

    p_tran <- ggplot(dat %>% dplyr::filter(index_type == "tran"),
                     aes(x = reorder(majorCluster, value), y = value, fill = majorCluster)) +
        geom_bar(stat = "identity") +
        coord_flip() +
        labs(x = "Cell Cluster", y = "Transition", title = "Transition Index") +
        theme_bw() +
        theme(legend.position = "none")

    # Combine plots
    combined <- cowplot::plot_grid(p_expa, p_migr, p_tran,
                                   ncol = 1, align = "v")

    if (!is.null(output_file)) {
        ggsave(output_file, combined, width = 10, height = 12)
    }

    return(combined)
}


#' Plot Significance Summary
#'
#' Visualize significance levels from permutation testing.
#'
#' @param result A StartracOut object
#'
#' @return A ggplot object
#'
#' @examples
#' \dontrun{
#' p <- plot_significance_summary(result)
#' }
plot_significance_summary <- function(result) {
    if (!inherits(result, "StartracOut")) {
        stop("Input must be a StartracOut object")
    }

    require(ggplot2)
    require(dplyr)

    # Check if significance data exists
    if (nrow(result@cluster.sig.data) == 0 ||
        all(is.na(result@cluster.sig.data$p.value))) {
        message("No significance data available (run with n.perm to enable)")
        return(NULL)
    }

    # Get main project results
    sig_data <- result@cluster.sig.data %>%
        dplyr::filter(aid == result@proj) %>%
        dplyr::mutate(significance = case_when(
            p.value < 0.001 ~ "***",
            p.value < 0.01 ~ "**",
            p.value < 0.05 ~ "*",
            TRUE ~ "ns"
        ))

    p <- ggplot(sig_data, aes(x = majorCluster, y = index, fill = significance)) +
        geom_tile() +
        scale_fill_manual(values = c("***" = "darkred", "**" = "red",
                                     "*" = "orange", "ns" = "gray90")) +
        labs(x = "Cell Cluster", y = "Index Type",
             title = "STARTRAC Significance Levels") +
        theme_bw() +
        theme(axis.text.x = element_text(angle = 45, hjust = 1))

    return(p)
}
