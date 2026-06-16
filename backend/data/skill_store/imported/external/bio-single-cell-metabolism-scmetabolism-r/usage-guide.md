# scMetabolism Usage Guide

## Overview

scMetabolism quantifies metabolic pathway activities in single-cell RNA-seq data using multiple gene set scoring algorithms. This guide provides step-by-step instructions for using the skill effectively.

## When to Use

Use scMetabolism when you need to:

- **Compare metabolic states** across cell types or conditions
- **Identify metabolic heterogeneity** within a cell population
- **Investigate pathway-level changes** in disease or treatment
- **Integrate metabolism** with cell type annotations
- **Visualize metabolic activities** on dimensionality reduction plots

### Typical Applications

| Application | Example |
|-------------|---------|
| Cancer metabolism | Glycolysis vs OXPHOS in tumor microenvironment |
| Immune cell states | Metabolic reprogramming in T cell activation |
| Stem cell differentiation | Metabolic shifts during differentiation |
| Drug response | Metabolic pathway changes after treatment |
| Spatial metabolism | Metabolic zonation in tissues |

## Quick Start

```r
library(Seurat)

# Source functions
source("scripts/r/run_scmetabolism.R")
source("scripts/r/visualize_scmetabolism.R")

# Load data
seurat_obj <- readRDS("your_data.rds")

# Run analysis
result <- run_scmetabolism(seurat_obj, method = "VISION")
seurat_obj <- result$seurat_obj

# Visualize
dimplot_metabolism(seurat_obj, pathway = "Glycolysis / Gluconeogenesis")
```

## Step-by-Step Workflow

### Step 1: Prepare Data

#### Load Seurat Object

```r
library(Seurat)

# Load your processed Seurat object
seurat_obj <- readRDS("seurat_processed.rds")

# Ensure data is normalized and has dimensionality reduction
# Required: RNA assay with counts or data slot
# Recommended: UMAP or tSNE reduction for visualization

# Check structure
seurat_obj
```

#### Data Requirements

- **Raw counts** (slot="counts") or **normalized data** (slot="data")
- Minimum 10 cells per gene, 10 genes per cell (adjustable)
- Metabolic pathway genes should be present in your gene set
- Recommended: cell type annotations in metadata

### Step 2: Choose Algorithm and Database

#### Algorithm Selection

```r
# For general use (balanced)
result <- run_scmetabolism(seurat_obj, method = "VISION")

# For large datasets (>10,000 cells)
result <- run_scmetabolism(seurat_obj, method = "AUCell")

# For detailed pathway analysis
result <- run_scmetabolism(seurat_obj, method = "ssGSEA")

# For standard GSVA analysis
result <- run_scmetabolism(seurat_obj, method = "GSVA")
```

#### Database Selection

```r
# KEGG - 85 metabolic pathways
result <- run_scmetabolism(seurat_obj, metabolism.type = "KEGG")

# REACTOME - 82 metabolic pathways
result <- run_scmetabolism(seurat_obj, metabolism.type = "REACTOME")
```

### Step 3: Run Analysis

#### Basic Analysis

```r
result <- run_scmetabolism(
  seurat_obj = seurat_obj,
  method = "VISION",
  metabolism.type = "KEGG",
  ncores = 4
)

seurat_obj <- result$seurat_obj
metabolism_matrix <- result$metabolism_matrix
```

#### Advanced Parameters

```r
result <- run_scmetabolism(
  seurat_obj = seurat_obj,
  method = "VISION",
  metabolism.type = "KEGG",
  imputation = FALSE,      # Set TRUE for very sparse data
  ncores = 8,              # Adjust based on available cores
  assay = "RNA",           # Alternative assay name
  slot = "counts",         # or "data" for normalized
  min.cells = 10,          # Minimum cells expressing gene
  min.feature = 10,        # Minimum genes per cell
  output_assay = "METABOLISM",
  return_matrix = TRUE
)
```

### Step 4: Explore Results

#### List Available Pathways

```r
# Get all KEGG pathways
kegg <- get_metabolic_pathways("KEGG")
print(kegg)

# Search for specific pathways
glycolysis_related <- kegg[grep("Glycolysis|Glucose|Pyruvate", kegg)]
print(glycolysis_related)
```

#### Extract Scores

```r
# Get all scores
all_scores <- extract_metabolism_scores(seurat_obj)

# Get specific pathways
glycolysis_scores <- extract_metabolism_scores(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Citrate cycle (TCA cycle)")
)

# Check dimensions
dim(all_scores)  # pathways x cells
```

#### Find Variable Pathways

```r
# Top 10 most variable pathways
top10 <- get_top_variable_pathways(seurat_obj, n_top = 10)
print(top10)

# Top 20
top20 <- get_top_variable_pathways(seurat_obj, n_top = 20)
```

### Step 5: Visualize

#### Dimensionality Reduction Overlay

```r
# UMAP with glycolysis scores
dimplot_metabolism(
  seurat_obj,
  pathway = "Glycolysis / Gluconeogenesis",
  reduction = "umap",
  size = 0.5,
  palette = "Zissou1"
)

# tSNE with OXPHOS
dimplot_metabolism(
  seurat_obj,
  pathway = "Oxidative phosphorylation",
  reduction = "tsne",
  palette = "plasma"
)

# Multiple pathways - save plots
pathways_to_plot <- c(
  "Glycolysis / Gluconeogenesis",
  "Oxidative phosphorylation",
  "Citrate cycle (TCA cycle)"
)

for (pw in pathways_to_plot) {
  p <- dimplot_metabolism(seurat_obj, pathway = pw, size = 0.5)
  ggsave(sprintf("umap_%s.pdf", gsub(" / ", "_", pw)), p, width = 6, height = 5)
}
```

#### Compare Across Groups

```r
# Dot plot by cell type
dotplot_metabolism(
  seurat_obj,
  pathways = top10[1:6],
  group.by = "cell_type",
  norm = "y"  # Normalize by pathway (row)
)

# Alternative: normalize by group (column)
dotplot_metabolism(
  seurat_obj,
  pathways = top10[1:6],
  group.by = "cell_type",
  norm = "x"
)

# No normalization
dotplot_metabolism(
  seurat_obj,
  pathways = top10[1:6],
  group.by = "cell_type",
  norm = "na"
)
```

#### Box Plots

```r
# Compare glycolysis between conditions
boxplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Oxidative phosphorylation"),
  group.by = "condition",
  ncol = 2
)

# By cell type with custom colors
boxplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis"),
  group.by = "cell_type",
  fill_color = "steelblue"
)
```

#### Heatmap

```r
# Heatmap of top pathways
heatmap_metabolism(
  seurat_obj,
  pathways = get_top_variable_pathways(seurat_obj, 20),
  group.by = "cell_type",
  scale = "row",           # Scale by pathway
  clustering_method = "ward.D2"
)

# Without scaling
heatmap_metabolism(
  seurat_obj,
  pathways = top10,
  group.by = "cell_type",
  scale = "none"
)
```

#### Violin and Ridge Plots

```r
# Violin plot
violinplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis"),
  group.by = "cell_type"
)

# Ridge plot
ridgeplot_metabolism(
  seurat_obj,
  pathways = c("Glycolysis / Gluconeogenesis", "Fatty acid degradation"),
  group.by = "cell_type",
  ncol = 1
)
```

### Step 6: Statistical Comparison

```r
# Compare metabolism between groups
comparison <- compare_metabolism(
  seurat_obj,
  group.by = "condition",
  pathways = get_top_variable_pathways(seurat_obj, 10),
  test = "wilcox"
)

# View results
head(comparison)

# Focus on specific comparison
library(dplyr)
comparison %>%
  filter(pathway == "Glycolysis / Gluconeogenesis") %>%
  arrange(desc(mean))
```

### Step 7: Export Results

```r
# Export all results
export_scmetabolism_results(
  seurat_obj,
  output_dir = "scmetabolism_output",
  prefix = "sample_analysis"
)

# Files created:
# - sample_analysis_scores.csv (cell x pathway matrix)
# - sample_analysis_params.txt (analysis parameters)
# - sample_analysis_mean_by_group.csv (group averages)

# Save annotated Seurat object
saveRDS(seurat_obj, "seurat_with_metabolism.rds")
```

## Methods

### VISION (Recommended Default)

```r
# Best for: General use, balanced performance
result <- run_scmetabolism(seurat_obj, method = "VISION")
```

- Uses random walk with restarts on cell-cell similarity graph
- Accounts for expression similarity between cells
- Good balance of speed and accuracy
- Memory: Medium | Speed: Medium

### AUCell

```r
# Best for: Large datasets, fast screening
result <- run_scmetabolism(seurat_obj, method = "AUCell", ncores = 4)
```

- Area Under the Curve calculation
- Fast and memory efficient
- Good for datasets >10,000 cells
- Memory: Low | Speed: Fast

### ssGSEA

```r
# Best for: Detailed pathway analysis
result <- run_scmetabolism(seurat_obj, method = "ssGSEA", ncores = 8)
```

- Single-sample Gene Set Enrichment Analysis
- Most sensitive for detecting subtle pathway differences
- Computationally intensive
- Memory: High | Speed: Slow

### GSVA

```r
# Best for: Standard pathway analysis
result <- run_scmetabolism(seurat_obj, method = "GSVA")
```

- Gene Set Variation Analysis
- Non-parametric, unsupervised
- Standard method for pathway enrichment
- Memory: Medium | Speed: Medium

## Pathway Databases

### KEGG (Default)

85 metabolic pathways including:

| Category | Count | Examples |
|----------|-------|----------|
| Carbohydrate Metabolism | 7 | Glycolysis, TCA cycle, Pentose phosphate |
| Energy Metabolism | 5 | Oxidative phosphorylation, Photosynthesis |
| Lipid Metabolism | 14 | Fatty acid synthesis/degradation, Steroids |
| Nucleotide Metabolism | 4 | Purine, Pyrimidine metabolism |
| Amino Acid Metabolism | 18 | Alanine, Glycine, Glutamate metabolism |
| Metabolism of Cofactors/Vitamins | 14 | Porphyrin, Riboflavin metabolism |
| Biosynthesis | 13 | Secondary metabolites, Terpenoids |

### REACTOME

82 metabolic pathways with alternative annotations and gene sets.

## Best Practices

### 1. Input Data

- Use **raw counts** for most accurate results
- For very sparse data, consider `imputation = TRUE`
- Ensure metabolic genes are present in your dataset

### 2. Algorithm Choice

| Dataset Size | Recommended Method |
|--------------|-------------------|
| < 5,000 cells | VISION or ssGSEA |
| 5,000 - 20,000 cells | VISION (default) |
| > 20,000 cells | AUCell |

### 3. Computational Resources

- Start with `ncores = 2` and increase based on memory
- Monitor memory usage with large datasets
- Consider subsampling for initial exploration

### 4. Interpretation

- Compare relative scores within a dataset, not across datasets
- Use multiple pathways to build metabolic profile
- Validate with known metabolic markers
- Consider cell type-specific metabolism

### 5. Common Pitfalls

- **Don't** compare absolute scores between different algorithms
- **Don't** expect all pathways to show variation
- **Do** check that pathway genes are expressed in your data
- **Do** consider batch effects in metabolic gene expression

## Advanced Usage

### Running on Raw Matrix

```r
# For non-Seurat workflows
metabolism_matrix <- run_scmetabolism_matrix(
  countexp = raw_counts,
  method = "VISION",
  metabolism.type = "KEGG",
  ncores = 4
)

# Add to Seurat object manually
seurat_obj[["METABOLISM"]] <- CreateAssayObject(data = as.matrix(metabolism_matrix))
```

### Comparing Multiple Methods

```r
# Run with different methods
result_v <- run_scmetabolism(seurat_obj, method = "VISION", output_assay = "METAB_V")
result_a <- run_scmetabolism(seurat_obj, method = "AUCell", output_assay = "METAB_A")

# Compare correlations for a pathway
v_scores <- extract_metabolism_scores(result_v$seurat_obj, assay = "METAB_V")
a_scores <- extract_metabolism_scores(result_a$seurat_obj, assay = "METAB_A")

correlation <- cor(
  as.numeric(v_scores["Glycolysis / Gluconeogenesis", ]),
  as.numeric(a_scores["Glycolysis / Gluconeogenesis", ])
)
print(sprintf("Correlation: %.3f", correlation))
```

### Custom Pathway Analysis

```r
# After running scMetabolism, subset to pathways of interest
pathways_of_interest <- c(
  "Glycolysis / Gluconeogenesis",
  "Citrate cycle (TCA cycle)",
  "Oxidative phosphorylation",
  "Pentose phosphate pathway"
)

# Create focused heatmap
heatmap_metabolism(
  seurat_obj,
  pathways = pathways_of_interest,
  group.by = "cell_type",
  scale = "row"
)
```

## Troubleshooting

### Pathway Not Found

```r
# Error: "Pathway 'X' not found"

# Solution 1: List all available pathways
all_pathways <- get_metabolic_pathways("KEGG")
print(all_pathways)

# Solution 2: Search for partial matches
matches <- grep("Glycolysis", all_pathways, value = TRUE)
print(matches)  # "Glycolysis / Gluconeogenesis"
```

### Low Scores Everywhere

```r
# Try using normalized data instead of counts
result <- run_scmetabolism(seurat_obj, slot = "data")

# Or enable imputation for sparse data
result <- run_scmetabolism(seurat_obj, imputation = TRUE)
```

### Out of Memory

```r
# Reduce cores
result <- run_scmetabolism(seurat_obj, ncores = 1)

# Use faster method
result <- run_scmetabolism(seurat_obj, method = "AUCell")

# Subsample cells
seurat_subset <- subset(seurat_obj, downsample = 5000)
result <- run_scmetabolism(seurat_subset)
```

### Missing Genes

```r
# Check overlap with pathway genes
library(scMetabolism)
kegg_file <- system.file("data", "KEGG_metabolism_nc.gmt", package = "scMetabolism")
gene_sets <- GSEABase::getGmt(kegg_file)
pathway_genes <- unique(unlist(lapply(gene_sets, function(x) x@geneIds)))

your_genes <- rownames(seurat_obj)
overlap <- intersect(your_genes, pathway_genes)
print(sprintf("Overlap: %d / %d pathway genes (%.1f%%)",
              length(overlap), length(pathway_genes),
              100 * length(overlap) / length(pathway_genes)))
```

## References

1. Wu Y, Yang S, Ma J, et al. Spatiotemporal Immune Landscape of Colorectal Cancer Liver Metastasis at Single-Cell Level. Cancer Discovery. 2021.
2. DeTomaso D, et al. Functional interpretation of single cell similarity maps. Nat Commun. 2019.
3. Aibar S, et al. SCENIC: single-cell regulatory network inference and clustering. Nat Methods. 2017.
4. Hänzelmann S, et al. GSVA: gene set variation analysis for microarray and RNA-seq data. BMC Bioinformatics. 2013.

## See Also

- Full API reference: [SKILL.md](SKILL.md)
- Complete example: [examples/example_basic.R](examples/example_basic.R)
- scMetabolism package: https://github.com/wu-yc/scMetabolism
