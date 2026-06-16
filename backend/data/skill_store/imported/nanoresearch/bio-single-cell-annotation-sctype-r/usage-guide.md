# ScType R - Usage Guide

## Overview

ScType is a marker-based cell type annotation method for single-cell RNA sequencing data. This R implementation integrates seamlessly with Seurat objects and provides:

- Built-in marker databases for 15+ tissues
- Support for custom marker sets
- Automatic tissue type detection
- Confidence scoring with adjustable thresholds

## Prerequisites

### Required R Packages

```r
install.packages(c("dplyr", "openxlsx", "HGNChelper"))
if (!requireNamespace("BiocManager", quietly = TRUE))
    install.packages("BiocManager")
BiocManager::install("Seurat")
```

## Quick Start

### 1. Source the Functions

```r
# Set working directory to skill root or use full paths
source("scripts/r/sctype_annotation.R")
```

### 2. Basic Annotation Workflow

```r
# Load your Seurat object (must have clusters)
seurat_obj <- readRDS("your_data.rds")

# Run annotation with Immune system markers
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system"
)

# Visualize
DimPlot(seurat_obj, group.by = "sctype_cell_type", label = TRUE, repel = TRUE)
```

## Common Use Cases

### Use Case 1: Auto-detect Tissue Type

When tissue origin is unknown:

```r
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = NULL,        # Auto-detect
    slot = "data"
)

# Check which tissue was selected
check_tissue <- auto_detect_tissue_type(
    path_to_db_file = "assets/markers/ScTypeDB_full.xlsx",
    seuratObject = seurat_obj,
    scaled = FALSE,
    assay = "RNA"
)
print(check_tissue)
```

### Use Case 2: Custom Markers for Specialized Tissues

For tissues not in the built-in database:

```r
# Define your own markers
my_markers <- create_marker_list(
    positive_markers = list(
        "Tumor_Epithelial" = c("EPCAM", "KRT8", "KRT18"),
        "Fibroblast" = c("COL1A1", "COL1A2", "VIM"),
        "Endothelial" = c("PECAM1", "VWF", "CD34"),
        "T_Cell" = c("CD3D", "CD3E", "CD247"),
        "Macrophage" = c("CD68", "CD14", "CSF1R")
    ),
    negative_markers = list(
        "Tumor_Epithelial" = c("VIM", "PECAM1"),
        "Fibroblast" = c("EPCAM", "PECAM1"),
        "Endothelial" = c("EPCAM", "COL1A1"),
        "T_Cell" = c("CD68", "EPCAM"),
        "Macrophage" = c("CD3D", "EPCAM")
    )
)

seurat_obj <- run_sctype_annotation(
    seurat_obj,
    marker_list = my_markers
)
```

### Use Case 3: Use Custom Excel Marker File

Create an Excel file with the ScTypeDB format:

| tissueType | cellName | geneSymbolmore1 | geneSymbolmore2 |
|------------|----------|-----------------|-----------------|
| PDAC | Ductal | EPCAM,KRT8,KRT18 | VIM,PECAM1 |
| PDAC | Acinar | PRSS1,CPA1,CTRB1 | EPCAM,VIM |
| PDAC | Fibroblast | COL1A1,COL1A2,VIM | EPCAM,CD68 |

```r
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    marker_file = "path/to/pdac_markers.xlsx",
    tissue = "PDAC"
)
```

### Use Case 4: Adjust Confidence Thresholds

For stricter or looser assignments:

```r
# Stricter threshold
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    score_threshold = 20    # Only high-confidence assignments
)

# More permissive (default is ncells/4)
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    score_threshold = 5
)
```

### Use Case 5: Working with Different Seurat Versions

The function auto-detects Seurat v4 vs v5:

```r
# Works with both v4 and v5
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    assay = "RNA",         # Or "SCT" for SCTransform
    slot = "data"          # Or "scale.data" for scaled data
)
```

### Use Case 6: Access Full Score Matrix

For downstream analysis:

```r
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    return_scores = TRUE
)

# Access cell-level scores
scores <- seurat_obj@misc$sctype_cell_type_scores

# Access cluster-level results
cluster_scores <- seurat_obj@misc$sctype_cell_type_cluster_scores

# Find alternative assignments
head(cluster_scores[order(cluster_scores$cluster, -cluster_scores$scores), ], 20)
```

## Output Interpretation

### Cell Type Assignments

The function adds a metadata column (default: `sctype_cell_type`) with:
- Assigned cell type names
- "Unknown" for low-confidence assignments

### Score Interpretation

- Higher scores = more confident assignment
- Default threshold: `ncells/4` (quarter of cells in cluster)
- Scores are normalized by marker set size

### Quality Control

```r
# Check distribution of cell types
table(seurat_obj$sctype_cell_type)

# Check for many "Unknown" cells (may indicate need for custom markers)
prop.table(table(seurat_obj$sctype_cell_type))

# Compare with manual cluster inspection
VlnPlot(seurat_obj, features = c("CD3E", "CD79A", "LYZ"), group.by = "sctype_cell_type")
```

## Troubleshooting

### Issue: All cells labeled "Unknown"

**Cause**: Low scores or marker mismatch

**Solutions**:
1. Lower threshold: `score_threshold = 5`
2. Check data slot: Try `slot = "scale.data"`
3. Verify gene names: Ensure uppercase gene symbols
4. Check tissue selection: Try auto-detect or different tissue

### Issue: Markers not found in dataset

**Cause**: Gene name format mismatch

**Solution**:
```r
# Check your gene names
head(rownames(seurat_obj))

# Convert to uppercase if needed
rownames(seurat_obj) <- toupper(rownames(seurat_obj))
```

### Issue: Seurat version conflicts

**Cause**: Mixed v4/v5 syntax

**Solution**: Function auto-detects version, but verify:
```r
# Check version
packageVersion("Seurat")

# If issues, specify explicitly
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    slot = "data"
)
```

## Best Practices

1. **Pre-filtering**: Run on good-quality cells only
2. **Clustering**: Ensure clusters are well-defined before annotation
3. **Marker validation**: Check known markers in your tissue
4. **Multiple tissues**: Try related tissues if unsure
5. **Custom markers**: For specialized tissues, custom markers often work better

## Example Workflow

```r
# Complete workflow example
library(Seurat)

# 1. Load data
seurat_obj <- CreateSeuratObject(counts = raw_data)

# 2. Standard preprocessing
seurat_obj <- NormalizeData(seurat_obj)
seurat_obj <- FindVariableFeatures(seurat_obj)
seurat_obj <- ScaleData(seurat_obj)
seurat_obj <- RunPCA(seurat_obj)
seurat_obj <- FindNeighbors(seurat_obj, dims = 1:10)
seurat_obj <- FindClusters(seurat_obj, resolution = 0.8)
seurat_obj <- RunUMAP(seurat_obj, dims = 1:10)

# 3. Source ScType
source("scripts/r/sctype_annotation.R")

# 4. Run annotation
seurat_obj <- run_sctype_annotation(
    seurat_obj,
    tissue = "Immune system",
    plot_results = TRUE,
    return_scores = TRUE
)

# 5. Visualize
p1 <- DimPlot(seurat_obj, group.by = "seurat_clusters", label = TRUE)
p2 <- DimPlot(seurat_obj, group.by = "sctype_cell_type", label = TRUE)
(p1 + p2)

# 6. Save results
saveRDS(seurat_obj, "annotated_data.rds")
```
