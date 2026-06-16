# bio-spatial-transcriptomics-integration-spclue

Spatial domain identification and multi-slice integration using cross-view contrastive learning (spCLUE).

## Overview

spCLUE is a deep learning method for analyzing spatial transcriptomics data that:

- **Identifies spatial domains** in single tissue sections using graph contrastive learning
- **Integrates multiple slices** with built-in batch correction
- **Combines spatial and expression information** through multi-view learning
- **Supports large-scale datasets** with batch training mode

## Architecture

```
Input Data (Gene Expression + Spatial Coordinates)
        |
        v
[Preprocessing] --> HVG selection, normalization, PCA
        |
        v
[Graph Construction]
   |            |
   v            v
Spatial Graph  Expression Graph
(KNN from      (KNN from PCA)
coordinates)
   |            |
   v            v
[Graph Convolutional Networks]
   |            |
   v            v
Spatial View   Expression View
Embeddings     Embeddings
   |            |
   +------+------+
          |
          v
   [Attention Fusion]
          |
          v
   Unified Embeddings
          |
          v
   [Clustering] --> Spatial Domains
```

## Key Features

### 1. Multi-View Graph Construction
- **Spatial view**: Captures tissue structure from physical coordinates
- **Expression view**: Captures gene expression similarity

### 2. Cross-View Contrastive Learning
- **Instance-level contrast**: Encourages consistency between spatial and expression views
- **Cluster-level contrast**: Learns discriminative cluster assignments
- **Reconstruction loss**: Preserves gene expression information

### 3. Batch Correction (Multi-Slice)
- Batch embedding module for domain adaptation
- Handles technical variation across tissue sections

### 4. Flexible Clustering
- mclust: Probabilistic clustering (requires R)
- Leiden: Graph-based clustering
- k-means: Classic centroid-based clustering

## Quick Start

> **Note:** `sc.pl.spatial()` was removed in scanpy 1.12+. Use `sq.pl.spatial_scatter()` from squidpy instead.  
> Parameter mapping: `spot_size` → `size`. `alpha_img`, `bw`, and `scale_factor` are not supported in squidpy.
```python
from scripts import spCLUE, preprocess, prepare_graph, clustering, fix_seed
from sklearn.decomposition import PCA
import scanpy as sc
import torch

# 1. Load data
adata = sc.read_h5ad("your_data.h5ad")

# 2. Preprocess
adata = preprocess(adata, hvgNumber=2000)

# 3. PCA
pca = PCA(n_components=200, random_state=0)
input_data = pca.fit_transform(adata.X)

# 4. Build graphs
graph_dict = {
    "spatial": prepare_graph(adata, key="spatial", n_neighbors=12),
    "expr": prepare_graph(adata, key="expr", n_neighbors=12, n_comps=50)
}

# 5. Train spCLUE
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model = spCLUE(
    input_data=input_data,
    graph_dict=graph_dict,
    n_clusters=12,
    epochs=500,
    device=device,
    random_seed=42
)

pred_labels, embeddings = model.train()

# 6. Store results and cluster
adata.obsm['spCLUE'] = embeddings
adata.obs['pred'] = pred_labels
adata = clustering(adata, n_clusters=12, key='spCLUE', cluster_methods='mclust')

# 7. Visualize
sq.pl.spatial_scatter(adata, color=['mclust'])
```

## Directory Structure

```
bio-spatial-transcriptomics-integration-spclue/
├── SKILL.md              # Detailed skill documentation
├── usage-guide.md        # Usage guide with examples
├── requirements.txt      # Python dependencies
├── scripts/              # Core implementation
│   ├── __init__.py
│   ├── spclue.py        # Main model class
│   ├── network.py       # Neural network architectures
│   ├── loss.py          # Loss functions
│   ├── preprocess.py    # Data preprocessing
│   └── utils.py         # Utility functions
├── examples/             # Example workflows
│   ├── single_slice_analysis.py
│   └── multi_slice_integration.py
└── tests/                # Unit tests
    └── test_spclue.py
```

## Examples

### Single-Slice Analysis

```bash
python examples/single_slice_analysis.py data.h5ad -n 12 -o results.h5ad
```

### Multi-Slice Integration

```bash
python examples/multi_slice_integration.py \
    slice1.h5ad slice2.h5ad slice3.h5ad \
    -n slice1 slice2 slice3 \
    -c 12 \
    -o integrated.h5ad
```

## Testing

```bash
python -m pytest tests/test_spclue.py
```

Or run directly:

```bash
python tests/test_spclue.py
```

## Requirements

- Python >= 3.8
- PyTorch >= 1.8.0
- scanpy >= 1.9.0
- anndata >= 0.8.0
- numpy >= 1.22.0
- scikit-learn >= 1.1.0
- scipy >= 1.8.0
- rpy2 >= 3.4.0 (for mclust)
- R >= 4.0.0 with mclust package

## Citation

If you use spCLUE in your research, please cite:

```
spCLUE: A Contrastive Learning Approach to Unified Spatial
Transcriptomics Analysis Across Single-Slice and Multi-Slice Data
```

Original implementation: https://github.com/liuchangyzu/spCLUE

## License

This implementation follows the original spCLUE license.
