---
name: bio-spatial-transcriptomics-microenvironment-misty-r
description: Multi-view spatial microenvironment analysis using mistyR with network export to Cytoscape
tool_type: r
primary_tool: mistyR
supported_tools: [SpatialExperiment, SingleCellExperiment, igraph, Cytoscape]
keywords: ["spatial", "microenvironment", "mistyR", "multi-view", "paracrine", "juxtacrine", "interaction-communities", "network-analysis", "cytoscape", "view-manipulation", "model-interpretation", "result-contrast"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.3"
  mistyR: ">=1.10"
  SpatialExperiment: ">=1.12"
---

## Version Compatibility

- **R**: 4.3+
- **mistyR**: 1.10+ (Bioconductor 3.18+)
- **SpatialExperiment**: 1.12+
- **Cytoscape**: 3.9+ (optional, for visualization)

## Installation

```r
# Install Bioconductor
if (!require("BiocManager"))
    install.packages("BiocManager")

# Install mistyR
BiocManager::install("mistyR")

# Install dependencies
install.packages(c("future", "dplyr", "ggplot2", "igraph", "tidyr", "jsonlite"))
BiocManager::install(c("SpatialExperiment", "SingleCellExperiment"))
```

# mistyR Microenvironment Analysis

Multi-view spatial modeling to quantify intracellular regulation, paracrine signaling, and spatial interaction patterns. Enhanced with network analysis and Cytoscape integration.

## Quick Selector

| View Type | Description | Spatial Scale |
|-----------|-------------|---------------|
| **Intraview** | Intracellular pathway regulation | Single spot |
| **Paraview** | Paracrine signaling (neighborhood) | Radius-defined |
| **Juxtaview** | Direct cell-cell contact | k-nearest neighbors |

### When to Use mistyR

- Identify spatial interaction communities
- Compare microenvironment patterns between conditions
- Analyze cell-type-specific spatial contexts
- **Export networks to Cytoscape for visualization**

---

## Quick Start

```r
library(mistyR)
library(future)

# Enable parallel processing
plan(multisession, workers = 4)

# Load all mistyR scripts
source("scripts/r/misty_analysis.R")
source("scripts/r/misty_network.R")
source("scripts/r/misty_layouts.R")
source("scripts/r/misty_cytoscape.R")
source("scripts/r/misty_views.R")
source("scripts/r/misty_interpretation.R")
source("scripts/r/misty_contrast.R")

# Run analysis
results <- run_misty_pipeline(
  expr_matrix = expr,
  coords = coords,
  para_radius = 100,
  juxta_neighbors = 4
)

# Create network and export to Cytoscape
network <- create_interaction_network(results$interactions)
layout <- apply_layout(network, method = "fr")
export_complete_cytoscape(network, "misty_network", layout = layout)
```

---

## Detailed Usage

### 1. Build Multi-View Model

```r
source("scripts/r/misty_analysis.R")

# Create intraview + paraview + juxtaview
views <- build_misty_views(
  expr_matrix,
  coords,
  para_radius = 100,      # microns
  juxta_neighbors = 4
)
```

### 2. Run Analysis

```r
# Run MISTy with cross-validation
misty_results <- run_misty(views, n.cv.folds = 10, seed = 42)

# Collect results
results <- collect_results(misty_results)
```

### 3. Network Creation and Analysis

```r
source("scripts/r/misty_network.R")

# Create interaction network
network <- create_interaction_network(
  results$interactions,
  view_name = "para.100",
  importance_threshold = 0.01
)

# Calculate network statistics
stats <- calculate_network_stats(network)
print(stats$basic)

# Calculate centrality
centrality <- calculate_centrality(network)
head(centrality[order(-centrality$page_rank), ], 10)

# Identify hubs
hubs <- identify_network_hubs(network, method = "composite", top_n = 20)

# Extract communities
communities <- extract_network_communities(network, algorithm = "louvain")
```

### 4. Network Layout

```r
source("scripts/r/misty_layouts.R")

# Apply layout
layout <- apply_layout(network, method = "fr")

# Community-aware layout
layout_comm <- layout_with_communities(network, communities$communities)

# Compare layouts
layout_comparison <- compare_layouts(network, methods = c("fr", "kk", "drl"))
```

### 5. Export to Cytoscape

```r
source("scripts/r/misty_cytoscape.R")

# Prepare node attributes
node_attrs <- data.frame(
  node = V(network)$name,
  degree = degree(network),
  betweenness = betweenness(network),
  page_rank = page_rank(network)$vector,
  community = communities$membership$community
)

# Export complete package
files <- export_complete_cytoscape(
  network,
  output_prefix = "misty_analysis",
  node_attrs = node_attrs,
  layout = layout,
  communities = communities,
  create_style = TRUE,
  create_script = TRUE
)
```

**Output files:**
- `misty_analysis.graphml` - Network file
- `misty_analysis_nodes.csv` - Node attributes
- `misty_analysis_edges.csv` - Edge attributes
- `misty_analysis.json` - Cytoscape.js format
- `misty_analysis_style.xml` - Visual style
- `misty_analysis_import.R` - RCy3 import script

### 6. Visualize in R

```r
# Plot view contributions
plot_view_contributions(results, top_n = 20)

# Plot interaction network
plot_communication_network(
  results$interactions,
  min_edge_weight = 0.02
)

# Network summary
cat(summarize_network(network, communities))
```

---

## Network Analysis Features

### Network Statistics

| Statistic | Function | Description |
|-----------|----------|-------------|
| Basic stats | `calculate_network_stats()` | Nodes, edges, density, diameter |
| Centrality | `calculate_centrality()` | Degree, betweenness, PageRank |
| Hubs | `identify_network_hubs()` | Multi-criteria hub detection |
| Communities | `extract_network_communities()` | Louvain, walktrap, infomap |

### Layout Algorithms

| Algorithm | Function | Best For |
|-----------|----------|----------|
| Fruchterman-Reingold | `apply_layout(method = "fr")` | General networks |
| Kamada-Kawai | `apply_layout(method = "kk")` | Distance preservation |
| DrL | `apply_layout(method = "drl")` | Large networks |
| MDS | `apply_layout(method = "mds")` | Similarity-based |
| Circular | `apply_layout(method = "circle")` | Community display |
| Hierarchical | `layout_hierarchical()` | Directed networks |
| Community | `layout_with_communities()` | Community preservation |

---

## Parameters

### mistyR Analysis

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `para_radius` | numeric | 100 | Neighborhood radius (microns) |
| `juxta_neighbors` | int | 4 | k-nearest neighbors |
| `n.cv.folds` | int | 10 | Cross-validation folds |

### Platform-Specific Settings

| Platform | para_radius | juxta_neighbors |
|----------|-------------|-----------------|
| Visium (55μm) | 100-150 | 4 |
| Visium HD | 20-50 | 6 |
| Xenium | 30-100 | 5 |

---

## API Reference

### Core mistyR Functions

| Function | Script | Description |
|----------|--------|-------------|
| `run_misty_pipeline()` | misty_analysis.R | Full pipeline |
| `build_misty_views()` | misty_analysis.R | Create views |
| `extract_interaction_communities()` | misty_analysis.R | Detect communities |
| `identify_hub_markers()` | misty_analysis.R | Find hub markers |

### Network Analysis

| Function | Script | Description |
|----------|--------|-------------|
| `create_interaction_network()` | misty_network.R | Create igraph object |
| `calculate_network_stats()` | misty_network.R | Network statistics |
| `calculate_centrality()` | misty_network.R | Centrality metrics |
| `identify_network_hubs()` | misty_network.R | Hub detection |
| `extract_network_communities()` | misty_network.R | Community detection |
| `compare_networks()` | misty_network.R | Compare two networks |

### Layout Functions

| Function | Script | Description |
|----------|--------|-------------|
| `apply_layout()` | misty_layouts.R | Apply layout algorithm |
| `layout_with_communities()` | misty_layouts.R | Community-aware layout |
| `layout_hierarchical()` | misty_layouts.R | Hierarchical layout |
| `compare_layouts()` | misty_layouts.R | Compare multiple layouts |

### Cytoscape Export

| Function | Script | Description |
|----------|--------|-------------|
| `export_cytoscape_graphml()` | misty_cytoscape.R | Export GraphML |
| `export_cytoscape_tables()` | misty_cytoscape.R | Export node/edge tables |
| `export_cytoscape_json()` | misty_cytoscape.R | Export Cytoscape.js JSON |
| `create_cytoscape_style()` | misty_cytoscape.R | Create style XML |
| `export_complete_cytoscape()` | misty_cytoscape.R | Complete export |

### View Manipulation

| Function | Script | Description |
|----------|--------|-------------|
| `add_custom_view()` | misty_views.R | Add custom view to composition |
| `remove_views()` | misty_views.R | Remove specific views |
| `update_view()` | misty_views.R | Update view data |
| `filter_views()` | misty_views.R | Filter views by pattern |
| `list_views()` | misty_views.R | List all views |
| `add_family_view()` | misty_views.R | Aggregate markers by families |
| `add_variable_radius_paraviews()` | misty_views.R | Multiple radius paraviews |
| `add_mask_view()` | misty_views.R | Create mask-based view |
| `add_distance_weighted_view()` | misty_views.R | Distance-weighted neighborhood |
| `validate_view_composition()` | misty_views.R | Validate view composition |

### Model Interpretation

| Function | Script | Description |
|----------|--------|-------------|
| `calculate_view_significance()` | misty_interpretation.R | Permutation testing for views |
| `analyze_importance_stability()` | misty_interpretation.R | Stability across CV folds |
| `calculate_interaction_redundancy()` | misty_interpretation.R | Redundancy between views |
| `identify_redundant_predictors()` | misty_interpretation.R | Find redundant predictors |
| `calculate_target_performance()` | misty_interpretation.R | Performance by target |
| `analyze_view_patterns()` | misty_interpretation.R | Cluster targets by patterns |
| `calculate_interaction_specificity()` | misty_interpretation.R | View specificity of interactions |
| `summarize_model_interpretation()` | misty_interpretation.R | Comprehensive summary |

### Result Contrast

| Function | Script | Description |
|----------|--------|-------------|
| `compare_view_contributions()` | misty_contrast.R | Compare contributions across conditions |
| `plot_contrast_results()` | misty_contrast.R | Visualize interaction changes |
| `compare_target_performance()` | misty_contrast.R | Compare performance across conditions |
| `identify_differential_interactions()` | misty_contrast.R | Find differential interactions |
| `plot_differential_network()` | misty_contrast.R | Visualize network differences |
| `create_contrast_summary()` | misty_contrast.R | Generate comparison report |

---

## Cytoscape Integration

### Import Guide

See [CYTOSCAPE_GUIDE.md](CYTOSCAPE_GUIDE.md) for detailed instructions on:
- Importing networks
- Visual styling
- Layout optimization
- Network analysis
- Exporting figures

### Quick Cytoscape Workflow

1. **Export from R:**
```r
export_complete_cytoscape(network, "my_network")
```

2. **Import to Cytoscape:**
   - File → Import → Network from File
   - Select `my_network.graphml`

3. **Apply Style:**
   - File → Import → Styles from File
   - Select `my_network_style.xml`

4. **Adjust Layout:**
   - Layout → yFiles → Organic

---

## Related Skills

- [bio-spatial-transcriptomics-niches](../bio-spatial-transcriptomics-niches/SKILL.md) - Niche clustering
- [bio-spatial-transcriptomics-communication-liana](../bio-spatial-transcriptomics-communication-liana/SKILL.md) - Ligand-receptor validation
- [bio-spatial-transcriptomics-deconvolution](../bio-spatial-transcriptomics-deconvolution/SKILL.md) - Cell type proportions input
- [bio-spatial-transcriptomics-communication-nichenet-r](../bio-spatial-transcriptomics-communication-nichenet-r/SKILL.md) - NicheNet communication

---

## References

1. Tanevski et al. (2022). mistyR: explainable machine learning for spatial omics. *Genome Biology*.
2. Tanevski et al. (2025). Emergence of persistent local patterns. *Nature Communications*.
3. Shannon et al. (2003). Cytoscape: a software environment for integrated models of biomolecular interaction networks. *Genome Research*.
4. https://github.com/saezlab/mistyR
5. https://cytoscape.org/
