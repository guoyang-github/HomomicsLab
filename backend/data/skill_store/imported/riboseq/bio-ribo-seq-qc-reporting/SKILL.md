---
name: bio-ribo-seq-qc-reporting
description: Generate quality control reports for Ribo-seq data including FastQC, MultiQC, length distribution, and periodicity summaries. Use after preprocessing and periodicity analysis.
tool_type: mixed
primary_tool: MultiQC
---

## Version Compatibility

Reference examples tested with: FastQC 0.12+, MultiQC 1.20+, matplotlib 3.8+, numpy 1.26+

Before using code patterns, verify installed versions match. If versions differ:
- CLI: `<tool> --version` then `<tool> --help` to confirm flags
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# Ribo-seq QC and Reporting

**"Generate QC reports for my Ribo-seq data"** → Run FastQC on raw and trimmed reads, aggregate with MultiQC, plot read length distributions, and compile periodicity summaries into a single HTML report.

## Output Directory Structure

```
results/01_qc/
├── fastqc_raw/
├── fastqc_trimmed/
├── multiqc_report.html
├── length_distributions/
│   └── {sample}_length_dist.pdf
└── periodicity_summary.pdf
```

## Step 1: FastQC on Raw and Trimmed Reads

```bash
bash scripts/run_fastqc.sh raw results/02_ribo_preprocessing results/01_qc
```

## Step 2: MultiQC Aggregation

```bash
bash scripts/run_multiqc.sh results/01_qc \
  results/01_qc/fastqc_raw/ \
  results/01_qc/fastqc_trimmed/ \
  results/02_ribo_preprocessing/
```

## Step 3: Read Length Distribution Plot

```bash
python scripts/plot_length_distribution.py \
  --bam results/02_ribo_preprocessing/sample1.sorted.bam \
  --sample sample1 \
  --outdir results/01_qc/length_distributions
```

## Step 4: Periodicity Summary Plot

```bash
python scripts/plot_periodicity_summary.py \
  --jsons results/03_periodicity/*_psite_offsets.json \
  --out results/01_qc/periodicity_summary.pdf
```

## Step 5: Generate Summary Report Table

```bash
python scripts/generate_qc_summary.py \
  --samplesheet samplesheet.csv \
  --out results/01_qc/qc_summary.csv
```

## Related Skills

- bio-ribo-seq-riboseq-preprocessing - Provides trimmed BAM and flagstat inputs
- bio-ribo-seq-ribosome-periodicity - Provides psite_offsets.json inputs
