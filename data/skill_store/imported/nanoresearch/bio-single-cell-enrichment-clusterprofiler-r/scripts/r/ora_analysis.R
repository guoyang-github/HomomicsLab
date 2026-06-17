# ORA (Over-Representation Analysis) using clusterProfiler
#
# Author: Yang Guo
# Date: 2026-04-03
#
# This script provides ORA analysis functions for single-cell data:
# - enrichGO: GO enrichment analysis
# - enrichKEGG: KEGG pathway enrichment
# - enricher: Universal enrichment with custom gene sets (MSigDB, etc.)

#' Run GO Enrichment Analysis
#'
#' @param gene_list Character vector of gene symbols or Entrez IDs
#' @param org_db OrgDb object (e.g., org.Hs.eg.db, org.Mm.eg.db)
#' @param keyType Gene ID type: "SYMBOL", "ENTREZID", "ENSEMBL", etc.
#' @param ont GO ontology: "BP" (Biological Process), "MF" (Molecular Function),
#'            "CC" (Cellular Component), or "ALL"
#' @param pvalueCutoff P-value cutoff for significant results
#' @param pAdjustMethod Multiple testing correction method: "BH", "bonferroni", etc.
#' @param qvalueCutoff Q-value cutoff for significant results
#' @param minGSSize Minimum gene set size for testing
#' @param maxGSSize Maximum gene set size for testing
#' @param universe Background gene list (default: all genes in org_db)
#' @param readable Whether to convert gene IDs to gene symbols in output
#' @param pool If ont="ALL", whether to pool three GO sub-ontologies
#'
#' @return enrichResult object
#'
#' @examples
#' \dontrun{
#' library(org.Hs.eg.db)
#' genes <- c("TP53", "BRCA1", "EGFR", "PTEN", "MYC")
#' result <- run_enrichGO(genes, org.Hs.eg.db, ont = "BP")
#' }
run_enrichGO <- function(
    gene_list,
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH",
    qvalueCutoff = 0.2,
    minGSSize = 10,
    maxGSSize = 500,
    universe = NULL,
    readable = TRUE,
    pool = FALSE
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler: BiocManager::install('clusterProfiler')")
    }
    if (!requireNamespace("AnnotationDbi", quietly = TRUE)) {
        stop("Please install AnnotationDbi")
    }

    # Validate inputs
    ont <- match.arg(toupper(ont), c("BP", "MF", "CC", "ALL"))
    pAdjustMethod <- match.arg(pAdjustMethod,
                               c("holm", "hochberg", "hommel", "bonferroni",
                                 "BH", "BY", "fdr", "none"))

    message(sprintf("Running GO enrichment for %d genes (ont=%s, keyType=%s)...",
                    length(gene_list), ont, keyType))

    # Run enrichment
    result <- clusterProfiler::enrichGO(
        gene = gene_list,
        OrgDb = org_db,
        keyType = keyType,
        ont = ont,
        pvalueCutoff = pvalueCutoff,
        pAdjustMethod = pAdjustMethod,
        qvalueCutoff = qvalueCutoff,
        minGSSize = minGSSize,
        maxGSSize = maxGSSize,
        universe = universe,
        readable = readable,
        pool = pool
    )

    if (is.null(result) || nrow(as.data.frame(result)) == 0) {
        warning("No significant GO terms found. Consider relaxing cutoffs.")
    } else {
        message(sprintf("Found %d significant GO terms", nrow(as.data.frame(result))))
    }

    return(result)
}


#' Run KEGG Pathway Enrichment Analysis
#'
#' @param gene_list Character vector of Entrez IDs (or gene symbols if convert_ids=TRUE)
#' @param organism Organism code: "hsa" (human), "mmu" (mouse), "rno" (rat), etc.
#' @param keyType Gene ID type for KEGG: "kegg", "ncbi-geneid", "ncbi-proteinid", "uniprot"
#' @param pvalueCutoff P-value cutoff for significant results
#' @param pAdjustMethod Multiple testing correction method
#' @param qvalueCutoff Q-value cutoff for significant results
#' @param minGSSize Minimum gene set size for testing
#' @param maxGSSize Maximum gene set size for testing
#' @param universe Background gene list
#' @param use_internal_data Use KEGG.db instead of online KEGG data
#' @param convert_ids Convert gene symbols to Entrez IDs using org_db
#' @param org_db OrgDb object for ID conversion (required if convert_ids=TRUE)
#'
#' @return enrichResult object
#'
#' @examples
#' \dontrun{
#' # Using Entrez IDs directly
#' entrez_ids <- c("7157", "672", "1956", "5728", "4609")
#' result <- run_enrichKEGG(entrez_ids, organism = "hsa")
#'
#' # Using gene symbols with automatic conversion
#' symbols <- c("TP53", "BRCA1", "EGFR", "PTEN", "MYC")
#' result <- run_enrichKEGG(symbols, organism = "hsa",
#'                          convert_ids = TRUE, org_db = org.Hs.eg.db)
#' }
run_enrichKEGG <- function(
    gene_list,
    organism = "hsa",
    keyType = "kegg",
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH",
    qvalueCutoff = 0.2,
    minGSSize = 10,
    maxGSSize = 500,
    universe = NULL,
    use_internal_data = FALSE,
    convert_ids = FALSE,
    org_db = NULL
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler: BiocManager::install('clusterProfiler')")
    }

    # Convert gene symbols to Entrez IDs if needed
    if (convert_ids) {
        if (is.null(org_db)) {
            stop("org_db must be provided when convert_ids=TRUE")
        }
        message("Converting gene symbols to Entrez IDs...")
        gene_df <- clusterProfiler::bitr(
            gene_list,
            fromType = "SYMBOL",
            toType = "ENTREZID",
            OrgDb = org_db
        )
        if (is.null(gene_df) || nrow(gene_df) == 0) {
            stop("No genes could be mapped to Entrez IDs")
        }
        gene_list <- gene_df$ENTREZID
        keyType <- "ncbi-geneid"
        message(sprintf("Converted to %d Entrez IDs", length(gene_list)))
    }

    message(sprintf("Running KEGG enrichment for %d genes (organism=%s)...",
                    length(gene_list), organism))

    result <- clusterProfiler::enrichKEGG(
        gene = gene_list,
        organism = organism,
        keyType = keyType,
        pvalueCutoff = pvalueCutoff,
        pAdjustMethod = pAdjustMethod,
        qvalueCutoff = qvalueCutoff,
        minGSSize = minGSSize,
        maxGSSize = maxGSSize,
        universe = universe,
        use_internal_data = use_internal_data
    )

    if (is.null(result) || nrow(as.data.frame(result)) == 0) {
        warning("No significant KEGG pathways found. Consider relaxing cutoffs.")
    } else {
        message(sprintf("Found %d significant KEGG pathways", nrow(as.data.frame(result))))
    }

    return(result)
}


#' Run Universal Enrichment Analysis with Custom Gene Sets
#'
#' @param gene_list Character vector of gene symbols or IDs
#' @param term2gene Data frame with columns: term ID, gene ID
#' @param term2name Data frame with columns: term ID, term name (optional)
#' @param pvalueCutoff P-value cutoff for significant results
#' @param pAdjustMethod Multiple testing correction method
#' @param qvalueCutoff Q-value cutoff for significant results
#' @param minGSSize Minimum gene set size for testing
#' @param maxGSSize Maximum gene set size for testing
#' @param universe Background gene list
#'
#' @return enrichResult object
#'
#' @examples
#' \dontrun{
#' # Custom gene sets
#' term2gene <- data.frame(
#'     term = c("Pathway1", "Pathway1", "Pathway2", "Pathway2"),
#'     gene = c("TP53", "BRCA1", "EGFR", "MYC")
#' )
#' result <- run_enricher(c("TP53", "EGFR"), term2gene)
#'
#' # MSigDB Hallmark gene sets
#' library(msigdbr)
#' msigdb_h <- msigdbr(species = "Homo sapiens", category = "H")
#' term2gene <- msigdb_h[, c("gs_name", "gene_symbol")]
#' result <- run_enricher(gene_list, term2gene)
#' }
run_enricher <- function(
    gene_list,
    term2gene,
    term2name = NULL,
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH",
    qvalueCutoff = 0.2,
    minGSSize = 10,
    maxGSSize = 500,
    universe = NULL
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler")
    }

    message(sprintf("Running universal enrichment for %d genes...", length(gene_list)))

    result <- clusterProfiler::enricher(
        gene = gene_list,
        TERM2GENE = term2gene,
        TERM2NAME = term2name,
        pvalueCutoff = pvalueCutoff,
        pAdjustMethod = pAdjustMethod,
        qvalueCutoff = qvalueCutoff,
        minGSSize = minGSSize,
        maxGSSize = maxGSSize,
        universe = universe
    )

    if (is.null(result) || nrow(as.data.frame(result)) == 0) {
        warning("No significant terms found. Consider relaxing cutoffs.")
    } else {
        message(sprintf("Found %d significant terms", nrow(as.data.frame(result))))
    }

    return(result)
}


#' Run ORA on Seurat DEG Results
#'
#' @param markers Data frame from FindAllMarkers() or FindMarkers()
#' @param cluster Character: specific cluster to analyze (NULL for all)
#' @param logfc_threshold Log2 fold change threshold for DEG selection
#' @param pval_threshold Adjusted p-value threshold for DEG selection
#' @param top_n Use top N genes instead of threshold-based selection
#' @param only.pos Only use positive markers (avg_log2FC > logfc_threshold).
#'                 If FALSE, uses both positive and negative markers.
#' @param ... Additional parameters passed to run_enrichGO, run_enrichKEGG, etc.
#'
#' @return Character vector of gene symbols
#'
#' @examples
#' \dontrun{
#' # Find markers first
#' markers <- FindAllMarkers(seurat_obj, only.pos = TRUE)
#'
#' # Extract gene symbols for cluster 0
#' genes <- run_ora_seurat(markers, cluster = "0")
#' }
run_ora_seurat <- function(
    markers,
    cluster = NULL,
    logfc_threshold = 0.25,
    pval_threshold = 0.05,
    top_n = NULL,
    only.pos = FALSE,
    ...
) {
    if (!is.data.frame(markers)) {
        stop("markers must be a data frame from FindAllMarkers() or FindMarkers()")
    }

    # Check required columns
    required_cols <- c("gene", "avg_log2FC", "p_val_adj")
    if (!all(required_cols %in% colnames(markers))) {
        stop(sprintf("markers must contain columns: %s", paste(required_cols, collapse = ", ")))
    }

    # Filter for specific cluster if specified
    if (!is.null(cluster)) {
        if (!("cluster" %in% colnames(markers))) {
            stop("markers does not have 'cluster' column. Did you use FindAllMarkers()?")
        }
        markers <- markers[markers$cluster == cluster, ]
        message(sprintf("Analyzing cluster %s (%d genes)", cluster, nrow(markers)))
    }

    # Select genes based on criteria
    if (!is.null(top_n)) {
        if (only.pos) {
            markers <- markers[order(-markers$avg_log2FC), ]
        } else {
            markers <- markers[order(-abs(markers$avg_log2FC)), ]
        }
        gene_list <- markers$gene[1:min(top_n, nrow(markers))]
        message(sprintf("Using top %d genes by log2FC", length(gene_list)))
    } else {
        if (only.pos) {
            sig_markers <- markers[markers$p_val_adj < pval_threshold &
                                   markers$avg_log2FC > logfc_threshold, ]
        } else {
            sig_markers <- markers[markers$p_val_adj < pval_threshold &
                                   abs(markers$avg_log2FC) > logfc_threshold, ]
        }
        gene_list <- sig_markers$gene
        message(sprintf("Using %d significant genes (padj<%.3f, |log2FC|>%.2f)",
                        length(gene_list), pval_threshold, logfc_threshold))
    }

    if (length(gene_list) < 5) {
        warning("Fewer than 5 genes selected. Enrichment analysis may not be reliable.")
    }

    return(gene_list)
}


#' Run ORA for All Clusters
#'
#' @param markers Data frame from FindAllMarkers()
#' @param enrich_fun Enrichment function to use: "enrichGO", "enrichKEGG", "enricher"
#' @param ... Additional parameters passed to the enrichment function
#'
#' @return List of enrichResult objects, one per cluster
#'
#' @examples
#' \dontrun{
#' markers <- FindAllMarkers(seurat_obj, only.pos = TRUE)
#'
#' # GO enrichment for all clusters
#' results <- run_ora_all_clusters(markers, enrich_fun = "enrichGO",
#'                                 org_db = org.Hs.eg.db, ont = "BP")
#'
#' # Access results
#' names(results)
#' head(as.data.frame(results[["0"]]))
#' }
run_ora_all_clusters <- function(
    markers,
    enrich_fun = "run_enrichGO",
    logfc_threshold = 0.25,
    pval_threshold = 0.05,
    top_n = NULL,
    ...
) {
    if (!("cluster" %in% colnames(markers))) {
        stop("markers must have 'cluster' column from FindAllMarkers()")
    }

    clusters <- unique(as.character(markers$cluster))
    message(sprintf("Running %s for %d clusters...", enrich_fun, length(clusters)))

    results <- list()

    for (cl in clusters) {
        message(sprintf("\n--- Processing cluster %s ---", cl))

        # Get gene list for this cluster
        gene_list <- run_ora_seurat(
            seurat_obj = NULL,
            markers = markers,
            cluster = cl,
            logfc_threshold = logfc_threshold,
            pval_threshold = pval_threshold,
            top_n = top_n
        )

        if (length(gene_list) < 5) {
            warning(sprintf("Too few genes for cluster %s (%d), skipping", cl, length(gene_list)))
            next
        }

        # Validate enrichment function against allowed list
        allowed_funs <- c("run_enrichGO", "run_enrichKEGG", "run_enricher",
                           "enrichGO", "enrichKEGG", "enricher")
        if (!(enrich_fun %in% allowed_funs)) {
            stop(sprintf(
                "Invalid enrich_fun '%s'. Must be one of: %s",
                enrich_fun,
                paste(allowed_funs, collapse = ", ")
            ))
        }

        # Run enrichment
        fun <- get(enrich_fun)
        tryCatch({
            result <- fun(gene_list = gene_list, ...)
            results[[cl]] <- result
        }, error = function(e) {
            warning(sprintf("Failed for cluster %s: %s", cl, e$message))
            results[[cl]] <- NULL
        })
    }

    # Remove NULL results
    results <- results[!sapply(results, is.null)]
    message(sprintf("\nCompleted! Successful for %d/%d clusters", length(results), length(clusters)))

    return(results)
}
