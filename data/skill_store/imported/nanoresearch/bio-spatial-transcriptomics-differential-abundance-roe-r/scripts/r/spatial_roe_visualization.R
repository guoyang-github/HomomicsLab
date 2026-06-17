# Spatial Ro/e Visualization Functions
# Including network plots, heatmaps, and spatial maps

#' @title Plot Spatial Ro/e Heatmap
#' @description Create a heatmap of Ro/e co-occurrence values
#' @param spatial_roe_result Result from calculate_spatial_roe()
#' @param cluster Whether to cluster rows/columns (default: TRUE)
#' @param min_roe Minimum Ro/e to display (default: 0)
#' @param show_values Whether to show Ro/e values on cells
#' @param title Plot title
#' @return ggplot object
#' @export
plot_spatial_roe_heatmap <- function(
    spatial_roe_result,
    cluster = TRUE,
    min_roe = 0,
    show_values = TRUE,
    title = "Spatial Ro/e Co-occurrence"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE) ||
        !requireNamespace("reshape2", quietly = TRUE)) {
        stop("Please install ggplot2 and reshape2")
    }

    # Extract Ro/e matrix
    roe_mat <- spatial_roe_result$roe

    # Filter by min_roe
    roe_mat[roe_mat < min_roe] <- 0

    # Get significant pairs
    sig_mat <- spatial_roe_result$statistics$significant

    # Convert to data frame
    roe_df <- reshape2::melt(roe_mat)
    colnames(roe_df) <- c("cell_type_a", "cell_type_b", "roe")

    sig_df <- reshape2::melt(sig_mat)
    roe_df$significant <- sig_df$value

    # Determine text color
    roe_df$text_color <- ifelse(roe_df$roe > 1.5, "white", "black")

    # Create plot
    p <- ggplot2::ggplot(roe_df, ggplot2::aes(x = cell_type_b, y = cell_type_a, fill = roe)) +
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
            subtitle = paste("Method:", spatial_roe_result$method),
            x = "Cell Type B (Neighbor)",
            y = "Cell Type A (Center)"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text.x = ggplot2::element_text(angle = 45, hjust = 1, size = 10),
            axis.text.y = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5),
            panel.grid = ggplot2::element_blank(),
            legend.position = "right"
        )

    # Add significance indicators
    if (any(roe_df$significant, na.rm = TRUE)) {
        sig_points <- roe_df[roe_df$significant & !is.na(roe_df$significant), ]
        if (nrow(sig_points) > 0) {
            p <- p + ggplot2::geom_point(
                data = sig_points,
                ggplot2::aes(x = cell_type_b, y = cell_type_a),
                shape = "*", size = 5, color = "black"
            )
        }
    }

    # Add value text
    if (show_values) {
        p <- p + ggplot2::geom_text(
            ggplot2::aes(label = sprintf("%.2f", roe)),
            color = roe_df$text_color,
            size = 3
        )
    }

    return(p)
}

#' @title Plot Spatial Ro/e Network
#' @description Create a network visualization of cell type co-localization
#' @param spatial_roe_result Result from calculate_spatial_roe()
#' @param min_roe Minimum Ro/e for drawing edges (default: 1.5)
#' @param max_roe Maximum Ro/e for scaling (default: NULL = auto)
#' @param layout Layout algorithm: "circle", "fr", or "kk"
#' @param node_color_by How to color nodes: "degree" or "none"
#' @param title Plot title
#' @return ggplot object
#' @export
plot_spatial_roe_network <- function(
    spatial_roe_result,
    min_roe = 1.5,
    max_roe = NULL,
    layout = "circle",
    node_color_by = "degree",
    title = "Cell Type Co-localization Network"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE) ||
        !requireNamespace("igraph", quietly = TRUE) ||
        !requireNamespace("ggraph", quietly = TRUE)) {
        stop("Please install ggplot2, igraph, and ggraph")
    }

    # Extract Ro/e matrix
    roe_mat <- spatial_roe_result$roe
    cell_types <- rownames(roe_mat)

    # Create edge list
    edges <- data.frame(
        from = character(),
        to = character(),
        roe = numeric(),
        stringsAsFactors = FALSE
    )

    for (i in 1:nrow(roe_mat)) {
        for (j in 1:ncol(roe_mat)) {
            if (i != j && roe_mat[i, j] >= min_roe && !is.na(roe_mat[i, j])) {
                edges <- rbind(edges, data.frame(
                    from = cell_types[i],
                    to = cell_types[j],
                    roe = roe_mat[i, j],
                    stringsAsFactors = FALSE
                ))
            }
        }
    }

    if (nrow(edges) == 0) {
        message("No edges meet the min_roe threshold")
        return(NULL)
    }

    # Create graph
    g <- igraph::graph_from_data_frame(edges, directed = FALSE, vertices = cell_types)

    # Calculate node degrees for sizing
    degrees <- igraph::degree(g)

    # Create layout
    if (layout == "circle") {
        layout_coords <- igraph::layout_in_circle(g)
    } else if (layout == "fr") {
        layout_coords <- igraph::layout_with_fr(g)
    } else {
        layout_coords <- igraph::layout_with_kk(g)
    }

    # Create plot
    p <- ggraph::ggraph(g, layout = "manual", x = layout_coords[, 1], y = layout_coords[, 2]) +
        ggraph::geom_edge_link(
            ggplot2::aes(edge_width = roe, edge_alpha = roe),
            color = "grey40",
            arrow = ggplot2::arrow(length = grid::unit(3, "mm")),
            end_cap = ggraph::circle(5, "mm")
        ) +
        ggraph::geom_node_point(
            ggplot2::aes(size = degrees),
            color = "steelblue",
            alpha = 0.8
        ) +
        ggraph::geom_node_text(
            ggplot2::aes(label = name),
            repel = TRUE,
            size = 4,
            fontface = "bold"
        ) +
        ggraph::scale_edge_width(range = c(0.5, 3), name = "Ro/e") +
        ggraph::scale_edge_alpha(range = c(0.3, 1), guide = "none") +
        ggplot2::scale_size_continuous(name = "Degree", range = c(5, 15)) +
        ggplot2::labs(title = title) +
        ggraph::theme_graph() +
        ggplot2::theme(
            plot.title = ggplot2::element_text(hjust = 0.5, size = 14, face = "bold")
        )

    return(p)
}

#' @title Plot Spatial Ro/e Chord Diagram
#' @description Create a chord diagram of cell type interactions
#' @param spatial_roe_result Result from calculate_spatial_roe()
#' @param min_roe Minimum Ro/e for drawing links (default: 1.5)
#' @param title Plot title
#' @return grid object
#' @export
plot_spatial_roe_chord <- function(
    spatial_roe_result,
    min_roe = 1.5,
    title = "Cell Type Co-localization"
) {
    if (!requireNamespace("circlize", quietly = TRUE)) {
        stop("Please install circlize: install.packages('circlize')")
    }

    # Extract data
    roe_df <- spatial_roe_to_dataframe(spatial_roe_result)

    # Filter for strong interactions
    strong_interactions <- roe_df[roe_df$roe >= min_roe &
                                   roe_df$cell_type_a != roe_df$cell_type_b, ]

    if (nrow(strong_interactions) == 0) {
        message("No strong interactions found")
        return(NULL)
    }

    # Create link data
    link_df <- data.frame(
        from = strong_interactions$cell_type_a,
        to = strong_interactions$cell_type_b,
        value = strong_interactions$roe,
        stringsAsFactors = FALSE
    )

    # Create chord diagram
    circlize::circos.clear()

    # Set up colors
    cell_types <- unique(c(link_df$from, link_df$to))
    colors <- RColorBrewer::brewer.pal(min(length(cell_types), 8), "Set1")
    if (length(cell_types) > 8) {
        colors <- colorRampPalette(colors)(length(cell_types))
    }
    names(colors) <- cell_types

    circlize::chordDiagram(
        link_df,
        grid.col = colors,
        transparency = 0.3,
        annotationTrack = c("name", "grid")
    )

    title(main = title)

    circlize::circos.clear()
}

#' @title Plot Top Interactions as Lollipop
#' @description Create a lollipop plot of top spatial interactions
#' @param spatial_roe_result Result from calculate_spatial_roe()
#' @param n_top Number of top interactions to show (default: 20)
#' @param exclude_self Whether to exclude self-interactions (default: TRUE)
#' @param title Plot title
#' @return ggplot object
#' @export
plot_spatial_roe_lollipop <- function(
    spatial_roe_result,
    n_top = 20,
    exclude_self = TRUE,
    title = "Top Spatial Co-localizations"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    # Convert to data frame
    roe_df <- spatial_roe_to_dataframe(spatial_roe_result)

    # Exclude self-interactions if requested
    if (exclude_self) {
        roe_df <- roe_df[roe_df$cell_type_a != roe_df$cell_type_b, ]
    }

    # Get top interactions
    roe_df <- roe_df[order(-roe_df$roe), ]
    top_df <- head(roe_df, n_top)

    # Create interaction label
    top_df$interaction <- paste(top_df$cell_type_a, "→", top_df$cell_type_b)
    top_df$interaction <- factor(top_df$interaction, levels = rev(top_df$interaction))

    # Determine color based on significance
    top_df$color <- ifelse(top_df$significant, "#b2182b", "grey50")

    # Create plot
    p <- ggplot2::ggplot(top_df, ggplot2::aes(x = interaction, y = roe)) +
        ggplot2::geom_hline(yintercept = 1, linetype = "dashed", color = "grey50") +
        ggplot2::geom_segment(
            ggplot2::aes(x = interaction, xend = interaction, y = 1, yend = roe),
            color = "grey70",
            linewidth = 0.5
        ) +
        ggplot2::geom_point(
            ggplot2::aes(size = observed, color = color),
            alpha = 0.8
        ) +
        ggplot2::scale_color_identity() +
        ggplot2::scale_size_continuous(name = "Observed\nCo-occurrence", range = c(3, 10)) +
        ggplot2::coord_flip() +
        ggplot2::labs(
            title = title,
            x = "Cell Type Interaction",
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

#' @title Plot Neighborhood on Spatial Map
#' @description Visualize neighborhoods on spatial coordinates
#' @param spatial_roe_result Result from calculate_spatial_roe()
#' @param coords Data frame with x, y coordinates
#' @param highlight_cell_type Cell type to highlight (optional)
#' @param spot_size Size of spots (default: 1)
#' @param title Plot title
#' @return ggplot object
#' @export
plot_neighborhood_map <- function(
    spatial_roe_result,
    coords,
    highlight_cell_type = NULL,
    spot_size = 1,
    title = "Spatial Neighborhoods"
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    # Calculate neighborhood sizes
    neigh_sizes <- sapply(spatial_roe_result$neighbors, length)

    # Create data frame
    map_df <- data.frame(
        x = coords[, 1],
        y = coords[, 2],
        n_neighbors = neigh_sizes,
        stringsAsFactors = FALSE
    )

    # Create base plot
    p <- ggplot2::ggplot(map_df, ggplot2::aes(x = x, y = y)) +
        ggplot2::geom_point(
            ggplot2::aes(color = n_neighbors),
            size = spot_size,
            alpha = 0.7
        ) +
        ggplot2::scale_color_viridis_c(name = "Neighbors", option = "plasma") +
        ggplot2::coord_fixed() +
        ggplot2::labs(
            title = title,
            x = "X Coordinate",
            y = "Y Coordinate"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5)
        )

    return(p)
}

#' @title Plot Cell Type Spatial Distribution
#' @description Show spatial distribution of a specific cell type
#' @param coords Data frame with x, y coordinates
#' @param cell_type_values Cell type proportions or binary presence
#' @param cell_type_name Name of cell type for title
#' @param title Plot title (optional, overrides cell_type_name)
#' @return ggplot object
#' @export
plot_celltype_spatial <- function(
    coords,
    cell_type_values,
    cell_type_name = "Cell Type",
    title = NULL
) {
    if (!requireNamespace("ggplot2", quietly = TRUE)) {
        stop("Please install ggplot2")
    }

    plot_df <- data.frame(
        x = coords[, 1],
        y = coords[, 2],
        value = cell_type_values,
        stringsAsFactors = FALSE
    )

    plot_title <- ifelse(is.null(title), paste("Spatial Distribution:", cell_type_name), title)

    p <- ggplot2::ggplot(plot_df, ggplot2::aes(x = x, y = y, color = value)) +
        ggplot2::geom_point(size = 1.5, alpha = 0.8) +
        ggplot2::scale_color_viridis_c(
            name = ifelse(all(cell_type_values %in% c(0, 1)), "Presence", "Proportion"),
            option = "magma"
        ) +
        ggplot2::coord_fixed() +
        ggplot2::labs(
            title = plot_title,
            x = "X Coordinate",
            y = "Y Coordinate"
        ) +
        ggplot2::theme_minimal() +
        ggplot2::theme(
            axis.text = ggplot2::element_text(size = 10),
            axis.title = ggplot2::element_text(size = 12, face = "bold"),
            plot.title = ggplot2::element_text(size = 14, face = "bold", hjust = 0.5)
        )

    return(p)
}
