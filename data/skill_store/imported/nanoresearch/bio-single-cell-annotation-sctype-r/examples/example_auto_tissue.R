# Auto Tissue Detection Example
# Demonstrates automatic tissue type detection from built-in database

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
source(file.path(base_dir, "scripts", "r", "auto_detect_tissue.R"))

# ============================================
# Example 1: View Available Tissues
# ============================================

message("=== Available Tissues in ScTypeDB ===")
tissues_full <- get_available_tissues(db_source = "full")
tissues_short <- get_available_tissues(db_source = "short")

message("Full Database (", length(tissues_full), " tissues):")
print(tissues_full)

message("\nShort Database (", length(tissues_short), " tissues):")
print(tissues_short)

# ============================================
# Example 2: Auto-detect on PBMC Data
# ============================================

message("\n=== Example 2: Auto-detect Tissue on PBMC Data ===")

# Create synthetic PBMC data
set.seed(42)
n_cells <- 400
n_genes <- 1500

counts <- matrix(rpois(n_cells * n_genes, lambda = 2), nrow = n_genes, ncol = n_cells)
rownames(counts) <- paste0("GENE", 1:n_genes)
colnames(counts) <- paste0("CELL", 1:n_cells)

# PBMC cell type markers
pbmc_markers <- list(
  CD4_T = c("IL7R", "CD4", "CD3D", "CD3E"),
  CD8_T = c("CD8A", "CD8B", "CD3D", "CD3E"),
  B_Cell = c("CD79A", "CD79B", "MS4A1"),
  Monocyte = c("CD14", "LYZ", "S100A9", "FCGR3A"),
  NK = c("GNLY", "NKG7", "KLRD1", "GZMA")
)

# Add marker expression
for (i in seq_along(pbmc_markers)) {
  cell_type <- names(pbmc_markers)[i]
  markers <- pbmc_markers[[i]]
  cells_in_type <- ((i-1) * 80 + 1):min(i * 80, n_cells)

  for (j in seq_along(markers)) {
    gene_idx <- (i-1) * 10 + j
    if (gene_idx <= n_genes) {
      rownames(counts)[gene_idx] <- markers[j]
      counts[gene_idx, cells_in_type] <- counts[gene_idx, cells_in_type] + rpois(length(cells_in_type), 20)
    }
  }
}

# Create Seurat object
pbmc <- CreateSeuratObject(counts = counts, min.cells = 3, min.features = 200)
pbmc <- NormalizeData(pbmc)
pbmc <- FindVariableFeatures(pbmc, selection.method = "vst", nfeatures = 1500)
pbmc <- ScaleData(pbmc)
pbmc <- RunPCA(pbmc, features = VariableFeatures(object = pbmc))
pbmc <- FindNeighbors(pbmc, dims = 1:10)
pbmc <- FindClusters(pbmc, resolution = 0.5)
pbmc <- RunUMAP(pbmc, dims = 1:10)

# Get database path
db_file <- file.path(base_dir, "assets", "markers", "ScTypeDB_full.xlsx")
if (!file.exists(db_file)) {
  db_file <- file.path(base_dir, "assets", "markers", "ScTypeDB_short.xlsx")
}

if (!file.exists(db_file)) {
  message("Database file not found, skipping auto-detect")
} else {
  # Run auto tissue detection
  message("\nRunning auto tissue detection...")
  message("This tests all tissue types and returns the best match.")
  message("\nTissue detection scores (higher = better match):")
  message("--------------------------------------------------")

  tissue_scores <- auto_detect_tissue_type(
    path_to_db_file = db_file,
    seuratObject = pbmc,
    scaled = FALSE,
    assay = "RNA"
  )

  message("\nTop 5 matching tissues:")
  print(head(tissue_scores, 5))

  # Use top tissue for annotation
  best_tissue <- tissue_scores$tissue[1]
  message(paste("\nUsing best matching tissue:", best_tissue))

  # Run annotation with auto-detected tissue
  pbmc <- run_sctype_annotation(
    pbmc,
    tissue = best_tissue,
    slot = "data",
    output_col = "auto_annotation",
    plot_results = FALSE
  )

  message("\nCell Type Distribution:")
  print(table(pbmc$auto_annotation))
}

# ============================================
# Example 3: Auto-detect with NULL parameter
# ============================================

message("\n=== Example 3: Using NULL for Auto-detection ===")

# Simply pass tissue = NULL to trigger auto-detection
message("Running annotation with tissue = NULL...")
message("This will auto-detect tissue before annotation.")

if (file.exists(db_file)) {
  pbmc <- run_sctype_annotation(
    pbmc,
    tissue = NULL,  # Auto-detect
    db_source = "short",  # Use short for faster auto-detect
    slot = "data",
    output_col = "null_auto_annotation",
    plot_results = FALSE
  )

  message("\nAuto-detected cell types:")
  print(table(pbmc$null_auto_annotation))
}

# ============================================
# Example 4: Compare Multiple Tissues
# ============================================

message("\n=== Example 4: Compare Annotation Across Tissues ===")

if (file.exists(db_file)) {
  # Try annotating with different immune-related tissues
  tissues_to_try <- c("Immune system", "PBMC", "Bone marrow", "Spleen", "Thymus")
  available_to_try <- intersect(tissues_to_try, tissues_full)

  results <- list()

  for (tissue in available_to_try) {
    message(paste("\nTrying tissue:", tissue))

    tryCatch({
      temp_obj <- run_sctype_annotation(
        pbmc,
        tissue = tissue,
        slot = "data",
        output_col = paste0("ann_", gsub(" ", "_", tissue)),
        plot_results = FALSE
      )

      # Count non-Unknown cells
      n_assigned <- sum(temp_obj@meta.data[[paste0("ann_", gsub(" ", "_", tissue))]] != "Unknown")
      message(paste("  Assigned cells:", n_assigned, "/", ncol(pbmc)))

      results[[tissue]] <- n_assigned

      # Copy annotation to main object for comparison
      pbmc@meta.data[[paste0("ann_", gsub(" ", "_", tissue))]] <-
        temp_obj@meta.data[[paste0("ann_", gsub(" ", "_", tissue))]]

    }, error = function(e) {
      message(paste("  Error:", conditionMessage(e)))
    })
  }

  message("\nSummary of tissue comparison:")
  message("(Higher assigned cells = better tissue match)")
  print(sort(unlist(results), decreasing = TRUE))
}

# ============================================
# Example 5: Brain Data Auto-detection
# ============================================

message("\n=== Example 5: Brain Data Auto-detection ===")

# Create synthetic brain data
set.seed(123)
n_cells_brain <- 300
n_genes_brain <- 1200

counts_brain <- matrix(rpois(n_cells_brain * n_genes_brain, lambda = 2),
                       nrow = n_genes_brain, ncol = n_cells_brain)
rownames(counts_brain) <- paste0("GENE", 1:n_genes_brain)
colnames(counts_brain) <- paste0("BRAIN", 1:n_cells_brain)

# Brain cell type markers
brain_markers <- list(
  Excitatory = c("SLC17A7", "CAMK2A", "SATB2"),
  Inhibitory = c("GAD1", "GAD2", "SLC32A1"),
  Astrocyte = c("GFAP", "AQP4", "SLC1A3"),
  Oligodendrocyte = c("MBP", "PLP1", "MOG"),
  Microglia = c("CX3CR1", "P2RY12", "TMEM119"),
  Endothelial = c("CLDN5", "PECAM1", "FLT1")
)

# Add marker expression
for (i in seq_along(brain_markers)) {
  cell_type <- names(brain_markers)[i]
  markers <- brain_markers[[i]]
  cells_in_type <- ((i-1) * 50 + 1):min(i * 50, n_cells_brain)

  for (j in seq_along(markers)) {
    gene_idx <- (i-1) * 10 + j
    if (gene_idx <= n_genes_brain) {
      rownames(counts_brain)[gene_idx] <- markers[j]
      counts_brain[gene_idx, cells_in_type] <- counts_brain[gene_idx, cells_in_type] + rpois(length(cells_in_type), 15)
    }
  }
}

brain <- CreateSeuratObject(counts = counts_brain, min.cells = 3, min.features = 200)
brain <- NormalizeData(brain)
brain <- FindVariableFeatures(brain, nfeatures = 1200)
brain <- ScaleData(brain)
brain <- RunPCA(brain, features = VariableFeatures(object = brain))
brain <- FindNeighbors(brain, dims = 1:10)
brain <- FindClusters(brain, resolution = 0.5)
brain <- RunUMAP(brain, dims = 1:10)

if (file.exists(db_file)) {
  message("\nRunning auto tissue detection on brain data...")

  tissue_scores_brain <- auto_detect_tissue_type(
    path_to_db_file = db_file,
    seuratObject = brain,
    scaled = FALSE,
    assay = "RNA"
  )

  message("\nTop 5 matching tissues for brain data:")
  print(head(tissue_scores_brain, 5))

  # Annotate with best tissue
  best_brain_tissue <- tissue_scores_brain$tissue[1]
  brain <- run_sctype_annotation(
    brain,
    tissue = best_brain_tissue,
    slot = "data",
    output_col = "brain_annotation",
    plot_results = FALSE
  )

  message("\nBrain cell type distribution:")
  print(table(brain$brain_annotation))
}

# ============================================
# Save Results
# ============================================

output_file_pbmc <- "pbmc_auto_tissue.rds"
saveRDS(pbmc, output_file_pbmc)
message(paste("\nPBMC object saved to:", output_file_pbmc))

output_file_brain <- "brain_auto_tissue.rds"
saveRDS(brain, output_file_brain)
message(paste("Brain object saved to:", output_file_brain))

message("\n=== Example Complete ===")
message("This example demonstrated:")
message("1. Listing available tissues from database")
message("2. Manual auto tissue detection")
message("3. Using NULL parameter for auto-detection")
message("4. Comparing multiple tissues on same data")
message("5. Auto-detection on brain data")
