# Utility functions for clusterProfiler enrichment analysis
#
# Author: Yang Guo
# Date: 2026-04-03

#' Convert Gene IDs using clusterProfiler::bitr
#'
#' @param genes Character vector of gene IDs
#' @param fromType Source ID type: "SYMBOL", "ENTREZID", "ENSEMBL", etc.
#' @param toType Target ID type(s): can be single string or vector
#' @param org_db OrgDb object (e.g., org.Hs.eg.db)
#' @param drop Drop unmapped genes (default: TRUE)
#'
#' @return Data frame with mapped IDs
#'
#' @examples
#' \dontrun{
#' library(org.Hs.eg.db)
#'
#' # SYMBOL to ENTREZID
#' mapped <- convert_gene_ids(c("TP53", "BRCA1"), "SYMBOL", "ENTREZID", org.Hs.eg.db)
#'
#' # Multiple target types
#' mapped <- convert_gene_ids(c("TP53", "BRCA1"), "SYMBOL",
#'                            c("ENTREZID", "ENSEMBL"), org.Hs.eg.db)
#' }
convert_gene_ids <- function(
    genes,
    fromType,
    toType,
    org_db,
    drop = TRUE
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler")
    }

    message(sprintf("Converting %d genes from %s to %s...",
                    length(genes), fromType, paste(toType, collapse = ", ")))

    result <- clusterProfiler::bitr(
        genes,
        fromType = fromType,
        toType = toType,
        OrgDb = org_db,
        drop = drop
    )

    message(sprintf("Successfully mapped %d/%d genes (%.1f%%)",
                    nrow(result), length(genes),
                    100 * nrow(result) / length(genes)))

    return(result)
}


#' Get MSigDB Gene Sets for Enrichment
#'
#' @param species Species name: "Homo sapiens" or "Mus musculus"
#' @param category MSigDB category: "H" (Hallmark), "C1"-"C8"
#' @param subcategory Subcategory (optional, e.g., "KEGG", "REACTOME")
#'
#' @return Data frame with columns: gs_name, gene_symbol (and more)
#'
#' @examples
#' \dontrun{
#' # Hallmark gene sets
#' h_sets <- get_msigdb_genesets("Homo sapiens", "H")
#'
#' # KEGG pathways from C2
#' kegg_sets <- get_msigdb_genesets("Homo sapiens", "C2", "KEGG")
#'
#' # Reactome pathways
#' reactome_sets <- get_msigdb_genesets("Homo sapiens", "C2", "REACTOME")
#'
#' # GO BP
#' go_bp_sets <- get_msigdb_genesets("Homo sapiens", "C5", "GO:BP")
#' }
get_msigdb_genesets <- function(
    species = "Homo sapiens",
    category = "H",
    subcategory = NULL
) {
    if (!requireNamespace("msigdbr", quietly = TRUE)) {
        stop("Please install msigdbr: install.packages('msigdbr')")
    }

    message(sprintf("Fetching MSigDB %s gene sets for %s...", category, species))

    if (!is.null(subcategory)) {
        gs <- msigdbr::msigdbr(species = species, category = category, subcategory = subcategory)
    } else {
        gs <- msigdbr::msigdbr(species = species, category = category)
    }

    message(sprintf("Retrieved %d gene sets", length(unique(gs$gs_name))))

    return(gs)
}


#' Prepare MSigDB for clusterProfiler
#'
#' @param msigdb_df Data frame from get_msigdb_genesets()
#' @param id_type Gene ID type to use: "gene_symbol" (default) or "entrez_gene"
#'
#' @return List with TERM2GENE and TERM2NAME data frames
#'
#' @examples
#' \dontrun{
#' h_sets <- get_msigdb_genesets("Homo sapiens", "H")
#' term2gene <- prepare_msigdb_for_enrichment(h_sets)
#'
#' # Run enrichment
#' result <- run_enricher(genes, term2gene$TERM2GENE, term2gene$TERM2NAME)
#' }
prepare_msigdb_for_enrichment <- function(
    msigdb_df,
    id_type = "gene_symbol"
) {
    if (!id_type %in% colnames(msigdb_df)) {
        stop(sprintf("id_type '%s' not found in data frame. Available: %s",
                     id_type, paste(colnames(msigdb_df), collapse = ", ")))
    }

    # Create TERM2GENE
    TERM2GENE <- msigdb_df[, c("gs_name", id_type)]
    colnames(TERM2GENE) <- c("term", "gene")

    # Create TERM2NAME (using gs_description if available)
    if ("gs_description" %in% colnames(msigdb_df)) {
        TERM2NAME <- unique(msigdb_df[, c("gs_name", "gs_description")])
        colnames(TERM2NAME) <- c("term", "name")
    } else {
        TERM2NAME <- NULL
    }

    return(list(
        TERM2GENE = TERM2GENE,
        TERM2NAME = TERM2NAME
    ))
}


#' Simplify GO Enrichment Results
#'
#' Remove redundant GO terms based on semantic similarity.
#'
#' @param enrich_result enrichResult object from enrichGO or gseGO
#' @param cutoff Similarity cutoff for redundancy (default: 0.7)
#' @param by Feature to select representative term (default: "p.adjust")
#' @param select_fun Function to select representative (default: min)
#' @param measure Semantic similarity measure: "Wang", "Rel", "Resnik", "Lin", "Jiang"
#' @param semData GOSemSim data object (optional, will be created if NULL)
#'
#' @return Simplified enrichResult object
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db, ont = "BP")
#'
#' # Simplify with default settings
#' simplified <- simplify_go_results(result)
#'
#' # More aggressive simplification
#' simplified <- simplify_go_results(result, cutoff = 0.5)
#'
#' # Use Resnik similarity
#' simplified <- simplify_go_results(result, measure = "Resnik")
#' }
simplify_go_results <- function(
    enrich_result,
    cutoff = 0.7,
    by = "p.adjust",
    select_fun = min,
    measure = "Wang",
    semData = NULL
) {
    if (!requireNamespace("clusterProfiler", quietly = TRUE)) {
        stop("Please install clusterProfiler")
    }

    if (!inherits(enrich_result, c("enrichResult", "gseaResult"))) {
        stop("Input must be enrichResult or gseaResult object")
    }

    # Check if ontology is supported
    ont <- if (inherits(enrich_result, "enrichResult")) {
        enrich_result@ontology
    } else {
        enrich_result@setType
    }

    if (!ont %in% c("BP", "MF", "CC", "GOALL")) {
        stop("simplify only works with GO enrichment results")
    }

    message(sprintf("Simplifying GO results (ont=%s, cutoff=%.2f, measure=%s)...",
                    ont, cutoff, measure))

    result <- clusterProfiler::simplify(
        enrich_result,
        cutoff = cutoff,
        by = by,
        select_fun = select_fun,
        measure = measure,
        semData = semData
    )

    before <- nrow(as.data.frame(enrich_result))
    after <- nrow(as.data.frame(result))
    message(sprintf("Simplified from %d to %d terms (%.1f%% reduction)",
                    before, after, 100 * (before - after) / before))

    return(result)
}


#' Extract Top Terms from Enrichment Results
#'
#' @param enrich_result enrichResult, gseaResult, or compareClusterResult
#' @param n Number of top terms to extract (default: 10)
#' @param by Sort by: "p.adjust", "pvalue", "Count", "GeneRatio"
#'
#' @return Data frame with top terms
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#'
#' # Top 10 by adjusted p-value
#' top10 <- get_top_terms(result, n = 10)
#'
#' # Top 20 by gene count
#' top20 <- get_top_terms(result, n = 20, by = "Count")
#' }
get_top_terms <- function(
    enrich_result,
    n = 10,
    by = "p.adjust"
) {
    df <- as.data.frame(enrich_result)

    if (nrow(df) == 0) {
        warning("No terms in result")
        return(df)
    }

    # Handle compareClusterResult
    if (inherits(enrich_result, "compareClusterResult")) {
        # Group by cluster
        clusters <- unique(df$Cluster)
        result_list <- lapply(clusters, function(cl) {
            sub_df <- df[df$Cluster == cl, ]
            sub_df <- sub_df[order(sub_df[[by]]), ]
            head(sub_df, n)
        })
        return(do.call(rbind, result_list))
    }

    # For enrichResult/gseaResult
    df <- df[order(df[[by]]), ]
    return(head(df, n))
}


#' Filter Enrichment Results
#'
#' @param enrich_result enrichResult or gseaResult object
#' @param pvalueCutoff P-value cutoff (optional)
#' @param qvalueCutoff Q-value cutoff (optional)
#' @param minCount Minimum gene count (optional)
#' @param maxCount Maximum gene count (optional)
#' @param term_contains Character vector: keep terms containing these strings
#'
#' @return Filtered enrichResult object
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#'
#' # Filter by p-value
#' filtered <- filter_enrichment(result, pvalueCutoff = 0.01)
#'
#' # Filter by term content
#' immune_terms <- filter_enrichment(result, term_contains = c("immune", "inflammatory"))
#' }
filter_enrichment <- function(
    enrich_result,
    pvalueCutoff = NULL,
    qvalueCutoff = NULL,
    minCount = NULL,
    maxCount = NULL,
    term_contains = NULL
) {
    if (!inherits(enrich_result, c("enrichResult", "gseaResult", "compareClusterResult"))) {
        stop("Input must be enrichResult, gseaResult, or compareClusterResult")
    }

    df <- as.data.frame(enrich_result)
    original_n <- nrow(df)

    # Apply filters
    if (!is.null(pvalueCutoff) && "pvalue" %in% colnames(df)) {
        df <- df[df$pvalue < pvalueCutoff, ]
    }

    if (!is.null(qvalueCutoff) && "qvalue" %in% colnames(df)) {
        df <- df[df$qvalue < qvalueCutoff, ]
    }

    if (!is.null(minCount) && "Count" %in% colnames(df)) {
        df <- df[df$Count >= minCount, ]
    }

    if (!is.null(maxCount) && "Count" %in% colnames(df)) {
        df <- df[df$Count <= maxCount, ]
    }

    if (!is.null(term_contains) && "Description" %in% colnames(df)) {
        pattern <- paste(term_contains, collapse = "|")
        df <- df[grepl(pattern, df$Description, ignore.case = TRUE), ]
    }

    # Update result object
    if (inherits(enrich_result, "compareClusterResult")) {
        enrich_result@compareClusterResult <- df
    } else {
        enrich_result@result <- df
    }

    message(sprintf("Filtered from %d to %d terms", original_n, nrow(df)))

    return(enrich_result)
}


#' Export Enrichment Results
#'
#' @param enrich_result enrichResult, gseaResult, or compareClusterResult
#' @param file Output file path (.csv, .xlsx, or .txt)
#' @param sheet_name For Excel files, sheet name (default: "Enrichment")
#' @param ... Additional arguments passed to write functions
#'
#' @return Invisible result data frame
#'
#' @examples
#' \dontrun{
#' result <- run_enrichGO(genes, org.Hs.eg.db)
#'
#' # Export to CSV
#' export_enrichment(result, "go_enrichment.csv")
#'
#' # Export to Excel
#' export_enrichment(result, "go_enrichment.xlsx")
#' }
export_enrichment <- function(
    enrich_result,
    file,
    sheet_name = "Enrichment",
    ...
) {
    df <- as.data.frame(enrich_result)

    if (nrow(df) == 0) {
        warning("No results to export")
        return(invisible(df))
    }

    # Determine format from extension
    ext <- tolower(tools::file_ext(file))

    if (ext == "csv") {
        write.csv(df, file, row.names = FALSE, ...)
    } else if (ext == "xlsx") {
        if (!requireNamespace("openxlsx", quietly = TRUE)) {
            stop("Please install openxlsx: install.packages('openxlsx')")
        }
        # openxlsx >= 4.2 uses 'sheet'; older versions use 'sheetName'
        tryCatch(
            openxlsx::write.xlsx(df, file, sheet = sheet_name, ...),
            error = function(e) {
                openxlsx::write.xlsx(df, file, sheetName = sheet_name, ...)
            }
        )
    } else if (ext == "txt" || ext == "tsv") {
        write.table(df, file, sep = "\t", row.names = FALSE, quote = FALSE, ...)
    } else {
        stop("Unsupported file format. Use .csv, .xlsx, .txt, or .tsv")
    }

    message(sprintf("Exported %d rows to %s", nrow(df), file))
    return(invisible(df))
}


#' Create Gene List from Seurat Object
#'
#' Utility to extract genes for enrichment from Seurat marker analysis.
#'
#' @param seurat_obj Seurat object
#' @param cluster Character: specific cluster (NULL for all cells)
#' @param group.by Metadata column for grouping
#' @param only.pos Only positive markers (default: TRUE)
#' @param min.pct Minimum expression percentage (default: 0.25)
#' @param logfc.threshold Minimum log2 fold change (default: 0.25)
#'
#' @return Character vector of gene symbols
#'
#' @examples
#' \dontrun{
#' # Get all positive markers
#' genes <- create_gene_list_seurat(seurat_obj, only.pos = TRUE)
#'
#' # Get markers for specific cluster
#' cluster0_genes <- create_gene_list_seurat(seurat_obj, cluster = "0")
#' }
create_gene_list_seurat <- function(
    seurat_obj,
    cluster = NULL,
    group.by = "seurat_clusters",
    only.pos = TRUE,
    min.pct = 0.25,
    logfc.threshold = 0.25
) {
    if (!requireNamespace("Seurat", quietly = TRUE)) {
        stop("Please install Seurat")
    }

    # Save original identities to restore later
    original_idents <- SeuratObject::Idents(seurat_obj)

    if (!is.null(cluster)) {
        # Find markers for specific cluster
        SeuratObject::Idents(seurat_obj) <- group.by
        markers <- Seurat::FindMarkers(
            seurat_obj,
            ident.1 = cluster,
            only.pos = only.pos,
            min.pct = min.pct,
            logfc.threshold = logfc.threshold
        )
    } else {
        # Find all markers
        SeuratObject::Idents(seurat_obj) <- group.by
        markers <- Seurat::FindAllMarkers(
            seurat_obj,
            only.pos = only.pos,
            min.pct = min.pct,
            logfc.threshold = logfc.threshold
        )
    }

    # Restore original identities
    SeuratObject::Idents(seurat_obj) <- original_idents

    genes <- rownames(markers)
    message(sprintf("Extracted %d genes from Seurat object", length(genes)))

    return(genes)
}
