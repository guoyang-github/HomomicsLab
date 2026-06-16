---
name: bio-single-cell-tcr-startrac-r
description: |
  STARTRAC (Single T-cell Analysis by Rna-seq and Tcr TRACking) for T cell dynamics analysis.
  Quantifies T cell clonotype expansion, migration between tissues, and state transitions.
  Provides three core indices: STARTRAC-expa (clonal expansion), STARTRAC-migr (tissue migration),
  and STARTRAC-tran (phenotypic transition). Supports multi-patient analysis with permutation-based
  significance testing.
tool_type: r
primary_tool: Startrac
supported_tools: [Seurat, data.table, plyr, ggplot2, ComplexHeatmap]
languages: [r]
keywords: ["single-cell", "tcr", "startrac", "t-cell", "clonotype", "migration", "transition", 
           "expansion", "dynamics", "trajectory", "r"]
code_location: scripts/r/
version_compatibility:
  r: ">=3.4"
  startrac: ">=0.1.0"
  seurat: ">=4.3.0"
---

## Version Compatibility

- **R**: 3.4+
- **Startrac**: 0.1.0+
- **Seurat**: >= 4.3.0 (optional, for input objects; compatible with both v4 and v5)
- **Dependencies**: data.table, plyr, doParallel, ggplot2, ComplexHeatmap, RColorBrewer, circlize, ggpubr

## Installation

```r
# Install from GitHub
if (!requireNamespace("devtools", quietly = TRUE))
    install.packages("devtools")
devtools::install_github("Japrin/STARTRAC")

# Or install dependencies manually
install.packages(c("data.table", "plyr", "doParallel", "ggplot2", "ggpubr",
                   "RColorBrewer", "circlize"))
BiocManager::install("ComplexHeatmap")
```

# STARTRAC TCR Dynamics Analysis

Analyze T cell clonal dynamics using single-cell RNA-seq and TCR sequencing data. STARTRAC quantifies three key aspects of T cell behavior:

1. **STARTRAC-expa**: Clonal expansion within cell clusters
2. **STARTRAC-migr**: Migration of T cells between tissues
3. **STARTRAC-tran**: Phenotypic transitions between cell states

## Quick Selector

### When to Use STARTRAC

- **TCR-seq data available**: Paired scRNA-seq and TCR sequencing
- **Multi-tissue sampling**: Same patient, different anatomical locations
- **Tumor immunity studies**: TIL analysis with peripheral blood comparison
- **Clonal dynamics tracking**: Understanding expansion and migration patterns

### Input Data Requirements

| Column | Description | Required |
|--------|-------------|----------|
| `Cell_Name` | Unique cell identifier | Yes |
| `clone.id` | Clonotype identifier (e.g., CDR3 sequences) | Yes |
| `patient` | Patient/sample identifier | Yes |
| `majorCluster` | Cell cluster annotation | Yes |
| `loc` | Tissue location (e.g., T/N/PB) | Yes |

---

## Quick Start

```r
library(Startrac)

# Source wrapper functions
source("scripts/r/startrac_analysis.R")

# Prepare input data from Seurat
input_data <- prepare_startrac_input(
    seurat_obj,
    clone_col = "clone_id",
    patient_col = "patient",
    cluster_col = "cell_type",
    loc_col = "tissue"
)

# Run STARTRAC analysis
result <- run_startrac(
    input_data,
    proj = "MyProject",
    cores = 4,
    n.perm = 100  # For significance testing
)

# Visualize results
plot(result, index.type = "cluster.all", byPatient = FALSE)
```

---

## Detailed Usage

### 1. Data Preparation

#### From Seurat Object

```r
source("scripts/r/startrac_analysis.R")

# Convert Seurat to STARTRAC input
input_data <- prepare_startrac_input(
    seurat_obj,
    clone_col = "clone_id",        # Column with clonotype IDs
    patient_col = "patient_id",     # Column with patient IDs
    cluster_col = "cell_type",      # Column with cell type/clusters
    loc_col = "tissue",             # Column with tissue location
    filter_single = TRUE            # Remove cells with unique clone IDs
)

# Check input format
head(input_data)
# Expected columns: Cell_Name, clone.id, patient, majorCluster, loc
```

#### Manual Data Preparation

```r
# Create input data frame manually
input_data <- data.frame(
    Cell_Name = seurat_obj$cell_barcode,
    clone.id = seurat_obj$tcr_clone_id,
    patient = seurat_obj$patient_id,
    majorCluster = seurat_obj$cell_type,
    loc = seurat_obj$tissue_location,
    stringsAsFactors = FALSE
)

# Filter requirements:
# - Remove cells without TCR information (NA clone.id)
# - Remove cells with unique clonotypes (optional)
input_data <- input_data[!is.na(input_data$clone.id), ]
```

### 2. Run Complete Analysis

```r
# Basic analysis
result <- run_startrac(
    input_data,
    proj = "CRC",           # Project identifier
    cores = 4,              # Number of cores for parallel processing
    n.perm = NULL,          # No permutation test
    verbose = 1             # Include intermediate objects
)

# With significance testing (permutation-based)
result <- run_startrac(
    input_data,
    proj = "CRC",
    cores = 4,
    n.perm = 100,           # Number of permutations for p-value
    verbose = 1
)
```

### 3. Access Results

```r
# Cluster-level indices
head(result@cluster.data)
# Columns: aid, majorCluster, expa, gini, migr, tran, NCells

# Pairwise migration indices
head(result@pIndex.migr)
# Migration between tissue pairs

# Pairwise transition indices
head(result@pIndex.tran)
# Transition between cluster pairs

# Significance data (if n.perm specified)
head(result@cluster.sig.data)
head(result@pIndex.sig.migr)
```

### 4. Step-by-Step Analysis

```r
library(Startrac)

# Step 1: Create Startrac object
obj <- new("Startrac", input_data, aid = "CRC")

# Step 2: Calculate cluster-level indices (expa, migr, tran)
obj <- calIndex(obj, cores = 4)

# Step 3: Calculate pairwise indices
obj <- pIndex(obj, cores = 4)

# Step 4: Get significance (optional)
obj <- getSig(obj, obj@cell.perm.data)

# Access results
head(obj@cluster.data)
head(obj@clonotype.data)
```

---

## Parameters

### Main Function: `run_startrac()`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cell.data` | data.frame | Required | Input data with required columns |
| `proj` | character | "CRC" | Project identifier |
| `cores` | integer | NULL | Number of cores for parallel processing |
| `n.perm` | integer | NULL | Number of permutations for significance |
| `verbose` | integer | 0 | Verbosity level (0-2) |

### Input Data Columns

| Column | Description |
|--------|-------------|
| `Cell_Name` | Unique cell identifier |
| `clone.id` | Clonotype ID (e.g., TRA+TRB CDR3) |
| `patient` | Patient/sample identifier |
| `majorCluster` | Cell cluster or cell type |
| `loc` | Tissue location code |

### Tissue Location Codes

Common conventions:
- `T`: Tumor
- `N`: Normal tissue
- `PB`: Peripheral blood
- `LN`: Lymph node
- `M`: Metastasis

---

## API Reference

| Function | Location | Description |
|----------|----------|-------------|
| `run_startrac()` | startrac_analysis.R | Main wrapper function |
| `prepare_startrac_input()` | startrac_analysis.R | Convert Seurat to input format |
| `plot_startrac_results()` | startrac_visualization.R | Comprehensive visualization |
| `export_startrac_results()` | startrac_utils.R | Export to CSV/Excel |
| `Startrac.run()` | Startrac package | Official pipeline function |
| `calIndex()` | Startrac package | Calculate cluster indices |
| `pIndex()` | Startrac package | Calculate pairwise indices |
| `getSig()` | Startrac package | Calculate significance |

---

## Index Interpretation

### STARTRAC-expa (Expansion Index)

Measures clonal expansion within each cluster.

- **Range**: 0-1
- **Interpretation**: Higher values indicate more clonal expansion
- **Calculation**: 1 - normalized entropy of clonotype distribution

```r
# High expansion: Few clones dominate
# Low expansion: Even clonotype distribution
```

### STARTRAC-migr (Migration Index)

Measures tissue migration potential of clonotypes.

- **Range**: 0-1 (or 0-log2(n_loc) if not normalized)
- **Interpretation**: Higher values indicate more migration between tissues
- **Calculation**: Mean entropy of clonotype tissue distribution

### STARTRAC-tran (Transition Index)

Measures phenotypic plasticity between cell states.

- **Range**: 0-1 (or 0-log2(n_cluster) if not normalized)
- **Interpretation**: Higher values indicate more state transitions
- **Calculation**: Mean entropy of clonotype cluster distribution

---

## Visualization

### Built-in Plotting

```r
library(ggplot2)
library(ComplexHeatmap)

# Plot cluster-level indices
plot(result, index.type = "cluster.all", byPatient = FALSE)

# Plot by patient (boxplot)
plot(result, index.type = "cluster.all", byPatient = TRUE)

# Plot pairwise migration
plot(result, index.type = "pairwise.migr", byPatient = FALSE)

# Plot transition heatmap
plot(result, index.type = "pairwise.tran", byPatient = FALSE)
```

### Custom Visualization

```r
source("scripts/r/startrac_visualization.R")

# Create comprehensive plots
plot_startrac_results(
    result,
    output_prefix = "startrac_analysis",
    plot_types = c("cluster", "migration", "transition")
)

# Individual plots
plot_expansion_bar(result)
plot_migration_heatmap(result)
plot_transition_network(result)
```

---

## Advanced Analysis

### Tissue Distribution Analysis

```r
source("scripts/r/startrac_utils.R")

# Calculate tissue distribution preference
dist_result <- calTissueDist(
    input_data,
    byPatient = FALSE,
    method = "chisq"  # or "fisher", "freq"
)

# Plot tissue distribution
plotTissueDist(dist_result$OR.tb)
```

### Multi-Patient Analysis

```r
# Run STARTRAC for each patient separately
patients <- unique(input_data$patient)
patient_results <- lapply(patients, function(pid) {
    patient_data <- subset(input_data, patient == pid)
    run_startrac(patient_data, proj = pid, cores = 2)
})

# Compare across patients
comparison_df <- compare_startrac_patients(patient_results)
```

---

## Output Description

### StartracOut Object Slots

| Slot | Description |
|------|-------------|
| `proj` | Project identifier |
| `cluster.data` | Cluster-level indices (expa, migr, tran) |
| `cluster.sig.data` | Significance values for cluster indices |
| `pIndex.migr` | Pairwise migration indices |
| `pIndex.tran` | Pairwise transition indices |
| `pIndex.sig.migr` | Significance for migration |
| `pIndex.sig.tran` | Significance for transition |

---

## Module Structure

```
scripts/r/
├── startrac_analysis.R      # Main analysis wrapper functions
│   - prepare_startrac_input()
│   - run_startrac()
├── startrac_visualization.R # Visualization functions
│   - plot_startrac_results()
│   - plot_expansion_bar()
│   - plot_migration_heatmap()
│   - plot_transition_network()
└── startrac_utils.R         # Utility functions
    - export_startrac_results()
    - filter_clones()
    - summarize_clonotypes()
```

---

## Related Skills

- [bio-single-cell-data-io](../bio-single-cell-data-io/SKILL.md) - Loading scRNA-seq and TCR data
- [bio-single-cell-annotation-sctype-r](../bio-single-cell-annotation-sctype-r/SKILL.md) - Cell type annotation
- [bio-single-cell-trajectory-monocle3-r](../bio-single-cell-trajectory-monocle3-r/SKILL.md) - Trajectory inference
- [bio-single-cell-communication-cellchat-r](../bio-single-cell-communication-cellchat-r/SKILL.md) - Cell-cell communication

---

## References

1. Zhang et al. (2018). Landscape of infiltrating T cells in liver cancer revealed by single-cell sequencing. *Cell*. https://doi.org/10.1016/j.cell.2017.11.041

2. Zhang et al. (2019). Single-cell analyses inform mechanisms of myeloid-targeted therapies in colon cancer. *Cell*. https://doi.org/10.1016/j.cell.2019.03.029

3. STARTRAC GitHub: https://github.com/Japrin/STARTRAC

4. Nature paper: https://www.nature.com/articles/s41586-018-0694-x
