# Cell2location Spatial Deconvolution Skill

Python-based spatial transcriptomics deconvolution using cell2location with Bayesian uncertainty quantification. See `SKILL.md` for the full agent-oriented reference.

## Quick Start

```python
from scripts.python.core_analysis import prepare_data, run_cell2location

spatial_prep, ref_prep = prepare_data(
    spatial_adata, reference_adata, cell_type_key='cell_type'
)

results = run_cell2location(
    spatial_prep, ref_prep,
    cell_type_key='cell_type',
    max_epochs=30000, gpu=True
)
```

## File Structure

```
bio-spatial-transcriptomics-deconvolution-cell2location/
├── SKILL.md                      # Agent-oriented skill reference
├── README.md                     # This file
├── usage-guide.md                # Detailed usage guide (raw cell2location API)
├── scripts/
│   └── python/
│       ├── __init__.py
│       ├── core_analysis.py      # Main analysis functions
│       ├── visualization.py      # Visualization utilities
│       └── utils.py              # Helper functions
├── tests/
│   └── test_cell2location.py     # Unit tests
└── examples/
    ├── minimal_example.py        # Basic workflow
    └── batch_analysis.py         # Multi-sample analysis
```

## Requirements

- Python >= 3.9
- cell2location >= 0.1.3
- scanpy >= 1.10.0
- **scvi-tools >= 1.0.0, < 1.2.0** (pin required — cell2location incompatible with ≥1.2.0)
- torch with CUDA (recommended)

## Key Functions

### Core
- `prepare_data()` — Harmonize spatial and reference data; enforce raw counts; subset to common genes
- `run_cell2location()` — Two-stage pipeline (RegressionModel signatures → Cell2location fitting); handles scvi-tools version compatibility
- `estimate_cell_type_proportions()` — Extract proportions from `.obsm` posteriors; normalize to sum 1
- `extract_proportions()` — Lower-level extractor returning `(DataFrame, cell_type_list)`

### Utilities
- `validate_inputs()` — Pre-flight checks: cell type key, ≥10 cells/type, spatial coordinates
- `filter_low_quality_spots()` — QC filter by counts and genes detected
- `estimate_optimal_epochs()` — Data-size-aware epoch recommendation

### Visualization
- `plot_proportions_spatial()` — Multi-panel spatial scatter maps
- `plot_cell_type_maps()` — q05/q50/q95 uncertainty comparison
- `plot_dominant_cell_type()` — Dominant cell type per spot
- `plot_proportion_distribution()` — Box plot of proportion distributions

## Output

| Key | Description | Location |
|-----|-------------|----------|
| `q05_cell_abundance_w_sf` | 5% quantile (conservative) | `.obsm` |
| `q50_cell_abundance_w_sf` | Median (best point estimate) | `.obsm` |
| `q95_cell_abundance_w_sf` | 95% quantile (liberal) | `.obsm` |
| `means_cell_abundance_w_sf` | Mean abundance | `.obsm` |
| `stds_cell_abundance_w_sf` | Standard deviation | `.obsm` |

## References

1. Kleshchevnikov et al. (2022). Cell2location maps fine-grained cell types in spatial transcriptomics. *Nature Biotechnology*, 40, 661–671.
2. Documentation: https://cell2location.readthedocs.io/
