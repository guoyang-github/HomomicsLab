---
name: bio-ribo-seq-workflow
description: End-to-end Ribo-seq analysis workflow from FASTQ to translation efficiency, ORF detection, and ribosome stalling using pure Bash. Use when analyzing ribosome profiling data to study translation.
tool_type: mixed
primary_tool: bash
---

## Version Compatibility

Reference examples tested with: Bash 5.0+, STAR 2.7.11+, Bowtie2 2.5.3+, cutadapt 4.4+, samtools 1.19+, MultiQC 1.20+, R 4.3+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `<tool> --version` then `<tool> --help` to confirm flags
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# Ribo-seq End-to-End Pipeline (Pure Bash)

**"Run the complete Ribo-seq pipeline from FASTQ to ORFs"** → Execute a standardized, end-to-end ribosome profiling workflow using pure Bash. Supports human, mouse, yeast, and plant parameter templates.

## Pipeline Overview

```
FASTQ
  |
  v
Index Building (once per genome)
  |
  v
QC Reporting (FastQC / MultiQC)
  |
  v
Ribo-seq Preprocessing (trim -> size-select -> rRNA removal -> align)
mRNA-seq Preprocessing (trim -> rRNA removal -> align -> count)
  |
  v
Periodicity Analysis (P-site offsets)
  |
  v
Differential Occupancy (DESeq2 / Xtail)
Translation Efficiency (riborex / DESeq2 interaction)
  |
  v
ORF Detection (RiboCode / RibORF)
ORF Quantification (ORFik / DESeq2)
  |
  v
Ribosome Stalling (pause sites, codon occupancy)
Metagene Visualization (publication figures)
  |
  v
Final MultiQC Report
```

## Prerequisites

- `samplesheet.csv` with columns: `sample,condition,ribo_fastq,rna_fastq_r1,rna_fastq_r2`
- Reference files: `genome.fa`, `annotation.gtf`, `rrna.fa`
- All executable scripts are located in `scripts/` (distributed with this skill under `skills/bio-ribo-seq-workflow/scripts/`)

## Quick Start

Run the full pipeline with the main orchestrator:

```bash
bash scripts/run_pipeline.sh human full genome.fa annotation.gtf rrna.fa
```

Or run individual steps:

```bash
bash scripts/project_setup.sh
bash scripts/build_indexes.sh
bash scripts/preprocess_riboseq.sh
```

## Step-by-Step Reference

### Step 0: Project Setup
Creates the standardized results directory tree.

```bash
bash scripts/project_setup.sh riboseq_project human full
```

### Step 1: Index Building
Run once per reference genome. Cleans GTF, builds STAR genome index, and Bowtie2 transcriptome/genome/rRNA indexes.

```bash
bash scripts/build_indexes.sh riboseq_project human genome.fa annotation.gtf rrna.fa
```

### Step 2: QC Reporting (Raw)
Runs FastQC on all raw FASTQ files listed in `samplesheet.csv`.

```bash
bash scripts/run_qc_raw.sh riboseq_project
```

### Step 3: Ribo-seq Preprocessing
Trims adapters, selects footprint length, removes rRNA, and aligns to the genome with STAR.

```bash
bash scripts/preprocess_riboseq.sh riboseq_project CTGTAGGCACCATCAAT 28 32
```

### Step 4: mRNA-seq Preprocessing
Trims paired-end mRNA-seq reads, removes rRNA, and performs splice-aware genome alignment.

```bash
bash scripts/preprocess_rnaseq.sh riboseq_project
```

### Step 5: Periodicity Analysis
Validates 3-nt periodicity with RiboCode and estimates P-site offsets using plastid metagene analysis.

```bash
bash scripts/run_periodicity.sh riboseq_project 28 32
```

### Step 6: Differential Occupancy & TE
Quantifies CDS/exon counts with `featureCounts`, then runs DESeq2.

With paired mRNA-seq (TE analysis):

```bash
featureCounts -T 8 -t CDS -g gene_id -a riboseq_project/results/00_index/annotation_clean.gtf \
  -o riboseq_project/results/04_differential/ribo_counts.tsv \
  riboseq_project/results/02_ribo_preprocessing/*.sorted.bam

featureCounts -T 8 -t exon -g gene_id -a riboseq_project/results/00_index/annotation_clean.gtf \
  -o riboseq_project/results/04_differential/rna_counts.tsv \
  riboseq_project/results/02_rna_preprocessing/*.sorted.bam

Rscript scripts/run_differential_te.R riboseq_project/results/04_differential
```

Ribo-seq only (occupancy analysis):

```bash
Rscript scripts/run_differential_occupancy.R riboseq_project/results/04_differential
```

### Step 7: ORF Detection
Detects translated ORFs with `RiboCode_onestep`.

```bash
bash scripts/detect_orfs.sh riboseq_project 28 32
```

### Step 8: ORF Quantification
Builds an ORF count matrix from BAMs and runs DESeq2.

```bash
Rscript scripts/quantify_orfs.R \
  riboseq_project/results/00_index/annotation_clean.gtf \
  riboseq_project/results/02_ribo_preprocessing \
  riboseq_project/results/03_periodicity \
  riboseq_project/results/06_orf_quantification
```

### Step 9: Ribosome Stalling
Detects codon-level pause sites using P-site corrected counts.

```bash
python3 scripts/detect_stalling.py \
  --bam-dir riboseq_project/results/02_ribo_preprocessing \
  --gtf riboseq_project/results/00_index/annotation_clean.gtf \
  --psite-dir riboseq_project/results/03_periodicity \
  --outdir riboseq_project/results/07_stalling
```

### Step 10: Metagene Visualization
Generates read-length distributions and frame-distribution metagene plots.

```bash
python3 scripts/generate_metagene_plots.py \
  --bam-dir riboseq_project/results/02_ribo_preprocessing \
  --gtf riboseq_project/results/00_index/annotation_clean.gtf \
  --psite-dir riboseq_project/results/03_periodicity \
  --outdir riboseq_project/results/08_visualization
```

### Step 11: Final Report
Aggregates all QC and log files into a MultiQC HTML report.

```bash
bash scripts/generate_final_report.sh riboseq_project
```

## Sample Sheet Format

```csv
sample,condition,ribo_fastq,rna_fastq_r1,rna_fastq_r2
sample1,control,sample1_ribo.fastq.gz,sample1_rna_R1.fastq.gz,sample1_rna_R2.fastq.gz
sample2,control,sample2_ribo.fastq.gz,sample2_rna_R1.fastq.gz,sample2_rna_R2.fastq.gz
sample3,treatment,sample3_ribo.fastq.gz,sample3_rna_R1.fastq.gz,sample3_rna_R2.fastq.gz
sample4,treatment,sample4_ribo.fastq.gz,sample4_rna_R1.fastq.gz,sample4_rna_R2.fastq.gz
```

For `ribo-only` mode, the RNA-seq columns may be left empty.

## Run Modes

| Mode | Steps Executed |
|------|----------------|
| `full` | All 11 steps |
| `ribo-only` | Index, QC, Ribo preprocessing, periodicity, ORF detection + quantification, visualization, report |
| `te-only` | Ribo + mRNA preprocessing, periodicity, differential/TE, report |
| `orf-only` | Ribo preprocessing, periodicity, ORF detection + quantification, visualization |

## Related Skills

- bio-ribo-seq-species-templates - Provides organism-specific parameters
- bio-ribo-seq-index-building - Reference index construction
- bio-ribo-seq-qc-reporting - FastQC / MultiQC integration
- bio-ribo-seq-riboseq-preprocessing - Ribo-seq read preprocessing
- bio-ribo-seq-rna-preprocessing - mRNA-seq preprocessing for TE
- bio-ribo-seq-ribosome-periodicity - P-site offset calculation
- bio-ribo-seq-differential-occupancy - DESeq2 / Xtail differential analysis
- bio-ribo-seq-translation-efficiency - riborex TE calculation
- bio-ribo-seq-orf-detection - RiboCode ORF calling
- bio-ribo-seq-orf-quantification - ORFik ORF quantification
- bio-ribo-seq-ribosome-stalling - Pause site detection
- bio-ribo-seq-metagene-visualization - Publication-quality figures
