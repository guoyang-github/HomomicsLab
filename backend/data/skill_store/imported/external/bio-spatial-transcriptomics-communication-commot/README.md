# COMMOT Spatial Cell-Cell Communication Analysis

[![Python >=3.9](https://img.shields.io/badge/python->=3.9-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive skill for spatially-informed cell-cell communication analysis using [COMMOT](https://github.com/zcang/COMMOT) (COMMunication analysis by Optimal Transport).

## Overview

COMMOT enables spatially-resolved cell-cell communication analysis by combining gene expression with spatial coordinates using optimal transport. Unlike traditional CCC methods, COMMOT accounts for physical distance between cells and can infer communication directionality.

### Key Features

- **Optimal Transport-Based**: Uses collective optimal transport for robust communication inference
- **Spatially-Aware**: Accounts for physical distance between cells/spots
- **Directional**: Infers communication direction using vector fields
- **Heteromeric Support**: Handles complex ligand-receptor interactions
- **Multiple Databases**: Supports CellChat and CellPhoneDB databases
- **Rich Visualization**: Spatial plots, network diagrams, streamlines, and more

## Quick Start

```python
import scanpy as sc
from scripts.python.core_analysis import (
    prepare_data, get_lr_database, run_commot
)
from visualization import (
    plot_communication_strength, plot_communication_direction
)

# Load spatial data
adata = sc.read_h5ad("spatial_data.h5ad")

# Prepare data
adata = prepare_data(adata, min_counts=100)

# Load LR database
df_lr = get_lr_database('CellChat', species='human')

# Run COMMOT
run_commot(adata, df_lr, database_name='cellchat', distance_threshold=200.0)

# Visualize
plot_communication_strength(adata, 'TGFB1-TGFBR1_TGFBR2', database_name='cellchat')
plot_communication_direction(adata, database_name='cellchat', lr_pair=('TGFB1', 'TGFBR1_TGFBR2'))
```

## Installation

### Prerequisites

```bash
# Install COMMOT
pip install commot

# Optional: for tradeSeq DEG analysis
pip install commot[tradeSeq]

# Additional visualization dependencies
pip install scanpy matplotlib seaborn pandas numpy
```

### System Requirements

- Python >= 3.9
- scanpy >= 1.9.0
- anndata >= 0.8.0
- COMMOT >= 0.2.0
- Sufficient memory for spatial analysis (8GB+ recommended for large datasets)

## File Structure

```
bio-spatial-transcriptomics-communication-commot/
├── README.md                    # This file
├── SKILL.md                     # Detailed API documentation
├── usage-guide.md               # Step-by-step usage guide
├── scripts/
│   └── python/
│       ├── core_analysis.py     # Core analysis functions
│       └── visualization.py     # Visualization functions
├── examples/
│   └── example_basic.py         # Complete workflow example
└── tests/
    └── test_commot.py           # Unit tests
```

## Core Functions

### Analysis Functions (`core_analysis.py`)

| Function | Description |
|----------|-------------|
| `prepare_data()` | Prepare spatial data for COMMOT analysis |
| `get_lr_database()` | Load built-in LR databases (CellChat/CellPhoneDB) |
| `filter_lr_database()` | Filter LR pairs by expression |
| `create_custom_lr_database()` | Create custom LR database |
| `run_commot()` | Main COMMOT analysis function |
| `run_commot_database()` | Convenience function with built-in DB |
| `infer_communication_direction()` | Infer communication direction |
| `cluster_communication()` | Cluster-level communication summary |
| `get_top_lr_pairs()` | Get top LR pairs by strength |
| `export_results()` | Export results to files |

### Visualization Functions (`visualization.py`)

| Function | Description |
|----------|-------------|
| `plot_communication_strength()` | Spatial map of communication strength |
| `plot_communication_direction()` | Vector field of communication direction |
| `plot_lr_expression()` | Ligand and receptor expression side-by-side |
| `plot_cluster_communication_network()` | Network diagram of cluster communication |
| `plot_cluster_communication_dotplot()` | Dot plot of cluster communication |
| `plot_cluster_communication_chord()` | Chord diagram (requires R) |
| `plot_communication_heatmap()` | Heatmap of communication strengths |
| `plot_top_lr_pairs()` | Bar chart of top LR pairs |
| `plot_multiple_lr_pairs()` | Grid of multiple LR pair plots |

## Algorithm Overview

### Optimal Transport for CCC

COMMOT uses optimal transport to infer cell-cell communication by:

1. **Cost Matrix**: Calculates spatial distance between cells
2. **Expression Coupling**: Couples ligand expression (sender) with receptor expression (receiver)
3. **Distance Constraint**: Limits communication to cells within `distance_threshold`
4. **Entropy Regularization**: Balances transport cost and solution smoothness

### Heteromeric Complexes

For complexes like TGFBR1_TGFBR2:
- `heteromeric_rule='min'`: Minimum expression across subunits
- `heteromeric_rule='ave'`: Average expression across subunits

## Example Workflow

See `examples/example_basic.py` for a complete workflow including:

1. Data loading and preparation
2. LR database loading and filtering
3. Running COMMOT with custom and built-in databases
4. Visualization (strength, direction, cluster networks)
5. Exporting results

Run the example:

```bash
cd examples
python example_basic.py
```

## Platform-Specific Settings

| Platform | Spot Size | dis_thr | Notes |
|----------|-----------|---------|-------|
| Visium (55μm) | ~55μm | 200-500μm | ~4-9 spot diameters |
| Visium HD | ~2μm | 50-100μm | Higher resolution |
| Xenium | ~0.5μm | 30-100μm | Subcellular resolution |
| MERFISH | ~1μm | 50-100μm | Single-cell resolution |
| Slide-seq | ~10μm | 100-200μm | Puck-based |

## Database Options

### CellChat Database
- Curated signaling pathways
- Secreted, contact, and ECM-receptor signaling
- Available for human, mouse, and zebrafish

### CellPhoneDB v4.0
- Multi-subunit complex support
- Secreted and membrane-bound signaling
- Available for human and mouse

### Custom Database
Format: DataFrame with columns:
- `ligand`: Ligand gene name
- `receptor`: Receptor gene name (use `_` for heteromeric, e.g., `TGFBR1_TGFBR2`)
- `pathway_name`: Signaling pathway name

## Output Structure

COMMOT stores results in `adata.obsm`:

```python
# Sender/receiver summaries (key pattern: 'commot-{database_name}-sum-{direction}')
adata.obsm['commot-cellchat-sum-sender']      # Total sent signal per spot
adata.obsm['commot-cellchat-sum-receiver']    # Total received signal per spot

# Individual LR pair communication matrices (in adata.obsp)
adata.obsp['commot-cellchat-TGFB1-TGFBR1_TGFBR2']  # Spot-to-spot communication

# Cluster communication (in adata.uns)
adata.uns['commot_cluster-leiden-cellchat-total-total']['communication_matrix']
```

## Troubleshooting

### No communication detected
- Reduce `distance_threshold` if set too high
- Check spatial coordinates are in microns
- Verify ligand/receptor expression in data
- Increase `min_exp_frac` threshold

### Out of memory
- Subsample to region of interest
- Limit LR pairs analyzed
- Increase spatial filtering
- Process samples separately

### Visualization issues
- Ensure spatial coordinates exist in `adata.obsm['spatial']`
- Check cluster annotations for network plots
- Install R/circlize for chord diagrams

## Citation

If you use COMMOT in your research, please cite:

```
Cang, Z., Zhao, Y., Almet, A.A. et al. Screening cell–cell communication 
in spatial transcriptomics via collective optimal transport. 
Nat Methods 20, 218–228 (2023). 
https://doi.org/10.1038/s41592-022-01728-4
```

## References

1. Cang et al. (2023). Screening cell–cell communication in spatial transcriptomics via collective optimal transport. *Nature Methods*.
2. Jin et al. (2021). Inference and analysis of cell-cell communication using CellChat. *Nature Communications*.
3. Efremova et al. (2020). CellPhoneDB: inferring cell–cell communication from combined expression of multi-subunit ligand–receptor complexes. *Nature Protocols*.

## Related Skills

- [bio-spatial-transcriptomics-communication-liana](../bio-spatial-transcriptomics-communication-liana/) - Alternative CCC method
- [bio-spatial-transcriptomics-communication-cellchat-r](../bio-spatial-transcriptomics-communication-cellchat-r/) - CellChat R implementation
- [bio-spatial-transcriptomics-analysis-scanpy](../bio-spatial-transcriptomics-analysis-scanpy/) - General spatial analysis

## License

This skill is provided under the MIT License. The underlying COMMOT package is under BSD-3-Clause.

## Contact

For questions about this skill, please open an issue in the repository.
For questions about COMMOT package, visit: https://github.com/zcang/COMMOT
