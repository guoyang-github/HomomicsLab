---
name: bio-single-cell-fastq2mtx
description: Generate gene expression count matrices from scRNA-seq FASTQ files using Cell Ranger or STARsolo. Supports single-sample and multi-sample processing via SampleSheet. Output is standard 10x MTX/h5 format ready for downstream data-io.
tool_type: cli
primary_tool: cellranger
supported_tools: [starsolo]
keywords: ["single-cell", "fastq", "cellranger", "starsolo", "alignment", "quantification", "10x", "count-matrix"]
multi_sample:
  supported: true
  input_format: samplesheet.csv
  formats: [fastq_dir]
---

## Version Compatibility

Reference examples tested with: Cell Ranger 8.0+, STAR 2.7.11b+, STARsolo

Before using code patterns, verify installed versions match:
- Cell Ranger: `cellranger --version`
- STAR: `STAR --version`

If versions differ, check `--help` output and adapt parameters to match the actual CLI rather than retrying.

## Skill Scope Definition

### What This Skill Covers
- FASTQ to count matrix alignment/quantification
- Cell Ranger `count` pipeline execution
- STARsolo alignment and UMI counting
- Single-sample and multi-sample batch submission
- Output validation (barcodes, features, matrix structure)

### What This Skill Does NOT Cover
- **Reference genome download/build** → Use provided scripts or download from 10x/Ensembl
- **Downstream analysis** → Use [bio-single-cell-data-io](../bio-single-cell-data-io/) to load output
- **Demultiplexing** → Assumes FASTQ files are already demultiplexed per sample
- **Multiome (RNA+ATAC)** → Cell Ranger `arc` not covered (RNA only)

### Workflow Position

```
[FASTQ raw data] → [bio-single-cell-fastq2mtx] → [bio-single-cell-data-io] → ...
        ↓                    ↓                           ↓
   原始测序数据        比对 + 定量生成矩阵           加载矩阵到 Seurat/Scanpy
```

### Input/Output State Mapping

| State | From | To | Description |
|-------|------|-----|-------------|
| [Raw FASTQ] | Sequencer | fastq2mtx | Raw `.fastq.gz` files |
| [Aligned] | fastq2mtx | fastq2mtx | BAM + count matrix |
| [MTX Output] | fastq2mtx | data-io | Standard 10x `filtered_feature_bc_matrix/` |

---

# Single-Cell FASTQ to Count Matrix

**"Quantify my scRNA-seq FASTQ files"** → Align reads and generate a UMI count matrix using Cell Ranger or STARsolo.
- Cell Ranger: `cellranger count --id=sample --transcriptome=ref --fastqs=dir`
- STARsolo: `STAR --soloType CB_UMI_Simple --readFilesIn R2.fastq.gz R1.fastq.gz`

Generate expression count matrices from raw single-cell RNA-seq FASTQ files.

---

## Input Format Requirements

### 10x Genomics FASTQ Naming Convention

Cell Ranger and STARsolo expect Illumina-standard FASTQ filenames:

```
{sample_name}_S1_L001_R1_001.fastq.gz   # Read 1: cell barcode + UMI (16bp + 10bp)
{sample_name}_S1_L001_R2_001.fastq.gz   # Read 2: cDNA insert
```

| Component | Meaning |
|-----------|---------|
| `{sample_name}` | Sample name (must match `--sample` argument) |
| `S1` | Sample number from sample sheet |
| `L001` | Lane number |
| `R1` / `R2` | Read 1 (barcode/UMI) / Read 2 (cDNA) |
| `001` | File segment |

**Important:** `R1` always contains the cell barcode and UMI; `R2` contains the biological read. Do not swap them.

### Directory Structure Example

```
fastqs/
├── PA08/
│   ├── PA08_S1_L001_R1_001.fastq.gz
│   ├── PA08_S1_L001_R2_001.fastq.gz
│   ├── PA08_S1_L002_R1_001.fastq.gz
│   └── PA08_S1_L002_R2_001.fastq.gz
└── PA11/
    ├── PA11_S1_L001_R1_001.fastq.gz
    ├── PA11_S1_L001_R2_001.fastq.gz
    └── ...
```

---

## Cell Ranger

**Goal:** Align reads and generate UMI count matrices using the 10x Genomics official pipeline.

**Approach:** Run `cellranger count` with a reference transcriptome. Outputs standard 10x MTX format compatible with downstream tools.

**Input State:** [Raw FASTQ] Demultiplexed `.fastq.gz` files
**Output State:** [MTX Output] Standard 10x `filtered_feature_bc_matrix/` directory

### Prerequisites

- Cell Ranger installed and on `PATH`
- Reference transcriptome (download from 10x Genomics or build custom)
- Linux environment (Cell Ranger is Linux-only; macOS requires Docker)

### Download Reference Transcriptome

```bash
# Human reference (GRCh38), ~10 GB
wget https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-GRCh38-2024-A.tar.gz
tar -xzvf refdata-gex-GRCh38-2024-A.tar.gz

# Mouse reference (mm10), ~10 GB
wget https://cf.10xgenomics.com/supp/cell-exp/refdata-gex-mm10-2020-A.tar.gz
tar -xzvf refdata-gex-mm10-2020-A.tar.gz
```

### Single Sample

```bash
cellranger count \
    --id=PA08 \
    --sample=PA08 \
    --transcriptome=/path/to/refdata-gex-GRCh38-2024-A \
    --fastqs=/path/to/fastqs/PA08 \
    --localcores=16 \
    --localmem=64
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--id` | string | Yes | - | Output directory name and run ID |
| `--sample` | string | Yes | - | Prefix of FASTQ files to analyze |
| `--transcriptome` | path | Yes | - | Path to reference transcriptome directory |
| `--fastqs` | path | Yes | - | Path to directory containing FASTQ files |
| `--localcores` | int | No | 16 | Max cores to use |
| `--localmem` | int | No | 64 | Max memory (GB) to use |
| `--expect-cells` | int | No | - | Expected number of recovered cells |
| `--chemistry` | string | No | auto | Chemistry configuration (SC3Pv3, SC3Pv2, etc.) |
| `--no-bam` | flag | No | false | Do not generate BAM file (saves space) |

| Output | Location | Description |
|--------|----------|-------------|
| Count matrix | `outs/filtered_feature_bc_matrix/` | Standard 10x MTX (cells x genes) |
| Count matrix (h5) | `outs/filtered_feature_bc_matrix.h5` | HDF5 format equivalent |
| BAM | `outs/possorted_genome_bam.bam` | Aligned reads |
| QC summary | `outs/metrics_summary.csv` | Cell-level and library-level metrics |
| Cloupe | `outs/cloupe.cloupe` | Loupe Browser file |

### Output Structure

```
PA08/
├── outs/
│   ├── filtered_feature_bc_matrix/
│   │   ├── barcodes.tsv.gz
│   │   ├── features.tsv.gz
│   │   └── matrix.mtx.gz
│   ├── filtered_feature_bc_matrix.h5
│   ├── metrics_summary.csv
│   ├── possorted_genome_bam.bam
│   └── web_summary.html
└── _cmdline  _log  _versions  ...
```

### Multi-Sample via SampleSheet

Use the provided script to batch-run Cell Ranger across multiple samples.

**SampleSheet Format (CSV):**

```csv
sample_id,fastq_dir,transcriptome,expect_cells,condition
PA08,fastqs/PA08,/ref/refdata-gex-GRCh38-2024-A,5000,High_NI
PA11,fastqs/PA11,/ref/refdata-gex-GRCh38-2024-A,5000,High_NI
PA02,fastqs/PA02,/ref/refdata-gex-GRCh38-2024-A,5000,High_NI
PA12,fastqs/PA12,/ref/refdata-gex-GRCh38-2024-A,5000,Low_NI
```

```bash
# Run batch pipeline
bash scripts/cellranger/run_count.sh samplesheet-fastq.csv --cores 16 --mem 64
```

Output directory structure after batch run:

```
results/
├── PA08/outs/filtered_feature_bc_matrix/
├── PA11/outs/filtered_feature_bc_matrix/
├── PA02/outs/filtered_feature_bc_matrix/
└── PA12/outs/filtered_feature_bc_matrix/
```

### Resource Requirements

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| CPU cores | 8 | 16-32 |
| Memory | 32 GB | 64-128 GB |
| Disk (per sample) | 50 GB | 100 GB |
| Wall time (per sample) | 4-6 hours | 2-4 hours (with 16+ cores) |

---

## STARsolo

**Goal:** Align reads and generate UMI count matrices using the open-source STARsolo pipeline.

**Approach:** Run `STAR` with `--soloType` options. STARsolo can produce output fully compatible with Cell Ranger's format.

**Input State:** [Raw FASTQ] Demultiplexed `.fastq.gz` files
**Output State:** [MTX Output] Standard 10x `filtered_feature_bc_matrix/` directory

### Prerequisites

- STAR installed and on `PATH`
- Reference genome index built with STAR (or download pre-built)

### Build Reference Genome Index

```bash
# Run the provided helper script
bash scripts/starsolo/make_index.sh \
    --genome-fasta /path/to/GRCh38.fa \
    --gtf /path/to/gencode.v45.annotation.gtf \
    --output-dir /path/to/star_index \
    --threads 16
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--genome-fasta` | path | Yes | Reference genome FASTA |
| `--gtf` | path | Yes | Gene annotation GTF |
| `--output-dir` | path | Yes | Where to write the index |
| `--threads` | int | No | Number of threads (default: 8) |

**Index size:** ~30 GB for human genome. Build once, reuse for all samples.

### Single Sample

```bash
bash scripts/starsolo/run_starsolo.sh \
    --index /path/to/star_index \
    --r1 fastqs/PA08/PA08_S1_L001_R1_001.fastq.gz \
    --r2 fastqs/PA08/PA08_S1_L001_R2_001.fastq.gz \
    --sample PA08 \
    --output-dir results/PA08 \
    --threads 16
```

For multiple lanes, concatenate in order:

```bash
bash scripts/starsolo/run_starsolo.sh \
    --index /path/to/star_index \
    --r1 fastqs/PA08/*_R1_*.fastq.gz \
    --r2 fastqs/PA08/*_R2_*.fastq.gz \
    --sample PA08 \
    --output-dir results/PA08 \
    --threads 16
```

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `--index` | path | Yes | - | Path to STAR genome index |
| `--r1` | path(s) | Yes | - | Read 1 FASTQ (barcode/UMI), space-separated if multiple |
| `--r2` | path(s) | Yes | - | Read 2 FASTQ (cDNA), space-separated if multiple |
| `--sample` | string | Yes | - | Sample name for output |
| `--output-dir` | path | Yes | - | Output directory |
| `--threads` | int | No | 8 | Number of threads |
| `--solo-features` | string | No | Gene | Features to count (Gene, GeneFull, SJ, etc.) |

### STARsolo Output Structure

```
results/PA08/
├── filtered_feature_bc_matrix/
│   ├── barcodes.tsv.gz
│   ├── features.tsv.gz
│   └── matrix.mtx.gz
├── Aligned.sortedByCoord.out.bam
├── Log.final.out
├── Solo.out/
│   ├── Gene/
│   │   ├── filtered/
│   │   └── raw/
│   └── Summary.csv
└── ...
```

### Convert to Cell-Ranger-Compatible Format

The script `run_starsolo.sh` automatically produces output in the standard 10x format. If running STAR manually, use these parameters for full compatibility:

```bash
STAR \
    --genomeDir /path/to/star_index \
    --readFilesIn R2.fastq.gz R1.fastq.gz \
    --readFilesCommand zcat \
    --soloType CB_UMI_Simple \
    --soloCBwhitelist /path/to/10x_v3_whitelist.txt \
    --soloFeatures Gene \
    --soloUMIlen 12 \
    --outFileNamePrefix results/PA08/ \
    --runThreadN 16
```

| Compatibility Parameter | Value | Description |
|------------------------|-------|-------------|
| `--readFilesIn` | `R2 R1` | STARsolo expects cDNA first, barcode second |
| `--soloType` | `CB_UMI_Simple` | Standard 10x format |
| `--soloFeatures` | `Gene` | Count reads per gene (like Cell Ranger) |
| `--soloUMIlen` | `12` | For 10x v3 chemistry |
| `--soloCBlen` | `16` | Cell barcode length (10x v3) |

### Resource Requirements

| Parameter | Minimum | Recommended |
|-----------|---------|-------------|
| CPU cores | 8 | 16-32 |
| Memory | 32 GB | 64-128 GB |
| Disk (per sample) | 50 GB | 100 GB |
| Wall time (per sample) | 1-3 hours | 1-2 hours (with 16+ cores) |

**Note:** STARsolo is typically **2-3x faster** than Cell Ranger but may require **more memory** for large genomes.

---

## Multi-Sample Batch Processing

### Using GNU Parallel

```bash
# Install: apt-get install parallel  or  conda install -c conda-forge parallel

cat samplesheet-fastq.csv | tail -n +2 | parallel --colsep ',' \
    'cellranger count --id={1} --sample={1} --transcriptome={3} --fastqs={2} --localcores=8 --localmem=32'
```

### Using Simple Loop

```bash
while IFS=',' read -r sample_id fastq_dir transcriptome expect_cells condition; do
    [[ "$sample_id" == "sample_id" ]] && continue  # skip header
    cellranger count \
        --id="$sample_id" \
        --sample="$sample_id" \
        --transcriptome="$transcriptome" \
        --fastqs="$fastq_dir" \
        --localcores=16 \
        --localmem=64
done < samplesheet-fastq.csv
```

---

## Output Validation

### Check Matrix Dimensions

```bash
# Python
python -c "import scanpy as sc; adata = sc.read_10x_mtx('PA08/outs/filtered_feature_bc_matrix/'); print(adata.shape)"

# R
R -e "library(Seurat); counts <- Read10X('PA08/outs/filtered_feature_bc_matrix/'); print(dim(counts))"
```

### Verify Expected Cell Counts

```bash
# Count barcodes
zcat PA08/outs/filtered_feature_bc_matrix/barcodes.tsv.gz | wc -l
```

### Compare to Cell Ranger Web Summary

Open `PA08/outs/web_summary.html` in a browser to view:
- Estimated number of cells
- Mean reads per cell
- Median genes per cell
- Sequencing saturation

---

## Method Comparison

| Feature | Cell Ranger | STARsolo |
|---------|-------------|----------|
| **License** | Commercial (free to use) | Open source (GPL) |
| **Speed** | Slower | 2-3x faster |
| **Memory** | Moderate (32-64 GB) | Higher (64-128 GB recommended) |
| **Output format** | Standard 10x MTX/h5 | Standard 10x MTX (with compatible params) |
| **BAM output** | Yes (sorted) | Yes (sorted) |
| **Web summary / QC** | Rich HTML report | Basic text logs |
| **Intron counting** | Yes (nuclear protocol) | Yes (`--soloFeatures GeneFull`) |
| **Custom references** | Supported | Supported |
| **Compatibility** | 10x official standard | Widely compatible |

**Recommendation:**
- Use **Cell Ranger** if you need the official 10x pipeline, web summary reports, or are submitting to journals requiring validated tools.
- Use **STARsolo** if you need faster turnaround, have compute resource constraints on time (not memory), or prefer fully open-source tools.

---

## Common Issues

### "Sample not found in input fastq files"
- Ensure `--sample` matches the prefix of FASTQ filenames exactly (case-sensitive)
- Check that FASTQ files are not nested inside additional subdirectories

### "Out of memory"
- Reduce `--localcores` (Cell Ranger) or `--runThreadN` (STAR)
- Request more memory from your job scheduler
- For STARsolo, consider `--genomeLoad NoSharedMemory` if running multiple instances

### "Empty filtered matrix"
- Check `web_summary.html` (Cell Ranger) or `Solo.out/Gene/Summary.csv` (STARsolo)
- Common causes: low sequencing depth, wrong chemistry (`--chemistry`), swapped R1/R2

---

## Related Skills

- **bio-single-cell-data-io** — Load the generated `filtered_feature_bc_matrix/` into Seurat or Scanpy
- **bio-single-cell-preprocessing** — QC filtering and normalization after loading
- **bio-single-cell-clustering** — Dimensionality reduction and clustering
