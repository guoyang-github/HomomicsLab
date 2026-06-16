# Cytoscape Network Visualization Guide

Complete guide for visualizing mistyR networks in Cytoscape.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Importing Networks](#importing-networks)
3. [Visual Styling](#visual-styling)
4. [Layout Optimization](#layout-optimization)
5. [Network Analysis](#network-analysis)
6. [Exporting Figures](#exporting-figures)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Export from mistyR

```r
# Run mistyR analysis
results <- run_misty_pipeline(expr, coords)

# Create network
network <- create_interaction_network(results$interactions)

# Calculate layout
coords <- apply_layout(network, method = "fr")

# Export to Cytoscape
export_complete_cytoscape(
  network,
  output_prefix = "misty_network",
  layout = coords,
  communities = communities
)
```

### Files Created

| File | Description |
|------|-------------|
| `misty_network.graphml` | Network in GraphML format |
| `misty_network_nodes.csv` | Node attributes table |
| `misty_network_edges.csv` | Edge attributes table |
| `misty_network.json` | Cytoscape.js JSON format |
| `misty_network_style.xml` | Visual style definition |
| `misty_network_import.R` | RCy3 import script |

---

## Importing Networks

### Method 1: GraphML Import (Recommended)

1. **Open Cytoscape**
2. **File → Import → Network from File...**
3. **Select** `misty_network.graphml`
4. **Click OK**

### Method 2: Table Import

Use when you need more control over mapping:

1. **File → Import → Network from File...**
2. **Select** `misty_network_edges.csv`
3. **Configure columns:**
   - Source Column: `source`
   - Target Column: `target`
   - Interaction Type Column: `interaction`
4. **Click OK**
5. **File → Import → Table from File...**
6. **Select** `misty_network_nodes.csv`
7. **Set Key Column to:** `id`

### Method 3: RCy3 (Automated)

```r
library(RCy3)

# Connect to Cytoscape
cytoscapePing()

# Import using generated script
source("misty_network_import.R")
```

---

## Visual Styling

### Import Style

1. **File → Import → Styles from File...**
2. **Select** `misty_network_style.xml`
3. **In Control Panel → Style**
4. **Select** `misty_style` from dropdown

### Manual Style Configuration

#### Node Settings

| Property | Recommended Value | Mapping |
|----------|-------------------|---------|
| Fill Color | `#CCCCCC` | Discrete Map: `community` |
| Size | `30` | Continuous Map: `degree` (10-50) |
| Shape | `ellipse` | - |
| Border Width | `2` | - |
| Border Color | `#666666` | - |
| Label | `name` | - |
| Label Font Size | `14` | - |

#### Edge Settings

| Property | Recommended Value | Mapping |
|----------|-------------------|---------|
| Line Type | `SOLID` | - |
| Color | `#999999` | - |
| Width | `1` | Continuous Map: `importance` (0.5-5) |
| Target Arrow | `ARROW` | - |
| Transparency | `150` | - |

### Color Schemes

#### Community Colors (Discrete)

```
Community 1: #E41A1C (Red)
Community 2: #377EB8 (Blue)
Community 3: #4DAF4A (Green)
Community 4: #984EA3 (Purple)
Community 5: #FF7F00 (Orange)
```

#### Edge Importance (Continuous)

```
Low (0.0):  #E8E8E8 (Light gray)
Mid (0.5):  #969696 (Gray)
High (1.0): #000000 (Black)
```

---

## Layout Optimization

### Built-in Layouts

| Layout | When to Use | Settings |
|--------|-------------|----------|
| **Force-Directed** | General networks | Edge weight: importance |
| **Circular** | Showing communities | Group by: community |
| **Hierarchical** | Directed networks | Orientation: Top-Bottom |
| **yFiles Organic** | Publication quality | Preferred edge length: 50 |
| **yFiles Circular** | Community emphasis | - |

### Layout Best Practices

1. **Start with Force-Directed** for initial layout
2. **Apply Edge Weights** to reflect importance
3. **Use Community Clustering** if available
4. **Manual Adjustment** for final touches

### Saving Layout

**File → Save → Network as...**
- Save positions with the network

---

## Network Analysis

### Using Built-in Tools

#### 1. Network Analyzer

**Tools → Analyze Network...**

Reports:
- Node degree distribution
- Shortest path lengths
- Clustering coefficient
- Network diameter

#### 2. Centrality Analysis

**Apps → Network Analyzer → Centrality**

Calculate:
- Betweenness centrality
- Closeness centrality
- Eigenvector centrality

#### 3. Community Detection

**Apps → ClusterMaker2**

Algorithms:
- MCL (Markov Clustering)
- GLAY (Community detection)
- Spectral clustering

### Recommended Plugins

| Plugin | Purpose | Installation |
|--------|---------|--------------|
| **cytoHubba** | Hub node detection | Apps → App Manager |
| **MCODE** | Module detection | Apps → App Manager |
| **ClueGO** | Functional annotation | Apps → App Manager |
| **yFiles** | Advanced layouts | Bundled with Cytoscape |

---

## Exporting Figures

### For Publications

#### Resolution Settings

**File → Export → Network to Image...**

| Setting | Value |
|---------|-------|
| Format | PDF or PNG |
| Resolution | 300 DPI (minimum) |
| Width | 2400 pixels |
| Height | 1800 pixels |

#### Color Settings

- Use CMYK-safe colors for print
- Ensure contrast for accessibility
- Consider colorblind-friendly palettes

### For Presentations

**File → Export → Network to PowerPoint...**

Or:
- Export as PNG with transparent background
- Import into PowerPoint/Keynote

### Legend Creation

1. **Create separate legend** using drawing tools
2. **Include:**
   - Node size scale
   - Edge width scale
   - Color meanings
   - Community labels

---

## Troubleshooting

### Import Issues

#### "No edges imported"
- Check column mapping in import dialog
- Verify source/target column names

#### "Missing node attributes"
- Ensure key column matches between nodes and edges
- Check for typos in node IDs

### Performance Issues

#### Slow rendering (> 1000 nodes)
- **View → Show Graphics Details** → Disable
- Reduce edge transparency
- Use simpler shapes

#### Memory errors
- Increase Cytoscape memory: **Edit → Preferences → Memory**
- Reduce network size

### Visual Issues

#### Nodes overlap
- Adjust layout parameters
- Increase repulsion strength
- Use larger canvas

#### Labels unreadable
- Increase font size
- Shorten labels
- Use label auto-rotation

#### Colors not applied
- Check column names match style definition
- Verify discrete vs continuous mapping

---

## Example Workflow

### Complete Analysis Pipeline

```r
# 1. Run mistyR
results <- run_misty_pipeline(expr, coords)

# 2. Create network
network <- create_interaction_network(results$interactions)

# 3. Calculate statistics
stats <- calculate_network_stats(network)
centrality <- calculate_centrality(network)
communities <- extract_network_communities(network)

# 4. Create layout
coords <- apply_layout(network, method = "fr")

# 5. Prepare node attributes
node_attrs <- data.frame(
  node = V(network)$name,
  degree = degree(network),
  betweenness = betweenness(network),
  page_rank = page_rank(network)$vector,
  community = communities$membership$community
)

# 6. Export to Cytoscape
files <- export_complete_cytoscape(
  network,
  "misty_analysis",
  node_attrs = node_attrs,
  layout = coords,
  communities = communities
)
```

### Cytoscape Steps

1. **Import** `misty_analysis.graphml`
2. **Import style** `misty_analysis_style.xml`
3. **Apply layout** → yFiles Organic
4. **Adjust** visual properties
5. **Analyze** with Network Analyzer
6. **Export** final figure

---

## Tips and Tricks

### Efficient Workflow

1. **Save sessions frequently** (File → Save)
2. **Use styles** instead of manual formatting
3. **Group nodes** by community for batch operations
4. **Use filters** to show/hide edges by weight

### Publication Checklist

- [ ] Nodes clearly visible
- [ ] Labels readable
- [ ] Colors distinguishable (B&W test)
- [ ] Legend included
- [ ] Scale bar added
- [ ] Resolution ≥ 300 DPI
- [ ] Font sizes ≥ 8pt

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + L` | Layout menu |
| `Ctrl + S` | Save session |
| `Ctrl + Z` | Undo |
| `Ctrl + Shift + Z` | Redo |
| `Delete` | Remove selected nodes/edges |

---

## References

1. [Cytoscape User Manual](https://cytoscape.org/cytoscape-tutorials/protocols/)
2. [RCy3 Documentation](https://bioconductor.org/packages/release/bioc/html/RCy3.html)
3. Shannon et al. (2003). Cytoscape: a software environment for integrated models of biomolecular interaction networks. *Genome Research*.
