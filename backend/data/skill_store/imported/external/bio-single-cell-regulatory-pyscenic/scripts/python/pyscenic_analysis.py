"""
pySCENIC Regulatory Network Analysis Module

A comprehensive wrapper for pySCENIC pipeline with database management,
automatic downloading, and best practices for regulatory network inference.

Author: Yang Guo
Date: 2026-04-03
Version: 1.0.0
"""

import os
import logging
import shutil
from pathlib import Path
from typing import List, Optional, Union, Dict, Tuple
import urllib.request
import hashlib

import numpy as np
import pandas as pd
import scanpy as sc

# Optional imports for pySCENIC
try:
    from pyscenic.aucell import aucell
    from pyscenic.cli.pyscenic import find_adjacencies_command, ctx_command, aucell_command
    from pyscenic.export import export2loom, export2csv
    from pyscenic.prune import prune2df
    from pyscenic.transform import df2regulons
    from pyscenic.utils import load_motifs, save_matrix, load_signatures, modules_from_adjacencies
    from arboreto.algo import genie3, grnboost2
    from arboreto.utils import load_tf_names
    from ctxcore.rnkdb import RankingDatabase, opendb
    PYSCENIC_AVAILABLE = True
except ImportError:
    PYSCENIC_AVAILABLE = False


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Database Management
# ============================================================================

# cisTarget database URLs and checksums (from https://resources.aertslab.org/cistarget/)
DATABASE_CONFIG = {
    "human": {
        "base_url": "https://resources.aertslab.org/cistarget/databases/homo_sapiens/hg38/refseq_r80/",
        "databases": {
            "500bp": {
                "file": "hg38__refseq-r80__500bp_up_and_100bp_down_tss.genes_vs_motifs.rankings.feather",
                "checksum": None,  # Add MD5 checksums when available
            },
            "10kb": {
                "file": "hg38__refseq-r80__10kb_up_and_down_tss.genes_vs_motifs.rankings.feather",
                "checksum": None,
            }
        },
        "motif_annotations": {
            "v9": "https://resources.aertslab.org/cistarget/motif2tf/motifs-v9-nr.hgnc-m0.001-o0.0.tbl",
            "v10": "https://resources.aertslab.org/cistarget/motif2tf/motifs-v10nr_clust-nr.hgnc-m0.001-o0.0.tbl",
        },
        "tf_list": "https://resources.aertslab.org/cistarget/tf_lists/allTFs_hg38.txt"
    },
    "mouse": {
        "base_url": "https://resources.aertslab.org/cistarget/databases/mus_musculus/mm10/",
        "databases": {
            "500bp": {
                "file": "mm10__refseq-r80__500bp_up_and_100bp_down_tss.genes_vs_motifs.rankings.feather",
                "checksum": None,
            },
            "10kb": {
                "file": "mm10__refseq-r80__10kb_up_and_down_tss.genes_vs_motifs.rankings.feather",
                "checksum": None,
            }
        },
        "motif_annotations": {
            "v9": "https://resources.aertslab.org/cistarget/motif2tf/motifs-v9-nr.mgi-m0.001-o0.0.tbl",
            "v10": "https://resources.aertslab.org/cistarget/motif2tf/motifs-v10nr_clust-nr.mgi-m0.001-o0.0.tbl",
        },
        "tf_list": "https://resources.aertslab.org/cistarget/tf_lists/allTFs_mm10.txt"
    },
    "fly": {
        "base_url": "https://resources.aertslab.org/cistarget/databases/drosophila_melanogaster/dm6/",
        "databases": {
            "500bp": {
                "file": "dm6__refseq-r80__500bp_up_and_100bp_down_tss.genes_vs_motifs.rankings.feather",
                "checksum": None,
            },
            "10kb": {
                "file": "dm6__refseq-r80__10kb_up_and_down_tss.genes_vs_motifs.rankings.feather",
                "checksum": None,
            }
        },
        "motif_annotations": {
            "v9": "https://resources.aertslab.org/cistarget/motif2tf/motifs-v9-nr.flybase-m0.001-o0.0.tbl",
        },
        "tf_list": "https://resources.aertslab.org/cistarget/tf_lists/allTFs_dmel.txt"
    }
}


def get_pyscenic_dir(prefer_skill_assets: bool = True) -> Path:
    """
    Get pySCENIC database directory with hierarchical lookup.

    Lookup order:
    1. If prefer_skill_assets=True: Check skill directory's assets/ folder first
    2. Fall back to ~/.pyscenic/ in user's home directory

    The assets/ folder in the skill directory allows for project-specific
    database storage without polluting the user's home directory.

    Parameters
    ----------
    prefer_skill_assets : bool, default True
        If True, prefer skill directory's assets/ folder.
        If False, always use ~/.pyscenic/

    Returns
    -------
    Path
        Path to the database directory

    Notes
    -----
    - Skill assets path: <skill_dir>/assets/
    - Home fallback path: ~/.pyscenic/
    - Creates the directory if it doesn't exist

    Examples
    --------
    >>> cache_dir = get_pyscenic_dir()
    >>> print(cache_dir)
    /path/to/bio-single-cell-regulatory-pyscenic/assets  # if exists
    >>> # or ~/.pyscenic/ if assets/ doesn't exist
    """
    if prefer_skill_assets:
        # Try skill directory assets/ first
        try:
            # Get the directory of this script
            script_dir = Path(__file__).parent.resolve()
            # Go up to skill root (scripts/python/ -> skill root)
            skill_dir = script_dir.parent.parent
            skill_assets = skill_dir / "assets"

            if skill_assets.exists() or skill_dir.name == "bio-single-cell-regulatory-pyscenic":
                # Create assets directory if it doesn't exist
                skill_assets.mkdir(parents=True, exist_ok=True)
                logger.info(f"Using skill assets directory: {skill_assets}")
                return skill_assets
        except Exception:
            pass  # Fall through to home directory

    # Fall back to home directory
    cache_dir = Path.home() / ".pyscenic"
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using home directory cache: {cache_dir}")
    return cache_dir


def list_pyscenic_cache_locations() -> Dict[str, Path]:
    """
    List all possible cache locations for pySCENIC databases.

    Returns
    -------
    Dict[str, Path]
        Dictionary with 'skill_assets' and 'home_cache' paths

    Examples
    --------
    >>> locations = list_pyscenic_cache_locations()
    >>> print(locations['skill_assets'])
    >>> print(locations['home_cache'])
    """
    locations = {
        'home_cache': Path.home() / ".pyscenic"
    }

    try:
        script_dir = Path(__file__).parent.resolve()
        skill_dir = script_dir.parent.parent
        locations['skill_assets'] = skill_dir / "assets"
    except Exception:
        locations['skill_assets'] = None

    return locations


def migrate_databases_to_skill_assets(dry_run: bool = True) -> Dict[str, list]:
    """
    Migrate databases from ~/.pyscenic/ to skill assets/ directory.

    Useful for consolidating databases in the skill directory for
    project isolation or sharing.

    Parameters
    ----------
    dry_run : bool, default True
        If True, only report what would be moved without actually moving files.

    Returns
    -------
    Dict[str, list]
        Dictionary with 'to_migrate' and 'already_present' file lists

    Examples
    --------
    >>> # Preview migration
    >>> result = migrate_databases_to_skill_assets(dry_run=True)
    >>> print(f"Files to migrate: {len(result['to_migrate'])}")
    >>>
    >>> # Actually migrate
    >>> result = migrate_databases_to_skill_assets(dry_run=False)
    """
    locations = list_pyscenic_cache_locations()
    home_cache = locations['home_cache']
    skill_assets = locations.get('skill_assets')

    if skill_assets is None:
        raise RuntimeError("Cannot determine skill assets directory")

    result = {
        'to_migrate': [],
        'already_present': [],
        'source_dir': str(home_cache),
        'target_dir': str(skill_assets)
    }

    if not home_cache.exists():
        logger.info("No home cache directory found")
        return result

    # Check for database files
    for file_path in home_cache.iterdir():
        if file_path.is_file():
            target_path = skill_assets / file_path.name
            if target_path.exists():
                result['already_present'].append(file_path.name)
            else:
                result['to_migrate'].append(file_path.name)

    logger.info(f"Found {len(result['to_migrate'])} files to migrate")
    logger.info(f"Found {len(result['already_present'])} files already present")

    if not dry_run and result['to_migrate']:
        skill_assets.mkdir(parents=True, exist_ok=True)
        for filename in result['to_migrate']:
            src = home_cache / filename
            dst = skill_assets / filename
            logger.info(f"Moving {filename} to skill assets...")
            shutil.copy2(src, dst)
            src.unlink()
        logger.info("Migration complete!")

    return result


def check_database(organism: str = "human",
                   db_type: str = "10kb",
                   motif_version: str = "v10") -> Dict[str, bool]:
    """
    Check if required databases are available.

    Parameters
    ----------
    organism : str
        Organism: "human", "mouse", or "fly"
    db_type : str
        Database type: "500bp" or "10kb"
    motif_version : str
        Motif annotation version: "v9" or "v10"

    Returns
    -------
    Dict[str, Union[bool, Path]]
        Dictionary with database availability status:
        - "database" (bool): Whether the ranking database exists
        - "motif_annotations" (bool): Whether the motif annotation file exists
        - "tf_list" (bool): Whether the TF list file exists
        - "db_path" (Path): Path to the ranking database file
        - "motif_path" (Path): Path to the motif annotation file
        - "tf_path" (Path): Path to the TF list file
    """
    cache_dir = get_pyscenic_dir()
    config = DATABASE_CONFIG.get(organism)

    if not config:
        raise ValueError(f"Unknown organism: {organism}")

    db_file = config["databases"][db_type]["file"]
    db_path = cache_dir / db_file

    motif_url = config["motif_annotations"].get(motif_version)
    motif_file = motif_url.split("/")[-1] if motif_url else None
    motif_path = cache_dir / motif_file if motif_file else None

    tf_file = config["tf_list"].split("/")[-1]
    tf_path = cache_dir / tf_file

    return {
        "database": db_path.exists(),
        "motif_annotations": motif_path.exists() if motif_path else False,
        "tf_list": tf_path.exists(),
        "db_path": db_path,
        "motif_path": motif_path,
        "tf_path": tf_path
    }


def _verify_checksum(file_path: Path, expected_md5: str) -> bool:
    """Verify file MD5 checksum."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest().lower() == expected_md5.lower()


def download_file(url: str, dest_path: Path, chunk_size: int = 8192) -> None:
    """Download a file with progress logging."""
    logger.info(f"Downloading {url} to {dest_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    def report_hook(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = min(downloaded * 100 / total_size, 100) if total_size > 0 else 0
        if block_num % 100 == 0:  # Log every 100 blocks
            logger.info(f"Downloaded {percent:.1f}%")

    urllib.request.urlretrieve(url, dest_path, reporthook=report_hook)
    logger.info(f"Download complete: {dest_path}")


def download_databases(organism: str = "human",
                       db_type: str = "10kb",
                       motif_version: str = "v10",
                       force: bool = False) -> Dict[str, Path]:
    """
    Download cisTarget databases for pySCENIC.

    Parameters
    ----------
    organism : str
        Organism: "human", "mouse", or "fly"
    db_type : str
        Database type: "500bp" or "10kb"
    motif_version : str
        Motif annotation version
    force : bool
        Force re-download even if cached

    Returns
    -------
    Dict with paths to downloaded files
    """
    cache_dir = get_pyscenic_dir()
    config = DATABASE_CONFIG.get(organism)

    if not config:
        raise ValueError(f"Unknown organism: {organism}")

    results = {}

    # Download ranking database
    db_config = config["databases"][db_type]
    db_file = db_config["file"]
    db_path = cache_dir / db_file
    db_url = config["base_url"] + db_file
    expected_checksum = db_config.get("checksum")

    if not db_path.exists() or force:
        logger.info(f"Downloading ranking database: {db_file}")
        download_file(db_url, db_path)
    else:
        logger.info(f"Ranking database already cached: {db_path}")

    # Verify download integrity
    if not db_path.exists() or db_path.stat().st_size == 0:
        raise RuntimeError(
            f"Downloaded database file is missing or empty: {db_path}. "
            f"Try removing the file and re-running download_databases()."
        )
    if expected_checksum and _verify_checksum(db_path, expected_checksum):
        logger.info(f"Checksum verified for {db_file}")
    elif expected_checksum:
        logger.warning(f"Checksum mismatch for {db_file}. File may be corrupted.")
    results["database"] = db_path

    # Download motif annotations
    motif_url = config["motif_annotations"].get(motif_version)
    if motif_url is None:
        available = list(config["motif_annotations"].keys())
        raise ValueError(
            f"Motif version '{motif_version}' not available for organism '{organism}'. "
            f"Available versions: {available}"
        )
    motif_file = motif_url.split("/")[-1]
    motif_path = cache_dir / motif_file
    if not motif_path.exists() or force:
        logger.info(f"Downloading motif annotations: {motif_file}")
        download_file(motif_url, motif_path)
    else:
        logger.info(f"Motif annotations already cached: {motif_path}")

    # Verify motif download
    if not motif_path.exists() or motif_path.stat().st_size == 0:
        raise RuntimeError(
            f"Downloaded motif file is missing or empty: {motif_path}. "
            f"Try removing the file and re-running download_databases()."
        )
    results["motif_annotations"] = motif_path

    # Download TF list
    tf_url = config["tf_list"]
    tf_file = tf_url.split("/")[-1]
    tf_path = cache_dir / tf_file
    if not tf_path.exists() or force:
        logger.info(f"Downloading TF list: {tf_file}")
        download_file(tf_url, tf_path)
    else:
        logger.info(f"TF list already cached: {tf_path}")

    # Verify TF list download
    if not tf_path.exists() or tf_path.stat().st_size == 0:
        raise RuntimeError(
            f"Downloaded TF list is missing or empty: {tf_path}. "
            f"Try removing the file and re-running download_databases()."
        )
    results["tf_list"] = tf_path

    return results


def list_available_databases() -> pd.DataFrame:
    """List all available databases and their download status.

    Checks each organism's available motif versions (not all organisms
    support all versions, e.g., fly only has v9).
    """
    records = []

    for organism, config in DATABASE_CONFIG.items():
        # Use the latest available motif version for this organism
        # Sort by numeric version (v10 > v9), not string order
        available_motif_versions = sorted(
            config["motif_annotations"].keys(),
            key=lambda v: int(v.lstrip("v"))
        )
        motif_version = available_motif_versions[-1]  # Latest version

        for db_type in ["500bp", "10kb"]:
            status = check_database(organism, db_type, motif_version)
            records.append({
                "organism": organism,
                "type": db_type,
                "motif_version": motif_version,
                "database_cached": status["database"],
                "motifs_cached": status["motif_annotations"],
                "tf_list_cached": status["tf_list"],
                "all_ready": all([
                    status["database"],
                    status["motif_annotations"],
                    status["tf_list"]
                ])
            })

    return pd.DataFrame(records)


# ============================================================================
# GRN Inference
# ============================================================================

def run_grn_inference(
    adata: sc.AnnData,
    tf_names: Optional[List[str]] = None,
    tf_file: Optional[Path] = None,
    method: str = "grnboost2",
    seed: Optional[int] = None,
    num_workers: int = 4,
    client_or_address: str = "local",
    verbose: bool = True
) -> pd.DataFrame:
    """
    Run GRN inference using GRNBoost2 or GENIE3.

    This step infers transcription factor-target gene relationships based on
    expression correlation using tree-based ensemble methods.

    Parameters
    ----------
    adata : sc.AnnData
        AnnData object with expression matrix (cells x genes).
        Gene names must be gene symbols (e.g., 'TP53', not Ensembl IDs).
        Both sparse and dense matrices are supported.
    tf_names : List[str], optional
        List of transcription factor names. If provided, tf_file is ignored.
    tf_file : Path, optional
        Path to TF list file (one TF per line). Downloaded automatically
        via download_databases() if not provided.
    method : str
        GRN inference algorithm:
        - "grnboost2": Faster, gradient boosting (recommended for >10k cells)
        - "genie3": Slower, random forests (more accurate for small datasets)
    seed : int, optional
        Random seed for reproducibility
    num_workers : int
        Number of parallel workers. Each worker requires ~2GB memory.
        Reduce to 2 if memory limited (<16GB RAM).
    client_or_address : str
        Dask client address for distributed computing, or "local" for local execution
    verbose : bool
        Print progress messages

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - 'TF': Transcription factor gene symbol
        - 'target': Target gene symbol
        - 'importance': Edge weight from GRN algorithm (0-1 scale)

    Notes
    -----
    - This is the most computationally intensive step
    - Runtime scales with: n_cells × n_genes × n_TFs × n_trees
    - GRNBoost2 is typically 2-5x faster than GENIE3 with similar accuracy
    - For datasets >50k cells, consider subsampling to 20k cells

    Examples
    --------
    >>> adjacencies = run_grn_inference(
    ...     adata=adata,
    ...     tf_file="allTFs_hg38.txt",
    ...     method="grnboost2",
    ...     num_workers=4
    ... )
    >>> adjacencies.head()
           TF  target  importance
    0   SOX10    MITF       0.085
    1   SOX10     DCT       0.072
    """
    if not PYSCENIC_AVAILABLE:
        raise ImportError("pySCENIC not installed. Install with: pip install pyscenic")

    if verbose:
        logger.info(f"Running {method} for GRN inference...")
        logger.info(f"Expression matrix shape: {adata.X.shape}")

    # Load TF names
    if tf_names is None:
        if tf_file is None:
            raise ValueError("Either tf_names or tf_file must be provided")
        tf_names = load_tf_names(str(tf_file))

    if verbose:
        logger.info(f"Using {len(tf_names)} transcription factors")

    # Validate TF overlap with adata gene names
    tf_overlap = set(tf_names) & set(adata.var_names)
    if not tf_overlap:
        raise ValueError(
            f"No TF names overlap with adata.var_names. "
            f"TF list has {len(tf_names)} TFs, adata has {adata.n_vars} genes. "
            f"Check that gene names are symbols (e.g., 'TP53') not Ensembl IDs."
        )
    overlap_pct = len(tf_overlap) / len(tf_names) * 100
    if overlap_pct < 50:
        logger.warning(
            f"Only {len(tf_overlap)}/{len(tf_names)} ({overlap_pct:.1f}%) TFs found in adata. "
            f"Low overlap may indicate gene ID mismatch."
        )

    # Convert to dense if sparse
    if hasattr(adata.X, 'toarray'):
        expr_matrix = pd.DataFrame(
            adata.X.toarray(),
            index=adata.obs_names,
            columns=adata.var_names
        )
    else:
        expr_matrix = pd.DataFrame(
            adata.X,
            index=adata.obs_names,
            columns=adata.var_names
        )

    # Run inference
    algo = grnboost2 if method == "grnboost2" else genie3

    network = algo(
        expression_data=expr_matrix,
        tf_names=tf_names,
        verbose=verbose,
        seed=seed,
        client_or_address=client_or_address,
        num_workers=num_workers
    )

    if verbose:
        logger.info(f"GRN inference complete: {len(network)} adjacencies found")

    return network


# ============================================================================
# CisTarget Analysis
# ============================================================================

def run_cistarget(
    adjacencies: pd.DataFrame,
    database_path: Path,
    motif_annotations_path: Path,
    adata: Optional[sc.AnnData] = None,
    ex_mtx: Optional[pd.DataFrame] = None,
    num_workers: int = 4,
    client_or_address: str = "dask_multiprocessing",
    auc_threshold: float = 0.05,
    nes_threshold: float = 3.0,
    rank_threshold: int = 1500,
    motif_similarity_fdr: float = 0.001,
    orthologuous_identity_threshold: float = 0.0,
    weighted_recovery: bool = False,
    module_chunksize: int = 100,
    verbose: bool = True
) -> List:
    """
    Run cisTarget analysis to prune regulons using motif enrichment.

    This step validates TF-target relationships by checking if the target genes
    are enriched for TF binding motifs (indicating direct regulation).

    Parameters
    ----------
    adjacencies : pd.DataFrame
        Adjacencies from GRN inference with columns: TF, target, importance
    database_path : Path
        Path to cisTarget ranking database (.feather file).
        Download via download_databases() or check_database()
    motif_annotations_path : Path
        Path to motif-to-TF annotation file (.tbl file)
    adata : sc.AnnData, optional
        AnnData object with expression matrix. Required if ex_mtx not provided.
        Must be the same cells used for GRN inference.
    ex_mtx : pd.DataFrame, optional
        Expression matrix (cells x genes). Alternative to adata.
        If both provided, ex_mtx takes precedence.
    num_workers : int
        Number of parallel workers. Each requires ~4GB memory for database access
    client_or_address : str, default "dask_multiprocessing"
        Dask client address for distributed computing, or:
        - "dask_multiprocessing": Local multiprocessing via dask (default)
        - "custom_multiprocessing": Custom multiprocessing implementation
        - IP address for distributed cluster (e.g., "192.168.1.10:8786")
    auc_threshold : float, default 0.05
        Fraction of ranked genome for AUC calculation (top 5%).
        Lower = more stringent.
    nes_threshold : float, default 3.0
        Normalized Enrichment Score threshold. Higher values = more stringent.
        Only regulons with NES > threshold are retained.
    rank_threshold : int, default 1500
        Number of top-ranked genes to include in recovery curve.
    motif_similarity_fdr : float, default 0.001
        Maximum FDR for motif similarity (controls false positives).
    orthologuous_identity_threshold : float, default 0.0
        Minimum orthologous identity for motif transfer across species.
    weighted_recovery : bool, default False
        If True, weight genes by their confidence score in recovery curve.
    module_chunksize : int, default 100
        Chunk size for dask distributed processing.
    verbose : bool
        Print progress messages

    Returns
    -------
    List[Regulon]
        List of regulon objects, each with:
        - name: Regulon name with gene count (e.g., "SOX10 (45g)")
        - gene2weight: Dict mapping target genes to confidence scores
        - transcription_factor: The TF driving this regulon

    Notes
    -----
    - Requires cisTarget database (~1GB download)
    - Database options: 500bp (promoter-focused) or 10kb (includes enhancers)
    - Only regulons with significant motif enrichment (NES > 3) are retained
    - This function automatically calls modules_from_adjacencies internally

    Examples
    --------
    >>> regulons = run_cistarget(
    ...     adjacencies=adjacencies,
    ...     database_path="hg38_10kb.feather",
    ...     motif_annotations_path="motifs-v10.tbl",
    ...     adata=adata,
    ...     num_workers=4
    ... )
    >>> print(f"Found {len(regulons)} regulons")
    Found 156 regulons
    >>> print(regulons[0].name)
    SOX10 (45g)
    """
    if not PYSCENIC_AVAILABLE:
        raise ImportError("pySCENIC not installed")

    if adata is None and ex_mtx is None:
        raise ValueError("Either adata or ex_mtx must be provided for cisTarget module creation")

    if verbose:
        logger.info("Running cisTarget analysis...")
        logger.info(f"Database: {database_path}")

    # Prepare expression matrix
    if ex_mtx is None:
        if hasattr(adata.X, 'toarray'):
            ex_mtx = pd.DataFrame(
                adata.X.toarray(),
                index=adata.obs_names,
                columns=adata.var_names
            )
        else:
            ex_mtx = pd.DataFrame(
                adata.X,
                index=adata.obs_names,
                columns=adata.var_names
            )

    # Step 1: Create modules from adjacencies (required by prune2df)
    if verbose:
        logger.info("Creating co-expression modules from adjacencies...")

    modules = list(modules_from_adjacencies(adjacencies, ex_mtx))

    if verbose:
        logger.info(f"Created {len(modules)} modules")

    # Step 2: Open database and run pruning
    db = opendb(str(database_path))

    df = prune2df(
        rnkdbs=[db],
        modules=modules,
        motif_annotations_fname=str(motif_annotations_path),
        num_workers=num_workers,
        client_or_address=client_or_address,
        auc_threshold=auc_threshold,
        nes_threshold=nes_threshold,
        rank_threshold=rank_threshold,
        motif_similarity_fdr=motif_similarity_fdr,
        orthologuous_identity_threshold=orthologuous_identity_threshold,
        weighted_recovery=weighted_recovery,
        module_chunksize=module_chunksize
    )

    # Convert to regulons
    regulons = df2regulons(df)

    if verbose:
        logger.info(f"cisTarget complete: {len(regulons)} regulons identified")

    return regulons


# ============================================================================
# AUCell Scoring
# ============================================================================

def run_aucell(
    adata: sc.AnnData,
    regulons: List,
    auc_threshold: float = 0.05,
    noweights: bool = False,
    num_workers: int = 4,
    seed: int = 42,
    verbose: bool = True
) -> pd.DataFrame:
    """
    Run AUCell to score cells for regulon activity.

    AUCell calculates the enrichment of each regulon's target genes in the
    top-ranked genes of each cell. This represents the "activity" of the
    transcription factor in that cell.

    Parameters
    ----------
    adata : sc.AnnData
        AnnData object with expression matrix.
        Should be the same cells used for GRN inference.
    regulons : List[Regulon]
        List of regulons from cisTarget analysis
    auc_threshold : float, default 0.05
        Threshold for determining active regulons (top 5% of rankings).
        Cells with AUC > threshold are considered to have the regulon active.
    noweights : bool, default False
        If True, ignore confidence weights and treat all targets equally.
        If False, weight target genes by their confidence score.
    num_workers : int
        Number of parallel workers for ranking calculation
    seed : int
        Random seed for reproducibility
    verbose : bool
        Print progress messages

    Returns
    -------
    pd.DataFrame
        Cell-by-regulon AUC scores (n_cells × n_regulons).
        Index: cell barcodes from adata.obs_names
        Columns: regulon names (e.g., "SOX10 (45g)")
        Values: AUC scores ranging from 0 to 1

    Notes
    -----
    - AUC score interpretation:
      * 0.0-0.3: Inactive regulon
      * 0.3-0.5: Low activity
      * 0.5-0.8: Moderate activity (likely functional)
      * 0.8-1.0: High activity (regulon is a driver)
    - The ranking is based on gene expression within each cell
    - Uses the Area Under the recovery Curve (AUC) method

    Examples
    --------
    >>> auc_matrix = run_aucell(
    ...     adata=adata,
    ...     regulons=regulons,
    ...     num_workers=4,
    ...     seed=42
    ... )
    >>> auc_matrix.head()
              SOX10 (45g)  MITF (32g)  TFAP2A (28g)
    cell_1        0.234       0.189         0.045
    cell_2        0.876       0.754         0.123
    cell_3        0.456       0.321         0.567
    >>> print(f"Shape: {auc_matrix.shape}")  # (n_cells, n_regulons)
    Shape: (5000, 156)
    """
    if not PYSCENIC_AVAILABLE:
        raise ImportError("pySCENIC not installed")

    if verbose:
        logger.info("Running AUCell...")

    # Convert to dense if sparse
    if hasattr(adata.X, 'toarray'):
        expr_matrix = pd.DataFrame(
            adata.X.toarray(),
            index=adata.obs_names,
            columns=adata.var_names
        )
    else:
        expr_matrix = pd.DataFrame(
            adata.X,
            index=adata.obs_names,
            columns=adata.var_names
        )

    auc_matrix = aucell(
        exp_mtx=expr_matrix,
        signatures=regulons,
        auc_threshold=auc_threshold,
        noweights=noweights,
        num_workers=num_workers,
        seed=seed
    )

    if verbose:
        logger.info(f"AUCell complete: {auc_matrix.shape}")

    return auc_matrix


# ============================================================================
# Complete Pipeline
# ============================================================================

def run_pyscenic_pipeline(
    adata: sc.AnnData,
    organism: str = "human",
    db_type: str = "10kb",
    motif_version: str = "v10",
    grn_method: str = "grnboost2",
    num_workers: int = 4,
    seed: int = 42,
    download_if_missing: bool = True,
    verbose: bool = True
) -> Tuple[pd.DataFrame, List, pd.DataFrame]:
    """
    Run complete pySCENIC pipeline (GRN inference → cisTarget → AUCell).

    This is the main entry point for pySCENIC analysis, running all three
    steps of the pipeline:
    1. GRN inference: Infer TF-target co-expression networks
    2. cisTarget: Prune networks using motif enrichment analysis
    3. AUCell: Score cells for regulon activity

    Parameters
    ----------
    adata : sc.AnnData
        AnnData object with expression matrix (cells x genes).
        Requirements:
        - Gene names must be gene symbols (e.g., 'TP53', 'SOX10')
        - Minimum: ~100 cells, 5,000 genes for meaningful results
        - Raw counts or normalized data both acceptable
    organism : str
        Organism for cisTarget databases:
        - "human": hg38 reference genome
        - "mouse": mm10 reference genome
        - "fly": dm6 reference genome
    db_type : str
        cisTarget database type:
        - "500bp": 500bp upstream + 100bp downstream of TSS
                   (promoter-focused, stricter regulation)
        - "10kb": 10kb upstream + downstream of TSS
                  (includes enhancers, broader regulatory landscape)
        Recommended: "10kb" for initial screening, "500bp" for focused analysis
    motif_version : str
        Motif annotation version:
        - "v9": Classic motif annotations
        - "v10": Cluster-optimized motifs (recommended for better signal-to-noise)
    grn_method : str
        GRN inference algorithm:
        - "grnboost2": Fast gradient boosting, 2-5x faster, good for >10k cells
        - "genie3": Random forest, more accurate but slower, good for <5k cells
    num_workers : int
        Number of parallel workers. Memory requirements:
        - GRN inference: ~2GB per worker
        - cisTarget: ~4GB per worker
        - Default 4 workers requires ~16GB RAM total
        Reduce to 2 if memory limited.
    seed : int
        Random seed for reproducibility of GRN inference and AUCell ranking
    download_if_missing : bool
        If True, automatically download required databases if not cached
        If False, raise FileNotFoundError if databases are missing
    verbose : bool
        If True, print detailed progress messages for each pipeline step

    Returns
    -------
    Tuple[pd.DataFrame, List[Regulon], pd.DataFrame]
        Three pipeline outputs:
        1. adjacencies: DataFrame with TF-target relationships (TF, target, importance)
        2. regulons: List of motif-validated regulons with target genes
        3. auc_matrix: DataFrame with cell-by-regulon activity scores

    Notes
    -----
    - Databases are cached in ~/.pyscenic/ (~1GB per database)
    - Pipeline runtime: 1-4 hours for typical datasets (5k-20k cells)
    - Most time-consuming step: GRN inference (60-80% of total time)

    Examples
    --------
    >>> # Basic usage with automatic database download
    >>> adj, reg, auc = run_pyscenic_pipeline(
    ...     adata=adata,
    ...     organism="human",
    ...     db_type="10kb",
    ...     grn_method="grnboost2",
    ...     num_workers=4
    ... )
    Pipeline complete!
      - Adjacencies: 125000 edges
      - Regulons: 156 regulons identified
      - AUC matrix: (5000, 156)

    >>> # Small dataset with higher accuracy
    >>> adj, reg, auc = run_pyscenic_pipeline(
    ...     adata=small_adata,
    ...     organism="mouse",
    ...     db_type="500bp",
    ...     grn_method="genie3",
    ...     num_workers=4,
    ...     seed=42
    ... )
    """
    if not PYSCENIC_AVAILABLE:
        raise ImportError("pySCENIC not installed. Install with: pip install pyscenic")

    # Validate data size
    MIN_CELLS = 100
    MIN_GENES = 5000
    if adata.n_obs < MIN_CELLS:
        raise ValueError(
            f"adata has only {adata.n_obs} cells, minimum recommended is {MIN_CELLS}. "
            f"Regulon inference is underpowered with fewer cells."
        )
    if adata.n_vars < MIN_GENES:
        logger.warning(
            f"adata has only {adata.n_vars} genes, minimum recommended is {MIN_GENES}. "
            f"Results may be unreliable with fewer genes."
        )

    if verbose:
        logger.info("=" * 60)
        logger.info("Starting pySCENIC Pipeline")
        logger.info("=" * 60)

    # Check/download databases
    db_status = check_database(organism, db_type, motif_version)

    if not all([db_status["database"], db_status["motif_annotations"], db_status["tf_list"]]):
        if download_if_missing:
            logger.info("Downloading required databases...")
            db_paths = download_databases(organism, db_type, motif_version)
            db_path = db_paths["database"]
            motif_path = db_paths["motif_annotations"]
            tf_path = db_paths["tf_list"]
        else:
            raise FileNotFoundError("Required databases not found. Run download_databases() first.")
    else:
        db_path = db_status["db_path"]
        motif_path = db_status["motif_path"]
        tf_path = db_status["tf_path"]

    # Step 1: GRN inference
    if verbose:
        logger.info("\n[Step 1/3] GRN Inference")
        logger.info("-" * 40)

    adjacencies = run_grn_inference(
        adata=adata,
        tf_file=tf_path,
        method=grn_method,
        seed=seed,
        num_workers=num_workers,
        verbose=verbose
    )

    # Step 2: cisTarget
    if verbose:
        logger.info("\n[Step 2/3] cisTarget Analysis")
        logger.info("-" * 40)

    regulons = run_cistarget(
        adjacencies=adjacencies,
        database_path=db_path,
        motif_annotations_path=motif_path,
        adata=adata,
        num_workers=num_workers,
        verbose=verbose
    )

    # Step 3: AUCell
    if verbose:
        logger.info("\n[Step 3/3] AUCell Scoring")
        logger.info("-" * 40)

    auc_matrix = run_aucell(
        adata=adata,
        regulons=regulons,
        num_workers=num_workers,
        seed=seed,
        verbose=verbose
    )

    if verbose:
        logger.info("\n" + "=" * 60)
        logger.info("pySCENIC Pipeline Complete!")
        logger.info("=" * 60)
        logger.info(f"Adjacencies: {len(adjacencies)}")
        logger.info(f"Regulons: {len(regulons)}")
        logger.info(f"AUC matrix: {auc_matrix.shape}")

    return adjacencies, regulons, auc_matrix


# ============================================================================
# Result Export and Visualization
# ============================================================================

def add_aucell_to_adata(
    adata: sc.AnnData,
    auc_matrix: pd.DataFrame,
    assay_name: str = "X_aucell"
) -> sc.AnnData:
    """
    Add AUCell scores to AnnData object for easy visualization and analysis.

    Stores the AUC matrix in adata.obsm for compatibility with Scanpy visualization
    tools like sc.pl.umap() and sc.pl.violin().

    Parameters
    ----------
    adata : sc.AnnData
        Original AnnData object. Must have the same cells as auc_matrix.
    auc_matrix : pd.DataFrame
        AUC scores from run_aucell() or run_pyscenic_pipeline()
        Shape: (n_cells, n_regulons)
    assay_name : str, default "X_aucell"
        Key name for storing in adata.obsm
        Can be any string, common choices: "X_aucell", "SCENIC", "regulon_activity"

    Returns
    -------
    sc.AnnData
        Modified AnnData with:
        - adata.obsm[assay_name]: AUC scores matrix (n_cells × n_regulons)
        - adata.uns["regulon_names"]: List of regulon names

    Notes
    -----
    After adding, visualize with:
    - sc.pl.umap(adata, color=["SOX10 (45g)"])  # if UMAP exists
    - sc.pl.violin(adata, keys=["SOX10 (45g)"], groupby="cell_type")

    Examples
    --------
    >>> adata = add_aucell_to_adata(adata, auc_matrix, assay_name="SCENIC")
    Added AUCell scores to adata.obsm['SCENIC']
    >>> adata.obsm["SCENIC"].shape
    (5000, 156)
    >>> sc.pl.umap(adata, color=["SOX10 (45g)", "MITF (32g)"])
    """
    # Validate index match
    if not auc_matrix.index.equals(adata.obs_names):
        missing_in_auc = set(adata.obs_names) - set(auc_matrix.index)
        missing_in_adata = set(auc_matrix.index) - set(adata.obs_names)
        msg = "auc_matrix index does not match adata.obs_names."
        if missing_in_auc:
            msg += f" {len(missing_in_auc)} cells missing in auc_matrix."
        if missing_in_adata:
            msg += f" {len(missing_in_adata)} extra cells in auc_matrix."
        raise ValueError(msg)

    adata.obsm[assay_name] = auc_matrix.loc[adata.obs_names].values
    adata.uns["regulon_names"] = list(auc_matrix.columns)

    logger.info(f"Added AUCell scores to adata.obsm['{assay_name}']")
    return adata


def export_regulons_to_gmt(
    regulons: List,
    output_file: Path,
    min_genes: int = 5
) -> None:
    """
    Export regulons to GMT format for use with GSEA or other tools.

    GMT format: name\tdescription\tgene1\tgene2\t...
    One regulon per line, suitable for Gene Set Enrichment Analysis.

    Parameters
    ----------
    regulons : List[Regulon]
        List of regulons from run_cistarget() or run_pyscenic_pipeline()
    output_file : Path
        Output GMT file path (e.g., "regulons.gmt")
    min_genes : int, default 5
        Minimum number of target genes required to export a regulon.
        Regulons with fewer genes are skipped (often low confidence).
        Recommended: 5-10 genes for meaningful enrichment analysis

    Returns
    -------
    None
        Writes GMT file to disk.

    Notes
    -----
    GMT format is widely supported:
    - GSEA (Broad Institute)
    - clusterProfiler (R)
    - Enrichr
    - etc.

    Examples
    --------
    >>> export_regulons_to_gmt(regulons, "my_regulons.gmt", min_genes=10)
    Exported 142 regulons to my_regulons.gmt

    >>> # View GMT file format
    >>> with open("my_regulons.gmt") as f:
    ...     print(f.readline())
    SOX10 (45g)\t\tMITF\tDCT\tTYR\t...
    """
    if not regulons:
        logger.warning(f"No regulons to export. GMT file will be empty: {output_file}")

    exported_count = 0
    with open(output_file, 'w') as f:
        for regulon in regulons:
            genes = list(regulon.gene2weight.keys())
            if len(genes) >= min_genes:
                line = f"{regulon.name}\t\t" + "\t".join(genes) + "\n"
                f.write(line)
                exported_count += 1

    if exported_count == 0 and regulons:
        logger.warning(
            f"All {len(regulons)} regulons had fewer than {min_genes} genes. "
            f"Consider lowering min_genes. Empty GMT file written: {output_file}"
        )
    else:
        logger.info(f"Exported {exported_count} regulons to {output_file} (skipped {len(regulons) - exported_count} with < {min_genes} genes)")


def get_top_regulons_per_celltype(
    adata: sc.AnnData,
    celltype_col: str,
    auc_key: str = "X_aucell",
    top_n: int = 10
) -> pd.DataFrame:
    """
    Get top regulons by mean activity for each cell type.

    Identifies the most active regulons in each cell type by averaging
    AUC scores across cells within that type.

    Parameters
    ----------
    adata : sc.AnnData
        AnnData object with AUCell scores added via add_aucell_to_adata()
    celltype_col : str
        Column name in adata.obs containing cell type labels
        (e.g., "cell_type", "cluster", "seurat_clusters")
    auc_key : str, default "X_aucell"
        Key in adata.obsm where AUC scores are stored
        Must match the assay_name used in add_aucell_to_adata()
    top_n : int, default 10
        Number of top regulons to return per cell type
        Set higher (e.g., 20-50) for exploratory analysis

    Returns
    -------
    pd.DataFrame
        DataFrame with columns:
        - 'cell_type': Cell type label
        - 'regulon': Regulon name (e.g., "SOX10 (45g)")
        - 'mean_auc': Mean AUC score for this regulon in this cell type

    Notes
    -----
    - Only shows regulons with highest absolute activity per cell type
    - For differential analysis (cell type specific), use statistical tests
    - Consider both high mean_auc AND low mean_auc in other types

    Examples
    --------
    >>> top_regulons = get_top_regulons_per_celltype(
    ...     adata,
    ...     celltype_col="cell_type",
    ...     auc_key="X_aucell",
    ...     top_n=5
    ... )
    >>> print(top_regulons.head())
      cell_type        regulon   mean_auc
    0   T_cells   TBX21 (38g)      0.823
    1   T_cells    GATA3 (45g)      0.756
    2   B_cells   PAX5 (52g)       0.891
    3   B_cells  EBF1 (48g)       0.834
    """
    if celltype_col not in adata.obs.columns:
        raise ValueError(
            f"celltype_col '{celltype_col}' not found in adata.obs. "
            f"Available columns: {list(adata.obs.columns)}"
        )

    if auc_key not in adata.obsm:
        raise ValueError(
            f"auc_key '{auc_key}' not found in adata.obsm. "
            f"Run add_aucell_to_adata() first."
        )

    auc_matrix = pd.DataFrame(
        adata.obsm[auc_key],
        index=adata.obs_names,
        columns=adata.uns.get("regulon_names", [f"Regulon_{i}" for i in range(adata.obsm[auc_key].shape[1])])
    )

    results = []
    for celltype in adata.obs[celltype_col].unique():
        cells = adata.obs_names[adata.obs[celltype_col] == celltype]
        mean_auc = auc_matrix.loc[cells].mean().sort_values(ascending=False)

        for regulon in mean_auc.head(top_n).index:
            results.append({
                "cell_type": celltype,
                "regulon": regulon,
                "mean_auc": mean_auc[regulon]
            })

    return pd.DataFrame(results)


if __name__ == "__main__":
    # Example usage
    print("pySCENIC Analysis Module")
    print("\nAvailable functions:")
    print("- check_database()")
    print("- download_databases()")
    print("- run_grn_inference()")
    print("- run_cistarget()")
    print("- run_aucell()")
    print("- run_pyscenic_pipeline()")
    print("\nFor more info, see examples/ directory.")
