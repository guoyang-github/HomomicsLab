# Basic SCENIC Analysis Example
# Demonstrates SCENIC pipeline for regulatory network inference

library(SCENIC)
library(Seurat)
library(AUCell)

# Source wrapper functions
source("../scripts/r/scenic_analysis.R")

# ============================================================================
# Step 1: Load Data
# ============================================================================

# Load your Seurat object
# seurat_obj <- readRDS("your_data.rds")

# For demonstration, create mock data
set.seed(42)
n_cells <- 200
n_genes <- 500

counts <- matrix(rpois(n_cells * n_genes, lambda = 3),
                 nrow = n_genes, ncol = n_cells)
rownames(counts) <- paste0("GENE", 1:n_genes)
colnames(counts) <- paste0("CELL", 1:n_cells)

seurat_obj <- CreateSeuratObject(counts = counts)
seurat_obj <- NormalizeData(seurat_obj, verbose = FALSE)
seurat_obj$cell_type <- sample(c("T_cell", "B_cell", "Monocyte"), n_cells, replace = TRUE)

# ============================================================================
# Step 2: Initialize SCENIC
# ============================================================================

# Download cisTarget databases first:
# https://resources.aertslab.org/cistarget/

# Initialize SCENIC options
scenicOptions <- init_scenic(
  org = "hgnc",  # or "mmusculus" for mouse
  dbDir = "cisTarget",
  datasetTitle = "MySCENIC",
  nCores = 4
)

# ============================================================================
# Step 3: Run SCENIC Pipeline
# ============================================================================

# Get expression matrix
if (packageVersion("SeuratObject") >= "5.0.0") {
  exprMat <- Seurat::GetAssayData(seurat_obj, layer = "counts")
} else {
  exprMat <- Seurat::GetAssayData(seurat_obj, slot = "counts")
}

# Run complete pipeline
# Note: This takes several hours for real datasets
scenicOptions <- run_scenic_pipeline(
  exprMat = exprMat,
  scenicOptions = scenicOptions,
  runGenie3 = TRUE,
  nParts = 10
)

# ============================================================================
# Step 4: Load Results
# ============================================================================

# Add SCENIC results to Seurat
seurat_obj <- add_scenic_to_seurat(seurat_obj, scenicOptions, assayName = "SCENIC")

# Load regulon AUC
regulonAUC <- load_scenic_results(scenicOptions, "aucell")

# ============================================================================
# Step 5: Analysis
# ============================================================================

# Get top regulons per cell type
DefaultAssay(seurat_obj) <- "SCENIC"
top_regulons <- get_top_regulons(seurat_obj, group_by = "cell_type", top_n = 10)
print(top_regulons)

# Find cell-type specific regulons
specific_regulons <- find_celltype_specific_regulons(
  seurat_obj,
  group_by = "cell_type",
  min_auc = 0.05
)

print("Cell-type specific regulons:")
for (cell_type in names(specific_regulons)) {
  cat(sprintf("\n%s: %s\n", cell_type, paste(specific_regulons[[cell_type]], collapse = ", ")))
}

# ============================================================================
# Step 6: Visualization
# ============================================================================

# Need to run dimensionality reduction first for visualization
seurat_obj <- FindVariableFeatures(seurat_obj, verbose = FALSE)
seurat_obj <- ScaleData(seurat_obj, verbose = FALSE)
seurat_obj <- RunPCA(seurat_obj, verbose = FALSE)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:10, verbose = FALSE)

# Plot regulon activity on UMAP
# Regulon names follow SCENIC format: "TF_NAME (n_targets)g"
# Replace with actual regulon names from your analysis
plot_regulon_activity(seurat_obj, regulons = c("SOX10 (45g)", "MITF (32g)", "TFAP2A (28g)"))

# Heatmap of regulon activity
DefaultAssay(seurat_obj) <- "SCENIC"
DoHeatmap(seurat_obj, features = rownames(seurat_obj[["SCENIC"]])[1:20])

# ============================================================================
# Alternative: Step-by-Step Execution
# ============================================================================

# If you prefer to run each step individually:

# Step 1: Co-expression network
runCorrelation(exprMat, scenicOptions)

# Step 2: GRN inference with GENIE3 (slow!)
runGenie3(exprMat, scenicOptions, nParts = 10)

# Step 3: Create modules
runSCENIC_1_coexNetwork2modules(scenicOptions)

# Step 4: Create regulons
runSCENIC_2_createRegulons(scenicOptions)

# Step 5: Score cells
runSCENIC_3_scoreCells(exprMat, scenicOptions)

# ============================================================================
# Save Results
# ============================================================================

saveRDS(seurat_obj, "scenic_results.rds")

# Export regulon information
regulons <- load_scenic_results(scenicOptions, "regulons")
write.csv(data.frame(
  regulon = names(regulons),
  n_targets = sapply(regulons, length)
), "regulons_summary.csv", row.names = FALSE)

# ============================================================================
# Notes
# ============================================================================

# 1. cisTarget databases are required and can be downloaded from:
#    https://resources.aertslab.org/cistarget/
#
# 2. The GENIE3 step is the slowest and can take hours for large datasets.
#    Consider using nParts > 10 for parallelization.
#
# 3. SCENIC requires significant memory (8GB+ recommended).
#
# 4. For mouse data, use org = "mmusculus" when initializing.
