"""GEO-specific loaders for spatial transcriptomics non-standard formats.

Reference: scanpy 1.10+, anndata 0.10+, pandas 2.2+

Handles common GEO patterns for spatial data:
- GEO Visium: h5 file + spatial.tar.gz (not in standard outs/ structure)
- GEO Visium H5 only (no spatial images)
"""

import os
import tarfile
from pathlib import Path

import scanpy as sc

from utils import validate_file_exists


def prepare_geo_visium_dir(
    data_dir: str,
    output_dir: str = None,
) -> str:
    """Prepare GEO Visium directory for standard loading.

    GEO often provides Visium data as:
      - .h5 count file (e.g., GSM1234567_PA08.h5)
      - spatial.tar.gz (e.g., GSM1234567_PA08_spatial.tar.gz)

    This function restructures them into standard Space Ranger format:
      output_dir/
      ├── filtered_feature_bc_matrix.h5
      └── spatial/
          ├── tissue_positions_list.csv
          ├── scalefactors_json.json
          ├── tissue_lowres_image.png
          └── ...

    Parameters
    ----------
    data_dir : str
        Directory containing GEO files.
    output_dir : str, optional
        Where to create standard structure. If None, uses data_dir.

    Returns
    -------
    Path to the restructured directory ready for sc.read_visium().
    """
    validate_file_exists(data_dir, "GEO data directory")

    if output_dir is None:
        output_dir = data_dir

    # Create standard structure
    spatial_dir = os.path.join(output_dir, "spatial")
    os.makedirs(spatial_dir, exist_ok=True)

    # Find H5 file
    h5_files = [
        f for f in os.listdir(data_dir)
        if f.endswith(".h5") and not f.startswith(".")
    ]
    if len(h5_files) == 0:
        raise FileNotFoundError(f"No H5 file found in: {data_dir}")

    h5_path = os.path.join(data_dir, sorted(h5_files)[0])

    # Find and extract spatial tar.gz
    tar_files = [
        f for f in os.listdir(data_dir)
        if f.endswith(".tar.gz") and "spatial" in f.lower()
    ]

    if len(tar_files) > 0:
        print(f"Extracting spatial tar.gz: {tar_files[0]}")
        tar_path = os.path.join(data_dir, tar_files[0])

        with tarfile.open(tar_path, "r:gz") as tar:
            # Extract to temp first
            temp_dir = os.path.join(output_dir, ".geo_extract_temp")
            os.makedirs(temp_dir, exist_ok=True)
            tar.extractall(path=temp_dir)

            # Find standard spatial files
            spatial_files = []
            for root, _dirs, files in os.walk(temp_dir):
                for f in files:
                    if any(
                        pat in f
                        for pat in [
                            "tissue_positions",
                            "scalefactors",
                            "tissue_",
                            "detected_tissue_image",
                        ]
                    ):
                        spatial_files.append(os.path.join(root, f))

            if len(spatial_files) == 0:
                print("WARNING: No standard spatial files found in tar.gz. Using H5 only.")
            else:
                for f in spatial_files:
                    dst = os.path.join(spatial_dir, os.path.basename(f))
                    os.replace(f, dst)
                print(f"  Copied {len(spatial_files)} spatial files to spatial/")

            # Clean up temp
            import shutil

            shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        print("WARNING: No spatial.tar.gz found. Loading H5 only.")

    # Rename H5 to standard name
    target_h5 = os.path.join(output_dir, "filtered_feature_bc_matrix.h5")
    if os.path.abspath(h5_path) != os.path.abspath(target_h5):
        import shutil

        shutil.copy2(h5_path, target_h5)
        print(f"  Copied H5 to: {os.path.basename(target_h5)}")

    return output_dir


def load_geo_visium(
    data_dir: str,
    sample_id: str = None,
    prepare: bool = True,
) -> sc.AnnData:
    """Load GEO Visium data.

    Handles GEO non-standard Visium format by restructuring files
    and then calling sc.read_visium().

    Parameters
    ----------
    data_dir : str
        Directory containing GEO files (.h5 + spatial.tar.gz).
    sample_id : str, optional
        Sample identifier to add to metadata.
    prepare : bool, default True
        If True, restructure files first. If False, assume data_dir
        is already in standard format.

    Returns
    -------
    AnnData with spatial data.
    """
    if prepare:
        data_dir = prepare_geo_visium_dir(data_dir)

    adata = sc.read_visium(data_dir)

    if sample_id is not None:
        adata.obs["sample_id"] = sample_id

    print(f"Loaded GEO Visium: {adata.n_obs} spots x {adata.n_vars} genes")
    return adata


def load_geo_visium_h5(
    h5_path: str,
    sample_id: str = None,
) -> sc.AnnData:
    """Load GEO Visium H5 file only (no spatial images).

    For GEO entries that only provide the H5 count file without spatial data.

    Parameters
    ----------
    h5_path : str
        Path to .h5 file.
    sample_id : str, optional
        Sample identifier.

    Returns
    -------
    AnnData without spatial images.
    """
    validate_file_exists(h5_path, "H5 file")

    adata = sc.read_10x_h5(h5_path)
    adata.var_names_make_unique()

    if sample_id is not None:
        adata.obs["sample_id"] = sample_id

    print(
        f"Loaded GEO Visium H5: {adata.n_obs} spots x {adata.n_vars} genes "
        f"(no spatial images)"
    )
    return adata
