"""Basic Solo doublet detection example."""

import scanpy as sc
from scvi.external import SOLO
import scvi
import numpy as np
import pandas as pd

# Create example data
np.random.seed(42)
adata = sc.AnnData(
    X=np.random.poisson(2, (500, 1000)),
    obs=pd.DataFrame(index=[f"cell_{i}" for i in range(500)]),
    var=pd.DataFrame(index=[f"GENE_{i}" for i in range(1000)])
)

print("Solo Doublet Detection Example")
print("=" * 40)

# Preprocess
print("\n1. Preprocessing data...")
sc.pp.filter_cells(adata, min_genes=3)
sc.pp.filter_genes(adata, min_cells=3)
# Note: SOLO requires raw counts. Do NOT normalize or log-transform.

# Setup scVI model
print("\n2. Training scVI model...")
scvi.model.SCVI.setup_anndata(adata)

vae = scvi.model.SCVI(adata, n_layers=2, n_latent=30)
vae.train()

# Run Solo
print("\n3. Running Solo...")
solo_model = SOLO.from_scvi_model(vae, adata=adata)
solo_model.train()

# Predict (soft=False returns labels; soft=True returns probabilities)
print("\n4. Predicting doublets...")
predictions = solo_model.predict(soft=False)
predictions_df = pd.DataFrame({'is_doublet': (predictions == 'doublet').astype(int)})

# Also get probability scores for reference
predictions_prob = solo_model.predict(soft=True)

# Add to AnnData
adata.obs['solo_prediction'] = predictions_df['is_doublet'].values
adata.obs['solo_score'] = predictions_prob['doublet'].values

# Results
n_doublets = sum(adata.obs['solo_prediction'] == 1)
print(f"\nDetected {n_doublets} potential doublets")

# Filter
print("\n5. Filtering doublets...")
adata_filtered = adata[adata.obs['solo_prediction'] == 0].copy()
print(f"   Cells before: {adata.n_obs}")
print(f"   Cells after: {adata_filtered.n_obs}")
