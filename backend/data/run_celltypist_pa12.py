#!/usr/bin/env python3
"""CellTypist annotation of PA12_sc.h5ad immune cells + comparison with all_celltype labels."""
import sys, os, json, warnings
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
import numpy as np
import pandas as pd
import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from core_analysis import (
    validate_celltypist_input, get_available_models, download_celltypist_model,
    annotate_cells, add_predictions_to_adata, filter_by_confidence, check_gene_overlap
)
from utils import (
    prepare_data_for_celltypist, summarize_annotations, export_annotations,
    safe_write_h5ad, create_annotation_report, compare_with_reference
)
from visualization import (
    plot_celltypist_dotplot, plot_confidence_distribution, plot_celltype_proportions,
    plot_top_celltypes, plot_reference_comparison, plot_prediction_heatmap
)

warnings.filterwarnings('ignore')

INPUT = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/raw/default/PA12_sc.h5ad'
OUTDIR = 'outputs'
MODEL = 'Immune_All_Low.pkl'
REF_COL = 'all_celltype'
os.makedirs(OUTDIR, exist_ok=True)

log_lines = []
def log(msg):
    print(msg, flush=True)
    log_lines.append(str(msg))

log('='*70)
log('Step 1: Load data')
adata = sc.read_h5ad(INPUT)
log(f'  AnnData: {adata.n_obs} cells x {adata.n_vars} genes')
log(f'  obs columns: {list(adata.obs.columns)}')
assert REF_COL in adata.obs.columns, f'{REF_COL} not in obs'
log(f'  Reference label {REF_COL}: {adata.obs[REF_COL].nunique()} categories')
log(str(adata.obs[REF_COL].value_counts()))

log('='*70)
log('Step 2: Validate input')
val = validate_celltypist_input(adata, check_normalized=True)
log(f'  valid={val["valid"]}, warnings={val["warnings"]}, errors={val["errors"]}')

log('='*70)
log('Step 3: Check existing normalization state')
x = adata.X
sample = x[: min(2000, adata.n_obs)]
if hasattr(sample, 'toarray'):
    sample = sample.toarray()
maxv = float(np.max(sample))
log(f'  max value in X sample = {maxv:.4f}')

log('='*70)
log('Step 4: Prepare log-normalized data for CellTypist')
adata_ct = prepare_data_for_celltypist(adata.copy(), normalize=True, target_sum=1e4, log_transform=True)
x2 = adata_ct.X[: min(2000, adata_ct.n_obs)]
if hasattr(x2, 'toarray'):
    x2 = x2.toarray()
log(f'  After prep: max={float(np.max(x2)):.4f} (log-normalized expected)')

log('='*70)
log('Step 5: Download model and check gene overlap')
download_celltypist_model(MODEL)
models_df = get_available_models()
log(f'  Available models: {len(models_df)}')

import celltypist
mdl = celltypist.models.Model.load(MODEL)
ov = check_gene_overlap(adata_ct, mdl)
log(f'  Model genes: {ov["n_model_genes"]}, overlap: {ov["n_overlap"]} ({ov["pct_overlap"]:.1f}%)')

log('='*70)
log('Step 6: Run CellTypist annotation (majority voting)')
predictions = annotate_cells(adata_ct, model=MODEL, majority_voting=True, mode='best match', p_thres=0.5)
log(f'  Prediction columns: {list(predictions.predicted_labels.columns)}')
adata = add_predictions_to_adata(predictions, insert_labels=True, insert_conf=True, insert_conf_by='majority_voting')
log(f'  adata.obs new columns: {[c for c in adata.obs.columns if "celltypist" in c or "majority" in c]}')

log('='*70)
log('Step 7: Summarize annotations')
summary = summarize_annotations(adata, label_col='majority_voting', conf_col='conf_score')
log(f'  Label column: {summary["label_col"]}, n unique labels: {summary["n_labels"]}')
log('  Label counts:\n' + summary['label_counts'].to_string())
if 'conf_summary' in summary and summary['conf_summary'] is not None:
    log('  Confidence summary:\n' + str(summary['conf_summary']))

log('='*70)
log('Step 8: Compare CellTypist majority_voting with reference all_celltype')
comp = compare_with_reference(adata, ref_col=REF_COL, pred_col='majority_voting', conf_col='conf_score')
for k in ['ari_all','nmi_all','ari_assigned','nmi_assigned','exact_match','n_assigned','n_total','pred_col','ref_col']:
    if k in comp:
        log(f'  {k}: {comp[k]}')
confusion = comp['confusion']
confusion.to_csv(os.path.join(OUTDIR, 'comparison_confusion_matrix.csv'))
comp['confusion_row_norm'].to_csv(os.path.join(OUTDIR, 'comparison_confusion_row_normalized.csv'))
if 'per_label_recall' in comp and comp['per_label_recall'] is not None:
    comp['per_label_recall'].to_csv(os.path.join(OUTDIR, 'comparison_per_label_recall.csv'))

metrics = {k: (float(v) if isinstance(v, (np.floating, float, np.integer, int)) else str(v))
           for k, v in comp.items() if k in ['ari_all','nmi_all','ari_assigned','nmi_assigned','exact_match','n_assigned','n_total']}
with open(os.path.join(OUTDIR, 'comparison_metrics.json'), 'w') as f:
    json.dump(metrics, f, indent=2)

log('='*70)
log('Step 9: Export annotation table')
export_annotations(adata, os.path.join(OUTDIR, 'celltypist_annotations.csv'), label_col='majority_voting', conf_col='conf_score')

log('='*70)
log('Step 10: Figures')
figdir = os.path.join(OUTDIR, 'figures')
os.makedirs(figdir, exist_ok=True)
plt.rcParams['figure.dpi'] = 120

try:
    ax = plot_celltypist_dotplot(predictions, use_as_reference=REF_COL, use_as_prediction='majority_voting',
                                 title='CellTypist vs all_celltype', figsize=(14, 10))
    plt.savefig(os.path.join(figdir, 'dotplot_pred_vs_ref.png'), bbox_inches='tight'); plt.close('all')
    log('  saved dotplot_pred_vs_ref.png')
except Exception as e:
    log(f'  dotplot failed: {e}')

try:
    plot_confidence_distribution(adata, conf_col='conf_score', label_col='majority_voting', figsize=(12, 6))
    plt.savefig(os.path.join(figdir, 'confidence_distribution.png'), bbox_inches='tight'); plt.close('all')
    log('  saved confidence_distribution.png')
except Exception as e:
    log(f'  conf dist failed: {e}')

try:
    plot_celltype_proportions(adata, label_col='majority_voting', figsize=(12, 6))
    plt.savefig(os.path.join(figdir, 'celltype_proportions.png'), bbox_inches='tight'); plt.close('all')
    log('  saved celltype_proportions.png')
except Exception as e:
    log(f'  proportions failed: {e}')

try:
    plot_top_celltypes(adata, label_col='majority_voting', top_n=20, figsize=(10, 8))
    plt.savefig(os.path.join(figdir, 'top_celltypes.png'), bbox_inches='tight'); plt.close('all')
    log('  saved top_celltypes.png')
except Exception as e:
    log(f'  top celltypes failed: {e}')

try:
    plot_reference_comparison(comp, figsize=(14, 12))
    plt.savefig(os.path.join(figdir, 'reference_comparison_heatmap.png'), bbox_inches='tight'); plt.close('all')
    log('  saved reference_comparison_heatmap.png')
except Exception as e:
    log(f'  ref comparison heatmap failed: {e}')

# UMAP if available
try:
    if 'X_umap' in adata.obsm:
        sc.pl.umap(adata, color=['majority_voting', REF_COL], legend_loc='on data', frameon=False, show=False)
        plt.savefig(os.path.join(figdir, 'umap_labels.png'), bbox_inches='tight', dpi=150); plt.close('all')
        log('  saved umap_labels.png')
    else:
        log('  no X_umap in obsm, skipping UMAP plot')
except Exception as e:
    log(f'  umap plot failed: {e}')

log('='*70)
log('Step 11: Write annotated h5ad and report')
safe_write_h5ad(adata, os.path.join(OUTDIR, 'PA12_sc_celltypist_annotated.h5ad'))
report_txt = create_annotation_report(adata, MODEL, output_file=os.path.join(OUTDIR, 'annotation_report.txt'),
                                      label_col='majority_voting', conf_col='conf_score')

with open(os.path.join(OUTDIR, 'run_log.txt'), 'w') as f:
    f.write('\n'.join(log_lines))

log('='*70)
log('DONE. Outputs written to ' + OUTDIR)
log('Key metrics: ' + json.dumps(metrics))
