# Usage Guide: bio-mrna-seq-qc-preprocessing

## When to Use
Use this skill at the very beginning of a bulk mRNA-seq project, immediately after receiving raw FASTQ files. It ensures reads are high-quality and adapter-free before alignment or pseudo-alignment.

## Inputs
- Raw FASTQ files (`.fastq.gz` or `.fq.gz`)
- Optional: known adapter sequences (fastp auto-detects most Illumina adapters)

## Outputs
- Cleaned FASTQ files (`*_clean_R1.fastq.gz`, `*_clean_R2.fastq.gz`)
- FastQC HTML reports per sample
- fastp JSON/HTML reports per sample
- MultiQC aggregated report (`multiqc/multiqc_report.html`)

## Quick Start
1. Run `fastqc *.fastq.gz` on all raw files.
2. Inspect reports for adapter contamination and low Q30.
3. Run `fastp` with `--detect_adapter_for_pe` to trim adapters and low-quality bases.
4. Aggregate all QC reports with `multiqc`.

## Tips
- **Always check Q30**: per-base Q30 should be > 80% before proceeding.
- **Paired-end**: use `-i/-I` and `-o/-O` flags; single-end uses `-i` and `-o` only.
- **Do not over-trim**: aggressive trimming can reduce mappability.

## Workflow Position
**Upstream**: Raw sequencing data  
**Downstream**: `bio-mrna-seq-alignment` or `bio-mrna-seq-quantification`
