# GSEA (Gene Set Enrichment Analysis) using clusterProfiler
#
# Author: Yang Guo
# Date: 2026-04-03
#
# This script provides GSEA functions for single-cell data:
# - gseGO: GO GSEA
# - gseKEGG: KEGG pathway GSEA
# - GSEA: Universal GSEA with custom gene sets

#' Run GO Gene Set Enrichment Analysis (GSEA)
#'
#' @param gene_list Named numeric vector of gene-level statistics (e.g., log2FC).
#'                  Names should be gene symbols or Entrez IDs.
#' @param org_db OrgDb object (e.g., org.Hs.eg.db, org.Mm.eg.db)
#' @param keyType Gene ID type: "SYMBOL", "ENTREZID", "ENSEMBL", etc.
#' @param ont GO ontology: "BP", "MF", "CC", or "ALL"
#' @param exponent Weight for each step in GSEA calculation (default: 1)
#' @param minGSSize Minimum gene set size for testing
#' @param maxGSSize Maximum gene set size for testing
#' @param pvalueCutoff P-value cutoff for significant results
#' @param pAdjustMethod Multiple testing correction method
#' @param method Method for calculating p-values: "multilevel", "monte carlo", "fgsea"
#' @param verbose Print progress messages
#'
#' @return gseaResult object
#'
#' @examples
#' \dontrun{
#' library(org.Hs.eg.db)
#'
#' # Create ranked gene list (e.g., from differential expression)
#' gene_list <- c(TP53 = 2.5, BRCA1 = -1.8, EGFR = 3.2, PTEN = -2.1, MYC = 1.5)
#' gene_list <- sort(gene_list, decreasing = TRUE)
#'
#' result <- run_gseGO(gene_list, org.Hs.eg.db, ont = "BP")
#' }
run_gseGO <- function(
    gene_list,
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    exponent = 1,
    minGSSize = 10,
    maxGSSize = 500,
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH",
    method = "multilevel",
    verbose = TRUE
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler: BiocManager::install('clusterProfiler')")
    }

    # Validate inputs
    ont <- match.arg(toupper(ont), c("BP", "MF", "CC", "ALL"))

    if (is.null(names(gene_list))) {
        stop("gene_list must be a named vector with gene IDs as names")
    }

    # Ensure sorted by decreasing value
    gene_list <- sort(gene_list, decreasing = TRUE)

    message(sprintf("Running GO GSEA for %d genes (ont=%s, keyType=%s)...",
                    length(gene_list), ont, keyType))

    result <- clusterProfiler::gseGO(
        geneList = gene_list,
        OrgDb = org_db,
        keyType = keyType,
        ont = ont,
        exponent = exponent,
        minGSSize = minGSSize,
        maxGSSize = maxGSSize,
        pvalueCutoff = pvalueCutoff,
        pAdjustMethod = pAdjustMethod,
        method = method,
        verbose = verbose
    )

    if (is.null(result) || nrow(as.data.frame(result)) == 0) {
        warning("No significant GO terms found. Consider relaxing cutoffs.")
    } else {
        message(sprintf("Found %d significant GO terms", nrow(as.data.frame(result))))
    }

    return(result)
}


#' Run KEGG Gene Set Enrichment Analysis (GSEA)
#'
#' @param gene_list Named numeric vector of gene-level statistics.
#'                  Names should be Entrez IDs (or gene symbols if convert_ids=TRUE)
#' @param organism Organism code: "hsa" (human), "mmu" (mouse), etc.
#' @param keyType Gene ID type for KEGG
#' @param exponent Weight for each step in GSEA calculation
#' @param minGSSize Minimum gene set size for testing
#' @param maxGSSize Maximum gene set size for testing
#' @param pvalueCutoff P-value cutoff for significant results
#' @param pAdjustMethod Multiple testing correction method
#' @param method Method for calculating p-values
#' @param use_internal_data Use KEGG.db instead of online KEGG data
#' @param convert_ids Convert gene symbols to Entrez IDs
#' @param org_db OrgDb object for ID conversion
#' @param verbose Print progress messages
#'
#' @return gseaResult object
#'
#' @examples
#' \dontrun{
#' # Using Entrez IDs
#' gene_list <- c(`7157` = 2.5, `672` = -1.8, `1956` = 3.2)
#' gene_list <- sort(gene_list, decreasing = TRUE)
#' result <- run_gseKEGG(gene_list, organism = "hsa")
#'
#' # Using gene symbols with conversion
#' gene_list <- c(TP53 = 2.5, BRCA1 = -1.8, EGFR = 3.2)
#' result <- run_gseKEGG(gene_list, organism = "hsa",
#'                       convert_ids = TRUE, org_db = org.Hs.eg.db)
#' }
run_gseKEGG <- function(
    gene_list,
    organism = "hsa",
    keyType = "kegg",
    exponent = 1,
    minGSSize = 10,
    maxGSSize = 500,
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH",
    method = "multilevel",
    use_internal_data = FALSE,
    convert_ids = FALSE,
    org_db = NULL,
    verbose = TRUE
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler")
    }

    if (is.null(names(gene_list))) {
        stop("gene_list must be a named vector with gene IDs as names")
    }

    # Convert gene symbols to Entrez IDs if needed
    if (convert_ids) {
        if (is.null(org_db)) {
            stop("org_db must be provided when convert_ids=TRUE")
        }
        message("Converting gene symbols to Entrez IDs...")

        gene_df <- data.frame(
            SYMBOL = names(gene_list),
            score = gene_list
        )

        converted <- clusterProfiler::bitr(
            gene_df$SYMBOL,
            fromType = "SYMBOL",
            toType = "ENTREZID",
            OrgDb = org_db
        )

        if (is.null(converted) || nrow(converted) == 0) {
            stop("No genes could be mapped to Entrez IDs")
        }

        # Merge scores with converted IDs
        merged <- merge(gene_df, converted, by = "SYMBOL")

        # Handle duplicates by taking mean
        gene_list <- tapply(merged$score, merged$ENTREZID, mean)
        gene_list <- sort(gene_list, decreasing = TRUE)

        keyType <- "ncbi-geneid"
        message(sprintf("Converted to %d Entrez IDs", length(gene_list)))
    } else {
        gene_list <- sort(gene_list, decreasing = TRUE)
    }

    message(sprintf("Running KEGG GSEA for %d genes (organism=%s)...",
                    length(gene_list), organism))

    result <- clusterProfiler::gseKEGG(
        geneList = gene_list,
        organism = organism,
        keyType = keyType,
        exponent = exponent,
        minGSSize = minGSSize,
        maxGSSize = maxGSSize,
        pvalueCutoff = pvalueCutoff,
        pAdjustMethod = pAdjustMethod,
        method = method,
        use_internal_data = use_internal_data,
        verbose = verbose
    )

    if (is.null(result) || nrow(as.data.frame(result)) == 0) {
        warning("No significant KEGG pathways found. Consider relaxing cutoffs.")
    } else {
        message(sprintf("Found %d significant KEGG pathways", nrow(as.data.frame(result))))
    }

    return(result)
}


#' Run Universal Gene Set Enrichment Analysis (GSEA)
#'
#' @param gene_list Named numeric vector of gene-level statistics.
#'                  Names should be gene symbols or IDs.
#' @param term2gene Data frame with columns: term ID, gene ID
#' @param term2name Data frame with columns: term ID, term name (optional)
#' @param exponent Weight for each step in GSEA calculation
#' @param minGSSize Minimum gene set size for testing
#' @param maxGSSize Maximum gene set size for testing
#' @param pvalueCutoff P-value cutoff for significant results
#' @param pAdjustMethod Multiple testing correction method
#' @param method Method for calculating p-values
#' @param verbose Print progress messages
#'
#' @return gseaResult object
#'
#' @examples
#' \dontrun{
#' # Custom gene sets
#' term2gene <- data.frame(
#'     term = c("Pathway1", "Pathway1", "Pathway2", "Pathway2", "Pathway2"),
#'     gene = c("TP53", "BRCA1", "EGFR", "MYC", "KRAS")
#' )
#'
#' gene_list <- c(TP53 = 2.5, BRCA1 = -1.8, EGFR = 3.2, MYC = 1.5, KRAS = -2.0)
#' gene_list <- sort(gene_list, decreasing = TRUE)
#'
#' result <- run_GSEA(gene_list, term2gene)
#'
#' # MSigDB Hallmark
#' library(msigdbr)
#' msigdb_h <- msigdbr(species = "Homo sapiens", category = "H")
#' term2gene <- msigdb_h[, c("gs_name", "gene_symbol")]
#' result <- run_GSEA(gene_list, term2gene)
#' }
run_GSEA <- function(
    gene_list,
    term2gene,
    term2name = NULL,
    exponent = 1,
    minGSSize = 10,
    maxGSSize = 500,
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH",
    method = "multilevel",
    verbose = TRUE
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler")
    }

    if (is.null(names(gene_list))) {
        stop("gene_list must be a named vector with gene IDs as names")
    }

    # Ensure sorted
    gene_list <- sort(gene_list, decreasing = TRUE)

    message(sprintf("Running GSEA for %d genes...", length(gene_list)))

    result <- clusterProfiler::GSEA(
        geneList = gene_list,
        TERM2GENE = term2gene,
        TERM2NAME = term2name,
        exponent = exponent,
        minGSSize = minGSSize,
        maxGSSize = maxGSSize,
        pvalueCutoff = pvalueCutoff,
        pAdjustMethod = pAdjustMethod,
        method = method,
        verbose = verbose
    )

    if (is.null(result) || nrow(as.data.frame(result)) == 0) {
        warning("No significant gene sets found. Consider relaxing cutoffs.")
    } else {
        message(sprintf("Found %d significant gene sets", nrow(as.data.frame(result))))
    }

    return(result)
}


#' Prepare Ranked Gene List from Seurat DEG Results
#'
#' @param markers Data frame from FindAllMarkers() or FindMarkers()
#' @param cluster Character: specific cluster to analyze (NULL for all)
#' @param rank_by Metric to use for ranking: "log2FC" (default), "pval", "avg_expr"
#' @param signed Use signed values (default: TRUE)
#'
#' @return Named numeric vector sorted by rank
#'
#' @examples
#' \dontrun{
#' markers <- FindAllMarkers(seurat_obj, only.pos = FALSE)
#'
#' # Prepare ranked list for cluster 0
#' ranked_genes <- prepare_ranked_list(markers, cluster = "0")
#'
#' # Run GSEA
#' result <- run_gseGO(ranked_genes, org.Hs.eg.db, ont = "BP")
#' }
prepare_ranked_list <- function(
    markers,
    cluster = NULL,
    rank_by = "log2FC",
    signed = TRUE
) {
    if (!is.data.frame(markers)) {
        stop("markers must be a data frame")
    }

    required_cols <- c("gene", "avg_log2FC")
    if (!all(required_cols %in% colnames(markers))) {
        stop(sprintf("markers must contain columns: %s", paste(required_cols, collapse = ", ")))
    }

    # Filter for specific cluster
    if (!is.null(cluster)) {
        if (!("cluster" %in% colnames(markers))) {
            stop("markers does not have 'cluster' column")
        }
        markers <- markers[markers$cluster == cluster, ]
    }

    # Calculate ranking metric
    if (rank_by == "log2FC") {
        scores <- markers$avg_log2FC
    } else if (rank_by == "pval") {
        # Transform p-values (smaller = more significant = higher rank)
        if (!("p_val" %in% colnames(markers))) {
            stop("markers must have 'p_val' column for rank_by='pval'")
        }
        scores <- -log10(markers$p_val) * sign(markers$avg_log2FC)
    } else if (rank_by == "avg_expr") {
        if (!("avg_expr" %in% colnames(markers))) {
            stop("markers must have 'avg_expr' column")
        }
        scores <- markers$avg_expr * sign(markers$avg_log2FC)
    } else {
        stop("rank_by must be one of: 'log2FC', 'pval', 'avg_expr'")
    }

    if (!signed) {
        scores <- abs(scores)
    }

    # Create named vector and sort
    gene_list <- setNames(scores, markers$gene)
    gene_list <- sort(gene_list, decreasing = TRUE)

    # Remove NA and Inf values
    gene_list <- gene_list[is.finite(gene_list) & !is.na(gene_list)]

    message(sprintf("Prepared ranked list with %d genes", length(gene_list)))
    return(gene_list)
}


#' Run GSEA for All Clusters
#'
#' @param markers Data frame from FindAllMarkers()
#' @param gsea_fun GSEA function to use: "gseGO", "gseKEGG", "GSEA"
#' @param ... Additional parameters passed to the GSEA function
#'
#' @return List of gseaResult objects
#'
#' @examples
#' \dontrun{
#' markers <- FindAllMarkers(seurat_obj, only.pos = FALSE)
#'
#' # GO GSEA for all clusters
#' results <- run_gsea_all_clusters(markers, gsea_fun = "gseGO",
#'                                   org_db = org.Hs.eg.db, ont = "BP")
#' }
run_gsea_all_clusters <- function(
    markers,
    gsea_fun = "run_gseGO",
    rank_by = "log2FC",
    signed = TRUE,
    min_genes = 10,
    ...
) {
    if (!("cluster" %in% colnames(markers))) {
        stop("markers must have 'cluster' column from FindAllMarkers()")
    }

    clusters <- unique(as.character(markers$cluster))
    message(sprintf("Running %s for %d clusters...", gsea_fun, length(clusters)))

    results <- list()

    for (cl in clusters) {
        message(sprintf("\n--- Processing cluster %s ---", cl))

        # Prepare ranked gene list
        gene_list <- prepare_ranked_list(
            markers,
            cluster = cl,
            rank_by = rank_by,
            signed = signed
        )

        if (length(gene_list) < min_genes) {
            warning(sprintf("Too few genes for cluster %s (%d < %d), skipping",
                            cl, length(gene_list), min_genes))
            next
        }

        # Run GSEA
        fun <- get(gsea_fun)
        tryCatch({
            result <- fun(gene_list = gene_list, ...)
            results[[cl]] <- result
        }, error = function(e) {
            warning(sprintf("Failed for cluster %s: %s", cl, e$message))
            results[[cl]] <- NULL
        })
    }

    results <- results[!sapply(results, is.null)]
    message(sprintf("\nCompleted! Successful for %d/%d clusters", length(results), length(clusters)))

    return(results)
}
