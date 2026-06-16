# Basic scMetabolism Analysis Example
# Demonstrates standard workflow for metabolic pathway analysis using scMetabolism
#
# This example shows how to:
# 1. Load data and prepare Seurat object
# 2. Run scMetabolism with different algorithms
# 3. Visualize metabolic pathway activities
# 4. Compare metabolism between cell groups

library(Seurat)
library(ggplot2)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source scMetabolism functions
source(file.path(base_dir, "scripts", "r", "run_scmetabolism.R"))
source(file.path(base_dir, "scripts", "r", "visualize_scmetabolism.R"))

# ============================================================================
# PART 1: Load or Create Example Data
# ============================================================================

message("=== Loading Example Data ===")

# Try to use pbmc3k from SeuratData if available
if (requireNamespace("SeuratData", quietly = TRUE)) {
  tryCatch({
    data("pbmc3k")
    seurat_obj <- pbmc3k
    message("Using pbmc3k dataset from SeuratData")
  }, error = function(e) {
    message("Creating minimal test data...")
  })
} else {
  # Create minimal test data
  message("Creating minimal test data with metabolic gene markers...")
  set.seed(42)

  # Create count matrix with metabolic genes
  n_genes <- 500
  n_cells <- 200
  counts <- matrix(rpois(n_genes * n_cells, lambda = 5), nrow = n_genes, ncol = n_cells)

  # Add metabolic pathway marker genes
  metabolic_genes <- c(
    # Glycolysis markers
    "HK1", "HK2", "GPI", "PFKM", "ALDOA", "GAPDH", "PGK1", "ENO1", "PKM", "LDHA",
    # TCA cycle markers
    "CS", "ACO2", "IDH1", "IDH2", "OGDH", "SDHA", "FH", "MDH1", "MDH2",
    # Oxidative phosphorylation markers
    "NDUFS1", "NDUFS2", "SDHA", "UQCRC1", "COX1", "ATP5F1A",
    # Fatty acid metabolism
    "ACACA", "FASN", "ACLY", "ACADS", "HADHA",
    # Glutamine metabolism
    "GLS", "GLUD1", "GLUL"
  )

  # Ensure gene names exist
  rownames(counts) <- c(
    metabolic_genes[1:min(length(metabolic_genes), n_genes)],
    paste0("GENE", (length(metabolic_genes) + 1):n_genes)
  )[1:n_genes]
  colnames(counts) <- paste0("CELL", 1:n_cells)

  # Create Seurat object with basic processing
  seurat_obj <- CreateSeuratObject(counts = counts)
  seurat_obj <- NormalizeData(seurat_obj)
  seurat_obj <- FindVariableFeatures(seurat_obj, nfeatures = 200)
  seurat_obj <- ScaleData(seurat_obj)
  seurat_obj <- RunPCA(seurat_obj, npcs = 20)
  seurat_obj <- FindNeighbors(seurat_obj, dims = 1:10)
  seurat_obj <- FindClusters(seurat_obj, resolution = 0.5)
  seurat_obj <- RunUMAP(seurat_obj, dims = 1:10)
}

message(sprintf("Seurat object: %d genes x %d cells", nrow(seurat_obj), ncol(seurat_obj)))
message(sprintf("Clusters: %s", paste(unique(seurat_obj$seurat_clusters), collapse = ", ")))

# ============================================================================
# PART 2: Run scMetabolism Analysis
# ============================================================================

message("\n=== Running scMetabolism Analysis ===")

# Get available metabolic pathways
message("\n--- Available KEGG Pathways (first 10) ---")
kegg_pathways <- get_metabolic_pathways("KEGG")
print(head(kegg_pathways, 10))

# Option 1: Run with VISION method (default, recommended)
message("\n--- Running with VISION method ---")
result_vision <- run_scmetabolism(
  seurat_obj = seurat_obj,
  method = "VISION",
  metabolism.type = "KEGG",
  imputation = FALSE,
  ncores = 2,
  assay = "RNA",
  slot = "counts"
)

seurat_obj <- result_vision$seurat_obj
metabolism_matrix <- result_vision$metabolism_matrix

message(sprintf("Metabolism matrix dimensions: %d pathways x %d cells",
                nrow(metabolism_matrix), ncol(metabolism_matrix)))

# Option 2: Run with AUCell method (uncomment to compare)
# message("\n--- Running with AUCell method ---")
# result_aucell <- run_scmetabolism(
#   seurat_obj = seurat_obj,
#   method = "AUCell",
#   metabolism.type = "KEGG",
#   ncores = 2,
#   output_assay = "METABOLISM_AUCell"
# )

# Option 3: Run with REACTOME database (uncomment to use)
# message("\n--- Running with REACTOME database ---")
# result_reactome <- run_scmetabolism(
#   seurat_obj = seurat_obj,
#   method = "VISION",
#   metabolism.type = "REACTOME",
#   ncores = 2,
#   output_assay = "METABOLISM_REACTOME"
# )

# ============================================================================
# PART 3: Extract and Explore Results
# ============================================================================

message("\n=== Exploring Results ===")

# Extract metabolism scores
scores <- extract_metabolism_scores(seurat_obj, assay = "METABOLISM")
message(sprintf("Extracted scores for %d pathways", nrow(scores)))

# Get top variable pathways
top_pathways <- get_top_variable_pathways(seurat_obj, n_top = 10, assay = "METABOLISM")
message("\n--- Top 10 Variable Pathways ---")
print(top_pathways)

# Extract specific pathway scores
glycolysis_scores <- extract_metabolism_scores(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Citrate cycle (TCA cycle)")
)
message("\n--- Glycolysis and TCA Cycle Scores Summary ---")
print(summary(t(glycolysis_scores)))

# Compare metabolism between clusters
message("\n--- Metabolism Comparison by Cluster ---")
comparison <- compare_metabolism(
  seurat_obj,
  group.by = "seurat_clusters",
  pathways = top_pathways[1:5],
  assay = "METABOLISM"
)
print(head(comparison))

# ============================================================================
# PART 4: Visualize Results
# ============================================================================

message("\n=== Creating Visualizations ===")

# 1. DimPlot (UMAP) for specific pathways
message("\n--- Creating DimPlots ---")

# Glycolysis on UMAP
p1 <- dimplot_metabolism(
  seurat_obj,
  pathway = "Glycolysis / Gluconeogenesis",
  reduction = "umap",
  size = 0.5
)
print(p1 + ggtitle("Glycolysis / Gluconeogenesis"))

# TCA cycle on UMAP
p2 <- dimplot_metabolism(
  seurat_obj,
  pathway = "Citrate cycle (TCA cycle)",
  reduction = "umap",
  size = 0.5,
  palette = "plasma"
)
print(p2 + ggtitle("TCA Cycle"))

# 2. Dot Plot for top pathways
message("\n--- Creating Dot Plot ---")
p_dot <- dotplot_metabolism(
  seurat_obj,
  pathways = top_pathways[1:8],
  group.by = "seurat_clusters",
  norm = "y"
)
print(p_dot + ggtitle("Metabolic Pathway Activity by Cluster"))

# 3. Box Plot for specific pathways
message("\n--- Creating Box Plots ---")
p_box <- boxplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Citrate cycle (TCA cycle)"),
  group.by = "seurat_clusters",
  ncol = 2
)
print(p_box)

# 4. Heatmap
message("\n--- Creating Heatmap ---")
heatmap_metabolism(
  seurat_obj,
  pathways = top_pathways[1:15],
  group.by = "seurat_clusters",
  scale = "row"
)

# 5. Violin Plot
message("\n--- Creating Violin Plot ---")
p_violin <- violinplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis"),
  group.by = "seurat_clusters"
)
print(p_violin)

# ============================================================================
# PART 5: Export Results
# ============================================================================

message("\n=== Exporting Results ===")

# Export results to files
output_dir <- "scmetabolism_output"
export_scmetabolism_results(
  seurat_obj,
  output_dir = output_dir,
  prefix = "example_analysis"
)

# Also save the annotated Seurat object
saveRDS(seurat_obj, file.path(output_dir, "seurat_with_metabolism.rds"))
message(sprintf("Seurat object saved to: %s", file.path(output_dir, "seurat_with_metabolism.rds")))

# ============================================================================
# PART 6: Advanced Analysis (Optional)
# ============================================================================

message("\n=== Advanced Analysis ===")

# Find cells with high glycolytic activity
glycolysis_scores <- as.numeric(scores["Glycolysis / Gluconeogenesis", ])
high_glycolysis <- colnames(scores)[glycolysis_scores > quantile(glycolysis_scores, 0.9)]
message(sprintf("Cells with high glycolytic activity: %d", length(high_glycolysis)))

# Compare two methods (if both were run)
# message("\n--- Comparing VISION vs AUCell ---")
# vision_scores <- extract_metabolism_scores(seurat_obj, assay = "METABOLISM")
# aucell_scores <- extract_metabolism_scores(seurat_obj, assay = "METABOLISM_AUCell")
# correlation <- cor(
#   as.numeric(vision_scores["Glycolysis / Gluconeogenesis", ]),
#   as.numeric(aucell_scores["Glycolysis / Gluconeogenesis", ])
# )
# message(sprintf("Correlation between methods: %.3f", correlation))

# ============================================================================
# Summary
# ============================================================================

message("\n=== Example Complete ===")
message(sprintf("Output directory: %s", output_dir))
message(sprintf("Results include:"))
message(sprintf("  - Metabolism scores matrix (%d pathways)", nrow(metabolism_matrix)))
message(sprintf("  - Mean scores by group"))
message(sprintf("  - Analysis parameters"))
message(sprintf("  - Annotated Seurat object"))
message("\nNext steps:")
message("  1. Explore metabolism scores in the Seurat object")
message("  2. Try different visualization methods")
message("  3. Compare results between different algorithms")
message("  4. Integrate with cell type annotations")
