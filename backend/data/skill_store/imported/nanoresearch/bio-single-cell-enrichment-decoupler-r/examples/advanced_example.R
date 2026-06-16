# decoupleR Advanced Example
# ===========================
#
# Advanced workflows including multi-method analysis, TF activity inference,
# differential analysis, consensus scoring, and comprehensive visualization

# Source wrapper functions
source("../scripts/r/core_analysis.R")
source("../scripts/r/visualization.R")
source("../scripts/r/utils.R")

library(decoupleR)
library(Seurat)
library(dplyr)
library(tidyr)

print("decoupleR Advanced Example")
print("===========================")

# ============================================================================
# Setup: Load and Prepare Data
# ============================================================================

print("\n1. Loading and preparing data...")
data("pbmc_small", package = "Seurat")
seurat_obj <- pbmc_small

# Add mock condition information for differential analysis
set.seed(42)
seurat_obj$condition <- sample(c("Control", "Treatment"), ncol(seurat_obj), replace = TRUE)
seurat_obj$cell_type <- Idents(seurat_obj)

print(paste("  Cells:", ncol(seurat_obj)))
print(paste("  Genes:", nrow(seurat_obj)))
print(paste("  Conditions:", paste(unique(seurat_obj$condition), collapse = ", ")))
print(paste("  Cell types:", length(unique(seurat_obj$cell_type))))

# ============================================================================
# PART 1: Multi-Method Pathway Analysis with Consensus
# ============================================================================

print("\n========================================")
print("PART 1: Multi-Method Pathway Analysis")
print("========================================")

# Get PROGENy network
print("\n2. Loading PROGENy network...")
progeny_net <- get_progeny_network(organism = "human", top = 500)
print(paste("  PROGENy pathways:", length(unique(progeny_net$source))))

# Extract expression matrix
if (packageVersion("SeuratObject") >= "5.0.0") {
  mat <- Seurat::GetAssayData(seurat_obj, layer = "data")
} else {
  mat <- Seurat::GetAssayData(seurat_obj, slot = "data")
}

# Check overlap
overlap <- check_gene_overlap(mat, progeny_net)
print(paste("  Gene overlap:", sprintf("%.1f%%", overlap$overlap_fraction * 100)))

# Run multiple methods
print("\n3. Running multiple methods (ULM, MLM, WSum)...")
acts_multi <- run_decoupler_multi(
  mat = mat,
  net = progeny_net,
  methods = c("ulm", "mlm", "wsum"),
  minsize = 5
)

print(paste("  Multi-method results:", nrow(acts_multi), "rows"))
print(paste("  Methods used:", paste(unique(acts_multi$statistic), collapse = ", ")))

# Create consensus score
print("\n4. Creating consensus scores...")
acts_consensus <- create_consensus_score(acts_multi)
print(paste("  Consensus results:", nrow(acts_consensus), "rows"))
# Note: create_consensus_score() adds consensus rows to the existing multi-method results

# Show top consensus activities
print("\n  Top 10 consensus pathway activities:")
top_consensus <- acts_consensus %>%
  group_by(source) %>%
  summarise(mean_score = mean(abs(score), na.rm = TRUE)) %>%
  arrange(desc(mean_score)) %>%
  head(10)
print(top_consensus)

# Compare methods
print("\n5. Method correlation analysis:")
method_cor <- acts_multi %>%
  select(source, condition, statistic, score) %>%
  pivot_wider(names_from = statistic, values_from = score) %>%
  select(ulm, mlm, wsum) %>%
  cor(use = "complete.obs")
print("  Correlation matrix:")
print(method_cor)

# ============================================================================
# PART 2: TF Activity Inference with DoRothEA
# ============================================================================

print("\n========================================")
print("PART 2: Transcription Factor Activity Inference")
print("========================================")

# Get DoRothEA network (high confidence: A and B)
print("\n6. Loading DoRothEA TF network...")
dorothea_net <- get_dorothea_network(organism = "human", levels = c("A", "B"))
print(paste("  DoRothEA TFs:", length(unique(dorothea_net$source))))
print(paste("  Interactions:", nrow(dorothea_net)))

# Show confidence distribution
print("  Confidence distribution:")
print(table(dorothea_net$level))

# Run TF activity inference using ULM
print("\n7. Running ULM for TF activities...")
tf_acts <- run_ulm_analysis(
  mat = mat,
  net = dorothea_net,
  minsize = 5,
  center = TRUE
)

print(paste("  TF activities inferred:", length(unique(tf_acts$source)), "TFs"))

# Get top TFs
print("\n  Top 10 TFs by mean absolute activity:")
top_tfs <- get_top_activities(tf_acts, n_top = 10)
print(top_tfs)

# ============================================================================
# PART 3: Differential Activity Analysis
# ============================================================================

print("\n========================================")
print("PART 3: Differential Activity Analysis")
print("========================================")

# Average expression by condition
print("\n8. Calculating average expression by condition...")
Idents(seurat_obj) <- "condition"
avg_expr <- AverageExpression(seurat_obj, group.by = "condition")$RNA

print(paste("  Conditions:", paste(colnames(avg_expr), collapse = ", ")))

# Run pathway analysis on condition averages
print("\n9. Running pathway analysis on condition averages...")
acts_condition <- run_ulm_analysis(
  mat = avg_expr,
  net = progeny_net,
  minsize = 5
)

# Get differential activities
print("\n10. Calculating differential pathway activities...")
diff_pathways <- get_differential_activities(
  acts_condition,
  cond1 = "Control",
  cond2 = "Treatment"
)

print(paste("  Pathways compared:", nrow(diff_pathways)))
print("\n  Top 10 differentially active pathways:")
print(head(diff_pathways, 10))

# ============================================================================
# PART 4: Per-Cell Type Analysis
# ============================================================================

print("\n========================================")
print("PART 4: Per-Cell Type Analysis")
print("========================================")

# Average expression by cell type
print("\n11. Analyzing pathway activities by cell type...")
Idents(seurat_obj) <- "cell_type"
avg_expr_celltype <- AverageExpression(seurat_obj, group.by = "cell_type")$RNA

# Run pathway analysis on cell type averages
acts_celltype <- run_ulm_analysis(
  mat = avg_expr_celltype,
  net = progeny_net,
  minsize = 5
)

print(paste("  Cell types analyzed:", length(unique(acts_celltype$condition))))

# Find most variable pathways across cell types
print("\n  Most variable pathways across cell types:")
var_pathways <- acts_celltype %>%
  group_by(source) %>%
  summarise(variance = var(score)) %>%
  arrange(desc(variance)) %>%
  head(10)
print(var_pathways)

# ============================================================================
# PART 5: Comprehensive Visualization
# ============================================================================

print("\n========================================")
print("PART 5: Comprehensive Visualization")
print("========================================")

# Create output directory
output_dir <- "./decoupler_output"
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

print(paste("  Output directory:", output_dir))

# 1. Multi-method heatmap
print("\n12. Creating visualizations...")
print("  - Multi-method activity heatmap...")
tryCatch({
  ht_multi <- plot_activity_heatmap(
    acts_multi,
    n_top = 12,
    scale = TRUE,
    title = "Multi-Method Pathway Activities"
  )
  print("    Created successfully")
}, error = function(e) {
  print(paste("    Error:", conditionMessage(e)))
})

# 2. Consensus scores
print("  - Consensus score bar plot...")
tryCatch({
  p_consensus <- plot_consensus_scores(acts_multi, top_n = 15)
  print("    Created successfully")
}, error = function(e) {
  print(paste("    Error:", conditionMessage(e)))
})

# 3. Method comparison scatter plots
print("  - Method comparison plots...")
tryCatch({
  # ULM vs MLM for all pathways
  p_compare_all <- plot_method_comparison(
    acts_multi,
    method_x = "ulm",
    method_y = "mlm"
  )

  # For specific pathway
  p_compare_tnfa <- plot_method_comparison(
    acts_multi,
    source_specific = "TNFa",
    method_x = "ulm",
    method_y = "mlm"
  )
  print("    Created successfully")
}, error = function(e) {
  print(paste("    Error:", conditionMessage(e)))
})

# 4. Differential activity volcano plot
print("  - Differential activity volcano plot...")
tryCatch({
  p_volcano <- plot_activity_volcano(
    diff_pathways,
    logfc_col = "diff",
    fc_threshold = 0.3
  )
  print("    Created successfully")
}, error = function(e) {
  print(paste("    Error:", conditionMessage(e)))
})

# 5. Top activities by cell type
print("  - Cell type activity plots...")
tryCatch({
  cell_types <- unique(acts_celltype$condition)
  for (ct in head(cell_types, 3)) {
    p <- plot_top_activities(
      acts_celltype,
      condition = ct,
      n_top = 10,
      color_by_sign = TRUE
    )
    print(paste("    Created for", ct))
  }
}, error = function(e) {
  print(paste("    Error:", conditionMessage(e)))
})

# 6. TF activity heatmap
print("  - TF activity heatmap...")
tryCatch({
  ht_tf <- plot_activity_heatmap(
    tf_acts,
    n_top = 15,
    title = "TF Activities"
  )
  print("    Created successfully")
}, error = function(e) {
  print(paste("    Error:", conditionMessage(e)))
})

# ============================================================================
# PART 6: Export Results
# ============================================================================

print("\n========================================")
print("PART 6: Export Results")
print("========================================")

# Export pathway results
print("\n13. Exporting pathway results...")
export_decoupler_results(
  acts_multi,
  output_dir = output_dir,
  prefix = "pathway_multi"
)

# Export TF results
print("  Exporting TF results...")
export_decoupler_results(
  tf_acts,
  output_dir = output_dir,
  prefix = "tf_activity"
)

# Export differential results
print("  Exporting differential pathway results...")
write.csv(
  diff_pathways,
  file.path(output_dir, "differential_pathways.csv"),
  row.names = FALSE
)

# Generate comprehensive report
print("\n14. Generating comprehensive report...")
report <- create_decoupler_report(
  acts_multi,
  net = progeny_net,
  output_file = file.path(output_dir, "decoupler_report.txt")
)

cat(report)

# ============================================================================
# Summary
# ============================================================================

print("\n========================================")
print("Advanced Example Summary")
print("========================================")
print(paste("  Multi-method pathway analysis:", nrow(acts_multi), "results"))
print(paste("  - ULM, MLM, WSum methods combined"))
print(paste("  - Consensus scores calculated"))
print(paste("  TF activity inference:", length(unique(tf_acts$source)), "TFs"))
print(paste("  Differential pathways:", nrow(diff_pathways), "compared"))
print(paste("  Cell type activities:", length(unique(acts_celltype$condition)), "types"))
print(paste("  Output directory:", output_dir))
print("")
print("Key takeaways:")
print("- Multiple methods provide robust results; use consensus for reliability")
print("- TF activity reveals upstream regulatory mechanisms")
print("- Differential analysis identifies condition-specific activities")
print("- Cell type-specific activities show functional specialization")
print("========================================")
print("Example completed successfully!")
print("========================================")
