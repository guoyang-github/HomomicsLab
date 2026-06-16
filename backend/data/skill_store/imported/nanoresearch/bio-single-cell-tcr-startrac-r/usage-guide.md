# STARTRAC Usage Guide

## Overview

STARTRAC (Single T-cell Analysis by Rna-seq and Tcr TRACking) is a computational framework for dissecting T cell dynamics using paired single-cell RNA-seq and TCR sequencing data. It provides quantitative measures of:

1. **Clonal Expansion**: How much T cells proliferate in specific clusters
2. **Tissue Migration**: How T cells traffic between different anatomical sites
3. **Phenotypic Transition**: How T cells transition between different functional states

## When to Use STARTRAC

### Ideal Use Cases

- **Cancer Immunology**: Analyze tumor-infiltrating lymphocytes (TILs) vs peripheral blood
- **Autoimmune Diseases**: Track T cell dynamics across affected tissues
- **Infection**: Study T cell responses across lymphoid and peripheral tissues
- **Transplantation**: Monitor alloreactive T cell migration patterns

### Data Requirements

**Required Data**:
- Single-cell RNA-seq with cell barcodes
- TCR-seq data (TRA and/or TRB chains) with clonotype annotations
- Cell cluster annotations (from Seurat, SingleR, etc.)
- Sample/patient metadata with tissue location

**Minimum Information per Cell**:
```
Cell_Name:    Unique cell identifier
clone.id:     Clonotype ID (e.g., CDR3 sequence combination)
patient:      Patient/sample identifier
majorCluster: Cell cluster or cell type
loc:          Tissue location (e.g., T, N, PB)
```

## Quick Start

### Complete Workflow

```r
library(Seurat)
library(Startrac)

# Source STARTRAC wrapper
source("scripts/r/startrac_analysis.R")
source("scripts/r/startrac_visualization.R")

# Load your data
seurat_obj <- readRDS("your_data.rds")

# Prepare input
input_data <- prepare_startrac_input(
    seurat_obj,
    clone_col = "tcr_clone_id",
    patient_col = "patient",
    cluster_col = "cell_type",
    loc_col = "tissue"
)

# Run analysis
result <- run_startrac(
    input_data,
    proj = "MyStudy",
    cores = 4,
    n.perm = 100
)

# Visualize
plot_startrac_results(result, output_prefix = "analysis/")
```

## Step-by-Step Guide

### 1. Data Preparation

#### From Seurat Object

```r
# Standard Seurat to STARTRAC conversion
input_data <- prepare_startrac_input(
    seurat_obj,
    clone_col = "clone_id",        # Your TCR column name
    patient_col = "patient_id",     # Patient/sample column
    cluster_col = "cell_type",      # Cluster annotation column
    loc_col = "tissue",             # Tissue location column
    filter_single = TRUE            # Remove singleton clones
)

# Verify format
str(input_data)
table(input_data$loc)
table(input_data$majorCluster)
```

#### From Data Table

```r
# If you have data in a data frame
input_data <- data.frame(
    Cell_Name = rownames(seurat_obj@meta.data),
    clone.id = seurat_obj$clone_id,
    patient = seurat_obj$patient,
    majorCluster = seurat_obj$cell_type,
    loc = seurat_obj$tissue,
    stringsAsFactors = FALSE
)

# Quality control
input_data <- input_data[!is.na(input_data$clone.id), ]
input_data <- input_data[input_data$clone.id != "", ]
```

#### Common Tissue Location Codes

| Code | Description | Use Case |
|------|-------------|----------|
| T | Tumor | Primary tumor tissue |
| N | Normal | Adjacent normal tissue |
| PB | Peripheral Blood | Blood samples |
| LN | Lymph Node | Lymphoid tissue |
| M | Metastasis | Metastatic lesions |
| TI | Tumor Interior | Core tumor region |
| TE | Tumor Edge | Invasive margin |

### 2. Run Analysis

#### Quick Analysis (No Permutation)

```r
result <- run_startrac(
    input_data,
    proj = "CRC",
    cores = 4
)
```

#### Full Analysis (With Significance)

```r
result <- run_startrac(
    input_data,
    proj = "CRC",
    cores = 4,
    n.perm = 100,       # Permutations for p-values
    verbose = 1
)
```

#### Multi-Patient Analysis

```r
# Get results per patient automatically
result <- run_startrac(input_data, proj = "All", cores = 4)

# Access per-patient results in cluster.sig.data
unique(result@cluster.sig.data$aid)
```

### 3. Access and Interpret Results

#### Cluster-Level Indices

```r
# Main indices per cluster
head(result@cluster.data)

# Columns:
# - aid: Analysis/project ID
# - majorCluster: Cell cluster
# - expa: Expansion index (0-1, higher = more expansion)
# - gini: Gini coefficient (clonality measure)
# - migr: Migration index (tissue trafficking)
# - tran: Transition index (state plasticity)
# - NCells: Number of cells in cluster
```

#### Interpretation Guide

| Index | Range | High Values Indicate |
|-------|-------|---------------------|
| expa | 0-1 | Dominant clones, strong expansion |
| migr | 0-1 | Active tissue trafficking |
| tran | 0-1 | Phenotypic plasticity |
| gini | 0-1 | Uneven clonotype distribution |

#### Pairwise Indices

```r
# Migration between tissue pairs
head(result@pIndex.migr)

# Transition between clusters
head(result@pIndex.tran)
```

### 4. Visualization

#### Built-in Plots

```r
library(ggplot2)

# Cluster indices bar plot
plot(result, index.type = "cluster.all", byPatient = FALSE)

# Box plot by patient
plot(result, index.type = "cluster.all", byPatient = TRUE)

# Pairwise migration
plot(result, index.type = "pairwise.migr", byPatient = FALSE)

# Transition heatmap
plot(result, index.type = "pairwise.tran", byPatient = FALSE)
```

#### Custom Visualization

```r
source("scripts/r/startrac_visualization.R")

# Comprehensive plot set
plot_startrac_results(
    result,
    output_prefix = "results/startrac",
    plot_types = c("expansion", "migration", "transition")
)

# Individual plots
plot_expansion_bar(result)
plot_migration_heatmap(result)
plot_transition_network(result)
```

### 5. Export Results

```r
source("scripts/r/startrac_utils.R")

# Export all results
export_startrac_results(
    result,
    output_prefix = "results/startrac",
    formats = c("csv", "rds")
)

# Individual exports
write.csv(result@cluster.data, "cluster_indices.csv")
write.csv(result@pIndex.migr, "migration_indices.csv")
write.csv(result@pIndex.tran, "transition_indices.csv")
```

## Advanced Topics

### Tissue Distribution Analysis

```r
# Analyze tissue distribution preference
dist_result <- calTissueDist(
    input_data,
    byPatient = FALSE,
    method = "chisq"  # chi-square test
)

# Fisher's exact test alternative
dist_result <- calTissueDist(
    input_data,
    method = "fisher"
)

# Frequency-based analysis
dist_result <- calTissueDist(
    input_data,
    method = "freq"
)

# Plot results
plotTissueDist(
    dist_result$OR.tb,
    out.prefix = "results/tissue_dist"
)
```

### Custom Permutation Test

```r
# Run with permutation for significance
obj <- new("Startrac", input_data, aid = "Project", n.perm = 100, cores = 4)
obj <- calIndex(obj, n.perm = 100)
obj <- pIndex(obj, n.perm = 100)
obj <- getSig(obj, obj@cell.perm.data)

# Access significance
head(obj@cluster.sig.data)
# p.value column shows empirical p-values
```

### Filtering and Subsetting

```r
source("scripts/r/startrac_utils.R")

# Filter by clone size
filtered_data <- filter_clones(
    input_data,
    min_size = 2,      # Minimum cells per clone
    max_size = NULL    # No maximum
)

# Filter by patient (minimum cells)
patient_counts <- table(input_data$patient)
valid_patients <- names(patient_counts[patient_counts >= 30])
filtered_data <- input_data[input_data$patient %in% valid_patients, ]
```

### Clonotype Analysis

```r
# Summarize clonotype distribution
clone_summary <- summarize_clonotypes(input_data)
print(clone_summary)

# Top expanded clones
head(clone_summary$top_clones, 10)

# Clonality by cluster
clone_summary$clonality_by_cluster
```

## Analysis Patterns

### Pattern 1: Basic TIL Analysis

```r
# Tumor vs Blood analysis
input_data <- prepare_startrac_input(
    seurat_obj,
    clone_col = "clone_id",
    patient_col = "patient",
    cluster_col = "cell_type",
    loc_col = "tissue"  # Should have "T" and "PB"
)

result <- run_startrac(input_data, proj = "TIL", cores = 4)
plot(result, index.type = "cluster.all")
```

### Pattern 2: Multi-Tissue Analysis

```r
# Tumor, Normal, Blood, Lymph Node
result <- run_startrac(input_data, proj = "Multi", cores = 4)

plot(result, index.type = "pairwise.migr")  # Shows all tissue pairs
```

### Pattern 3: By-Patient Comparison

```r
# Analyze each patient separately
patients <- unique(input_data$patient)
results_list <- lapply(patients, function(pid) {
    pdata <- subset(input_data, patient == pid)
    run_startrac(pdata, proj = pid, cores = 2)
})

# Compare across patients
comparison <- do.call(rbind, lapply(results_list, function(r) {
    r@cluster.data
}))
```

### Pattern 4: Treatment Response

```r
# Pre vs Post treatment
# Add treatment info to patient ID
input_data$patient_treatment <- paste(
    input_data$patient,
    input_data$treatment,
    sep = "_"
)

# Run analysis
custom_data <- input_data
colnames(custom_data)[colnames(custom_data) == "patient"] <- "patient_orig"
colnames(custom_data)[colnames(custom_data) == "patient_treatment"] <- "patient"

result <- run_startrac(custom_data, proj = "Treatment", cores = 4)
```

## Troubleshooting

### Issue: "cell.data must be data.frame and contain these columns"

**Cause**: Missing required columns or wrong column names

**Solution**:
```r
# Check column names
required_cols <- c("Cell_Name", "clone.id", "patient", "majorCluster", "loc")
missing <- setdiff(required_cols, colnames(input_data))
if (length(missing) > 0) {
    print(paste("Missing columns:", paste(missing, collapse = ", ")))
}

# Rename if needed
colnames(input_data)[colnames(input_data) == "your_clone_col"] <- "clone.id"
```

### Issue: "No cells with valid TCR information"

**Cause**: All clone.id values are NA or empty

**Solution**:
```r
# Check TCR data
sum(is.na(input_data$clone.id))
sum(input_data$clone.id == "")

# Filter out cells without TCR
input_data <- input_data[!is.na(input_data$clone.id), ]
input_data <- input_data[input_data$clone.id != "", ]
```

### Issue: Very low expansion indices

**Cause**: Too many singleton clones (unique TCRs)

**Solution**:
```r
# Remove singletons
clone_counts <- table(input_data$clone.id)
recurrent_clones <- names(clone_counts[clone_counts > 1])
input_data <- input_data[input_data$clone.id %in% recurrent_clones, ]
```

### Issue: "Error in validObject(.Object)"

**Cause**: Invalid object construction

**Solution**:
```r
# Check data types
str(input_data)

# Ensure character columns are not factors
input_data$clone.id <- as.character(input_data$clone.id)
input_data$patient <- as.character(input_data$patient)
input_data$majorCluster <- as.character(input_data$majorCluster)
input_data$loc <- as.character(input_data$loc)
```

## AI Agent Test Cases

### Basic Usage
> "Run STARTRAC analysis on T cells with tumor and blood samples"

> "Calculate clonal expansion and migration indices for my TCR data"

> "Visualize STARTRAC results showing expansion by cell type"

### Advanced
> "Compare STARTRAC indices between responders and non-responders"

> "Analyze T cell migration patterns across tumor, normal, and lymph node"

> "Identify highly expanded clones with tissue migration potential"

### Troubleshooting
> "My STARTRAC analysis shows all zero expansion indices - what's wrong?"

> "How to prepare TCR data from Cell Ranger output for STARTRAC?"

## References

1. Zhang et al. (2018). Landscape of infiltrating T cells in liver cancer revealed by single-cell sequencing. *Cell*.
2. Zhang et al. (2019). Single-cell analyses inform mechanisms of myeloid-targeted therapies in colon cancer. *Cell*.
3. STARTRAC GitHub: https://github.com/Japrin/STARTRAC
