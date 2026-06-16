"""
Core Analysis Functions for pertpy
====================================

This module provides wrapper functions for pertpy perturbation analysis,
including perturbation space computation, distance calculation, Augur
classification, and Mixscape analysis.
"""

import numpy as np
import pandas as pd
from typing import Optional, Union, List, Dict, Tuple, Literal, Any
import warnings


def check_perturbation_data(
    adata,
    perturbation_col: str = "perturbation",
    control: Optional[str] = None
) -> bool:
    """
    Validate AnnData object for perturbation analysis.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column in .obs containing perturbation labels
    control : str, optional
        Control perturbation label

    Returns
    -------
    bool
        True if data is valid
    """
    if perturbation_col not in adata.obs.columns:
        raise ValueError(f"Perturbation column '{perturbation_col}' not found in adata.obs")

    n_perturbations = adata.obs[perturbation_col].nunique()
    if n_perturbations < 2:
        raise ValueError(f"Need at least 2 perturbations, found {n_perturbations}")

    print(f"Data validation passed:")
    print(f"  Cells: {adata.n_obs}")
    print(f"  Genes: {adata.n_vars}")
    print(f"  Perturbations: {n_perturbations}")
    print(f"  Perturbation column: {perturbation_col}")

    if control:
        if control not in adata.obs[perturbation_col].values:
            raise ValueError(f"Control '{control}' not found in {perturbation_col}")
        print(f"  Control: {control}")

    return True


def compute_pseudobulk_space(
    adata,
    perturbation_col: str = "perturbation",
    layer: Optional[str] = None,
    replicate_col: Optional[str] = None,
    **kwargs
) -> Any:
    """
    Compute pseudobulk space for perturbation analysis.

    Aggregates cells by perturbation to create pseudobulk profiles.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column in .obs containing perturbation labels
    layer : str, optional
        Layer to use for computation. If None, uses .X
    replicate_col : str, optional
        Column for biological replicates
    **kwargs
        Additional arguments for PseudobulkSpace

    Returns
    -------
    AnnData
        Pseudobulk AnnData with one observation per perturbation
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required. Install with: pip install pertpy")

    check_perturbation_data(adata, perturbation_col)

    print("Computing pseudobulk space...")

    ps = pt.tl.PseudobulkSpace()

    compute_kwargs = {"target_col": perturbation_col, "layer_key": layer}
    if replicate_col is not None:
        compute_kwargs["groups_col"] = replicate_col
    compute_kwargs.update(kwargs)
    ps_adata = ps.compute(adata, **compute_kwargs)

    print(f"Pseudobulk space computed: {ps_adata.n_obs} perturbations x {ps_adata.n_vars} genes")

    return ps_adata


def compute_centroid_space(
    adata,
    perturbation_col: str = "perturbation",
    embedding_key: str = "X_umap",
    **kwargs
) -> Any:
    """
    Compute centroid space from pre-computed embedding.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with embedding
    perturbation_col : str
        Column in .obs containing perturbation labels
    embedding_key : str
        Key in .obsm for the embedding to use
    **kwargs
        Additional arguments for CentroidSpace

    Returns
    -------
    AnnData
        Centroid AnnData with one observation per perturbation
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    if embedding_key not in adata.obsm:
        raise ValueError(f"Embedding '{embedding_key}' not found in adata.obsm")

    check_perturbation_data(adata, perturbation_col)

    print(f"Computing centroid space using {embedding_key}...")

    cs = pt.tl.CentroidSpace()

    cs_adata = cs.compute(
        adata,
        target_col=perturbation_col,
        embedding_key=embedding_key,
        **kwargs
    )

    print(f"Centroid space computed: {cs_adata.n_obs} perturbations")

    return cs_adata


def run_augur_classification(
    adata,
    estimator: Literal["random_forest_classifier", "random_forest_regressor", "logistic_regression_classifier"] = "random_forest_classifier",
    labels_col: str = "perturbation",
    cell_type_col: Optional[str] = None,
    **kwargs
) -> Any:
    """
    Run Augur for perturbation effect classification.

    Augur uses machine learning to classify perturbations and quantify
    their effects based on cell type prioritization.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    estimator : str
        Estimator to use for classification
    labels_col : str
        Column with perturbation labels
    cell_type_col : str, optional
        Column with cell type labels
    **kwargs
        Additional arguments for Augur

    Returns
    -------
    AnnData
        AnnData with Augur results in .uns
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    print(f"Running Augur with {estimator}...")

    augur = pt.tl.Augur(estimator)

    # Load data
    load_kwargs = {"label_col": labels_col}
    if cell_type_col is not None:
        load_kwargs["cell_type_col"] = cell_type_col
    adata_augur = augur.load(adata, **load_kwargs)

    # Predict (returns tuple: AnnData, dict)
    adata_augur, results = augur.predict(adata_augur)

    print("Augur classification complete")

    return adata_augur


def calculate_perturbation_distances(
    adata,
    perturbation_col: str = "perturbation",
    metric: Literal["edistance", "euclidean", "cosine_distance", "mmd", "wasserstein"] = "edistance",
    control: Optional[str] = None,
    **kwargs
) -> pd.DataFrame:
    """
    Calculate distances between perturbations.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels
    metric : str
        Distance metric to use
    control : str, optional
        Control perturbation for pairwise comparisons
    **kwargs
        Additional arguments for Distance

    Returns
    -------
    pd.DataFrame
        DataFrame with distance matrix
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    check_perturbation_data(adata, perturbation_col)

    print(f"Calculating {metric} distances...")

    distance = pt.tl.Distance(metric=metric, **kwargs)

    # Compute pairwise distances
    dist_df = distance.pairwise(
        adata,
        groupby=perturbation_col,
        show_progressbar=True
    )

    print(f"Distance matrix shape: {dist_df.shape}")

    return dist_df


def compute_perturbation_signature(
    adata,
    perturbation_col: str = "perturbation",
    control: str = "control",
    split_by: Optional[str] = None,
    n_neighbors: int = 20,
    **kwargs
) -> Any:
    """
    Compute perturbation signature using Mixscape.

    The perturbation signature is calculated by subtracting the expression
    profile of control cells from each cell.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels
    control : str
        Control perturbation label
    split_by : str, optional
        Column for splitting by replicates/batches
    n_neighbors : int
        Number of neighbors from control to use
    **kwargs
        Additional arguments

    Returns
    -------
    AnnData
        AnnData with perturbation signature in .layers['X_pert']
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    check_perturbation_data(adata, perturbation_col, control)

    print("Computing perturbation signatures...")

    ms = pt.tl.Mixscape()

    ms.perturbation_signature(
        adata,
        pert_key=perturbation_col,
        control=control,
        split_by=split_by,
        n_neighbors=n_neighbors,
        **kwargs
    )

    print("Perturbation signatures stored in .layers['X_pert']")

    return adata


def run_mixscape_classification(
    adata,
    perturbation_col: str = "perturbation",
    control: str = "control",
    new_class_name: str = "mixscape_class",
    min_de_genes: int = 5,
    logfc_threshold: float = 0.25,
    **kwargs
) -> Any:
    """
    Run Mixscape to classify cells into perturbation groups.

    Identifies perturbed and non-perturbed cells in CRISPR screens.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix with perturbation signature
    perturbation_col : str
        Column with perturbation labels
    control : str
        Control perturbation label
    new_class_name : str
        Name for the new classification column
    min_de_genes : int
        Minimum number of DE genes required
    logfc_threshold : float
        Log fold change threshold for DE genes
    **kwargs
        Additional arguments for mixscape

    Returns
    -------
    AnnData
        AnnData with mixscape classifications
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    check_perturbation_data(adata, perturbation_col, control)

    if "X_pert" not in adata.layers:
        raise ValueError("Perturbation signature not found. Run compute_perturbation_signature first.")

    print("Running Mixscape classification...")

    ms = pt.tl.Mixscape()

    ms.mixscape(
        adata,
        pert_key=perturbation_col,
        control=control,
        new_class_name=new_class_name,
        min_de_genes=min_de_genes,
        logfc_threshold=logfc_threshold,
        **kwargs
    )

    print(f"Mixscape classification complete. Results in .obs['{new_class_name}']")

    return adata


def assign_guide_rna(
    adata,
    guide_rna_column: str = "guide_identity",
    assignment_method: Literal["mixture", "threshold"] = "threshold",
    threshold: int = 5,
    **kwargs
) -> Any:
    """
    Assign guide RNAs to cells based on capture.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    guide_rna_column : str
        Column with guide RNA identities
    assignment_method : str
        Method for assignment: "mixture" or "threshold"
    threshold : int
        Minimum counts for guide assignment (for threshold method)
    **kwargs
        Additional arguments

    Returns
    -------
    AnnData
        AnnData with guide assignments
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    print(f"Assigning guide RNAs using {assignment_method} method...")

    ga = pt.pp.GuideAssignment()

    if assignment_method == "threshold":
        ga.assign_by_threshold(
            adata,
            assignment_threshold=threshold,
            **kwargs
        )
    elif assignment_method == "mixture":
        ga.assign_mixture_model(
            adata,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown assignment method: {assignment_method}")

    print("Guide RNA assignment complete")

    return adata


def compare_perturbations(
    adata,
    perturbation_col: str = "perturbation",
    reference: str = "control",
    method: Literal["pydeseq2", "edger", "ttest", "wilcoxon"] = "pydeseq2",
    replicate_col: Optional[str] = None,
    **kwargs
) -> Dict[str, pd.DataFrame]:
    """
    Perform differential expression analysis between perturbations.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels
    reference : str
        Reference/control perturbation
    method : str
        DE method to use
    replicate_col : str, optional
        Column with replicate information
    **kwargs
        Additional arguments for DE methods

    Returns
    -------
    dict
        Dictionary with DE results for each perturbation
    """
    try:
        import pertpy as pt
    except ImportError:
        raise ImportError("pertpy is required")

    check_perturbation_data(adata, perturbation_col, reference)

    print(f"Running differential expression with {method}...")

    # Map method names to pertpy class names
    method_map = {
        "pydeseq2": "PyDESeq2",
        "edger": "EdgeR",
        "ttest": "TTest",
        "wilcoxon": "WilcoxonTest",
    }
    class_name = method_map.get(method)
    if class_name is None:
        raise ValueError(f"Unknown DE method: {method}. Supported: {list(method_map.keys())}")

    de_class = getattr(pt.tl, class_name)
    perturbations = adata.obs[perturbation_col].unique()
    results = {}

    # Linear model methods (PyDESeq2, EdgeR)
    if method in ("pydeseq2", "edger"):
        design = f"~{perturbation_col}"
        if replicate_col is not None:
            design = f"~{replicate_col} + {perturbation_col}"
        de = de_class(adata, design=design)
        de.fit()
        for pert in perturbations:
            if pert == reference:
                continue
            print(f"  Comparing {pert} vs {reference}...")
            results[pert] = de.compare_groups(
                column=perturbation_col,
                baseline=reference,
                group_to_compare=pert,
            )
    else:
        # Simple tests (TTest, WilcoxonTest)
        for pert in perturbations:
            if pert == reference:
                continue
            print(f"  Comparing {pert} vs {reference}...")
            de = de_class(adata)
            results[pert] = de.compare_groups(
                column=perturbation_col,
                baseline=reference,
                group_to_compare=pert,
            )

    print(f"DE analysis complete for {len(results)} perturbations")

    return results


def run_complete_perturbation_analysis(
    adata,
    perturbation_col: str = "perturbation",
    control: str = "control",
    compute_signature: bool = True,
    run_mixscape: bool = True,
    run_augur: bool = True,
    **kwargs
) -> Any:
    """
    Run complete perturbation analysis pipeline.

    Parameters
    ----------
    adata : AnnData
        Annotated data matrix
    perturbation_col : str
        Column with perturbation labels
    control : str
        Control perturbation label
    compute_signature : bool
        Whether to compute perturbation signatures
    run_mixscape : bool
        Whether to run Mixscape classification
    run_augur : bool
        Whether to run Augur classification
    **kwargs
        Additional arguments

    Returns
    -------
    AnnData
        AnnData with all analysis results
    """
    print("=== Complete Perturbation Analysis ===\n")

    check_perturbation_data(adata, perturbation_col, control)

    # Step 1: Compute perturbation signatures
    if compute_signature:
        print("[1/3] Computing perturbation signatures...")
        adata = compute_perturbation_signature(adata, perturbation_col, control, **kwargs)
        print()

    # Step 2: Mixscape classification
    if run_mixscape and compute_signature:
        print("[2/3] Running Mixscape classification...")
        adata = run_mixscape_classification(adata, perturbation_col, control, **kwargs)
        print()

    # Step 3: Augur classification
    if run_augur:
        print("[3/3] Running Augur classification...")
        adata = run_augur_classification(adata, labels_col=perturbation_col, **kwargs)
        print()

    print("=== Analysis Complete ===")

    return adata
