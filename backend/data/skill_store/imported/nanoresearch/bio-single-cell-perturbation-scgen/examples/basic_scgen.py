"""Basic scGen perturbation modeling example."""

import scanpy as sc
import pertpy as pt

# Load your Perturb-seq data
# adata = sc.read_h5ad("perturb_seq_data.h5ad")

print("scGen Perturbation Modeling")
print("=" * 40)

print("\n1. Preprocess data:")
# sc.pp.normalize_total(adata, target_sum=1e4)
# sc.pp.log1p(adata)
# sc.pp.highly_variable_genes(adata, n_top_genes=2000)

print("\n2. Setup scGen:")
# pt.tl.Scgen.setup_anndata(
#     adata,
#     batch_key='perturbation',
#     labels_key='cell_type'
# )

print("\n3. Train model:")
# model = pt.tl.Scgen(adata)
# model.train(max_epochs=100, batch_size=32)

print("\n4. Batch correction:")
# corrected = model.batch_removal()

print("\n5. Predict perturbation effects:")
# predicted, delta = model.predict(
#     ctrl_key='control',
#     stim_key='treatment',
#     celltype_to_predict='T_cell'
# )

print("\nNote: Uncomment code above to run actual analysis")
print("Requires pertpy package and sufficient training data")
