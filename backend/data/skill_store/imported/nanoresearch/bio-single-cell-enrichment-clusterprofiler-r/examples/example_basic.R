# Basic clusterProfiler Workflow Example
#
# This example demonstrates basic ORA and GSEA workflows using clusterProfiler
# with example gene lists.
#
# Author: Yang Guo
# Date: 2026-04-03

# ============================================================================
# Setup
# ============================================================================

# Install required packages (run once)
# BiocManager::install(c("clusterProfiler", "org.Hs.eg.db", "enrichplot"))
# install.packages("msigdbr")

# Load libraries
library(clusterProfiler)
library(org.Hs.eg.db)
library(enrichplot)
library(ggplot2)

# Source skill scripts
source("../scripts/r/ora_analysis.R")
source("../scripts/r/gsea_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

# ============================================================================
# Example 1: GO ORA with Example Genes
# ============================================================================

cat("\n=== Example 1: GO ORA ===\n")

# Example gene list (TP53 pathway related)
example_genes <- c(
    "TP53", "BRCA1", "BRCA2", "ATM", "CHEK2", "MDM2", "MDM4",
    "CDKN2A", "CDKN1A", "GADD45A", "SFN", "BAX", "BAK1",
    "BCL2", "BCL2L1", "CASP3", "CASP8", "CASP9", "FAS", "FASLG"
)

cat("Gene list:", length(example_genes), "genes\n")

# Run GO enrichment (Biological Process)
go_bp <- run_enrichGO(
    gene_list = example_genes,
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    pvalueCutoff = 0.05,
    readable = TRUE
)

# View results
if (!is.null(go_bp) && nrow(as.data.frame(go_bp)) > 0) {
    cat("\nTop 5 GO BP terms:\n")
    print(head(as.data.frame(go_bp), 5)[, c("ID", "Description", "p.adjust", "Count")])

    # Visualize
    p1 <- plot_enrichment_dot(go_bp, showCategory = 10)
    print(p1)

    # Save plot
    # ggsave("go_bp_dotplot.pdf", p1, width = 10, height = 8)
}

# Run GO enrichment for Molecular Function and Cellular Component
for (ont in c("MF", "CC")) {
    result <- run_enrichGO(
        gene_list = example_genes,
        org_db = org.Hs.eg.db,
        ont = ont,
        pvalueCutoff = 0.05
    )

    if (!is.null(result) && nrow(as.data.frame(result)) > 0) {
        cat(sprintf("\nFound %d GO %s terms\n", nrow(as.data.frame(result)), ont))
    }
}

# ============================================================================
# Example 2: KEGG ORA
# ============================================================================

cat("\n=== Example 2: KEGG ORA ===\n")

# KEGG uses Entrez IDs, so we convert first
kegg_result <- run_enrichKEGG(
    gene_list = example_genes,
    organism = "hsa",
    convert_ids = TRUE,
    org_db = org.Hs.eg.db,
    pvalueCutoff = 0.05
)

if (!is.null(kegg_result) && nrow(as.data.frame(kegg_result)) > 0) {
    cat("\nTop KEGG pathways:\n")
    print(head(as.data.frame(kegg_result), 5)[, c("ID", "Description", "p.adjust")])
}

# ============================================================================
# Example 3: MSigDB Enrichment
# ============================================================================

cat("\n=== Example 3: MSigDB Hallmark Enrichment ===\n")

# Check if msigdbr is available
if (requireNamespace("msigdbr", quietly = TRUE)) {
    # Get Hallmark gene sets
    h_sets <- get_msigdb_genesets("Homo sapiens", "H")
    prepared <- prepare_msigdb_for_enrichment(h_sets)

    cat(sprintf("Loaded %d Hallmark gene sets\n", length(unique(h_sets$gs_name))))

    # Run enrichment
    msig_result <- run_enricher(
        gene_list = example_genes,
        term2gene = prepared$TERM2GENE,
        term2name = prepared$TERM2NAME,
        pvalueCutoff = 0.1
    )

    if (!is.null(msig_result) && nrow(as.data.frame(msig_result)) > 0) {
        cat("\nTop Hallmark pathways:\n")
        print(head(as.data.frame(msig_result), 5)[, c("ID", "Description", "p.adjust")])
    }
} else {
    cat("msigdbr not installed. Install with: install.packages('msigdbr')\n")
}

# ============================================================================
# Example 4: GO GSEA
# ============================================================================

cat("\n=== Example 4: GO GSEA ===\n")

# Create example ranked gene list (simulated log2FC)
set.seed(42)
all_genes <- sample(keys(org.Hs.eg.db, keytype = "SYMBOL"), 500)
ranked_scores <- rnorm(500, mean = 0, sd = 2)
ranked_scores[1:20] <- ranked_scores[1:20] + 5  # Top genes upregulated
names(ranked_scores) <- all_genes
ranked_scores <- sort(ranked_scores, decreasing = TRUE)

cat(sprintf("Created ranked list with %d genes\n", length(ranked_scores)))

# Run GSEA
gsea_result <- run_gseGO(
    gene_list = ranked_scores,
    org_db = org.Hs.eg.db,
    ont = "BP",
    pvalueCutoff = 0.1,
    method = "multilevel"
)

if (!is.null(gsea_result) && nrow(as.data.frame(gsea_result)) > 0) {
    cat("\nTop GSEA results:\n")
    print(head(as.data.frame(gsea_result), 5)[, c("ID", "Description", "NES", "p.adjust")])

    # Plot running score for top pathway
    p2 <- plot_gsea_running(gsea_result, geneSetID = 1)
    print(p2)
}

# ============================================================================
# Example 5: Simplify GO Results
# ============================================================================

cat("\n=== Example 5: GO Simplification ===\n")

# Run enrichment without simplification
raw_go <- run_enrichGO(
    gene_list = example_genes,
    org_db = org.Hs.eg.db,
    ont = "BP",
    pvalueCutoff = 0.1
)

if (!is.null(raw_go) && nrow(as.data.frame(raw_go)) > 0) {
    cat(sprintf("\nBefore simplification: %d terms\n", nrow(as.data.frame(raw_go))))

    # Simplify (requires GOSemSim)
    if (requireNamespace("GOSemSim", quietly = TRUE)) {
        simplified <- simplify_go_results(raw_go, cutoff = 0.7)
        cat(sprintf("After simplification: %d terms\n", nrow(as.data.frame(simplified))))
    } else {
        cat("GOSemSim not installed. Install with: BiocManager::install('GOSemSim')\n")
    }
}

# ============================================================================
# Example 6: Export Results
# ============================================================================

cat("\n=== Example 6: Export Results ===\n")

if (!is.null(go_bp) && nrow(as.data.frame(go_bp)) > 0) {
    # Export to data frame
df <- as.data.frame(go_bp)
    cat(sprintf("\nExporting %d rows\n", nrow(df)))

    # Show available columns
    cat("\nResult columns:\n")
    print(colnames(df))

    # Export to CSV (example)
    # export_enrichment(go_bp, "go_enrichment_results.csv")
}

cat("\n=== Examples completed! ===\n")
