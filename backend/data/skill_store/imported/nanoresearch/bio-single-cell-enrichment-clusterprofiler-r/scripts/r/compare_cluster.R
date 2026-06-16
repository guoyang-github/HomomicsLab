# Compare Cluster Enrichment Analysis using clusterProfiler
#
# Author: Yang Guo
# Date: 2026-04-03
#
# This script provides functions to compare enrichment across multiple gene clusters
# using clusterProfiler's compareCluster function

#' Compare Enrichment Across Multiple Clusters
#'
#' @param gene_clusters List of gene lists, one per cluster.
#'                      Names of list elements become cluster labels.
#' @param fun Enrichment function: "enrichGO", "enrichKEGG", "enricher",
#'            "gseGO", "gseKEGG", "GSEA"
#' @param ... Additional parameters passed to the enrichment function
#'
#' @return compareClusterResult object
#'
#' @examples
#' \dontrun{
#' # Create gene clusters from markers
#' markers <- FindAllMarkers(seurat_obj, only.pos = TRUE)
#'
#' # Split by cluster
#' gene_clusters <- split(markers$gene, markers$cluster)
#'
#' # Compare GO enrichment across clusters
#' result <- run_compareCluster(gene_clusters, fun = "enrichGO",
#'                              OrgDb = org.Hs.eg.db, ont = "BP")
#'
#' # Visualize
#' dotplot(result, showCategory = 10)
#' }
run_compareCluster <- function(
    gene_clusters,
    fun = "enrichGO",
    ...
) {
    if (!is.list(gene_clusters)) {
        stop("gene_clusters must be a list of gene vectors")
    }

    if (is.null(names(gene_clusters))) {
        stop("gene_clusters must be a named list of gene vectors")
    }

    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler: BiocManager::install('clusterProfiler')")
    }

    message(sprintf("Comparing enrichment across %d clusters using %s...",
                    length(gene_clusters), fun))

    result <- clusterProfiler::compareCluster(
        geneClusters = gene_clusters,
        fun = fun,
        ...
    )

    if (is.null(result) || nrow(as.data.frame(result)) == 0) {
        warning("No significant enrichment found across clusters.")
    } else {
        message(sprintf("Found enrichment for comparison"))
    }

    return(result)
}


#' Compare Enrichment from Seurat Markers
#'
#' @param markers Data frame from FindAllMarkers() or FindMarkers()
#' @param top_n Use top N genes per cluster (default: all significant genes)
#' @param logfc_threshold Minimum log2FC for gene selection
#' @param pval_threshold Maximum adjusted p-value for gene selection
#' @param only.pos Only use positive markers (avg_log2FC > logfc_threshold).
#'                 If FALSE, uses both positive and negative markers.
#' @param ... Additional parameters passed to run_compareCluster
#'
#' @return compareClusterResult object
#'
#' @examples
#' \dontrun{
#' markers <- FindAllMarkers(seurat_obj, only.pos = TRUE)
#'
#' # Compare top 100 genes per cluster
#' result <- compareCluster_seurat(markers, top_n = 100,
#'                                 fun = "enrichGO",
#'                                 OrgDb = org.Hs.eg.db, ont = "BP")
#' }
compareCluster_seurat <- function(
    markers,
    top_n = NULL,
    logfc_threshold = 0.25,
    pval_threshold = 0.05,
    only.pos = TRUE,
    ...
) {
    if (!is.data.frame(markers)) {
        stop("markers must be a data frame")
    }

    if (!("cluster" %in% colnames(markers))) {
        stop("markers must have 'cluster' column from FindAllMarkers()")
    }

    # Get unique clusters
    clusters <- unique(as.character(markers$cluster))
    message(sprintf("Preparing gene lists for %d clusters...", length(clusters)))

    # Create gene list for each cluster
    gene_clusters <- lapply(clusters, function(cl) {
        cluster_markers <- markers[markers$cluster == cl, ]

        # Filter by significance
        if (only.pos) {
            sig_markers <- cluster_markers[
                cluster_markers$p_val_adj < pval_threshold &
                cluster_markers$avg_log2FC > logfc_threshold,
            ]
        } else {
            sig_markers <- cluster_markers[
                cluster_markers$p_val_adj < pval_threshold &
                abs(cluster_markers$avg_log2FC) > logfc_threshold,
            ]
        }

        # Select genes
        if (!is.null(top_n)) {
            sig_markers <- sig_markers[order(-sig_markers$avg_log2FC), ]
            genes <- sig_markers$gene[1:min(top_n, nrow(sig_markers))]
        } else {
            genes <- sig_markers$gene
        }

        message(sprintf("  Cluster %s: %d genes", cl, length(genes)))
        return(genes)
    })

    names(gene_clusters) <- clusters

    # Remove empty clusters
    gene_clusters <- gene_clusters[sapply(gene_clusters, length) > 0]

    if (length(gene_clusters) == 0) {
        stop("No genes selected for any cluster")
    }

    # Run comparison
    result <- run_compareCluster(gene_clusters, ...)

    return(result)
}


#' Compare GSEA Across Multiple Clusters
#'
#' @param markers Data frame from FindAllMarkers() with signed log2FC
#' @param gsea_fun GSEA function: "gseGO", "gseKEGG", "GSEA"
#' @param min_genes Minimum number of genes per cluster
#' @param ... Additional parameters passed to compareCluster
#'
#' @return compareClusterResult object
#'
#' @examples
#' \dontrun{
#' markers <- FindAllMarkers(seurat_obj, only.pos = FALSE)
#'
#' result <- compareGSEA_seurat(markers, gsea_fun = "gseGO",
#'                              OrgDb = org.Hs.eg.db, ont = "BP")
#' }
compareGSEA_seurat <- function(
    markers,
    gsea_fun = "gseGO",
    min_genes = 10,
    ...
) {
    if (!("cluster" %in% colnames(markers))) {
        stop("markers must have 'cluster' column")
    }

    clusters <- unique(as.character(markers$cluster))
    message(sprintf("Preparing ranked gene lists for %d clusters...", length(clusters)))

    # Create ranked gene list for each cluster
    gene_clusters <- lapply(clusters, function(cl) {
        cluster_markers <- markers[markers$cluster == cl, ]

        # Create named vector (log2FC as values, gene names as names)
        gene_list <- setNames(cluster_markers$avg_log2FC, cluster_markers$gene)
        gene_list <- sort(gene_list, decreasing = TRUE)
        gene_list <- gene_list[is.finite(gene_list)]

        message(sprintf("  Cluster %s: %d genes", cl, length(gene_list)))
        return(gene_list)
    })

    names(gene_clusters) <- clusters

    # Filter by minimum size
    gene_clusters <- gene_clusters[sapply(gene_clusters, length) >= min_genes]

    if (length(gene_clusters) == 0) {
        stop("No clusters have enough genes for GSEA")
    }

    # Run compareCluster with GSEA function
    result <- run_compareCluster(
        gene_clusters = gene_clusters,
        fun = gsea_fun,
        ...
    )

    return(result)
}


#' Merge Multiple enrichResult Objects for Comparison
#'
#' Alternative to compareCluster when you already have enrichment results.
#' Useful for combining results from different databases or conditions.
#'
#' @param enrich_list Named list of enrichResult objects
#'
#' @return compareClusterResult object
#'
#' @examples
#' \dontrun{
#' # Run separate enrichments
#' go_result <- run_enrichGO(genes1, org.Hs.eg.db)
#' kegg_result <- run_enrichKEGG(genes1, "hsa")
#'
#' # Merge
#' combined <- merge_enrichResults(list(
#'     GO = go_result,
#'     KEGG = kegg_result
#' ))
#'
#' dotplot(combined)
#' }
merge_enrichResults <- function(enrich_list) {
    if (!is.list(enrich_list) || is.null(names(enrich_list))) {
        stop("enrich_list must be a named list of enrichResult objects")
    }

    # Check all elements are enrichResult
    valid <- sapply(enrich_list, function(x) {
        inherits(x, c("enrichResult", "gseaResult"))
    })

    if (!all(valid)) {
        stop("All elements must be enrichResult or gseaResult objects")
    }

    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler")
    }

    result <- clusterProfiler::merge_result(enrich_list)

    return(result)
}


#' Simplify GO Compare Cluster Results
#'
#' Remove redundant GO terms from compareCluster results.
#' Only applicable for GO enrichment results.
#'
#' @param compare_result compareClusterResult object from GO analysis
#' @param cutoff Similarity cutoff for redundancy (default: 0.7)
#' @param by Feature to select representative term (default: "p.adjust")
#' @param measure Semantic similarity measure: "Wang", "Rel", "Resnik", etc.
#'
#' @return Simplified compareClusterResult object
#'
#' @examples
#' \dontrun{
#' result <- run_compareCluster(gene_clusters, fun = "enrichGO",
#'                              OrgDb = org.Hs.eg.db, ont = "BP")
#'
#' # Remove redundant terms
#' simplified <- simplify_compareCluster(result, cutoff = 0.7)
#'
#' dotplot(simplified)
#' }
simplify_compareCluster <- function(
    compare_result,
    cutoff = 0.7,
    by = "p.adjust",
    measure = "Wang"
) {
    if (!inherits(compare_result, "compareClusterResult")) {
        stop("Input must be a compareClusterResult object")
    }

    if (!requireNamespace("GOSemSim", quietly = TRUE)) {
        stop("Please install GOSemSim: BiocManager::install('GOSemSim')")
    }

    message(sprintf("Simplifying GO results (cutoff=%.2f, measure=%s)...",
                    cutoff, measure))

    result <- clusterProfiler::simplify(
        compare_result,
        cutoff = cutoff,
        by = by,
        measure = measure
    )

    message(sprintf("Simplified from %d to %d terms",
                    nrow(compare_result@compareClusterResult),
                    nrow(result@compareClusterResult)))

    return(result)
}
