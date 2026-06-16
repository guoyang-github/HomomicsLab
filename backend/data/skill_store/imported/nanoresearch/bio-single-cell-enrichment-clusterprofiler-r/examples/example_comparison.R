# Multi-Cluster Comparison Example for clusterProfiler
#
# This example demonstrates how to compare enrichment across multiple cell clusters
# using compareCluster and visualization techniques.
#
# Author: Yang Guo
# Date: 2026-04-03

# ============================================================================
# Setup
# ============================================================================

# Install required packages
# BiocManager::install(c("clusterProfiler", "org.Hs.eg.db", "enrichplot", "GOSemSim"))

# Load libraries
library(clusterProfiler)
library(org.Hs.eg.db)
library(enrichplot)
library(ggplot2)
library(dplyr)
library(patchwork)

# Source skill scripts
source("../scripts/r/ora_analysis.R")
source("../scripts/r/compare_cluster.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# ============================================================================
# Create Example Gene Lists (simulating marker genes from different clusters)
# ============================================================================

cat("\n=== Creating example cluster gene lists ===\n")

# Simulate marker genes for different cell types
# In practice, these come from FindAllMarkers()
cluster_genes <- list(
    # T cells - immune response, T cell activation
    "T_cells" = c(
        "IL7R", "CD3D", "CD3E", "CD8A", "CD4", "CCR7", "LEF1",
        "GZMB", "PRF1", "IFNG", "IL2", "TBX21", "EOMES",
        "TCF7", "SELL", "CD28", "ICOS", "CD27"
    ),

    # B cells - B cell activation, antibody production
    "B_cells" = c(
        "CD79A", "CD79B", "MS4A1", "CD19", "CD22", "CD40",
        "BANK1", "BLK", "PAX5", "SPIB", "IGHD", "IGHM",
        "MZB1", "JCHAIN", "XBP1", "PRDM1"
    ),

    # Monocytes - inflammatory response, phagocytosis
    "Monocytes" = c(
        "CD14", "LYZ", "S100A9", "S100A8", "FCGR3A", "CSF1R",
        "CD68", "FCGR1A", "MARCO", "MPO", "ELANE", "AZU1",
        "TLR4", "TLR2", "NOD2", "MYD88"
    ),

    # NK cells - cytotoxicity, innate immunity
    "NK_cells" = c(
        "NCAM1", "FCGR3A", "NKG7", "GNLY", "PRF1", "GZMB", "GZMA",
        "KLRB1", "KLRD1", "KLRK1", "CD247", "XCL1", "XCL2",
        "CCL3", "CCL4", "IFNG"
    ),

    # DCs - antigen presentation
    "Dendritic_cells" = c(
        "CD1C", "CLEC10A", "FCER1A", "HLA-DRA", "HLA-DRB1",
        "CD74", "CD86", "CD83", "ITGAX", "ITGAM",
        "LY75", "CLEC9A", "XCR1", "CCL17", "CCL22"
    )
)

# Print summary
for (name in names(cluster_genes)) {
    cat(sprintf("  %s: %d genes\n", name, length(cluster_genes[[name]])))
}

# ============================================================================
# Example 1: Compare GO Enrichment Across Clusters
# ============================================================================

cat("\n=== Example 1: GO Comparison Across Clusters ===\n")

# Run compareCluster with GO BP
compare_go <- run_compareCluster(
    cluster_genes,
    fun = "enrichGO",
    OrgDb = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    pvalueCutoff = 0.05,
    pAdjustMethod = "BH"
)

if (!is.null(compare_go) && nrow(as.data.frame(compare_go)) > 0) {
    cat(sprintf("Found enrichment across %d clusters\n",
                length(unique(as.data.frame(compare_go)$Cluster))))

    # View top results
    cat("\nTop enriched terms by cluster:\n")
    df <- as.data.frame(compare_go)
    for (cluster in unique(df$Cluster)) {
        cluster_df <- df[df$Cluster == cluster, ]
        if (nrow(cluster_df) > 0) {
            cat(sprintf("\n%s: %s\n", cluster, cluster_df$Description[1]))
        }
    }

    # Visualize with dotplot
    p1 <- plot_enrichment_dot(
        compare_go,
        showCategory = 8,
        title = "GO BP Comparison Across Cell Types"
    )
    print(p1)
}

# ============================================================================
# Example 2: Compare KEGG Pathways
# ============================================================================

cat("\n=== Example 2: KEGG Pathway Comparison ===\n")

# Run compareCluster with KEGG
compare_kegg <- run_compareCluster(
    cluster_genes,
    fun = "enrichKEGG",
    organism = "hsa",
    keyType = "kegg",
    pvalueCutoff = 0.05
)

if (!is.null(compare_kegg) && nrow(as.data.frame(compare_kegg)) > 0) {
    cat("Found KEGG pathway enrichment\n")

    # Visualize
    p2 <- plot_enrichment_dot(
        compare_kegg,
        showCategory = 6,
        title = "KEGG Pathway Comparison"
    )
    print(p2)
}

# ============================================================================
# Example 3: Simplify GO Comparison Results
# ============================================================================

cat("\n=== Example 3: Simplify GO Results ===\n")

if (requireNamespace("GOSemSim", quietly = TRUE) &&
    !is.null(compare_go) && nrow(as.data.frame(compare_go)) > 0) {

    cat(sprintf("\nBefore simplification: %d terms\n",
                nrow(as.data.frame(compare_go))))

    # Simplify to remove redundant GO terms
    simplified <- simplify_compareCluster(
        compare_go,
        cutoff = 0.7,
        measure = "Wang"
    )

    cat(sprintf("After simplification: %d terms\n",
                nrow(as.data.frame(simplified))))

    # Visualize simplified results
    p3 <- plot_enrichment_dot(
        simplified,
        showCategory = 6,
        title = "Simplified GO Comparison"
    )
    print(p3)
} else {
    cat("GOSemSim not available, skipping simplification\n")
}

# ============================================================================
# Example 4: MSigDB Comparison
# ============================================================================

cat("\n=== Example 4: MSigDB Hallmark Comparison ===\n")

if (requireNamespace("msigdbr", quietly = TRUE)) {
    # Get Hallmark gene sets
    h_sets <- get_msigdb_genesets("Homo sapiens", "H")
    prepared <- prepare_msigdb_for_enrichment(h_sets)

    # Run compareCluster with enricher
    compare_msig <- run_compareCluster(
        cluster_genes,
        fun = "enricher",
        TERM2GENE = prepared$TERM2GENE,
        TERM2NAME = prepared$TERM2NAME,
        pvalueCutoff = 0.05
    )

    if (!is.null(compare_msig) && nrow(as.data.frame(compare_msig)) > 0) {
        cat("Found MSigDB Hallmark enrichment\n")

        # Visualize
        p4 <- plot_enrichment_dot(
            compare_msig,
            showCategory = 6,
            title = "MSigDB Hallmark Comparison"
        ) + theme(axis.text.y = element_text(size = 8))
        print(p4)
    }
} else {
    cat("msigdbr not installed, skipping MSigDB comparison\n")
}

# ============================================================================
# Example 5: Custom Comparison Layout
# ============================================================================

cat("\n=== Example 5: Custom Visualization Layout ===\n")

if (!is.null(compare_go) && nrow(as.data.frame(compare_go)) > 0) {
    # Create a custom dotplot with different aesthetics
    p5 <- dotplot(
        compare_go,
        showCategory = 5,
        color = "p.adjust",
        size = "Count"
    ) +
        scale_color_gradient(low = "red", high = "blue") +
        ggtitle("Custom Styled Comparison") +
        theme(
            plot.title = element_text(size = 14, hjust = 0.5),
            axis.text.y = element_text(size = 9),
            strip.text = element_text(size = 10, face = "bold")
        )
    print(p5)
}

# ============================================================================
# Example 6: Merge Individual enrichResults
# ============================================================================

cat("\n=== Example 6: Merge Individual Results ===\n")

# Run separate enrichments and merge
cat("Running separate enrichments...\n")

enrich_list <- list()
for (name in names(cluster_genes)) {
    result <- tryCatch({
        run_enrichGO(
            cluster_genes[[name]],
            org_db = org.Hs.eg.db,
            ont = "BP",
            pvalueCutoff = 0.1
        )
    }, error = function(e) NULL)

    if (!is.null(result) && nrow(as.data.frame(result)) > 0) {
        enrich_list[[name]] <- result
        cat(sprintf("  %s: %d terms\n", name, nrow(as.data.frame(result))))
    }
}

# Merge results
if (length(enrich_list) > 0) {
    merged <- merge_enrichResults(enrich_list)
    cat(sprintf("\nMerged results from %d clusters\n", length(enrich_list)))

    # Visualize merged results
    if (nrow(as.data.frame(merged)) > 0) {
        p6 <- dotplot(merged, showCategory = 6) +
            ggtitle("Merged Enrichment Results")
        print(p6)
    }
}

# ============================================================================
# Example 7: Export Comparison Results
# ============================================================================

cat("\n=== Example 7: Export Results ===\n")

if (!is.null(compare_go)) {
    # Get data frame
df <- as.data.frame(compare_go)

    cat(sprintf("Comparison results: %d rows\n", nrow(df)))
    cat("Columns:", paste(colnames(df), collapse = ", "), "\n")

    # Example exports (uncomment to save)
    # export_enrichment(compare_go, "cluster_comparison.csv")
    # export_enrichment(compare_go, "cluster_comparison.xlsx")

    cat("Export functions demonstrated (files not saved)\n")
}

# ============================================================================
# Example 8: Create Summary Table
# ============================================================================

cat("\n=== Example 8: Create Summary Table ===\n")

if (!is.null(compare_go)) {
    df <- as.data.frame(compare_go)

    # Summarize by cluster
    summary_table <- df %>%
        group_by(Cluster) %>%
        summarise(
            n_terms = n(),
            top_term = Description[1],
            top_pvalue = min(p.adjust),
            avg_gene_count = mean(Count)
        )

    cat("\nSummary by cluster:\n")
    print(summary_table)
}

cat("\n=== Multi-cluster comparison examples completed! ===\n")
