# infercnvpy CNV Analysis Skill

A comprehensive Python-based skill for inferring copy number variation (CNV) from single-cell RNA-seq data using infercnvpy.

## Features

- **CNV Inference**: Sliding window approach for robust CNV detection
- **Gene Position Annotation**: Utilities for adding genomic coordinates
- **Reference Cell Support**: Flexible reference/normal cell specification
- **Clustering**: Identify subclones by CNV profile similarity
- **Visualization**: Chromosome heatmaps and UMAP projections
- **Export**: Save results for downstream analysis

## Quick Start

```python
from infercnv_analysis import run_infercnv_pipeline

# Run CNV inference using immune cells as reference
run_infercnv_pipeline(
    adata,
    reference_key="cell_type",
    reference_cat=["T_cell", "B_cell", "Macrophage"],
    window_size=100,
    key_added="cnv"
)

# Visualize
import infercnvpy as cnv
cnv.pl.chromosome_heatmap(adata, groupby="cell_type")
```

## File Structure

```
bio-single-cell-cnv-infercnvpy/
├── SKILL.md                          # Skill metadata
├── README.md                         # This file
├── usage-guide.md                    # Detailed usage guide
├── scripts/python/
│   └── infercnv_analysis.py         # Main analysis module
├── tests/
│   └── test_infercnvpy.py           # Unit tests
└── examples/
    └── example_basic.py             # Basic usage example
```

## Requirements

- Python >= 3.10
- infercnvpy >= 0.4
- scanpy >= 1.9
- anndata >= 0.8

## Installation

```bash
pip install infercnvpy
```

## Input Data Requirements

1. **Expression matrix**: AnnData object with gene expression
2. **Gene positions**: `chromosome`, `start`, `end` columns in `adata.var`
3. **Reference cells**: Column in `adata.obs` identifying normal cells

## Key Functions

| Function | Purpose |
|----------|---------|
| `run_infercnv_pipeline()` | Complete CNV inference workflow |
| `add_gene_positions()` | Add genomic coordinates from GTF |
| `cluster_by_cnv()` | Cluster cells by CNV profile |
| `identify_cnv_regions()` | Find significant alterations |
| `export_cnv_results()` | Save results to files |

## References

1. infercnvpy: https://infercnvpy.readthedocs.io/
2. Original InferCNV: https://github.com/broadinstitute/inferCNV
