# NicheNet Skill Usage Guide

Complete guide for using the bio-single-cell-communication-nichenet-r skill.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Database Management](#database-management)
3. [Core Principle](#core-principle)
4. [Usage Scenarios](#usage-scenarios)
5. [Basic Analysis](#basic-analysis)
6. [Seurat Integration](#seurat-integration)
7. [Differential Analysis](#differential-analysis)
8. [Batch Analysis](#batch-analysis)
9. [Visualization](#visualization)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### When to Use NicheNet

Use NicheNet when you want to answer: **"Which ligands from sender cells regulate gene expression in receiver cells?"**

- ✅ Condition comparisons (treatment vs control)
- ✅ Cell state changes (exhausted vs naive T cells)
- ✅ Identifying active signaling pathways
- ❌ Simple ligand-receptor pairing (use CellChat instead)

### Installation

```r
# Install nichenetr (required dependency)
devtools::install_github("saeyslab/nichenetr")

# Install optional dependencies
BiocManager::install("ComplexHeatmap")
```

### Loading Scripts

```r
# Source all skill scripts
source("scripts/r/nichenet_database.R")
source("scripts/r/nichenet_analysis.R")
source("scripts/r/nichenet_seurat.R")
source("scripts/r/nichenet_visualization.R")
source("scripts/r/nichenet_utils.R")
```

### First Run

On first use, the system will automatically download NicheNet databases (~1.5GB):

```r
# Check status
check_nichenet_database("human")

# Or download explicitly
download_nichenet_database("human")
```

### Quick Example

```r
# Complete workflow in 3 steps
source("scripts/r/nichenet_seurat.R")

# 1. Check database
download_nichenet_database("human")

# 2. Run analysis
results <- run_nichenet_aggregate(
  seurat_obj,
  sender = "Macrophage",
  receiver = "T_cell",
  condition_colname = "stimulation",
  condition_oi = "stimulated",
  condition_reference = "control"
)

# 3. View top ligands
print(results$top_ligands[1:10])
```

---

## Database Management

### Automatic Caching

Databases are cached in `~/.nichenetr/` to avoid repeated downloads:

```r
# List cached databases
list_nichenet_databases()

# Output:
#   organism                 file cached size_mb            modified
# 1    human ligand_target_matrix.rds   TRUE  520.5 2026-04-01 10:30:00
# 2    human          lr_network.rds   TRUE   12.3 2026-04-01 10:30:00
# ...
```

### Loading Individual Components

```r
# Load specific databases
ligand_target_matrix <- get_ligand_target_matrix("human")
lr_network <- get_lr_network("human")
weighted_networks <- get_weighted_networks("human")
sig_network <- get_sig_network("human")
gr_network <- get_gr_network("human")
```

### Clearing Cache

```r
# Clear all cached databases
clear_database_cache(confirm = TRUE)
```

---

## Core Principle

NicheNet answers a specific question: **"Which ligands from sender cells are most likely causing the observed gene expression changes in receiver cells?"**

Unlike simple ligand-receptor pairing methods, NicheNet:

1. **Integrates prior knowledge**: Uses curated signaling and gene regulatory networks
2. **Predicts functional regulation**: Calculates how well a ligand explains target gene expression
3. **Ranks by activity**: Provides quantitative scores (Pearson correlation) for each ligand

### Analysis Workflow

```
Sender Cells ──express──► Ligands ──bind──► Receptors on Receiver Cells
                                                    │
                                                    ▼
                                    Activate signaling pathways
                                                    │
                                                    ▼
                                    Regulate target gene expression
                                                    │
                                                    ▼
                              NicheNet scores: How well does each ligand
                              explain the observed target gene changes?
```

### Output Interpretation

| Metric | Meaning | Interpretation |
|--------|---------|----------------|
| `pearson` | Activity score | Higher = ligand more likely regulates targets |
| `test_ligand` | Candidate ligand | Can be validated experimentally |
| `ligand_targets` | Predicted target genes | Use for pathway enrichment |
| `lr_network` | Ligand-receptor pairs | Cross-validate with CellChat |

---

## Usage Scenarios

Choose the right analysis mode based on your biological question:

| Scenario | Method | Core Question | Required Input |
|----------|--------|---------------|----------------|
| **Condition Comparison** | `run_nichenet_aggregate()` | What ligands drive expression changes after stimulation? | Seurat + condition column |
| **Cell State Comparison** | `run_nichenet_cluster_de()` | What ligands regulate exhausted vs naive T cells? | Seurat + cell type labels |
| **Basic Cell Pair** | `run_nichenet_celltype_pair()` | Do known pathways explain marker expression? | Seurat + gene list |
| **Batch Analysis** | `run_nichenet_batch()` | Which communications occur across all cell types? | Seurat + pairs table |
| **Manual Analysis** | `predict_ligand_activities()` | Analyze custom gene sets without Seurat | Gene lists manually |

### Scenario 1: Condition Comparison (Aggregate Mode) ⭐ Most Common

**When to use**: Compare treatment vs control, disease vs normal, before/after stimulation

**Biological question**: *"After LPS stimulation, which macrophage-derived ligands activate T cells?"*

```r
results <- run_nichenet_aggregate(
  seurat_obj = seurat_obj,
  sender = "Macrophage",              # Sending cell type
  receiver = "T_cell",                 # Receiving cell type
  condition_colname = "stimulation",   # Column with conditions
  condition_oi = "LPS_stimulated",     # Condition of interest
  condition_reference = "control",     # Reference condition
  organism = "human"
)
```

**What it does internally**:
1. Identifies differentially expressed genes in receiver (stim vs control)
2. Gets expressed genes in sender and receiver
3. Filters to ligands with expressed receptors
4. Runs NicheNet to rank ligands by their ability to explain DE genes

**Key outputs**:
- `results$ligand_activities`: Ligands ranked by activity score
- `results$top_ligands`: Top 20 predicted ligands
- `results$ligand_targets`: Target genes for each top ligand

---

### Scenario 2: Cell State Comparison (Cluster DE Mode)

**When to use**: Compare two states of the same cell type (e.g., exhausted vs naive)

**Biological question**: *"What ligands drive T cell exhaustion in the tumor microenvironment?"*

```r
results <- run_nichenet_cluster_de(
  seurat_obj,
  receiver_affected = "T_cell_exhausted",  # Affected state
  receiver_reference = "T_cell_naive",      # Reference state
  sender = "Macrophage"                     # Potential regulator
)
```

**vs Aggregate Mode**: Uses cell type labels for comparison instead of condition column

---

### Scenario 3: Basic Cell Type Pair Analysis

**When to use**: You have a specific hypothesis about ligands and want to test their target predictions

**Biological question**: *"Does TGFB1 signaling explain the regulatory T cell signature we observe?"*

```r
# Define genes of interest (e.g., Treg markers)
treg_markers <- c("FOXP3", "IL2RA", "CTLA4", "TGFB1", "IL10")

results <- run_nichenet_celltype_pair(
  seurat_obj,
  sender_celltype = "Dendritic_cell",
  receiver_celltype = "T_cell",
  genes_of_interest = treg_markers
)
```

**Characteristics**:
- No condition comparison
- Directly tests if known ligands explain your gene set
- Good for validating specific hypotheses

---

### Scenario 4: Batch Analysis

**When to use**: Systematically analyze multiple sender-receiver pairs

**Biological question**: *"Which cell types communicate in our tumor microenvironment?"*

```r
# Define all pairs to test
pairs <- data.frame(
  sender = c("Macrophage", "Macrophage", "DC", "Fibroblast", "B_cell"),
  receiver = c("T_cell", "B_cell", "T_cell", "T_cell", "T_cell")
)

# Run all analyses
results <- run_nichenet_batch(
  seurat_obj,
  pairs,
  condition_col = "treatment",
  condition_oi = "anti_PD1",
  condition_ref = "vehicle"
)

# Access results
macro_t_results <- results$Macrophage_to_T_cell
dc_t_results <- results$DC_to_T_cell
```

**Advantages**:
- Automates multiple analyses
- Consistent parameters across comparisons
- Easy to identify dominant communication axes

---

### Scenario 5: Manual Analysis (No Seurat)

**When to use**: External data or when you already have curated gene lists

**Biological question**: *"Based on published literature, which cytokines could explain this response signature?"*

```r
# Load database
ligand_target_matrix <- get_ligand_target_matrix("human")

# Manually define input
genes_of_interest <- c("IL2RA", "IFNG", "TNF", "GZMB", "PRF1", "IL2")
background_genes <- c(genes_of_interest, "ACTB", "GAPDH", "CD3D", "CD3E")
candidate_ligands <- c("IL2", "IL12", "IL15", "TGFB1", "IFNG")

# Run analysis
results <- predict_ligand_activities(
  geneset = genes_of_interest,
  background_expressed_genes = background_genes,
  ligand_target_matrix = ligand_target_matrix,
  potential_ligands = candidate_ligands
)
```

**Use cases**:
- Analyze bulk RNA-seq data
- Test literature-derived signatures
- Validate experimental results

---

## Basic Analysis

### Manual Gene List Analysis

When you already know your genes of interest:

```r
# Define your genes
genes_of_interest <- c("IL2RA", "IFNG", "TNF", "GZMB", "PRF1")

# Get potential ligands from sender
ligands <- c("IL2", "IL7", "IL15", "TGFB1", "TNF")

# Run prediction
results <- predict_ligand_activities(
  geneset = genes_of_interest,
  background_expressed_genes = expressed_in_receiver,
  ligand_target_matrix = ligand_target_matrix,
  potential_ligands = ligands
)

# View results
head(results, 10)
```

### Getting Top Targets

```r
# Get top 100 target genes for a ligand
targets <- get_top_targets("TGFB1", ligand_target_matrix, n = 100)

# Get with scores
targets_with_scores <- get_top_targets(
  "TGFB1",
  ligand_target_matrix,
  n = 100,
  return_scores = TRUE
)
```

---

## Seurat Integration

### Prerequisites

Your Seurat object should have:
- Cell type annotations in metadata
- Optional: condition labels for differential analysis

```r
# Check required columns
head(seurat_obj@meta.data)
# Should contain: cell_type, condition (optional)
```

### Aggregate Mode (Recommended)

Best for comparing conditions (e.g., stimulated vs control):

```r
results <- run_nichenet_aggregate(
  seurat_obj = seurat_obj,
  sender = "Macrophage",              # Can be multiple: c("Macrophage", "DC")
  receiver = "T_cell",
  condition_colname = "stimulation",
  condition_oi = "stimulated",
  condition_reference = "control"
)
```

**What it does:**
1. Finds DE genes in receiver (stim vs control)
2. Gets expressed genes in sender and receiver
3. Filters to ligands with expressed receptors
4. Runs NicheNet prediction

### Cluster DE Mode

For comparing two receiver cell states:

```r
results <- run_nichenet_cluster_de(
  seurat_obj,
  receiver_affected = "T_cell_exhausted",
  receiver_reference = "T_cell_naive",
  sender = "Macrophage"
)
```

### Cell Type Pair Mode

For basic analysis with known marker genes:

```r
results <- run_nichenet_celltype_pair(
  seurat_obj,
  sender_celltype = "Macrophage",
  receiver_celltype = "T_cell",
  genes_of_interest = c("IL2", "IFNG", "TNF")  # Your marker genes
)
```

---

## Differential Analysis

### Comparing Two Conditions

To find condition-specific ligands, run analysis in both directions:

```r
# Stimulated condition
results_stim <- run_nichenet_aggregate(
  seurat_obj,
  sender = "Macrophage",
  receiver = "T_cell",
  condition_colname = "condition",
  condition_oi = "stimulated",
  condition_reference = "control"
)

# Control condition (reverse comparison)
results_ctrl <- run_nichenet_aggregate(
  seurat_obj,
  sender = "Macrophage",
  receiver = "T_cell",
  condition_colname = "condition",
  condition_oi = "control",              # Now control is "oi"
  condition_reference = "stimulated"     # And stimulated is reference
)

# Compare rankings
stim_ranking <- results_stim$ligand_activities$test_ligand
ctrl_ranking <- results_ctrl$ligand_activities$test_ligand

# Find ligands specific to stimulated
stim_specific <- setdiff(head(stim_ranking, 20), head(ctrl_ranking, 30))
```

### Visualizing Differential Results

```r
# Create scatter plot of rankings
compare_df <- data.frame(
  ligand = unique(c(stim_ranking[1:30], ctrl_ranking[1:30]))
)
compare_df$stim_rank <- match(compare_df$ligand, stim_ranking)
compare_df$ctrl_rank <- match(compare_df$ligand, ctrl_ranking)

ggplot(compare_df, aes(x = stim_rank, y = ctrl_rank)) +
  geom_point(aes(color = stim_rank - ctrl_rank), size = 3) +
  geom_abline(intercept = 0, slope = 1, linetype = "dashed")
```

---

## Batch Analysis

### Running Multiple Pairs

```r
# Define pairs to analyze
pairs <- data.frame(
  sender = c("Macrophage", "Macrophage", "DC", "B_cell"),
  receiver = c("T_cell", "B_cell", "T_cell", "T_cell")
)

# Run all analyses
results <- run_nichenet_batch(
  seurat_obj,
  pairs,
  condition_col = "stimulation",
  condition_oi = "stimulated",
  condition_ref = "control"
)

# Access individual results
macro_t_results <- results$Macrophage_to_T_cell
```

### Processing Batch Results

```r
# Combine top ligands from all analyses
all_top_ligands <- lapply(results, function(x) head(x$top_ligands, 5))

# Find common ligands across multiple interactions
Reduce(intersect, all_top_ligands)
```

---

## Visualization

### Ligand Activity Dot Plot

```r
# Basic plot
plot_ligand_activity_dotplot(results$ligand_activities)

# Customized
ggsave("ligand_dotplot.png",
  plot_ligand_activity_dotplot(
    results$ligand_activities,
    top_n = 15,
    title = "Macrophage to T Cell Communication"
  ),
  width = 8, height = 6
)
```

### Ligand-Target Heatmap

```r
# Save heatmap
png("ligand_target_heatmap.png", width = 10, height = 8, units = "in", res = 150)
plot_ligand_target_heatmap(
  ligand_target_matrix,
  ligands = results$top_ligands[1:5],
  n_targets = 50
)
dev.off()
```

### Ligand-Receptor Heatmap

```r
png("lr_heatmap.png", width = 8, height = 10, units = "in", res = 150)
plot_ligand_receptor_heatmap(
  results$lr_network,
  seurat_obj,
  sender_celltype = "Macrophage",
  receiver_celltype = "T_cell"
)
dev.off()
```

### Exporting Results

```r
# Export all results to CSV
export_nichenet_results(results, "./output", prefix = "my_analysis")

# Files created:
# - my_analysis_ligand_activities.csv
# - my_analysis_ligand_targets.csv
# - my_analysis_lr_network.csv
```

---

## Troubleshooting

### Database Download Issues

```r
# If automatic download fails, try manual
download_nichenet_database("human", force = TRUE)

# Check your internet connection
# Try different mirror if Zenodo is slow
```

### Gene Symbol Mismatches

```r
# Check if your gene symbols match expected format
check_gene_format(your_genes, "human")

# Convert between human and mouse
human_genes <- convert_mouse_to_human(mouse_genes, lr_network)
mouse_genes <- convert_human_to_mouse(human_genes, lr_network)
```

### Memory Issues

The ligand-target matrix is large (~500MB):

```r
# Check memory before loading
ligand_target_matrix <- get_ligand_target_matrix("human")

# Process in chunks if needed
top_ligands_only <- ligand_target_matrix[, results$top_ligands[1:10]]
```

### Low Prediction Scores

If all Pearson correlations are low (<0.05):

1. **Check gene overlap:**
```r
overlap <- intersect(genes_of_interest, rownames(ligand_target_matrix))
message(sprintf("%d/%d genes in matrix", length(overlap), length(genes_of_interest)))
```

2. **Check ligand expression:**
```r
potential_ligands <- intersect(ligands, colnames(ligand_target_matrix))
message(sprintf("%d ligands available", length(potential_ligands)))
```

3. **Use more specific gene sets:**
- Focus on pathway-specific markers
- Remove housekeeping genes from background

### No Receptors Found

If `lr_network` is empty after filtering:

```r
# Check receptor expression
receptors <- unique(lr_network$to)
expressed_receptors <- intersect(receptors, receiver_genes)
message(sprintf("%d receptors expressed", length(expressed_receptors)))
```

---

## Output Interpretation Guide

### Understanding Ligand Activity Scores

```r
# View top results
head(results$ligand_activities)
#   test_ligand    pearson ligand target
# 1        IL2  0.2345678    IL2     NA
# 2       IL15  0.1987654   IL15     NA
# 3      TGFB1  0.1765432  TGFB1     NA
```

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| > 0.15 | Strong predictor | High confidence candidate |
| 0.08 - 0.15 | Moderate predictor | Validate with additional evidence |
| 0.05 - 0.08 | Weak predictor | Consider with caution |
| < 0.05 | Poor predictor | Likely not functional |

### Accessing Target Genes

```r
# Get targets for top ligand
top_ligand <- results$top_ligands[1]
targets <- results$ligand_targets[[top_ligand]]

# Check overlap with your genes of interest
overlap <- intersect(targets, genes_of_interest)
message(sprintf("%d/%d genes of interest are predicted targets of %s",
               length(overlap), length(genes_of_interest), top_ligand))
```

### Cross-Validation with CellChat

NicheNet and CellChat are complementary:

| Aspect | NicheNet | CellChat |
|--------|----------|----------|
| **Output** | Ligand activity ranking | Ligand-receptor pairs |
| **Strength** | Predicts functional regulation | Identifies expressed LR pairs |
| **Use together** | "Which ligands are active?" | "Which receptors are present?" |

**Recommended workflow**:
1. Run CellChat to identify potential LR pairs
2. Run NicheNet to identify which ligands actually regulate target genes
3. Compare: High NicheNet score + Expressed receptor = High confidence interaction

---

## Best Practices

1. **Sender Selection**
   - Use specific cell types rather than "all" when possible
   - Ensure >50 cells per sender type
   - Consider using "all" only for exploratory analysis

2. **Receiver Definition**
   - Focus on one receiver type at a time for clear interpretation
   - Use cluster DE mode for comparing receiver states
   - Ensure sufficient cells (>50) in each condition/cluster

3. **Gene Sets**
   - Use biologically meaningful gene sets (50-500 genes)
   - Remove housekeeping genes from background
   - Focus on pathway-specific markers rather than whole transcriptome

4. **Validation**
   - Top predictions should be validated experimentally (e.g., receptor blocking)
   - Compare with known literature
   - Use multiple visualization methods
   - Cross-reference with CellChat results

5. **Reproducibility**
   - Save database version used
   - Document all parameters
   - Export results for sharing
   - Record random seeds if applicable

6. **Common Pitfalls**
   - Don't interpret low scores as "no communication"
   - Ensure genes of interest are expressed in receiver
   - Check that ligands are expressed in sender
   - Verify organism matches (human vs mouse)
