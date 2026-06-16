# FastCCC Cell-Cell Communication Analysis

Fast permutation-free cell-cell communication analysis for single-cell and spatial transcriptomics data.

## Quick Start

```python
import sys
sys.path.append('scripts/python')

from core_analysis import run_fastccc_cauchy_combined, get_significant_interactions

# Run FastCCC with Cauchy combination
results = run_fastccc_cauchy_combined(
    adata,
    database_file_path='./cellphonedb_data',
    groupby='cell_type',
    save_path='./fastccc_results'
)

# Get significant interactions
significant = get_significant_interactions(
    results['pvals'],
    results['interactions_strength'],
    pval_threshold=0.05
)
```

## Installation

```bash
# Install FastCCC
pip install fastccc

# Install additional dependencies
pip install scanpy pandas numpy matplotlib seaborn networkx
```

## Documentation

- **[SKILL.md](SKILL.md)** - Complete API reference and function documentation
- **[usage-guide.md](usage-guide.md)** - Step-by-step usage guide

## Structure

```
bio-spatial-transcriptomics-communication-fastccc/
├── scripts/python/
│   ├── core_analysis.py         # Core FastCCC functions
│   ├── reference_builder.py     # Reference panel building and inference
│   ├── utils.py                  # Utility functions
│   └── visualization.py          # Plotting functions
├── examples/
│   ├── minimal_example.py        # Basic usage example
│   └── advanced_example.py       # Advanced features demo
├── tests/
│   └── test_fastccc.py           # Unit tests
├── SKILL.md                      # Skill documentation
├── usage-guide.md                # Detailed usage guide
└── README.md                     # This file
```

## Key Features

- **Permutation-free**: Analytical p-values via FFT convolution
- **Scalable**: Handles 100k+ cells efficiently
- **Reference-based**: Leverage atlas-scale references
- **Cauchy combination**: Robust multi-method aggregation
- **Modular scoring**: Mean, Median, Quantile summaries

## When to Use

- Large-scale CCC analysis (10k+ cells)
- Multiple condition comparisons
- Reference-based inference
- Fast initial screening
- Spatial transcriptomics CCC

## Speed Comparison

| Dataset Size | FastCCC | CellPhoneDB | CellChat |
|--------------|---------|-------------|----------|
| 1k cells | 30s | 5min | 10min |
| 10k cells | 2min | 1hr | 2hr |
| 50k cells | 10min | 8hr | 16hr |

## Example: Reference-Based Analysis

```python
from reference_builder import build_reference_panel, infer_ccc_with_reference

# Build reference from control data
ref_path = build_reference_panel(
    control_adata,
    database_file_path='./cellphonedb_data',
    reference_name='PBMC_ref',
    groupby='cell_type'
)

# Infer CCC on treatment data
results = infer_ccc_with_reference(
    treatment_adata,
    database_file_path='./cellphonedb_data',
    reference_path=ref_path,
    groupby='cell_type'
)
```

## Example: Cauchy Combination

```python
from core_analysis import run_fastccc_cauchy_combined

# Run multiple methods and combine
results = run_fastccc_cauchy_combined(
    adata,
    database_file_path='./cellphonedb_data',
    groupby='cell_type',
    single_unit_summary_list=['Mean', 'Median', 'Q3'],
    complex_aggregation_list=['Minimum', 'Average'],
    lr_combination_list=['Arithmetic', 'Geometric']
)
```

## Citation

Hou et al. (2025). FastCCC: a permutation-free framework for scalable, robust, and reference-based cell-cell communication analysis in single cell transcriptomics studies. *Nature Communications* 16, 11428.

## License

FastCCC is released under the MIT License. This skill wrapper follows the same license.
