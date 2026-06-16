# clusterProfiler Skill Test Suite
# Tests for bio-single-cell-enrichment-clusterprofiler-r

library(testthat)

# Get script directory
script_dir <- file.path(getwd(), "..", "scripts", "r")
if (!dir.exists(script_dir)) {
  script_dir <- file.path(getwd(), "scripts", "r")
}

# Source all scripts
source(file.path(script_dir, "ora_analysis.R"))
source(file.path(script_dir, "gsea_analysis.R"))
source(file.path(script_dir, "compare_cluster.R"))
source(file.path(script_dir, "visualization.R"))
source(file.path(script_dir, "utils.R"))

# ============================================================================
# ORA Analysis Tests
# ============================================================================

context("ORA Analysis")

test_that("run_ora_seurat validates inputs", {
  # Non-data.frame input
  expect_error(run_ora_seurat("not a df"), "must be a data frame")

  # Missing required columns
  bad_df <- data.frame(gene = c("A", "B"), avg_log2FC = c(1, 2))
  expect_error(run_ora_seurat(bad_df), "must contain columns")
})

test_that("run_ora_seurat extracts genes correctly", {
  markers <- data.frame(
    gene = c("TP53", "BRCA1", "EGFR", "MYC", "KRAS"),
    avg_log2FC = c(1.5, 0.5, -1.2, 2.0, 0.1),
    p_val_adj = c(0.001, 0.01, 0.049, 0.0001, 0.5),
    cluster = c("0", "0", "0", "1", "1")
  )

  # Default: both positive and negative
  genes <- run_ora_seurat(markers, cluster = "0", only.pos = FALSE)
  expect_type(genes, "character")
  expect_equal(sort(genes), sort(c("TP53", "BRCA1", "EGFR")))

  # only.pos = TRUE
  genes_pos <- run_ora_seurat(markers, cluster = "0", only.pos = TRUE)
  expect_equal(sort(genes_pos), sort(c("TP53", "BRCA1")))
})

test_that("run_ora_seurat handles top_n", {
  markers <- data.frame(
    gene = c("A", "B", "C", "D", "E"),
    avg_log2FC = c(3.0, 2.0, 1.0, -1.5, -2.5),
    p_val_adj = rep(0.001, 5),
    cluster = rep("0", 5)
  )

  # top_n with only.pos = FALSE: should order by abs(log2FC)
  genes <- run_ora_seurat(markers, top_n = 3, only.pos = FALSE)
  expect_length(genes, 3)

  # top_n with only.pos = TRUE: should order by log2FC (positive first)
  genes_pos <- run_ora_seurat(markers, top_n = 2, only.pos = TRUE)
  expect_length(genes_pos, 2)
  expect_equal(genes_pos[1], "A")
})

test_that("run_ora_seurat warns on few genes", {
  markers <- data.frame(
    gene = c("A", "B"),
    avg_log2FC = c(0.1, 0.1),
    p_val_adj = c(0.5, 0.5),
    cluster = c("0", "0")
  )

  expect_warning(
    run_ora_seurat(markers, cluster = "0"),
    "Fewer than 5 genes"
  )
})

test_that("run_ora_all_clusters validates input", {
  bad_df <- data.frame(gene = c("A"), avg_log2FC = c(1), p_val_adj = c(0.01))
  expect_error(
    run_ora_all_clusters(bad_df),
    "must have 'cluster' column"
  )
})

# ============================================================================
# GSEA Analysis Tests
# ============================================================================

context("GSEA Analysis")

test_that("prepare_ranked_list validates inputs", {
  expect_error(prepare_ranked_list("not a df"), "must be a data frame")

  bad_df <- data.frame(gene = c("A", "B"))
  expect_error(prepare_ranked_list(bad_df), "must contain columns")
})

test_that("prepare_ranked_list creates ranked vector", {
  markers <- data.frame(
    gene = c("A", "B", "C", "D"),
    avg_log2FC = c(2.5, -1.8, 0.5, -3.0),
    p_val = c(0.001, 0.01, 0.1, 0.0001),
    cluster = c("0", "0", "1", "1")
  )

  # Default: log2FC
  ranked <- prepare_ranked_list(markers, cluster = "0")
  expect_type(ranked, "double")
  expect_equal(names(ranked)[1], "A")  # highest positive

  # By pval
  ranked_p <- prepare_ranked_list(markers, cluster = "0", rank_by = "pval")
  expect_type(ranked_p, "double")

  # signed = FALSE
  ranked_abs <- prepare_ranked_list(markers, cluster = "0", signed = FALSE)
  expect_true(all(ranked_abs >= 0))
})

test_that("prepare_ranked_list removes NA/Inf", {
  markers <- data.frame(
    gene = c("A", "B", "C"),
    avg_log2FC = c(2.0, Inf, NA),
    cluster = c("0", "0", "0")
  )

  ranked <- prepare_ranked_list(markers, cluster = "0")
  expect_true(all(is.finite(ranked)))
  expect_true(all(!is.na(ranked)))
})

test_that("run_gsea_all_clusters validates input", {
  bad_df <- data.frame(gene = c("A"), avg_log2FC = c(1))
  expect_error(
    run_gsea_all_clusters(bad_df),
    "must have 'cluster' column"
  )
})

# ============================================================================
# Compare Cluster Tests
# ============================================================================

context("Compare Cluster")

test_that("run_compareCluster validates inputs", {
  expect_error(run_compareCluster("not a list"), "must be a list")

  unnamed_list <- list(c("A", "B"), c("C", "D"))
  expect_error(run_compareCluster(unnamed_list), "must be a named list")
})

test_that("compareCluster_seurat validates inputs", {
  expect_error(compareCluster_seurat("not a df"), "must be a data frame")

  bad_df <- data.frame(gene = c("A"), avg_log2FC = c(1), p_val_adj = c(0.01))
  expect_error(
    compareCluster_seurat(bad_df),
    "must have 'cluster' column"
  )
})

test_that("compareCluster_seurat respects only.pos", {
  skip_if_not_installed("clusterProfiler")

  markers <- data.frame(
    gene = c("A", "B", "C", "D", "E"),
    avg_log2FC = c(2.0, 1.5, -1.5, -2.0, 0.1),
    p_val_adj = c(0.001, 0.001, 0.001, 0.001, 0.5),
    cluster = c("0", "0", "0", "0", "0")
  )

  # only.pos = TRUE should only get positive markers
  expect_error(
    compareCluster_seurat(markers, only.pos = TRUE),
    NA  # Should not error but may have no genes for compareCluster
  )
})

test_that("compareGSEA_seurat validates input", {
  bad_df <- data.frame(gene = c("A"), avg_log2FC = c(1))
  expect_error(
    compareGSEA_seurat(bad_df),
    "must have 'cluster' column"
  )
})

test_that("merge_enrichResults validates inputs", {
  expect_error(merge_enrichResults("not a list"), "must be a named list")

  unnamed_list <- list("a", "b")
  expect_error(merge_enrichResults(unnamed_list), "must be a named list")
})

test_that("simplify_compareCluster validates input", {
  expect_error(simplify_compareCluster("not compareCluster"), "must be a compareClusterResult")
})

# ============================================================================
# Visualization Tests
# ============================================================================

context("Visualization")

test_that("plot_enrichment_comprehensive validates input type", {
  expect_error(
    plot_enrichment_comprehensive("not a result", "/tmp/test.pdf"),
    "must be enrichResult or gseaResult"
  )
})

test_that("plot_enrichment_bar rejects non-enrichResult", {
  expect_error(
    plot_enrichment_bar("not enrichResult"),
    "must be enrichResult"
  )
})

test_that("plot_gene_concept_network rejects non-enrichResult", {
  expect_error(
    plot_gene_concept_network("not enrichResult"),
    "must be enrichResult"
  )
})

test_that("plot_upset rejects non-enrichResult", {
  expect_error(
    plot_upset("not enrichResult"),
    "must be enrichResult"
  )
})

test_that("plot_gsea_running rejects non-gseaResult", {
  expect_error(
    plot_gsea_running("not gseaResult"),
    "must be gseaResult"
  )
})

test_that("plot_gsea_ridge rejects non-gseaResult", {
  expect_error(
    plot_gsea_ridge("not gseaResult"),
    "must be gseaResult"
  )
})

# ============================================================================
# Utility Tests
# ============================================================================

context("Utilities")

test_that("get_top_terms handles empty results", {
  # Create a minimal mock enrichResult-like object
  empty_df <- data.frame()
  class(empty_df) <- c("enrichResult", "data.frame")

  # This won't fully work as mock, so test with real empty data frame behavior
  result <- get_top_terms(empty_df)
  expect_equal(nrow(result), 0)
})

test_that("filter_enrichment validates input", {
  expect_error(
    filter_enrichment("not a result"),
    "must be enrichResult, gseaResult, or compareClusterResult"
  )
})

test_that("filter_enrichment filters by pvalue", {
  skip_if_not_installed("clusterProfiler")

  # Create a mock enrichResult with a result slot
  mock_result <- structure(
    list(
      result = data.frame(
        ID = c("GO:001", "GO:002", "GO:003"),
        Description = c("A", "B", "C"),
        pvalue = c(0.001, 0.05, 0.1),
        qvalue = c(0.01, 0.1, 0.2),
        Count = c(10, 5, 2),
        stringsAsFactors = FALSE
      )
    ),
    class = "enrichResult"
  )

  filtered <- filter_enrichment(mock_result, pvalueCutoff = 0.01)
  expect_lte(nrow(as.data.frame(filtered)), nrow(as.data.frame(mock_result)))
})

test_that("filter_enrichment filters by term_contains", {
  skip_if_not_installed("clusterProfiler")

  mock_result <- structure(
    list(
      result = data.frame(
        ID = c("GO:001", "GO:002", "GO:003"),
        Description = c("immune response", "cell cycle", "signaling"),
        pvalue = c(0.001, 0.05, 0.01),
        stringsAsFactors = FALSE
      )
    ),
    class = "enrichResult"
  )

  filtered <- filter_enrichment(mock_result, term_contains = "immune")
  df <- as.data.frame(filtered)
  expect_equal(nrow(df), 1)
  expect_equal(df$Description[1], "immune response")
})

test_that("export_enrichment validates file format", {
  skip_if_not_installed("clusterProfiler")

  mock_result <- structure(
    list(
      result = data.frame(
        ID = "GO:001",
        Description = "test",
        pvalue = 0.01,
        stringsAsFactors = FALSE
      )
    ),
    class = "enrichResult"
  )

  expect_error(
    export_enrichment(mock_result, "test.pdf"),
    "Unsupported file format"
  )
})

test_that("prepare_msigdb_for_enrichment validates id_type", {
  msigdb_df <- data.frame(
    gs_name = c("HALLMARK_A", "HALLMARK_A", "HALLMARK_B"),
    gene_symbol = c("TP53", "BRCA1", "EGFR"),
    stringsAsFactors = FALSE
  )

  expect_error(
    prepare_msigdb_for_enrichment(msigdb_df, id_type = "nonexistent"),
    "not found in data frame"
  )
})

test_that("prepare_msigdb_for_enrichment creates correct output", {
  msigdb_df <- data.frame(
    gs_name = c("HALLMARK_A", "HALLMARK_A", "HALLMARK_B"),
    gene_symbol = c("TP53", "BRCA1", "EGFR"),
    gs_description = c("Desc A", "Desc A", "Desc B"),
    stringsAsFactors = FALSE
  )

  result <- prepare_msigdb_for_enrichment(msigdb_df)
  expect_named(result, c("TERM2GENE", "TERM2NAME"))
  expect_equal(ncol(result$TERM2GENE), 2)
  expect_equal(colnames(result$TERM2GENE), c("term", "gene"))
})

test_that("simplify_go_results rejects non-GO results", {
  # Mock KEGG result (non-GO)
  mock_kegg <- structure(
    list(
      result = data.frame(),
      ontology = "KEGG"
    ),
    class = "enrichResult"
  )

  # Test would need actual clusterProfiler, so skip if not installed
  skip_if_not_installed("clusterProfiler")

  expect_error(
    simplify_go_results(mock_kegg),
    "only works with GO"
  )
})

# ============================================================================
# Integration-like Tests
# ============================================================================

context("Integration")

test_that("run_ora_seurat + run_enrichGO pipeline works end-to-end", {
  skip_if_not_installed("clusterProfiler")
  skip_if_not_installed("org.Hs.eg.db")

  markers <- data.frame(
    gene = c("TP53", "BRCA1", "EGFR", "PTEN", "MYC",
             "CDK1", "CDK2", "CCNA2", "CCNB1", "CCND1",
             "STAT1", "STAT3", "IRF3", "IRF7", "IFNG"),
    avg_log2FC = c(rep(1.5, 5), rep(2.0, 5), rep(1.8, 5)),
    p_val_adj = rep(0.001, 15),
    cluster = c(rep("0", 10), rep("1", 5))
  )

  # Extract genes for cluster 0
  genes <- run_ora_seurat(markers, cluster = "0", only.pos = TRUE)
  expect_type(genes, "character")
  expect_equal(length(genes), 10)

  # Run GO enrichment (may fail if no mapping, but shouldn't error on structure)
  result <- run_enrichGO(
    gene_list = genes,
    org_db = org.Hs.eg.db,
    keyType = "SYMBOL",
    ont = "BP",
    pvalueCutoff = 0.1  # Relaxed for small test set
  )

  expect_s4_class(result, "enrichResult")
})

# Note: Run tests using test_file() or test_dir() from testthat package
# Example: testthat::test_file("tests/test_clusterprofiler.R")
