# Custom Marker Set Example
# Demonstrates using user-defined markers for specialized tissues

library(Seurat)
library(dplyr)
library(openxlsx)

# Set paths
base_dir <- file.path(getwd(), "..")
if (!dir.exists(file.path(base_dir, "scripts"))) {
  base_dir <- getwd()
}

# Source ScType functions
source(file.path(base_dir, "scripts", "r", "sctype_annotation.R"))
source(file.path(base_dir, "scripts", "r", "gene_sets_prepare.R"))
source(file.path(base_dir, "scripts", "r", "sctype_score.R"))

# ============================================
# Example 1: Custom Markers via R List
# ============================================

message("=== Example 1: Custom Markers via R List ===")

# Create a synthetic PDAC (Pancreatic Ductal Adenocarcinoma) dataset
set.seed(42)
n_cells <- 500
n_genes <- 2000

counts <- matrix(rpois(n_cells * n_genes, lambda = 2), nrow = n_genes, ncol = n_cells)
rownames(counts) <- paste0("GENE", 1:n_genes)
colnames(counts) <- paste0("CELL", 1:n_cells)

# Define marker genes for PDAC cell types
pdac_markers <- list(
  Ductal_Epithelial = c("EPCAM", "KRT8", "KRT18", "KRT19", "MUC1"),
  Acinar = c("PRSS1", "CPA1", "CTRB1", "CTRB2", "REG1A"),
  Endocrine = c("CHGA", "CHGB", "SST", "GCG", "INS"),
  Fibroblast = c("COL1A1", "COL1A2", "VIM", "ACTA2", "PDGFRA"),
  Endothelial = c("PECAM1", "VWF", "CD34", "KDR", "ENG"),
  Macrophage = c("CD68", "CD14", "CSF1R", "FCGR3A", "CD163"),
  T_Cell = c("CD3D", "CD3E", "CD247", "TRAC", "TRBC1"),
  B_Cell = c("CD79A", "CD79B", "MS4A1", "IGHG1", "IGKC")
)

# Add marker expression to simulate cell types
# Replace some genes with actual marker names
for (i in seq_along(pdac_markers)) {
  cell_type <- names(pdac_markers)[i]
  markers <- pdac_markers[[i]]

  # Assign cells to this type (even distribution)
  cells_in_type <- ((i-1) * 62 + 1):min(i * 62, n_cells)

  for (j in seq_along(markers)) {
    gene_idx <- (i-1) * 10 + j
    if (gene_idx <= n_genes) {
      rownames(counts)[gene_idx] <- markers[j]
      counts[gene_idx, cells_in_type] <- counts[gene_idx, cells_in_type] + rpois(length(cells_in_type), 15)
    }
  }
}

# Create Seurat object
pdac <- CreateSeuratObject(counts = counts, min.cells = 3, min.features = 200)
pdac <- NormalizeData(pdac)
pdac <- FindVariableFeatures(pdac, selection.method = "vst", nfeatures = 2000)
pdac <- ScaleData(pdac)
pdac <- RunPCA(pdac, features = VariableFeatures(object = pdac))
pdac <- FindNeighbors(pdac, dims = 1:15)
pdac <- FindClusters(pdac, resolution = 0.6)
pdac <- RunUMAP(pdac, dims = 1:15)

# Define custom markers (positive only)
message("Defining custom marker list...")
custom_markers <- create_marker_list(
  positive_markers = list(
    Ductal = c("EPCAM", "KRT8", "KRT19"),
    Acinar = c("PRSS1", "CPA1", "CTRB1"),
    Endocrine = c("CHGA", "CHGB", "SST"),
    Fibroblast = c("COL1A1", "COL1A2", "VIM"),
    Endothelial = c("PECAM1", "VWF", "CD34"),
    Macrophage = c("CD68", "CD14", "CSF1R"),
    T_Cell = c("CD3D", "CD3E", "CD247"),
    B_Cell = c("CD79A", "CD79B", "MS4A1")
  ),
  negative_markers = list(
    Ductal = c("VIM", "PECAM1", "CD68"),
    Acinar = c("EPCAM", "VIM", "PECAM1"),
    Endocrine = c("VIM", "PECAM1", "CD68"),
    Fibroblast = c("EPCAM", "PECAM1", "CD68"),
    Endothelial = c("EPCAM", "VIM", "CD68"),
    Macrophage = c("EPCAM", "VIM", "CD3D"),
    T_Cell = c("EPCAM", "VIM", "CD68"),
    B_Cell = c("EPCAM", "VIM", "CD68")
  )
)

# Run ScType with custom markers
message("Running ScType with custom markers...")
pdac <- run_sctype_annotation(
  pdac,
  marker_list = custom_markers,
  slot = "data",
  output_col = "custom_annotation",
  plot_results = FALSE
)

# View results
message("\nCell Type Distribution (Custom Markers):")
print(table(pdac$custom_annotation))

message("\nCluster vs Cell Type:")
print(table(pdac$seurat_clusters, pdac$custom_annotation))

# ============================================
# Example 2: Custom Markers via Excel File
# ============================================

message("\n=== Example 2: Custom Markers via Excel File ===")

# Create custom marker Excel file
custom_db <- data.frame(
  tissueType = rep("PDAC_Custom", 5),
  cellName = c("Ductal_Malignant", "Acinar", "Fibroblast", "Macrophage", "T_Cell"),
  geneSymbolmore1 = c(
    "EPCAM,KRT8,KRT18,KRT19,MUC1,CEACAM5",
    "PRSS1,CPA1,CTRB1,CTRB2,REG1A",
    "COL1A1,COL1A2,VIM,ACTA2,PDGFRA",
    "CD68,CD14,CSF1R,FCGR3A,CD163",
    "CD3D,CD3E,CD247,TRAC,TRBC1"
  ),
  geneSymbolmore2 = c(
    "VIM,PECAM1,CD68,CD3D",
    "EPCAM,VIM,PECAM1,CD68",
    "EPCAM,PECAM1,CD68,CD3D",
    "EPCAM,VIM,CD3D,MS4A1",
    "EPCAM,VIM,CD68,MS4A1"
  ),
  shortName = c("Ductal", "Acinar", "Fibro", "Macro", "T"),
  stringsAsFactors = FALSE
)

# Save to Excel
custom_marker_file <- file.path(getwd(), "custom_pdac_markers.xlsx")
write.xlsx(custom_db, custom_marker_file, rowNames = FALSE)
message(paste("Custom marker file saved to:", custom_marker_file))

# Run ScType with custom Excel file
message("\nRunning ScType with custom Excel markers...")
pdac <- run_sctype_annotation(
  pdac,
  marker_file = custom_marker_file,
  tissue = "PDAC_Custom",
  slot = "data",
  output_col = "excel_annotation",
  plot_results = FALSE
)

# View results
message("\nCell Type Distribution (Excel Markers):")
print(table(pdac$excel_annotation))

# Compare annotations
message("\nComparison of Annotation Methods:")
comparison <- table(pdac$custom_annotation, pdac$excel_annotation)
print(comparison)

# ============================================
# Example 3: Fine-tuning Marker Specificity
# ============================================

message("\n=== Example 3: Fine-tuning Marker Specificity ===")

# More specific markers for cancer subtypes
specific_markers <- create_marker_list(
  positive_markers = list(
    Classical_Ductal = c("KRT8", "KRT18", "KRT19", "TFF1", "TFF2"),
    Basal_Like = c("KRT5", "KRT14", "TP63", "NGFR"),
    Fibroblast = c("COL1A1", "COL1A2", "VIM", "ACTA2"),
    Myeloid = c("CD68", "CD14", "LYZ", "FCGR3A"),
    Lymphoid = c("CD3D", "CD3E", "CD79A", "MS4A1")
  ),
  negative_markers = list(
    Classical_Ductal = c("KRT5", "VIM", "CD68"),
    Basal_Like = c("KRT8", "VIM", "CD68"),
    Fibroblast = c("EPCAM", "CD68", "CD3D"),
    Myeloid = c("EPCAM", "VIM", "CD3D"),
    Lymphoid = c("EPCAM", "VIM", "CD68")
  )
)

pdac <- run_sctype_annotation(
  pdac,
  marker_list = specific_markers,
  slot = "data",
  output_col = "specific_annotation",
  score_threshold = 5  # Lower threshold for this example
)

message("\nCell Type Distribution (Specific Markers):")
print(table(pdac$specific_annotation))

# ============================================
# Save Results
# ============================================

output_file <- "pdac_custom_annotated.rds"
saveRDS(pdac, output_file)
message(paste("\nAnnotated object saved to:", output_file))

# Cleanup
tryCatch({
  file.remove(custom_marker_file)
  message("Cleaned up temporary marker file")
}, error = function(e) NULL)

message("\n=== Example Complete ===")
message("This example demonstrated:")
message("1. Creating custom marker lists in R")
message("2. Using custom Excel marker files")
message("3. Fine-tuning marker specificity for subtypes")
