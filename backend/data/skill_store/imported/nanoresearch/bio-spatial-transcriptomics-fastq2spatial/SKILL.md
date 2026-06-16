---
name: bio-spatial-transcriptomics-fastq2spatial
description: Generate spatial gene expression count matrices from spatial transcriptomics FASTQ files using Space Ranger or Spacemake. Supports Visium (brightfield and fluorescence), Visium HD, and Slide-seq. Output is standard Space Ranger format with spatial coordinates and tissue images, ready for downstream data-io.
tool_type: cli
primary_tool: spaceranger
supported_tools: [spacemake]
keywords: ["spatial", "fastq", "spaceranger", "spacemake", "visium", "alignment", "quantification", "spatial-transcriptomics", "count-matrix"]
multi_sample:
  supported: true
  input_format: samplesheet.csv
  formats: [fastq_dir]
---

## Version Compatibility

Reference examples tested with: Space Ranger 3.0+, Spacemake 0.7+

Before using code patterns, verify installed versions match:
- Space Ranger: `spaceranger --version`
- Spacemake: `spacemake --version`

If versions differ, check `--help` output and adapt parameters to match the actual CLI rather than retrying.

## Skill Scope Definition

### What This Skill Covers
- FASTQ + tissue image to spatial count matrix alignment/quantification
- Space Ranger `count` pipeline for Visium (brightfield and CytAssist)
- Spacemake workflow for Visium, Slide-seq, and custom spatial platforms
- Single-sample and multi-sample batch submission
- Output validation (spatial coordinates, tissue image alignment)

### What This Skill Does NOT Cover
- **Reference genome download/build** → Use provided scripts or download from 10x/Ensembl
- **Tissue image preprocessing** → Assumes H&E or fluorescence images are ready
- **Manual fiducial alignment** → Use Loupe Browser for manual alignment if automatic fails
- **Downstream analysis** → Use [bio-spatial-transcriptomics-data-io](../bio-spatial-transcriptomics-data-io/) to load output
- **Multiome (RNA+ATAC) spatial** → Space Ranger `multi` not covered

### Workflow Position

```
[FASTQ + Image] → [bio-spatial-transcriptomics-fastq2spatial] → [bio-spatial-transcriptomics-data-io] → ...
       ↓                      ↓                                   ↓
  原始测序数据          比对 + 空间定量生成矩阵              加载矩阵到 Seurat/Scanpy/Squidpy
```

### Input/Output State Mapping

| State | From | To | Description |
|-------|------|-----|-------------|
| [Raw FASTQ] | Sequencer | fastq2spatial | Raw `.fastq.gz` files |
| [Tissue Image] | Microscope | fastq2spatial | H&E `.tif` or fluorescence `.tif` |
| [Aligned] | fastq2spatial | fastq2spatial | BAM + spatial count matrix |
| [Spatial Output] | fastq2spatial | data-io | Standard Space Ranger output with `spatial/` |

---

# Spatial Transcriptomics FASTQ to Spatial Count Matrix

**"Quantify my Visium spatial data"** → Align spatial transcriptomics reads and generate a UMI count matrix with spatial coordinates using Space Ranger or Spacemake.
- Space Ranger: `spaceranger count --id=sample --transcriptome=ref --fastqs=dir --image=image.tif`
- Spacemake: `spacemake init` → `spacemake run_sample --sample=sample`

Generate spatially-resolved expression count matrices from raw spatial transcriptomics FASTQ files and tissue images.

---

## Input Format Requirements

### 10x Visium FASTQ Naming Convention

Space Ranger expects the same Illumina-standard FASTQ filenames as Cell Ranger:

```
{sample_name}_S1_L001_R1_001.fastq.gz   # Read 1: spatial barcode + UMI
{sample_name}_S1_L001_R2_001.fastq.gz   # Read 2: cDNA insert
```

### Tissue Image Requirements

| Platform | Image Type | Format | Requirements |
|----------|-----------|--------|--------------|
| **Visium (standard)** | Brightfield H&E | `.tif` or `.jpg` | Minimum 2000x2000 pixels, full resolution |
| **Visium (CytAssist)** | Brightfield H&E | `.tif` | CytAssist capture area visible, proper orientation |
| **Visium (fluorescence)** | Multi-channel IF | `.tif` | One or more channels, DAPI required |
| **Visium HD** | Brightfield H&E | `.tif` | 2x2 um barcode binning |

**Image registration:** Space Ranger automatically aligns the tissue image to the fiducial frame using the corner fiducials. If automatic alignment fails, use Loupe Browser to create a `.json` alignment file and pass it via `--loupe-alignment`.

### Directory Structure Example

```
project/
├── fastqs/
│   ├── PA08/
│   │   ├── PA08_S1_L001_R1_001.fastq.gz
│   │   └── PA08_S1_L001_R2_001.fastq.gz
│   └── PA11/
│       ├── PA11_S1_L001_R1_001.fastq.gz
│       └── PA11_S1_L001_R2_001.fastq.gz
├── images/
│   ├── PA08_tissue.tif
│   └── PA11_tissue.tif
└── loupe_alignments/  (optional, for manual alignment)
    ├── PA08_alignment.json
    └── PA11_alignment.json
```

---

## Space Ranger

**Goal:** Align spatial transcriptomics reads and generate UMI count matrices with spatial coordinates using the 10x Genomics official pipeline.

**Approach:** Run `spaceranger count` with a reference transcriptome, FASTQ files, and a tissue image. Outputs standard Space Ranger format with `spatial/` directory.

**Input State:** [Raw FASTQ] + [Tissue Image] Demultiplexed `.fastq.gz` and `.tif`
**Output State:** [Spatial Output] Standard Space Ranger output with `filtered_feature_bc_matrix/` + `spatial/`

### Prerequisites

- Space Ranger installed and on `PATH`
- Reference transcriptome (download from 10x Genomics or build custom)
- Tissue image (H&E or fluorescence)
- Linux environment (Space Ranger is Linux-only)

### Download Reference Transcriptome

```bash
# Human reference (GRCh38), ~10 GB
wget https://cf.10xgenomics.com/supp/spatial-exp/refdata-gex-GRCh38-2020-A.tar.gz
tar -xzvf refdata-gex-GRCh38-2020-A.tar.gz

# Mouse reference (mm10), ~10 GB
wget https://cf.10xgenomics.com/supp/spatial-exp/refdata-gex-mm10-2020-A.tar.gz
tar -xzvf refdata-gex-mm10-2020-A.tar.gz
```

### Single Sample (Brightfield H&E)

```bash
spaceranger count \
    --id=PA08 \
    --sample=PA08 \
    --transcriptome=/path/to/refdata-gex-GRCh38-2020-A \
    --fastqs=/path/to/fastqs/PA08 \
    --image=/path/to/images/PA08_tissue.tif \
    --slide=V19L01-041 \
    --area=A1 \
    --localcores=16 \
    --localmem=64
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--id` | string | Yes | - | Output directory name and run ID |
| `--sample` | string | Yes | - | Prefix of FASTQ files to analyze |
| `--transcriptome` | path | Yes | - | Path to reference transcriptome directory |
| `--fastqs` | path | Yes | - | Path to directory containing FASTQ files |
| `--image` | path | Yes* | - | Path to brightfield H&E image (`.tif` or `.jpg`) |
| `--darkimage` | path | Yes* | - | Path to fluorescence image (for IF experiments) |
| `--slide` | string | No | - | Slide serial number (e.g., `V19L01-041`) |
| `--area` | string | No | - | Capture area identifier (e.g., `A1`, `B1`, `C1`, `D1`) |
| `--loupe-alignment` | path | No | - | JSON alignment file from Loupe Browser |
| `--localcores` | int | No | 16 | Max cores to use |
| `--localmem` | int | No | 64 | Max memory (GB) to use |
| `--cytaimage` | path | No | - | CytAssist captured image |

*Either `--image` (brightfield) or `--darkimage` (fluorescence) is required.

**Slide/Area lookup:** If you know the slide serial number and capture area, provide both. If unknown, omit both and Space Ranger will attempt automatic detection (requires `.tif` with proper metadata).

### Single Sample (Fluorescence)

```bash
spaceranger count \
    --id=PA08_IF \
    --sample=PA08 \
    --transcriptome=/path/to/refdata-gex-GRCh38-2020-A \
    --fastqs=/path/to/fastqs/PA08 \
    --darkimage=/path/to/images/PA08_dapi.tif \
    --darkimage=/path/to/images/PA08_cd45.tif \
    --slide=V19L01-041 \
    --area=A1 \
    --localcores=16 \
    --localmem=64
```

### Using Manual Alignment (Loupe Browser)

If automatic fiducial alignment fails:

1. Open Loupe Browser (download from 10x Genomics)
2. Load the tissue image and manually align fiducials
3. Export alignment as `.json`
4. Pass to Space Ranger:

```bash
spaceranger count \
    --id=PA08 \
    --sample=PA08 \
    --transcriptome=/path/to/refdata-gex-GRCh38-2020-A \
    --fastqs=/path/to/fastqs/PA08 \
    --image=/path/to/images/PA08_tissue.tif \
    --loupe-alignment=/path/to/PA08_alignment.json \
    --localcores=16 \
    --localmem=64
```

### Output Structure

```
PA08/
├── outs/
│   ├── filtered_feature_bc_matrix/
│   │   ├── barcodes.tsv.gz
│   │   ├── features.tsv.gz
│   │   └── matrix.mtx.gz
│   ├── filtered_feature_bc_matrix.h5
│   ├── spatial/
│   │   ├── tissue_positions_list.csv    # Spot barcodes + pixel coordinates
│   │   ├── tissue_positions.parquet     # Parquet format (Space Ranger 2.0+)
│   │   ├── scalefactors_json.json       # Scale factors for hires/lowres images
│   │   ├── tissue_lowres_image.png      # Low-res tissue image
│   │   ├── tissue_hires_image.png       # High-res tissue image
│   │   └── aligned_fiducials.jpg        # Fiducial alignment visualization
│   ├── web_summary.html
│   ├── metrics_summary.csv
│   └── possorted_genome_bam.bam
└── _cmdline  _log  _versions  ...
```

### Multi-Sample via SampleSheet

Use the provided script to batch-run Space Ranger across multiple samples.

**SampleSheet Format (CSV):**

```csv
sample_id,fastq_dir,image_path,transcriptome,slide,area,condition
PA08,fastqs/PA08,images/PA08_tissue.tif,/ref/refdata-gex-GRCh38-2020-A,V19L01-041,A1,High_NI
PA11,fastqs/PA11,images/PA11_tissue.tif,/ref/refdata-gex-GRCh38-2020-A,V19L01-041,B1,High_NI
PA02,fastqs/PA02,images/PA02_tissue.tif,/ref/refdata-gex-GRCh38-2020-A,V19L01-042,A1,Low_NI
PA12,fastqs/PA12,images/PA12_tissue.tif,/ref/refdata-gex-GRCh38-2020-A,V19L01-042,B1,Low_NI
```

```bash
# Run batch pipeline
bash scripts/spaceranger/run_count.sh samplesheet-spatial.csv --cores 16 --mem 64
```

Output directory structure after batch run:

```
results/
├── PA08/outs/filtered_feature_bc_matrix/
├── PA08/outs/spatial/
├── PA11/outs/filtered_feature_bc_matrix/
├── PA11/outs/spatial/
└── ...
```

### Resource Requirements

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| CPU cores | 8 | 16-32 |
| Memory | 32 GB | 64-128 GB |
| Disk (per sample) | 100 GB | 200 GB |
| Wall time (per sample) | 6-12 hours | 3-6 hours (with 16+ cores) |

---

## Spacemake

**Goal:** Align spatial transcriptomics reads and generate count matrices using the open-source Spacemake workflow.

**Approach:** Initialize a Spacemake project, add samples to the config, and run the Snakemake pipeline. Supports Visium, Slide-seq, and custom spatial barcodes.

**Input State:** [Raw FASTQ] + [Tissue Image] (for Visium)
**Output State:** [Spatial Output] AnnData `.h5ad` files + standard MTX output

### Prerequisites

- Spacemake installed (via pip or conda)
- Snakemake installed
- STAR installed (for alignment)

### Install Spacemake

```bash
# Via pip
pip install spacemake

# Or via conda
conda install -c bioconda spacemake
```

### Initialize Project

```bash
# Run the provided helper script
bash scripts/spacemake/init_project.sh \
    --project-dir /path/to/spacemake_project \
    --species human \
    --genome-fasta /path/to/GRCh38.fa \
    --gtf /path/to/gencode.v45.annotation.gtf
```

### Project Structure

```
spacemake_project/
├── config.yaml              # Spacemake configuration
├── samples.csv              # Sample definitions
├── species_data/
│   └── human/               # STAR index and annotation
│       ├── star_index/
│       └── annotation.gtf
└── projects/
    └── default/
        └── processed_data/  # Output goes here
```

### Add Sample and Run

```bash
# Add a Visium sample
spacemake projects add_sample \
    --project default \
    --sample_id PA08 \
    --R1 fastqs/PA08/PA08_S1_L001_R1_001.fastq.gz \
    --R2 fastqs/PA08/PA08_S1_L001_R2_001.fastq.gz \
    --species human \
    --puck visium \
    --run_mode visium

# Run the pipeline
spacemake run \
    --cores 16 \
    --knit \
    --sample_id PA08
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--project` | string | Yes | Project name (default: `default`) |
| `--sample_id` | string | Yes | Unique sample identifier |
| `--R1` | path | Yes | Read 1 FASTQ (barcode/UMI) |
| `--R2` | path | Yes | Read 2 FASTQ (cDNA) |
| `--species` | string | Yes | Species name (must match config) |
| `--puck` | string | Yes | Puck/barcode type (`visium`, `slide_seq`, `custom`) |
| `--run_mode` | string | Yes | Analysis mode (`visium`, `scRNA-seq`, `processed`) |
| `--dge` | flag | No | Run digital gene expression quantification |

### Spacemake Output Structure

```
spacemake_project/projects/default/processed_data/
├── PA08/
│   ├── adatas/
│   │   └── PA08_visium.h5ad          # Main output: AnnData with spatial coords
│   ├── bam/
│   │   └── PA08_aligned.bam
│   ├── dge/
│   │   └── PA08_visium.dge.txt.gz    # DGE matrix (spots x genes)
│   ├── logs/
│   └── summary/
│       └── PA08_visium_summary.pdf   # QC summary plots
```

### Multi-Sample via SampleSheet

Spacemake uses a `samples.csv` file for batch processing:

```bash
# Generate samples.csv from template
bash scripts/spacemake/run_spacemake.sh \
    --project-dir /path/to/spacemake_project \
    --samplesheet samplesheet-spacemake.csv \
    --cores 16
```

**SampleSheet Format (CSV) for Spacemake:**

```csv
sample_id,R1,R2,species,puck,run_mode,condition
PA08,fastqs/PA08_R1.fastq.gz,fastqs/PA08_R2.fastq.gz,human,visium,visium,High_NI
PA11,fastqs/PA11_R1.fastq.gz,fastqs/PA11_R2.fastq.gz,human,visium,visium,High_NI
PA02,fastqs/PA02_R1.fastq.gz,fastqs/PA02_R2.fastq.gz,human,visium,visium,Low_NI
```

### Resource Requirements

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| CPU cores | 8 | 16-32 |
| Memory | 32 GB | 64-128 GB |
| Disk (per sample) | 50 GB | 100 GB |
| Wall time (per sample) | 4-8 hours | 2-4 hours (with 16+ cores) |

---

## Output Validation

### Check Matrix Dimensions

```bash
# Python
python -c "
import scanpy as sc
adata = sc.read_visium('PA08/outs/')
print(f'PA08: {adata.n_obs} spots x {adata.n_vars} genes')
print(f'Spatial coords: {adata.obsm[\"spatial\"].shape}')
"

# R
R -e "
library(Seurat)
obj <- Load10X_Spatial('PA08/outs/')
print(dim(obj))
"
```

### Verify Spatial Coordinates

```bash
# Check tissue_positions_list.csv
head PA08/outs/spatial/tissue_positions_list.csv

# Expected columns (Space Ranger < 2.0):
# barcode,in_tissue,array_row,array_col,pxl_col_in_fullres,pxl_row_in_fullres

# Expected columns (Space Ranger >= 2.0, parquet format):
# barcode,in_tissue,array_row,array_col,pxl_col_in_fullres,pxl_row_in_fullres
```

### Verify Tissue Image Alignment

Open `PA08/outs/spatial/aligned_fiducials.jpg` to visually confirm fiducial alignment. If alignment is poor, re-run with `--loupe-alignment`.

### Compare to Space Ranger Web Summary

Open `PA08/outs/web_summary.html` in a browser to view:
- Number of spots under tissue
- Mean reads per spot
- Median genes per spot
- Sequencing saturation
- Tissue coverage plot

---

## Method Comparison

| Feature | Space Ranger | Spacemake |
|---------|--------------|-----------|
| **License** | Commercial (free to use) | Open source (MIT) |
| **Platforms** | Visium, Visium HD | Visium, Slide-seq, custom pucks |
| **Speed** | Standard | Comparable |
| **Memory** | Moderate (64-128 GB) | Moderate (64-128 GB) |
| **Output format** | Standard Space Ranger (`spatial/` + MTX) | AnnData `.h5ad` + MTX |
| **Web summary** | Rich HTML report | PDF summary |
| **Fluorescence support** | Yes (`--darkimage`) | Limited |
| **CytAssist support** | Yes | Via Visium mode |
| **Custom barcodes** | No | Yes |
| **Slide-seq support** | No | Yes |

**Recommendation:**
- Use **Space Ranger** for standard Visium workflows requiring official 10x outputs, web summaries, or CytAssist/fluorescence support.
- Use **Spacemake** for non-standard platforms (Slide-seq), custom spatial barcodes, or when you prefer a fully open-source Snakemake workflow with AnnData output.

---

## Common Issues

### "Fiducial alignment failed"
- Check image quality and orientation
- Ensure fiducials are visible at the corners of the capture area
- Try manual alignment in Loupe Browser and pass `--loupe-alignment`

### "Slide/area not found in image metadata"
- Provide `--slide` and `--area` explicitly
- Or omit both and let Space Ranger attempt auto-detection

### "Out of memory"
- Reduce `--localcores` / `--cores`
- Request more memory from your job scheduler
- For large Visium HD samples, use 128+ GB RAM

### "Empty tissue coverage"
- Check `web_summary.html` for sequencing depth
- Common causes: low sequencing depth, wrong chemistry, poor tissue quality

---

## Related Skills

- **bio-spatial-transcriptomics-data-io** — Load the generated Space Ranger output into Seurat, Scanpy, or Squidpy
- **bio-spatial-transcriptomics-preprocessing** — QC filtering and normalization after loading
- **bio-spatial-transcriptomics-neighbors** — Spatial neighbor analysis after preprocessing
