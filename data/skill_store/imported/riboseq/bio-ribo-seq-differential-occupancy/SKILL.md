---
name: bio-ribo-seq-differential-occupancy
description: Detect differential ribosome occupancy from Ribo-seq data alone using DESeq2, Xtail, or Babel. Use when comparing translational changes without paired RNA-seq.
tool_type: mixed
primary_tool: DESeq2
---

## Version Compatibility

Reference examples tested with: DESeq2 1.42+, Xtail 1.1.5+, Babel 1.0+, pandas 2.2+

Before using code patterns, verify installed versions match. If versions differ:
- R: `packageVersion('<pkg>')` then `?function_name` to verify parameters
- Python: `pip show <package>` then `help(module.function)` to check signatures

If code throws errors, introspect the installed package and adapt the example to match the actual API rather than retrying.

# Differential Ribosome Occupancy

**"Find genes with differential ribosome occupancy between conditions"** → Compare Ribo-seq counts across conditions to identify genes with altered ribosome density, independent of RNA abundance changes.

## Output Directory Structure

```
results/04_differential/
├── deseq2_occupancy_results.csv
├── xtail_results.csv
└── babel_results.csv
```

## Step 1: Prepare Count Matrix

Ribo-seq counts should be CDS-level, ideally P-site corrected, generated from aligned BAM files.

```bash
featureCounts -T 8 -t CDS -g gene_id \
  -a results/00_index/annotation_clean.gtf \
  -o results/04_differential/ribo_counts.tsv \
  results/02_ribo_preprocessing/*.sorted.bam
```

## Step 2: Run DESeq2 for Differential Occupancy

```bash
Rscript scripts/run_deseq2_occupancy.R \
  results/04_differential/ribo_counts.tsv \
  results/04_differential/deseq2_occupancy_results.csv \
  results/04_differential/sample_conditions.tsv
```

## Step 3: Run Xtail (with paired RNA-seq)

```bash
Rscript scripts/run_xtail.R \
  results/04_differential/ribo_counts.tsv \
  results/02_rna_preprocessing/counts/rna_counts_matrix.tsv \
  results/04_differential/xtail_results.csv
```

## Step 4: Run Babel for Differential Translation

```bash
Rscript scripts/run_babel.R \
  results/04_differential/ribo_counts.tsv \
  results/02_rna_preprocessing/counts/rna_counts_matrix.tsv \
  results/04_differential/babel_results.csv
```

## Step 5: Run PyDESeq2 (Python alternative)

```bash
python scripts/run_pydeseq2.py \
  --counts results/04_differential/ribo_counts.tsv \
  --out results/04_differential/pydeseq2_occupancy_results.csv
```

## Result Interpretation

| Metric | Interpretation |
|--------|----------------|
| log2FoldChange > 0 | Increased ribosome occupancy in treatment |
| log2FoldChange < 0 | Decreased ribosome occupancy in treatment |
| padj < 0.05 | Statistically significant |
| TE change (Xtail/Babel) | Translational regulation independent of transcription |

## Related Skills

- bio-ribo-seq-riboseq-preprocessing - Provides aligned BAMs for count matrix
- bio-ribo-seq-rna-preprocessing - Provides RNA-seq counts for Xtail / Babel
- bio-ribo-seq-translation-efficiency - Overlaps conceptually but focuses on TE ratios
