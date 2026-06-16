# Seurat Integration Example for clusterProfiler
#
# This example demonstrates how to use clusterProfiler with Seurat objects
# for single-cell enrichment analysis.
#
# Note: This example uses simulated data. Replace with your actual Seurat object.
#
# Author: Yang Guo
# Date: 2026-04-03

# ============================================================================
# Setup
# ============================================================================

# Install required packages
# BiocManager::install(c("Seurat", "clusterProfiler", "org.Hs.eg.db", "enrichplot"))

# Load libraries
library(Seurat)
library(clusterProfiler)
library(org.Hs.eg.db)
library(enrichplot)
library(ggplot2)
library(dplyr)

# Source skill scripts
source("../scripts/r/ora_analysis.R")
source("../scripts/r/gsea_analysis.R")
source("../scripts/r/compare_cluster.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# ============================================================================
# Create Example Seurat Object (or load your own)
# ============================================================================

cat("\n=== Creating example Seurat object ===\n")

# Simulate count data
set.seed(42)
n_cells <- 500
n_genes <- 2000

counts <- matrix(
    rpois(n_cells * n_genes, lambda = 0.5),
    nrow = n_genes,
    ncol = n_cells
)
rownames(counts) <- paste0("GENE", 1:n_genes)
colnames(counts) <- paste0("CELL", 1:n_cells)

# Add some marker genes with cluster-specific expression
marker_genes <- list(
    "CD4_T_cell" = c("IL7R", "CD4", "CD3D", "CD3E", "CCR7"),
    "CD8_T_cell" = c("CD8A", "CD8B", "CD3D", "GZMB", "PRF1"),
    "B_cell" = c("CD79A", "CD79B", "MS4A1", "CD19"),
    "Monocyte" = c("CD14", "LYZ", "S100A9", "FCGR3A")
)

# Replace some genes with marker names
for (i in seq_along(marker_genes)) {
    genes <- marker_genes[[i]]
    idx <- (i-1) * 5 + 1:5
    rownames(counts)[idx] <- genes
}

# Create Seurat object
seurat_obj <- CreateSeuratObject(counts = counts, project = "Example")

# Add simulated clusters
seurat_obj$seurat_clusters <- factor(sample(0:3, n_cells, replace = TRUE))
Idents(seurat_obj) <- "seurat_clusters"

# Normalize
seurat_obj <- NormalizeData(seurat_obj)
seurat_obj <- FindVariableFeatures(seurat_obj, nfeatures = 500)
seurat_obj <- ScaleData(seurat_obj)

# Add cluster-specific expression for markers
# Seurat v5 compatible: modify layer data via replacement function
for (cluster in 0:3) {
    cell_idx <- which(seurat_obj$seurat_clusters == cluster)
    if (length(cell_idx) > 0 && cluster < length(marker_genes)) {
        marker_names <- marker_genes[[cluster + 1]]
        data_layer <- SeuratObject::LayerData(seurat_obj, assay = "RNA", layer = "data")
        for (gene in marker_names) {
            if (gene %in% rownames(seurat_obj)) {
                data_layer[gene, cell_idx] <- data_layer[gene, cell_idx] + 2
            }
        }
        SeuratObject::LayerData(seurat_obj, assay = "RNA", layer = "data") <- data_layer
    }
}

cat(sprintf("Created Seurat object with %d cells and %d genes\n",
            ncol(seurat_obj), nrow(seurat_obj)))
cat("Clusters:", levels(seurat_obj$seurat_clusters), "\n")

# ============================================================================
# Find Markers
# ============================================================================

cat("\n=== Finding cluster markers ===\n")

# Find all markers
markers <- FindAllMarkers(
    seurat_obj,
    only.pos = TRUE,
    min.pct = 0.1,
    logfc.threshold = 0.25
)

cat(sprintf("Found %d marker genes across all clusters\n", nrow(markers)))

# ============================================================================
# Example 1: ORA for Specific Cluster
# ============================================================================

cat("\n=== Example 1: ORA for Cluster 0 ===\n")

# Extract genes for cluster 0
cluster0_genes <- run_ora_seurat(
    seurat_obj,
    markers,
    cluster = "0",
    logfc_threshold = 0.25,
    pval_threshold = 0.05
)

cat(sprintf("Selected %d genes for cluster 0\n", length(cluster0_genes)))

if (length(cluster0_genes) >= 5) {
    # GO enrichment
    go_result <- run_enrichGO(
        gene_list = cluster0_genes,
        org_db = org.Hs.eg.db,
        keyType = "SYMBOL",
        ont = "BP",
        pvalueCutoff = 0.1
    )

    if (!is.null(go_result) && nrow(as.data.frame(go_result)) > 0) {
        cat("\nTop GO terms for cluster 0:\n")
        print(head(as.data.frame(go_result), 5)[, c("Description", "p.adjust", "Count")])

        # Visualize
        p1 <- plot_enrichment_dot(go_result, showCategory = 10,
                                   title = "Cluster 0: GO BP")
        print(p1)
    }
}

# ============================================================================
# Example 2: ORA for All Clusters
# ============================================================================

cat("\n=== Example 2: ORA for All Clusters ===\n")

# Run GO enrichment for all clusters
all_results <- run_ora_all_clusters(
    markers,
    enrich_fun = "run_enrichGO",
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    pvalueCutoff = 0.1
)

cat(sprintf("Successfully completed for %d clusters\n", length(all_results)))

# Print summary for each cluster
for (cluster_name in names(all_results)) {
    result <- all_results[[cluster_name]]
    n_terms <- if (!is.null(result)) nrow(as.data.frame(result)) else 0
    cat(sprintf("  Cluster %s: %d enriched terms\n", cluster_name, n_terms))
}

# ============================================================================
# Example 3: Compare Clusters
# ============================================================================

cat("\n=== Example 3: Compare Clusters ===\n")

# Prepare gene list per cluster
gene_clusters <- split(markers$gene, markers$cluster)
cat(sprintf("Prepared gene lists for %d clusters\n", length(gene_clusters)))

# Run compareCluster (limit to first 50 genes per cluster for speed)
gene_clusters_subset <- lapply(gene_clusters, function(genes) head(genes, 50))

compare_result <- run_compareCluster(
    gene_clusters_subset,
    fun = "enrichGO",
    OrgDb = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    pvalueCutoff = 0.1
)

if (!is.null(compare_result) && nrow(as.data.frame(compare_result)) > 0) {
    cat(sprintf("Found enrichment across clusters\n"))

    # Visualize comparison
    p2 <- plot_enrichment_dot(compare_result, showCategory = 8,
                               title = "Cluster Comparison: GO BP")
    print(p2)
}

# ============================================================================
# Example 4: GSEA for Specific Cluster
# ============================================================================

cat("\n=== Example 4: GSEA for Cluster 0 ===\n")

# Prepare ranked gene list for cluster 0
gene_list <- prepare_ranked_list(
    markers,
    cluster = "0",
    rank_by = "log2FC"
)

cat(sprintf("Prepared ranked list with %d genes\n", length(gene_list)))

if (length(gene_list) >= 10) {
    # Run GSEA
    gsea_result <- run_gseGO(
        gene_list = gene_list,
        org_db = org.Hs.eg.db,
        ont = "BP",
        pvalueCutoff = 0.1,
        method = "multilevel"
    )

    if (!is.null(gsea_result) && nrow(as.data.frame(gsea_result)) > 0) {
        cat("\nTop GSEA results:\n")
        print(head(as.data.frame(gsea_result), 3)[, c("Description", "NES", "p.adjust")])

        # Plot running score
        p3 <- plot_gsea_running(gsea_result, geneSetID = 1,
                                 title = "Cluster 0: Top Pathway")
        print(p3)
    }
}

# ============================================================================
# Example 5: GSEA for All Clusters
# ============================================================================

cat("\n=== Example 5: GSEA for All Clusters ===\n")

gsea_all_results <- run_gsea_all_clusters(
    markers,
    gsea_fun = "run_gseGO",
    org_db = org.Hs.eg.db,
    ont = "BP",
    pvalueCutoff = 0.1
)

cat(sprintf("GSEA completed for %d clusters\n", length(gsea_all_results)))

# ============================================================================
# Example 6: Comprehensive Visualization
# ============================================================================

cat("\n=== Example 6: Comprehensive Visualization ===\n")

if (exists("go_result") && !is.null(go_result) &&
    nrow(as.data.frame(go_result)) > 0) {

    # Get fold changes for network plot
    cluster0_markers <- markers[markers$cluster == "0", ]
    fc <- setNames(cluster0_markers$avg_log2FC, cluster0_markers$gene)

    # Create multi-panel figure
    # Note: Uncomment to save
    # plot_enrichment_comprehensive(
    #     go_result,
    #     save_path = "cluster0_enrichment.pdf",
    #     top_n = 10,
    #     foldChange = fc
    # )

    cat("Multi-panel figure created (not saved in this example)\n")
}

# ============================================================================
# Example 7: Export Results
# ============================================================================

cat("\n=== Example 7: Export Results ===\n")

if (exists("go_result") && !is.null(go_result)) {
    # Export to data frame
    df <- as.data.frame(go_result)
    cat(sprintf("Results contain %d rows and %d columns\n",
                nrow(df), ncol(df)))

    # Example export (uncomment to save)
    # export_enrichment(go_result, "cluster0_go_enrichment.csv")
    # export_enrichment(go_result, "cluster0_go_enrichment.xlsx")

    cat("Export functions demonstrated (files not saved)\n")
}

cat("\n=== Seurat integration examples completed! ===\n")
