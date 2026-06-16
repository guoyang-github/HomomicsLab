# pySCENIC Regulatory Network Analysis Skill

Python-based skill for inferring gene regulatory networks from single-cell RNA-seq data using pySCENIC. See `SKILL.md` for the full agent-oriented reference.

## Quick Start

```python
from scripts.python.pyscenic_analysis import run_pyscenic_pipeline

adjacencies, regulons, auc_matrix = run_pyscenic_pipeline(
    adata=adata,
    organism="human",
    db_type="10kb",
    grn_method="grnboost2",
    num_workers=4
)
```

## File Structure

```
bio-single-cell-regulatory-pyscenic/
├── SKILL.md                          # Agent-oriented skill reference
├── usage-guide.md                    # Detailed usage guide
├── README.md                         # This file
├── scripts/
│   └── python/
│       └── pyscenic_analysis.py      # Main analysis module
├── tests/
│   └── test_pyscenic.py              # Unit tests
└── examples/
    └── example_basic.py              # Basic usage example
```

## Database Management

| Organism | Available Types | Motif Versions |
|----------|----------------|----------------|
| human | 500bp, 10kb | v9, v10 |
| mouse | 500bp, 10kb | v9, v10 |
| fly | 500bp, 10kb | v9 only |

⚠️ **fly does not support v10**. Use `"v9"` for fly databases.

## Key Functions

### Database Management
- `check_database()` — Check database availability
- `download_databases()` — Download cisTarget databases (raises `ValueError` for invalid motif versions)
- `list_available_databases()` — List all database status (uses latest available motif version per organism)

### Pipeline Steps
- `run_pyscenic_pipeline()` — Complete pipeline (auto-downloads databases)
- `run_grn_inference()` — GRN inference with GRNBoost2/GENIE3
- `run_cistarget()` — cisTarget motif enrichment (internally calls `modules_from_adjacencies`)
- `run_aucell()` — AUCell regulon scoring

### Result Analysis
- `add_aucell_to_adata()` — Add AUC scores to `obsm` (returns modified adata)
- `get_top_regulons_per_celltype()` — Top regulons by mean activity per cell type
- `export_regulons_to_gmt()` — Export to GMT format (filters by `min_genes`)

## Testing

```bash
cd tests
python test_pyscenic.py
```

## Requirements

- Python >=3.9
- pyscenic >=0.12
- scanpy >=1.9
- arboreto >=0.1.5
- ctxcore >=0.2

## References

1. Aibar et al. (2017). SCENIC: single-cell regulatory network inference and clustering. *Nature Methods*.
2. Van de Sande et al. (2020). A scalable SCENIC workflow for single-cell gene regulatory network analysis. *Nature Protocols*.
3. pySCENIC: https://github.com/aertslab/pySCENIC
