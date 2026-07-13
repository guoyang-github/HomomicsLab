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

WS = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/backend/data/workspaces/b14_test'
INPUT = os.path.join(WS, 'data', 'PA12_small.h5ad')
OUT = os.path.join(WS, 'celltypist_results')
os.makedirs(OUT, exist_ok=True)
MODEL = 'Immune_All_Low.pkl'
CONF = 0.5

sc.settings.verbosity = 1
print('Loading:', INPUT)
adata = sc.read_h5ad(INPUT)
print('Raw shape:', adata.shape)
print('var_names head:', list(adata.var_names[:10]))
print('obs columns:', list(adata.obs.columns))
print('layers:', list(adata.layers.keys()))

# Prepare log-normalized data (full gene set, no HVG subsetting before annotation)
adata = prepare_data_for_celltypist(adata, normalize=True, target_sum=1e4,
                                    log_transform=True, highly_variable_genes=False)

val = validate_celltypist_input(adata)
print('Validation:', json.dumps({k:v for k,v in val.items() if k!='warnings'}, default=str))
for w in val.get('warnings', []):
    print('WARNING:', w)

# Load model and check gene overlap
model = load_celltypist_model(MODEL)
overlap = check_gene_overlap(adata, model)
with open(os.path.join(OUT, 'gene_overlap.json'), 'w') as f:
    json.dump(overlap, f, indent=2, default=str)
print('Overlap fraction:', round(overlap['overlap_fraction'], 3))

# Ensure Leiden clusters for majority voting
if 'leiden' not in adata.obs.columns:
    print('Computing neighbors + leiden for majority voting')
    hv = adata.copy()
    sc.pp.highly_variable_genes(hv, n_top_genes=min(2000, hv.n_vars))
    sc.pp.pca(hv, use_highly_variable=True)
    sc.pp.neighbors(hv)
    sc.tl.leiden(hv, resolution=0.5, key_added='leiden')
    adata.obs['leiden'] = hv.obs['leiden'].reindex(adata.obs.index).values
    # also keep a umap for convenience
    try:
        sc.tl.umap(hv)
        adata.obsm['X_umap'] = hv.obsm['X_umap']
    except Exception as e:
        print('UMAP skipped:', e)
else:
    print('Using existing leiden clusters')

# Run CellTypist
predictions = celltypist.annotate(
    adata, model=model, mode='best match',
    majority_voting=True, over_clustering='leiden')

# Capture matrices before to_adata
predictions.probability_matrix.to_csv(os.path.join(OUT, 'probability_matrix.csv'))
predictions.decision_matrix.to_csv(os.path.join(OUT, 'decision_matrix.csv'))
try:
    freq_mv = predictions.summary_frequency(by='majority_voting')
    freq_pl = predictions.summary_frequency(by='predicted_labels')
    freq_mv.to_csv(os.path.join(OUT, 'summary_frequency_majority_voting.csv'))
    freq_pl.to_csv(os.path.join(OUT, 'summary_frequency_predicted_labels.csv'))
except Exception as e:
    print('summary_frequency skipped:', e)

# Add predictions to AnnData (convenience celltypist_label column)
adata = add_predictions_to_adata(predictions, prefix='celltypist_')
adata = filter_by_confidence(adata, conf_col='celltypist_conf_score',
                             label_col='celltypist_label', threshold=CONF)

# Summary + exports
summary = summarize_annotations(adata)
summary.to_csv(os.path.join(OUT, 'annotation_summary.csv'), index=False)
print(summary.to_string(index=False))
export_annotations(adata, os.path.join(OUT, 'annotations.csv'))
create_annotation_report(adata, MODEL, os.path.join(OUT, 'annotation_report.txt'))

# Model info
info = {
    'model': MODEL,
    'n_cell_types': len(model.cell_types),
    'n_features': len(model.features),
    'cell_types': list(model.cell_types),
}
with open(os.path.join(OUT, 'model_info.json'), 'w') as f:
    json.dump(info, f, indent=2, default=str)

# Save annotated h5ad (handles nullable strings)
out_h5ad = os.path.join(OUT, 'PA12_small_celltypist_annotated.h5ad')
safe_write_h5ad(adata, out_h5ad)
print('DONE. Outputs in', OUT)
print('obs cols added:', [c for c in adata.obs.columns if 'celltypist' in c])
