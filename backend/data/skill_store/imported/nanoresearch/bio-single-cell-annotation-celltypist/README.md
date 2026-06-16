# CellTypist: Automated Cell Type Annotation

Python package for automated cell type classification using pre-trained logistic regression models. Best suited for human immune cell annotation.

## Overview

CellTypist provides fast and accurate cell type annotation using:

- **Pre-trained models**: Ready-to-use models for human and mouse immune cells
- **Logistic regression**: Probabilistic cell type classification
- **Majority voting**: Refine predictions using cluster consensus
- **Multi-label classification**: Assign multiple labels to ambiguous cells

Reference: Domínguez Conde et al., "Cross-tissue immune cell analysis reveals tissue-specific features in humans", Science 2022

## Installation

```bash
pip install celltypist scanpy
```

Optional for visualization:
```bash
pip install seaborn matplotlib
```

## Quick Start

```python
import celltypist
import scanpy as sc

# Source wrapper functions
from scripts.python.core_analysis import run_celltypist_annotation

# Load data
adata = sc.read_h5ad("your_data.h5ad")

# Run annotation
adata = run_celltypist_annotation(
    adata,
    model='Immune_All_Low.pkl',
    majority_voting=True
)

# View results
print(adata.obs['celltypist_label'].value_counts())
```

## Directory Structure

```
.
├── README.md                   # This file
├── SKILL.md                    # Detailed documentation for LLM agents
├── usage-guide.md              # Step-by-step usage guide
├── examples/                   # Example scripts
│   ├── minimal_example.py      # Basic workflow
│   └── advanced_example.py     # Comprehensive workflow
├── scripts/python/             # Core analysis scripts
│   ├── core_analysis.py        # Main analysis functions
│   ├── visualization.py        # Plotting functions
│   └── utils.py                # Utility functions
├── tests/                      # Unit tests
│   └── test_celltypist.py
└── assets/                     # Additional resources
    └── celltypist_models.json  # Model catalog
```

## Core Modules

### core_analysis.py

Main analysis functions:

| Function | Description |
|----------|-------------|
| `validate_celltypist_input()` | Validate input data |
| `get_available_models()` | List available models |
| `download_celltypist_model()` | Download pre-trained model |
| `load_celltypist_model()` | Load model from disk |
| `annotate_cells()` | Run cell type annotation |
| `add_predictions_to_adata()` | Add predictions to AnnData |
| `run_celltypist_annotation()` | Complete annotation pipeline |
| `filter_by_confidence()` | Filter by confidence threshold |
| `get_model_info()` | Get model information |
| `compare_models()` | Compare multiple models |
| `train_celltypist_model()` | Train custom model |

### visualization.py

Plotting functions:

| Function | Description |
|----------|-------------|
| `plot_celltypist_dotplot()` | Dot plot (predictions vs reference) |
| `plot_confidence_distribution()` | Confidence score distribution |
| `plot_celltype_proportions()` | Cell type proportions |
| `plot_umap_with_predictions()` | UMAP with predictions |
| `plot_prediction_heatmap()` | Prediction heatmap |
| `plot_top_celltypes()` | Top cell types bar plot |
| `plot_annotation_summary()` | Comprehensive summary plot |

### utils.py

Utility functions:

| Function | Description |
|----------|-------------|
| `create_test_data()` | Generate test data |
| `prepare_data_for_celltypist()` | Prepare AnnData |
| `get_model_catalog()` | Get model catalog |
| `recommend_model()` | Recommend model by tissue/species |
| `summarize_annotations()` | Summarize annotation results |
| `export_annotations()` | Export to CSV |
| `check_gene_overlap()` | Check gene overlap with model |
| `create_annotation_report()` | Generate text report |

## Available Models

### Human Models

| Model | Cell Types | Tissue | Use Case |
|-------|-----------|--------|----------|
| **Immune_All_Low** | 28 | Immune | General immune, broad categories |
| **Immune_All_High** | 98 | Immune | Detailed immune subtypes |
| **Cells_Intestinal_Training** | 56 | Intestine | Colon/small intestine epithelial |
| **Cells_Lung_Airway_Training** | 38 | Lung | Airway epithelial cells |
| **COVID19_Immune_Landscape** | - | Blood | COVID-specific immune states |

### Mouse Models

| Model | Cell Types | Use Case |
|-------|-----------|----------|
| **NLP_Mouse_Immune** | 22 | Mouse immune annotation |

## Input Data Format

### Required

```python
# AnnData with:
# - log-normalized expression data
# - Gene symbols (not ENSEMBL IDs)
# - Optional: UMAP coordinates for visualization

import scanpy as sc

# Load data
adata = sc.read_h5ad("your_data.h5ad")

# Ensure log-normalized data
sc.pp.normalize_total(adata, target_sum=1e4)
sc.pp.log1p(adata)
```

### From Raw Counts

```python
# Normalize raw counts
adata = sc.read_10x_mtx("path/to/counts/")
adata = prepare_data_for_celltypist(adata, normalize=True, log_transform=True)
```

## Output Data

| Output | Description |
|--------|-------------|
| `celltypist_label` | Predicted cell type labels |
| `celltypist_conf_score` | Confidence scores |
| `predicted_labels` | Individual predictions |
| `majority_voting` | Majority voting results |
| `over_clustering` | Over-clustering assignments |
| `celltypist_label_filtered` | Filtered labels (if filtered) |

## Examples

### Minimal Example

See `examples/minimal_example.py` for a basic workflow.

### Advanced Example

See `examples/advanced_example.py` for comprehensive analysis including:
- Model selection and comparison
- Custom over-clustering
- Multiple confidence thresholds
- Comprehensive visualization
- Custom model training example

## Testing

Run unit tests:

```bash
cd skills/bio-single-cell-annotation-celltypist
python tests/test_celltypist.py
```

Or with pytest:

```bash
pytest tests/test_celltypist.py -v
```

## Documentation

- **SKILL.md**: Comprehensive documentation with workflow, parameters, and error handling
- **usage-guide.md**: Step-by-step guide with code examples
- **examples/**: Working example scripts

## Best Practices

1. **Use majority voting** for more robust predictions
2. **Filter by confidence** (threshold 0.5) to remove uncertain assignments
3. **Match tissue type** to appropriate model
4. **Validate with marker genes** for quality control
5. **Check gene overlap** to ensure data compatibility

## References

1. Domínguez Conde et al. (2022). Cross-tissue immune cell analysis reveals tissue-specific features in humans. *Science*, 376, eabl5197.
2. CellTypist documentation: https://www.celltypist.org/
3. GitHub: https://github.com/Teichlab/celltypist

## License

This skill wrapper follows the same license as CellTypist (MIT).
