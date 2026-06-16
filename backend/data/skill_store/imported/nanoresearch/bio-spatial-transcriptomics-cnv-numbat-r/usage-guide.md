# Numbat Spatial Transcriptomics - Usage Guide

Complete guide for haplotype-aware CNV calling from spatial transcriptomics data using Numbat.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Data Preparation](#data-preparation)
4. [Quick Start](#quick-start)
5. [Step-by-Step Analysis](#step-by-step-analysis)
6. [Visualization](#visualization)
7. [Multi-Sample Analysis](#multi-sample-analysis)
8. [Troubleshooting](#troubleshooting)
9. [Complete Example](#complete-example)

---

## Overview

Numbat is a haplotype-aware CNV caller that integrates gene expression, allelic ratio, and population-derived haplotype information to infer allele-specific CNVs in spatial transcriptomics data.

### Key Features

- **Allele-specific CNVs**: Distinguishes maternal vs paternal allele copy numbers
- **Clonal architecture**: Reconstructs tumor phylogeny and subclones
- **Spatial context**: Maps CNVs and clones onto tissue architecture
- **No DNA required**: Works solely on RNA-seq data

### When to Use Numbat for Spatial Data

| Scenario | Recommended | Notes |
|----------|-------------|-------|
| Visium (fresh frozen) | ✅ Yes | 1-10 cells/spot, good allele coverage |
| Visium FFPE | ⚠️ Limited | May have lower allele coverage |
| Slide-seqV2 | ✅ Yes | Near single-cell resolution |
| Stereo-seq | ✅ Yes | Subcellular resolution |
| Xenium | ⚠️ Limited | Limited allele info currently |

### Assumptions for Spatial Data

> Most spots contain cells from the same clone (genetic homogeneity within spot). Mixed spots will show intermediate CNV probabilities (~0.5).

---

## Installation

### Option 1: Docker (Recommended)

```bash
# Pull and run Docker container
docker run -v /work:/mnt/mydata -it pkharchenkolab/numbat-rbase:latest /bin/bash

# Inside container, tools are pre-installed:
# - cellsnp-lite, eagle2, samtools
# - 1000G reference files in /data/
```

### Option 2: Manual Installation

**1. Install R package:**

```r
install.packages('numbat', dependencies = TRUE)

# Or latest GitHub version:
devtools::install_github("https://github.com/kharchenkolab/numbat")
```

**2. Install external dependencies:**

```bash
# Install cellsnp-lite
conda install -c bioconda cellsnp-lite

# Install eagle2
wget https://storage.googleapis.com/broad-alkesgroup-public/Eagle/downloads/Eagle_v2.4.1.tar.gz
tar -xvzf Eagle_v2.4.1.tar.gz

# Install samtools
conda install -c bioconda samtools
```

**3. Download reference data:**

```bash
# Create reference directory
mkdir -p ~/numbat_ref && cd ~/numbat_ref

# Download SNP VCF
wget https://sourceforge.net/projects/cellsnp/files/SNPlist/genome1K.phase3.SNP_AF5e2.chr1toX.hg38.vcf.gz

# Download phasing reference panel
wget http://pklab.med.harvard.edu/teng/data/1000G_hg38.zip
unzip 1000G_hg38.zip
```

---

## Data Preparation

### Input Files Required

| File | Source | Description |
|------|--------|-------------|
| BAM | SpaceRanger | Aligned reads with CB/UB tags |
| Barcodes | SpaceRanger | Cell/spots barcode list |
| Gene expression | SpaceRanger | Raw count matrix |
| Reference | HCA or custom | Normal cell expression profile |

### Step 1: Run pileup_and_phase

```bash
# Using the script provided in this skill
Rscript scripts/r/pileup_and_phase.R \
    --label Sample1 \
    --samples Sample1 \
    --bams /data/Sample1/outs/possorted_genome_bam.bam \
    --barcodes /data/Sample1/outs/filtered_feature_bc_matrix/barcodes.tsv.gz \
    --outdir ./numbat_preprocessing/Sample1 \
    --gmap /Eagle_v2.4.1/tables/genetic_map_hg38_withX.txt.gz \
    --snpvcf ~/numbat_ref/genome1K.phase3.SNP_AF5e2.chr1toX.hg38.vcf.gz \
    --paneldir ~/numbat_ref/1000G_hg38 \
    --ncores 8
```

**Output files:**
- `Sample1_allele_counts.tsv.gz` - Phased allele counts (main output)
- `phasing/` - Phased VCF files
- `pileup/` - Raw pileup counts

**For multiple samples from same patient:**

```bash
Rscript pileup_and_phase.R \
    --label Patient1 \
    --samples "Sample1,Sample2,Sample3" \
    --bams "S1.bam,S2.bam,S3.bam" \
    --barcodes "S1_barcodes.tsv,S2_barcodes.tsv,S3_barcodes.tsv" \
    --outdir ./numbat_preprocessing/Patient1 \
    ...
```

### Step 2: Verify Allele Data Quality

```r
library(data.table)

# Load allele counts
df_allele <- fread("Sample1_allele_counts.tsv.gz")

# Check coverage
df_allele[, .(
    mean_DP = mean(DP),
    median_DP = median(DP),
    n_snps = .N
), by = cell][order(-mean_DP)]

# Visualize coverage distribution
hist(df_allele$DP, breaks = 50, main = "Allele Depth Distribution")
abline(v = 5, col = "red", lty = 2)
```

**Quality thresholds:**
- Mean DP ≥ 5: Good coverage
- Mean DP 3-5: Acceptable for Visium
- Mean DP < 3: Consider co-genotyping with scRNA-seq

---

## Quick Start

```r
library(numbat)

# Load data
count_mat <- readRDS("count_matrix.rds")
df_allele <- fread("Sample1_allele_counts.tsv.gz")

# Run Numbat with spatial defaults
nb <- run_numbat_spatial(
    count_mat = count_mat,
    lambdas_ref = ref_hca,
    df_allele = df_allele,
    out_dir = "./numbat_output"
)

# Visualize
nb$plot_phylo_heatmap()
```

---

## Step-by-Step Analysis

### Step 1: Prepare Expression Count Matrix

```r
library(Seurat)

# Load Visium data
seurat_obj <- Load10X_Spatial(
    data.dir = "./filtered_feature_bc_matrix/",
    filename = "filtered_feature_bc_matrix.h5"
)

# Get raw counts
count_mat <- GetAssayData(seurat_obj, slot = "counts")

# Filter to cells with allele data
cells_with_allele <- unique(df_allele$cell)
count_mat <- count_mat[, colnames(count_mat) %in% cells_with_allele]
```

### Step 2: Prepare Reference

**Option A: Use built-in HCA reference (quick start)**

```r
# Load built-in reference
data(ref_hca)
lambdas_ref <- ref_hca
```

**Option B: Build custom reference from normal spots**

```r
# Load normal Visium sample
seurat_normal <- Load10X_Spatial("./normal_visium/")

# Cluster spots
seurat_normal <- SCTransform(seurat_normal)
seurat_normal <- RunPCA(seurat_normal)
seurat_normal <- FindNeighbors(seurat_normal, dims = 1:20)
seurat_normal <- FindClusters(seurat_normal, resolution = 0.5)

# Aggregate by cluster
counts_normal <- GetAssayData(seurat_normal, slot = "counts")
cell_annot <- data.frame(
    cell = colnames(counts_normal),
    group = seurat_normal$seurat_clusters
)

ref_custom <- aggregate_counts(counts_normal, cell_annot)
```

### Step 3: Run Numbat

```r
# Basic run with spatial defaults
nb <- run_numbat_spatial(
    count_mat = count_mat,
    lambdas_ref = ref_hca,
    df_allele = df_allele,
    genome = "hg38",
    max_entropy = 0.8,      # Higher for spatial data
    t = 1e-5,               # Transition probability
    gamma = 20,             # Overdispersion
    min_cells = 50,
    ncores = 4,
    plot = TRUE,
    out_dir = "./numbat_output"
)
```

**Key parameter adjustments:**

| Situation | Parameter Change | Effect |
|-----------|------------------|--------|
| Low allele coverage | `max_entropy = 0.9` | More tolerant |
| Complex karyotype | `t = 1e-6` | More breakpoints |
| Noisy data | `t = 1e-4` | Fewer false positives |
| Small spots | `min_cells = 20` | Smaller clusters |

### Step 4: Inspect Results

```r
# Clone assignments
head(nb$clone_post)
# cell | p_cnv | clone_opt | clone_post_prob

# CNV events per spot
head(nb$joint_post)
# cell | seg | cnv_state | p_cnv | LLR

# Consensus CNV segments
head(nb$segs_consensus)
# seg | CHROM | POS | cnv_state | LLR
```

---

## Visualization

### 1. Phylogeny and CNV Heatmap

```r
# Default plot
nb$plot_phylo_heatmap()

# With custom colors
colors <- c(
    `1` = "gray",      # Normal
    `2` = "#9E0142",   # Clone 1
    `3` = "#F67D4A",   # Clone 2
    `4` = "#F2EA91",   # Clone 3
    `5` = "#77C8A4"    # Clone 4
)
nb$plot_phylo_heatmap(pal_clone = colors)
```

### 2. CNV Probability on Tissue

```r
library(ggplot2)
library(data.table)

# Load spatial coordinates
spots <- fread("./spatial/tissue_positions.csv")

# Plot CNV probability
p <- spots %>%
    left_join(nb$clone_post, by = c("barcode" = "cell")) %>%
    filter(in_tissue == 1) %>%
    ggplot(aes(x = array_row, y = array_col)) +
    geom_point(aes(color = p_cnv), size = 1, alpha = 0.8) +
    scale_color_gradient2(
        low = 'darkgreen',      # Normal
        mid = 'yellow',         # Mixed
        high = 'red3',          # Mutant
        midpoint = 0.5,
        limits = c(0, 1),
        name = "P(CNV)"
    ) +
    theme_bw() +
    coord_fixed() +
    labs(title = "Tumor vs Normal Probability")

print(p)
ggsave("cnv_probability.png", p, width = 8, height = 8, dpi = 300)
```

### 3. Clonal Architecture on Tissue

```r
# Get clone colors from phylogeny plot
colors <- c(
    `1` = "gray",
    `2` = "#9E0142",
    `3` = "#F67D4A",
    `4` = "#F2EA91",
    `5` = "#77C8A4",
    `6` = "#5E4FA2"
)

p_clone <- spots %>%
    left_join(nb$clone_post, by = c("barcode" = "cell")) %>%
    filter(in_tissue == 1) %>%
    mutate(clone_opt = factor(clone_opt)) %>%
    ggplot(aes(x = array_row, y = array_col)) +
    geom_point(aes(color = clone_opt), size = 0.5) +
    scale_color_manual(values = colors, name = "Clone") +
    theme_bw() +
    coord_fixed() +
    labs(title = "Clonal Architecture")

print(p_clone)
```

### 4. Per-Event CNV Spatial Map

```r
# Top CNV events by prevalence
top_cnvs <- nb$joint_post %>%
    filter(LLR > 35 & avg_entropy < 0.6) %>%
    group_by(seg) %>%
    summarise(
        total_p = sum(p_cnv),
        cnv_state = first(cnv_state)
    ) %>%
    arrange(-total_p) %>%
    head(6)

# Plot top events
plot_data <- nb$joint_post %>%
    filter(seg %in% top_cnvs$seg) %>%
    mutate(seg_label = paste0(seg, "(", cnv_state, ")"))

p_events <- spots %>%
    left_join(plot_data, by = c("barcode" = "cell")) %>%
    filter(in_tissue == 1) %>%
    ggplot(aes(x = array_row, y = array_col)) +
    geom_point(aes(color = p_cnv), size = 0.3) +
    scale_color_gradient2(
        low = 'blue',
        mid = 'white',
        high = 'red3',
        midpoint = 0.5,
        limits = c(0, 1),
        name = "P(CNV)"
    ) +
    facet_wrap(~seg_label, ncol = 3) +
    theme_bw() +
    coord_fixed()

print(p_events)
```

### 5. Overlay with H&E Image

```r
library(jpeg)
library(ggpubr)

# Load H&E image
img <- readJPEG("./spatial/tissue_hires_image.jpg")

# Plot with image background
p_he <- spots %>%
    left_join(nb$clone_post, by = c("barcode" = "cell")) %>%
    filter(in_tissue == 1) %>%
    ggplot(aes(x = array_row, y = array_col)) +
    background_image(img) +
    geom_point(aes(color = p_cnv), size = 0.3, alpha = 0.7) +
    scale_color_gradient2(
        low = 'darkgreen',
        mid = 'yellow',
        high = 'red3',
        midpoint = 0.5,
        limits = c(0, 1)
    ) +
    theme_bw() +
    coord_fixed()

print(p_he)
```

---

## Multi-Sample Analysis

### Co-genotyping Multiple Samples

```bash
# Run pileup_and_phase with multiple samples from same patient
Rscript scripts/r/pileup_and_phase.R \
    --label Patient1 \
    --samples "Tumor1,Tumor2,Normal" \
    --bams "T1.bam,T2.bam,N.bam" \
    --barcodes "T1.tsv,T2.tsv,N.tsv" \
    --outdir ./Patient1 \
    --gmap /Eagle_v2.4.1/tables/genetic_map_hg38_withX.txt.gz \
    --snpvcf ~/numbat_ref/genome1K.phase3.SNP_AF5e2.chr1toX.hg38.vcf.gz \
    --paneldir ~/numbat_ref/1000G_hg38 \
    --ncores 8
```

### Analyze Each Sample Separately

```r
# Sample list
samples <- c("Tumor1", "Tumor2", "Normal")

# Run Numbat on each
for (sample in samples) {
    count_mat <- readRDS(paste0(sample, "_counts.rds"))
    df_allele <- fread(paste0("Patient1_", sample, "_allele_counts.tsv.gz"))
    
    nb <- run_numbat_spatial(
        count_mat = count_mat,
        lambdas_ref = ref_hca,
        df_allele = df_allele,
        out_dir = paste0("./numbat_", sample)
    )
    
    saveRDS(nb, paste0(sample, "_numbat.rds"))
}
```

### Compare Across Samples

```r
# Load results
nb_list <- list(
    Tumor1 = readRDS("Tumor1_numbat.rds"),
    Tumor2 = readRDS("Tumor2_numbat.rds"),
    Normal = readRDS("Normal_numbat.rds")
)

# Compare CNV burden
library(purrr)
cnv_summary <- map_dfr(nb_list, function(nb) {
    data.frame(
        mean_p_cnv = mean(nb$clone_post$p_cnv),
        n_clones = length(unique(nb$clone_post$clone_opt))
    )
}, .id = "sample")

print(cnv_summary)
```

---

## Troubleshooting

### No CNVs Detected

**Symptoms:** All spots have p_cnv ~ 0.5 or all assigned to diploid

**Solutions:**
```r
# 1. Check allele coverage
mean(df_allele$DP)  # Should be > 3

# 2. Try more sensitive parameters
nb <- run_numbat_spatial(
    count_mat = count_mat,
    lambdas_ref = ref_hca,
    df_allele = df_allele,
    t = 1e-6,              # More breakpoints
    max_entropy = 0.9,     # More tolerant
    out_dir = "./numbat_sensitive"
)

# 3. Verify reference doesn't contain tumor cells
# Check reference cell type composition
```

### Too Many False Positive CNVs

**Symptoms:** Many small CNV segments, implausible karyotypes

**Solutions:**
```r
# Use more stringent parameters
nb <- run_numbat_spatial(
    count_mat = count_mat,
    lambdas_ref = ref_hca,
    df_allele = df_allele,
    t = 1e-4,              # Fewer breakpoints
    min_LLR = 10,          # Higher evidence threshold
    max_entropy = 0.5,     # Stricter
    out_dir = "./numbat_stringent"
)
```

### Poor Clone Separation

**Symptoms:** All spots in one clone, or clones don't make biological sense

**Solutions:**
```r
# Adjust initial cluster number
nb <- run_numbat_spatial(
    count_mat = count_mat,
    lambdas_ref = ref_hca,
    df_allele = df_allele,
    init_k = 5,            # More initial clusters
    out_dir = "./numbat_more_clusters"
)
```

### Low Allele Coverage

**Symptoms:** mean_DP < 3, many spots with no allele information

**Solutions:**
1. Co-genotype with matching scRNA-seq data
2. Use a priori genotyping from DNA
3. Proceed with higher max_entropy (0.9)

### Memory Issues

**Symptoms:** R crashes during run

**Solutions:**
```r
# Reduce cores
nb <- run_numbat_spatial(..., ncores = 1)

# Filter low-coverage cells first
cells_keep <- df_allele[, .(mean_dp = mean(DP)), by = cell][mean_dp > 3, cell]
count_mat <- count_mat[, cells_keep]
df_allele <- df_allele[cell %in% cells_keep]
```

---

## Complete Example

```r
# ============================================
# Complete Numbat Spatial Analysis Pipeline
# ============================================

library(numbat)
library(Seurat)
library(data.table)
library(ggplot2)
library(dplyr)

# 1. Load spatial data
seurat_obj <- Load10X_Spatial(
    data.dir = "./Visium_Sample1/outs/"
)

# 2. Load allele data (from pileup_and_phase)
df_allele <- fread("Sample1_allele_counts.tsv.gz")

# 3. Prepare count matrix
count_mat <- GetAssayData(seurat_obj, slot = "counts")
cells_keep <- intersect(colnames(count_mat), unique(df_allele$cell))
count_mat <- count_mat[, cells_keep]

# 4. Load reference
data(ref_hca)

# 5. Run Numbat
nb <- run_numbat_spatial(
    count_mat = count_mat,
    lambdas_ref = ref_hca,
    df_allele = df_allele,
    genome = "hg38",
    max_entropy = 0.8,
    t = 1e-5,
    ncores = 4,
    out_dir = "./numbat_Sample1"
)

# 6. Visualize phylogeny
nb$plot_phylo_heatmap()

# 7. Plot on tissue
spots <- fread("./Visium_Sample1/outs/spatial/tissue_positions.csv")

p_cnv <- spots %>%
    left_join(nb$clone_post, by = c("barcode" = "cell")) %>%
    filter(in_tissue == 1) %>%
    ggplot(aes(x = array_row, y = array_col)) +
    geom_point(aes(color = p_cnv), size = 1) +
    scale_color_gradient2(
        low = 'darkgreen', mid = 'yellow', high = 'red3',
        midpoint = 0.5, limits = c(0, 1)
    ) +
    theme_bw() +
    coord_fixed()

print(p_cnv)

# 8. Export results
export_numbat_results(nb, "./results", "Sample1")

# 9. Save Numbat object
saveRDS(nb, "Sample1_numbat.rds")
```

---

## References

1. Gao et al. (2022). Haplotype-aware analysis of somatic copy number variations from single-cell transcriptomes. *Nature Biotechnology*.
2. Li et al. (2025). Numbat-multiome: inferring copy number variations by combining RNA and chromatin accessibility information. *Briefings in Bioinformatics*.
3. Numbat Documentation: https://kharchenkolab.github.io/numbat/
4. Spatial Transcriptomics Tutorial: https://kharchenkolab.github.io/numbat/articles/spatial-rna.html
