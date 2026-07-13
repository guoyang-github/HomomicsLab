import sys, os
sys.path.insert(0, '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/skills/bio-single-cell-data-io/scripts/python')
from utils import detect_format_from_path, validate_file_exists
import anndata as ad
import pandas as pd

input_file = '/mnt/c/Users/guoyang/Desktop/data/PA12_small.h5ad'
output_dir = '/mnt/c/Users/guoyang/Desktop/TEST/HomomicsLab/tmp_dbg/dataio_small/outputs'
os.makedirs(output_dir, exist_ok=True)

validate_file_exists(input_file, context='input h5ad')
fmt = detect_format_from_path(input_file)

adata = ad.read_h5ad(input_file, backed='r')
n_cells = adata.n_obs
n_genes = adata.n_vars
obs_cols = list(adata.obs.columns)
vc = adata.obs['all_celltype'].value_counts(dropna=False)
adata.file.close()

rows = [
    ('format', fmt),
    ('n_cells', n_cells),
    ('n_genes', n_genes),
    ('n_obs_columns', len(obs_cols)),
    ('obs_columns', ';'.join(obs_cols)),
]
summary = pd.DataFrame(rows, columns=['item', 'value'])
counts = pd.DataFrame({'item': ['all_celltype:' + str(k) for k in vc.index],
                       'value': vc.values})
out = pd.concat([summary, counts], ignore_index=True)

out_csv = os.path.join(output_dir, 'obs_metadata_summary.csv')
out.to_csv(out_csv, index=False)
print('absolute output path:', os.path.abspath(out_csv))
print(out.to_string(index=False))
