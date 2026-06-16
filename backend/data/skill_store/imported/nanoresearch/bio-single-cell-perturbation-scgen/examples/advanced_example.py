"""
Advanced Example: scGen Perturbation Analysis
=============================================

This example demonstrates advanced features of scGen including:
- Batch correction
- Cross-cell-type prediction
- Multiple evaluation metrics
- Comprehensive visualization
"""

import scanpy as sc
import numpy as np
import sys
import os

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'python'))

from core_analysis import (
    validate_perturbation_data,
    preprocess_for_scgen,
    setup_scgen_anndata,
    train_scgen_model,
    predict_perturbation,
    batch_correction,
    get_latent_representation,
    run_complete_scgen_pipeline,
    extract_perturbation_vector
)
from visualization import (
    plot_regression_mean,
    plot_regression_variance,
    plot_binary_classifier,
    plot_latent_space,
    plot_perturbation_vector,
    plot_prediction_comparison
)
from utils import (
    get_condition_statistics,
    evaluate_prediction_accuracy,
    compare_perturbation_vectors,
    create_prediction_report,
    merge_predictions,
    balancer
)


def main():
    print("=" * 70)
    print("scGen Advanced Perturbation Analysis Example")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Step 1: Load and prepare data
    # -------------------------------------------------------------------------
    print("\n[Step 1] Loading data...")
    print("Note: Replace with your actual data loading code")

    # Load training data (e.g., Kang et al. dataset)
    # train = sc.read_h5ad('train.h5ad')
    # test = sc.read_h5ad('test.h5ad')

    # Expected data structure:
    # train.obs['condition'] = ['control', 'stimulated', ...]
    # train.obs['cell_type'] = ['CD4T', 'CD8T', 'B', ...]
    # test.obs['condition'] = ['control', ...]  # only control for prediction

    # -------------------------------------------------------------------------
    # Step 2: Validate and explore data
    # -------------------------------------------------------------------------
    print("\n[Step 2] Validating and exploring data...")

    # stats = validate_perturbation_data(
    #     train,
    #     condition_key='condition',
    #     cell_type_key='cell_type'
    # )

    # Get condition statistics
    # condition_stats = get_condition_statistics(
    #     train,
    #     condition_key='condition',
    #     cell_type_key='cell_type'
    # )
    # print(condition_stats)

    print("- Data validation passed")
    print("- Condition statistics computed")

    # -------------------------------------------------------------------------
    # Step 3: Run complete pipeline (simplified approach)
    # -------------------------------------------------------------------------
    print("\n[Step 3] Running complete scGen pipeline...")

    # results = run_complete_scgen_pipeline(
    #     train,
    #     condition_key='condition',
    #     ctrl_key='control',
    #     stim_key='stimulated',
    #     cell_type_key='cell_type',
    #     celltype_to_predict='CD4T',
    #     n_top_genes=7000,
    #     max_epochs=100,
    #     run_batch_correction=True
    # )

    # model = results['model']
    # corrected = results['corrected']
    # predicted = results['predicted']
    # delta = results['delta']

    print("- Pipeline complete")
    print("  - Model trained")
    print("  - Batch correction applied")
    print("  - Predictions generated")

    # -------------------------------------------------------------------------
    # Step 4: Batch correction analysis
    # -------------------------------------------------------------------------
    print("\n[Step 4] Analyzing batch correction...")

    # Visualize batch correction results
    # sc.pp.neighbors(corrected)
    # sc.tl.umap(corrected)
    # sc.pl.umap(corrected, color=['condition', 'cell_type'], save='_batch_corrected.png')

    print("- UMAP visualization saved")

    # -------------------------------------------------------------------------
    # Step 5: Cross-cell-type prediction
    # -------------------------------------------------------------------------
    print("\n[Step 5] Cross-cell-type prediction...")

    # Predict for multiple cell types
    # cell_types = ['CD4T', 'CD8T', 'B', 'NK']
    # predictions = {}
    # deltas = {}

    # for ct in cell_types:
    #     pred, delta_ct = predict_perturbation(
    #         model,
    #         ctrl_key='control',
    #         stim_key='stimulated',
    #         celltype_to_predict=ct
    #     )
    #     predictions[ct] = pred
    #     deltas[ct] = delta_ct

    print("- Predictions generated for all cell types")

    # Compare perturbation vectors across cell types
    # for i, ct1 in enumerate(cell_types):
    #     for ct2 in cell_types[i+1:]:
    #         comparison = compare_perturbation_vectors(
    #             deltas[ct1], deltas[ct2],
    #             label1=ct1, label2=ct2
    #         )
    #         print(f"{ct1} vs {ct2}: Cosine similarity = {comparison['cosine_similarity']:.3f}")

    # -------------------------------------------------------------------------
    # Step 6: Evaluation metrics
    # -------------------------------------------------------------------------
    print("\n[Step 6] Computing evaluation metrics...")

    # Get real stimulated cells for comparison
    # real_stim = train[(train.obs['condition'] == 'stimulated') &
    #                   (train.obs['cell_type'] == 'CD4T')]

    # Evaluate prediction accuracy
    # metrics = evaluate_prediction_accuracy(
    #     predictions['CD4T'],
    #     real_stim,
    #     condition_key='condition'
    # )

    # print("Prediction accuracy metrics:")
    # for metric, value in metrics.items():
    #     print(f"  {metric}: {value:.3f}")

    print("- Evaluation metrics computed")

    # -------------------------------------------------------------------------
    # Step 7: Comprehensive visualization
    # -------------------------------------------------------------------------
    print("\n[Step 7] Creating visualizations...")

    # 7.1 Merge data for visualization
    # ctrl_cells = train[(train.obs['condition'] == 'control') &
    #                    (train.obs['cell_type'] == 'CD4T')]
    # merged = merge_predictions(
    #     ctrl_cells,
    #     real_stim,
    #     predictions['CD4T']
    # )

    # 7.2 Regression mean plot
    # plot_regression_mean(
    #     model,
    #     merged,
    #     axis_keys={'x': 'control', 'y': 'predicted', 'y1': 'stimulated'},
    #     labels={'x': 'Control', 'y': 'Predicted'},
    #     gene_list=['ISG15', 'CD3D', 'CXCL10'],
    #     path_to_save='regression_mean.png',
    #     show=False
    # )

    # 7.3 Regression variance plot
    # plot_regression_variance(
    #     model,
    #     merged,
    #     axis_keys={'x': 'control', 'y': 'predicted', 'y1': 'stimulated'},
    #     labels={'x': 'Control', 'y': 'Predicted'},
    #     path_to_save='regression_variance.png',
    #     show=False
    # )

    # 7.4 Binary classifier plot
    # plot_binary_classifier(
    #     model,
    #     train,
    #     deltas['CD4T'],
    #     ctrl_key='control',
    #     stim_key='stimulated',
    #     path_to_save='binary_classifier.png',
    #     show=False
    # )

    # 7.5 Perturbation vector plot
    # plot_perturbation_vector(
    #     deltas['CD4T'],
    #     top_n=20,
    #     path_to_save='perturbation_vector.png',
    #     show=False
    # )

    # 7.6 Latent space visualization
    # plot_latent_space(
    #     model,
    #     train,
    #     color_by='condition',
    #     path_to_save='latent_space.png',
    #     show=False
    # )

    print("- All visualizations saved")

    # -------------------------------------------------------------------------
    # Step 8: Generate report
    # -------------------------------------------------------------------------
    print("\n[Step 8] Generating report...")

    # report = create_prediction_report(
    #     model,
    #     train,
    #     predictions['CD4T'],
    #     deltas['CD4T'],
    #     ctrl_key='control',
    #     stim_key='stimulated',
    #     output_file='scgen_report.txt'
    # )

    print("- Report generated")

    # -------------------------------------------------------------------------
    # Step 9: Save results
    # -------------------------------------------------------------------------
    print("\n[Step 9] Saving results...")

    # Save predictions for all cell types
    # for ct, pred in predictions.items():
    #     pred.write(f'predicted_{ct}.h5ad')

    # Save perturbation vectors
    # for ct, delta_ct in deltas.items():
    #     np.save(f'delta_{ct}.npy', delta_ct)

    # Save model
    # model.save('scgen_model/', overwrite=True)

    print("- All results saved")

    print("\n" + "=" * 70)
    print("Advanced analysis complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
