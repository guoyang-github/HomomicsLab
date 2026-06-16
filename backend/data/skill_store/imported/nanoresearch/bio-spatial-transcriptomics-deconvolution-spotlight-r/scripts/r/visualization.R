# SPOTlight Visualization Functions
#
# Plotting functions for SPOTlight deconvolution results.

#' Plot Cell Type Proportions
#'
#' Visualize cell type proportions from SPOTlight results.
#'
#' @param proportions Matrix of proportions (spots x cell_types)
#' @param plot_type Type of plot: "bar", "heatmap", "box", "stacked" (default: "bar")
#' @param n_top Number of top cell types to show (default: all)
#'
#' @return ggplot object
#'
#' @export
#'
#' @examples
#' \dontrun{
#' plot_cell_type_proportions(results$proportions, plot_type = "bar")
#' }
plot_cell_type_proportions <- function(proportions, plot_type = "bar", n_top = NULL) {
    library(ggplot2)
    library(reshape2)

    # Select top cell types if specified
    if (!is.null(n_top)) {
        avg_props <- colMeans(proportions)
        top_ct <- names(sort(avg_props, decreasing = TRUE))[1:min(n_top, length(avg_props))]
        proportions <- proportions[, top_ct, drop = FALSE]
    }

    if (plot_type == "bar") {
        # Bar plot of average proportions
        avg_props <- colMeans(proportions)
        df <- data.frame(
            CellType = names(avg_props),
            Proportion = avg_props
        )

        p <- ggplot(df, aes(x = reorder(CellType, -Proportion), y = Proportion)) +
            geom_bar(stat = "identity", fill = "steelblue") +
            theme_minimal() +
            theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
            labs(x = "Cell Type", y = "Average Proportion",
                 title = "Cell Type Proportions")

    } else if (plot_type == "box") {
        # Box plot
        df <- melt(proportions)
        colnames(df) <- c("Spot", "CellType", "Proportion")

        p <- ggplot(df, aes(x = CellType, y = Proportion)) +
            geom_boxplot(fill = "steelblue") +
            theme_minimal() +
            theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
            labs(x = "Cell Type", y = "Proportion",
                 title = "Distribution of Cell Type Proportions")

    } else if (plot_type == "heatmap") {
        # Heatmap
        df <- melt(proportions)
        colnames(df) <- c("Spot", "CellType", "Proportion")

        p <- ggplot(df, aes(x = CellType, y = Spot, fill = Proportion)) +
            geom_tile() +
            scale_fill_gradient(low = "white", high = "steelblue") +
            theme_minimal() +
            theme(axis.text.y = element_blank()) +
            labs(x = "Cell Type", y = "Spot",
                 title = "Cell Type Proportions Heatmap")

    } else if (plot_type == "stacked") {
        # Stacked bar plot (first 50 spots)
        n_spots <- min(50, nrow(proportions))
        props_sub <- proportions[1:n_spots, ]
        df <- melt(props_sub)
        colnames(df) <- c("Spot", "CellType", "Proportion")

        p <- ggplot(df, aes(x = factor(Spot), y = Proportion, fill = CellType)) +
            geom_bar(stat = "identity") +
            theme_minimal() +
            theme(axis.text.x = element_blank()) +
            labs(x = "Spot", y = "Proportion",
                 title = "Cell Type Composition (First 50 Spots)")

    } else {
        stop("Unknown plot_type. Use 'bar', 'box', 'heatmap', or 'stacked'")
    }

    return(p)
}


#' Plot Proportions on Spatial Coordinates
#'
#' Plot cell type proportions overlaid on spatial coordinates.
#'
#' @param proportions Matrix of proportions
#' @param spatial_coords Data frame with x, y coordinates for each spot
#' @param cell_type Cell type to plot (column name from proportions)
#' @param pt_size Point size (default: 2)
#'
#' @return ggplot object
#'
#' @export
plot_spatial_proportions <- function(proportions, spatial_coords, cell_type, pt_size = 2) {
    library(ggplot2)

    if (!(cell_type %in% colnames(proportions))) {
        stop(sprintf("Cell type '%s' not found in proportions", cell_type))
    }

    if (nrow(spatial_coords) != nrow(proportions)) {
        stop("Number of spots in spatial_coords must match proportions")
    }

    df <- data.frame(
        x = spatial_coords[, 1],
        y = spatial_coords[, 2],
        proportion = proportions[, cell_type]
    )

    p <- ggplot(df, aes(x = x, y = y, color = proportion)) +
        geom_point(size = pt_size) +
        scale_color_gradient(low = "lightgrey", high = "darkred",
                            name = "Proportion") +
        coord_fixed() +
        theme_minimal() +
        labs(title = sprintf("%s Spatial Distribution", cell_type),
             x = "X", y = "Y")

    return(p)
}


#' Plot Proportion Correlation
#'
#' Plot correlation between cell type proportions.
#'
#' @param proportions Matrix of proportions
#'
#' @return ggplot object
#'
#' @export
plot_proportion_correlation <- function(proportions) {
    library(ggplot2)
    library(reshape2)

    # Calculate correlation
    cor_matrix <- cor(proportions)

    # Melt for ggplot
    cor_df <- melt(cor_matrix)
    colnames(cor_df) <- c("CellType1", "CellType2", "Correlation")

    p <- ggplot(cor_df, aes(x = CellType1, y = CellType2, fill = Correlation)) +
        geom_tile() +
        scale_fill_gradient2(low = "blue", mid = "white", high = "red",
                            midpoint = 0, limits = c(-1, 1)) +
        theme_minimal() +
        theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
        labs(title = "Cell Type Proportion Correlation")

    return(p)
}


#' Plot NMF Factorization
#'
#' Visualize NMF basis and coefficient matrices.
#'
#' @param spotlight_results Results from run_spotlight
#' @param n_genes Number of top genes to show (default: 10)
#'
#' @return List of ggplot objects
#'
#' @export
plot_nmf_factorization <- function(spotlight_results, n_genes = 10) {
    library(ggplot2)
    library(reshape2)

    plots <- list()

    # Plot basis matrix (gene x factor)
    if (!is.null(spotlight_results$nmf_model$basis)) {
        basis <- spotlight_results$nmf_model$basis

        # Select top genes for each factor
        top_genes <- lapply(1:ncol(basis), function(i) {
            idx <- order(basis[, i], decreasing = TRUE)[1:n_genes]
            data.frame(
                Factor = paste0("Factor", i),
                Gene = rownames(basis)[idx],
                Weight = basis[idx, i]
            )
        })
        basis_df <- do.call(rbind, top_genes)

        plots$basis <- ggplot(basis_df, aes(x = reorder(Gene, Weight), y = Weight)) +
            geom_bar(stat = "identity", fill = "steelblue") +
            facet_wrap(~Factor, scales = "free_y") +
            coord_flip() +
            theme_minimal() +
            labs(title = "NMF Basis Matrix (Top Genes)", x = "Gene", y = "Weight")
    }

    # Plot coefficient matrix (factor x spot) for first 50 spots
    if (!is.null(spotlight_results$nmf_model$coef)) {
        coef <- spotlight_results$nmf_model$coef
        n_spots <- min(50, ncol(coef))
        coef_sub <- coef[, 1:n_spots, drop = FALSE]

        coef_df <- melt(coef_sub)
        colnames(coef_df) <- c("Factor", "Spot", "Coefficient")

        plots$coef <- ggplot(coef_df, aes(x = Spot, y = Factor, fill = Coefficient)) +
            geom_tile() +
            scale_fill_gradient(low = "white", high = "steelblue") +
            theme_minimal() +
            theme(axis.text.x = element_blank()) +
            labs(title = "NMF Coefficient Matrix (First 50 Spots)")
    }

    return(plots)
}


#' Create Cell Type Composition Plot
#'
#' Create a pie or donut chart of cell type composition.
#'
#' @param proportions Matrix of proportions
#' @param plot_type "pie" or "donut" (default: "donut")
#'
#' @return ggplot object
#'
#' @export
plot_composition <- function(proportions, plot_type = "donut") {
    library(ggplot2)

    avg_props <- colMeans(proportions)
    df <- data.frame(
        CellType = names(avg_props),
        Proportion = avg_props
    )

    if (plot_type == "pie") {
        p <- ggplot(df, aes(x = "", y = Proportion, fill = CellType)) +
            geom_bar(stat = "identity", width = 1) +
            coord_polar("y", start = 0) +
            theme_void() +
            labs(title = "Cell Type Composition")

    } else if (plot_type == "donut") {
        p <- ggplot(df, aes(x = 2, y = Proportion, fill = CellType)) +
            geom_bar(stat = "identity", width = 1) +
            coord_polar("y", start = 0) +
            xlim(0.5, 2.5) +
            theme_void() +
            labs(title = "Cell Type Composition")

    } else {
        stop("Unknown plot_type. Use 'pie' or 'donut'")
    }

    return(p)
}


#' Save SPOTlight Plots
#'
#' Save multiple SPOTlight visualizations to files.
#'
#' @param spotlight_results Results from run_spotlight
#' @param output_dir Output directory for plots
#' @param prefix File prefix (default: "spotlight")
#' @param spatial_coords Optional spatial coordinates for spatial plots
#'
#' @export
save_spotlight_plots <- function(spotlight_results, output_dir, prefix = "spotlight",
                                  spatial_coords = NULL) {
    if (!dir.exists(output_dir)) {
        dir.create(output_dir, recursive = TRUE)
    }

    proportions <- spotlight_results$proportions

    # 1. Bar plot
    p1 <- plot_cell_type_proportions(proportions, plot_type = "bar")
    ggsave(file.path(output_dir, paste0(prefix, "_proportions_bar.pdf")),
           p1, width = 10, height = 6)

    # 2. Box plot
    p2 <- plot_cell_type_proportions(proportions, plot_type = "box")
    ggsave(file.path(output_dir, paste0(prefix, "_proportions_box.pdf")),
           p2, width = 10, height = 6)

    # 3. Heatmap
    p3 <- plot_cell_type_proportions(proportions, plot_type = "heatmap")
    ggsave(file.path(output_dir, paste0(prefix, "_proportions_heatmap.pdf")),
           p3, width = 8, height = 10)

    # 4. Correlation plot
    p4 <- plot_proportion_correlation(proportions)
    ggsave(file.path(output_dir, paste0(prefix, "_correlation.pdf")),
           p4, width = 8, height = 7)

    # 5. Spatial plots (if coordinates provided)
    if (!is.null(spatial_coords)) {
        for (ct in colnames(proportions)) {
            p <- plot_spatial_proportions(proportions, spatial_coords, ct)
            ggsave(file.path(output_dir, paste0(prefix, "_spatial_", ct, ".pdf")),
                   p, width = 6, height = 6)
        }
    }

    cat(sprintf("Saved plots to %s\n", output_dir))
}
