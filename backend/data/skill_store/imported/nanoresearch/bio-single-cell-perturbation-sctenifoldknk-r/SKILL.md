---
name: bio-single-cell-perturbation-sctenifoldknk-r
description: |
  scTenifoldKnk performs in-silico gene knockdown experiments on single-cell gene regulatory networks.
  Uses network-based manifold learning to predict gene knockout effects without wet lab experiments.
  Constructs scGRNs from wild-type data, simulates knockout by zeroing target gene edges, and identifies
tool_type: r
primary_tool: scTenifoldKnk
languages: [r]
keywords: ["single-cell", "perturbation", "knockdown", "scTenifoldKnk", "gene-knockout",
           "network", "manifold-learning", "in-silico", "virtual-knockout", "R"]
---

## Version Compatibility

- **R**: >= 4.2.0
- **scTenifoldKnk**: >=1.0
- **scTenifoldNet**: >=1.0 (dependency for network construction)
- **Seurat**: >=4.0 (for data input)
- **Matrix**: >=1.5
- **igraph**: >=1.3 (for network visualization)
- **enrichR**: >=3.0 (for enrichment analysis)
- **fgsea**: >=1.20 (for pathway enrichment)

## Installation

```r
# Install from GitHub
if (!requireNamespace("remotes", quietly = TRUE)) {
  install.packages("remotes")
}
remotes::install_github("cailab-tamu/scTenifoldKnk")

# Load required packages
library(scTenifoldKnk)
library(scTenifoldNet)
library(Seurat)
library(Matrix)
```

## Data Requirements

Input requirements:
- **Count matrix**: Genes × cells matrix (sparse or dense)
  - Genes as row names (HGNC symbols recommended)
  - Cells as column names
  - Raw counts or normalized data accepted
- **Gene to knockout**: Must be present in row names of count matrix
- **Minimum requirements**:
  - At least 300 cells
  - At least 1000 genes
  - Gene of interest must be expressed in sufficient cells

**Data Validation:**
```r
source("scripts/r/utils.R")

# Check if data is suitable
validation <- validate_knk_data(
  count_matrix,
  target_gene = "POU5F1",
  min_cells = 300,
  min_genes = 1000
)
print_validation_results(validation)
```

## Core Analysis Workflow

### 1. Data Loading and Preparation

**Input formats supported:**
```r
# From Seurat object (recommended)
library(Seurat)
seurat_obj <- readRDS("data.rds")
counts <- GetAssayData(seurat_obj, slot = "counts")

# From matrix file
library(Matrix)
counts <- readMM("matrix.mtx")
rownames(counts) <- readLines("genes.txt")
colnames(counts) <- readLines("barcodes.txt")

# Filter mitochondrial and ribosomal genes (optional)
counts <- counts[!grepl("^MT-|^RPL|^RPS", rownames(counts), ignore.case = TRUE), ]
```

**Key Points:**
- Raw counts preferred (QC will be applied internally)
- Gene symbols should be unique
- Sufficient cell numbers required for network construction

### 2. Run In-silico Knockdown

Function: `run_knockdown_analysis(countMatrix, gKO, ...)`

**Purpose:** Perform virtual knockout experiment and identify differentially regulated genes.

**Key Parameters:**
- `countMatrix`: Gene expression matrix (genes × cells)
- `gKO`: Gene symbol to knock out (must exist in rownames)
- `qc`: Apply quality control (default: TRUE)
- `qc_minLSize`: Minimum library size per cell (default: 1000)
- `qc_mtThreshold`: Maximum mitochondrial ratio (default: 0.1)
- `nc_nNet`: Number of networks to generate (default: 10)
- `nc_nCells`: Cells to subsample per network (default: 500)
- `nc_nComp`: PCA components for network construction (default: 3)
- `nc_q`: Quantile threshold for network edges (default: 0.9)
- `td_K`: Rank-one tensors for CP decomposition (default: 3)
- `ma_nDim`: Dimensions for manifold alignment (default: 2)
- `nCores`: Number of parallel cores (default: detectCores())

**Process:**
1. Quality control (optional): Filter cells by library size and mitochondrial content
2. Network construction: Build ensemble of gene regulatory networks using PCR
3. Tensor decomposition: Denoise networks using CP decomposition
4. Knockout simulation: Zero outgoing edges from target gene
5. Manifold alignment: Align WT and KO networks in low-dimensional space
6. Differential regulation: Compute distances and identify affected genes

**Output:**
List containing:
- `tensorNetworks$WT`: Wild-type network (sparse matrix)
- `tensorNetworks$KO`: Knockout network (sparse matrix)
- `manifoldAlignment`: Aligned low-dimensional coordinates
- `diffRegulation`: Data frame with differential regulation results

**Example:**
```r
source("scripts/r/core_analysis.R")

# Run basic knockdown analysis
result <- run_knockdown_analysis(
  countMatrix = counts,
  gKO = "POU5F1",
  qc = TRUE,
  qc_minLSize = 1000,
  nc_nNet = 10,
  nc_nCells = 500,
  verbose = TRUE
)
```

### 3. Result Interpretation

Function: `summarize_knockdown_results(result, ...)`

**Purpose:** Extract and interpret knockdown analysis results.

**Output Columns:**
- `gene`: Gene symbol
- `distance`: Euclidean distance between WT and KO in manifold space
- `Z`: Z-score after Box-Cox transformation
- `FC`: Fold change relative to expectation
- `p.value`: Statistical significance (chi-square)
- `p.adj`: FDR-adjusted p-value

**Example:**
```r
source("scripts/r/utils.R")

# View summary
summary <- summarize_knockdown_results(result)
print(summary)

# Get significantly affected genes
sig_genes <- get_significant_genes(result, p_cutoff = 0.05)
cat("Significant genes:", length(sig_genes), "\n")

# Get top upregulated/downregulated genes
top_up <- get_top_affected_genes(result, direction = "up", n = 20)
top_down <- get_top_affected_genes(result, direction = "down", n = 20)
```

### 4. Multiple Gene Knockdowns

Function: `run_multiple_knockdowns(countMatrix, gene_list, ...)`

**Purpose:** Run knockdown analysis for multiple genes in batch.

**Example:**
```r
# Define genes to knock down
genes_to_knock <- c("POU5F1", "SOX2", "NANOG", "KLF4")

# Run multiple knockdowns
results <- run_multiple_knockdowns(
  countMatrix = counts,
  gene_list = genes_to_knock,
  qc = TRUE,
  nc_nNet = 10,
  verbose = TRUE
)

# Access individual results
pou5f1_result <- results[["POU5F1"]]
sox2_result <- results[["SOX2"]]
```

### 5. Visualization

**Available plots:**
```r
source("scripts/r/visualization.R")

# Volcano plot of differential regulation
plot_volcano(result, gKO = "POU5F1", save_path = "volcano.png")

# Network plot centered on knocked-out gene
plot_ko_network(result, gKO = "POU5F1", q = 0.99, annotate = TRUE)

# Top affected genes barplot
plot_top_genes(result, n = 20, save_path = "top_genes.png")

# Compare multiple knockdowns
plot_comparison_heatmap(results, save_path = "comparison.png")
```

### 6. Pathway Enrichment Analysis

Function: `run_enrichment_analysis(result, ...)`

**Purpose:** Identify enriched pathways in differentially regulated genes.

**Example:**
```r
source("scripts/r/enrichment.R")

# Run enrichment on significant genes
enrichment <- run_enrichment_analysis(
  result,
  databases = c("KEGG_2019_Human", "GO_Biological_Process_2018"),
  p_cutoff = 0.05,
  fdr_threshold = 0.05
)

# View top enriched pathways
print(enrichment$KEGG)
print(enrichment$GO_BP)

# Plot enrichment results
plot_enrichment(enrichment, save_path = "enrichment.png")
```

### 7. Compare with Real Knockdown Data

Function: `compare_with_experiment(predicted, experimental, ...)`

**Purpose:** Validate predictions against real CRISPR/drug perturbation data.

**Example:**
```r
# Load experimental differential expression
exp_de <- read.csv("experimental_de.csv")

# Compare with predicted
comparison <- compare_with_experiment(
  predicted = result,
  experimental = exp_de,
  method = "correlation"
)

# Plot comparison
plot_prediction_validation(comparison, save_path = "validation.png")
```

### 8. Complete Pipeline

Function: `run_complete_knockdown_analysis(countMatrix, gKO, ...)`

**Purpose:** Run the complete analysis pipeline with all outputs.

**Example:**
```r
source("scripts/r/core_analysis.R")

result <- run_complete_knockdown_analysis(
  countMatrix = counts,
  gKO = "POU5F1",
  output_dir = "knockdown_results",
  run_enrichment = TRUE,
  create_plots = TRUE,
  verbose = TRUE
)

# Generate report
report <- create_knockdown_report(result, output_file = "report.txt")
```

### 9. Export Results

Function: `export_knockdown_results(result, output_dir, ...)`

**Example:**
```r
source("scripts/r/utils.R")

export_knockdown_results(
  result,
  output_dir = "results",
  prefix = "POU5F1_knockdown",
  export_networks = TRUE,
  export_genelist = TRUE,
  export_tables = TRUE
)
```

## Input Requirements

### Required Data Format

```r
# Matrix format: genes as rows, cells as columns
class(counts)  # Matrix or dgCMatrix

# Check dimensions
dim(counts)  # Should be [n_genes, n_cells]

# Required row/gene names
head(rownames(counts))
# [1] "A1BG" "A1CF" "A2M"  "A2ML1" "A3GALT2" "A4GALT"

# Required column/cell names
head(colnames(counts))
# [1] "AAACCTGAGCAGCCTC-1" "AAACCTGAGTCGAGTG-1" ...
```

### Quality Control Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `qc_minLSize` | 1000 | Minimum UMIs per cell |
| `qc_mtThreshold` | 0.1 | Maximum mitochondrial ratio |
| `qc_minCells` | 25 | Minimum cells per gene |

## Output Specifications

### Core Outputs

| Output | Location | Description |
|--------|----------|-------------|
| WT Network | `result$tensorNetworks$WT` | Wild-type gene regulatory network |
| KO Network | `result$tensorNetworks$KO` | Knockout gene regulatory network |
| Manifold Alignment | `result$manifoldAlignment` | Aligned low-dimensional coordinates |
| Differential Regulation | `result$diffRegulation` | Affected genes data frame |

### Differential Regulation Columns

| Column | Description |
|--------|-------------|
| `gene` | Gene symbol |
| `distance` | Euclidean distance in manifold space |
| `Z` | Z-score (Box-Cox transformed) |
| `FC` | Fold change vs expectation |
| `p.value` | Raw p-value (chi-square) |
| `p.adj` | FDR-adjusted p-value |

### Network Construction Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `nc_nNet` | 10 | Number of networks in ensemble |
| `nc_nCells` | 500 | Cells subsampled per network |
| `nc_nComp` | 3 | PCA components for PCR |
| `nc_q` | 0.9 | Edge weight quantile threshold |
| `nc_lambda` | 0 | Directionality strength |
| `td_K` | 3 | CP tensor decomposition rank |
| `ma_nDim` | 2 | Manifold alignment dimensions |

## Expected Runtime

| Cells | Genes | Networks | Runtime |
|-------|-------|----------|---------|
| 300 | 1,000 | 10 | ~3.5 min |
| 1,000 | 1,000 | 10 | ~4.5 min |
| 1,000 | 5,000 | 10 | ~3 hours |
| 5,000 | 5,000 | 10 | ~3 hours |
| 7,500 | 7,500 | 10 | ~10 hours |

*Runtime estimates on 8-core CPU with 32GB RAM*

## Error Handling

### Common Errors and Solutions

**Gene not found**
```
Error: POU5F1 is not present in the count matrix
```
→ Check gene symbol spelling and case
→ Verify gene exists: `target_gene %in% rownames(counts)`

**Gene filtered out during QC**
```
Error: POU5F1 is not present after quality control
```
→ Disable QC: `qc = FALSE`
→ Or lower `qc_minCells` threshold

**Insufficient cells**
```
Error: nNet * nCells > total cells
```
→ Reduce `nc_nNet` or `nc_nCells` parameters
→ Or use more cells in input

**Memory issues**
```
Error: cannot allocate vector of size X Gb
```
→ Reduce `nc_nNet` or `nc_nCells`
→ Reduce number of genes in input
→ Use fewer cores: `nCores = 1`

## Common Analysis Patterns

### Pattern 1: Quick Single Gene Knockdown
```r
result <- scTenifoldKnk(counts, gKO = "POU5F1")
sig_genes <- result$diffRegulation$gene[result$diffRegulation$p.adj < 0.05]
```

### Pattern 2: Multiple Transcription Factors
```r
tfs <- c("OCT4", "SOX2", "NANOG", "KLF4")
results <- lapply(tfs, function(g) scTenifoldKnk(counts, gKO = g))
names(results) <- tfs
```

### Pattern 3: Compare with Experimental Data
```r
# Run prediction
predicted <- scTenifoldKnk(counts, gKO = "TREM2")

# Load real KO data
real_ko <- read.csv("trem2_ko_de.csv")

# Compare
cor(predicted$diffRegulation$Z, real_ko$logFC, method = "spearman")
```

### Pattern 4: Comprehensive Report
```r
result <- run_complete_knockdown_analysis(
  counts, gKO = "POU5F1",
  output_dir = "results",
  run_enrichment = TRUE
)
```

## Module Structure

```
scripts/r/
├── core_analysis.R       # run_knockdown_analysis(), run_multiple_knockdowns(),
│                         # run_complete_knockdown_analysis()
├── enrichment.R          # run_enrichment_analysis(), plot_enrichment()
├── visualization.R       # plot_volcano(), plot_ko_network(), plot_top_genes(),
│                         # plot_comparison_heatmap()
└── utils.R               # validate_knk_data(), summarize_knockdown_results(),
                          # get_significant_genes(), export_knockdown_results(),
                          # create_knockdown_report()

examples/
├── minimal_example.R     # Basic single gene knockdown
└── advanced_example.R    # Multiple genes, enrichment, comparison

tests/
└── test_sctenifoldknk.R  # Unit tests
```

## Interpretation Guidelines

### Understanding Results

**Distance metric:**
- Euclidean distance in aligned manifold space
- Larger distance = greater regulatory change
- Box-Cox transformed to Z-scores for normality

**Fold Change (FC):**
- Computed as (distance²) / mean(other distances²)
- Higher FC = more significant change
- Chi-square p-values test significance

**Significance thresholds:**
- p.adj < 0.05: Significantly affected genes
- Top 1% by distance: Most strongly affected
- Compare Z-scores across different knockdowns

### Network Interpretation

**WT vs KO networks:**
- WT: Original gene regulatory network
- KO: Network with target gene edges removed
- Edge weights represent regulatory strength
- Red edges = activation, Blue = repression

**Manifold alignment:**
- Non-linear alignment of WT and KO networks
- Preserves local structure while allowing comparison
- d=2 dimensions typically sufficient

## Related Skills

- [bio-single-cell-perturbation-pertpy](../bio-single-cell-perturbation-pertpy/SKILL.md) - Python toolkit for perturbation analysis
- [bio-single-cell-regulatory-pyscenic](../bio-single-cell-regulatory-pyscenic/SKILL.md) - Gene regulatory network inference
- [bio-single-cell-trajectory-monocle3-r](../bio-single-cell-trajectory-monocle3-r/SKILL.md) - Trajectory analysis

## References

1. Osorio et al. (2020). Systematic characterization of gene knockdown perturbations in single-cell data. *bioRxiv*. https://doi.org/10.1101/2020.09.18.301879
2. scTenifoldKnk GitHub: https://github.com/cailab-tamu/scTenifoldKnk
3. scTenifoldKnk Python version: https://github.com/qwerty239qwe/scTenifoldpy
4. scGEAToolbox (MATLAB): https://github.com/jamesjcai/scGEAToolbox
