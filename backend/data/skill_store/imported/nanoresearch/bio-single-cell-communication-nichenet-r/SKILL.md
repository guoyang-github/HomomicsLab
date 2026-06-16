---
name: bio-single-cell-communication-nichenet-r
description: Predict ligand-target relationships and cell-cell communication using NicheNet with automatic database download. Use when investigating how ligands from sender cells regulate target genes in receiver cells.
tool_type: r
primary_tool: nichenetr
language: r
dependencies:
  - nichenetr
  - Seurat >= 4.3.0
  - dplyr
  - ggplot2
  - ComplexHeatmap
  - tidyr
system_requirements:
  - R >= 4.2.0
  - ~2GB disk space for databases
keywords: ["single-cell", "nichenet", "ligand-target", "communication", "regulation", "cell-cell", "R"]
---

## Version Compatibility

- **R**: 4.2.0+
- **nichenetr**: 1.1.0+
- **Seurat**: 4.3+

## Installation

```r
# Install nichenetr
devtools::install_github("saeyslab/nichenetr")

# Install this skill's scripts (no additional packages needed)
```

## Quick Start

```r
source("scripts/r/nichenet_database.R")
source("scripts/r/nichenet_analysis.R")
source("scripts/r/nichenet_seurat.R")
source("scripts/r/nichenet_visualization.R")

# 1. Download NicheNet database (one-time, auto-cached)
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

# 3. Visualize
plot_ligand_activity_dotplot(results$ligand_activities)
```

---

## Features

### Automatic Database Management

| Feature | Description |
|---------|-------------|
| Auto-download | Downloads from Zenodo on first use |
| Local cache | Cached in `~/.nichenetr/` for reuse |
| Human & Mouse | Supports both organisms |
| Version check | Validates database integrity |

### Analysis Modes

| Mode | Use Case | Function |
|------|----------|----------|
| **Aggregate** | Condition comparison (stim vs control) | `run_nichenet_aggregate()` |
| **Cluster DE** | Compare receiver clusters | `run_nichenet_cluster_de()` |
| **Cell Type Pair** | Basic sender→receiver analysis | `run_nichenet_celltype_pair()` |
| **Cell Specific** | Custom cell barcodes | `run_nichenet_celltype_specific()` |
| **Batch** | Multiple pairs at once | `run_nichenet_batch()` |

---

## Detailed Usage

### 1. Database Management

```r
# Check database status
check_nichenet_database("human")

# List cached databases
list_nichenet_databases()

# Download manually (optional - auto-downloaded on first use)
download_nichenet_database("human")
download_nichenet_database("mouse")

# Clear cache if needed
clear_database_cache()
```

### 2. Load Databases

```r
# Load individual components
ligand_target_matrix <- get_ligand_target_matrix("human")
lr_network <- get_lr_network("human")
weighted_networks <- get_weighted_networks("human")
```

### 3. Condition Comparison (Aggregate Mode)

Analyze how ligands from sender cells change gene expression in receiver cells across conditions.

```r
results <- run_nichenet_aggregate(
  seurat_obj = seurat_obj,
  sender = "Macrophage",              # Sender cell type(s)
  receiver = "T_cell",                 # Receiver cell type
  condition_colname = "stimulation",   # Condition column
  condition_oi = "stimulated",         # Condition of interest
  condition_reference = "control",     # Reference condition
  organism = "human"                   # "human" or "mouse"
)

# Results include:
# - $ligand_activities: Activity scores for each ligand
# - $top_ligands: Top 20 predicted ligands
# - $ligand_targets: Target genes for top ligands
# - $lr_network: Ligand-receptor interactions
```

### 4. Cluster Comparison (Cluster DE Mode)

Compare two receiver cell states to find regulatory ligands.

```r
results <- run_nichenet_cluster_de(
  seurat_obj,
  receiver_affected = "T_cell_exhausted",
  receiver_reference = "T_cell_naive",
  sender = "Macrophage"
)
```

### 5. Basic Cell Type Pair Analysis

```r
# Define genes of interest manually
genes_of_interest <- c("IL2", "IFNG", "TNF", "GZMB")

results <- run_nichenet_celltype_pair(
  seurat_obj,
  sender_celltype = "Macrophage",
  receiver_celltype = "T_cell",
  genes_of_interest = genes_of_interest
)
```

### 6. Batch Analysis

```r
# Define multiple sender-receiver pairs
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

---

## Visualization

### Ligand Activity Dot Plot

```r
plot_ligand_activity_dotplot(
  results$ligand_activities,
  top_n = 20,
  title = "Top Predicted Ligands"
)
```

### Ligand-Target Heatmap

```r
plot_ligand_target_heatmap(
  ligand_target_matrix,
  ligands = results$top_ligands[1:10],
  n_targets = 50
)
```

### Ligand-Receptor Expression Heatmap

```r
plot_ligand_receptor_heatmap(
  results$lr_network,
  seurat_obj,
  sender_celltype = "Macrophage",
  receiver_celltype = "T_cell"
)
```

### Top Ligand Bar Plot

```r
plot_top_ligand_barplot(results$ligand_activities, top_n = 15)
```

### Target Gene Expression

```r
plot_target_expression(
  seurat_obj,
  targets = c("IL2", "IFNG"),
  receiver_celltype = "T_cell",
  group_by = "stimulation"
)
```

---

## Utility Functions

### Gene Symbol Conversion

```r
# Convert mouse to human
human_genes <- convert_mouse_to_human(c("Il2", "Ifng", "Tnf"))

# Convert human to mouse
mouse_genes <- convert_human_to_mouse(c("IL2", "IFNG", "TNF"))
```

### Get Expressed/DE Genes

```r
# Get expressed genes
expressed <- get_expressed_genes(seurat_obj, "T_cell", pct = 0.10)

# Get DE genes
de_genes <- get_de_genes(
  seurat_obj,
  condition_col = "stimulation",
  condition_oi = "stimulated",
  condition_reference = "control",
  cell_type_col = "cell_type",
  cell_type = "T_cell"
)
```

### Export Results

```r
export_nichenet_results(results, "./nichenet_output", prefix = "my_analysis")
# Creates:
# - my_analysis_ligand_activities.csv
# - my_analysis_ligand_targets.csv
# - my_analysis_lr_network.csv
```

---

## Parameters

### run_nichenet_aggregate()

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sender` | char/vector | required | Sender cell type(s) or "all" |
| `receiver` | char | required | Receiver cell type |
| `condition_colname` | char | required | Condition column name |
| `condition_oi` | char | required | Condition of interest |
| `condition_reference` | char | required | Reference condition |
| `organism` | char | "human" | "human" or "mouse" |
| `ligand_target_matrix` | matrix | NULL | Auto-loaded if NULL |
| `lr_network` | df | NULL | Auto-loaded if NULL |

### Database Functions

| Function | Purpose |
|----------|---------|
| `download_nichenet_database(organism)` | Download and cache database |
| `get_ligand_target_matrix(organism)` | Load ligand-target matrix |
| `get_lr_network(organism)` | Load ligand-receptor network |
| `get_weighted_networks(organism)` | Load weighted networks |
| `check_nichenet_database(organism)` | Verify database status |
| `list_nichenet_databases()` | List cached files |
| `clear_database_cache()` | Remove all caches |

---

## Output Structure

NicheNet results list contains:

```r
results <- list(
  ligand_activities = data.frame(    # Activity scores
    test_ligand = character(),
    pearson = numeric(),             # Correlation score
    ligand = character(),
    target = character()
  ),
  top_ligands = character(),          # Top 20 ligands
  ligand_targets = list(),            # Targets per ligand
  lr_network = data.frame(),          # LR interactions
  sender = character(),               # Sender cell type(s)
  receiver = character(),             # Receiver cell type
  condition_oi = character(),         # Condition of interest
  condition_reference = character(),  # Reference condition
  parameters = list()                 # Analysis parameters
)
```

---

## API Reference

| Function | Script | Description |
|----------|--------|-------------|
| `download_nichenet_database()` | database | Download NicheNet database |
| `get_ligand_target_matrix()` | database | Load ligand-target matrix |
| `get_lr_network()` | database | Load LR network |
| `predict_ligand_activities()` | analysis | Core prediction function |
| `get_expressed_genes()` | analysis | Get expressed genes |
| `get_de_genes()` | analysis | Get DE genes |
| `run_nichenet_aggregate()` | seurat | Condition comparison |
| `run_nichenet_cluster_de()` | seurat | Cluster comparison |
| `run_nichenet_celltype_pair()` | seurat | Basic pair analysis |
| `run_nichenet_batch()` | seurat | Batch analysis |
| `plot_ligand_activity_dotplot()` | viz | Ligand activity plot |
| `plot_ligand_target_heatmap()` | viz | LT heatmap |
| `plot_ligand_receptor_heatmap()` | viz | LR heatmap |
| `export_nichenet_results()` | viz | Export to CSV |
| `convert_mouse_to_human()` | utils | Gene conversion |

---

## File Structure

```
bio-single-cell-communication-nichenet-r/
├── SKILL.md                          # This file
├── usage-guide.md                    # Detailed usage guide
├── scripts/r/
│   ├── nichenet_database.R           # Database management
│   ├── nichenet_analysis.R           # Core analysis
│   ├── nichenet_seurat.R             # Seurat integration
│   ├── nichenet_visualization.R      # Visualization
│   └── nichenet_utils.R              # Utilities
├── examples/
│   ├── example_basic.R               # Basic analysis
│   ├── example_seurat.R              # Seurat workflow
│   └── example_differential.R        # Differential analysis
└── tests/
    └── test_nichenet.R               # Unit tests
```

---

## Best Practices

1. **Database Management**: Let the system auto-download on first use
2. **Sender Selection**: Use "all" only when cell types are clearly separated
3. **Replicates**: Ensure sufficient cells (>50) in each group
4. **Gene Sets**: Focus on biologically relevant genes of interest
5. **Validation**: Always validate top predictions experimentally

---

## Related Skills

- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/SKILL.md) - Alternative CCC method
- [bio-spatial-transcriptomics-communication-commot](../bio-spatial-transcriptomics-communication-commot/SKILL.md) - Spatial CCC with Commot

---

## References

1. Browaeys et al. (2020). NicheNet: modeling intercellular communication by linking ligands to target genes. *Nature Methods*.
2. NicheNet documentation: https://github.com/saeyslab/nichenetr
