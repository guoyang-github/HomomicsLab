# mistyR Usage Guide

## Overview

mistyR analyzes tissue microenvironment using multi-view spatial modeling. Identifies spatial interaction communities and quantifies view contributions.

**Enhanced capabilities:**
- Network analysis and Cytoscape export
- Advanced view manipulation (custom views, variable radii, masks)
- Model interpretation (significance testing, stability analysis)
- Result contrast (multi-condition comparison, differential interactions)

## When to Use

- Spatial interaction analysis
- Identify spatial communities
- Compare conditions
- Multi-view modeling (intra/para/juxta)
- **Network visualization in Cytoscape**
- **Advanced view manipulation**
- **Model interpretation and significance testing**
- **Multi-condition result contrast**

## Quick Start

```r
library(mistyR)
library(future)

# Enable parallel processing
plan(multisession, workers = 4)

# Load all scripts
source("scripts/r/misty_analysis.R")
source("scripts/r/misty_network.R")
source("scripts/r/misty_layouts.R")
source("scripts/r/misty_cytoscape.R")
source("scripts/r/misty_views.R")
source("scripts/r/misty_interpretation.R")
source("scripts/r/misty_contrast.R")

# Build views
views <- build_misty_views(expr, coords, para_radius = 100, juxta_neighbors = 4)

# Run analysis
results <- run_misty_pipeline(views)

# Create and export network
network <- create_interaction_network(results$interactions)
layout <- apply_layout(network, method = "fr")
export_complete_cytoscape(network, "misty_network", layout = layout)
```

## View Types

| View | Description | Spatial Scale |
|------|-------------|---------------|
| Intraview | Intracellular | Single spot |
| Paraview | Paracrine | Radius-defined |
| Juxtaview | Direct contact | k-nearest neighbors |

## Step-by-Step

### 1. Prepare Data

```r
# Expression matrix: genes x spots
expr_matrix <- assay(spe, "logcounts")

# Coordinates: spots x 2
coords <- spatialCoords(spe)
```

### 2. Build Views

```r
views <- build_misty_views(
  expr_matrix,
  coords,
  para_radius = 100,      # microns
  juxta_neighbors = 4
)
```

### 3. Run Analysis

```r
results <- run_misty_pipeline(
  expr_matrix,
  coords,
  para_radius = 100,
  juxta_neighbors = 4,
  n.cv.folds = 10
)
```

### 4. Network Creation

```r
# Create network from interactions
network <- create_interaction_network(
  results$interactions,
  view_name = "para.100",
  importance_threshold = 0.01
)

# Multi-view network
multi_network <- create_multi_view_network(
  results$interactions,
  views = c("intra", "para.100", "juxta.4")
)
```

### 5. Network Analysis

#### Statistics

```r
# Calculate network statistics
stats <- calculate_network_stats(network)
print(stats$basic)
# $n_nodes
# $n_edges
# $density
# $diameter
```

#### Centrality Analysis

```r
# Calculate centrality metrics
centrality <- calculate_centrality(network)

# View top nodes by PageRank
head(centrality[order(-centrality$page_rank), ], 10)

# Identify hubs
hubs <- identify_network_hubs(
  network,
  method = "composite",  # or "degree", "betweenness", "pagerank"
  top_n = 20
)
```

#### Community Detection

```r
# Extract communities
communities <- extract_network_communities(
  network,
  algorithm = "louvain",  # or "walktrap", "infomap", "label_prop"
  weights = TRUE
)

# View community summary
print(communities$summary)
```

### 6. Network Layout

```r
# Apply layout
layout <- apply_layout(network, method = "fr")

# Available methods:
# "fr" - Fruchterman-Reingold (force-directed)
# "kk" - Kamada-Kawai
# "drl" - DrL (large networks)
# "mds" - Multi-dimensional scaling
# "circle" - Circular layout
# "hierarchical" - Hierarchical layout

# Community-aware layout
layout_comm <- layout_with_communities(
  network,
  communities$communities,
  expand = 2
)

# Compare layouts
layout_comparison <- compare_layouts(
  network,
  methods = c("fr", "kk", "drl"),
  plot = TRUE
)
```

### 7. Export to Cytoscape

```r
# Prepare node attributes
node_attrs <- data.frame(
  node = V(network)$name,
  degree = degree(network),
  betweenness = betweenness(network),
  page_rank = page_rank(network)$vector,
  community = communities$membership$community,
  stringsAsFactors = FALSE
)

# Complete export
files <- export_complete_cytoscape(
  network,
  output_prefix = "misty_analysis",
  node_attrs = node_attrs,
  layout = layout,
  communities = communities,
  create_style = TRUE,
  create_script = TRUE
)

# Output files:
# - misty_analysis.graphml
# - misty_analysis_nodes.csv
# - misty_analysis_edges.csv
# - misty_analysis.json
# - misty_analysis_style.xml
# - misty_analysis_import.R
```

### 8. Visualize in R

```r
# Standard mistyR plots
plot_view_contributions(results, top_n = 20)
plot_communication_network(results$interactions)

# Network summary
cat(summarize_network(network, communities))

# Plot with custom layout
plot(network, layout = layout,
     vertex.size = 5,
     vertex.color = communities$membership$community,
     vertex.label = V(network)$name,
     edge.width = E(network)$weight * 2)
```

### 9. View Manipulation (Advanced)

```r
source("scripts/r/misty_views.R")

# Add variable radius paraviews for multi-scale analysis
views <- add_variable_radius_paraviews(
  views,
  coords,
  radii = c(50, 100, 150, 200)
)

# Add marker family aggregation view
families <- list(
  immune = c("CD3D", "CD4", "CD8A", "CD68"),
  stroma = c("COL1A1", "ACTA2"),
  proliferation = c("MKI67", "PCNA")
)
views <- add_family_view(views, families, aggregation = "mean")

# Add spatial mask view (e.g., tumor region)
tumor_mask <- coords[, 1] > 500  # Define tumor region
views <- add_mask_view(views, coords, tumor_mask, "tumor_region")

# Add distance-weighted view
views <- add_distance_weighted_view(
  views, coords, radius = 100,
  weight_function = "gaussian", sigma = 50
)

# List and validate views
list_views(views)
validate_view_composition(views)

# Filter views
views_filtered <- filter_views(views, pattern = "^para\\.")  # Keep only paraviews
```

### 10. Model Interpretation

```r
source("scripts/r/misty_interpretation.R")

# Calculate view contribution significance
sig_results <- calculate_view_significance(results, n_permutations = 100)
print(sig_results %>% filter(significant_adj))

# Analyze importance stability across CV folds
stability <- analyze_importance_stability(results, importance_threshold = 0.01)
print(stability %>% filter(reliable))

# Calculate interaction redundancy between views
redundancy <- calculate_interaction_redundancy(results, method = "correlation")
print(redundancy$average)

# Identify redundant predictors
redundant <- identify_redundant_predictors(results, correlation_threshold = 0.8)
print(redundant)

# Calculate target performance
performance <- calculate_target_performance(results, measure = "multi.R2")
print(performance %>% filter(performance_category %in% c("Very Good", "Excellent")))

# Analyze view contribution patterns
patterns <- analyze_view_patterns(results, method = "kmeans", n_clusters = 4)
print(patterns$cluster_profiles)

# Calculate interaction specificity
specificity <- calculate_interaction_specificity(results)
print(specificity %>% filter(specific))

# Generate comprehensive interpretation summary
interpretation <- summarize_model_interpretation(results)
cat(interpretation$summary_text)
```

### 11. Result Contrast (Multi-condition)

```r
source("scripts/r/misty_contrast.R")

# Compare two conditions
results_list <- list(
  control = control_results,
  treated = treated_results
)

# Compare view contributions
contrib_comparison <- compare_view_contributions(results_list)
print(contrib_comparison$summary)

# Compare target performance
perf_comparison <- compare_target_performance(
  results_list,
  measure = "multi.R2"
)
print(perf_comparison$wide_format)

# Identify differential interactions
diff_interactions <- identify_differential_interactions(
  list(control_results, treated_results),
  view = "para.100",
  importance_threshold = 0.01,
  fold_change_threshold = 2
)
print(diff_interactions)

# Visualize contrast results
contrast_plot <- plot_contrast_results(
  control_results,
  treated_results,
  view = "para.100",
  cutoff = 0.5,
  plot_type = "heatmap"
)

# Plot differential network
plot_differential_network(
  diff_interactions,
  top_n = 50
)

# Generate comprehensive contrast summary
summary <- create_contrast_summary(
  control_results,
  treated_results,
  "Control", "Treated"
)
cat(summary$summary_text)
```

## Platform-Specific Settings

| Platform | para_radius | juxta_neighbors |
|----------|-------------|-----------------|
| Visium (55μm) | 100-150 | 4 |
| Visium HD | 20-50 | 6 |
| Xenium | 30-100 | 5 |

## Network Analysis Best Practices

### Choosing Layouts

| Layout | Best For | Network Size |
|--------|----------|--------------|
| Force-directed (FR) | General use | < 1000 nodes |
| Kamada-Kawai | Distance preservation | < 500 nodes |
| DrL | Large networks | > 1000 nodes |
| MDS | Similarity-based | Any |
| Circular | Community display | < 200 nodes |
| Hierarchical | Directed networks | Any |

### View Manipulation Functions

| Function | Purpose | Use Case |
|----------|---------|----------|
| `add_variable_radius_paraviews()` | Multi-scale analysis | Compare different spatial scales |
| `add_family_view()` | Marker aggregation | Group markers by function/pathway |
| `add_mask_view()` | Region-specific | Analyze specific tissue regions |
| `add_distance_weighted_view()` | Weighted neighborhood | Gaussian/exponential decay |
| `add_custom_view()` | Custom data | Add experimental data as view |
| `filter_views()` | View selection | Focus on specific view types |
| `validate_view_composition()` | Quality check | Ensure views are consistent |

### Model Interpretation Functions

| Function | Purpose | Output |
|----------|---------|--------|
| `calculate_view_significance()` | Statistical testing | P-values for view contributions |
| `analyze_importance_stability()` | Reliability assessment | Stability scores per interaction |
| `calculate_interaction_redundancy()` | Redundancy analysis | Correlation matrices |
| `calculate_target_performance()` | Predictive power | R² values per target |
| `analyze_view_patterns()` | Pattern discovery | Target clusters by contribution |
| `calculate_interaction_specificity()` | Specificity analysis | View-specific interactions |

### Result Contrast Functions

| Function | Purpose | Use Case |
|----------|---------|----------|
| `compare_view_contributions()` | Compare contributions | Which views differ between conditions |
| `identify_differential_interactions()` | Find changes | Gained/lost interactions |
| `plot_contrast_results()` | Visualize differences | Heatmap of interaction changes |
| `compare_target_performance()` | Performance diff | Which targets predict better/worse |
| `create_contrast_summary()` | Comprehensive report | Complete condition comparison |

### Centrality Interpretation

| Measure | Interpretation |
|---------|----------------|
| Degree | Number of connections |
| Betweenness | Bridge between communities |
| PageRank | Influence in network |
| Eigenvector | Connection to important nodes |
| Closeness | Short paths to other nodes |

### Community Detection

| Algorithm | Best For | Speed |
|-----------|----------|-------|
| Louvain | General use | Fast |
| Walktrap | Hierarchical structure | Medium |
| Infomap | Information flow | Slow |
| Label Propagation | Large networks | Fast |

## Complete Workflow Example

```r
library(mistyR)
library(future)
plan(multisession, workers = 4)

# Load all scripts
source("scripts/r/misty_analysis.R")
source("scripts/r/misty_network.R")
source("scripts/r/misty_layouts.R")
source("scripts/r/misty_cytoscape.R")
source("scripts/r/misty_views.R")
source("scripts/r/misty_interpretation.R")
source("scripts/r/misty_contrast.R")

# 1. Prepare data
expr_matrix <- assay(spe, "logcounts")
coords <- spatialCoords(spe)

# 2. Run mistyR
results <- run_misty_pipeline(
  expr_matrix,
  coords,
  para_radius = 100,
  juxta_neighbors = 4,
  n.cv.folds = 10
)

# 3. Create network
network <- create_interaction_network(
  results$interactions,
  view_name = "para.100",
  importance_threshold = 0.01
)

# 4. Analyze network
stats <- calculate_network_stats(network)
centrality <- calculate_centrality(network)
communities <- extract_network_communities(network, algorithm = "louvain")
hubs <- identify_network_hubs(network, top_n = 20)

# 5. Create layout
layout <- layout_with_communities(network, communities$communities)

# 6. Prepare attributes
node_attrs <- data.frame(
  node = V(network)$name,
  degree = degree(network),
  betweenness = betweenness(network),
  page_rank = page_rank(network)$vector,
  community = communities$membership$community,
  is_hub = V(network)$name %in% hubs$node,
  stringsAsFactors = FALSE
)

# 7. Export to Cytoscape
files <- export_complete_cytoscape(
  network,
  "misty_analysis",
  node_attrs = node_attrs,
  layout = layout,
  communities = communities
)

# 8. Summary
print(stats$basic)
cat(summarize_network(network, communities))
```

## Advanced Workflow: Multi-scale Analysis with Interpretation

```r
library(mistyR)
library(future)
plan(multisession, workers = 4)

# Load all scripts
source("scripts/r/misty_analysis.R")
source("scripts/r/misty_network.R")
source("scripts/r/misty_layouts.R")
source("scripts/r/misty_cytoscape.R")
source("scripts/r/misty_views.R")
source("scripts/r/misty_interpretation.R")
source("scripts/r/misty_contrast.R")

# 1. Prepare data
expr_matrix <- assay(spe, "logcounts")
coords <- spatialCoords(spe)

# 2. Build multi-scale views
views <- build_misty_views(
  expr_matrix,
  coords,
  para_radius = 100,
  juxta_neighbors = 4
)

# Add variable radius paraviews for multi-scale analysis
views <- add_variable_radius_paraviews(
  views, coords, radii = c(50, 100, 150)
)

# Add marker family view
families <- list(
  immune = c("CD3D", "CD4", "CD8A", "CD68"),
  stroma = c("COL1A1", "COL1A2", "ACTA2"),
  proliferation = c("MKI67", "PCNA")
)
views <- add_family_view(views, families, aggregation = "mean")

# Validate views
validate_view_composition(views)

# 3. Run mistyR
results <- run_misty_pipeline(
  views,
  n.cv.folds = 10,
  seed = 42
)

# 4. Model interpretation
sig_results <- calculate_view_significance(results, n_permutations = 100)
stability <- analyze_importance_stability(results)
performance <- calculate_target_performance(results)
interpretation <- summarize_model_interpretation(results)
cat(interpretation$summary_text)

# 5. Create and analyze network
network <- create_interaction_network(
  results$interactions,
  view_name = "para.100",
  importance_threshold = 0.01
)

communities <- extract_network_communities(network, algorithm = "louvain")
layout <- layout_with_communities(network, communities$communities)

# 6. Export to Cytoscape
node_attrs <- data.frame(
  node = V(network)$name,
  degree = degree(network),
  betweenness = betweenness(network),
  page_rank = page_rank(network)$vector,
  community = communities$membership$community,
  stringsAsFactors = FALSE
)

files <- export_complete_cytoscape(
  network,
  "misty_advanced",
  node_attrs = node_attrs,
  layout = layout,
  communities = communities
)
```

## Condition Comparison Workflow

```r
# Run mistyR on two conditions
control_results <- run_misty_pipeline(control_views, n.cv.folds = 10)
treated_results <- run_misty_pipeline(treated_views, n.cv.folds = 10)

# Compare view contributions
contrib_comparison <- compare_view_contributions(
  list(control = control_results, treated = treated_results)
)
print(contrib_comparison$summary)

# Identify differential interactions
diff_interactions <- identify_differential_interactions(
  list(control_results, treated_results),
  view = "para.100",
  importance_threshold = 0.01,
  fold_change_threshold = 2
)

# Visualize contrast
plot_contrast_results(
  control_results,
  treated_results,
  view = "para.100",
  cutoff = 0.5,
  plot_type = "heatmap"
)

# Generate comprehensive summary
summary <- create_contrast_summary(
  control_results,
  treated_results,
  "Control",
  "Treated"
)
cat(summary$summary_text)
```

## Best Practices

### Analysis Setup
1. **Choose appropriate radius** based on tissue scale
2. **Use HVGs** for computational efficiency
3. **Enable parallel** processing for speed
4. **Validate communities** with known biology
5. **Export to Cytoscape** for publication-quality figures
6. **Compare multiple layouts** to find best representation

### View Manipulation
1. **Use variable radius paraviews** to find optimal spatial scale
2. **Add family views** for pathway-level analysis
3. **Use mask views** to compare different tissue regions
4. **Validate view composition** before running mistyR
5. **Remove unused views** to reduce computation time

### Model Interpretation
1. **Check view significance** to validate contribution importance
2. **Analyze stability** to identify reliable interactions
3. **Calculate redundancy** to understand view relationships
4. **Review target performance** to identify well/poorly predicted markers
5. **Use specificity analysis** to find view-specific interactions

### Result Contrast
1. **Compare view contributions** first to identify changed mechanisms
2. **Use fold-change threshold** appropriately (2x for stringent, 1.5x for exploratory)
3. **Visualize with heatmaps** for many interactions, networks for few
4. **Validate differential interactions** with stability metrics
5. **Create summary reports** for documentation

## Troubleshooting

### Out of memory
- Reduce gene set (use HVGs)
- Subsample spots
- Reduce CV folds

### No significant interactions
- Increase radius
- Check coordinate units
- Verify expression values

### Layout issues
- Try different layout algorithms
- Adjust importance threshold
- Filter low-weight edges

### Cytoscape import fails
- Check file encoding (UTF-8)
- Verify column names match
- Ensure no special characters in node names

## References

1. Tanevski et al. (2022). mistyR: explainable machine learning for spatial omics. *Genome Biology*.
2. Shannon et al. (2003). Cytoscape: a software environment for integrated models of biomolecular interaction networks. *Genome Research*.

## Additional Documentation

- [CYTOSCAPE_GUIDE.md](CYTOSCAPE_GUIDE.md) - Complete Cytoscape visualization guide
