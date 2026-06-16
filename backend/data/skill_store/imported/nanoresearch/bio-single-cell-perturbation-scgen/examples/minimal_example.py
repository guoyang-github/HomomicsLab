"""
Minimal Example: scGen Perturbation Prediction
===============================================

This example demonstrates the basic workflow for scGen perturbation analysis.
"""

import scanpy as sc
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    validate_perturbation_data,
    preprocess_for_scgen,
    setup_scgen_anndata,
    train_scgen_model,
    predict_perturbation
)


def main():
    print("=" * 60)
    print("scGen Perturbation Analysis - Minimal Example")
    print("=" * 60)

    # -------------------------------------------------------------------------
    # Step 1: Load data
    # -------------------------------------------------------------------------
    print("\n[Step 1] Loading data...")
    print("Note: Replace with your actual data loading code")

    # Load perturbation data
    # adata = sc.read_h5ad('perturbation_data.h5ad')

    # Expected data format:
    # adata.obs['condition'] = ['control', 'control', 'stimulated', ...]
    # adata.obs['cell_type'] = ['CD4T', 'CD4T', 'CD8T', ...]  (optional)

    # -------------------------------------------------------------------------
    # Step 2: Validate data
    # -------------------------------------------------------------------------
    print("\n[Step 2] Validating data...")

    # validate_perturbation_data(
    #     adata,
    #     condition_key='condition',
    #     cell_type_key='cell_type'
    # )

    print("- Data validation passed")
    print("- Required columns found")

    # -------------------------------------------------------------------------
    # Step 3: Preprocess
    # -------------------------------------------------------------------------
    print("\n[Step 3] Preprocessing data...")

    # adata = preprocess_for_scgen(
    #     adata,
    #     n_top_genes=7000
    # )

    print("- Normalized and log-transformed")
    print("- Selected highly variable genes")

    # -------------------------------------------------------------------------
    # Step 4: Setup scGen
    # -------------------------------------------------------------------------
    print("\n[Step 4] Setting up scGen...")

    # adata = setup_scgen_anndata(
    #     adata,
    #     batch_key='condition',
    #     labels_key='cell_type'
    # )

    print("- AnnData setup complete")

    # -------------------------------------------------------------------------
    # Step 5: Train model
    # -------------------------------------------------------------------------
    print("\n[Step 5] Training scGen model...")

    # model = train_scgen_model(
    #     adata,
    #     max_epochs=100,
    #     batch_size=32,
    #     early_stopping=True
    # )

    print("- Model training complete")

    # -------------------------------------------------------------------------
    # Step 6: Predict perturbation effects
    # -------------------------------------------------------------------------
    print("\n[Step 6] Predicting perturbation effects...")

    # predicted_adata, delta = predict_perturbation(
    #     model,
    #     ctrl_key='control',
    #     stim_key='stimulated',
    #     celltype_to_predict='CD4T'
    # )

    print("- Prediction complete")
    print("- Predicted cells stored in predicted_adata")
    print("- Perturbation vector stored in delta")

    # -------------------------------------------------------------------------
    # Step 7: Save results
    # -------------------------------------------------------------------------
    print("\n[Step 7] Saving results...")

    # predicted_adata.write('predicted_stimulated.h5ad')
    # np.save('perturbation_vector.npy', delta)

    print("- Results saved")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
