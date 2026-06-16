---
name: bio-spatial-transcriptomics-cnv-numbat-r
description: Haplotype-aware CNV calling from spatial transcriptomics using Numbat. Integrates gene expression, allelic ratio, and haplotype information to infer allele-specific CNVs and reconstruct clonal architecture.
tool_type: r
primary_tool: numbat
languages: [r]
keywords: ["spatial-transcriptomics", "CNV", "numbat", "haplotype-aware", "allele-specific", "copy-number", "clones", "Visium", "cancer"]
code_location: scripts/r/
version_compatibility:
  r: ">=4.2.0"
  numbat: ">=1.0"
---

# Spatial CNV Analysis with Numbat

## Version Compatibility

| Package | Required | Notes |
|---------|----------|-------|
| R | >= 4.2.0 | |
| numbat | >= 1.0 | Install from GitHub, NOT CRAN |
| data.table | >= 1.14 | Fast I/O |
| dplyr | >= 1.0 | Data manipulation |
| ggplot2 | >= 3.3 | Visualization |
| Seurat | >= 4.3 | Optional, for input objects |
| **cellsnp-lite** | required | External binary for SNP pileup |
| **eagle2** | required | External binary for phasing |
| **samtools** | required | External binary |

## Installation

```r
# Numbat is NOT on CRAN. Install from GitHub:
install.packages("devtools")
devtools::install_github("kharchenkolab/numbat")
```

External dependencies (install via conda or manually):

```bash
conda install -c bioconda cellsnp-lite samtools

# Eagle2 (download manually)
wget https://storage.googleapis.com/broad-alkesgroup-public/Eagle/downloads/Eagle_v2.4.1.tar.gz
tar -xvzf Eagle_v2.4.1.tar.gz

# Reference data
wget https://sourceforge.net/projects/cellsnp/files/SNPlist/genome1K.phase3.SNP_AF5e2.chr1toX.hg38.vcf.gz
wget http://pklab.med.harvard.edu/teng/data/1000G_hg38.zip && unzip 1000G_hg38.zip
```

Docker (recommended for dependency management):

```bash
docker run -v /work:/mnt/mydata -it pkharchenkolab/numbat-rbase:latest
```

## Skill Overview

**Use this skill when you need to:**
- Detect copy number variations (CNVs) in cancer spatial transcriptomics
- Distinguish maternal vs paternal allele-specific CNVs
- Reconstruct tumor clonal architecture and phylogeny
- Map CNVs and clones onto tissue spatial coordinates

**Do NOT use this skill when:**
- You only have gene expression without BAM files (no allele data possible)
- The tumor is known to be diploid / not aneuploid
- You need CNVs for non-human species (Numbat uses 1000G human reference)
- Allele depth (DP) is consistently < 3 per spot (insufficient coverage)

## Core Workflow

### Step 1: Generate Allele Counts [BAM] → [AlleleCounts]

Run SNP pileup and phasing from the BAM file produced by SpaceRanger. This is a **command-line step** that must be completed before entering R.

```bash
Rscript scripts/r/pileup_and_phase.R \
    --label Sample1 \
    --samples Sample1 \
    --bams /data/Sample1/outs/possorted_genome_bam.bam \
    --barcodes /data/Sample1/outs/filtered_feature_bc_matrix/barcodes.tsv.gz \
    --outdir ./numbat_preprocessing \
    --gmap /Eagle_v2.4.1/tables/genetic_map_hg38_withX.txt.gz \
    --snpvcf ~/numbat_ref/genome1K.phase3.SNP_AF5e2.chr1toX.hg38.vcf.gz \
    --paneldir ~/numbat_ref/1000G_hg38 \
    --ncores 4
```

**Required arguments:**

| Argument | Description |
|----------|-------------|
| `--label` | Individual identifier (one per patient) |
| `--samples` | Sample name(s); comma-delimited for multiple |
| `--bams` | BAM file path(s); comma-delimited |
| `--barcodes` | Barcode file(s); comma-delimited |
| `--outdir` | Output directory |
| `--gmap` | Eagle2 genetic map (e.g. `genetic_map_hg38_withX.txt.gz`) |
| `--snpvcf` | 1000G SNP VCF for pileup |
| `--paneldir` | 1000G phasing reference panel directory |

**Output:** `{sample}_allele_counts.tsv.gz` — phased allele counts per spot.

**⚠️ Critical:** This script calls internal Numbat functions (`numbat:::genotype`, `numbat:::preprocess_allele`). If Numbat updates its internal API, this script may break.

### Step 2: Prepare Expression Data [Seurat] → [CountMatrix]

Extract the gene × cell raw UMI count matrix. **Orientation must be genes as rows, cells as columns.**

```r
library(Seurat)
library(data.table)

# Load spatial data
seurat_obj <- Load10X_Spatial(data.dir = "./filtered_feature_bc_matrix/")

# Extract raw counts (gene × cell)
count_mat <- GetAssayData(seurat_obj, layer = "counts")

# Load allele counts
df_allele <- fread("Sample1_allele_counts.tsv.gz")

# Filter to spots that have allele data
cells_keep <- intersect(colnames(count_mat), unique(df_allele$cell))
count_mat <- count_mat[, cells_keep]
```

**⚠️ Critical:** `count_mat` must be **gene × cell** (not cell × gene). Numbat expects this orientation.

### Step 3: Prepare Reference [Seurat/AnnData] → [Reference]

Numbat needs a normal reference expression profile (`lambdas_ref`) to distinguish tumor from normal cells.

**Option A: Built-in HCA reference (human only, quick start)**

```r
data(ref_hca)
lambdas_ref <- ref_hca
```

**Option B: Custom reference from normal spots**

```r
source("scripts/r/numbat_spatial.R")

ref_custom <- aggregate_counts(
  count_mat = count_mat_normal,   # normal sample counts
  cell_annot = data.frame(
    cell = colnames(count_mat_normal),
    group = cluster_labels         # cluster or cell type labels
  ),
  normalize = TRUE                # produces CPM
)
```

| Reference Source | Quality | Notes |
|------------------|---------|-------|
| Matching normal Visium | **Best** | Same modality, minimal batch effect |
| scRNA-seq normal | Good | Ensure cell types are comparable |
| Built-in `ref_hca` | Acceptable | Quick start, may have batch effects |

### Step 4: Run Numbat [CountMatrix+AlleleCounts+Reference] → [NumbatObject]

```r
library(numbat)
source("scripts/r/numbat_spatial.R")

# Run with spatial-optimized defaults
nb <- run_numbat_spatial(
  count_mat = count_mat,
  lambdas_ref = lambdas_ref,
  df_allele = df_allele,
  genome = "hg38",
  max_entropy = 0.8,      # higher for sparse spatial data (default 0.5)
  t = 1e-5,               # HMM transition prob (lower = more breakpoints)
  gamma = 20,             # overdispersion (20 for UMI, 5 for non-UMI)
  ncores = 4,
  out_dir = "./numbat_output"
)
```

| Parameter | Default | Spatial Recommendation | Description |
|-----------|---------|------------------------|-------------|
| `max_entropy` | 0.5 | **0.8** | Tolerance for sparse allele data |
| `t` | 1e-5 | 1e-5 | Transition probability; 1e-6 for complex karyotypes |
| `gamma` | 20 | 20 | Allele overdispersion |
| `min_cells` | 50 | 50 | Minimum cells per CNV cluster |
| `init_k` | 3 | 3 | Initial number of clusters |

**Output:** Numbat R6 object with:
- `nb$clone_post` — clone assignments per spot
- `nb$joint_post` — per-event CNV probabilities
- `nb$segs_consensus` — consensus CNV segments
- `nb$gtree` — phylogenetic tree
- `nb$plot_phylo_heatmap()` — visualization method

### Step 5: Visualize on Tissue [NumbatObject] → [SpatialPlots]

```r
library(ggplot2)
library(data.table)

# Load spatial coordinates
spots <- fread("./spatial/tissue_positions.csv")

# CNV probability map
source("scripts/r/numbat_spatial.R")
plot_cnv_spatial(nb, spots, title = "Sample1")

# Clonal architecture map
plot_clone_spatial(nb, spots, title = "Clonal Architecture")
```

**⚠️ Critical:** `spots` dataframe must contain columns: `barcode`, `array_row`, `array_col`, `in_tissue`.

### Step 6: Export Results [NumbatObject] → [Files]

```r
export_numbat_results(
  nb,
  output_dir = "./numbat_export",
  prefix = "Sample1"
)
```

Exports: `clone_assignments.csv`, `cnv_events.csv`, `consensus_segments.csv`, `phylogeny.newick`.

## Complete Pipeline

```bash
# === PREPROCESSING (command line) ===
Rscript scripts/r/pileup_and_phase.R \
    --label Sample1 \
    --samples Sample1 \
    --bams /data/Sample1.bam \
    --barcodes /data/Sample1_barcodes.tsv \
    --outdir ./numbat_preprocessing \
    --gmap /ref/genetic_map_hg38_withX.txt.gz \
    --snpvcf /ref/genome1K.phase3.SNP_AF5e2.chr1toX.hg38.vcf.gz \
    --paneldir /ref/1000G_hg38 \
    --ncores 4
```

```r
# === ANALYSIS (R) ===
library(numbat)
library(Seurat)
library(data.table)
library(ggplot2)
source("scripts/r/numbat_spatial.R")

# Expression
count_mat <- GetAssayData(
  Load10X_Spatial("./filtered_feature_bc_matrix/"),
  layer = "counts"
)

# Alleles
df_allele <- fread("Sample1_allele_counts.tsv.gz")

# Reference
data(ref_hca)

# Filter to common spots
cells_keep <- intersect(colnames(count_mat), unique(df_allele$cell))
count_mat <- count_mat[, cells_keep]

# Run
nb <- run_numbat_spatial(
  count_mat = count_mat,
  lambdas_ref = ref_hca,
  df_allele = df_allele,
  out_dir = "./numbat_output"
)

# Plot on tissue
spots <- fread("./spatial/tissue_positions.csv")
plot_cnv_spatial(nb, spots)

# Export
export_numbat_results(nb, "./results", "Sample1")
```

## Skill-Provided Functions

### Analysis

| Function | Purpose |
|----------|---------|
| `run_numbat_spatial(count_mat, lambdas_ref, df_allele, ...)` | Run Numbat with spatial-optimized defaults (`max_entropy = 0.8`) |
| `aggregate_counts(count_mat, cell_annot, normalize = TRUE)` | Build reference expression profile by aggregating counts per cluster |
| `load_numbat_results(out_dir, i = 2)` | Load results from files into a list (not R6 object) |

### Export

| Function | Purpose |
|----------|---------|
| `export_numbat_results(nb, output_dir, prefix)` | Export clone assignments, CNV events, segments, phylogeny |

### Visualization

| Function | Purpose |
|----------|---------|
| `plot_cnv_spatial(nb, spots, title, ...)` | CNV probability map on tissue coordinates |
| `plot_clone_spatial(nb, spots, pal, title)` | Clone assignments on tissue coordinates |

## Official API — Agents Often Miss These

### 1. `numbat` is NOT on CRAN

```r
# WRONG — will fail
install.packages("numbat")

# CORRECT
devtools::install_github("kharchenkolab/numbat")
```

### 2. `count_mat` must be **gene × cell**

Numbat expects genes as rows and cells/spots as columns. Most single-cell objects store cell × gene. Transpose if needed:

```r
count_mat <- t(GetAssayData(seurat_obj, layer = "counts"))
```

### 3. `pileup_and_phase.R` uses internal Numbat functions

`numbat:::genotype()` and `numbat:::preprocess_allele()` are not exported. Future Numbat versions may rename or remove them.

### 4. `ref_hca` is human-only

For mouse or other species, you **must** build a custom reference with `aggregate_counts()`.

### 5. `load_numbat_results()` returns a list, not a Numbat R6 object

The returned list has `$clone_post`, `$joint_post`, `$segs_consensus`, `$gtree`, but it does **not** support R6 methods like `$plot_phylo_heatmap()`. Use the original `nb` object for plotting.

### 6. Seurat v5 changed `slot` to `layer`

```r
# Seurat v4
count_mat <- GetAssayData(seurat_obj, slot = "counts")

# Seurat v5 (still accepts slot with warning)
count_mat <- GetAssayData(seurat_obj, layer = "counts")
```

### 7. `run_numbat_spatial` passes `...` to `numbat::run_numbat()`

Any additional parameters accepted by `run_numbat()` (e.g., `min_LLR`, `tau`, `init_k`) can be passed through the wrapper:

```r
nb <- run_numbat_spatial(
  count_mat, lambdas_ref, df_allele,
  min_LLR = 10,
  tau = 0.3,
  init_k = 5
)
```

### 8. `plot_cnv_spatial` expects `array_row` / `array_col` in `spots`

The function uses hex-grid coordinates, not pixel coordinates. If you need to overlay on H&E, use `pxl_col_in_fullres` / `pxl_row_in_fullres` from `tissue_positions.csv` with standard `ggplot2` instead.

## Common Pitfalls

1. **⚠️ Forgetting the preprocessing step** — Numbat requires phased allele counts from `pileup_and_phase.R`. You cannot run `run_numbat` with expression data alone.

2. **⚠️ `count_mat` orientation** — Must be gene × cell. Many spatial objects are spot × gene. Always verify with `dim(count_mat)`.

3. **⚠️ Missing spots in allele data** — Filter `count_mat` to spots present in `df_allele` before running Numbat:
   ```r
   cells_keep <- intersect(colnames(count_mat), unique(df_allele$cell))
   count_mat <- count_mat[, cells_keep]
   ```

4. **⚠️ Normal reference contamination** — If the reference contains tumor cells, Numbat will fail to detect CNVs. Verify reference purity.

5. **⚠️ Low allele coverage** — Mean DP < 3 per spot leads to unreliable CNV calls. Check coverage before running:
   ```r
   mean(df_allele$DP)
   ```

6. **⚠️ Mixed spots show intermediate probabilities** — Visium spots may contain cells from multiple clones. These spots show `p_cnv ~ 0.5`. Do not force them into binary normal/mutant calls.

7. **⚠️ FFPE samples may have poor allele coverage** — Fresh frozen (FF) Visium is preferred. FFPE can work but often requires higher `max_entropy` (0.9).

## Troubleshooting

### No CNVs Detected

```r
# Check allele depth
mean(df_allele$DP)  # should be > 3

# More sensitive parameters
nb <- run_numbat_spatial(
  count_mat, lambdas_ref, df_allele,
  t = 1e-6,          # more breakpoints
  max_entropy = 0.9  # more tolerant
)
```

### Too Many False Positives

```r
nb <- run_numbat_spatial(
  count_mat, lambdas_ref, df_allele,
  t = 1e-4,          # fewer breakpoints
  min_LLR = 10       # higher evidence threshold
)
```

### Memory Issues

```r
nb <- run_numbat_spatial(
  count_mat, lambdas_ref, df_allele,
  ncores = 1         # reduce parallelization
)
```

### Poor Clone Separation

```r
nb <- run_numbat_spatial(
  count_mat, lambdas_ref, df_allele,
  init_k = 5         # more initial clusters
)
```

## Related Skills

- [bio-single-cell-cnv-infercnv-r](../bio-single-cell-cnv-infercnv-r) — Alternative CNV caller (expression-only)
- [bio-single-cell-cnv-copykat-r](../bio-single-cell-cnv-copykat-r) — CNV calling without allele info
- [bio-spatial-transcriptomics-cnv-fastcnv-r](../bio-spatial-transcriptomics-cnv-fastcnv-r) — Fast CNV for spatial
- [bio-single-cell-cnv-scevan-r](../bio-single-cell-cnv-scevan-r) — SCEVAN CNV caller

## References

1. Gao et al. (2022). Haplotype-aware analysis of somatic copy number variations from single-cell transcriptomes. *Nature Biotechnology*, 40(11), 1608-1618.
2. Li et al. (2025). Numbat-multiome: inferring copy number variations by combining RNA and chromatin accessibility information from single-cell data. *Briefings in Bioinformatics*, 26(5), bbaf516.
3. Numbat Documentation: https://kharchenkolab.github.io/numbat/
4. Numbat GitHub: https://github.com/kharchenkolab/numbat
5. Spatial Transcriptomics Vignette: https://kharchenkolab.github.io/numbat/articles/spatial-rna.html
