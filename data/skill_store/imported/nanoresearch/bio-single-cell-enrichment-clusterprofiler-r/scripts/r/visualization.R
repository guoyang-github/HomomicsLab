# Visualization functions for clusterProfiler enrichment results
#
# Author: Yang Guo
# Date: 2026-04-03
#
# This script provides visualization wrappers for clusterProfiler results:
# - dotplot: Dot plots of enrichment results
# - barplot: Bar plots
# - cnetplot: Gene-concept networks
# - emapplot: Enrichment maps
# - upsetplot: Upset plots
# - gseaplot: GSEA running score plots

#' Plot Enrichment Results as Dot Plot
#'
#' @param enrich_result enrichResult, gseaResult, or compareClusterResult object
#' @param showCategory Number of categories to show (default: 15)
#' @param split Split by variable (for compareCluster results)
#' @param font_size Font size for labels
#' @param title Plot title
#' @param color Color scale: "pvalue" or "p.adjust"
#' @param size Size variable: "Count" or "GeneRatio"
#' @param save_path Path to save plot (optional)
#' @param width Plot width in inches
#' @param height Plot height in inches
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' # Single enrichment result
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#' plot_enrichment_dot(result, showCategory = 10)
#'
#' # Compare cluster result
#' compare_result <- run_compareCluster(gene_clusters, fun = "enrichGO",
#'                                      OrgDb = org.Hs.eg.db)
#' plot_enrichment_dot(compare_result, showCategory = 10)
#' }
plot_enrichment_dot <- function(
    enrich_result,
    showCategory = 15,
    split = NULL,
    font_size = 12,
    title = NULL,
    color = "p.adjust",
    size = "Count",
    save_path = NULL,
    width = 10,
    height = 8
) {
    if (!requireNamespace("enrichplot", quietly = TRUE)) {
        stop("Please install enrichplot: BiocManager::install('enrichplot')")
    }

    if (!inherits(enrich_result, c("enrichResult", "gseaResult", "compareClusterResult"))) {
        stop("Input must be enrichResult, gseaResult, or compareClusterResult")
    }

    # Create title if not provided
    if (is.null(title)) {
        if (inherits(enrich_result, "enrichResult")) {
            title <- paste(enrich_result@ontology, "Enrichment")
        } else if (inherits(enrich_result, "gseaResult")) {
            title <- paste(enrich_result@setType, "GSEA")
        } else {
            title <- "Enrichment Comparison"
        }
    }

    # Create plot
    p <- enrichplot::dotplot(
        enrich_result,
        showCategory = showCategory,
        split = split,
        font.size = font_size,
        title = title,
        color = color,
        size = size
    )

    # Save if path provided
    if (!is.null(save_path)) {
        ggplot2::ggsave(save_path, p, width = width, height = height)
        message(sprintf("Plot saved to %s", save_path))
    }

    return(p)
}


#' Plot Enrichment Results as Bar Plot
#'
#' @param enrich_result enrichResult object
#' @param showCategory Number of categories to show (default: 15)
#' @param font_size Font size for labels
#' @param title Plot title
#' @param color Color scale: "pvalue" or "p.adjust"
#' @param save_path Path to save plot (optional)
#' @param width Plot width in inches
#' @param height Plot height in inches
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#' plot_enrichment_bar(result, showCategory = 10)
#' }
plot_enrichment_bar <- function(
    enrich_result,
    showCategory = 15,
    font_size = 12,
    title = NULL,
    color = "p.adjust",
    save_path = NULL,
    width = 10,
    height = 8
) {
    if (!inherits(enrich_result, "enrichResult")) {
        stop("Input must be enrichResult object")
    }

    if (is.null(title)) {
        title <- paste(enrich_result@ontology, "Enrichment")
    }

    p <- enrichplot::barplot(
        enrich_result,
        showCategory = showCategory,
        font.size = font_size,
        title = title,
        color = color
    )

    if (!is.null(save_path)) {
        ggplot2::ggsave(save_path, p, width = width, height = height)
        message(sprintf("Plot saved to %s", save_path))
    }

    return(p)
}


#' Plot Gene-Concept Network
#'
#' Shows relationships between genes and enriched terms.
#'
#' @param enrich_result enrichResult object
#' @param showCategory Number of categories to show (default: 5)
#' @param foldChange Named vector of fold changes for genes (optional)
#' @param circular Layout as circular network (default: FALSE)
#' @param colorEdge Color edges by category (default: TRUE)
#' @param node_label Node label type: "category", "gene", "all", "none"
#' @param save_path Path to save plot (optional)
#' @param width Plot width in inches
#' @param height Plot height in inches
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#'
#' # With fold change coloring
#' fc <- setNames(markers$avg_log2FC, markers$gene)
#' plot_gene_concept_network(result, showCategory = 5, foldChange = fc)
#' }
plot_gene_concept_network <- function(
    enrich_result,
    showCategory = 5,
    foldChange = NULL,
    circular = FALSE,
    colorEdge = TRUE,
    node_label = "all",
    save_path = NULL,
    width = 12,
    height = 10
) {
    if (!inherits(enrich_result, "enrichResult")) {
        stop("Input must be enrichResult object")
    }

    if (!requireNamespace("enrichplot", quietly = TRUE)) {
        stop("Please install enrichplot: BiocManager::install('enrichplot')")
    }

    p <- enrichplot::cnetplot(
        enrich_result,
        showCategory = showCategory,
        foldChange = foldChange,
        circular = circular,
        colorEdge = colorEdge,
        node_label = node_label
    )

    if (!is.null(save_path)) {
        ggplot2::ggsave(save_path, p, width = width, height = height)
        message(sprintf("Plot saved to %s", save_path))
    }

    return(p)
}


#' Plot Enrichment Map
#'
#' Network of enriched terms with edges representing similarity.
#'
#' @param enrich_result enrichResult object
#' @param showCategory Number of categories to show (default: 30)
#' @param color Color scale: "pvalue" or "p.adjust"
#' @param layout Network layout: "kk", "star", "circle", etc.
#' @param save_path Path to save plot (optional)
#' @param width Plot width in inches
#' @param height Plot height in inches
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#' plot_enrichment_map(result, showCategory = 20)
#' }
plot_enrichment_map <- function(
    enrich_result,
    showCategory = 30,
    color = "p.adjust",
    layout = "kk",
    save_path = NULL,
    width = 12,
    height = 10
) {
    if (!requireNamespace("enrichplot", quietly = TRUE)) {
        stop("Please install enrichplot")
    }

    if (!inherits(enrich_result, c("enrichResult", "gseaResult"))) {
        stop("Input must be enrichResult or gseaResult object")
    }

    # Calculate pairwise term similarity
    enrich_result <- enrichplot::pairwise_termsim(enrich_result)

    p <- enrichplot::emapplot(
        enrich_result,
        showCategory = showCategory,
        color = color,
        layout = layout
    )

    if (!is.null(save_path)) {
        ggplot2::ggsave(save_path, p, width = width, height = height)
        message(sprintf("Plot saved to %s", save_path))
    }

    return(p)
}


#' Plot Upset Plot for Enrichment Results
#'
#' Shows overlap of genes across enriched terms.
#'
#' @param enrich_result enrichResult object
#' @param n Number of terms to include (default: 10)
#' @param save_path Path to save plot (optional)
#' @param width Plot width in inches
#' @param height Plot height in inches
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#' plot_upset(result, n = 15)
#' }
plot_upset <- function(
    enrich_result,
    n = 10,
    save_path = NULL,
    width = 10,
    height = 6
) {
    if (!inherits(enrich_result, "enrichResult")) {
        stop("Input must be enrichResult object")
    }

    if (!requireNamespace("enrichplot", quietly = TRUE)) {
        stop("Please install enrichplot")
    }

    p <- enrichplot::upsetplot(enrich_result, n = n)

    if (!is.null(save_path)) {
        ggplot2::ggsave(save_path, p, width = width, height = height)
        message(sprintf("Plot saved to %s", save_path))
    }

    return(p)
}


#' Plot GSEA Running Score
#'
#' Visualize GSEA results for specific gene sets.
#'
#' @param gsea_result gseaResult object
#' @param geneSetID Gene set ID(s) to plot. Can be numeric index or character ID.
#' @param title Plot title (optional)
#' @param save_path Path to save plot (optional)
#' @param width Plot width in inches
#' @param height Plot height in inches
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' result <- run_gseGO(gene_list, org.Hs.eg.db)
#'
#' # Plot top pathway
#' plot_gsea_running(result, geneSetID = 1)
#'
#' # Plot specific pathway
#' plot_gsea_running(result, geneSetID = "GO:0007049")
#'
#' # Plot multiple pathways
#' plot_gsea_running(result, geneSetID = 1:3)
#' }
plot_gsea_running <- function(
    gsea_result,
    geneSetID = 1,
    title = NULL,
    save_path = NULL,
    width = 8,
    height = 6
) {
    if (!inherits(gsea_result, "gseaResult")) {
        stop("Input must be gseaResult object")
    }

    if (!requireNamespace("enrichplot", quietly = TRUE)) {
        stop("Please install enrichplot")
    }

    # Handle multiple gene sets
    if (length(geneSetID) > 1) {
        plots <- lapply(geneSetID, function(id) {
            plot_gsea_running(gsea_result, geneSetID = id, title = title)
        })

        if (!is.null(save_path)) {
            # Combine plots
            combined <- patchwork::wrap_plots(plots, ncol = 1)
            ggplot2::ggsave(save_path, combined, width = width, height = height * length(geneSetID))
            message(sprintf("Combined plot saved to %s", save_path))
        }

        return(plots)
    }

    # Get gene set name for title
    if (is.null(title)) {
        if (is.numeric(geneSetID)) {
            title <- gsea_result@result$Description[geneSetID]
        } else {
            title <- geneSetID
        }
    }

    p <- enrichplot::gseaplot2(
        gsea_result,
        geneSetID = geneSetID,
        title = title
    )

    if (!is.null(save_path) && length(geneSetID) == 1) {
        ggplot2::ggsave(save_path, p, width = width, height = height)
        message(sprintf("Plot saved to %s", save_path))
    }

    return(p)
}


#' Plot GSEA Ridge Plot
#'
#' Distribution of GSEA scores across gene sets.
#'
#' @param gsea_result gseaResult object
#' @param showCategory Number of categories to show (default: 15)
#' @param fill Fill color: "pvalue" or "p.adjust"
#' @param core_enrichment Show only core enrichment genes (default: TRUE)
#' @param save_path Path to save plot (optional)
#' @param width Plot width in inches
#' @param height Plot height in inches
#'
#' @return ggplot object
#'
#' @examples
#' \dontrun{
#' result <- run_gseGO(gene_list, org.Hs.eg.db)
#' plot_gsea_ridge(result, showCategory = 10)
#' }
plot_gsea_ridge <- function(
    gsea_result,
    showCategory = 15,
    fill = "p.adjust",
    core_enrichment = TRUE,
    save_path = NULL,
    width = 10,
    height = 8
) {
    if (!inherits(gsea_result, "gseaResult")) {
        stop("Input must be gseaResult object")
    }

    if (!requireNamespace("enrichplot", quietly = TRUE)) {
        stop("Please install enrichplot")
    }

    p <- enrichplot::ridgeplot(
        gsea_result,
        showCategory = showCategory,
        fill = fill,
        core_enrichment = core_enrichment
    )

    if (!is.null(save_path)) {
        ggplot2::ggsave(save_path, p, width = width, height = height)
        message(sprintf("Plot saved to %s", save_path))
    }

    return(p)
}


#' Create Multi-Panel Enrichment Visualization
#'
#' Create a comprehensive figure with multiple visualization types.
#'
#' @param enrich_result enrichResult or gseaResult object
#' @param save_path Path to save combined plot (required)
#' @param top_n Number of top terms to show in each plot
#' @param foldChange Named vector of fold changes (optional, for cnetplot)
#' @param width Overall width in inches
#' @param height Overall height in inches
#'
#' @return Combined ggplot object
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#'
#' fc <- setNames(markers$avg_log2FC, markers$gene)
#' plot_enrichment_comprehensive(
#'     result,
#'     save_path = "enrichment_overview.pdf",
#'     top_n = 10,
#'     foldChange = fc
#' )
#' }
plot_enrichment_comprehensive <- function(
    enrich_result,
    save_path,
    top_n = 10,
    foldChange = NULL,
    width = 16,
    height = 12
) {
    if (!inherits(enrich_result, c("enrichResult", "gseaResult"))) {
        stop("Input must be enrichResult or gseaResult object")
    }

    if (!requireNamespace("patchwork", quietly = TRUE)) {
        stop("Please install patchwork: install.packages('patchwork')")
    }
    if (!requireNamespace("enrichplot", quietly = TRUE)) {
        stop("Please install enrichplot: BiocManager::install('enrichplot')")
    }

    is_gsea <- inherits(enrich_result, "gseaResult")

    if (is_gsea) {
        # GSEA-specific multi-panel visualization
        p1 <- plot_enrichment_dot(enrich_result, showCategory = top_n) +
            ggplot2::ggtitle("A) Dot Plot")

        p2 <- plot_enrichment_map(enrich_result, showCategory = top_n) +
            ggplot2::ggtitle("B) Enrichment Map")

        p3 <- plot_gsea_running(enrich_result, geneSetID = 1) +
            ggplot2::ggtitle("C) Top GSEA Running Score")

        p4 <- plot_gsea_ridge(enrich_result, showCategory = min(10, top_n)) +
            ggplot2::ggtitle("D) Ridge Plot")

        title_text <- paste(enrich_result@setType, "GSEA")
    } else {
        # ORA multi-panel visualization
        p1 <- plot_enrichment_dot(enrich_result, showCategory = top_n) +
            ggplot2::ggtitle("A) Dot Plot")

        p2 <- plot_enrichment_bar(enrich_result, showCategory = top_n) +
            ggplot2::ggtitle("B) Bar Plot")

        p3 <- plot_enrichment_map(enrich_result, showCategory = top_n) +
            ggplot2::ggtitle("C) Enrichment Map")

        p4 <- plot_gene_concept_network(
            enrich_result,
            showCategory = min(5, top_n),
            foldChange = foldChange
        ) +
            ggplot2::ggtitle("D) Gene-Concept Network")

        title_text <- paste(enrich_result@ontology, "Enrichment Analysis")
    }

    # Combine plots
    combined <- (p1 + p2) / (p3 + p4) +
        patchwork::plot_annotation(
            title = title_text,
            theme = ggplot2::theme(plot.title = ggplot2::element_text(size = 16, hjust = 0.5))
        )

    ggplot2::ggsave(save_path, combined, width = width, height = height, dpi = 300)
    message(sprintf("Comprehensive plot saved to %s", save_path))

    return(combined)
}
