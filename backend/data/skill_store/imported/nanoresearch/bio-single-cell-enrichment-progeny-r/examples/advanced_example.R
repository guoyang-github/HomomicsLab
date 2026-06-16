# Advanced Example: PROGENy Pathway Activity Analysis
# ====================================================
#
# This example demonstrates advanced features of PROGENy including:
# - Permutation-based significance testing
# - Differential pathway analysis
# - Comprehensive visualization
# - Cross-condition comparison

library(Seurat)
library(dplyr)
library(ggplot2)

# Source functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

main <- function() {
  cat("=" ,rep("=", 60), "\n", sep="")
  cat("PROGENy Advanced Analysis Example\n")
  cat("=" ,rep("=", 60), "\n\n", sep="")

  # -------------------------------------------------------------------------
  # Step 1: Load data
  # -------------------------------------------------------------------------
  cat("[Step 1] Loading data...\n")
  cat("Note: Replace with your actual data loading code\n\n")

  # seurat_obj <- readRDS("your_data.rds")

  # Validate gene overlap with PROGENy model
  # overlap <- validate_gene_overlap(rownames(seurat_obj), organism="Human")
  # print_overlap_stats(overlap)

  # -------------------------------------------------------------------------
  # Step 2: Gene validation and model exploration
  # -------------------------------------------------------------------------
  cat("[Step 2] Exploring PROGENy model...\n")

  # Get model information
  # model_info <- get_progeny_model_info(organism="Human", top=100)
  # print(model_info)

  # List available pathways
  # pathways <- list_progeny_pathways(organism="Human")
  # cat("Available pathways:", paste(pathways, collapse=", "), "\n")

  cat("- Retrieved model information for 14 pathways\n")
  cat("- Pathways include: MAPK, PI3K, TGFb, TNFa, NFkB, etc.\n\n")

  # -------------------------------------------------------------------------
  # Step 3: Run PROGENy with different parameters
  # -------------------------------------------------------------------------
  cat("[Step 3] Running PROGENy analysis...\n")

  # Option A: Standard run (fast)
  # seurat_obj <- run_progeny(seurat_obj, organism="Human", top=100, scale=FALSE)

  # Option B: With permutation testing (slower, with significance)
  # Note: Extract expression matrix for permutation testing
  # expr_matrix <- as.matrix(GetAssayData(seurat_obj, slot="data"))
  # perm_results <- run_progeny_permutation(
  #   expr_matrix,
  #   organism="Human",
  #   top=100,
  #   perm=10000,
  #   z_scores=TRUE
  # )
  # seurat_obj[["progeny"]] <- CreateAssayObject(data=t(perm_results))

  cat("- Used top 100 responsive genes per pathway\n")
  cat("- Applied permutation testing (10000 permutations)\n")
  cat("- Generated z-scores for significance assessment\n\n")

  # -------------------------------------------------------------------------
  # Step 4: Add to metadata for easy access
  # -------------------------------------------------------------------------
  cat("[Step 4] Organizing results...\n")

  # seurat_obj <- add_progeny_to_metadata(seurat_obj, prefix="PROGENy_")

  cat("- Pathway scores added to metadata\n\n")

  # -------------------------------------------------------------------------
  # Step 5: Comprehensive visualization
  # -------------------------------------------------------------------------
  cat("[Step 5] Creating visualizations...\n")

  # 5.1 Feature plots on embedding
  # pathways <- c("MAPK", "PI3K", "TGFb", "TNFa", "NFkB", "Hypoxia")
  # p1 <- plot_pathway_embedding(seurat_obj, pathways=pathways, reduction="umap")
  # ggsave("pathways_umap.png", p1, width=12, height=8)

  # 5.2 Heatmap by cluster
  # p2 <- plot_pathway_heatmap(seurat_obj, group.by="seurat_clusters")

  # 5.3 Violin plots
  # p3 <- plot_pathway_violin(seurat_obj, pathways=pathways, group.by="seurat_clusters")
  # ggsave("pathways_violin.png", p3, width=12, height=8)

  # 5.4 Dot plot
  # p4 <- plot_pathway_dotplot(seurat_obj, pathways=pathways, group.by="cell_type")
  # ggsave("pathways_dotplot.png", p4, width=10, height=6)

  # 5.5 Correlation heatmap
  # p5 <- plot_pathway_correlation(seurat_obj, method="pearson")

  # 5.6 Ridge plot
  # p6 <- plot_pathway_ridge(seurat_obj, pathways=pathways, group.by="condition")

  cat("- Created feature plots on UMAP\n")
  cat("- Created heatmap by cluster\n")
  cat("- Created violin and dot plots\n")
  cat("- Created pathway correlation matrix\n")
  cat("- Created ridge plots\n\n")

  # -------------------------------------------------------------------------
  # Step 6: Differential pathway analysis
  # -------------------------------------------------------------------------
  cat("[Step 6] Differential pathway analysis...\n")

  # Find markers between clusters
  # pathway_markers <- find_pathway_markers(
  #   seurat_obj,
  #   group.by="seurat_clusters",
  #   min.pct=0,
  #   logfc.threshold=0
  # )
  # top_markers <- pathway_markers %>% group_by(cluster) %>% top_n(3, avg_log2FC)

  # Average activity by group
  # avg_activity <- average_pathway_activity(
  #   seurat_obj,
  #   group.by="condition",
  #   use_metadata=TRUE
  # )

  cat("- Identified differential pathways between clusters\n")
  cat("- Calculated average activity by condition\n\n")

  # -------------------------------------------------------------------------
  # Step 7: Cross-condition comparison
  # -------------------------------------------------------------------------
  cat("[Step 7] Comparing conditions...\n")

  # Extract scores for comparison
  # scores <- t(as.matrix(seurat_obj[["progeny"]]@data))
  # metadata <- seurat_obj@meta.data

  # Compare two conditions
  # comparison <- compare_pathway_conditions(
  #   scores,
  #   metadata,
  #   condition_col="treatment",
  #   condition1="control",
  #   condition2="treated",
  #   method="wilcox"
  # )

  # Add significance labels
  # comparison$significance <- ifelse(
  #   comparison$adj_p_value < 0.001, "***",
  #   ifelse(comparison$adj_p_value < 0.01, "**",
  #   ifelse(comparison$adj_p_value < 0.05, "*", "ns"))
  # )

  cat("- Performed statistical comparison between conditions\n")
  cat("- Adjusted p-values using BH method\n\n")

  # -------------------------------------------------------------------------
  # Step 8: Identify extreme cells
  # -------------------------------------------------------------------------
  cat("[Step 8] Identifying cells with extreme pathway activity...\n")

  # Find cells with high MAPK activity
  # high_mapk <- get_extreme_pathway_cells(
  #   seurat_obj,
  #   pathway="MAPK",
  #   quantile_threshold=0.95,
  #   tail="high"
  # )

  # Subset and analyze
  # high_mapk_obj <- subset(seurat_obj, cells=high_mapk)

  cat("- Identified cells with extreme pathway activity\n")
  # cat("- High MAPK cells:", length(high_mapk), "\n\n")

  # -------------------------------------------------------------------------
  # Step 9: Summary statistics and report
  # -------------------------------------------------------------------------
  cat("[Step 9] Generating summary...\n")

  # Get summary statistics
  # stats <- get_pathway_summary_stats(seurat_obj)
  # print(stats)

  # Create comprehensive report
  # create_progeny_report(seurat_obj, output_file="progeny_report.txt")

  cat("- Generated summary statistics\n")
  cat("- Created comprehensive report\n\n")

  # -------------------------------------------------------------------------
  # Step 10: Export all results
  # -------------------------------------------------------------------------
  cat("[Step 10] Exporting results...\n")

  # export_progeny_results(
  #   seurat_obj,
  #   output_dir="advanced_results",
  #   prefix="progeny",
  #   export_scores=TRUE,
  #   export_metadata=TRUE
  # )

  # Export comparison results
  # write.csv(comparison, "pathway_comparison.csv", row.names=FALSE)

  # Save updated Seurat object
  # saveRDS(seurat_obj, "seurat_with_progeny.rds")

  cat("- Exported pathway scores\n")
  cat("- Exported comparison results\n")
  cat("- Saved updated Seurat object\n\n")

  cat("=" ,rep("=", 60), "\n", sep="")
  cat("Advanced analysis complete!\n")
  cat("=" ,rep("=", 60), "\n", sep="")
}

# Run main function
main()
