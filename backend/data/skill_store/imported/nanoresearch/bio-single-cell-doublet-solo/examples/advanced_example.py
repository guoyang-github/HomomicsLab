#!/usr/bin/env python
"""
Advanced Example: SOLO Doublet Detection

This example demonstrates advanced features including:
- Multi-batch processing
- Threshold optimization
- Comparison with other methods
- Detailed visualization
"""

import scanpy as sc
import pandas as pd
import numpy as np
import sys
sys.path.insert(0, '../scripts/python')

from core_analysis import (
    train_scvi_model, train_solo_model, predict_doublets,
    run_solo_per_batch, add_predictions_to_adata
)
from visualization import (
    plot_doublet_summary, plot_batch_comparison,
    plot_training_history,
    plot_doublet_score_boxplot, plot_agreement_heatmap
)
from utils import (
    preprocess_for_solo, estimate_optimal_threshold,
    optimize_threshold_range, estimate_expected_doublet_rate,
    compare_predictions
)

# ==============================================================================
# Example 1: Custom scVI and SOLO Training
# ==============================================================================

print("="*60)
print("Example 1: Custom Training with Specific Parameters")
print("="*60)

# Load data
adata = sc.read_h5ad("your_data.h5ad")

# Preprocess
adata = preprocess_for_solo(
    adata,
    min_genes=200,
    min_cells=3,
    max_genes=8000,      # Remove high gene count outliers
    max_counts=50000,    # Remove high count outliers
    mt_threshold=20      # Remove high mitochondrial % cells
)

# Train scVI with custom parameters
vae = train_scvi_model(
    adata,
    batch_key='batch',
    n_latent=20,              # Larger latent space
    n_hidden=256,             # Larger hidden layers
    n_layers=2,               # Fewer but larger layers
    max_epochs=400,
    early_stopping_patience=60,
    learning_rate=1e-3,
    use_gpu=True,
    verbose=True
)

# Train SOLO with custom parameters
solo = train_solo_model(
    vae,
    doublet_ratio=3,          # More simulated doublets
    max_epochs=150,
    early_stopping_patience=40,
    early_stopping_min_delta=0.001,
    learning_rate=5e-4,       # Lower learning rate
    use_gpu=True,
    verbose=True
)

# Plot training histories
plot_training_history(vae, title='scVI Training History', save_path='scvi_history.pdf')
plot_training_history(solo, title='SOLO Training History', save_path='solo_history.pdf')

# Predict
predictions = predict_doublets(solo, soft=True)
predictions['prediction'] = (predictions['doublet'] > 0.5).astype(int)
predictions['prediction_label'] = predictions['prediction'].map({0: 'singlet', 1: 'doublet'})

print(f"\nPredictions: {len(predictions)} cells")
print(predictions['prediction_label'].value_counts())

# Save model for later use
solo.save('./solo_model', overwrite=True, save_anndata=False)

# ==============================================================================
# Example 2: Threshold Optimization
# ==============================================================================

print("\n" + "="*60)
print("Example 2: Threshold Optimization")
print("="*60)

# Try multiple thresholds
threshold_comparison = optimize_threshold_range(
    predictions,
    thresholds=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
)
print("\nThreshold comparison:")
print(threshold_comparison)

# Estimate optimal threshold
optimal_thresh = estimate_optimal_threshold(
    predictions,
    expected_doublet_rate=None,  # Auto-estimate
    method='otsu'
)
print(f"\nOptimal threshold (Otsu): {optimal_thresh:.3f}")

# Compare to expected rate
expected_rate = estimate_expected_doublet_rate(adata.n_obs, method='10x')
n_total = len(predictions)
n_predicted = (predictions['doublet'] > 0.5).sum()
predicted_rate = n_predicted / n_total
print(f"Expected doublet rate: {expected_rate*100:.2f}%")
print(f"Predicted doublet rate: {predicted_rate*100:.2f}%")
print(f"Difference: {(predicted_rate - expected_rate)*100:.2f}%")

# ==============================================================================
# Example 3: Multi-Batch Processing
# ==============================================================================

print("\n" + "="*60)
print("Example 3: Per-Batch Doublet Detection")
print("="*60)

# If data has multiple batches, process each separately
if 'batch' in adata.obs.columns:
    batch_results = run_solo_per_batch(
        adata,
        batch_key='batch',
        scvi_epochs=400,
        solo_epochs=100,
        doublet_ratio=2,
        use_gpu=True,
        verbose=True
    )

    # Visualize batch comparison
    plot_batch_comparison(batch_results, save_path='batch_comparison.pdf')

    # Combine predictions
    all_predictions = pd.concat(batch_results.values())
    print(f"\nCombined predictions: {len(all_predictions)} cells")

# ==============================================================================
# Example 4: Advanced Visualization
# ==============================================================================

print("\n" + "="*60)
print("Example 4: Advanced Visualization")
print("="*60)

# Comprehensive summary plot
plot_doublet_summary(
    predictions,
    threshold=0.5,
    title="SOLO Doublet Detection Summary",
    save_path='solo_summary.pdf'
)

# Box plot by batch
if 'batch' in adata.obs.columns:
    predictions_with_batch = predictions.copy()
    predictions_with_batch['batch'] = adata.obs['batch']

    plot_doublet_score_boxplot(
        predictions_with_batch,
        groupby='batch',
        save_path='doublet_score_by_batch.pdf'
    )

# ==============================================================================
# Example 5: Comparison with Other Methods
# ==============================================================================

print("\n" + "="*60)
print("Example 5: Comparing with Scrublet")
print("="*60)

# Run Scrublet for comparison
from scrublet import Scrublet

scrub = Scrublet(adata.X)
doublet_scores_scrublet, predicted_doublets = scrub.scrub_doublets()

scrublet_preds = pd.DataFrame({
    'scrublet_score': doublet_scores_scrublet,
    'scrublet_prediction': predicted_doublets
}, index=adata.obs_names)

# Compare methods
comparison = compare_predictions(
    predictions,
    scrublet_preds,
    other_name='scrublet',
    solo_threshold=0.5,
    other_threshold=0.5
)

print(f"\nSOLO vs Scrublet Agreement: {comparison['agreement']:.2%}")
print(f"Both doublet: {comparison['both_doublet']}")
print(f"Both singlet: {comparison['both_singlet']}")
print(f"SOLO only: {comparison['solo_only']}")
print(f"Scrublet only: {comparison['scrublet_only']}")

# Create comparison DataFrame
comparison_df = pd.DataFrame({
    'solo': predictions['prediction_label'],
    'scrublet': scrublet_preds['scrublet_prediction'].map({True: 'doublet', False: 'singlet'})
})

# Agreement heatmap
plot_agreement_heatmap(
    comparison_df,
    method_columns=['solo', 'scrublet'],
    save_path='method_agreement.pdf'
)

# ==============================================================================
# Example 6: Export and Reporting
# ==============================================================================

print("\n" + "="*60)
print("Example 6: Export Results")
print("="*60)

# Export predictions
predictions.to_csv('solo_predictions.csv')
predictions.to_csv('solo_predictions.tsv', sep='\t')

# Add to AnnData and save
add_predictions_to_adata(adata, predictions, prefix='solo')
adata.write_h5ad('data_with_solo_predictions.h5ad')

# Filter and save clean data
adata_clean = adata[adata.obs['solo_prediction'] == 'singlet'].copy()
adata_clean.write_h5ad('data_filtered.h5ad')

print(f"\nOriginal: {adata.n_obs} cells")
print(f"Filtered: {adata_clean.n_obs} cells")
print(f"Removed: {adata.n_obs - adata_clean.n_obs} doublets")

print("\nAdvanced analysis complete!")
