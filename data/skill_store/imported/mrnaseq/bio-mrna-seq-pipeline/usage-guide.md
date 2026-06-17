# Usage Guide: bio-mrna-seq-pipeline

## When to Use
Use this skill as the **master orchestrator** when you want to run a complete bulk mRNA-seq analysis from FASTQ files to biological interpretation. It links all `bio-mrna-seq-*` skills into a coherent workflow.

## Inputs
- Raw FASTQ files
- Reference genome, GTF annotation, and sample metadata
- Experimental design (conditions, batches, covariates)

## Outputs
- QC reports, count matrices, DE results, pathway enrichments, and publication-ready plots

## Recommended Directory Structure
```
project/
├── 01_fastq/
├── 02_qc/
├── 03_alignment/
├── 04_counts/
├── 05_de/
├── 06_pathways/
└── multiqc_report/
```

## Quick Start Workflow
1. `bio-mrna-seq-qc-preprocessing` — trim and QC FASTQ files
2. `bio-mrna-seq-alignment` or `bio-mrna-seq-quantification` — generate counts
3. `bio-mrna-seq-count-prep` — clean matrix and align metadata
4. `bio-mrna-seq-qc-exploratory` — PCA, outlier detection
5. `bio-mrna-seq-differential-expression` — identify DEGs
6. `bio-mrna-seq-pathway-enrichment` — functional interpretation

## Tips
- Choose **alignment-based** (STAR → featureCounts) if you need BAMs for splice analysis.
- Choose **alignment-free** (Salmon) for speed and lower compute requirements.
- Always run exploratory QC before DE — catching batch effects early saves time.
- For complex designs (time-series, strong batch effects), invoke the corresponding advanced skill.

## Related Advanced Skills
- `bio-mrna-seq-batch-correction` — strong batch effects
- `bio-mrna-seq-timeseries` — longitudinal designs
- `bio-mrna-seq-splicing` — alternative splicing
