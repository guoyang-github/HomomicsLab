import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist/scripts/python')
import numpy as np, pandas as pd, anndata as ad
from core_analysis import annotate_cells, add_predictions_to_adata, filter_by_confidence
from utils import prepare_data_for_celltypist, summarize_annotations, export_annotations

inp = '/mnt/c/Users/guoyang/Desktop/data/PA12_small.h5ad'
outdir = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/celltypist_small/outputs'
model = 'Immune_All_Low.pkl'
target = 'all_celltype'

adata = ad.read_h5ad(inp)
adata = prepare_data_for_celltypist(adata, layer='counts', normalize=True, target_sum=1e4, log_transform=True)

preds = annotate_cells(adata, model=model, majority_voting=True, mode='best match')
adata = add_predictions_to_adata(preds, insert_labels=True, insert_conf=True, prefix='celltypist_')
adata = filter_by_confidence(adata, conf_col='celltypist_conf_score', label_col='celltypist_predicted_labels',
                             threshold=0.5, unassigned_label='Unassigned_lowconf')

summ = summarize_annotations(adata, label_col='celltypist_predicted_labels', conf_col='celltypist_conf_score')
summ.to_csv(os.path.join(outdir, 'annotation_summary.csv'))
export_annotations(adata, os.path.join(outdir, 'annotations.csv'), label_col='celltypist_predicted_labels', conf_col='celltypist_conf_score')

# Compare vs ground truth
gt = adata.obs[target].astype(str)
pl = adata.obs['celltypist_predicted_labels'].astype(str)
conf = pd.crosstab(gt, pl)
conf.to_csv(os.path.join(outdir, 'confusion.csv'))
exact = (gt == pl).mean()

report = []
report.append(f'Model: {model}')
report.append(f'Cells: {adata.n_obs}, Genes: {adata.n_vars}')
report.append(f'Majority voting: True; mode: best match')
report.append(f'Exact label match accuracy vs {target}: {exact:.4f}')
report.append(f'Predicted label set ({pl.nunique()}): {sorted(pl.unique())}')
report.append(f'Ground truth label set ({gt.nunique()}): {sorted(gt.unique())}')
report.append('NOTE: granularity may differ between model labels and ground truth; see confusion.csv for raw mapping.')
report.append('')
report.append('Prediction counts:')
report.append(pl.value_counts().to_string())
report.append('')
report.append('Mean confidence by predicted label:')
report.append(summ.to_string())
with open(os.path.join(outdir, 'report.txt'), 'w') as f:
    f.write('\n'.join(report))

adata.write_h5ad(os.path.join(outdir, 'annotated.h5ad'))
print('DONE exact_accuracy=%.4f' % exact)
