"""
Core Analysis Functions for LIANA+ Cell-Cell Communication

Lightweight wrappers around native liana-py API.
For visualization, use native liana.plotting functions directly.

Author: Yang Guo
Date: 2026-05-14
"""

import pandas as pd
import scanpy as sc
from typing import List, Dict, Optional, Union, Tuple


def run_rank_aggregate(
    adata: sc.AnnData,
    groupby: str,
    resource_name: str = 'consensus',
    expr_prop: float = 0.1,
    min_cells: int = 5,
    aggregate_method: str = 'rra',
    n_perms: int = 100,
    seed: int = 42,
    use_raw: bool = True,
    layer: Optional[str] = None,
    key_added: str = 'liana_res',
    inplace: bool = True,
    verbose: bool = True,
    **kwargs
) -> Optional[pd.DataFrame]:
    """
    Run LIANA+ rank aggregate (consensus across multiple CCC methods).

    This is the recommended default for single-cell CCC analysis.
    Native API: ln.mt.rank_aggregate(...)

    Parameters
    ----------
    adata : sc.AnnData
        Annotated data matrix with cell type annotations
    groupby : str
        Column in adata.obs for cell type grouping
    resource_name : str, default='consensus'
        LR database: 'consensus', 'CellChatDB', 'CellPhoneDB', etc. Run ln.rs.show_resources().
    expr_prop : float, default=0.1
        Min fraction of cells expressing a gene (0-1)
    min_cells : int, default=5
        Min cells per group
    aggregate_method : str, default='rra'
        'rra' (RobustRankAggregate) or 'mean'
    n_perms : int, default=100
        Permutations for statistical testing
    seed : int, default=42
        Random seed
    use_raw : bool, default=True
        Use adata.raw expression values if present. Set to False to use adata.X instead.
    layer : Optional[str], default=None
        Specific layer from adata.layers
    key_added : str, default='liana_res'
        Key to store results in adata.uns
    inplace : bool, default=True
        If True, store results in adata.uns[key_added]
        If False, return DataFrame
    verbose : bool, default=True
        Print progress
    **kwargs
        Passed to ln.mt.rank_aggregate

    Returns
    -------
    Optional[pd.DataFrame]
        Results DataFrame if inplace=False
    """
    import liana as ln

    if verbose:
        print(f"Running LIANA+ rank_aggregate...")
        print(f"  groupby: {groupby}, resource: {resource_name}")

    liana_res = ln.mt.rank_aggregate(
        adata=adata,
        groupby=groupby,
        resource_name=resource_name,
        expr_prop=expr_prop,
        min_cells=min_cells,
        aggregate_method=aggregate_method,
        n_perms=n_perms,
        seed=seed,
        use_raw=use_raw,
        layer=layer,
        key_added=key_added,
        inplace=False,
        verbose=verbose,
        **kwargs
    )

    if verbose:
        print(f"  Found {len(liana_res)} interactions")

    if inplace:
        adata.uns[key_added] = liana_res
        if verbose:
            print(f"  Results stored in adata.uns['{key_added}']")
    else:
        return liana_res


def run_individual_method(
    adata: sc.AnnData,
    method: str,
    groupby: str,
    resource_name: str = 'consensus',
    expr_prop: float = 0.1,
    min_cells: int = 5,
    n_perms: int = 100,
    seed: int = 42,
    use_raw: bool = False,
    layer: Optional[str] = None,
    key_added: Optional[str] = None,
    inplace: bool = True,
    verbose: bool = True,
    **kwargs
) -> Optional[pd.DataFrame]:
    """
    Run a specific individual CCC method.

    Available methods: 'cellphonedb', 'cellchat', 'connectome',
    'natmi', 'singlecellsignalr', 'geometric_mean', 'scseqcomm', 'logfc'

    Parameters
    ----------
    adata : sc.AnnData
        Annotated data matrix
    method : str
        Method name (case-insensitive)
    groupby : str
        Cell type annotation column
    resource_name : str, default='consensus'
        LR database name
    expr_prop : float, default=0.1
        Min expression proportion
    min_cells : int, default=5
        Min cells per group
    n_perms : int, default=100
        Permutations (for permutation-based methods)
    seed : int, default=42
        Random seed
    use_raw : bool, default=False
        Use adata.raw
    layer : Optional[str], default=None
        adata.layers key
    key_added : Optional[str], default=None
        Results key. If None, uses 'liana_{method}'
    inplace : bool, default=True
        Store in adata.uns or return DataFrame
    verbose : bool, default=True
        Print progress
    **kwargs
        Passed to method function

    Returns
    -------
    Optional[pd.DataFrame]
        Results if inplace=False
    """
    import liana as ln

    method_map = {
        'cellphonedb': ln.mt.cellphonedb,
        'cellchat': ln.mt.cellchat,
        'connectome': ln.mt.connectome,
        'natmi': ln.mt.natmi,
        'singlecellsignalr': ln.mt.singlecellsignalr,
        'scsignalr': ln.mt.singlecellsignalr,
        'geometric_mean': ln.mt.geometric_mean,
        'scseqcomm': ln.mt.scseqcomm,
        'logfc': ln.mt.logfc,
    }

    method_lower = method.lower()
    if method_lower not in method_map:
        raise ValueError(
            f"Unknown method: {method}. Choose from: {list(method_map.keys())}"
        )

    if key_added is None:
        key_added = f'liana_{method_lower}'

    if verbose:
        print(f"Running {method_lower}...")

    method_func = method_map[method_lower]
    liana_res = method_func(
        adata=adata,
        groupby=groupby,
        resource_name=resource_name,
        expr_prop=expr_prop,
        min_cells=min_cells,
        n_perms=n_perms,
        seed=seed,
        use_raw=use_raw,
        layer=layer,
        inplace=False,
        verbose=verbose,
        **kwargs
    )

    if verbose:
        print(f"  Found {len(liana_res)} interactions")

    if inplace:
        adata.uns[key_added] = liana_res
        if verbose:
            print(f"  Results stored in adata.uns['{key_added}']")
    else:
        return liana_res


def get_top_interactions(
    liana_res: pd.DataFrame,
    n: int = 20,
    by: str = 'magnitude_rank',
    ascending: bool = True,
    source_cells: Optional[List[str]] = None,
    target_cells: Optional[List[str]] = None,
    ligand: Optional[str] = None,
    receptor: Optional[str] = None
) -> pd.DataFrame:
    """
    Get top N interactions from LIANA results.

    Parameters
    ----------
    liana_res : pd.DataFrame
        LIANA results DataFrame
    n : int, default=20
        Number of top interactions
    by : str, default='magnitude_rank'
        Column to sort by
    ascending : bool, default=True
        Sort ascending (for ranks) or descending
    source_cells : Optional[List[str]], default=None
        Filter to specific source cell types
    target_cells : Optional[List[str]], default=None
        Filter to specific target cell types
    ligand : Optional[str], default=None
        Filter to specific ligand
    receptor : Optional[str], default=None
        Filter to specific receptor

    Returns
    -------
    pd.DataFrame
        Filtered and sorted top N results
    """
    result = liana_res.copy()

    if source_cells is not None:
        result = result[result['source'].isin(source_cells)]
    if target_cells is not None:
        result = result[result['target'].isin(target_cells)]
    if ligand is not None:
        result = result[result['ligand'] == ligand]
    if receptor is not None:
        result = result[result['receptor'] == receptor]

    if by in result.columns:
        result = result.sort_values(by=by, ascending=ascending)

    return result.head(n)


def summarize_by_cell_pair(
    liana_res: pd.DataFrame,
    agg_func: str = 'count',
    value_col: Optional[str] = None
) -> pd.DataFrame:
    """
    Summarize interactions by source-target cell pairs.

    Parameters
    ----------
    liana_res : pd.DataFrame
        LIANA results
    agg_func : str, default='count'
        'count', 'mean', 'sum', 'max'
    value_col : Optional[str], default=None
        Column to aggregate (for non-count funcs)

    Returns
    -------
    pd.DataFrame
        Pivoted matrix (source x target)
    """
    if agg_func == 'count':
        summary = liana_res.groupby(['source', 'target']).size().reset_index(name='n_interactions')
    else:
        if value_col is None:
            candidates = ['magnitude_rank', 'specificity_rank', 'lr_means']
            value_col = next((c for c in candidates if c in liana_res.columns), liana_res.columns[-1])
        summary = liana_res.groupby(['source', 'target'])[value_col].agg(agg_func).reset_index()

    summary_matrix = summary.pivot(index='source', columns='target', values=summary.columns[-1])
    return summary_matrix.fillna(0)


def export_results(
    liana_res: pd.DataFrame,
    output_path: str,
    format: str = 'csv'
):
    """
    Export LIANA results to file.

    Parameters
    ----------
    liana_res : pd.DataFrame
        Results DataFrame
    output_path : str
        Output file path
    format : str, default='csv'
        'csv', 'tsv', 'excel'
    """
    if format == 'csv':
        liana_res.to_csv(output_path, index=False)
    elif format == 'tsv':
        liana_res.to_csv(output_path, sep='\t', index=False)
    elif format == 'excel':
        liana_res.to_excel(output_path, index=False)
    else:
        raise ValueError(f"Unknown format: {format}. Use 'csv', 'tsv', or 'excel'.")

    print(f"Exported {len(liana_res)} interactions to {output_path}")
