"""pertpy Perturbation Analysis Example."""

import pertpy as pt
import scanpy as sc
import numpy as np
import pandas as pd

# Create example data
np.random.seed(42)
n_cells = 500
n_genes = 1000

adata = sc.AnnData(
    X=np.random.lognormal(3, 1, (n_cells, n_genes)),
    obs=pd.DataFrame({
        'perturbation': np.random.choice(['control', 'gene_A', 'gene_B', 'gene_C'], n_cells),
        'replicate': np.random.choice(['rep1', 'rep2', 'rep3'], n_cells)
    }, index=[f"cell_{i}" for i in range(n_cells)]),
    var=pd.DataFrame(index=[f"GENE_{i}" for i in range(n_genes)])
)

print("pertpy Perturbation Analysis Example")
print("=" * 40)

# Preprocess
print("\n1. Preprocessing...")
sc.pp.filter_genes(adata, min_cells=3)
sc.pp.normalize_total(adata)
sc.pp.log1p(adata)
sc.pp.highly_variable_genes(adata, n_top_genes=500)

# Step 1: Pseudobulk DE
print("\n2. Pseudobulk Differential Expression...")
ps = pt.tl.PseudobulkSpace()
deseq2_results = ps.compute(
    adata,
    target_col="perturbation",
    groups_col="replicate"
)
print(f"DE results shape: {deseq2_results.shape}")

# Step 2: Augur classification
print("\n3. Augur perturbation classification...")
augur = pt.tl.Augur(estimator="random_forest")
adata = augur.load(adata, label_col="perturbation")
adata, results = augur.predict(adata)
print("Augur results added to adata.uns")

# Step 3: View Augur results
print("\n4. Augur results:")
if 'augur_results' in adata.uns:
    print(adata.uns['augur_results'].head())

# Step 4: Mixscape for CRISPR screens
print("\n5. Mixscape for genetic screens...")
# For CRISPR data with guide RNA information
# pt.tl.mixscape(
#     adata,
#     labels="guide_rna",
#     control="non-targeting",
#     layer="X_pert"
# )

print("\nNote: Mixscape requires guide RNA data")
