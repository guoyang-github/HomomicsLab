import os, numpy as np, pandas as pd
OUT = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/celltypist_small/outputs'
GT = 'all_celltype'
ann = pd.read_csv(os.path.join(OUT, 'annotations.csv'), index_col=0)
pred_col = 'ct_majority_voting'

def coarse(lab):
    l = str(lab).lower()
    if 'cytotoxic t cell' in l or 'mait' in l or ('cd8' in l and 't cell' in l): return 'CD8T'
    if 'helper t cell' in l or ('cd4' in l and 't cell' in l): return 'CD4T'
    if 'nk' in l or 'natural killer' in l or 'ilc' in l: return 'NK'
    if 'plasma' in l: return 'Plasma'
    if 'b cell' in l or 'bcell' in l: return 'B'
    if any(k in l for k in ['macrophage','monocyte','dendritic',' dc','myeloid','mast']): return 'Myeloid'
    if 'ductal' in l or 'epithelial' in l: return 'Ductal'
    if 'stellate' in l: return 'Stellate'
    if 'endothelial' in l: return 'Endothelial'
    if 'platelet' in l or 'megakaryocyte' in l: return 'Platelet'
    if 'fibroblast' in l or 'caf' in l: return 'CAF'
    if 'endocrine' in l: return 'Endocrine'
    if 'schwann' in l: return 'Schwann'
    if 't cell' in l: return 'CD4T'
    return 'Unassigned'

ann['pred_coarse'] = ann[pred_col].map(coarse)
ann.to_csv(os.path.join(OUT, 'annotations.csv'))

y_true = ann[GT].astype(str).values
y_fine = ann[pred_col].astype(str).values
y_coarse = ann['pred_coarse'].values
acc_exact = float(np.mean(y_true == y_fine))
acc_coarse = float(np.mean(y_true == y_coarse))

pd.crosstab(pd.Series(y_true, name='true'), pd.Series(y_coarse, name='pred_coarse')).to_csv(os.path.join(OUT, 'confusion.csv'))

rows = []
for lab in sorted(set(y_true)):
    tp = int(((y_true == lab) & (y_coarse == lab)).sum())
    n = int((y_true == lab).sum()); pn = int((y_coarse == lab).sum())
    rows.append({'label': lab, 'n_true': n, 'recall': round(tp/n,4) if n else None, 'precision': round(tp/pn,4) if pn else None})
rep = pd.DataFrame(rows)
rep.to_csv(os.path.join(OUT, 'per_class_metrics.csv'), index=False)

with open(os.path.join(OUT, 'report.txt'), 'w') as f:
    f.write('CellTypist annotation report\nmodel: Immune_All_Low.pkl (98 fine-grained immune cell types)\n')
    f.write('input: /mnt/c/Users/guoyang/Desktop/data/PA12_small.h5ad\n')
    f.write(f'n_cells: {len(ann)}\nprediction column: {pred_col} (majority voting enabled, over-clustering resolution 5)\n')
    f.write(f'ground truth column: {GT} (coarse taxonomy: CD8T/CD4T/NK/B/Myeloid/...)\n')
    f.write('NOTE: model predicts fine-grained labels (e.g. "Tem/Trm cytotoxic T cells"); a biologically\n')
    f.write('      grounded coarse mapping was applied for comparison with the ground truth:\n')
    f.write('      cytotoxic T cells/MAIT->CD8T, helper T cells->CD4T, epithelial->Ductal, fibroblast->CAF.\n')
    f.write(f'exact-label accuracy (fine vs coarse taxonomy): {acc_exact:.4f}\n')
    f.write(f'coarse-mapped accuracy: {acc_coarse:.4f}\n\n')
    f.write('Per-class metrics (coarse mapping):\n' + rep.to_string(index=False) + '\n\n')
    f.write('Fine-grained prediction distribution:\n' + ann[pred_col].value_counts().to_string() + '\n\n')
    f.write('Coarse-mapped distribution:\n' + ann['pred_coarse'].value_counts().to_string() + '\n')
print('exact acc:', acc_exact, '| coarse acc:', round(acc_coarse,4))
print(rep.to_string(index=False))
