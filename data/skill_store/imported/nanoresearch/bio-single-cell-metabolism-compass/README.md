# COMPASS Single-Cell Metabolic Flux Analysis

Metabolic flux inference using COMPASS (COBRA for Personalized Analysis of Single-cell metabolism) for single-cell transcriptomics data.

## Quick Start

```python
import sys
sys.path.append('scripts/python')

from core_analysis import run_compass, add_compass_results_to_adata

# Run COMPASS analysis
compass_results = run_compass(
    adata,
    output_dir='./compass_output',
    model='RECON2_mat',
    species='homo_sapiens',
    num_processes=4
)

# Add results to AnnData
adata = add_compass_results_to_adata(adata, compass_results)
```

## Installation

```bash
# Install COMPASS (requires IBM CPLEX)
pip install compass-sc

# Install additional dependencies
pip install scanpy pandas numpy matplotlib seaborn statsmodels
```

**Note**: COMPASS requires IBM CPLEX optimization solver. Academic licenses are free.

## Documentation

- **[SKILL.md](SKILL.md)** - Complete API reference and function documentation
- **[usage-guide.md](usage-guide.md)** - Step-by-step usage guide

## Structure

```
bio-single-cell-metabolism-compass/
├── scripts/python/
│   ├── core_analysis.py      # Core COMPASS functions
│   ├── utils.py               # Utility functions
│   └── visualization.py       # Plotting functions
├── examples/
│   ├── minimal_example.py     # Basic usage example
│   └── advanced_example.py    # Advanced features demo
├── tests/
│   └── test_compass.py        # Unit tests
├── SKILL.md                   # Skill documentation
├── usage-guide.md             # Detailed usage guide
└── README.md                  # This file
```

## Key Features

- **Metabolic Flux Analysis**: Predict metabolic reaction activities at single-cell resolution
- **Metabolite Exchange**: Calculate uptake and secretion potentials
- **Differential Analysis**: Compare metabolic states between conditions
- **Visualization**: Comprehensive plotting functions
- **Integration**: Seamless Scanpy/AnnData integration

## When to Use

- Characterize metabolic heterogeneity between cell types
- Identify metabolic dependencies and vulnerabilities
- Study metabolite exchange in the microenvironment
- Connect gene expression to metabolic function

## Available Models

| Model | Species | Reactions | Use Case |
|-------|---------|-----------|----------|
| RECON2_mat | Human | ~7,440 | General metabolism (recommended) |
| RECON1_mat | Human | ~3,740 | Core metabolism |
| RECON2.2 | Human | ~7,780 | Updated annotations |
| Mouse-GEM | Mouse | ~7,600 | Mouse metabolism |

## Example: Differential Flux Analysis

```python
from core_analysis import run_compass, analyze_differential_flux
from visualization import plot_differential_flux

# Run COMPASS
compass_results = run_compass(adata, output_dir='./output', ...)

# Compare conditions
diff_results = analyze_differential_flux(
    compass_results['reaction_scores'],
    adata.obs['condition']
)

# Visualize
plot_differential_flux(diff_results, save_path='diff_flux.png')
```

## Citation

Wagner et al. (2021). Metabolic modeling of single cells via flux balance analysis and constraint programming. *Nature Communications* 12, 3635.

## License

COMPASS is released under the MIT License. This skill wrapper follows the same license.
