# scTenifoldKnk Usage Guide

## Overview

scTenifoldKnk is a machine learning workflow that performs in-silico (virtual) gene knockdown experiments using single-cell RNA sequencing data. It constructs single-cell gene regulatory networks (scGRNs) from wild-type data, simulates gene knockout by removing the target gene's outgoing edges, and identifies differentially regulated genes.

### Key Features

- **In-silico perturbation**: Predict gene knockout effects without wet lab experiments
- **Network-based approach**: Uses gene regulatory networks and manifold learning
- **Tensor decomposition**: Denoises networks using CP decomposition
- **Differential regulation**: Identifies genes affected by the knockout

### When to Use scTenifoldKnk

| Scenario | Recommended Tool |
|----------|------------------|
| Predict gene knockout effects | **scTenifoldKnk** |
| In-silico drug target validation | **scTenifoldKnk** |
| Study TF perturbations | **scTenifoldKnk** |
| Compare with real CRISPR data | **scTenifoldKnk** + experimental |
| Perturb-seq analysis | pertpy |
| General perturbation analysis | pertpy or scTenifoldKnk |

## Quick Start

### Installation

```r
# Install from GitHub
if (!requireNamespace("remotes", quietly = TRUE)) {
  install.packages("remotes")
}
remotes::install_github("cailab-tamu/scTenifoldKnk")

# Load package
library(scTenifoldKnk)
library(Seurat)
```

### Basic Workflow

```r
# Load count matrix
counts <- GetAssayData(seurat_obj, slot = "counts")

# Run in-silico knockdown
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "POU5F1",  # Gene to knock out
  qc = TRUE,
  nc_nNet = 10,
  nc_nCells = 500
)

# View results
head(result$diffRegulation)
```

## Step-by-Step Guide

### Step 1: Load and Prepare Data

#### From Seurat Object

```r
library(Seurat)

# Load data
seurat_obj <- readRDS("single_cell_data.rds")

# Extract count matrix
counts <- GetAssayData(seurat_obj, slot = "counts")

# Check dimensions
dim(counts)

# Verify gene names
head(rownames(counts))
```

#### From Matrix Files

```r
library(Matrix)

# Load MatrixMarket format
counts <- readMM("matrix.mtx")
rownames(counts) <- readLines("genes.txt")
colnames(counts) <- readLines("barcodes.txt")

# Optional: Filter mitochondrial/ribosomal genes
counts <- counts[!grepl("^MT-|^RPL|^RPS", rownames(counts), ignore.case = TRUE), ]
```

#### Data Validation

```r
source("scripts/r/utils.R")

validation <- validate_knk_data(
  counts,
  target_gene = "POU5F1",
  min_cells = 300,
  min_genes = 1000
)

print_validation_results(validation)
```

### Step 2: Run In-silico Knockdown

```r
# Basic usage
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "POU5F1",
  qc = TRUE,
  qc_minLSize = 1000,
  qc_mtThreshold = 0.1,
  nc_nNet = 10,
  nc_nCells = 500,
  nc_q = 0.9,
  nCores = 4
)

# Custom parameters for large datasets
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "TREM2",
  nc_nNet = 20,      # More networks for stability
  nc_nCells = 1000,  # More cells per network
  nc_q = 0.95,       # Stricter edge threshold
  td_K = 5,          # Higher rank tensor decomposition
  nCores = 8
)
```

**Parameter Guidelines:**

| Parameter | Default | When to Increase | When to Decrease |
|-----------|---------|------------------|------------------|
| `nc_nNet` | 10 | Small datasets (<500 cells) | Large datasets (>5000 cells) |
| `nc_nCells` | 500 | Heterogeneous populations | Memory constraints |
| `nc_q` | 0.9 | Sparse networks needed | Dense networks preferred |
| `td_K` | 3 | Complex regulatory patterns | Faster computation |

### Step 3: Interpret Results

```r
# Access differential regulation results
dr <- result$diffRegulation

# View top significant genes
head(dr[order(dr$p.adj), ])

# Filter significant genes
sig_genes <- dr$gene[dr$p.adj < 0.05]
up_genes <- dr$gene[dr$p.adj < 0.05 & dr$Z > 0]
down_genes <- dr$gene[dr$p.adj < 0.05 & dr$Z < 0]

# Summary statistics
source("scripts/r/utils.R")
summary <- summarize_knockdown_results(result)
print(summary$statistics)
```

**Understanding Output:**

| Column | Interpretation |
|--------|----------------|
| `gene` | Gene symbol |
| `distance` | Euclidean distance in manifold space |
| `Z` | Z-score (Box-Cox transformed) |
| `FC` | Fold change vs expectation |
| `p.value` | Raw p-value |
| `p.adj` | FDR-adjusted p-value |

### Step 4: Multiple Gene Knockdowns

```r
source("scripts/r/core_analysis.R")

# Define genes to knock down
genes_to_knock <- c("POU5F1", "SOX2", "NANOG", "KLF4")

# Run batch analysis
results <- run_multiple_knockdowns(
  countMatrix = counts,
  gene_list = genes_to_knock,
  nc_nNet = 10,
  nc_nCells = 500,
  verbose = TRUE
)

# Access individual results
pou5f1_result <- results[["POU5F1"]]
sox2_result <- results[["SOX2"]]

# Compare knockdowns
comparison <- compare_knockdowns(results, method = "correlation")
print(comparison)
```

### Step 5: Visualize Results

```r
source("scripts/r/visualization.R")

# Volcano plot
plot_volcano(
  result,
  gKO = "POU5F1",
  p_cutoff = 0.05,
  label_top_n = 15,
  save_path = "volcano.png"
)

# Top affected genes barplot
plot_top_genes(
  result,
  n = 20,
  direction = "both",
  save_path = "top_genes.png"
)

# Network plot (requires plotKO from scTenifoldKnk)
plot_ko_network(
  result,
  gKO = "POU5F1",
  q = 0.99,
  annotate = TRUE,
  save_path = "network.png"
)
```

### Step 6: Pathway Enrichment

```r
source("scripts/r/enrichment.R")

# Run enrichment analysis
enrichment <- run_enrichment_analysis(
  result,
  databases = c(
    "KEGG_2019_Human",
    "GO_Biological_Process_2018",
    "Reactome_2016"
  ),
  p_cutoff = 0.05,
  organism = "human"
)

# View top pathways
head(enrichment$enrichr$KEGG_2019_Human)

# Plot enrichment
plot_enrichment(
  enrichment,
  database = "KEGG_2019_Human",
  n_terms = 15,
  save_path = "enrichment.png"
)
```

### Step 7: Compare with Experimental Data

```r
# Load experimental differential expression
exp_de <- read.csv("experimental_knockdown.csv")

# Compare with prediction
comparison <- compare_with_experiment(
  predicted = result,
  experimental = exp_de,
  method = "correlation"
)

# View correlation
cat(sprintf("Spearman rho: %.3f\n", comparison$correlation$rho))
cat(sprintf("P-value: %.2e\n", comparison$correlation$p.value))

# Plot comparison
plot_prediction_validation(comparison, save_path = "validation.png")
```

### Step 8: Complete Pipeline

```r
# Run complete analysis with all outputs
result <- run_complete_knockdown_analysis(
  countMatrix = counts,
  gKO = "POU5F1",
  output_dir = "results",
  run_enrichment = TRUE,
  create_plots = TRUE,
  qc = TRUE,
  nc_nNet = 10,
  nc_nCells = 500
)

# Generate report
report <- create_knockdown_report(
  result,
  gKO = "POU5F1",
  output_file = "report.txt"
)

# Export results
export_knockdown_results(
  result,
  output_dir = "results",
  prefix = "POU5F1_knockdown",
  export_networks = TRUE,
  export_genelist = TRUE,
  export_tables = TRUE
)
```

## Advanced Topics

### Memory Management for Large Datasets

```r
# For datasets > 5000 cells
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "TREM2",
  nc_nNet = 5,       # Fewer networks
  nc_nCells = 1000,  # But more cells per network
  nc_q = 0.95,       # Stricter threshold = sparser matrix
  nCores = 1         # Single core to reduce memory
)
```

### Custom Quality Control

```r
# If you have pre-filtered data
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "POU5F1",
  qc = FALSE  # Skip internal QC
)

# Or custom thresholds
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "POU5F1",
  qc = TRUE,
  qc_minLSize = 500,      # Lower minimum library size
  qc_mtThreshold = 0.2,   # Higher mitochondrial threshold
  qc_minCells = 10        # Fewer cells required per gene
)
```

### Network Customization

```r
# For directed networks (strong directionality)
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "POU5F1",
  nc_symmetric = FALSE,
  nc_lambda = 0.5  # Stronger directionality enforcement
)

# For denser networks
result <- scTenifoldKnk(
  countMatrix = counts,
  gKO = "POU5F1",
  nc_q = 0.8,      # Include more edges
  nc_scaleScores = FALSE  # Don't normalize
)
```

## Troubleshooting

### Gene Not Found After QC

```r
# Check if gene is present
"POU5F1" %in% rownames(counts)

# Check expression level
sum(counts["POU5F1", ] > 0)

# Disable QC if gene is borderline
result <- scTenifoldKnk(counts, gKO = "POU5F1", qc = FALSE)
```

### Memory Issues

```r
# Reduce parameters
result <- scTenifoldKnk(
  counts,
  gKO = "POU5F1",
  nc_nNet = 3,     # Fewer networks
  nc_nCells = 200, # Fewer cells per network
  nCores = 1       # Single core
)
```

### Long Running Time

```r
# For faster execution (less accurate)
result <- scTenifoldKnk(
  counts,
  gKO = "POU5F1",
  nc_nNet = 3,      # Fewer networks
  nc_nCells = 200,
  td_maxIter = 100, # Fewer iterations
  nCores = parallel::detectCores()  # Use all cores
)
```

## AI Agent Test Cases

### Basic Usage
> "Run scTenifoldKnk in-silico knockdown for gene POU5F1"

```r
result <- scTenifoldKnk(counts, gKO = "POU5F1")
```

### Multiple Genes
> "Predict effects of knocking down OCT4, SOX2, and NANOG"

```r
genes <- c("POU5F1", "SOX2", "NANOG")
results <- run_multiple_knockdowns(counts, gene_list = genes)
```

### With Enrichment
> "Run scTenifoldKnk and identify enriched pathways"

```r
result <- scTenifoldKnk(counts, gKO = "TREM2")
enrichment <- run_enrichment_analysis(result)
```

### Validation
> "Compare scTenifoldKnk predictions with experimental data"

```r
predicted <- scTenifoldKnk(counts, gKO = "TREM2")
comparison <- compare_with_experiment(predicted, experimental_de)
```

## Interpretation Guidelines

### Understanding Z-scores

- **Z > 2**: Strongly upregulated after knockout
- **Z < -2**: Strongly downregulated after knockout
- **|Z| > 1.96**: Statistically significant (approximate)

### Network Effects

- **Direct targets**: Genes with very high Z-scores, likely direct regulators
- **Secondary effects**: Moderate Z-scores, indirect regulation
- **Opposite direction**: Genes that increase when TF is knocked down (likely repressed by TF)

### Validation Criteria

Good predictions should show:
- Correlation > 0.3 with experimental data
- Significant overlap with known target genes
- Enriched pathways consistent with gene function

## Best Practices

1. **Input Data**: Use raw counts, 300+ cells, 1000+ genes
2. **Target Selection**: Choose genes with sufficient expression (>10 cells)
3. **QC Settings**: Adjust based on your data quality
4. **Network Parameters**: More networks = more stable but slower
5. **Validation**: Always compare with experimental data when available
6. **Biological Context**: Consider cell type specificity

## References

1. Osorio et al. (2020). Systematic characterization of gene knockdown perturbations in single-cell data. *bioRxiv*. https://doi.org/10.1101/2020.09.18.301879
2. scTenifoldKnk GitHub: https://github.com/cailab-tamu/scTenifoldKnk
3. scTenifoldKnk Python: https://github.com/qwerty239qwe/scTenifoldpy
4. scGEAToolbox (MATLAB): https://github.com/jamesjcai/scGEAToolbox
