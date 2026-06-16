---
name: bio-spatial-transcriptomics-deconvolution-card-r
description: |
  CARD (Conditional Autoregressive-based Deconvolution) performs spatially-informed
  cell type deconvolution for spatial transcriptomics. Uses a conditional autoregressive
  model to leverage spatial correlation structure while estimating cell type proportions.
  Supports reference-based deconvolution, reference-free mode (CARDfree), high-resolution
  imputation, and single-cell mapping.
tool_type: r
primary_tool: CARD
languages: [r]
keywords: ["spatial", "deconvolution", "CARD", "CAR", "spatial-correlation", "imputation",
           "ct2loc", "reference-free", "high-resolution", "R"]
---

## Version Compatibility

- **R**: >= 4.2.0
- **CARD**: >=1.0 (GitHub: YingMa0107/CARD)
- **Seurat**: >=4.3.0
- **SingleCellExperiment**: >=1.20.0
- **Matrix**: >=1.5
- **ggplot2**: >=3.4.0

## Installation

```r
# Install CARD from GitHub
if (!requireNamespace("devtools", quietly = TRUE)) {
  install.packages("devtools")
}
devtools::install_github("YingMa0107/CARD")

# Install dependencies
install.packages(c("Matrix", "ggplot2", "Rcpp", "RcppArmadillo"))
BiocManager::install(c("SingleCellExperiment", "SummarizedExperiment"))
```

## Data Requirements

Input requirements:
- **Reference scRNA-seq**: Gene expression matrix (genes × cells) with cell type labels
- **Spatial data**: Gene expression matrix (genes × spots) with spatial coordinates
- **Spatial coordinates**: Data frame with x, y coordinates matching spot barcodes
- **Minimum requirements**:
  - Reference: 20+ cells per cell type
  - Spatial: 50+ spots
  - Genes: 100+ common genes between reference and spatial

**Data Validation:**
```r
source("scripts/r/utils.R")

validation <- validate_card_data(
  sc_count = ref_counts,
  spatial_count = spatial_counts,
  spatial_location = spatial_coords,
  sc_meta = metadata,
  min_cells = 20,
  min_genes = 100
)
print_validation_results(validation)
```

## Core Analysis Workflow

### 1. Data Loading and Preparation

**Input formats supported:**
```r
# From Seurat objects
library(Seurat)
ref_obj <- readRDS("reference_sc.rds")
spatial_obj <- readRDS("spatial_data.rds")

# Extract counts and metadata
sc_count <- GetAssayData(ref_obj, layer = "counts", assay = "RNA")
sc_meta <- data.frame(
  cell_type = ref_obj$cell_type,
  sample = ref_obj$sample,
  row.names = colnames(ref_obj)
)

spatial_count <- GetAssayData(spatial_obj, layer = "counts", assay = "Spatial")
spatial_location <- GetTissueCoordinates(spatial_obj)

# From Matrix files
library(Matrix)
sc_count <- readMM("reference_counts.mtx")
spatial_count <- readMM("spatial_counts.mtx")
```

### 2. Create CARD Object

Function: `createCARDObject()`

**Purpose:** Create and validate the CARD object with all input data.

**Key Parameters:**
- `sc_count`: Single-cell count matrix (genes × cells)  (RNA assay)
- `sc_meta`: Metadata with cell type and sample information
- `spatial_count`: Spatial count matrix (genes × spots)  (Spatial assay)
- `spatial_location`: Spatial coordinates data frame (x, y)
- `ct.varname`: Column name for cell type in sc_meta
- `ct.select`: Cell types to include (NULL = all)
- `sample.varname`: `sc_meta` 中的样本列名，用于构建reference时做跨样本批次校正。
  - **单样本reference**：设为 `NULL`（强制）
  - **多样本reference**：设为 `sc_meta` 中存在的列名（如 `"sample"`）
  - **注意**：这是scRNA-seq reference的样本列，不是spatial数据的样本列
- `minCountGene`: Minimum count per gene for filtering (default: 100)
- `minCountSpot`: Minimum count per spot for filtering (default: 5)

**Process:**
1. **QC on scRNA-seq**: Filter low-quality cells and genes
2. **QC on spatial**: Filter low-quality spots and genes
3. **Check gene overlap**: Ensure common genes exist
4. **Check coordinate alignment**: Match spatial barcodes with coordinates

**Example:**
```r
library(CARD)

# Create CARD object
CARD_obj <- createCARDObject(
  sc_count = sc_count,
  sc_meta = sc_meta,
  spatial_count = spatial_count,
  spatial_location = spatial_location,
  ct.varname = "cell_type",
  ct.select = NULL,              # Use all cell types
  sample.varname = "sample",     # Or NULL for single sample
  minCountGene = 100,
  minCountSpot = 5
)
```

### 3. Run CARD Deconvolution

Function: `CARD_deconvolution()`

**Purpose:** Estimate cell type proportions using spatially-informed deconvolution.

**Key Parameters (set in CARD object):**
- `ct.varname`: Cell type column name
- `ct.select`: Selected cell types
- `sample.varname`: Sample column name

**Internal Parameters:**
- `isigma`: Gaussian kernel scale (default: 0.1)
- `epsilon`: Convergence threshold (default: 1e-4)
- `phi`: Grid of spatial correlation values (default: c(0.01,0.1,0.3,0.5,0.7,0.9,0.99))
- `max_iter`: Maximum iterations (default: 1000)

**Process:**
1. **Create reference basis**: Build cell type signature matrix using MuSiC
2. **Select informative genes**: Filter genes with log2FC > 1.25 and low dispersion
3. **Initialize proportions**: Dirichlet initialization
4. **Fit CAR model**: Grid search over phi values, optimize with NNLS
5. **Select optimal phi**: Choose phi with maximum objective function
6. **Normalize proportions**: Row-normalize to sum to 1

**Output:**
CARD object with slots:
- `Proportion_CARD`: Cell type proportion matrix (spots × cell types)
- `algorithm_matrix`: B (basis), Xinput_norm (normalized counts), Res (full results)
- `info_parameters$phi`: Optimal spatial correlation parameter

**Example:**
```r
# Run deconvolution
CARD_obj <- CARD_deconvolution(CARD_obj)

# Extract proportions
proportions <- CARD_obj@Proportion_CARD
head(proportions)
```

### 4. Reference-Free Deconvolution (CARDfree)

Function: `createCARDfreeObject()` and `CARD_refFree()`

**Purpose:** Deconvolute without scRNA-seq reference using marker genes only.

**Key Parameters:**
- `markerList`: List of marker genes per cell type
- `spatial_count`: Spatial count matrix
- `spatial_location`: Spatial coordinates

**Example:**
```r
# Define markers
markerList <- list(
  T_cell = c("CD3D", "CD3E", "CD8A"),
  B_cell = c("CD79A", "CD79B", "MS4A1"),
  Myeloid = c("LYZ", "CD14", "CD68")
)

# Create CARDfree object
CARDfree_obj <- createCARDfreeObject(
  markerList = markerList,
  spatial_count = spatial_count,
  spatial_location = spatial_location,
  minCountGene = 100,
  minCountSpot = 5
)

# Run reference-free deconvolution
CARDfree_obj <- CARD_refFree(CARDfree_obj)
proportions <- CARDfree_obj@Proportion_CARD
```

### 5. High-Resolution Imputation

Function: `CARD.imputation()`

**Purpose:** Impute cell type compositions at higher resolution grid locations.

**Key Parameters:**
- `CARD_object`: CARD object with deconvolution results
- `NumGrids`: Approximate number of new grid locations (default: 2000)
- `ineibor`: Number of neighbors for imputation (default: 10)
- `exclude`: Spots to exclude from shape detection (optional)

**Process:**
1. **Create grid**: Sample points within tissue shape using concave hull
2. **Calculate covariance**: Spatial correlation structure between original and new locations
3. **Conditional MVN**: Impute proportions using conditional multivariate normal

**Example:**
```r
# Run imputation
CARD_obj <- CARD.imputation(
  CARD_obj,
  NumGrids = 2000,
  ineibor = 10,
  exclude = NULL
)

# Access refined results
refined_props <- CARD_obj@refined_prop
refined_expr <- CARD_obj@refined_expression
```

### 6. Single-Cell Mapping

Function: `CARD_SCMapping()`

**Purpose:** Map single cells to spatial locations based on deconvolution results.

**Key Parameters:**
- `CARD_object`: CARD object with results
- `shapeSpot`: "Square" or "Circle" for cell distribution (default: "Square")
- `numCell`: Number of cells per spot (default: 5)
  - ST technology: ~20
  - 10x Visium: ~7
  - Slide-seq: ~2
- `ncore`: Parallel cores (default: 10)

**Example:**
```r
# Map single cells to spatial locations
sce_mapped <- CARD_SCMapping(
  CARD_obj,
  shapeSpot = "Square",
  numCell = 7,
  ncore = 10
)

# Access mapped data
mapped_counts <- assays(sce_mapped)$counts
mapped_coords <- colData(sce_mapped)[, c("x", "y")]
```

### 7. Result Interpretation

```r
source("scripts/r/utils.R")

# Summarize results
summary <- summarize_card_results(CARD_obj)
print(summary)

# Get dominant cell type per spot
dominant <- get_dominant_cell_type(CARD_obj@Proportion_CARD)
table(dominant)

# Calculate spatial entropy (cell type diversity per spot)
entropy <- calculate_spatial_entropy(CARD_obj@Proportion_CARD)
```

### 8. Visualization

**Available plots:**
```r
source("scripts/r/visualization.R")

# Spatial proportion maps
CARD.visualize.prop(
  proportion = CARD_obj@Proportion_CARD,
  spatial_location = CARD_obj@spatial_location,
  ct.visualize = c("T_cell", "B_cell", "Myeloid"),
  colors = c("lightblue", "lightyellow", "red"),
  NumCols = 3,
  pointSize = 3.0
)

# Two cell type comparison
CARD.visualize.prop.2CT(
  proportion = CARD_obj@Proportion_CARD,
  spatial_location = CARD_obj@spatial_location,
  ct2.visualize = c("T_cell", "B_cell"),
  colors = list(c("lightblue", "lightyellow", "red"),
                c("lightblue", "lightyellow", "black"))
)

# Scatterpie plot
CARD.visualize.pie(
  proportion = CARD_obj@Proportion_CARD,
  spatial_location = CARD_obj@spatial_location,
  colors = NULL,    # Auto-generate colors
  radius = NULL,    # Auto-calculate radius
  seed = 12345
)

# Correlation matrix
CARD.visualize.Cor(
  proportion = CARD_obj@Proportion_CARD,
  colors = c("#91a28c", "white", "#8f2c37")
)

# Gene expression visualization
CARD.visualize.gene(
  spatial_expression = CARD_obj@refined_expression,
  spatial_location = CARD_obj@spatial_location,
  gene.visualize = c("CD3D", "CD79A"),
  colors = NULL,
  NumCols = 2
)
```

### 9. Export Results

```r
source("scripts/r/utils.R")

export_card_results(
  CARD_obj,
  output_dir = "card_results",
  prefix = "sample1",
  export_proportions = TRUE,
  export_refined = TRUE,
  export_object = TRUE
)
```

### 10. Complete Pipeline

```r
source("scripts/r/core_analysis.R")

# Run complete analysis
results <- run_card_pipeline(
  sc_count = sc_count,
  sc_meta = sc_meta,
  spatial_count = spatial_count,
  spatial_location = spatial_location,
  ct.varname = "cell_type",
  run_imputation = TRUE,
  NumGrids = 2000,
  output_dir = "results",
  create_plots = TRUE
)
```

## Input Requirements

### Required Data Format

```r
# Single-cell reference
class(sc_count)     # matrix, dgCMatrix
rownames(sc_count)  # Gene symbols
colnames(sc_count)  # Cell barcodes

# Single-cell metadata
class(sc_meta)      # data.frame
head(sc_meta)
#                 cell_type sample
# Cell_AAA       T_cell    S1
# Cell_AAB       B_cell    S1

# Spatial counts
class(spatial_count)     # matrix, dgCMatrix
dim(spatial_count)       # genes × spots

# Spatial coordinates
class(spatial_location)  # data.frame
head(spatial_location)
#           x    y
# Spot_1    1    1
# Spot_2    2    1
```

## Output Specifications

### Core Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Proportions | `Proportion_CARD` | Cell type proportions (spots × cell types) |
| Spatial location | `spatial_location` | Coordinates data frame |
| Optimal phi | `info_parameters$phi` | Estimated spatial correlation |
| Basis matrix | `algorithm_matrix$B` | Reference basis matrix |
| Refined props | `refined_prop` | High-resolution proportions (after imputation) |
| Refined expr | `refined_expression` | High-resolution gene expression (after imputation) |

### CARD Object Structure

| Slot | Description |
|------|-------------|
| `sc_eset` | SingleCellExperiment of reference |
| `spatial_countMat` | Spatial count matrix |
| `spatial_location` | Spatial coordinates |
| `Proportion_CARD` | Estimated proportions |
| `project` | Project name |
| `info_parameters` | Model parameters |
| `algorithm_matrix` | Intermediate matrices |
| `refined_prop` | Refined proportions |
| `refined_expression` | Refined expression |

## Key Parameters

### Deconvolution

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `minCountGene` | 100 | Min count per gene | Lower for shallow data |
| `minCountSpot` | 5 | Min count per spot | Lower for sparse data |
| `isigma` | 0.1 | Kernel scale | Increase for broader spatial effects |
| `phi` | 0.01-0.99 | Spatial correlation grid | Extend range if over/under-smoothing |
| `epsilon` | 1e-4 | Convergence tolerance | Decrease for stricter convergence |

### Imputation

| Parameter | Default | Description | When to Adjust |
|-----------|---------|-------------|----------------|
| `NumGrids` | 2000 | Number of new grid points | Increase for higher resolution |
| `ineibor` | 10 | Neighbors for imputation | Increase for smoother results |
| `concavity` | 2.0 | Shape detail level | Increase for complex tissue shapes |

### Single-Cell Mapping

| Parameter | Default | Description | Technology |
|-----------|---------|-------------|------------|
| `numCell` | 5 | Cells per spot | ST:~20, Visium:~7, Slide-seq:~2 |
| `shapeSpot` | "Square" | Cell distribution | "Circle" for round spots |
| `ncore` | 10 | Parallel cores | Match available cores |

## Expected Runtime

| Dataset Size | Create Object | Deconvolution | Imputation | SC Mapping |
|--------------|---------------|---------------|------------|------------|
| 100 spots, 3 types | <5s | 30-60s | 10-30s | 30s |
| 1K spots, 5 types | 10-30s | 5-10min | 1-5min | 5-10min |
| 5K spots, 10 types | 1-2min | 30-60min | 10-20min | 30-60min |

*Runtime estimates on 8-core CPU with 32GB RAM*

## Error Handling

### Common Errors and Solutions

**No common genes**
```
Error: There are no common gene names in spatial count data and single cell RNAseq count data
```
→ Check gene name consistency (case, format)
→ Ensure gene symbols match between datasets

**Mismatched barcodes**
```
Error: Cell name in scRNAseq count data does not match with the rownames of metaData
```
→ Ensure `rownames(sc_meta) == colnames(sc_count)`
→ Check for whitespace or suffix differences

**Insufficient markers (CARDfree)**
```
Error: The average number of unique marker genes for each cell type is less than 20
```
→ Provide more marker genes per cell type
→ Check marker gene naming consistency

**Coordinate mismatch**
```
Error: The number of spatial locations in spatial_count and spatial_location should be consistent
```
→ Ensure `ncol(spatial_count) == nrow(spatial_location)`
→ Check that barcodes match

**sample.varname 列不存在**
```
Error: sample.varname is not in the meta data
```
→ 确认该列存在于 `sc_meta`，而非spatial对象
→ 若reference为单样本，将 `sample.varname` 设为 `NULL`

## Common Analysis Patterns

### Pattern 1: Quick Deconvolution
```r
CARD_obj <- createCARDObject(sc_count, sc_meta, spatial_count, spatial_location,
                             ct.varname = "cell_type")
CARD_obj <- CARD_deconvolution(CARD_obj)
proportions <- CARD_obj@Proportion_CARD
```

### Pattern 2: With Cell Type Selection
```r
ct_select <- c("T_cell", "B_cell", "Myeloid", "Fibroblast")
CARD_obj <- createCARDObject(sc_count, sc_meta, spatial_count, spatial_location,
                             ct.varname = "cell_type", ct.select = ct_select)
CARD_obj <- CARD_deconvolution(CARD_obj)
```

### Pattern 3: High-Resolution Analysis
```r
# Run deconvolution
CARD_obj <- CARD_deconvolution(CARD_obj)

# Impute to higher resolution
CARD_obj <- CARD.imputation(CARD_obj, NumGrids = 5000, ineibor = 15)

# Map single cells
sce_mapped <- CARD_SCMapping(CARD_obj, numCell = 7, ncore = 10)
```

### Pattern 4: Reference-Free Analysis
```r
markerList <- list(
  T_cell = c("CD3D", "CD3E", "CD8A"),
  B_cell = c("CD79A", "CD79B", "MS4A1"),
  Myeloid = c("LYZ", "CD14", "CD68")
)
CARDfree_obj <- createCARDfreeObject(markerList, spatial_count, spatial_location)
CARDfree_obj <- CARD_refFree(CARDfree_obj)
```

### Pattern 5: Multi-Sample Analysis
```r
samples <- c("S1", "S2", "S3")
results_list <- lapply(samples, function(s) {
  sp_count <- spatial_counts[[s]]
  sp_loc <- spatial_locations[[s]]
  CARD_obj <- createCARDObject(sc_count, sc_meta, sp_count, sp_loc,
                               ct.varname = "cell_type", sample.varname = "sample")
  CARD_deconvolution(CARD_obj)
})
```

## Module Structure

```
scripts/r/
├── core_analysis.R       # run_card_pipeline(), create_card_object_extended()
├── visualization.R       # CARD.visualize.*() wrappers
├── imputation.R          # CARD.imputation() wrappers
├── mapping.R             # CARD_SCMapping() wrappers
└── utils.R               # validate_card_data(), summarize_card_results(),
                          # export_card_results(), get_dominant_cell_type()

examples/
├── minimal_example.R     # Basic CARD usage
└── advanced_example.R    # Full pipeline with imputation and mapping

tests/
└── test_card.R           # Unit tests
```

## Interpretation Guidelines

### Understanding Phi Parameter

- **Low phi (<0.3)**: Weak spatial correlation, proportions more independent
- **Medium phi (0.3-0.7)**: Moderate spatial smoothing
- **High phi (>0.7)**: Strong spatial correlation, extensive smoothing

### Quality Assessment

**Good deconvolution:**
- Clear spatial patterns matching tissue structure
- Reasonable cell type proportions per spot
- Correlation matrix shows expected relationships
- Low residuals in algorithm_matrix$Res

**Potential issues:**
- Uniform proportions: Check phi parameter
- No spatial pattern: Check spatial coordinates
- Single dominant type: May need more cell types

### Cell Type Proportions

- Sum to 1 per spot (after normalization)
- Values represent relative abundance
- Dominant type: highest proportion per spot
- Mixed spots: multiple cell types with significant proportions

## Related Skills

- [bio-spatial-transcriptomics-deconvolution-spotlight-r](../bio-spatial-transcriptomics-deconvolution-spotlight-r/SKILL.md) - SPOTlight deconvolution
- [bio-spatial-transcriptomics-deconvolution-rctd-r](../bio-spatial-transcriptomics-deconvolution-rctd-r/SKILL.md) - RCTD deconvolution
- [bio-spatial-transcriptomics-deconvolution-cell2location](../bio-spatial-transcriptomics-deconvolution-cell2location/SKILL.md) - cell2location (Python)

## References

1. Ma et al. (2022). CARD: Computational deconvolution of spatial transcriptomics with conditional autoregressive model. *Nature Communications*, 13: 5871. https://doi.org/10.1038/s41467-022-35027-3
2. CARD GitHub: https://github.com/YingMa0107/CARD
3. CARD Tutorial: https://yingma0107.github.io/CARD/
