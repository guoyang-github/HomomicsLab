# Spatial Transcriptomics Statistics - Python Modules

This directory contains modular Python implementations of spatial statistics methods for spatial transcriptomics data analysis.

## Module Structure

```
scripts/python/
├── __init__.py          # Package initialization with exports
├── core_stats.py        # Spatial autocorrelation (Moran's I, Geary's C, LISA)
├── hotspot.py           # Hotspot detection (Getis-Ord Gi*)
├── pattern.py           # Pattern analysis (Co-occurrence, Join Counts, Ripley's K/L)
├── network.py           # Network analysis (Centrality, Network Properties)
├── zones.py             # Zone analysis (Anchor Zones, Ro/e, Niche Enrichment)
└── utils.py             # Utility functions (Validation, Platform detection)
```

## Quick Start

### Method 1: Import Specific Functions

```python
import sys
sys.path.append('scripts/python')

from core_stats import compute_morans_i, compute_lisa
from hotspot import compute_getis_ord_gi
from pattern import compute_cooccurrence

# Use the functions
results = compute_morans_i(adata, genes=['GeneA'])
```

### Method 2: Import by Module

```python
import sys
sys.path.append('scripts/python')

import core_stats
import hotspot
import pattern

# Use with module prefix
results = core_stats.compute_morans_i(adata, genes=['GeneA'])
```

## Dependencies

```bash
pip install scanpy squidpy numpy pandas matplotlib seaborn
pip install libpysal esda pointpats networkx scikit-learn scipy
```

## Module Reference

### core_stats.py
- `compute_morans_i()` - Global spatial autocorrelation
- `compute_gearys_c()` - Alternative spatial autocorrelation
- `compute_lisa()` - Local spatial autocorrelation
- `compute_bivariate_moran()` - Cross-variable spatial correlation
- `run_autocorrelation_analysis()` - Comprehensive analysis workflow

### hotspot.py
- `compute_getis_ord_gi()` - Hotspot/coldspot detection
- `compute_getis_ord_gi_batch()` - Batch hotspot analysis
- `comprehensive_hotspot_analysis()` - Complete hotspot workflow

### pattern.py
- `compute_cooccurrence()` - Cell type co-occurrence analysis
- `compute_join_counts()` - Categorical spatial autocorrelation
- `compute_ripley_k()` / `compute_ripley_l()` - Point pattern analysis
- `compute_neighborhood_enrichment()` - Local cell-type interactions

### network.py
- `compute_centrality_scores()` - Node centrality measures
- `compute_network_properties()` - Global network statistics
- `compute_interaction_matrix()` - Cell-type connectivity patterns

### zones.py
- `define_anchor_zones()` / `define_neural_zones()` - Zone creation
- `compute_roe()` - Ratio of observed/expected analysis
- `analyze_spatial_zones()` - Complete zone analysis workflow

### utils.py
- `validate_spatial_data()` - Data format validation
- `infer_spatial_platform()` - Auto-detect platform type
- `suggest_neighbors()` - Recommend neighbor count

## Examples

See `../../examples/` directory for complete workflow examples.
