# CellChat Single-Cell Usage Guide

## Overview

CellChat is an R package for inference, analysis, and visualization of cell-cell communication from single-cell RNA-seq data using ligand-receptor (L-R) interactions. It provides a comprehensive framework to identify and interpret intercellular communication networks.

## Key Features

- **Comprehensive Database**: ~3,300 validated L-R interactions (CellChatDB v2)
- **Multiple Signaling Types**: Secreted, ECM-Receptor, Cell-Cell Contact, Non-protein
- **Systems Analysis**: Network centrality, pattern recognition, manifold learning
- **Multi-condition Comparison**: Identify altered signaling across conditions

## When to Use CellChat

- Infer cell-cell communication from scRNA-seq data
- Identify active signaling pathways between cell types
- Compare communication networks across conditions
- Explore global communication patterns and coordination

## Step-by-Step

### 1. Prepare Data

```r
library(Seurat)
library(CellChat)

# Load Seurat object
seurat_obj <- readRDS("annotated_data.rds")

# Ensure cell type annotations exist
table(seurat_obj$cell_type)
```

### 2. Run CellChat Analysis

```r
source("scripts/r/cellchat_analysis.R")

# Run complete pipeline
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  sample_name = "Sample1",
  
  # Database options
  db_use = "CellChatDB.human",  # or "CellChatDB.mouse"
  signaling_type = "Secreted Signaling",  # or "all", "Cell-Cell Contact", "ECM-Receptor"
  
  # Analysis parameters
  type = "triMean",  # Average method: "triMean", "truncatedMean"
  min_cells = 10,    # Min cells per group
  
  # Parallel processing
  n_workers = 4
)
```

### 3. Visualize Results

#### Aggregated Network

```r
# Circle plot showing all interactions
plot_cellchat_circle(cellchat)

# Heatmap
netVisual_heatmap(cellchat, measure = "count")
```

#### Specific Pathways

```r
# Visualize CXCL signaling pathway
plot_cellchat_pathway(
  cellchat,
  signaling = "CXCL",
  layout = "circle"  # or "hierarchy", "chord"
)

# Contribution of each L-R pair
netAnalysis_contribution(cellchat, signaling = "CXCL")
```

#### Bubble Plot

```r
# Show all significant L-R pairs
plot_cellchat_bubble(
  cellchat,
  sources.use = c("T_cell", "B_cell"),
  targets.use = c("Tumor", "Macrophage")
)

# Show specific signaling pathways
plot_cellchat_bubble(
  cellchat,
  signaling = c("CXCL", "CCL", "TNF")
)
```

### 4. Systems Analysis

#### Network Centrality

```r
# Compute centrality scores
cellchat <- compute_cellchat_centrality(cellchat)

# Heatmap of signaling roles
netAnalysis_signalingRole_heatmap(cellchat, pattern = "outgoing")
netAnalysis_signalingRole_heatmap(cellchat, pattern = "incoming")

# Scatter plot
netAnalysis_signalingRole_scatter(cellchat)
```

#### Communication Patterns

```r
# Identify outgoing patterns (sender coordination)
cellchat <- identify_cellchat_patterns(
  cellchat,
  pattern = "outgoing",
  k = 5  # Number of patterns
)

# River plot
netAnalysis_river(cellchat, pattern = "outgoing")

# Dot plot
netAnalysis_dot(cellchat, pattern = "outgoing")
```

#### Similarity Analysis

```r
# Functional similarity
cellchat <- computeNetSimilarity(cellchat, type = "functional")
cellchat <- netEmbedding(cellchat, type = "functional")
cellchat <- netClustering(cellchat, type = "functional")
netVisual_embedding(cellchat, type = "functional")

# Structural similarity
cellchat <- computeNetSimilarity(cellchat, type = "structural")
cellchat <- netEmbedding(cellchat, type = "structural")
netVisual_embedding(cellchat, type = "structural")
```

### 5. Multi-Condition Comparison

```r
# Analyze each condition separately
control <- run_cellchat(seurat_control, group_by = "cell_type")
treatment <- run_cellchat(seurat_treatment, group_by = "cell_type")

# Compare conditions
comparison <- compare_cellchat_conditions(
  object.list = list(Control = control, Treatment = treatment),
  add.names = c("Control", "Treatment")
)

# Visualize differences
plot_cellchat_comparison(comparison)

# Differential interaction heatmap
netVisual_heatmap(comparison)

# Circle plot of differential network
netVisual_diffInteraction(comparison, weight.scale = TRUE)
```

### 6. Extract and Export Results

```r
# Extract all communications
df_net <- extract_cellchat_communications(cellchat)
head(df_net)

# Extract specific signaling
df_cxcl <- subsetCommunication(cellchat, signaling = "CXCL")

# Export to CSV
write.csv(df_net, "cellchat_lr_pairs.csv", row.names = FALSE)

# Save CellChat object
saveRDS(cellchat, "cellchat_analysis.rds")
```

## Specify Signaling Type

Use `signaling_type` to restrict the ligand-receptor database before inference. You can pass a single string or a character vector to select multiple categories:

| Option | Meaning | When to Use |
|--------|---------|-------------|
| `"Secreted Signaling"` | Cytokines, chemokines, growth factors | General analysis (default) |
| `"Cell-Cell Contact"` | Membrane-bound ligands and receptors | Juxtacrine signaling |
| `"ECM-Receptor"` | Extracellular matrix – receptor interactions | Studying tissue microenvironment |
| `"all"` | All categories combined | Exploratory analysis |

```r
# Single category
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  signaling_type = "Cell-Cell Contact"
)

# Multiple categories
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  signaling_type = c("Secreted Signaling", "ECM-Receptor")
)
```

## Subset to Specific Cell Types

Limit the analysis to selected cell types with the `cell_types` parameter. This reduces computation and improves statistical power:

```r
cellchat <- run_cellchat(
  seurat_obj = seurat_obj,
  group_by = "cell_type",
  cell_types = c("T_cell", "Macrophage", "Tumor")
)
```

After analysis, filter by direction with `subsetCommunication()`:

```r
df <- subsetCommunication(
  cellchat,
  sources.use = c("Macrophage"),
  targets.use = c("T_cell")
)
```

## Parameters

### run_cellchat()

| Parameter | Description | Default |
|-----------|-------------|---------|
| `seurat_obj` | Seurat object | Required |
| `group_by` | Cell type column | "cell_type" |
| `sample_name` | Sample identifier | "Sample" |
| `db_use` | Database | "CellChatDB.human" |
| `signaling_type` | Signaling subset(s) to analyze (char or vector) | "Secreted Signaling" |
| `type` | Average method | "triMean" |
| `trim` | Trim value for truncatedMean | NULL |
| `population.size` | Consider cell proportion | FALSE |
| `cell_types` | Cell types to include (NULL = all) | NULL |
| `min_cells` | Min cells per group | 10 |
| `n_workers` | Number of parallel workers | 4 |
| `verbose` | Print progress messages | TRUE |

### Visualization Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `layout` | Plot layout | "circle" |
| `vertex.receiver` | Target cells for hierarchy | NULL |
| `sources.use` | Source cell groups | NULL |
| `targets.use` | Target cell groups | NULL |
| `signaling` | Signaling pathways | NULL |

## AI Agent Test Cases

### Basic Usage

> "Run CellChat on my annotated scRNA-seq data"

```r
cellchat <- run_cellchat(seurat_obj, group_by = "cell_type")
```

> "Identify cell-cell communication in my tumor data"

```r
cellchat <- run_cellchat(
  seurat_tumor,
  group_by = "cell_type",
  signaling_type = "Secreted Signaling"
)
```

### Visualization

> "Show me all cell-cell interactions as a circle plot"

```r
plot_cellchat_circle(cellchat)
```

> "Visualize CXCL signaling pathway"

```r
plot_cellchat_pathway(cellchat, signaling = "CXCL", layout = "circle")
```

> "Show bubble plot of T cell to tumor interactions"

```r
plot_cellchat_bubble(
  cellchat,
  sources.use = c("CD4_T", "CD8_T"),
  targets.use = "Tumor"
)
```

### Systems Analysis

> "Find the dominant senders and receivers"

```r
cellchat <- compute_cellchat_centrality(cellchat)
netAnalysis_signalingRole_scatter(cellchat)
```

> "Identify global communication patterns"

```r
cellchat <- identify_cellchat_patterns(cellchat, pattern = "outgoing", k = 5)
netAnalysis_river(cellchat, pattern = "outgoing")
```

### Multi-Condition Comparison

> "Compare cell communication between control and treatment"

```r
comparison <- compare_cellchat_conditions(
  list(Control = control, Treatment = treatment)
)
plot_cellchat_comparison(comparison)
```

> "Show differential interactions between conditions"

```r
netVisual_diffInteraction(comparison, weight.scale = TRUE)
```

### Database Customization

> "Use only cell-cell contact signaling"

```r
cellchat <- run_cellchat(
  seurat_obj,
  group_by = "cell_type",
  signaling_type = "Cell-Cell Contact"
)
```

> "Analyze multiple signaling categories"

```r
cellchat <- run_cellchat(
  seurat_obj,
  group_by = "cell_type",
  signaling_type = c("Secreted Signaling", "ECM-Receptor")
)
```

> "Use mouse database"

```r
cellchat <- run_cellchat(
  seurat_mouse,
  group_by = "cell_type",
  db_use = "CellChatDB.mouse"
)
```

## Best Practices

1. **Cell Type Quality**: Use well-annotated cell types for meaningful results
2. **Database Selection**: Choose species-appropriate database (human/mouse)
3. **Signaling Type**: Start with "Secreted Signaling" for general analysis
4. **Min Cells**: Increase threshold if too many weak interactions
5. **Comparison**: Ensure similar cell type composition when comparing conditions

## Troubleshooting

### No Communication Detected
- Check cell type annotations are correct
- Reduce `min_cells` threshold
- Try `type = "truncatedMean"` with `trim = 0.1`
- Check database species matches data

### Too Many Communications
- Increase `min_cells` filter
- Use `type = "triMean"` for stricter filtering
- Focus on specific signaling pathways

### Memory Issues
- Reduce number of workers: `future::plan("multisession", workers = 1)`
- Process in chunks for large datasets

## References

1. Jin et al. (2024). CellChat for systematic analysis of cell-cell communication from single-cell transcriptomics. Nature Protocols.
2. Jin et al. (2021). Inference and analysis of cell-cell communication using CellChat. Nature Communications.
3. CellChat documentation: https://github.com/jinworks/CellChat
