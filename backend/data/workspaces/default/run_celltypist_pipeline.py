import os, sys, json, warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
import scanpy as sc
import celltypist

SKILL = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-annotation-celltypist'
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'python'))
from utils import (prepare_data_for_celltypist, check_gene_overlap,
                   summarize_annotations, export_annotations,
                   safe_write_h5ad, create_annotation_report)
from core_analysis import (validate_celltypist_input, load_celltypist_model,
                           add_predictions_to_adata, filter_by_confidence)

WS = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/workspaces/default'
INPUT = os.path.join(WS, 'data', 'PA12_small.h5ad')
OUT = os.path.join(WS, 'outputs')
os.makedirs(OUT, exist_ok=True)
MODEL = 'Immune_All_Low.pkl'
CONF = 0.5

sc.settings.verbosity = 1
print('Loading:', INPUT, flush=True)
adata = sc.read_h5ad(INPUT)
print('Raw shape:', adata.shape, flush=True)
print('obs columns:', list(adata.obs.columns), flush=True)
print('layers:', list(adata.layers.keys()), flush=True)

adata = prepare_data_for_celltypist(adata, normalize=True, target_sum=1e4,
                                    log_transform=True, highly_variable_genes=False)

val = validate_celltypist_input(adata)
print('Validation:', json.dumps({k: v for k, v in val.items() if k != 'warnings'}, default=str), flush=True)

model = load_celltypist_model(MODEL)
overlap = check_gene_overlap(adata, model)
with open(os.path.join(OUT, 'gene_overlap.json'), 'w') as f:
    json.dump(overlap, f, indent=2, default=str)
print('Overlap fraction:', round(overlap['overlap_fraction'], 3), flush=True)

if 'leiden' not in adata.obs.columns:
    print('Computing neighbors + leiden for majority voting', flush=True)
    hv = adata.copy()
    sc.pp.highly_variable_genes(hv, n_top_genes=min(2000, hv.n_vars))
    sc.pp.pca(hv, use_highly_variable=True)
    sc.pp.neighbors(hv)
    sc.tl.leiden(hv, resolution=0.5, key_added='leiden')
    adata.obs['leiden'] = hv.obs['leiden'].reindex(adata.obs.index).values
    try:
        sc.tl.umap(hv)
        adata.obsm['X_umap'] = hv.obsm['X_umap']
    except Exception as e:
        print('UMAP skipped:', e, flush=True)
else:
    print('Using existing leiden clusters', flush=True)

print('Running celltypist.annotate ...', flush=True)
predictions = celltypist.annotate(
    adata, model=model, mode='best match',
    majority_voting=True, over_clustering='leiden')

predictions.probability_matrix.to_csv(os.path.join(OUT, 'probability_matrix.csv'))
predictions.decision_matrix.to_csv(os.path.join(OUT, 'decision_matrix.csv'))
try:
    predictions.summary_frequency(by='majority_voting').to_csv(
        os.path.join(OUT, 'summary_frequency_majority_voting.csv'))
    predictions.summary_frequency(by='predicted_labels').to_csv(
        os.path.join(OUT, 'summary_frequency_predicted_labels.csv'))
except Exception as e:
    print('summary_frequency skipped:', e, flush=True)

adata = add_predictions_to_adata(predictions, prefix='celltypist_')
adata = filter_by_confidence(adata, conf_col='celltypist_conf_score',
                             label_col='celltypist_label', threshold=CONF)

summary = summarize_annotations(adata)
summary.to_csv(os.path.join(OUT, 'annotation_summary.csv'), index=False)
print(summary.to_string(index=False), flush=True)
export_annotations(adata, os.path.join(OUT, 'annotations.csv'))
create_annotation_report(adata, MODEL, os.path.join(OUT, 'annotation_report.txt'))

info = {'model': MODEL, 'n_cell_types': len(model.cell_types),
        'n_features': len(model.features), 'cell_types': list(model.cell_types)}
with open(os.path.join(OUT, 'model_info.json'), 'w') as f:
    json.dump(info, f, indent=2, default=str)

out_h5ad = os.path.join(OUT, 'PA12_small_celltypist_annotated.h5ad')
safe_write_h5ad(adata, out_h5ad)
print('DONE. Outputs in', OUT, flush=True)
print('obs cols added:', [c for c in adata.obs.columns if 'celltypist' in c], flush=True)
